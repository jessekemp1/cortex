#!/usr/bin/env python3
"""
Intelligent Batch Orchestrator

Collaborates with Cortex to maximize overnight batch API utilization.
Analyzes pending work, calculates capacity, and fills the queue intelligently.

Key Features:
- Analyzes Cortex goals and identifies batch-able work
- Calculates overnight capacity (10pm-6am window)
- Respects batch API limits (100K input, 8K output tokens)
- Prioritizes work based on impact and urgency
- Generates optimal batch job queue
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure parent directory is on path so "from batch.xxx import ..." works
# when this script is run directly (e.g., by launchd)
_cortex_root = str(Path(__file__).resolve().parent.parent)
if _cortex_root not in sys.path:
    sys.path.insert(0, _cortex_root)


@dataclass
class BatchCapacity:
    """Batch API capacity limits and calculations"""

    # Batch API limits (per Claude API docs)
    max_input_tokens_per_request: int = 100_000
    max_output_tokens_per_request: int = 8_000
    max_concurrent_batches: int = 5

    # Overnight window
    overnight_start_hour: int = 22  # 10 PM
    overnight_end_hour: int = 6     # 6 AM
    overnight_hours: int = 8

    # Token budget constraints
    weekly_token_budget: int = 60 * 60 * 15_000  # 60 hours @ 15K tokens/hour
    current_weekly_usage: int = 0

    def available_overnight_tokens(self) -> int:
        """Calculate available tokens for overnight batch processing"""
        # Conservative: use 40% of weekly budget for overnight batches
        overnight_allocation = self.weekly_token_budget * 0.40
        remaining = overnight_allocation - self.current_weekly_usage
        return max(0, int(remaining))

    def max_jobs_by_tokens(self, avg_tokens_per_job: int = 50_000) -> int:
        """Calculate max jobs that fit in overnight token budget"""
        available = self.available_overnight_tokens()
        return available // avg_tokens_per_job

    def max_jobs_by_time(self, avg_hours_per_job: float = 0.5) -> int:
        """Calculate max jobs that fit in overnight time window"""
        # Batch jobs complete within 24h, but we want results by morning
        # Conservative: assume 2 hours for processing
        processing_window = self.overnight_hours - 2
        return int(processing_window / avg_hours_per_job)


@dataclass
class BatchWorkItem:
    """A potential batch job to be queued"""

    id: str
    title: str
    description: str
    prompt: str
    priority: str  # "immediate", "high", "normal", "low" (matches CLI)
    estimated_input_tokens: int
    estimated_output_tokens: int
    source: str  # "goal", "pattern", "security", "docs", "research"
    project: Optional[str] = None
    files: List[str] = field(default_factory=list)
    deadline_hours: int = 12

    @property
    def total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens

    @property
    def priority_score(self) -> int:
        """Numeric priority for sorting (higher = more important)"""
        scores = {"immediate": 100, "high": 75, "normal": 50, "low": 25}
        return scores.get(self.priority, 0)


class IntelligentBatchOrchestrator:
    """
    Orchestrates batch job creation by analyzing Cortex state
    and generating optimal overnight batch queue.
    """

    def __init__(self, root_dir: str = "/Users/jesse.kemp/Dev"):
        self.root_dir = Path(root_dir)
        self.cortex_dir = self.root_dir / "cortex"
        self.capacity = BatchCapacity()
        self.work_items: List[BatchWorkItem] = []

    def analyze_cortex_state(self) -> Dict[str, Any]:
        """Get current Cortex state (goals, projects, blockers)"""
        try:
            result = subprocess.run(
                ["python", str(self.cortex_dir / "cli.py"), "status"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse output for key metrics
            output = result.stdout
            state = {
                "active_projects": self._extract_metric(output, "Active"),
                "priority_a_goals": self._extract_metric(output, "Priority A"),
                "priority_b_goals": self._extract_metric(output, "Priority B"),
                "pending_goals": self._extract_metric(output, "pending"),
            }
            return state
        except Exception as e:
            print(f"Warning: Failed to get Cortex state: {e}", file=sys.stderr)
            return {}

    def _extract_metric(self, text: str, pattern: str) -> int:
        """Extract numeric metric from status output"""
        for line in text.split("\n"):
            if pattern in line:
                # Extract first number from line
                numbers = [int(s) for s in line.split() if s.isdigit()]
                if numbers:
                    return numbers[0]
        return 0

    def generate_work_items(self) -> List[BatchWorkItem]:
        """Generate batch work items from Cortex intelligence"""
        work_items = []
        state = self.analyze_cortex_state()

        # 1. Security & Vulnerability Scans (Critical)
        active_projects = state.get("active_projects", 0)
        if active_projects > 0:
            work_items.append(BatchWorkItem(
                id="security-scan",
                title="Overnight Security Audit",
                description="Scan all active projects for vulnerabilities, exposed secrets, security anti-patterns",
                prompt=f"Perform comprehensive security audit across {active_projects} active projects. Check for: SQL injection, XSS, exposed credentials, insecure dependencies, missing input validation.",
                priority="immediate",
                estimated_input_tokens=30_000,
                estimated_output_tokens=5_000,
                source="security",
                deadline_hours=8
            ))

        # 2. Code Quality & Pattern Analysis (High)
        work_items.append(BatchWorkItem(
            id="code-quality-scan",
            title="Code Quality Analysis",
            description="Analyze code quality across active projects: complexity, duplication, anti-patterns",
            prompt=f"Analyze code quality across {active_projects} projects. Identify: high complexity functions (>50 lines), code duplication, anti-patterns, circular imports, missing error handling.",
            priority="high",
            estimated_input_tokens=40_000,
            estimated_output_tokens=6_000,
            source="pattern",
            deadline_hours=12
        ))

        # 3. Test Coverage Analysis (High)
        work_items.append(BatchWorkItem(
            id="test-coverage-analysis",
            title="Test Coverage Gap Analysis",
            description="Identify untested code paths and missing test cases",
            prompt=f"Analyze test coverage across {active_projects} projects. Identify: critical paths without tests, edge cases not covered, integration test gaps, missing error scenario tests.",
            priority="high",
            estimated_input_tokens=35_000,
            estimated_output_tokens=5_000,
            source="pattern",
            deadline_hours=12
        ))

        # 4. Documentation Completeness (Medium)
        work_items.append(BatchWorkItem(
            id="docs-completeness",
            title="Documentation Completeness Audit",
            description="Identify missing or outdated documentation",
            prompt=f"Audit documentation across {active_projects} projects. Check: missing README sections, undocumented API endpoints, outdated examples, missing function docstrings for public APIs.",
            priority="normal",
            estimated_input_tokens=25_000,
            estimated_output_tokens=4_000,
            source="docs",
            deadline_hours=24
        ))

        # 5. Dependency Audit (Medium)
        work_items.append(BatchWorkItem(
            id="dependency-audit",
            title="Dependency Version Audit",
            description="Check for outdated dependencies and version conflicts",
            prompt=f"Audit dependencies across {active_projects} projects. Check: outdated packages, security vulnerabilities in dependencies, version conflicts, unused dependencies.",
            priority="normal",
            estimated_input_tokens=20_000,
            estimated_output_tokens=3_000,
            source="security",
            deadline_hours=24
        ))

        # 6. Performance Bottleneck Analysis (Medium)
        work_items.append(BatchWorkItem(
            id="performance-analysis",
            title="Performance Bottleneck Detection",
            description="Identify performance bottlenecks and optimization opportunities",
            prompt=f"Analyze performance across {active_projects} projects. Identify: N+1 queries, missing indexes, inefficient algorithms (O(n²)), blocking I/O, missing caching opportunities.",
            priority="normal",
            estimated_input_tokens=30_000,
            estimated_output_tokens=4_000,
            source="pattern",
            deadline_hours=24
        ))

        # 7. API Documentation Generation (Low - if APIs detected)
        work_items.append(BatchWorkItem(
            id="api-docs-generation",
            title="API Documentation Generation",
            description="Generate/update API documentation for public endpoints",
            prompt="Generate API documentation for all public endpoints. Include: request/response examples, parameter descriptions, error codes, authentication requirements.",
            priority="low",
            estimated_input_tokens=20_000,
            estimated_output_tokens=8_000,
            source="docs",
            deadline_hours=48
        ))

        # 8. Refactoring Opportunities (Low)
        work_items.append(BatchWorkItem(
            id="refactoring-suggestions",
            title="Refactoring Opportunity Analysis",
            description="Identify code that would benefit from refactoring",
            prompt=f"Identify refactoring opportunities across {active_projects} projects. Suggest: function extraction, class extraction, interface simplification, dead code removal.",
            priority="low",
            estimated_input_tokens=35_000,
            estimated_output_tokens=6_000,
            source="pattern",
            deadline_hours=48
        ))

        return work_items

    def prioritize_work(self, work_items: List[BatchWorkItem]) -> List[BatchWorkItem]:
        """Sort work items by priority and token efficiency"""
        return sorted(
            work_items,
            key=lambda x: (
                -x.priority_score,  # Higher priority first
                x.total_tokens      # Lower tokens first (fit more jobs)
            )
        )

    def fill_overnight_queue(self, max_jobs: Optional[int] = None, use_optimizer: bool = True) -> List[BatchWorkItem]:
        """
        Fill overnight batch queue to maximize capacity.

        Args:
            max_jobs: Maximum jobs to queue (overrides capacity calculation)
            use_optimizer: Use adaptive optimizer for work generation and bin packing

        Returns list of jobs to submit for overnight processing.
        """
        # Option 1: Use adaptive optimizer (recommended)
        if use_optimizer:
            try:
                from batch.optimizer import integrate_with_orchestrator
                return integrate_with_orchestrator(self.root_dir)
            except Exception as e:
                print(f"Warning: Optimizer failed, falling back to basic mode: {e}")
                # Fall through to basic mode

        # Option 2: Basic mode (legacy)
        # Generate potential work
        work_items = self.generate_work_items()

        # Prioritize
        prioritized = self.prioritize_work(work_items)

        # Calculate capacity constraints
        max_by_tokens = self.capacity.max_jobs_by_tokens()
        max_by_time = self.capacity.max_jobs_by_time()
        max_by_concurrent = self.capacity.max_concurrent_batches

        # Use most restrictive limit
        if max_jobs is None:
            max_jobs = min(max_by_tokens, max_by_time, max_by_concurrent)

        # Fill queue up to capacity
        selected_jobs = []
        total_tokens = 0

        for item in prioritized:
            if len(selected_jobs) >= max_jobs:
                break

            # Check if adding this job would exceed token budget
            if total_tokens + item.total_tokens <= self.capacity.available_overnight_tokens():
                selected_jobs.append(item)
                total_tokens += item.total_tokens
            else:
                # Skip this job, try next one
                continue

        return selected_jobs

    def submit_batch_queue(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Submit overnight batch queue.

        Args:
            dry_run: If True, don't actually submit, just show what would be submitted

        Returns:
            Summary of submitted jobs
        """
        queue = self.fill_overnight_queue()

        summary = {
            "total_jobs": len(queue),
            "total_tokens": sum(j.total_tokens for j in queue),
            "by_priority": {
                "critical": len([j for j in queue if j.priority == "critical"]),
                "high": len([j for j in queue if j.priority == "high"]),
                "medium": len([j for j in queue if j.priority == "medium"]),
                "low": len([j for j in queue if j.priority == "low"]),
            },
            "jobs": [],
            "capacity": {
                "available_tokens": self.capacity.available_overnight_tokens(),
                "utilization_pct": (sum(j.total_tokens for j in queue) / self.capacity.available_overnight_tokens() * 100) if self.capacity.available_overnight_tokens() > 0 else 0,
            }
        }

        for job in queue:
            job_summary = {
                "id": job.id,
                "title": job.title,
                "priority": job.priority,
                "tokens": job.total_tokens,
                "source": job.source,
            }

            if not dry_run:
                # Submit via BatchOrchestrator (routes to correct backend)
                try:
                    from batch.orchestrator import BatchOrchestrator

                    orchestrator = BatchOrchestrator()

                    # Convert BatchWorkItem to API job format
                    api_job = {
                        "id": job.id,
                        "description": job.description,
                        "priority": job.priority,
                        "tasks": [{
                            "task_id": f"{job.id}_task_1",
                            "title": job.title,
                            "prompt": job.prompt,
                            "context": "",
                            "files_affected": job.files,
                            "estimated_tokens": job.estimated_input_tokens
                        }],
                        "estimated_total_tokens": job.total_tokens,
                        "source": job.source,
                        "project": job.project
                    }

                    # Submit - orchestrator will auto-detect as API job
                    job_id = orchestrator.submit_job(api_job, auto_detect=True)

                    job_summary["submitted"] = True
                    job_summary["job_id"] = job_id
                    job_summary["error"] = None
                except Exception as e:
                    job_summary["submitted"] = False
                    job_summary["error"] = str(e)
            else:
                job_summary["submitted"] = "dry_run"

            summary["jobs"].append(job_summary)

        # Sync all queued JSON jobs to SQLite ONCE after all submissions
        if not dry_run and any(j.get("submitted") is True for j in summary["jobs"]):
            try:
                from batch.orchestrator import BatchOrchestrator
                orch = BatchOrchestrator()
                synced = orch.sync_to_daemon()
                summary["synced_to_daemon"] = synced
            except Exception as e:
                summary["sync_error"] = str(e)

        return summary

    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Pretty print submission summary"""
        print("╔══════════════════════════════════════════════════════╗")
        print("║      INTELLIGENT BATCH ORCHESTRATOR - SUMMARY       ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()

        print("📊 QUEUE COMPOSITION")
        print("────────────────")
        print(f"Total Jobs: {summary['total_jobs']}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print("Priority Breakdown:")
        for priority, count in summary['by_priority'].items():
            if count > 0:
                print(f"  {priority.capitalize()}: {count}")
        print()

        print("💾 CAPACITY UTILIZATION")
        print("────────────────")
        print(f"Available Tokens: {summary['capacity']['available_tokens']:,}")
        print(f"Utilization: {summary['capacity']['utilization_pct']:.1f}%")
        print()

        print("📋 JOBS QUEUED")
        print("────────────────")
        for job in summary['jobs']:
            status_icon = "✅" if job.get("submitted") == True else ("🔄" if job.get("submitted") == "dry_run" else "❌")
            print(f"{status_icon} [{job['priority'].upper()}] {job['title']}")
            print(f"   Tokens: {job['tokens']:,} | Source: {job['source']}")
            if job.get("error"):
                print(f"   Error: {job['error']}")
        print()


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent Batch Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted without actually submitting")
    parser.add_argument("--max-jobs", type=int, help="Maximum number of jobs to queue (overrides capacity calculation)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of formatted text")
    parser.add_argument("--no-optimizer", action="store_true", help="Disable adaptive optimizer (use basic mode)")

    args = parser.parse_args()

    orchestrator = IntelligentBatchOrchestrator()

    # Override fill_overnight_queue if --no-optimizer is set
    if args.no_optimizer:
        orchestrator.fill_overnight_queue = lambda **kwargs: orchestrator.fill_overnight_queue(use_optimizer=False, **kwargs)

    summary = orchestrator.submit_batch_queue(dry_run=args.dry_run)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        orchestrator.print_summary(summary)

        if args.dry_run:
            print("💡 This was a dry run. Use without --dry-run to actually submit jobs.")
        else:
            print("✅ Batch queue submitted for overnight processing!")
            print("📊 Check status: cortex batch status")
            print("📥 Results available in morning briefing")


if __name__ == "__main__":
    main()
