"""
Tests for batch queue task management.

Tests basic queue operations like add_task, get_task, etc.
Command validation has been moved to BatchExecutor.
"""

import tempfile
from pathlib import Path



class TestBasicQueueOperations:
    """Tests for basic BatchTaskQueue operations."""

    def setup_method(self):
        """Create a batch queue with temp directory."""
        from intelligence.process_monitor.batch_queue import BatchTaskQueue

        self.tmpdir = tempfile.mkdtemp()
        self.queue = BatchTaskQueue(db_path=Path(self.tmpdir) / "test_queue.db")

    def test_add_task_accepts_shell_command(self):
        """add_task should accept valid shell commands."""
        task = self.queue.add_task(
            command="python -m cortex briefing",
            task_type="general",
            description="Generate morning briefing",
        )
        assert task.command == "python -m cortex briefing"
        assert task.task_type == "general"
        assert task.description == "Generate morning briefing"

    def test_add_task_with_priority(self):
        """add_task should accept priority parameter."""
        task = self.queue.add_task(
            command="pytest tests/",
            task_type="test",
            description="Run tests",
            priority="high",
        )
        assert task.priority == "high"

    def test_get_task(self):
        """get_task should retrieve task by ID."""
        created_task = self.queue.add_task(
            command="echo test",
            task_type="test",
            description="Test task",
        )

        retrieved_task = self.queue.get_task(created_task.task_id)
        assert retrieved_task is not None
        assert retrieved_task.task_id == created_task.task_id
        assert retrieved_task.command == "echo test"

    def test_add_task_with_dependencies(self):
        """add_task should accept dependencies."""
        task1 = self.queue.add_task(
            command="echo setup",
            task_type="setup",
            description="Setup task",
        )

        task2 = self.queue.add_task(
            command="echo run",
            task_type="run",
            description="Run task",
            dependencies=[task1.task_id],
        )

        assert task2.dependencies == [task1.task_id]
