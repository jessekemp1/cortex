#!/usr/bin/env python3
"""
Test script for orchestration database.

Verifies:
- Database creation
- Task CRUD operations
- Worker state management
- Trace event logging
- Dependency tracking
- Migration from batch_queue.db
"""

import uuid
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from orchestration.database import OrchestrationDatabase
from orchestration.models import (
    Task,
    TaskPhase,
    TaskPriority,
    TaskStatus,
    ExecutionBackend,
    WorkerState,
    WorkerRole,
    TraceEventType,
    ValidationCriteria,
    create_task_event,
)


def test_database_creation():
    """Test database initialization."""
    print("\n=== Testing Database Creation ===")

    # Use temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Check database exists
    assert db.db_path.exists(), "Database file not created"
    print(f"✅ Database created at: {db.db_path}")

    # Get stats (should be empty)
    stats = db.get_stats()
    print(f"✅ Database stats: {stats}")

    # Cleanup
    db_path.unlink()


def test_task_operations():
    """Test task CRUD operations."""
    print("\n=== Testing Task Operations ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Create a task
    task = Task(
        id=str(uuid.uuid4()),
        title="Test Task",
        description="This is a test task for database validation",
        priority=TaskPriority.A,
        deadline=datetime.now() + timedelta(hours=4),
        prompt="Test prompt for task execution",
        files_affected=["test.py", "models.py"],
        tags=["test", "validation"],
        source="test_script",
    )

    # Add validation criteria
    validation = ValidationCriteria(
        requires_unit_tests=True,
        test_commands=["pytest test_database.py"],
        success_patterns=["All tests passed"],
        required_files=["test_database.py"],
    )

    db.create_task(task, validation)
    print(f"✅ Created task: {task.id}")

    # Retrieve task
    retrieved = db.get_task(task.id)
    assert retrieved is not None, "Failed to retrieve task"
    assert retrieved.title == task.title
    assert retrieved.priority == TaskPriority.A
    print(f"✅ Retrieved task: {retrieved.title}")

    # Retrieve validation criteria
    retrieved_validation = db.get_validation_criteria(task.id)
    assert retrieved_validation is not None
    assert retrieved_validation.requires_unit_tests is True
    print("✅ Retrieved validation criteria")

    # Update task phase
    db.update_task_phase(task.id, TaskPhase.INVESTIGATING)
    updated = db.get_task(task.id)
    assert updated.phase == TaskPhase.INVESTIGATING
    print(f"✅ Updated task phase to: {updated.phase.value}")

    # Update execution backend
    db.update_task_execution_backend(task.id, ExecutionBackend.API_REALTIME)
    print("✅ Updated execution backend")

    # Test ready tasks query
    # Note: Task is PENDING status but INVESTIGATING phase, so it will show up
    # In a real scenario, we'd mark it as RUNNING when investigation starts
    ready_tasks = db.get_ready_tasks()
    assert len(ready_tasks) == 1  # Task still has PENDING status
    print(f"✅ Get ready tasks: {len(ready_tasks)}")

    # Update status to RUNNING to exclude from ready queue
    task.status = TaskStatus.RUNNING
    db.update_task(task)
    ready_tasks_after = db.get_ready_tasks()
    assert len(ready_tasks_after) == 0  # Now excluded because status is RUNNING
    print(f"✅ Get ready tasks after status update: {len(ready_tasks_after)}")

    # Cleanup
    db_path.unlink()


def test_dependency_tracking():
    """Test task dependency management."""
    print("\n=== Testing Dependency Tracking ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Create parent task
    parent_task = Task(
        id=str(uuid.uuid4()),
        title="Parent Task",
        description="This task must complete first",
        priority=TaskPriority.A,
        status=TaskStatus.PENDING,
    )
    db.create_task(parent_task)

    # Create dependent task
    dependent_task = Task(
        id=str(uuid.uuid4()),
        title="Dependent Task",
        description="This task depends on parent",
        priority=TaskPriority.B,
        blocked_by=[parent_task.id],
        status=TaskStatus.BLOCKED,
    )
    db.create_task(dependent_task)

    print(f"✅ Created parent task: {parent_task.id}")
    print(f"✅ Created dependent task: {dependent_task.id} (blocked by parent)")

    # Get ready tasks (should not include dependent task)
    ready = db.get_ready_tasks()
    ready_ids = [t.id for t in ready]
    assert parent_task.id in ready_ids
    assert dependent_task.id not in ready_ids
    print(f"✅ Ready tasks: {len(ready)} (excludes blocked task)")

    # Get blocked tasks
    blocked = db.get_blocked_tasks()
    assert len(blocked) == 1
    assert blocked[0].id == dependent_task.id
    print(f"✅ Blocked tasks: {len(blocked)}")

    # Complete parent task
    parent_task.phase = TaskPhase.COMPLETED
    parent_task.status = TaskStatus.COMPLETED
    parent_task.completed_at = datetime.now()
    db.update_task(parent_task)
    print("✅ Completed parent task")

    # Unblock dependent tasks
    unblocked_ids = db.unblock_dependent_tasks(parent_task.id)
    assert dependent_task.id in unblocked_ids
    print(f"✅ Unblocked tasks: {unblocked_ids}")

    # Verify dependent task is now unblocked
    updated_dependent = db.get_task(dependent_task.id)
    assert not updated_dependent.is_blocked
    print("✅ Dependent task is now unblocked")

    # Cleanup
    db_path.unlink()


def test_worker_operations():
    """Test worker state management."""
    print("\n=== Testing Worker Operations ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Create worker
    worker = WorkerState(
        worker_id="test-worker-1",
        role=WorkerRole.IMPLEMENTER,
        max_concurrent_tasks=3,
        specialties=["python", "testing"],
    )
    db.create_worker(worker)
    print(f"✅ Created worker: {worker.worker_id}")

    # Retrieve worker
    retrieved = db.get_worker(worker.worker_id)
    assert retrieved is not None
    assert retrieved.role == WorkerRole.IMPLEMENTER
    print(f"✅ Retrieved worker: {retrieved.worker_id}")

    # Assign task to worker
    task_id = str(uuid.uuid4())
    worker.assign_task(task_id)
    db.update_worker(worker)
    print(f"✅ Assigned task {task_id} to worker")

    # Check worker capacity
    updated_worker = db.get_worker(worker.worker_id)
    assert updated_worker.current_task_count == 1
    assert updated_worker.can_accept_task
    print(f"✅ Worker capacity: {updated_worker.capacity_percent:.1f}%")

    # Complete task
    worker.complete_task(task_id, success=True, duration_minutes=15.5)
    db.update_worker(worker)
    print("✅ Completed task (duration: 15.5 min)")

    # Check updated metrics
    final_worker = db.get_worker(worker.worker_id)
    assert final_worker.current_task_count == 0
    assert final_worker.total_tasks_completed == 1
    assert final_worker.average_task_duration_minutes > 0
    print(f"✅ Worker metrics updated: {final_worker.total_tasks_completed} completed")

    # Get available workers
    available = db.get_available_workers(role=WorkerRole.IMPLEMENTER)
    assert len(available) == 1
    print(f"✅ Available implementers: {len(available)}")

    # Cleanup
    db_path.unlink()


def test_trace_events():
    """Test trace event logging."""
    print("\n=== Testing Trace Events ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Create a task
    task = Task(
        id=str(uuid.uuid4()),
        title="Test Task for Events",
        description="Testing trace events",
        priority=TaskPriority.B,
    )
    db.create_task(task)

    # Log task creation event
    event = create_task_event(
        TraceEventType.TASK_CREATED,
        task,
        f"Created task: {task.title}",
        details={"priority": task.priority.value},
    )
    db.add_trace_event(event)
    print("✅ Logged task creation event")

    # Log phase change event
    task.advance_phase()
    phase_event = create_task_event(
        TraceEventType.TASK_PHASE_CHANGED,
        task,
        f"Phase changed to {task.phase.value}",
    )
    db.add_trace_event(phase_event)
    print("✅ Logged phase change event")

    # Retrieve events for task
    events = db.get_trace_events(task_id=task.id)
    assert len(events) == 2
    print(f"✅ Retrieved {len(events)} events for task")

    # Print events
    for evt in events:
        print(f"   - {evt}")

    # Cleanup
    db_path.unlink()


def test_migration():
    """Test migration from batch_queue.db."""
    print("\n=== Testing Migration ===")

    # Check if batch_queue.db exists
    batch_queue_path = Path.home() / ".cortex" / "batch_queue.db"

    if not batch_queue_path.exists():
        print("⚠️  Skipping migration test (batch_queue.db not found)")
        return

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Migrate tasks
    migrated_count = db.migrate_from_batch_queue(batch_queue_path)
    print(f"✅ Migrated {migrated_count} tasks from batch_queue.db")

    # Get stats
    stats = db.get_stats()
    print("✅ Database stats after migration:")
    for key, value in stats.items():
        print(f"   - {key}: {value}")

    # Cleanup
    db_path.unlink()


def main():
    """Run all tests."""
    print("╔══════════════════════════════════════════════════════╗")
    print("║   Orchestration Database Test Suite                 ║")
    print("╚══════════════════════════════════════════════════════╝")

    tests = [
        test_database_creation,
        test_task_operations,
        test_dependency_tracking,
        test_worker_operations,
        test_trace_events,
        test_migration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 56}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 56}\n")

    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed")


if __name__ == "__main__":
    main()
