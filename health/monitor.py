#!/usr/bin/env python3
"""
Health Monitoring System

Tracks system health metrics and generates actionable alerts:
- Queue depth (optimal: 3-8 tasks)
- Success rate (optimal: >85%)
- Cycle time (optimal: <4 hours)
- Blocked tasks (optimal: 0)
- Cost tracking

Provides real-time visibility into whether the system is in optimal state.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List


@dataclass
class HealthMetrics:
    """Current system health metrics."""

    queue_depth: int          # Number of tasks in queue
    success_rate: float       # % of tasks completing successfully
    avg_cycle_time_hours: float  # Average time from start to completion
    blocked_tasks: int        # Tasks waiting on dependencies
    cost_per_day_usd: float   # Daily API cost
    active_executors: int     # Number of running executors
    tasks_completed_24h: int  # Tasks completed in last 24h
    tasks_failed_24h: int     # Tasks failed in last 24h


@dataclass
class Alert:
    """Actionable alert requiring human attention."""

    severity: str  # "info", "warning", "critical"
    message: str
    action: str    # What human should do
    timestamp: datetime = field(default_factory=datetime.now)


class HealthMonitor:
    """Real-time system health assessment."""

    # Optimal thresholds
    OPTIMAL_THRESHOLDS = {
        "queue_depth_min": 3,
        "queue_depth_max": 8,
        "success_rate_min": 0.85,
        "cycle_time_max_hours": 4.0,
        "blocked_tasks_max": 0,
        "cost_per_day_max_usd": 50.0,
    }

    def __init__(self):
        self.cortex_dir = Path.home() / ".cortex"
        self.history_dir = self.cortex_dir / "health_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def health_status(self) -> tuple[HealthMetrics, List[Alert]]:
        """
        Get current health status and alerts.

        Returns:
            (metrics, alerts) tuple
        """
        metrics = self._collect_metrics()
        alerts = self._generate_alerts(metrics)

        # Save snapshot
        self._save_snapshot(metrics, alerts)

        return metrics, alerts

    def _collect_metrics(self) -> HealthMetrics:
        """Collect current health metrics."""

        # Load queue data
        signals_dir = self.cortex_dir / "signals"
        contracts_dir = self.cortex_dir / "contracts"
        batches_dir = self.cortex_dir / "batches"

        # Count queue depth (pending contracts)
        queue_depth = len(list(contracts_dir.glob("*.json"))) if contracts_dir.exists() else 0

        # Load task history for success rate
        success_rate, tasks_completed, tasks_failed = self._calculate_success_rate()

        # Calculate average cycle time
        avg_cycle_time = self._calculate_avg_cycle_time()

        # Count blocked tasks
        blocked_tasks = self._count_blocked_tasks()

        # Calculate cost
        cost_per_day = self._calculate_daily_cost()

        # Count active executors
        active_executors = self._count_active_executors()

        return HealthMetrics(
            queue_depth=queue_depth,
            success_rate=success_rate,
            avg_cycle_time_hours=avg_cycle_time,
            blocked_tasks=blocked_tasks,
            cost_per_day_usd=cost_per_day,
            active_executors=active_executors,
            tasks_completed_24h=tasks_completed,
            tasks_failed_24h=tasks_failed,
        )

    def _calculate_success_rate(self) -> tuple[float, int, int]:
        """
        Calculate success rate from task history.

        Returns:
            (success_rate, completed_count, failed_count)
        """
        # Check batch orchestrator task history
        try:
            from batch.orchestrator import BatchOrchestrator

            orchestrator = BatchOrchestrator()
            jobs = orchestrator.list_jobs(backend="both", limit=100)

            if not jobs:
                return (1.0, 0, 0)

            # Filter to last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)
            recent_jobs = [j for j in jobs if j.created_at >= cutoff]

            if not recent_jobs:
                return (1.0, 0, 0)

            completed = len([j for j in recent_jobs if j.state.value == "completed"])
            failed = len([j for j in recent_jobs if j.state.value == "failed"])
            total = completed + failed

            success_rate = completed / total if total > 0 else 1.0

            return (success_rate, completed, failed)

        except Exception:
            # Fallback
            return (1.0, 0, 0)

    def _calculate_avg_cycle_time(self) -> float:
        """Calculate average cycle time from start to completion."""
        try:
            from batch.orchestrator import BatchOrchestrator

            orchestrator = BatchOrchestrator()
            jobs = orchestrator.list_jobs(backend="both", limit=50)

            cycle_times = []
            for job in jobs:
                if job.state.value == "completed" and job.started_at and job.completed_at:
                    cycle_time = (job.completed_at - job.started_at).total_seconds() / 3600
                    cycle_times.append(cycle_time)

            if cycle_times:
                return sum(cycle_times) / len(cycle_times)

            return 0.0

        except Exception:
            return 0.0

    def _count_blocked_tasks(self) -> int:
        """Count tasks blocked on dependencies."""
        # Check batch queue for tasks with unsatisfied dependencies
        batch_queue = self.cortex_dir / "batches" / "remediation_queue.json"

        if not batch_queue.exists():
            return 0

        try:
            data = json.loads(batch_queue.read_text())
            blocked = 0

            for job in data.get("priority_jobs", []):
                depends_on = job.get("depends_on", [])
                if depends_on:
                    # Check if dependencies are satisfied
                    # Simplified: count all with dependencies as potentially blocked
                    blocked += 1

            return blocked

        except (json.JSONDecodeError, KeyError):
            return 0

    def _calculate_daily_cost(self) -> float:
        """Calculate daily API cost."""
        # Check recent batch jobs for cost data
        # Simplified: would integrate with actual cost tracking
        return 5.0  # Placeholder

    def _count_active_executors(self) -> int:
        """Count active executors (running jobs)."""
        try:
            from batch.orchestrator import BatchOrchestrator

            orchestrator = BatchOrchestrator()
            jobs = orchestrator.list_jobs(backend="both", limit=100)

            active = len([j for j in jobs if j.state.value in ["running", "scheduled"]])
            return active

        except Exception:
            return 0

    def _generate_alerts(self, metrics: HealthMetrics) -> List[Alert]:
        """Generate actionable alerts based on metrics."""
        alerts = []

        # Queue depth alerts
        if metrics.queue_depth < self.OPTIMAL_THRESHOLDS["queue_depth_min"]:
            alerts.append(Alert(
                severity="warning",
                message=f"Queue running low ({metrics.queue_depth} tasks) - may run out of work",
                action="Run signal detection to generate new tasks: `cortex scan`"
            ))
        elif metrics.queue_depth > self.OPTIMAL_THRESHOLDS["queue_depth_max"]:
            alerts.append(Alert(
                severity="info",
                message=f"Queue backed up ({metrics.queue_depth} tasks) - healthy backlog",
                action="No action needed - system has work queued"
            ))

        # Success rate alerts
        if metrics.success_rate < self.OPTIMAL_THRESHOLDS["success_rate_min"]:
            alerts.append(Alert(
                severity="critical",
                message=f"Success rate low ({metrics.success_rate:.1%}) - tasks failing",
                action=f"Review {metrics.tasks_failed_24h} failed tasks. May need contract refinement or better verification."
            ))

        # Cycle time alerts
        if metrics.avg_cycle_time_hours > self.OPTIMAL_THRESHOLDS["cycle_time_max_hours"]:
            alerts.append(Alert(
                severity="warning",
                message=f"Slow cycle time ({metrics.avg_cycle_time_hours:.1f}h avg, target: {self.OPTIMAL_THRESHOLDS['cycle_time_max_hours']}h)",
                action="Consider routing more tasks to faster executors or parallelizing"
            ))

        # Blocked tasks alerts
        if metrics.blocked_tasks > self.OPTIMAL_THRESHOLDS["blocked_tasks_max"]:
            alerts.append(Alert(
                severity="critical",
                message=f"{metrics.blocked_tasks} tasks blocked on dependencies",
                action="Review blocked tasks and resolve dependencies"
            ))

        # Cost alerts
        if metrics.cost_per_day_usd > self.OPTIMAL_THRESHOLDS["cost_per_day_max_usd"]:
            alerts.append(Alert(
                severity="warning",
                message=f"High daily cost (${metrics.cost_per_day_usd:.2f}, target: ${self.OPTIMAL_THRESHOLDS['cost_per_day_max_usd']:.2f})",
                action="Review task routing - consider using cheaper models for low-complexity tasks"
            ))

        # No work alert
        if metrics.active_executors == 0 and metrics.queue_depth == 0:
            alerts.append(Alert(
                severity="warning",
                message="No active work and empty queue",
                action="Run signal detection to find work: `cortex scan`"
            ))

        # All green
        if not alerts:
            alerts.append(Alert(
                severity="info",
                message="✅ System healthy - all metrics optimal",
                action="No action needed"
            ))

        return alerts

    def _save_snapshot(self, metrics: HealthMetrics, alerts: List[Alert]) -> None:
        """Save health snapshot for historical tracking."""
        snapshot_file = self.history_dir / f"health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "queue_depth": metrics.queue_depth,
                "success_rate": metrics.success_rate,
                "avg_cycle_time_hours": metrics.avg_cycle_time_hours,
                "blocked_tasks": metrics.blocked_tasks,
                "cost_per_day_usd": metrics.cost_per_day_usd,
                "active_executors": metrics.active_executors,
                "tasks_completed_24h": metrics.tasks_completed_24h,
                "tasks_failed_24h": metrics.tasks_failed_24h,
            },
            "alerts": [
                {
                    "severity": a.severity,
                    "message": a.message,
                    "action": a.action,
                }
                for a in alerts
            ]
        }

        snapshot_file.write_text(json.dumps(data, indent=2))

    def get_history(self, hours: int = 24) -> List[Dict]:
        """Get historical health snapshots."""
        cutoff = datetime.now() - timedelta(hours=hours)
        snapshots = []

        for snapshot_file in sorted(self.history_dir.glob("health_*.json"), reverse=True):
            try:
                # Parse timestamp from filename
                timestamp_str = snapshot_file.stem.replace("health_", "")
                file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                if file_time < cutoff:
                    break

                data = json.loads(snapshot_file.read_text())
                snapshots.append(data)

            except (json.JSONDecodeError, ValueError):
                continue

        return snapshots


if __name__ == "__main__":
    # Test health monitoring
    monitor = HealthMonitor()
    metrics, alerts = monitor.health_status()

    print("=== SYSTEM HEALTH ===\n")

    print(f"Queue Depth: {metrics.queue_depth} (optimal: 3-8)")
    print(f"Success Rate: {metrics.success_rate:.1%} (optimal: >85%)")
    print(f"Avg Cycle Time: {metrics.avg_cycle_time_hours:.1f}h (optimal: <4h)")
    print(f"Blocked Tasks: {metrics.blocked_tasks} (optimal: 0)")
    print(f"Cost/Day: ${metrics.cost_per_day_usd:.2f} (optimal: <$50)")
    print(f"Active Executors: {metrics.active_executors}")
    print(f"Completed (24h): {metrics.tasks_completed_24h}")
    print(f"Failed (24h): {metrics.tasks_failed_24h}")

    print("\n=== ALERTS ===\n")
    for alert in alerts:
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}[alert.severity]
        print(f"{icon} [{alert.severity.upper()}] {alert.message}")
        print(f"   Action: {alert.action}\n")
