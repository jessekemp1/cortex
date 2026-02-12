"""
Basic tests for task queue system.

Run with: pytest cortex/orchestration/test_queue_system.py -v
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from orchestration.scheduler import TaskScheduler
from orchestration.task import Task, TaskPhase, TaskPriority, TaskStatus
from orchestration.task_queue import TaskQueue


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def queue(temp_db):
    """Create fresh queue for each test"""
    return TaskQueue(db_path=temp_db)


@pytest.fixture
def scheduler(queue):
    """Create scheduler with test queue"""
    return TaskScheduler(queue=queue)


class TestTask:
    """Test Task dataclass functionality"""

    def test_task_creation(self):
        """Test basic task creation"""
        task = Task(
            id="test-1",
            title="Test Task",
            description="A test task for validation",
            priority=TaskPriority.B,
        )

        assert task.id == "test-1"
        assert task.priority == TaskPriority.B
        assert task.phase == TaskPhase.QUEUED
        assert task.status == TaskStatus.PENDING
        assert task.estimated_input_tokens > 0  # Auto-calculated

    def test_token_estimation(self):
        """Test automatic token estimation"""
        description = "x" * 400  # ~100 tokens
        task = Task(
            id="test-2",
            title="Token test",
            description=description,
            priority=TaskPriority.A,
        )

        assert task.estimated_input_tokens == 100
        assert task.total_estimated_tokens == 4100  # 100 + 4000 default output

    def test_deadline_calculation(self):
        """Test deadline calculations"""
        # Task with 1 hour deadline
        task = Task(
            id="test-3",
            title="Urgent task",
            description="Must complete soon",
            priority=TaskPriority.B,
            deadline=datetime.now() + timedelta(hours=1),
        )

        assert task.hours_until_deadline == pytest.approx(1.0, abs=0.1)
        assert task.is_urgent  # < 2 hours

    def test_phase_advancement(self):
        """Test phase transitions"""
        task = Task(
            id="test-4",
            title="Phase test",
            description="Testing phase advancement",
            priority=TaskPriority.A,
        )

        assert task.phase == TaskPhase.QUEUED

        task.advance_phase()
        assert task.phase == TaskPhase.INVESTIGATING

        task.advance_phase()
        assert task.phase == TaskPhase.PLANNING

        task.advance_phase()
        assert task.phase == TaskPhase.IMPLEMENTING

        task.advance_phase()
        assert task.phase == TaskPhase.TESTING

        task.advance_phase()
        assert task.phase == TaskPhase.COMPLETED
        assert task.status == TaskStatus.COMPLETED

    def test_task_serialization(self):
        """Test to_dict/from_dict round-trip"""
        original = Task(
            id="test-5",
            title="Serialization test",
            description="Testing JSON serialization",
            priority=TaskPriority.B,
            deadline=datetime.now() + timedelta(hours=24),
        )

        # Serialize
        data = original.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == "test-5"

        # Deserialize
        restored = Task.from_dict(data)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.priority == original.priority


class TestTaskQueue:
    """Test TaskQueue persistence and operations"""

    def test_enqueue_dequeue(self, queue):
        """Test basic enqueue/dequeue"""
        task = Task(
            id="queue-1",
            title="Queue test",
            description="Testing queue operations",
            priority=TaskPriority.B,
        )

        # Enqueue
        queue.enqueue(task)
        assert queue.size() == 1

        # Dequeue marks as scheduled
        dequeued = queue.dequeue()
        assert dequeued.id == "queue-1"
        # After dequeue, it's marked as scheduled
        assert dequeued.status == TaskStatus.SCHEDULED

    def test_priority_ordering(self, queue):
        """Test priority-based ordering (A > B > C)"""
        # Add tasks in reverse priority order
        task_c = Task(id="c", title="C", description="Low priority", priority=TaskPriority.C)
        task_b = Task(id="b", title="B", description="Medium priority", priority=TaskPriority.B)
        task_a = Task(id="a", title="A", description="High priority", priority=TaskPriority.A)

        queue.enqueue(task_c)
        queue.enqueue(task_b)
        queue.enqueue(task_a)

        # Should dequeue in priority order: A, B, C
        first = queue.dequeue()
        assert first.id == "a"

        second = queue.dequeue()
        assert second.id == "b"

        third = queue.dequeue()
        assert third.id == "c"

    def test_dependency_tracking(self, queue):
        """Test blocked_by/blocks relationships"""
        task1 = Task(
            id="dep-1", title="First", description="Must complete first", priority=TaskPriority.B
        )
        task2 = Task(
            id="dep-2",
            title="Second",
            description="Depends on first",
            priority=TaskPriority.B,
            blocked_by=["dep-1"],
        )
        task1.blocks = ["dep-2"]

        queue.enqueue(task1)
        queue.enqueue(task2)

        # Only task1 should be ready
        ready = queue.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "dep-1"

        # Blocked tasks
        blocked = queue.get_blocked_tasks()
        assert len(blocked) == 1
        assert blocked[0].id == "dep-2"

        # Complete task1
        queue.complete_task("dep-1")

        # Now task2 should be ready
        ready = queue.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "dep-2"

    def test_persistence(self, temp_db):
        """Test SQLite persistence across instances"""
        # Create queue, add task, close
        queue1 = TaskQueue(db_path=temp_db)
        task = Task(
            id="persist-1", title="Persist", description="Test persistence", priority=TaskPriority.A
        )
        queue1.enqueue(task)

        # Create new queue instance with same DB
        queue2 = TaskQueue(db_path=temp_db)
        assert queue2.size() == 1

        retrieved = queue2.get("persist-1")
        assert retrieved is not None
        assert retrieved.title == "Persist"

    def test_queue_stats(self, queue):
        """Test statistics collection"""
        # Add mix of tasks
        queue.enqueue(Task(id="s1", title="T1", description="Test", priority=TaskPriority.A))
        queue.enqueue(Task(id="s2", title="T2", description="Test", priority=TaskPriority.B))
        queue.enqueue(Task(id="s3", title="T3", description="Test", priority=TaskPriority.C))

        stats = queue.get_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 3
        assert stats["by_priority"]["A"] == 1
        assert stats["by_priority"]["B"] == 1
        assert stats["by_priority"]["C"] == 1


class TestScheduler:
    """Test task scheduling logic"""

    def test_priority_a_always_realtime(self, scheduler):
        """Priority A always routes to realtime"""
        task = Task(
            id="sched-a",
            title="Critical",
            description="Critical task",
            priority=TaskPriority.A,
        )

        decision = scheduler.schedule(task)
        assert decision.execution_mode == "realtime"
        assert "Priority A" in decision.reason

    def test_priority_c_always_batch(self, scheduler):
        """Priority C always routes to batch"""
        task = Task(
            id="sched-c",
            title="Background",
            description="Background task",
            priority=TaskPriority.C,
        )

        decision = scheduler.schedule(task)
        assert decision.execution_mode == "batch"
        assert "Priority C" in decision.reason

    def test_priority_b_deadline_routing(self, scheduler):
        """Priority B routes based on deadline"""
        # Short deadline: realtime
        task_short = Task(
            id="sched-b-short",
            title="Short deadline",
            description="Must finish soon",
            priority=TaskPriority.B,
            deadline=datetime.now() + timedelta(hours=2),
        )
        decision_short = scheduler.schedule(task_short)
        assert decision_short.execution_mode == "realtime"

        # Long deadline: batch
        task_long = Task(
            id="sched-b-long",
            title="Long deadline",
            description="Can wait",
            priority=TaskPriority.B,
            deadline=datetime.now() + timedelta(hours=24),
        )
        decision_long = scheduler.schedule(task_long)
        assert decision_long.execution_mode == "batch"

    def test_urgent_override(self, scheduler):
        """Urgent tasks force realtime regardless of priority"""
        task = Task(
            id="sched-urgent",
            title="Urgent",
            description="Very urgent",
            priority=TaskPriority.B,
            deadline=datetime.now() + timedelta(minutes=30),
        )

        decision = scheduler.schedule(task)
        assert decision.execution_mode == "realtime"
        assert "Urgent" in decision.reason

    def test_enqueue_and_schedule(self, scheduler):
        """Test combined enqueue + schedule operation"""
        task = Task(
            id="sched-combo",
            title="Combo test",
            description="Test enqueue and schedule",
            priority=TaskPriority.B,
            deadline=datetime.now() + timedelta(hours=24),
        )

        decision = scheduler.enqueue_and_schedule(task)
        assert decision.execution_mode == "batch"

        # Verify in queue with execution mode set but still pending
        queued = scheduler.queue.get("sched-combo")
        assert queued is not None
        assert queued.execution_mode == "batch"
        assert queued.status == TaskStatus.PENDING  # Still pending until assigned

    def test_scheduling_stats(self, scheduler):
        """Test scheduling statistics"""
        # Add mix of tasks
        scheduler.enqueue_and_schedule(
            Task(id="stat-1", title="T1", description="Test", priority=TaskPriority.A)
        )
        scheduler.enqueue_and_schedule(
            Task(id="stat-2", title="T2", description="Test", priority=TaskPriority.C)
        )

        stats = scheduler.get_scheduling_stats()
        assert stats["total_pending"] == 2
        assert stats["realtime"] == 1
        assert stats["batch"] == 1

    def test_cost_savings_estimate(self, scheduler):
        """Test batch cost savings calculation"""
        # Add batch task
        task = Task(
            id="cost-1",
            title="Batch task",
            description="x" * 4000,  # ~1000 tokens
            priority=TaskPriority.C,
        )
        scheduler.enqueue_and_schedule(task)

        savings = scheduler.estimate_batch_cost_savings()
        assert savings["batch_tasks"] == 1
        assert savings["savings_pct"] == 50.0
        assert savings["savings_usd"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
