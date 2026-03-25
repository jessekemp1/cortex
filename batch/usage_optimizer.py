"""
Usage Optimization Tracker

Tracks real-time vs batch Claude usage to ensure compliance with limits.
Integrates with Claude Usage Optimization Guide recommendations.

Target: Reduce from 13.9 hrs/day to 8.6 hrs/day sustainable rate
Strategy: Move eligible work to Batch API (50% cost, overnight processing)
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class UsageTarget:
    """Usage targets based on optimization guide"""

    # From CLAUDE_USAGE_OPTIMIZATION_GUIDE.md
    weekly_hour_limit: float = 60.0  # Hours per week
    daily_sustainable_hours: float = 8.6  # Hours per day target
    current_burn_rate: float = 13.9  # Current hours per day

    # Reduction needed
    hours_to_reduce: float = 5.3  # 13.9 - 8.6

    # Strategy: Move work to batch
    batch_discount: float = 0.50  # 50% cost savings
    target_batch_percentage: float = 40.0  # Aim for 40% of work via batch


class UsageOptimizer:
    """
    Tracks and optimizes Claude usage between real-time and batch.

    Goals:
    - Reduce real-time usage from 13.9 to 8.6 hours/day
    - Move 40% of eligible work to Batch API
    - Stay within 60 hour/week limit
    """

    def __init__(self, storage_path: Path = None):
        if storage_path is None:
            storage_path = Path.home() / ".cortex" / "usage_tracking"

        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.targets = UsageTarget()

    def record_real_time_usage(
        self,
        tokens: int,
        task_type: str,
        could_be_batch: bool = False,
        model: str = None,
        cost_usd: float = None,
    ):
        """
        Record real-time Claude usage.

        Args:
            tokens: Number of tokens used
            task_type: Type of task (interactive, analysis, etc.)
            could_be_batch: Whether this could have been a batch task
            model: Model used (e.g. claude-sonnet-4-6, claude-haiku-4-5)
            cost_usd: Estimated cost in USD
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "real_time",
            "tokens": tokens,
            "task_type": task_type,
            "could_be_batch": could_be_batch,
            "model": model,
            "cost_usd": cost_usd,
        }

        self._append_record(record)

    def record_batch_usage(
        self, tokens: int, task_type: str, savings: float, model: str = None, cost_usd: float = None
    ):
        """
        Record batch API usage.

        Args:
            tokens: Number of tokens used
            task_type: Type of task
            savings: Dollar amount saved vs real-time
            model: Model used
            cost_usd: Actual cost in USD
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "batch",
            "tokens": tokens,
            "task_type": task_type,
            "savings": savings,
            "model": model,
            "cost_usd": cost_usd,
        }

        self._append_record(record)

    def _append_record(self, record: Dict):
        """Append usage record to log"""
        log_file = self.storage_path / f"usage_{datetime.now().strftime('%Y%m')}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")

    def get_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get usage summary for the past N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with usage analysis
        """
        cutoff = datetime.now() - timedelta(days=days)
        records = self._load_records_since(cutoff)

        # Categorize records
        real_time_records = [r for r in records if r["type"] == "real_time"]
        batch_records = [r for r in records if r["type"] == "batch"]

        # Calculate totals
        real_time_tokens = sum(r["tokens"] for r in real_time_records)
        batch_tokens = sum(r["tokens"] for r in batch_records)
        total_tokens = real_time_tokens + batch_tokens

        # Calculate batch percentage
        batch_pct = (batch_tokens / total_tokens * 100) if total_tokens > 0 else 0

        # Estimate cost (Opus pricing: $15/M input, $75/M output - rough average $45/M)
        real_time_cost = real_time_tokens / 1_000_000 * 45
        batch_cost = batch_tokens / 1_000_000 * 45 * 0.5  # 50% discount
        total_savings = sum(r.get("savings", 0) for r in batch_records)

        # Find tasks that could have been batch
        could_be_batch = [r for r in real_time_records if r.get("could_be_batch", False)]
        missed_opportunities_tokens = sum(r["tokens"] for r in could_be_batch)
        potential_additional_savings = missed_opportunities_tokens / 1_000_000 * 45 * 0.5

        return {
            "days_analyzed": days,
            "real_time": {
                "sessions": len(real_time_records),
                "tokens": real_time_tokens,
                "estimated_cost": round(real_time_cost, 2),
            },
            "batch": {
                "tasks": len(batch_records),
                "tokens": batch_tokens,
                "estimated_cost": round(batch_cost, 2),
                "total_savings": round(total_savings, 2),
            },
            "totals": {
                "tokens": total_tokens,
                "estimated_cost": round(real_time_cost + batch_cost, 2),
                "batch_percentage": round(batch_pct, 1),
                "target_percentage": self.targets.target_batch_percentage,
            },
            "optimization": {
                "missed_opportunities": len(could_be_batch),
                "missed_tokens": missed_opportunities_tokens,
                "potential_additional_savings": round(potential_additional_savings, 2),
                "on_track": batch_pct >= self.targets.target_batch_percentage,
            },
        }

    def get_compliance_report(self) -> Dict[str, Any]:
        """
        Check compliance with usage targets.

        Returns:
            Dict with compliance status
        """
        # Get last 7 days of usage
        summary = self.get_usage_summary(days=7)

        # Rough token-to-hour conversion (very rough estimate)
        # Assume average session is 50k tokens and lasts 30 minutes
        tokens_per_hour = 100_000

        real_time_hours = summary["real_time"]["tokens"] / tokens_per_hour
        daily_real_time_hours = real_time_hours / 7

        # Check compliance
        within_target = daily_real_time_hours <= self.targets.daily_sustainable_hours

        reduction_achieved = self.targets.current_burn_rate - daily_real_time_hours

        return {
            "targets": {
                "weekly_limit_hours": self.targets.weekly_hour_limit,
                "daily_target_hours": self.targets.daily_sustainable_hours,
                "current_burn_rate": self.targets.current_burn_rate,
                "reduction_needed": self.targets.hours_to_reduce,
            },
            "current": {
                "daily_real_time_hours": round(daily_real_time_hours, 1),
                "weekly_real_time_hours": round(real_time_hours, 1),
                "within_target": within_target,
                "reduction_achieved": round(reduction_achieved, 1),
            },
            "batch_usage": {
                "percentage": summary["totals"]["batch_percentage"],
                "target_percentage": self.targets.target_batch_percentage,
                "on_track": summary["optimization"]["on_track"],
            },
            "recommendations": self._get_recommendations(
                daily_real_time_hours, summary["totals"]["batch_percentage"]
            ),
        }

    def _get_recommendations(self, daily_hours: float, batch_pct: float) -> List[str]:
        """Generate optimization recommendations"""
        recs = []

        if daily_hours > self.targets.daily_sustainable_hours:
            excess = daily_hours - self.targets.daily_sustainable_hours
            recs.append(f"⚠️  Reduce real-time usage by {excess:.1f} hours/day to meet target")

        if batch_pct < self.targets.target_batch_percentage:
            gap = self.targets.target_batch_percentage - batch_pct
            recs.append(f"📊 Increase batch usage by {gap:.1f}% (currently {batch_pct:.1f}%)")

        if (
            batch_pct >= self.targets.target_batch_percentage
            and daily_hours <= self.targets.daily_sustainable_hours
        ):
            recs.append("✅ Usage optimized! Maintaining target levels.")

        # Always useful tips
        recs.append("💡 Schedule analysis tasks as batch work (6 PM submission)")
        recs.append("💡 Use batch API for: code analysis, documentation, planning")
        recs.append("💡 Reserve real-time for: interactive coding, debugging, urgent tasks")

        return recs

    def _load_records_since(self, cutoff: datetime) -> List[Dict]:
        """Load all usage records since cutoff date"""
        records = []

        # Determine which month files to check
        current = datetime.now()
        months_to_check = []

        # Current month
        months_to_check.append(current.strftime("%Y%m"))

        # Previous month if cutoff is in it
        if cutoff.month != current.month:
            months_to_check.append(cutoff.strftime("%Y%m"))

        # Load records from each month file
        for month in months_to_check:
            log_file = self.storage_path / f"usage_{month}.jsonl"

            if not log_file.exists():
                continue

            with open(log_file) as f:
                for line in f:
                    record = json.loads(line)
                    record_time = datetime.fromisoformat(record["timestamp"])

                    if record_time >= cutoff:
                        records.append(record)

        return records


def generate_optimization_report():
    """Generate a comprehensive optimization report"""
    optimizer = UsageOptimizer()

    print("=" * 70)
    print("Claude Usage Optimization Report")
    print("=" * 70)
    print()

    # Compliance check
    compliance = optimizer.get_compliance_report()

    print("📊 COMPLIANCE STATUS")
    print("-" * 70)
    print(f"Current daily usage:    {compliance['current']['daily_real_time_hours']:.1f} hours")
    print(f"Target daily usage:     {compliance['targets']['daily_target_hours']:.1f} hours")
    print(
        f"Status:                 {'✅ WITHIN TARGET' if compliance['current']['within_target'] else '⚠️  OVER TARGET'}"
    )
    print()

    print(f"Batch usage:            {compliance['batch_usage']['percentage']:.1f}%")
    print(f"Target batch usage:     {compliance['batch_usage']['target_percentage']:.1f}%")
    print(
        f"Status:                 {'✅ ON TRACK' if compliance['batch_usage']['on_track'] else '📈 NEEDS IMPROVEMENT'}"
    )
    print()

    # Usage summary
    summary = optimizer.get_usage_summary(days=7)

    print("💰 COST ANALYSIS (7 days)")
    print("-" * 70)
    print(f"Real-time cost:         ${summary['real_time']['estimated_cost']:.2f}")
    print(f"Batch cost:             ${summary['batch']['estimated_cost']:.2f}")
    print(f"Savings achieved:       ${summary['batch']['total_savings']:.2f}")
    print()

    if summary["optimization"]["missed_opportunities"] > 0:
        print("⚠️  MISSED OPPORTUNITIES")
        print("-" * 70)
        print(
            f"Tasks that could have been batch: {summary['optimization']['missed_opportunities']}"
        )
        print(
            f"Potential additional savings:     ${summary['optimization']['potential_additional_savings']:.2f}"
        )
        print()

    # Recommendations
    print("💡 RECOMMENDATIONS")
    print("-" * 70)
    for rec in compliance["recommendations"]:
        print(f"  {rec}")
    print()

    print("=" * 70)


if __name__ == "__main__":
    generate_optimization_report()
