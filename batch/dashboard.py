#!/usr/bin/env python3
"""
Batch API Dashboard

Comprehensive view of batch API usage, costs, and status.
Goal: Make it easy to track batch adoption and savings.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Try to import batch components
try:
    from batch_api_client import BatchAPIClient
except ImportError:
    BatchAPIClient = None

try:
    from batch_scheduler import BatchScheduler
except ImportError:
    BatchScheduler = None


class BatchDashboard:
    """Unified dashboard for batch API status and metrics."""

    def __init__(self):
        self.cortex_dir = Path.home() / ".cortex"
        self.batch_dir = self.cortex_dir / "batch"
        self.batches_dir = self.cortex_dir / "batches"
        self.perf_db = self.batch_dir / "performance.db"

        # Initialize client if available
        self.client = None
        if BatchAPIClient:
            try:
                self.client = BatchAPIClient()
            except Exception:
                pass

    def get_api_batches(self, limit: int = 10) -> List[Dict]:
        """Get recent batches from Anthropic API."""
        if not self.client:
            return []

        try:
            return self.client.list_batches(limit=limit)
        except Exception:
            return []

    def get_local_queue(self) -> Dict[str, Any]:
        """Get local batch queue status."""
        queue_file = self.batches_dir / "remediation_queue.json"

        if not queue_file.exists():
            return {"total": 0, "jobs": []}

        try:
            with open(queue_file) as f:
                data = json.load(f)

            jobs = data.get("priority_jobs", [])
            return {
                "total": len(jobs),
                "queued": len([j for j in jobs if j.get("status") == "queued"]),
                "submitted": len([j for j in jobs if j.get("status") == "submitted"]),
                "completed": len([j for j in jobs if j.get("status") == "completed"]),
                "jobs": jobs,
            }
        except Exception:
            return {"total": 0, "jobs": []}

    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get performance metrics from tracking database."""
        if not self.perf_db.exists():
            return self._empty_metrics()

        try:
            conn = sqlite3.connect(str(self.perf_db))
            cursor = conn.cursor()

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # Total tasks
            cursor.execute(
                "SELECT COUNT(*), SUM(actual_input_tokens + actual_output_tokens) "
                "FROM batch_tasks WHERE submitted_at >= ? AND status = 'completed'",
                (cutoff,)
            )
            row = cursor.fetchone()
            total_tasks = row[0] or 0
            total_tokens = row[1] or 0

            # By source
            cursor.execute(
                "SELECT source, COUNT(*), SUM(actual_input_tokens + actual_output_tokens) "
                "FROM batch_tasks WHERE submitted_at >= ? GROUP BY source",
                (cutoff,)
            )
            by_source = {}
            for row in cursor.fetchall():
                by_source[row[0] or "unknown"] = {
                    "tasks": row[1],
                    "tokens": row[2] or 0,
                }

            # By priority
            cursor.execute(
                "SELECT priority, COUNT(*) "
                "FROM batch_tasks WHERE submitted_at >= ? GROUP BY priority",
                (cutoff,)
            )
            by_priority = {row[0]: row[1] for row in cursor.fetchall()}

            conn.close()

            # Calculate cost savings
            # Opus pricing rough estimate: $45/million tokens average
            real_time_cost = (total_tokens / 1_000_000) * 45
            batch_cost = real_time_cost * 0.5
            savings = real_time_cost - batch_cost

            return {
                "days": days,
                "total_tasks": total_tasks,
                "total_tokens": total_tokens,
                "by_source": by_source,
                "by_priority": by_priority,
                "cost_estimate": {
                    "real_time_would_be": round(real_time_cost, 2),
                    "batch_actual": round(batch_cost, 2),
                    "savings": round(savings, 2),
                },
            }

        except Exception as e:
            return self._empty_metrics()

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "days": 0,
            "total_tasks": 0,
            "total_tokens": 0,
            "by_source": {},
            "by_priority": {},
            "cost_estimate": {
                "real_time_would_be": 0,
                "batch_actual": 0,
                "savings": 0,
            },
        }

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get batch scheduler status."""
        if not BatchScheduler:
            return {"available": False}

        try:
            scheduler = BatchScheduler()
            pending = scheduler.get_pending_tasks()
            submitted = scheduler.get_submitted_tasks()
            completed = scheduler.get_completed_tasks(days=7)

            return {
                "available": True,
                "pending": len(pending),
                "submitted": len(submitted),
                "completed_7d": len(completed),
                "next_submit": pending[0].submit_after.isoformat() if pending else None,
            }
        except Exception:
            return {"available": False}

    def generate_report(self) -> str:
        """Generate full dashboard report."""
        lines = []

        lines.append("")
        lines.append("=" * 70)
        lines.append("           CORTEX BATCH API DASHBOARD")
        lines.append("=" * 70)
        lines.append(f"           Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # === API BATCHES ===
        api_batches = self.get_api_batches(limit=5)
        lines.append("-" * 70)
        lines.append("  ANTHROPIC API BATCHES (Recent)")
        lines.append("-" * 70)

        if api_batches:
            for batch in api_batches:
                counts = batch.get("request_counts", {})
                total = sum(counts.values())
                done = counts.get("succeeded", 0) + counts.get("errored", 0)
                status = batch.get("status", "unknown")
                status_icon = {
                    "in_progress": "...",
                    "validating": "...",
                    "finalizing": "...",
                    "ended": "OK",
                }.get(status, "??")

                lines.append(
                    f"  [{status_icon:4}] {batch['id'][:25]}... | {done}/{total} done"
                )
        else:
            lines.append("  No recent API batches found")
            lines.append("  (Or API key not configured)")

        lines.append("")

        # === LOCAL QUEUE ===
        local = self.get_local_queue()
        lines.append("-" * 70)
        lines.append("  LOCAL QUEUE STATUS")
        lines.append("-" * 70)
        lines.append(f"  Total Jobs:    {local['total']}")
        lines.append(f"  Queued:        {local.get('queued', 0)}")
        lines.append(f"  Submitted:     {local.get('submitted', 0)}")
        lines.append(f"  Completed:     {local.get('completed', 0)}")
        lines.append("")

        # === SCHEDULER ===
        scheduler = self.get_scheduler_status()
        lines.append("-" * 70)
        lines.append("  BATCH SCHEDULER")
        lines.append("-" * 70)
        if scheduler.get("available"):
            lines.append(f"  Pending Tasks:      {scheduler.get('pending', 0)}")
            lines.append(f"  Processing:         {scheduler.get('submitted', 0)}")
            lines.append(f"  Completed (7d):     {scheduler.get('completed_7d', 0)}")
            if scheduler.get("next_submit"):
                lines.append(f"  Next Submit:        {scheduler['next_submit']}")
        else:
            lines.append("  Scheduler not available")
        lines.append("")

        # === PERFORMANCE METRICS ===
        metrics = self.get_performance_metrics(days=7)
        lines.append("-" * 70)
        lines.append("  PERFORMANCE METRICS (7 days)")
        lines.append("-" * 70)
        lines.append(f"  Total Tasks:        {metrics['total_tasks']}")
        lines.append(f"  Total Tokens:       {metrics['total_tokens']:,}")
        lines.append("")
        lines.append("  Cost Analysis:")
        lines.append(f"    Real-time would be: ${metrics['cost_estimate']['real_time_would_be']:.2f}")
        lines.append(f"    Batch actual:       ${metrics['cost_estimate']['batch_actual']:.2f}")
        lines.append(f"    SAVINGS:            ${metrics['cost_estimate']['savings']:.2f}")
        lines.append("")

        if metrics["by_source"]:
            lines.append("  By Source:")
            for source, data in metrics["by_source"].items():
                lines.append(f"    {source:<15} {data['tasks']} tasks, {data['tokens']:,} tokens")

        lines.append("")

        # === RECOMMENDATIONS ===
        lines.append("-" * 70)
        lines.append("  RECOMMENDATIONS")
        lines.append("-" * 70)

        # Check batch adoption rate
        total_tasks = metrics["total_tasks"]
        if total_tasks == 0:
            lines.append("  [!] No batch tasks in last 7 days")
            lines.append("      Consider using batch for:")
            lines.append("      - Code reviews (/batch-submit review)")
            lines.append("      - Documentation (/batch-submit docs)")
            lines.append("      - Research questions (/batch-submit research)")
        elif total_tasks < 10:
            lines.append("  [~] Low batch adoption ({} tasks/week)".format(total_tasks))
            lines.append("      Target: 40% of work via batch")
            lines.append("      Tip: Run /batch-orchestrate before leaving for day")
        else:
            savings = metrics["cost_estimate"]["savings"]
            lines.append(f"  [+] Good batch adoption! Saved ${savings:.2f} this week")

        # Check queue status
        if local.get("queued", 0) > 0:
            lines.append(f"  [!] {local['queued']} jobs waiting in queue")
            lines.append("      Run: python batch/queue_manager.py to process")

        lines.append("")
        lines.append("=" * 70)
        lines.append("  Quick Commands:")
        lines.append("    /batch-submit <type>    - Submit batch job")
        lines.append("    /batch-status           - Check job status")
        lines.append("    /batch-orchestrate      - Fill overnight queue")
        lines.append("    /batch-retrieve <id>    - Get results")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Batch API Dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")

    args = parser.parse_args()

    dashboard = BatchDashboard()

    if args.json:
        data = {
            "api_batches": dashboard.get_api_batches(),
            "local_queue": dashboard.get_local_queue(),
            "scheduler": dashboard.get_scheduler_status(),
            "metrics": dashboard.get_performance_metrics(days=args.days),
        }
        print(json.dumps(data, indent=2, default=str))
    else:
        print(dashboard.generate_report())


if __name__ == "__main__":
    main()
