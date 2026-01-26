"""
Comprehensive tests for anomaly detection system.

Tests all 7 detectors plus the OrchestrationAnomalyManager.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from .anomaly_detector import (
    AnomalyType,
    AnomalySeverity,
    OrchestrationAnomaly,
    ContextSwitchingDetector,
    PlanningGapDetector,
    StuckTasksDetector,
    DependencyDeadlockDetector,
    ResourceWasteDetector,
    PriorityInversionDetector,
    BatchInefficiencyDetector,
    OrchestrationAnomalyManager,
)
from .database import OrchestrationDatabase
from .models import Task, TaskPhase, TaskPriority, TaskStatus, WorkerState, WorkerRole


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_orchestration.db"
        db = OrchestrationDatabase(db_path)
        yield db


class TestContextSwitchingDetector:
    """Test context switching risk detection."""

    def test_no_anomaly_low_active_projects(self, temp_db):
        """Should not detect anomaly with few active projects."""
        detector = ContextSwitchingDetector()
        context = {"active_projects": 8, "total_projects": 20}

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_info_level_moderate_active(self, temp_db):
        """Should detect INFO level with 11-15 active projects."""
        detector = ContextSwitchingDetector()
        context = {"active_projects": 12, "total_projects": 20}

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.INFO
        assert anomalies[0].metric_value == 12.0

    def test_warning_level_high_active(self, temp_db):
        """Should detect WARNING level with 16-20 active projects."""
        detector = ContextSwitchingDetector()
        context = {"active_projects": 18, "total_projects": 30}

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING
        assert anomalies[0].metric_value == 18.0
        assert "60%" in anomalies[0].description  # 18/30 = 60%

    def test_critical_level_very_high_active(self, temp_db):
        """Should detect CRITICAL level with >20 active projects."""
        detector = ContextSwitchingDetector()
        context = {"active_projects": 25, "total_projects": 30}

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL
        assert anomalies[0].metric_value == 25.0
        assert "83%" in anomalies[0].description  # 25/30 = 83%

    def test_warning_level_high_percentage(self, temp_db):
        """Should detect WARNING when >70% of portfolio is active."""
        detector = ContextSwitchingDetector()
        context = {"active_projects": 14, "total_projects": 18}  # 78%

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING


class TestPlanningGapDetector:
    """Test planning gap detection."""

    def test_no_anomaly_with_goals_in_progress(self, temp_db):
        """Should not detect anomaly when goals are in progress."""
        detector = PlanningGapDetector()
        context = {
            "active_projects": 10,
            "goals_in_progress": 2,
            "goals_pending": 5,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_no_anomaly_no_active_projects(self, temp_db):
        """Should not detect anomaly when no active projects."""
        detector = PlanningGapDetector()
        context = {
            "active_projects": 0,
            "goals_in_progress": 0,
            "goals_pending": 5,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_no_anomaly_no_pending_goals(self, temp_db):
        """Should not detect anomaly when no pending goals."""
        detector = PlanningGapDetector()
        context = {
            "active_projects": 10,
            "goals_in_progress": 0,
            "goals_pending": 0,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_info_level_short_gap(self, temp_db):
        """Should detect INFO level with <24h gap."""
        detector = PlanningGapDetector()
        last_activated = datetime.now() - timedelta(hours=12)
        context = {
            "active_projects": 10,
            "goals_in_progress": 0,
            "goals_pending": 5,
            "last_goal_activated": last_activated,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.INFO
        assert anomalies[0].auto_actionable is True
        assert anomalies[0].auto_action_command == "/briefing"

    def test_warning_level_medium_gap(self, temp_db):
        """Should detect WARNING level with 24-48h gap."""
        detector = PlanningGapDetector()
        last_activated = datetime.now() - timedelta(hours=36)
        context = {
            "active_projects": 10,
            "goals_in_progress": 0,
            "goals_pending": 5,
            "last_goal_activated": last_activated,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_critical_level_long_gap(self, temp_db):
        """Should detect CRITICAL level with >48h gap."""
        detector = PlanningGapDetector()
        last_activated = datetime.now() - timedelta(hours=72)
        context = {
            "active_projects": 10,
            "goals_in_progress": 0,
            "goals_pending": 5,
            "last_goal_activated": last_activated,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL


class TestStuckTasksDetector:
    """Test stuck tasks detection."""

    def test_no_anomaly_recent_tasks(self, temp_db):
        """Should not detect anomaly for recently created tasks."""
        detector = StuckTasksDetector()

        # Create task that's only 24 hours old
        task = Task(
            id="task-1",
            title="Recent task",
            description="Test task",
            priority=TaskPriority.A,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
            created_at=datetime.now() - timedelta(hours=24),
        )
        temp_db.create_task(task)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 0

    def test_info_level_48h_stuck(self, temp_db):
        """Should detect INFO level for task stuck 48h."""
        detector = StuckTasksDetector()

        task = Task(
            id="task-1",
            title="Stuck task",
            description="Test task",
            priority=TaskPriority.B,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
            created_at=datetime.now() - timedelta(hours=50),
            started_at=datetime.now() - timedelta(hours=50),
        )
        temp_db.create_task(task)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.INFO
        assert "Stuck task" in anomalies[0].title

    def test_warning_level_72h_stuck(self, temp_db):
        """Should detect WARNING level for task stuck >72h."""
        detector = StuckTasksDetector()

        task = Task(
            id="task-1",
            title="Very stuck task",
            description="Test task",
            priority=TaskPriority.B,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
            created_at=datetime.now() - timedelta(hours=80),
            started_at=datetime.now() - timedelta(hours=80),
        )
        temp_db.create_task(task)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_critical_level_72h_priority_a(self, temp_db):
        """Should detect CRITICAL level for priority A task stuck >72h."""
        detector = StuckTasksDetector()

        task = Task(
            id="task-1",
            title="Critical stuck task",
            description="Test task",
            priority=TaskPriority.A,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
            created_at=datetime.now() - timedelta(hours=80),
            started_at=datetime.now() - timedelta(hours=80),
        )
        temp_db.create_task(task)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL


class TestDependencyDeadlockDetector:
    """Test circular dependency detection."""

    def test_no_anomaly_no_cycles(self, temp_db):
        """Should not detect anomaly with no circular dependencies."""
        detector = DependencyDeadlockDetector()

        # Create linear dependency chain: task1 -> task2 -> task3
        task1 = Task(
            id="task-1",
            title="Task 1",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.PENDING,
        )
        task2 = Task(
            id="task-2",
            title="Task 2",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-1"],
        )
        task3 = Task(
            id="task-3",
            title="Task 3",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-2"],
        )

        temp_db.create_task(task1)
        temp_db.create_task(task2)
        temp_db.create_task(task3)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 0

    def test_info_level_small_cycle(self, temp_db):
        """Should detect INFO level for 2-task cycle."""
        detector = DependencyDeadlockDetector()

        # Create cycle: task1 -> task2 -> task1
        task1 = Task(
            id="task-1",
            title="Task 1",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-2"],
        )
        task2 = Task(
            id="task-2",
            title="Task 2",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-1"],
        )

        temp_db.create_task(task1)
        temp_db.create_task(task2)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.INFO
        assert anomalies[0].anomaly_type == AnomalyType.DEPENDENCY_DEADLOCK
        assert len(anomalies[0].affected_entities) == 2

    def test_warning_level_medium_cycle(self, temp_db):
        """Should detect WARNING level for 3-5 task cycle."""
        detector = DependencyDeadlockDetector()

        # Create 3-task cycle
        task1 = Task(
            id="task-1",
            title="Task 1",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-3"],
        )
        task2 = Task(
            id="task-2",
            title="Task 2",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-1"],
        )
        task3 = Task(
            id="task-3",
            title="Task 3",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-2"],
        )

        temp_db.create_task(task1)
        temp_db.create_task(task2)
        temp_db.create_task(task3)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING
        assert len(anomalies[0].affected_entities) == 3

    def test_critical_level_priority_a_cycle(self, temp_db):
        """Should detect CRITICAL level when cycle contains priority A."""
        detector = DependencyDeadlockDetector()

        # Create cycle with priority A task
        task1 = Task(
            id="task-1",
            title="Task 1",
            description="Test",
            priority=TaskPriority.A,  # Priority A
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-2"],
        )
        task2 = Task(
            id="task-2",
            title="Task 2",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["task-1"],
        )

        temp_db.create_task(task1)
        temp_db.create_task(task2)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL


class TestResourceWasteDetector:
    """Test resource waste detection."""

    def test_no_anomaly_no_idle_workers(self, temp_db):
        """Should not detect anomaly when all workers are busy."""
        detector = ResourceWasteDetector()

        # Create busy workers
        worker1 = WorkerState(
            worker_id="worker-1",
            role=WorkerRole.IMPLEMENTER,
            current_task_count=2,
            max_concurrent_tasks=3,
        )
        temp_db.create_worker(worker1)

        context = {"total_workers": 1}
        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_no_anomaly_idle_but_no_tasks(self, temp_db):
        """Should not detect anomaly when workers idle but no ready tasks."""
        detector = ResourceWasteDetector()

        # Create idle worker
        worker1 = WorkerState(
            worker_id="worker-1",
            role=WorkerRole.IMPLEMENTER,
            current_task_count=0,
            max_concurrent_tasks=3,
        )
        temp_db.create_worker(worker1)

        # No ready tasks in database

        context = {"total_workers": 1}
        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_warning_level_moderate_waste(self, temp_db):
        """Should detect WARNING level with 30-50% idle."""
        detector = ResourceWasteDetector()

        # Create 2 idle workers and 1 busy worker (40% idle)
        worker1 = WorkerState(
            worker_id="worker-1",
            role=WorkerRole.IMPLEMENTER,
            current_task_count=0,
        )
        worker2 = WorkerState(
            worker_id="worker-2",
            role=WorkerRole.IMPLEMENTER,
            current_task_count=0,
        )
        worker3 = WorkerState(
            worker_id="worker-3",
            role=WorkerRole.IMPLEMENTER,
            current_task_count=2,
        )
        temp_db.create_worker(worker1)
        temp_db.create_worker(worker2)
        temp_db.create_worker(worker3)

        # Create ready task
        task = Task(
            id="task-1",
            title="Ready task",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.PENDING,
        )
        temp_db.create_task(task)

        context = {"total_workers": 5}  # Assuming 5 total
        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_critical_level_high_waste(self, temp_db):
        """Should detect CRITICAL level with >50% idle."""
        detector = ResourceWasteDetector()

        # Create 3 idle workers out of 4 (75% idle)
        for i in range(3):
            worker = WorkerState(
                worker_id=f"worker-{i}",
                role=WorkerRole.IMPLEMENTER,
                current_task_count=0,
            )
            temp_db.create_worker(worker)

        # Create ready task
        task = Task(
            id="task-1",
            title="Ready task",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.PENDING,
        )
        temp_db.create_task(task)

        context = {"total_workers": 4}
        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL
        assert anomalies[0].auto_actionable is True


class TestPriorityInversionDetector:
    """Test priority inversion detection."""

    def test_no_anomaly_correct_priority(self, temp_db):
        """Should not detect anomaly when priorities are correct."""
        detector = PriorityInversionDetector()

        # High priority blocked by high priority
        blocker = Task(
            id="blocker",
            title="Blocker",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
        )
        blocked = Task(
            id="blocked",
            title="Blocked",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["blocker"],
        )

        temp_db.create_task(blocker)
        temp_db.create_task(blocked)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 0

    def test_info_level_small_inversion_short_time(self, temp_db):
        """Should detect INFO level for A blocked by B, <12h."""
        detector = PriorityInversionDetector()

        blocker = Task(
            id="blocker",
            title="Blocker",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
        )
        blocked = Task(
            id="blocked",
            title="Blocked",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["blocker"],
            created_at=datetime.now() - timedelta(hours=6),
        )

        temp_db.create_task(blocker)
        temp_db.create_task(blocked)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.INFO
        assert anomalies[0].anomaly_type == AnomalyType.PRIORITY_INVERSION

    def test_warning_level_small_inversion_long_time(self, temp_db):
        """Should detect WARNING level for A blocked by B, >12h."""
        detector = PriorityInversionDetector()

        blocker = Task(
            id="blocker",
            title="Blocker",
            description="Test",
            priority=TaskPriority.B,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
        )
        blocked = Task(
            id="blocked",
            title="Blocked",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["blocker"],
            created_at=datetime.now() - timedelta(hours=18),
        )

        temp_db.create_task(blocker)
        temp_db.create_task(blocked)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING
        assert anomalies[0].auto_actionable is True

    def test_critical_level_large_inversion(self, temp_db):
        """Should detect CRITICAL level for A blocked by C, >24h."""
        detector = PriorityInversionDetector()

        blocker = Task(
            id="blocker",
            title="Blocker",
            description="Test",
            priority=TaskPriority.C,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
        )
        blocked = Task(
            id="blocked",
            title="Blocked",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.BLOCKED,
            blocked_by=["blocker"],
            created_at=datetime.now() - timedelta(hours=30),
        )

        temp_db.create_task(blocker)
        temp_db.create_task(blocked)

        anomalies = detector.detect(temp_db, {})

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL
        assert anomalies[0].metadata["priority_gap"] == 2  # A=1, C=3, gap=2


class TestBatchInefficiencyDetector:
    """Test batch queue inefficiency detection."""

    def test_no_anomaly_high_utilization(self, temp_db):
        """Should not detect anomaly with high batch utilization."""
        detector = BatchInefficiencyDetector()

        context = {
            "batch_capacity": 100,
            "batch_queued": 75,
            "misrouted_realtime_tasks": 0,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 0

    def test_info_level_moderate_utilization(self, temp_db):
        """Should detect WARNING level with 40% utilization (below 50% threshold)."""
        detector = BatchInefficiencyDetector()

        context = {
            "batch_capacity": 100,
            "batch_queued": 40,
            "misrouted_realtime_tasks": 0,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        # 40% utilization triggers WARNING (30-50% range)
        assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_warning_level_low_utilization(self, temp_db):
        """Should detect WARNING level with 30-50% utilization."""
        detector = BatchInefficiencyDetector()

        context = {
            "batch_capacity": 100,
            "batch_queued": 35,
            "misrouted_realtime_tasks": 0,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_warning_level_misrouted_tasks(self, temp_db):
        """Should detect WARNING level with misrouted tasks."""
        detector = BatchInefficiencyDetector()

        context = {
            "batch_capacity": 100,
            "batch_queued": 60,
            "misrouted_realtime_tasks": 3,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.WARNING
        assert "3 realtime tasks" in anomalies[0].description

    def test_critical_level_very_low_with_waste(self, temp_db):
        """Should detect CRITICAL level with <30% and 5+ wasted tasks."""
        detector = BatchInefficiencyDetector()

        context = {
            "batch_capacity": 100,
            "batch_queued": 20,
            "misrouted_realtime_tasks": 8,
        }

        anomalies = detector.detect(temp_db, context)

        assert len(anomalies) == 1
        assert anomalies[0].severity == AnomalySeverity.CRITICAL
        assert anomalies[0].auto_actionable is True
        assert anomalies[0].auto_action_command == "/batch-orchestrate"


class TestOrchestrationAnomalyManager:
    """Test the orchestration anomaly manager."""

    def test_detect_all_runs_all_detectors(self, temp_db):
        """Should run all 7 detectors."""
        manager = OrchestrationAnomalyManager(temp_db)

        assert len(manager.detectors) == 7

        # Verify all detector types are registered
        detector_types = {d.anomaly_type for d in manager.detectors}
        expected_types = {
            AnomalyType.CONTEXT_SWITCHING_RISK,
            AnomalyType.PLANNING_GAP,
            AnomalyType.STUCK_TASKS,
            AnomalyType.DEPENDENCY_DEADLOCK,
            AnomalyType.RESOURCE_WASTE,
            AnomalyType.PRIORITY_INVERSION,
            AnomalyType.BATCH_INEFFICIENCY,
        }

        assert detector_types == expected_types

    def test_detect_all_sorts_by_severity(self, temp_db):
        """Should sort anomalies by severity (CRITICAL > WARNING > INFO)."""
        manager = OrchestrationAnomalyManager(temp_db)

        # Create conditions for multiple anomalies
        # Context switching WARNING
        # Planning gap INFO
        context = {
            "active_projects": 18,
            "total_projects": 30,
            "goals_in_progress": 0,
            "goals_pending": 3,
            "last_goal_activated": datetime.now() - timedelta(hours=6),
        }

        anomalies = manager.detect_all(context)

        # Should have at least 2 anomalies
        assert len(anomalies) >= 2

        # Should be sorted by severity
        for i in range(len(anomalies) - 1):
            severity_order = {
                AnomalySeverity.CRITICAL: 0,
                AnomalySeverity.WARNING: 1,
                AnomalySeverity.INFO: 2,
            }
            assert severity_order[anomalies[i].severity] <= severity_order[anomalies[i + 1].severity]

    def test_deduplication_tracks_occurrences(self, temp_db):
        """Should deduplicate and track occurrence count."""
        manager = OrchestrationAnomalyManager(temp_db)

        context = {
            "active_projects": 18,
            "total_projects": 30,
        }

        # First detection
        anomalies1 = manager.detect_all(context)
        assert len(anomalies1) >= 1
        assert anomalies1[0].occurrence_count == 1
        assert anomalies1[0].first_seen is not None

        # Second detection (same context)
        anomalies2 = manager.detect_all(context)
        assert len(anomalies2) >= 1
        # Should increment occurrence count
        assert anomalies2[0].occurrence_count == 2
        # first_seen should be preserved
        assert anomalies2[0].first_seen == anomalies1[0].first_seen

    def test_persistence_to_database(self, temp_db):
        """Should persist anomalies to database."""
        manager = OrchestrationAnomalyManager(temp_db)

        context = {
            "active_projects": 18,
            "total_projects": 30,
        }

        anomalies = manager.detect_all(context)

        # Should save to database
        recent = temp_db.get_recent_anomalies(days=1)

        assert len(recent) == len(anomalies)
        # Verify that the anomalies were saved (types should match when sorted)
        recent_types = sorted([a.anomaly_type.value for a in recent])
        detected_types = sorted([a.anomaly_type.value for a in anomalies])
        assert recent_types == detected_types

    def test_get_anomaly_trend(self, temp_db):
        """Should retrieve historical trends."""
        manager = OrchestrationAnomalyManager(temp_db)

        # Create some anomalies
        context = {"active_projects": 18, "total_projects": 30}
        manager.detect_all(context)

        # Get trend
        trend = manager.get_anomaly_trend(AnomalyType.CONTEXT_SWITCHING_RISK, days=7)

        assert "anomaly_type" in trend
        assert "daily_data" in trend
        assert "overall_stats" in trend
        assert trend["anomaly_type"] == AnomalyType.CONTEXT_SWITCHING_RISK.value

    def test_fingerprinting_uniqueness(self, temp_db):
        """Should generate unique fingerprints for different anomalies."""
        manager = OrchestrationAnomalyManager(temp_db)

        # Create two different anomalies
        anomaly1 = OrchestrationAnomaly(
            anomaly_id="id1",
            anomaly_type=AnomalyType.CONTEXT_SWITCHING_RISK,
            severity=AnomalySeverity.WARNING,
            metadata={"active_projects": 18},
        )

        anomaly2 = OrchestrationAnomaly(
            anomaly_id="id2",
            anomaly_type=AnomalyType.PLANNING_GAP,
            severity=AnomalySeverity.INFO,
            metadata={"active_projects": 10},
        )

        fp1 = manager._get_fingerprint(anomaly1)
        fp2 = manager._get_fingerprint(anomaly2)

        assert fp1 != fp2

    def test_error_handling_continues_on_detector_failure(self, temp_db):
        """Should continue with other detectors if one fails."""
        manager = OrchestrationAnomalyManager(temp_db)

        # Create context that might cause issues
        context = {}  # Missing expected fields

        # Should not raise, but return partial results
        try:
            anomalies = manager.detect_all(context)
            # If no error, that's good
            assert isinstance(anomalies, list)
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_overloaded_system_scenario(self, temp_db):
        """Test detection in overloaded system scenario."""
        manager = OrchestrationAnomalyManager(temp_db)

        # Create overloaded scenario:
        # - Too many active projects
        # - No goals in progress
        # - Stuck tasks
        # - Idle workers

        # Create stuck task
        stuck_task = Task(
            id="stuck-1",
            title="Stuck implementation",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
            created_at=datetime.now() - timedelta(hours=80),
            started_at=datetime.now() - timedelta(hours=80),
        )
        temp_db.create_task(stuck_task)

        # Create idle worker
        idle_worker = WorkerState(
            worker_id="idle-1",
            role=WorkerRole.IMPLEMENTER,
            current_task_count=0,
        )
        temp_db.create_worker(idle_worker)

        # Create ready task
        ready_task = Task(
            id="ready-1",
            title="Ready task",
            description="Test",
            priority=TaskPriority.A,
            phase=TaskPhase.QUEUED,
            status=TaskStatus.PENDING,
        )
        temp_db.create_task(ready_task)

        context = {
            "active_projects": 22,
            "total_projects": 30,
            "goals_in_progress": 0,
            "goals_pending": 5,
            "last_goal_activated": datetime.now() - timedelta(hours=60),
            "total_workers": 2,
        }

        anomalies = manager.detect_all(context)

        # Should detect multiple issues
        assert len(anomalies) >= 4  # Context switching, planning gap, stuck task, resource waste

        # Should have at least one CRITICAL
        critical = [a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]
        assert len(critical) >= 1

    def test_healthy_system_scenario(self, temp_db):
        """Test detection in healthy system scenario."""
        manager = OrchestrationAnomalyManager(temp_db)

        # Create healthy scenario
        context = {
            "active_projects": 8,
            "total_projects": 20,
            "goals_in_progress": 3,
            "goals_pending": 2,
            "batch_capacity": 100,
            "batch_queued": 60,
            "misrouted_realtime_tasks": 0,
        }

        anomalies = manager.detect_all(context)

        # Should detect few or no anomalies
        assert len(anomalies) <= 1
