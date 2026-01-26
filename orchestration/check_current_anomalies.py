"""
Check current orchestration state for anomalies.

Run with: python -m orchestration.check_current_anomalies
"""

from pathlib import Path
from .anomaly_detector import OrchestrationAnomalyManager, AnomalySeverity
from .database import OrchestrationDatabase


def main():
    """Check current orchestration state for anomalies."""
    print("🔍 Checking Current Orchestration State for Anomalies")
    print("=" * 80)

    # Use real orchestration database
    db_path = Path.home() / ".cortex" / "orchestration.db"

    if not db_path.exists():
        print(f"\n❌ No orchestration database found at: {db_path}")
        print("The orchestration system has not been initialized yet.")
        return

    print(f"\nDatabase: {db_path}")

    db = OrchestrationDatabase(db_path)

    # Get stats
    stats = db.get_stats()
    print("\n📊 Current State:")
    print(f"  Tasks by status: {stats.get('tasks_by_status', {})}")
    print(f"  Tasks by phase: {stats.get('tasks_by_phase', {})}")
    print(f"  Workers: {stats.get('total_workers', 0)} total, {stats.get('available_workers', 0)} available")

    # Initialize anomaly manager
    manager = OrchestrationAnomalyManager(db)

    # Build context from database state
    # Note: In production, this would come from GOALS.md parser and project state
    context = {
        "active_projects": 0,  # Would come from GOALS.md
        "total_projects": 0,
        "goals_in_progress": 0,
        "goals_pending": 0,
        "total_workers": stats.get("total_workers", 0),
        "batch_capacity": 100,
        "batch_queued": 0,
        "misrouted_realtime_tasks": 0,
    }

    print("\n🔎 Running Anomaly Detection...")

    anomalies = manager.detect_all(context)

    if not anomalies:
        print("\n✅ No anomalies detected - orchestration is healthy!")
        return

    print(f"\n⚠️  DETECTED {len(anomalies)} ANOMALIES")
    print("=" * 80)

    # Group by severity
    critical = [a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]
    warnings = [a for a in anomalies if a.severity == AnomalySeverity.WARNING]
    info = [a for a in anomalies if a.severity == AnomalySeverity.INFO]

    if critical:
        print(f"\n🔴 CRITICAL ({len(critical)}):")
        for anomaly in critical:
            print(f"  • {anomaly.title}")
            print(f"    {anomaly.remediation}")

    if warnings:
        print(f"\n🟡 WARNING ({len(warnings)}):")
        for anomaly in warnings:
            print(f"  • {anomaly.title}")
            print(f"    {anomaly.remediation}")

    if info:
        print(f"\nℹ️  INFO ({len(info)}):")
        for anomaly in info:
            print(f"  • {anomaly.title}")

    print("\n📈 Historical Anomalies (last 7 days):")
    recent = db.get_recent_anomalies(days=7)
    if recent:
        print(f"  Total: {len(recent)} anomalies detected")
        by_type = {}
        for a in recent:
            by_type[a.anomaly_type.value] = by_type.get(a.anomaly_type.value, 0) + 1
        for anomaly_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            print(f"    {anomaly_type}: {count}")
    else:
        print("  No historical data yet")


if __name__ == "__main__":
    main()
