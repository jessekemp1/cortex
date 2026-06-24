"""Tests for OrchestrationAnomalyManager and individual anomaly detectors.

Covers: manager initialization, detector registration, context-switching detection,
planning gap detection, stuck task detection, batch inefficiency detection,
deduplication, fingerprinting, alert dispatch, severity ordering, and error resilience.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cortex.orchestration.anomaly_detector import (
    AnomalySeverity,
    AnomalyType,
    BatchInefficiencyDetector,
    ContextSwitchingDetector,
    OrchestrationAnomaly,
    OrchestrationAnomalyManager,
    PlanningGapDetector,
    ResourceWasteDetector,
    StuckTasksDetector,
)
from cortex.orchestration.models import WorkerRole, WorkerState
from cortex.orchestration.task import Task, TaskPhase, TaskPriority, TaskStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Mock OrchestrationDatabase with sane defaults."""
    db = MagicMock()
    db.get_tasks_by_status.return_value = []
    db.get_blocked_tasks.return_value = []
    db.get_available_workers.return_value = []
    db.get_ready_tasks.return_value = []
    db.get_recent_anomalies.return_value = []
    db.save_anomalies.return_value = None
    db.get_anomaly_trend.return_value = {"count": 0, "trend": "stable"}
    return db


@pytest.fixture
def manager(mock_db):
    """OrchestrationAnomalyManager with alerts disabled."""
    return OrchestrationAnomalyManager(mock_db, enable_alerts=False)


@pytest.fixture
def manager_with_alerts(mock_db):
    """OrchestrationAnomalyManager with alerts enabled."""
    return OrchestrationAnomalyManager(mock_db, enable_alerts=True)


def _make_task(
    task_id: str = "task-1",
    title: str = "Test task",
    priority: TaskPriority = TaskPriority.B,
    phase: TaskPhase = TaskPhase.IMPLEMENTING,
    status: TaskStatus = TaskStatus.RUNNING,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    blocked_by: list[str] | None = None,
) -> Task:
    """Helper to build a Task with sensible defaults."""
    return Task(
        id=task_id,
        title=title,
        description="Test task description",
        priority=priority,
        phase=phase,
        status=status,
        created_at=created_at or datetime.now(),
        started_at=started_at,
        blocked_by=blocked_by or [],
    )


def _make_worker(
    worker_id: str = "w-1",
    current_task_count: int = 0,
) -> WorkerState:
    return WorkerState(
        worker_id=worker_id,
        role=WorkerRole.IMPLEMENTER,
        current_task_count=current_task_count,
    )


# ---------------------------------------------------------------------------
# Manager initialization and registration
# ---------------------------------------------------------------------------


class TestManagerInit:
    def test_registers_all_seven_detectors(self, manager):
        assert len(manager.detectors) == 7

    def test_detector_types_are_unique(self, manager):
        types = [d.anomaly_type for d in manager.detectors]
        assert len(types) == len(set(types))

    def test_detector_names_are_nonempty(self, manager):
        for d in manager.detectors:
            assert isinstance(d.name, str)
            assert len(d.name) > 0

    def test_stores_db_reference(self, manager, mock_db):
        assert manager.db is mock_db


# ---------------------------------------------------------------------------
# ContextSwitchingDetector
# ---------------------------------------------------------------------------


class TestContextSwitchingDetector:
    def setup_method(self):
        self.detector = ContextSwitchingDetector()
        self.db = MagicMock()

    def test_no_anomaly_below_threshold(self):
        result = self.detector.detect(self.db, {"active_projects": 5})
        assert result == []

    def test_info_at_11_projects(self):
        result = self.detector.detect(self.db, {"active_projects": 11})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.INFO

    def test_warning_at_16_projects(self):
        result = self.detector.detect(self.db, {"active_projects": 16})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.WARNING

    def test_critical_at_21_projects(self):
        result = self.detector.detect(self.db, {"active_projects": 21})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL

    def test_warning_at_high_active_percentage(self):
        result = self.detector.detect(self.db, {"active_projects": 8, "total_projects": 10})
        # 80% active → WARNING (>70%)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.WARNING

    def test_critical_at_very_high_percentage(self):
        result = self.detector.detect(self.db, {"active_projects": 9, "total_projects": 10})
        # 90% active → CRITICAL (>85%)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL

    def test_anomaly_type_is_context_switching(self):
        result = self.detector.detect(self.db, {"active_projects": 16})
        assert result[0].anomaly_type == AnomalyType.CONTEXT_SWITCHING_RISK

    def test_remediation_is_set(self):
        result = self.detector.detect(self.db, {"active_projects": 16})
        assert (
            "backlog" in result[0].remediation.lower() or "pause" in result[0].remediation.lower()
        )


# ---------------------------------------------------------------------------
# PlanningGapDetector
# ---------------------------------------------------------------------------


class TestPlanningGapDetector:
    def setup_method(self):
        self.detector = PlanningGapDetector()
        self.db = MagicMock()

    def test_no_anomaly_when_goals_in_progress(self):
        ctx = {"active_projects": 5, "goals_in_progress": 2, "goals_pending": 3}
        assert self.detector.detect(self.db, ctx) == []

    def test_no_anomaly_when_no_active_projects(self):
        ctx = {"active_projects": 0, "goals_in_progress": 0, "goals_pending": 3}
        assert self.detector.detect(self.db, ctx) == []

    def test_no_anomaly_when_no_pending_goals(self):
        ctx = {"active_projects": 5, "goals_in_progress": 0, "goals_pending": 0}
        assert self.detector.detect(self.db, ctx) == []

    def test_info_for_recent_gap(self):
        ctx = {
            "active_projects": 5,
            "goals_in_progress": 0,
            "goals_pending": 3,
            "last_goal_activated": datetime.now() - timedelta(hours=10),
        }
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.INFO

    def test_warning_for_day_old_gap(self):
        ctx = {
            "active_projects": 5,
            "goals_in_progress": 0,
            "goals_pending": 3,
            "last_goal_activated": datetime.now() - timedelta(hours=30),
        }
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.WARNING

    def test_critical_for_old_gap(self):
        ctx = {
            "active_projects": 5,
            "goals_in_progress": 0,
            "goals_pending": 3,
            "last_goal_activated": datetime.now() - timedelta(hours=72),
        }
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL

    def test_critical_when_no_last_goal_activated(self):
        """Unknown last activation treated as very long gap → CRITICAL."""
        ctx = {
            "active_projects": 5,
            "goals_in_progress": 0,
            "goals_pending": 3,
        }
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL

    def test_auto_actionable_set(self):
        ctx = {
            "active_projects": 5,
            "goals_in_progress": 0,
            "goals_pending": 3,
        }
        result = self.detector.detect(self.db, ctx)
        assert result[0].auto_actionable is True
        assert result[0].auto_action_command == "/briefing"


# ---------------------------------------------------------------------------
# StuckTasksDetector
# ---------------------------------------------------------------------------


class TestStuckTasksDetector:
    def setup_method(self):
        self.detector = StuckTasksDetector()

    def test_no_anomaly_for_fresh_tasks(self, mock_db):
        task = _make_task(started_at=datetime.now() - timedelta(hours=2))
        mock_db.get_tasks_by_status.return_value = [task]
        assert self.detector.detect(mock_db, {}) == []

    def _setup_db_with_task(self, mock_db, task):
        """Return task only for the matching status call, empty for others."""

        def by_status(status, limit=1000):
            if status == task.status:
                return [task]
            return []

        mock_db.get_tasks_by_status.side_effect = by_status

    def test_info_at_48h(self, mock_db):
        task = _make_task(started_at=datetime.now() - timedelta(hours=50))
        self._setup_db_with_task(mock_db, task)
        result = self.detector.detect(mock_db, {})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.INFO

    def test_warning_at_72h_priority_b(self, mock_db):
        task = _make_task(
            started_at=datetime.now() - timedelta(hours=80),
            priority=TaskPriority.B,
        )
        self._setup_db_with_task(mock_db, task)
        result = self.detector.detect(mock_db, {})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.WARNING

    def test_critical_at_72h_priority_a(self, mock_db):
        task = _make_task(
            started_at=datetime.now() - timedelta(hours=80),
            priority=TaskPriority.A,
        )
        self._setup_db_with_task(mock_db, task)
        result = self.detector.detect(mock_db, {})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL

    def test_uses_created_at_when_no_started_at(self, mock_db):
        task = _make_task(
            started_at=None,
            created_at=datetime.now() - timedelta(hours=50),
            status=TaskStatus.PENDING,
        )
        self._setup_db_with_task(mock_db, task)
        result = self.detector.detect(mock_db, {})
        assert len(result) == 1

    def test_affected_entities_contains_task_id(self, mock_db):
        task = _make_task(
            task_id="stuck-123",
            started_at=datetime.now() - timedelta(hours=50),
        )
        mock_db.get_tasks_by_status.return_value = [task]
        result = self.detector.detect(mock_db, {})
        assert "stuck-123" in result[0].affected_entities


# ---------------------------------------------------------------------------
# BatchInefficiencyDetector
# ---------------------------------------------------------------------------


class TestBatchInefficiencyDetector:
    def setup_method(self):
        self.detector = BatchInefficiencyDetector()
        self.db = MagicMock()

    def test_no_anomaly_when_well_utilized(self):
        ctx = {"batch_capacity": 100, "batch_queued": 60}
        assert self.detector.detect(self.db, ctx) == []

    def test_warning_at_low_utilization(self):
        ctx = {"batch_capacity": 100, "batch_queued": 40}
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.WARNING

    def test_critical_with_low_util_and_misrouted(self):
        ctx = {
            "batch_capacity": 100,
            "batch_queued": 20,
            "misrouted_realtime_tasks": 5,
        }
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL

    def test_warning_with_misrouted_only(self):
        ctx = {
            "batch_capacity": 100,
            "batch_queued": 60,
            "misrouted_realtime_tasks": 3,
        }
        result = self.detector.detect(self.db, ctx)
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.WARNING


# ---------------------------------------------------------------------------
# ResourceWasteDetector
# ---------------------------------------------------------------------------


class TestResourceWasteDetector:
    def setup_method(self):
        self.detector = ResourceWasteDetector()

    def test_no_anomaly_when_no_idle_workers(self, mock_db):
        w = _make_worker(current_task_count=2)
        mock_db.get_available_workers.return_value = [w]
        mock_db.get_ready_tasks.return_value = [_make_task()]
        assert self.detector.detect(mock_db, {"total_workers": 1}) == []

    def test_no_anomaly_when_no_ready_tasks(self, mock_db):
        w = _make_worker(current_task_count=0)
        mock_db.get_available_workers.return_value = [w]
        mock_db.get_ready_tasks.return_value = []
        assert self.detector.detect(mock_db, {"total_workers": 1}) == []

    def test_critical_when_majority_idle(self, mock_db):
        workers = [_make_worker(f"w-{i}", current_task_count=0) for i in range(6)]
        mock_db.get_available_workers.return_value = workers
        mock_db.get_ready_tasks.return_value = [_make_task()]
        result = self.detector.detect(mock_db, {"total_workers": 10})
        assert len(result) == 1
        assert result[0].severity == AnomalySeverity.CRITICAL


# ---------------------------------------------------------------------------
# OrchestrationAnomaly serialisation
# ---------------------------------------------------------------------------


class TestAnomalySerialization:
    def test_round_trip_to_dict_and_back(self):
        original = OrchestrationAnomaly(
            anomaly_id="test-123",
            anomaly_type=AnomalyType.CONTEXT_SWITCHING_RISK,
            severity=AnomalySeverity.WARNING,
            title="Test anomaly",
            description="A test description",
            metric_value=16.0,
            threshold_value=15.0,
            affected_entities=["proj-a", "proj-b"],
            metadata={"active_projects": 16},
            remediation="Do something",
        )
        d = original.to_dict()
        restored = OrchestrationAnomaly.from_dict(d)

        assert restored.anomaly_id == "test-123"
        assert restored.anomaly_type == AnomalyType.CONTEXT_SWITCHING_RISK
        assert restored.severity == AnomalySeverity.WARNING
        assert restored.metric_value == 16.0
        assert restored.affected_entities == ["proj-a", "proj-b"]
        assert restored.metadata == {"active_projects": 16}
        assert restored.auto_actionable is False

    def test_from_dict_parses_json_strings(self):
        d = {
            "anomaly_id": "x",
            "anomaly_type": "planning_gap",
            "severity": "CRITICAL",
            "detected_at": datetime.now().isoformat(),
            "title": "t",
            "description": "d",
            "metric_value": 0,
            "threshold_value": 0,
            "affected_entities": '["a", "b"]',
            "metadata": '{"key": "val"}',
            "remediation": "r",
            "auto_actionable": 1,
            "auto_action_command": None,
            "first_seen": None,
            "occurrence_count": 1,
        }
        a = OrchestrationAnomaly.from_dict(d)
        assert a.affected_entities == ["a", "b"]
        assert a.metadata == {"key": "val"}
        assert a.auto_actionable is True


# ---------------------------------------------------------------------------
# Manager.detect_all integration
# ---------------------------------------------------------------------------


class TestDetectAll:
    def test_detect_all_returns_sorted_by_severity(self, manager, mock_db):
        ctx = {"active_projects": 26}
        results = manager.detect_all(ctx)
        # With 26 active projects, should detect context switching (CRITICAL)
        assert len(results) >= 1
        assert results[0].severity == AnomalySeverity.CRITICAL

    def test_detect_all_saves_to_database(self, manager, mock_db):
        manager.detect_all({"active_projects": 16})
        assert mock_db.save_anomalies.call_count == 1

    def test_detect_all_handles_detector_errors_gracefully(self, manager, mock_db):
        """A failing detector should not crash the whole run."""
        # Make get_tasks_by_status raise for StuckTasksDetector
        mock_db.get_tasks_by_status.side_effect = RuntimeError("DB gone")
        mock_db.get_blocked_tasks.side_effect = RuntimeError("DB gone")
        mock_db.get_available_workers.side_effect = RuntimeError("DB gone")

        # Should still succeed (context-switching and batch detectors don't need DB)
        results = manager.detect_all(
            {
                "active_projects": 16,
                "batch_capacity": 100,
                "batch_queued": 20,
            }
        )
        # At least context switching should be detected
        types = [r.anomaly_type for r in results]
        assert AnomalyType.CONTEXT_SWITCHING_RISK in types

    def test_detect_all_returns_empty_for_healthy_state(self, manager, mock_db):
        ctx = {
            "active_projects": 3,
            "goals_in_progress": 2,
            "batch_capacity": 100,
            "batch_queued": 60,
        }
        results = manager.detect_all(ctx)
        assert results == []

    def test_detect_all_multiple_anomaly_types(self, manager, mock_db):
        ctx = {
            "active_projects": 16,
            "goals_in_progress": 0,
            "goals_pending": 5,
            "batch_capacity": 100,
            "batch_queued": 10,
        }
        results = manager.detect_all(ctx)
        types = {r.anomaly_type for r in results}
        assert AnomalyType.CONTEXT_SWITCHING_RISK in types
        assert AnomalyType.PLANNING_GAP in types
        assert AnomalyType.BATCH_INEFFICIENCY in types


# ---------------------------------------------------------------------------
# Deduplication and fingerprinting
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_fingerprint_is_stable_for_same_anomaly(self, manager):
        a1 = OrchestrationAnomaly(
            anomaly_id="id1",
            anomaly_type=AnomalyType.CONTEXT_SWITCHING_RISK,
            severity=AnomalySeverity.WARNING,
            metadata={"active_projects": 16},
        )
        a2 = OrchestrationAnomaly(
            anomaly_id="id2",
            anomaly_type=AnomalyType.CONTEXT_SWITCHING_RISK,
            severity=AnomalySeverity.WARNING,
            metadata={"active_projects": 16},
        )
        assert manager._get_fingerprint(a1) == manager._get_fingerprint(a2)

    def test_fingerprint_differs_for_different_types(self, manager):
        a1 = OrchestrationAnomaly(
            anomaly_id="id1",
            anomaly_type=AnomalyType.CONTEXT_SWITCHING_RISK,
            severity=AnomalySeverity.WARNING,
            metadata={"active_projects": 16},
        )
        a2 = OrchestrationAnomaly(
            anomaly_id="id2",
            anomaly_type=AnomalyType.PLANNING_GAP,
            severity=AnomalySeverity.WARNING,
            metadata={},
        )
        assert manager._get_fingerprint(a1) != manager._get_fingerprint(a2)

    def test_dedup_increments_occurrence_count(self, manager, mock_db):
        """Recurring anomaly should get occurrence_count > 1."""
        existing = OrchestrationAnomaly(
            anomaly_id="old",
            anomaly_type=AnomalyType.CONTEXT_SWITCHING_RISK,
            severity=AnomalySeverity.WARNING,
            metadata={"active_projects": 16},
            occurrence_count=3,
            detected_at=datetime.now() - timedelta(hours=2),
            first_seen=datetime.now() - timedelta(days=2),
        )
        mock_db.get_recent_anomalies.return_value = [existing]

        results = manager.detect_all({"active_projects": 16})
        ctx_anomalies = [r for r in results if r.anomaly_type == AnomalyType.CONTEXT_SWITCHING_RISK]
        assert len(ctx_anomalies) == 1
        assert ctx_anomalies[0].occurrence_count == 4

    def test_dedup_removes_batch_duplicates(self, manager, mock_db):
        """Two identical anomalies in the same batch should deduplicate to one."""
        # The context-switching detector only returns 1, so we test via _deduplicate_and_track
        a1 = OrchestrationAnomaly(
            anomaly_id="dup1",
            anomaly_type=AnomalyType.STUCK_TASKS,
            severity=AnomalySeverity.INFO,
            metadata={"task_id": "t-1"},
            affected_entities=["t-1"],
        )
        a2 = OrchestrationAnomaly(
            anomaly_id="dup2",
            anomaly_type=AnomalyType.STUCK_TASKS,
            severity=AnomalySeverity.INFO,
            metadata={"task_id": "t-1"},
            affected_entities=["t-1"],
        )
        deduped = manager._deduplicate_and_track([a1, a2])
        assert len(deduped) == 1


# ---------------------------------------------------------------------------
# Alert dispatch
# ---------------------------------------------------------------------------


class TestAlertDispatch:
    @patch("cortex.orchestration.anomaly_detector.AlertManager", create=True)
    def test_alerts_sent_for_critical_only(self, MockAlertMgr, mock_db):
        """Only CRITICAL anomalies trigger alert dispatch."""
        mock_alert_instance = MagicMock()
        manager = OrchestrationAnomalyManager(mock_db, enable_alerts=True)
        manager._alert_manager = mock_alert_instance

        manager.detect_all({"active_projects": 26})
        # 26 projects → CRITICAL context switching
        assert mock_alert_instance.send_alert.called
        call_kwargs = mock_alert_instance.send_alert.call_args
        assert (
            call_kwargs[1]["severity"] == "CRITICAL"
            or call_kwargs.kwargs.get("severity") == "CRITICAL"
        )

    def test_no_alerts_when_disabled(self, manager, mock_db):
        """Manager with enable_alerts=False should not attempt alerts."""
        manager._alert_manager = MagicMock()
        manager.detect_all({"active_projects": 26})
        assert manager._alert_manager.send_alert.call_count == 0

    def test_alert_failure_does_not_crash_detection(self, mock_db):
        """If AlertManager.send_alert raises, detect_all still returns results."""
        manager = OrchestrationAnomalyManager(mock_db, enable_alerts=True)
        mock_alert = MagicMock()
        mock_alert.send_alert.side_effect = RuntimeError("notification service down")
        manager._alert_manager = mock_alert

        results = manager.detect_all({"active_projects": 26})
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# get_anomaly_trend
# ---------------------------------------------------------------------------


class TestAnomalyTrend:
    def test_delegates_to_db(self, manager, mock_db):
        mock_db.get_anomaly_trend.return_value = {"count": 5, "trend": "increasing"}
        result = manager.get_anomaly_trend(AnomalyType.STUCK_TASKS, days=14)
        assert result == {"count": 5, "trend": "increasing"}
        mock_db.get_anomaly_trend.assert_called_once_with(AnomalyType.STUCK_TASKS, 14)


# ---------------------------------------------------------------------------
# Base AnomalyDetector.calculate_severity
# ---------------------------------------------------------------------------


class TestCalculateSeverity:
    def test_critical_at_double_threshold(self):
        d = ContextSwitchingDetector()
        assert d.calculate_severity(20, 10, {}) == AnomalySeverity.CRITICAL

    def test_warning_at_1_5x_threshold(self):
        d = ContextSwitchingDetector()
        assert d.calculate_severity(15, 10, {}) == AnomalySeverity.WARNING

    def test_info_below_1_5x(self):
        d = ContextSwitchingDetector()
        assert d.calculate_severity(12, 10, {}) == AnomalySeverity.INFO
