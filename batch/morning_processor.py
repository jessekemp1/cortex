#!/usr/bin/env python3
"""
Morning Batch Processor

Runs at 6 AM to:
1. Process completed batch job results
2. Generate morning briefing summary
3. Update session cache for fast context loading
4. Alert on any overnight failures

This feeds directly into /briefing command results.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

# Paths
CORTEX_DIR = Path.home() / ".cortex"
BATCH_DIR = CORTEX_DIR / "batch"
RESULTS_DIR = BATCH_DIR / "results"
# The actual batch results live under ~/.cortex/batches/ (plural), not ~/.cortex/batch/results/
# monitor_batch_overnight.py and queue_manager write results to ~/.cortex/batches/
BATCHES_DIR = CORTEX_DIR / "batches"
SESSION_CACHE = CORTEX_DIR / "session_cache.json"
BRIEFING_CACHE = CORTEX_DIR / "briefing_cache.json"


def get_overnight_v2_lessons() -> List[Dict[str, Any]]:
    """Read LESSON nodes created in last 24h from ContextGraph."""
    try:
        from cortex.engines.synthesis import ContextGraph, NodeType

        graph = ContextGraph(storage_path=Path.home() / ".cortex" / "graph")
        all_nodes = (
            graph.get_nodes_by_type(NodeType.LESSON) if hasattr(graph, "get_nodes_by_type") else []
        )
        cutoff = datetime.now() - timedelta(hours=24)
        recent: List[Dict[str, Any]] = []
        for n in all_nodes:
            try:
                updated = n.updated_at if hasattr(n, "updated_at") else n.created_at
                if updated > cutoff:
                    recent.append({"name": n.name, "data": n.data, "type": str(n.type)})
            except Exception:
                continue
        return recent
    except Exception:
        return []


def get_overnight_results() -> List[Dict[str, Any]]:
    """
    Fetch batch job results from overnight processing.

    Searches multiple result locations:
    1. ~/.cortex/batch/results/ (legacy path for inline results)
    2. ~/.cortex/batches/remediation_queue.json (completed jobs from queue_manager)
    3. ~/.cortex/batches/msgbatch_*_results/ (results from monitor_batch_overnight.py)

    Returns:
        List of result dictionaries with job metadata and outcomes
    """
    results = []
    cutoff = datetime.now() - timedelta(hours=12)

    # Source 1: Legacy results directory (~/.cortex/batch/results/)
    if RESULTS_DIR.exists():
        for result_file in RESULTS_DIR.glob("*.json"):
            try:
                data = json.loads(result_file.read_text())
                completed_at = data.get("completed_at")
                if completed_at:
                    completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    if completed_dt.replace(tzinfo=None) > cutoff:
                        results.append(data)
            except Exception:
                continue

    # Source 2: Completed jobs from remediation_queue.json
    queue_file = BATCHES_DIR / "remediation_queue.json"
    if queue_file.exists():
        try:
            queue_data = json.loads(queue_file.read_text())
            for job in queue_data.get("priority_jobs", []):
                if job.get("status") == "completed":
                    completed_at = job.get("completed_at")
                    if completed_at:
                        try:
                            completed_dt = datetime.fromisoformat(
                                completed_at.replace("Z", "+00:00")
                            )
                            if completed_dt.replace(tzinfo=None) > cutoff:
                                results.append(
                                    {
                                        "job_id": job.get("id"),
                                        "title": job.get("description", ""),
                                        "status": "completed",
                                        "completed_at": completed_at,
                                        "source": job.get("source", "other"),
                                        "type": job.get("source", "other"),
                                        "output": json.dumps(job.get("final_status", {})),
                                        "tokens_used": job.get("estimated_total_tokens", 0),
                                    }
                                )
                        except (ValueError, TypeError):
                            continue
        except Exception:
            pass

    # Source 3: Batch result directories (~/.cortex/batches/msgbatch_*_results/)
    if BATCHES_DIR.exists():
        for result_dir in BATCHES_DIR.glob("msgbatch_*_results"):
            for result_file in result_dir.glob("*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(result_file.stat().st_mtime)
                    if file_mtime > cutoff:
                        data = json.loads(result_file.read_text())
                        # Normalize result format
                        if isinstance(data, list):
                            for item in data:
                                results.append(
                                    {
                                        "job_id": item.get("custom_id", result_file.stem),
                                        "title": item.get("custom_id", result_file.stem),
                                        "status": item.get("status", "completed"),
                                        "completed_at": file_mtime.isoformat(),
                                        "source": "research",
                                        "type": "batch_api",
                                        "output": json.dumps(item.get("result", {}))[:500],
                                        "tokens_used": 0,
                                    }
                                )
                        elif isinstance(data, dict):
                            results.append(
                                {
                                    "job_id": data.get("custom_id", result_file.stem),
                                    "title": data.get("custom_id", result_file.stem),
                                    "status": data.get("status", "completed"),
                                    "completed_at": file_mtime.isoformat(),
                                    "source": "research",
                                    "type": "batch_api",
                                    "output": json.dumps(data)[:500],
                                    "tokens_used": 0,
                                }
                            )
                except Exception:
                    continue

    # Source 4: Completed tasks from unified SQLite queue (BatchTaskQueue)
    try:
        from intelligence.process_monitor.batch_queue import BatchTaskQueue, TaskState
    except ImportError:
        try:
            from cortex.intelligence.process_monitor.batch_queue import (
                BatchTaskQueue,
                TaskState,
            )
        except ImportError:
            TaskState = None

    if TaskState is not None:
        try:
            queue = BatchTaskQueue()
            # Get recently completed tasks (within cutoff window)
            completed_tasks = queue.get_tasks_by_state(TaskState.COMPLETED)
            for task in completed_tasks:
                completed_at = task.completed_at
                if completed_at and completed_at > cutoff:
                    # Deduplicate: skip if we already have this job_id from other sources
                    existing_ids = {r.get("job_id") for r in results}
                    if task.task_id not in existing_ids:
                        results.append(
                            {
                                "job_id": task.task_id,
                                "title": task.description,
                                "status": "completed",
                                "completed_at": completed_at.isoformat(),
                                "source": task.metadata.get("source", task.task_type),
                                "type": task.task_type,
                                "output": (task.result_text or "")[:500],
                                "tokens_used": (task.token_input or 0) + (task.token_output or 0),
                            }
                        )
        except Exception:
            pass

    return results


def categorize_results(results: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Categorize results by type for briefing.

    Args:
        results: Raw result list

    Returns:
        Dict with categorized results
    """
    categories = {
        "security": [],
        "quality": [],
        "tests": [],
        "docs": [],
        "research": [],
        "other": [],
    }

    for result in results:
        source = result.get("source", "other")
        job_type = result.get("type", "other")

        # Map to category
        if source == "security" or "security" in job_type.lower():
            categories["security"].append(result)
        elif source == "pattern" or "quality" in job_type.lower():
            categories["quality"].append(result)
        elif "test" in job_type.lower():
            categories["tests"].append(result)
        elif source == "docs" or "doc" in job_type.lower():
            categories["docs"].append(result)
        elif source == "research":
            categories["research"].append(result)
        else:
            categories["other"].append(result)

    return categories


def extract_key_findings(results: List[Dict]) -> List[Dict]:
    """
    Extract key findings from batch results.

    Identifies:
    - Security vulnerabilities
    - Test failures
    - High-priority issues
    - Actionable recommendations

    Returns:
        List of key findings with priority
    """
    findings = []

    for result in results:
        # Extract text from either legacy 'output' or new 'results[].response_text'
        output = result.get("output", "")
        if not output and "results" in result:
            # New format: extract response_text from results array
            for r in result.get("results", []):
                if r.get("response_text"):
                    output = r["response_text"]
                    break
        if isinstance(output, str):
            # Look for severity indicators
            if any(
                word in output.lower() for word in ["critical", "high severity", "vulnerability"]
            ):
                findings.append(
                    {
                        "type": "security",
                        "priority": "high",
                        "job_id": result.get("job_id"),
                        "summary": _extract_first_issue(output),
                        "source": result.get("title", "Unknown job"),
                    }
                )

            # Look for test failures
            if any(word in output.lower() for word in ["failed", "failing", "broken"]):
                findings.append(
                    {
                        "type": "test",
                        "priority": "medium",
                        "job_id": result.get("job_id"),
                        "summary": _extract_first_issue(output),
                        "source": result.get("title", "Unknown job"),
                    }
                )

        # Check status
        status = result.get("status", "")
        if status == "failed":
            findings.append(
                {
                    "type": "batch_failure",
                    "priority": "low",
                    "job_id": result.get("job_id"),
                    "summary": result.get("error", "Unknown error"),
                    "source": result.get("title", "Unknown job"),
                }
            )

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda x: priority_order.get(x["priority"], 3))

    return findings[:10]  # Top 10


def _extract_first_issue(text: str) -> str:
    """Extract first issue/finding from output text"""
    lines = text.split("\n")

    for line in lines:
        # Look for bullet points or numbered items
        line = line.strip()
        if line.startswith(("- ", "* ", "• ", "1.", "1)")):
            return line[:200]  # Truncate

        # Look for issue keywords
        if any(word in line.lower() for word in ["found", "detected", "issue", "warning"]):
            return line[:200]

    return text[:200] if text else "No details available"


def generate_briefing_summary(results: List[Dict]) -> Dict[str, Any]:
    """
    Generate morning briefing summary.

    Args:
        results: Overnight batch results

    Returns:
        Briefing summary for /briefing command
    """
    categories = categorize_results(results)
    findings = extract_key_findings(results)

    # Count successes and failures
    total = len(results)
    succeeded = len([r for r in results if r.get("status") == "completed"])
    failed = total - succeeded

    # Calculate token savings
    total_tokens = sum(r.get("tokens_used", 0) for r in results)
    savings_estimate = total_tokens * 0.5  # 50% batch discount

    summary = {
        "generated_at": datetime.now().isoformat(),
        "overnight_jobs": {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "success_rate": (succeeded / total * 100) if total > 0 else 0,
        },
        "categories": {cat: len(items) for cat, items in categories.items() if items},
        "key_findings": findings,
        "tokens": {"total_used": total_tokens, "estimated_savings": int(savings_estimate)},
        "alerts": [],
    }

    # V2: Add overnight lessons from ContextGraph
    summary["v2_lessons"] = get_overnight_v2_lessons()

    # Add alerts for critical findings
    critical_findings = [f for f in findings if f["priority"] == "high"]
    if critical_findings:
        summary["alerts"].append(
            {
                "level": "warning",
                "message": f"{len(critical_findings)} high-priority issues found overnight",
                "details": [f["summary"] for f in critical_findings[:3]],
            }
        )

    if failed > 0:
        summary["alerts"].append(
            {
                "level": "info",
                "message": f"{failed} batch jobs failed overnight",
                "action": "Run /batch-status to investigate",
            }
        )

    return summary


def update_session_cache(briefing: Dict[str, Any]):
    """
    Update session cache for fast context loading.

    The session_start hook reads this cache to provide
    instant context without slow API calls.
    """
    cache = {
        "cached_at": datetime.now().isoformat(),
        "context": {
            "overnight_summary": {
                "jobs_run": briefing["overnight_jobs"]["total"],
                "success_rate": briefing["overnight_jobs"]["success_rate"],
                "key_alerts": len(briefing.get("alerts", [])),
            },
            "action_items": [f["summary"] for f in briefing.get("key_findings", [])[:3]],
            "batch_health": (
                "healthy" if briefing["overnight_jobs"]["success_rate"] >= 80 else "degraded"
            ),
        },
    }

    SESSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_CACHE.write_text(json.dumps(cache, indent=2))


def save_briefing_cache(briefing: Dict[str, Any]):
    """Save briefing cache for /briefing command"""
    BRIEFING_CACHE.parent.mkdir(parents=True, exist_ok=True)
    BRIEFING_CACHE.write_text(json.dumps(briefing, indent=2))


def print_summary(briefing: Dict[str, Any]):
    """Print human-readable summary"""
    print("╔══════════════════════════════════════════════════════╗")
    print("║         MORNING BATCH PROCESSOR - SUMMARY           ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    jobs = briefing["overnight_jobs"]
    print(f"📊 Overnight Jobs: {jobs['total']} total")
    print(f"   ✅ Succeeded: {jobs['succeeded']}")
    print(f"   ❌ Failed: {jobs['failed']}")
    print(f"   📈 Success Rate: {jobs['success_rate']:.0f}%")
    print()

    if briefing["categories"]:
        print("📁 By Category:")
        for cat, count in briefing["categories"].items():
            print(f"   {cat}: {count}")
        print()

    if briefing["key_findings"]:
        print("🔍 Key Findings:")
        for finding in briefing["key_findings"][:5]:
            icon = (
                "🔴"
                if finding["priority"] == "high"
                else "🟡"
                if finding["priority"] == "medium"
                else "🔵"
            )
            print(f"   {icon} [{finding['type']}] {finding['summary'][:60]}...")
        print()

    if briefing["alerts"]:
        print("⚠️  Alerts:")
        for alert in briefing["alerts"]:
            print(f"   {alert['message']}")
        print()

    tokens = briefing["tokens"]
    print(f"💰 Token Savings: ~{tokens['estimated_savings']:,} tokens (50% batch discount)")
    print()


def run_pending_watches() -> List[Dict[str, Any]]:
    """Run any pending Cortex Watch tasks and return results.

    Watch tasks are scheduled verifications created during sessions
    that need to execute between sessions and report back.
    """
    try:
        from cortex.watches import format_results, list_pending, run_watch
    except ImportError:
        try:
            import sys

            sys.path.insert(0, str(Path.home() / "Dev"))
            from cortex.watches import format_results, list_pending, run_watch
        except ImportError:
            print("  (watches module not available)")
            return []

    pending = list_pending()
    if not pending:
        print("  No pending watch tasks")
        return []

    print(f"  Found {len(pending)} pending watch tasks")
    results = []

    watches_dir = Path.home() / ".cortex" / "watches" / "pending"
    for watch_file in sorted(watches_dir.glob("*.json")):
        print(f"  Running: {watch_file.stem}...")
        result = run_watch(watch_file)
        if result.get("status") == "skipped":
            print(f"    Skipped: {result.get('reason')}")
            continue
        status = result.get("status", "unknown")
        print(f"    Result: {status.upper()}")
        results.append(result)

    if results:
        print()
        print(format_results(results))

    return results


def retrieve_completed_batches():
    """
    Retrieve actual LLM responses for any submitted-but-not-retrieved batches.

    Runs before get_overnight_results() so that fresh content is available
    for the morning briefing. Uses unified BatchRetriever (SQLite-first),
    falling back to legacy BatchQueueManager if needed.
    """
    # Primary: unified BatchRetriever (SQLite-first pipeline)
    try:
        from batch.retriever import BatchRetriever

        retriever = BatchRetriever()
        stats = retriever.retrieve_completed()
        print(
            f"  Retrieved {stats.tasks_completed} completed, "
            f"{stats.tasks_failed} failed "
            f"({stats.batches_checked} batches checked)"
        )
        if stats.errors:
            for err in stats.errors[:3]:
                print(f"    Error: {err}")
        return
    except ImportError:
        pass
    except Exception as e:
        print(f"  BatchRetriever error: {e}")

    # Fallback: legacy BatchQueueManager (JSON-based)
    try:
        from batch.queue_manager import BatchQueueManager

        manager = BatchQueueManager()
        manager.monitor_and_update_status()
        print("  (legacy) Checked submitted batches for completed results")
    except ImportError:
        print("  (retriever not available, skipping batch retrieval)")
    except Exception as e:
        print(f"  Error retrieving batch results: {e}")


def _validate_env() -> None:
    """Validate required environment variables before doing any API work.

    Exits with a clear error message if required vars are missing, rather
    than failing silently mid-run (the failure mode that killed 6 weeks of batch cycles).
    """
    required = {
        "ANTHROPIC_API_KEY": "Anthropic API calls in batch processing",  # pragma: allowlist secret
    }
    missing = [f"  {k} ({v})" for k, v in required.items() if not os.getenv(k)]
    if missing:
        print("FATAL: Missing required environment variables:", file=sys.stderr)
        for m in missing:
            print(m, file=sys.stderr)
        print(
            "\nFix: add EnvironmentVariables to com.cortex.batch.morning.plist",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    """Main entry point for morning processor"""
    _validate_env()
    print(f"Morning processor starting at {datetime.now().isoformat()}")

    # Phase 0: Retrieve LLM responses for completed API batches
    print("\n--- Batch Retrieval ---")
    retrieve_completed_batches()

    # Phase 1: Run pending watch tasks (scheduled verifications)
    print("\n--- Watch Tasks ---")
    watch_results = run_pending_watches()

    # Phase 2: Get overnight batch results
    print("\n--- Batch Results ---")
    results = get_overnight_results()

    # Generate briefing (even if no batch results — watches may have results)
    briefing = (
        generate_briefing_summary(results)
        if results
        else {
            "generated_at": datetime.now().isoformat(),
            "overnight_jobs": {"total": 0, "succeeded": 0, "failed": 0, "success_rate": 0},
            "categories": {},
            "key_findings": [],
            "tokens": {"total_used": 0, "estimated_savings": 0},
            "alerts": [],
        }
    )

    # Inject watch results into briefing
    if watch_results:
        briefing["watch_results"] = watch_results
        for wr in watch_results:
            if wr.get("status") == "fail":
                briefing["alerts"].append(
                    {
                        "level": "warning",
                        "message": f"Watch FAILED: {wr['name']} — {wr.get('context', '')[:80]}",
                        "action": "Review watch results in briefing",
                    }
                )
            elif wr.get("status") == "pass":
                briefing["alerts"].append(
                    {
                        "level": "info",
                        "message": f"Watch PASSED: {wr['name']}",
                    }
                )

    # Update caches
    update_session_cache(briefing)
    save_briefing_cache(briefing)

    # Print summary
    if results:
        print_summary(briefing)
    else:
        print("  No overnight batch results found")

    # Phase 3: Seed intelligence layer from overnight results
    print("\n--- Intelligence Seeding ---")
    try:
        import sys as _sys

        _sys.path.insert(0, str(Path.home() / "Dev"))
        _sys.path.insert(0, str(Path.home() / "Dev" / "cortex"))
        from cortex.intelligence.spec_knowledge_base import SpecKnowledgeBase
        from cortex.portfolio_memory import PortfolioMemory

        kb = SpecKnowledgeBase()
        before = kb.collection.count()

        # Import seeder functions
        _script = Path.home() / "Dev" / "cortex" / "scripts" / "seed_intelligence.py"
        import importlib.util as _ilu

        _spec = _ilu.spec_from_file_location("seed_intelligence", _script)
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        projects = ["cortex", "Vortex/backend", "Vortex/frontend", "alpha_arena", "pupil"]
        n1 = _mod.seed_from_outcomes(kb)
        n2 = _mod.seed_from_git(kb, projects)
        n3 = _mod.seed_from_goals(kb)
        after = kb.collection.count()
        print(f"  SpecKnowledgeBase: {before} -> {after} docs (+{after - before})")
        print(f"  Indexed: {n1} outcomes, {n2} git histories, {n3} goals")

        portfolio = PortfolioMemory()
        n4 = _mod.seed_portfolio_memory(portfolio, projects)
        print(f"  PortfolioMemory: seeded {n4} projects")
    except Exception as _e:
        print(f"  Intelligence seeding failed (non-fatal): {_e}")

    print("\nMorning processing complete!")


if __name__ == "__main__":
    main()
