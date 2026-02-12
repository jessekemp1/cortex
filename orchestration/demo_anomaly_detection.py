"""
Demo script to show anomaly detection in action.

Run with: python -m orchestration.demo_anomaly_detection
"""

from datetime import datetime, timedelta
from pathlib import Path

from .anomaly_detector import AnomalySeverity, OrchestrationAnomalyManager
from .database import OrchestrationDatabase
from .models import Task, TaskPhase, TaskPriority, TaskStatus, WorkerRole, WorkerState


def create_demo_scenario(db: OrchestrationDatabase) -> None:
    """Create a demo scenario with various anomalies."""

    # Scenario 1: Stuck task (80 hours in implementing phase)
    stuck_task = Task(
        id="demo-stuck-1",
        title="Refactor authentication system",
        description="Modernize auth flow with OAuth2",
        priority=TaskPriority.A,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
        created_at=datetime.now() - timedelta(hours=85),
        started_at=datetime.now() - timedelta(hours=85),
        project="auth-modernization",
    )
    db.create_task(stuck_task)

    # Scenario 2: Circular dependency (A -> B -> C -> A)
    cycle_task_a = Task(
        id="demo-cycle-a",
        title="Update API endpoints",
        description="REST API changes",
        priority=TaskPriority.A,
        phase=TaskPhase.PLANNING,
        status=TaskStatus.BLOCKED,
        blocked_by=["demo-cycle-c"],
        project="api-v2",
    )

    cycle_task_b = Task(
        id="demo-cycle-b",
        title="Update database schema",
        description="Add new tables",
        priority=TaskPriority.B,
        phase=TaskPhase.PLANNING,
        status=TaskStatus.BLOCKED,
        blocked_by=["demo-cycle-a"],
        project="api-v2",
    )

    cycle_task_c = Task(
        id="demo-cycle-c",
        title="Update client SDK",
        description="TypeScript SDK updates",
        priority=TaskPriority.B,
        phase=TaskPhase.PLANNING,
        status=TaskStatus.BLOCKED,
        blocked_by=["demo-cycle-b"],
        project="api-v2",
    )

    db.create_task(cycle_task_a)
    db.create_task(cycle_task_b)
    db.create_task(cycle_task_c)

    # Scenario 3: Priority inversion (A blocked by C)
    blocker_low = Task(
        id="demo-blocker-low",
        title="Update documentation",
        description="API docs update",
        priority=TaskPriority.C,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
        project="docs",
    )

    blocked_high = Task(
        id="demo-blocked-high",
        title="Critical security patch",
        description="Fix CVE-2024-1234",
        priority=TaskPriority.A,
        phase=TaskPhase.QUEUED,
        status=TaskStatus.BLOCKED,
        blocked_by=["demo-blocker-low"],
        created_at=datetime.now() - timedelta(hours=30),
        project="security",
    )

    db.create_task(blocker_low)
    db.create_task(blocked_high)

    # Scenario 4: Idle workers with ready tasks
    idle_worker_1 = WorkerState(
        worker_id="demo-worker-1",
        role=WorkerRole.IMPLEMENTER,
        current_task_count=0,
        max_concurrent_tasks=3,
    )

    idle_worker_2 = WorkerState(
        worker_id="demo-worker-2",
        role=WorkerRole.IMPLEMENTER,
        current_task_count=0,
        max_concurrent_tasks=3,
    )

    busy_worker = WorkerState(
        worker_id="demo-worker-3",
        role=WorkerRole.IMPLEMENTER,
        current_task_count=2,
        max_concurrent_tasks=3,
    )

    db.create_worker(idle_worker_1)
    db.create_worker(idle_worker_2)
    db.create_worker(busy_worker)

    # Create ready tasks
    for i in range(3):
        ready_task = Task(
            id=f"demo-ready-{i}",
            title=f"Implement feature {i}",
            description=f"Feature implementation {i}",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.PENDING,
            project=f"feature-{i}",
        )
        db.create_task(ready_task)


def print_anomalies(anomalies: list) -> None:
    """Pretty print detected anomalies."""
    if not anomalies:
        print("\n✅ No anomalies detected - orchestration is healthy!")
        return

    print(f"\n⚠️  DETECTED {len(anomalies)} ORCHESTRATION ANOMALIES")
    print("=" * 80)

    # Group by severity
    critical = [a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]
    warnings = [a for a in anomalies if a.severity == AnomalySeverity.WARNING]
    info = [a for a in anomalies if a.severity == AnomalySeverity.INFO]

    # Print critical anomalies
    if critical:
        print(f"\n🔴 CRITICAL ({len(critical)})")
        print("-" * 80)
        for anomaly in critical:
            print(f"\n  Title: {anomaly.title}")
            print(f"  Type: {anomaly.anomaly_type.value}")
            print(f"  Description: {anomaly.description}")
            print(
                f"  Metric: {anomaly.metric_value:.1f} (threshold: {anomaly.threshold_value:.1f})"
            )
            print(f"  Remediation: {anomaly.remediation}")
            if anomaly.auto_actionable:
                print(f"  Auto-action: {anomaly.auto_action_command or 'Suggested'}")
            if anomaly.affected_entities:
                print(f"  Affected: {len(anomaly.affected_entities)} entities")

    # Print warnings
    if warnings:
        print(f"\n🟡 WARNINGS ({len(warnings)})")
        print("-" * 80)
        for anomaly in warnings:
            print(f"\n  Title: {anomaly.title}")
            print(f"  Type: {anomaly.anomaly_type.value}")
            print(f"  Description: {anomaly.description}")
            print(f"  Remediation: {anomaly.remediation}")
            if anomaly.auto_actionable:
                print(f"  Auto-action: {anomaly.auto_action_command or 'Suggested'}")

    # Print info (collapsed)
    if info:
        print(f"\nℹ️  INFO ({len(info)})")
        print("-" * 80)
        for anomaly in info:
            print(f"  • {anomaly.title}")
            if anomaly.auto_actionable:
                print(f"    Action: {anomaly.auto_action_command or 'Suggested'}")


def main():
    """Run anomaly detection demo."""
    print("🔍 Cortex Orchestration Anomaly Detection Demo")
    print("=" * 80)

    # Create temporary database for demo
    db_path = Path.home() / ".cortex" / "demo_orchestration.db"
    db_path.parent.mkdir(exist_ok=True)

    # Clean up any existing demo database
    if db_path.exists():
        db_path.unlink()

    print(f"\nCreating demo database: {db_path}")
    db = OrchestrationDatabase(db_path)

    # Create demo scenario
    print("Setting up demo scenario with various anomalies...")
    create_demo_scenario(db)

    # Initialize anomaly manager
    print("Initializing anomaly detection system (7 detectors)...")
    manager = OrchestrationAnomalyManager(db)

    # Create context simulating overloaded system
    context = {
        "active_projects": 22,  # Too many active projects
        "total_projects": 30,
        "goals_in_progress": 0,  # No active goals
        "goals_pending": 8,
        "last_goal_activated": datetime.now() - timedelta(hours=60),  # Long gap
        "total_workers": 3,
        "batch_capacity": 100,
        "batch_queued": 25,  # Low batch utilization
        "misrouted_realtime_tasks": 4,
    }

    # Run detection
    print("Running anomaly detection...")
    anomalies = manager.detect_all(context)

    # Print results
    print_anomalies(anomalies)

    # Show stats
    print("\n📊 ANOMALY STATISTICS")
    print("=" * 80)
    print(f"Total anomalies detected: {len(anomalies)}")
    print(f"Critical: {len([a for a in anomalies if a.severity == AnomalySeverity.CRITICAL])}")
    print(f"Warning: {len([a for a in anomalies if a.severity == AnomalySeverity.WARNING])}")
    print(f"Info: {len([a for a in anomalies if a.severity == AnomalySeverity.INFO])}")
    print(f"Auto-actionable: {len([a for a in anomalies if a.auto_actionable])}")

    # Show detector coverage
    print("\n🔎 DETECTOR COVERAGE")
    print("=" * 80)
    anomaly_types = set(a.anomaly_type.value for a in anomalies)
    all_types = {
        "context_switching_risk",
        "planning_gap",
        "stuck_tasks",
        "dependency_deadlock",
        "resource_waste",
        "priority_inversion",
        "batch_inefficiency",
    }

    for anomaly_type in all_types:
        detected = "✅" if anomaly_type in anomaly_types else "  "
        count = len([a for a in anomalies if a.anomaly_type.value == anomaly_type])
        print(f"{detected} {anomaly_type}: {count} detected")

    print(f"\nDemo database saved to: {db_path}")
    print("Run this script again to see deduplication in action!")


if __name__ == "__main__":
    main()
