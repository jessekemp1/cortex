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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Paths
CORTEX_DIR = Path.home() / ".cortex"
BATCH_DIR = CORTEX_DIR / "batch"
RESULTS_DIR = BATCH_DIR / "results"
SESSION_CACHE = CORTEX_DIR / "session_cache.json"
BRIEFING_CACHE = CORTEX_DIR / "briefing_cache.json"


def get_overnight_results() -> List[Dict[str, Any]]:
    """
    Fetch batch job results from overnight processing.

    Returns:
        List of result dictionaries with job metadata and outcomes
    """
    results = []

    # Check for completed results files
    if not RESULTS_DIR.exists():
        return results

    cutoff = datetime.now() - timedelta(hours=12)

    for result_file in RESULTS_DIR.glob("*.json"):
        try:
            data = json.loads(result_file.read_text())

            # Check if this is from overnight
            completed_at = data.get("completed_at")
            if completed_at:
                completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                if completed_dt.replace(tzinfo=None) > cutoff:
                    results.append(data)
        except Exception:
            continue

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
        "other": []
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
        # Check for security issues
        output = result.get("output", "")
        if isinstance(output, str):
            # Look for severity indicators
            if any(word in output.lower() for word in ["critical", "high severity", "vulnerability"]):
                findings.append({
                    "type": "security",
                    "priority": "high",
                    "job_id": result.get("job_id"),
                    "summary": _extract_first_issue(output),
                    "source": result.get("title", "Unknown job")
                })

            # Look for test failures
            if any(word in output.lower() for word in ["failed", "failing", "broken"]):
                findings.append({
                    "type": "test",
                    "priority": "medium",
                    "job_id": result.get("job_id"),
                    "summary": _extract_first_issue(output),
                    "source": result.get("title", "Unknown job")
                })

        # Check status
        status = result.get("status", "")
        if status == "failed":
            findings.append({
                "type": "batch_failure",
                "priority": "low",
                "job_id": result.get("job_id"),
                "summary": result.get("error", "Unknown error"),
                "source": result.get("title", "Unknown job")
            })

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
            "success_rate": (succeeded / total * 100) if total > 0 else 0
        },
        "categories": {
            cat: len(items) for cat, items in categories.items() if items
        },
        "key_findings": findings,
        "tokens": {
            "total_used": total_tokens,
            "estimated_savings": int(savings_estimate)
        },
        "alerts": []
    }

    # Add alerts for critical findings
    critical_findings = [f for f in findings if f["priority"] == "high"]
    if critical_findings:
        summary["alerts"].append({
            "level": "warning",
            "message": f"{len(critical_findings)} high-priority issues found overnight",
            "details": [f["summary"] for f in critical_findings[:3]]
        })

    if failed > 0:
        summary["alerts"].append({
            "level": "info",
            "message": f"{failed} batch jobs failed overnight",
            "action": "Run /batch-status to investigate"
        })

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
                "key_alerts": len(briefing.get("alerts", []))
            },
            "action_items": [
                f["summary"] for f in briefing.get("key_findings", [])[:3]
            ],
            "batch_health": "healthy" if briefing["overnight_jobs"]["success_rate"] >= 80 else "degraded"
        }
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
            icon = "🔴" if finding["priority"] == "high" else "🟡" if finding["priority"] == "medium" else "🔵"
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


def main():
    """Main entry point for morning processor"""
    print(f"Morning processor starting at {datetime.now().isoformat()}")

    # Get overnight results
    results = get_overnight_results()

    if not results:
        print("No overnight batch results found")
        return

    # Generate briefing
    briefing = generate_briefing_summary(results)

    # Update caches
    update_session_cache(briefing)
    save_briefing_cache(briefing)

    # Print summary
    print_summary(briefing)

    print("Morning processing complete!")


if __name__ == "__main__":
    main()
