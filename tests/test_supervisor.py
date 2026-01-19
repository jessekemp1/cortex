"""
Tests for Cortex Supervisor.

Tests:
- HealthMonitor: stuck task detection and healing
- TaskRouter: shell vs AI routing (Phase 2)
- CortexSupervisor: tick cycle and daemon lifecycle
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch



class TestHealthMonitor:
    """Tests for the HealthMonitor component."""

    def test_health_monitor_creation(self):
        """Test creating a HealthMonitor."""
        from supervisor.health import HealthMonitor

        monitor = HealthMonitor()
        assert monitor.stale_task_hours == 4
        assert monitor.max_retries == 3

    def test_health_monitor_custom_config(self):
        """Test HealthMonitor with custom configuration."""
        from supervisor.health import HealthMonitor

        monitor = HealthMonitor(stale_task_hours=2, max_retries=5)
        assert monitor.stale_task_hours == 2
        assert monitor.max_retries == 5

    def test_check_returns_empty_when_healthy(self):
        """Test that check() returns empty list when no issues."""
        from supervisor.health import HealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue

            queue = BatchTaskQueue(db_path=Path(tmpdir) / "test.db")
            monitor = HealthMonitor(shell_queue=queue)

            issues = monitor.check()
            # No tasks = no issues
            assert len(issues) == 0

    def test_detects_stuck_shell_task(self):
        """Test detection of stuck shell tasks."""
        from supervisor.health import HealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            from intelligence.process_monitor.batch_queue import (
                BatchTaskQueue,
                TaskState,
            )

            queue = BatchTaskQueue(db_path=Path(tmpdir) / "test.db")

            # Create a task that's been "running" for too long
            task = queue.add_task(
                command="echo 'stuck'",
                task_type="test",
                description="Stuck test task",
            )

            # Manually set it to running with old start time
            queue.update_task_state(
                task.task_id,
                TaskState.RUNNING,
                started_at=datetime.now() - timedelta(hours=5),
            )

            monitor = HealthMonitor(shell_queue=queue, stale_task_hours=4)

            # Mock _is_process_alive to return False (no process)
            with patch.object(queue, "_is_process_alive", return_value=False):
                issues = monitor.check()

            assert len(issues) == 1
            assert issues[0].issue_type == "stuck_shell_task"
            assert issues[0].target_id == task.task_id
            assert issues[0].auto_healable is True

    def test_heals_stuck_task_by_retrying(self):
        """Test that stuck tasks are healed by marking failed and retrying."""
        from supervisor.health import HealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            from intelligence.process_monitor.batch_queue import (
                BatchTaskQueue,
                TaskState,
            )

            queue = BatchTaskQueue(db_path=Path(tmpdir) / "test.db")

            # Create stuck task
            task = queue.add_task(
                command="echo 'stuck'",
                task_type="test",
                description="Stuck test task",
            )
            queue.update_task_state(
                task.task_id,
                TaskState.RUNNING,
                started_at=datetime.now() - timedelta(hours=5),
            )

            monitor = HealthMonitor(shell_queue=queue, stale_task_hours=4)

            with patch.object(queue, "_is_process_alive", return_value=False):
                actions = monitor.check_and_heal()

            assert len(actions) == 1
            assert actions[0].success is True
            assert actions[0].action == "retried"

            # Task should now be pending again (retry resets state)
            updated_task = queue.get_task(task.task_id)
            assert updated_task.state == TaskState.PENDING
            assert updated_task.retry_count == 1

    def test_does_not_heal_task_at_max_retries(self):
        """Test that tasks at max retries are not auto-healed."""
        from supervisor.health import HealthMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            from intelligence.process_monitor.batch_queue import (
                BatchTaskQueue,
                TaskState,
            )

            queue = BatchTaskQueue(db_path=Path(tmpdir) / "test.db")

            # Create task at max retries
            task = queue.add_task(
                command="echo 'stuck'",
                task_type="test",
                description="Stuck test task",
            )
            queue.update_task_state(
                task.task_id,
                TaskState.RUNNING,
                started_at=datetime.now() - timedelta(hours=5),
            )

            # Manually set retry count to max
            import sqlite3

            conn = sqlite3.connect(queue.db_path)
            conn.execute(
                "UPDATE batch_tasks SET retry_count = ? WHERE task_id = ?",
                (3, task.task_id),
            )
            conn.commit()
            conn.close()

            monitor = HealthMonitor(shell_queue=queue, stale_task_hours=4, max_retries=3)

            with patch.object(queue, "_is_process_alive", return_value=False):
                issues = monitor.check()

            # Issue should be detected but not auto-healable
            assert len(issues) == 1
            assert issues[0].auto_healable is False
            assert issues[0].severity == "critical"


class TestSupervisorConfig:
    """Tests for SupervisorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        from supervisor.config import SupervisorConfig

        config = SupervisorConfig()
        assert config.tick_interval_seconds == 30
        assert config.health_check_interval_seconds == 60
        assert config.max_concurrent_shell_tasks == 3
        assert config.stale_task_hours == 4

    def test_config_from_env(self):
        """Test configuration from environment variables."""
        import os

        from supervisor.config import SupervisorConfig

        os.environ["CORTEX_SUPERVISOR_TICK_INTERVAL"] = "15"
        os.environ["CORTEX_SUPERVISOR_MAX_CONCURRENT"] = "5"

        try:
            config = SupervisorConfig.from_env()
            assert config.tick_interval_seconds == 15
            assert config.max_concurrent_shell_tasks == 5
        finally:
            del os.environ["CORTEX_SUPERVISOR_TICK_INTERVAL"]
            del os.environ["CORTEX_SUPERVISOR_MAX_CONCURRENT"]


class TestTickResult:
    """Tests for TickResult model."""

    def test_tick_result_creation(self):
        """Test creating a TickResult."""
        from supervisor.models import TickResult

        result = TickResult()
        assert result.work_discovered == 0
        assert result.shell_tasks_started == 0
        assert result.tasks_healed == 0

    def test_tick_result_summary(self):
        """Test TickResult summary generation."""
        from supervisor.models import TickResult

        result = TickResult(
            work_discovered=5,
            shell_tasks_started=3,
            tasks_healed=1,
        )

        summary = result.summary()
        assert "discovered=5" in summary
        assert "shell_started=3" in summary
        assert "healed=1" in summary

    def test_tick_result_to_dict(self):
        """Test TickResult serialization."""
        from supervisor.models import TickResult

        result = TickResult(
            work_discovered=2,
            shell_tasks_started=1,
            shell_task_ids=["task_1"],
        )

        data = result.to_dict()
        assert data["work_discovered"] == 2
        assert data["shell_tasks_started"] == 1
        assert data["shell_task_ids"] == ["task_1"]
        assert "timestamp" in data


class TestCortexSupervisor:
    """Tests for the main CortexSupervisor class."""

    def test_supervisor_creation(self):
        """Test creating a CortexSupervisor."""
        from supervisor import CortexSupervisor

        supervisor = CortexSupervisor()
        assert supervisor.config is not None
        assert supervisor.health_monitor is not None
        assert supervisor.shell_queue is not None
        assert supervisor.shell_executor is not None

    def test_tick_with_empty_queue(self):
        """Test tick() with no tasks."""
        from supervisor import CortexSupervisor, SupervisorConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue
            from intelligence.process_monitor.batch_executor import BatchExecutor

            # Create isolated queue for test
            queue = BatchTaskQueue(db_path=Path(tmpdir) / "test.db")
            config = SupervisorConfig()

            supervisor = CortexSupervisor(config=config)
            supervisor.shell_queue = queue
            supervisor.shell_executor = BatchExecutor(queue=queue)

            result = supervisor.tick()

            assert result.shell_tasks_started == 0
            assert result.work_discovered == 0
            assert result.errors == []

    def test_tick_executes_ready_tasks(self):
        """Test that tick() executes tasks that are ready."""
        from supervisor import CortexSupervisor

        with tempfile.TemporaryDirectory() as tmpdir:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue

            queue = BatchTaskQueue(db_path=Path(tmpdir) / "test.db")

            # Add a task that's ready to run
            task = queue.add_task(
                command="echo 'test'",
                task_type="test",
                description="Test task",
            )

            from supervisor import SupervisorConfig

            config = SupervisorConfig()
            supervisor = CortexSupervisor(config=config)
            supervisor.shell_queue = queue

            # Mock executor to track calls
            mock_executor = MagicMock()
            mock_executor.can_execute_now.return_value = (True, "")
            supervisor.shell_executor = mock_executor

            result = supervisor.tick()

            # Executor should have been called
            mock_executor.execute_task_async.assert_called_once()
            assert result.shell_tasks_started == 1

    def test_run_once(self):
        """Test run_once() returns a TickResult."""
        from supervisor import CortexSupervisor

        supervisor = CortexSupervisor()
        result = supervisor.run_once()

        assert result is not None
        assert hasattr(result, "timestamp")
        assert hasattr(result, "shell_tasks_started")

    def test_get_queue_summary(self):
        """Test queue summary generation."""
        from supervisor import CortexSupervisor

        supervisor = CortexSupervisor()
        summary = supervisor.get_queue_summary()

        assert "total_tasks" in summary
        assert "by_state" in summary
        assert "running" in summary
        assert "ready" in summary

    def test_status_when_not_running(self):
        """Test status() when supervisor is not running."""
        from supervisor import CortexSupervisor

        supervisor = CortexSupervisor()
        status = supervisor.status()

        assert status["running"] is False
        assert "message" in status


class TestWorkItem:
    """Tests for WorkItem model."""

    def test_work_item_creation(self):
        """Test creating a WorkItem."""
        from supervisor.models import WorkItem, WorkItemPriority

        item = WorkItem(
            id="test_1",
            source="recommendation",
            task_type="test",
            description="Test work item",
            command="pytest tests/",
            priority=WorkItemPriority.HIGH,
            confidence=0.9,
        )

        assert item.id == "test_1"
        assert item.source == "recommendation"
        assert item.command == "pytest tests/"
        assert item.priority == WorkItemPriority.HIGH

    def test_work_item_priority_score(self):
        """Test priority score calculation."""
        from supervisor.models import WorkItem, WorkItemPriority

        high_priority = WorkItem(
            id="high",
            source="test",
            task_type="test",
            description="High priority",
            priority=WorkItemPriority.HIGH,
            confidence=0.9,
        )

        low_priority = WorkItem(
            id="low",
            source="test",
            task_type="test",
            description="Low priority",
            priority=WorkItemPriority.LOW,
            confidence=0.5,
        )

        assert high_priority.priority_score > low_priority.priority_score


class TestRoutedTask:
    """Tests for RoutedTask model."""

    def test_routed_task_as_shell_task(self):
        """Test converting RoutedTask to shell task kwargs."""
        from supervisor.models import RoutedTask, TaskTarget, WorkItem

        work_item = WorkItem(
            id="test_1",
            source="recommendation",
            task_type="test",
            description="Run tests",
            command="pytest tests/",
        )

        routed = RoutedTask(
            work_item=work_item,
            target=TaskTarget.SHELL,
            priority="normal",
        )

        shell_kwargs = routed.as_shell_task()
        assert shell_kwargs["command"] == "pytest tests/"
        assert shell_kwargs["task_type"] == "test"
        assert shell_kwargs["description"] == "Run tests"
        assert shell_kwargs["priority"] == "normal"

    def test_routed_task_as_ai_request(self):
        """Test converting RoutedTask to AI request format."""
        from supervisor.models import RoutedTask, TaskTarget, WorkItem

        work_item = WorkItem(
            id="test_1",
            source="recommendation",
            task_type="research",
            description="Analyze code",
            prompt="Analyze the authentication module",
            system_prompt="You are a code reviewer.",
        )

        routed = RoutedTask(
            work_item=work_item,
            target=TaskTarget.AI_BATCH,
            priority="normal",
            estimated_tokens=1000,
        )

        ai_request = routed.as_ai_request()
        assert ai_request["custom_id"] == "test_1"
        assert "messages" in ai_request["params"]
        assert ai_request["params"]["system"] == "You are a code reviewer."
