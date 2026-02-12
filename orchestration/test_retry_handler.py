#!/usr/bin/env python3
"""
Test script for retry handler and failure escalation system.

Verifies:
- Failure classification (all 5 types)
- Retry decision logic
- Exponential backoff calculation
- Max retries exceeded → escalation
- Database persistence of retry configs
- Trace event logging
"""

import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from orchestration.database import OrchestrationDatabase
from orchestration.models import (
    Task,
    TaskPhase,
    TaskPriority,
    TaskStatus,
    TraceEventType,
)
from orchestration.retry_handler import (
    DEFAULT_RETRY_CONFIGS,
    FailureClassifier,
    FailureType,
    RetryConfig,
    RetryHandler,
    RetryStrategy,
)


def test_failure_classification():
    """Test failure type classification from error messages."""
    print("\n=== Testing Failure Classification ===")

    classifier = FailureClassifier()

    # Test transient errors
    transient_errors = [
        "Connection timeout",
        "network unreachable",
        "502 Bad Gateway",
        "Rate limit exceeded",
        "temporary failure in name resolution",
    ]
    for error in transient_errors:
        failure_type = classifier.classify(None, error)
        assert failure_type == FailureType.TRANSIENT, f"Expected TRANSIENT for: {error}"
        print(f"✅ Classified as TRANSIENT: {error[:50]}")

    # Test resource errors
    resource_errors = [
        "Out of memory",
        "Disk full",
        "Quota exceeded",
        "Cannot allocate memory",
        "Too many open files",
    ]
    for error in resource_errors:
        failure_type = classifier.classify(None, error)
        assert failure_type == FailureType.RESOURCE, f"Expected RESOURCE for: {error}"
        print(f"✅ Classified as RESOURCE: {error[:50]}")

    # Test validation errors
    validation_errors = [
        "Test failed: test_example",
        "Assertion error in test_foo",
        "Lint error: unused variable",
        "Type error in module.py",
        "Import error: module not found",
    ]
    for error in validation_errors:
        failure_type = classifier.classify(None, error)
        assert failure_type == FailureType.VALIDATION, f"Expected VALIDATION for: {error}"
        print(f"✅ Classified as VALIDATION: {error[:50]}")

    # Test dependency errors
    dependency_errors = [
        "Blocked by task ABC",
        "Dependency not met: requires task XYZ",
        "Waiting for prerequisite",
        "Missing dependency: package-name",
    ]
    for error in dependency_errors:
        failure_type = classifier.classify(None, error)
        assert failure_type == FailureType.DEPENDENCY, f"Expected DEPENDENCY for: {error}"
        print(f"✅ Classified as DEPENDENCY: {error[:50]}")

    # Test permanent errors
    permanent_errors = [
        "Unauthorized",
        "Access denied",
        "Invalid API key",
        "404 Not Found",
        "Permission denied",
    ]
    for error in permanent_errors:
        failure_type = classifier.classify(None, error)
        assert failure_type == FailureType.PERMANENT, f"Expected PERMANENT for: {error}"
        print(f"✅ Classified as PERMANENT: {error[:50]}")

    # Test unknown errors
    unknown_error = "Something weird happened"
    failure_type = classifier.classify(None, unknown_error)
    assert failure_type == FailureType.UNKNOWN
    print(f"✅ Classified as UNKNOWN: {unknown_error}")

    print("\n✅ All failure classification tests passed")


def test_retry_strategy_mapping():
    """Test that failure types map to correct retry strategies."""
    print("\n=== Testing Retry Strategy Mapping ===")

    classifier = FailureClassifier()

    # Test strategy mappings
    expected_mappings = {
        FailureType.TRANSIENT: RetryStrategy.IMMEDIATE,
        FailureType.RESOURCE: RetryStrategy.EXPONENTIAL,
        FailureType.VALIDATION: RetryStrategy.NO_RETRY,
        FailureType.DEPENDENCY: RetryStrategy.DEPENDENCY_WAIT,
        FailureType.PERMANENT: RetryStrategy.NO_RETRY,
        FailureType.UNKNOWN: RetryStrategy.EXPONENTIAL,
    }

    for failure_type, expected_strategy in expected_mappings.items():
        strategy = classifier.get_strategy(failure_type)
        assert strategy == expected_strategy, f"{failure_type} should map to {expected_strategy}"
        print(f"✅ {failure_type.value} → {strategy.value}")

    print("\n✅ All strategy mapping tests passed")


def test_exponential_backoff():
    """Test exponential backoff calculation with jitter."""
    print("\n=== Testing Exponential Backoff ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)
    handler = RetryHandler(db)

    # Test immediate retry
    config = RetryConfig(
        strategy=RetryStrategy.IMMEDIATE,
        current_retry_count=0,
    )
    delay = handler.calculate_retry_delay(config)
    assert 1 <= delay <= 5, f"Immediate retry should be 1-5 seconds, got {delay}"
    print(f"✅ Immediate retry delay: {delay}s (range: 1-5s)")

    # Test exponential backoff
    config = RetryConfig(
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=10,
        backoff_multiplier=2.0,
        current_retry_count=0,
    )

    delays = []
    for retry_count in range(5):
        config.current_retry_count = retry_count
        delay = handler.calculate_retry_delay(config)
        delays.append(delay)

        # Calculate expected range (base * multiplier^retry_count with 0-20% jitter)
        expected_base = 10 * (2.0**retry_count)
        expected_min = expected_base
        expected_max = expected_base * 1.2

        assert (
            expected_min <= delay <= expected_max
        ), f"Retry {retry_count}: delay {delay}s not in range [{expected_min:.1f}, {expected_max:.1f}]"
        print(
            f"✅ Retry {retry_count}: {delay}s (expected range: {expected_min:.1f}-{expected_max:.1f}s)"
        )

    # Verify delays are increasing
    for i in range(len(delays) - 1):
        assert delays[i] < delays[i + 1], "Delays should be increasing"

    # Test max delay cap
    config = RetryConfig(
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=100,
        backoff_multiplier=3.0,
        max_delay_seconds=500,
        current_retry_count=10,  # Would be huge without cap
    )
    delay = handler.calculate_retry_delay(config)
    assert delay <= 500, f"Delay should be capped at max_delay_seconds (500), got {delay}"
    print(f"✅ Max delay cap enforced: {delay}s (max: 500s)")

    db_path.unlink()
    print("\n✅ All backoff calculation tests passed")


def test_retry_decision_logic():
    """Test retry decision logic for different scenarios."""
    print("\n=== Testing Retry Decision Logic ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)
    handler = RetryHandler(db)

    # Create a test task
    task = Task(
        id=str(uuid.uuid4()),
        title="Test Task",
        description="Task for testing retry logic",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task)

    # Test 1: Transient error - should retry
    decision = handler.handle_failure(
        task=task,
        error="Connection timeout",
        phase=TaskPhase.IMPLEMENTING,
    )
    assert decision.should_retry, "Transient error should trigger retry"
    assert decision.failure_type == FailureType.TRANSIENT
    assert decision.strategy == RetryStrategy.IMMEDIATE
    assert not decision.escalate, "Transient error should not escalate"
    print("✅ Transient error: Retry scheduled")

    # Test 2: Validation error - should NOT retry, should escalate
    task2 = Task(
        id=str(uuid.uuid4()),
        title="Test Task 2",
        description="Task for testing validation failure",
        priority=TaskPriority.B,
        phase=TaskPhase.TESTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task2)

    decision = handler.handle_failure(
        task=task2,
        error="Test failed: test_example AssertionError",
        phase=TaskPhase.TESTING,
    )
    assert not decision.should_retry, "Validation error should not retry"
    assert decision.failure_type == FailureType.VALIDATION
    assert decision.escalate, "Validation error should escalate"
    print("✅ Validation error: No retry, escalated")

    # Test 3: Max retries exceeded - should escalate
    task3 = Task(
        id=str(uuid.uuid4()),
        title="Test Task 3",
        description="Task for testing max retries",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task3)

    # Fail multiple times
    for i in range(4):
        decision = handler.handle_failure(
            task=task3,
            error="Connection timeout",
            phase=TaskPhase.IMPLEMENTING,
        )
        if i < 3:
            assert decision.should_retry, f"Retry {i+1} should be allowed"
            print(f"✅ Retry {i+1}/3 scheduled")
        else:
            assert not decision.should_retry, "Max retries should block retry"
            assert decision.escalate, "Max retries should trigger escalation"
            print("✅ Max retries exceeded: Escalated")

    # Test 4: Resource error - exponential backoff
    task4 = Task(
        id=str(uuid.uuid4()),
        title="Test Task 4",
        description="Task for testing resource failure",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task4)

    decision = handler.handle_failure(
        task=task4,
        error="Out of memory",
        phase=TaskPhase.IMPLEMENTING,
    )
    assert decision.should_retry, "Resource error should retry"
    assert decision.failure_type == FailureType.RESOURCE
    assert decision.strategy == RetryStrategy.EXPONENTIAL
    assert decision.delay_seconds > 50, "Resource error should use longer delay"
    print(f"✅ Resource error: Retry scheduled with {decision.delay_seconds}s delay")

    db_path.unlink()
    print("\n✅ All retry decision tests passed")


def test_retry_config_persistence():
    """Test database persistence of retry configs."""
    print("\n=== Testing Retry Config Persistence ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)

    # Create a task
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        title="Test Task",
        description="Task for testing config persistence",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task)

    # Create a retry config
    config = RetryConfig(
        max_retries=5,
        current_retry_count=2,
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=120,
        backoff_multiplier=2.5,
        failure_type=FailureType.RESOURCE,
        escalated=False,
    )

    db.create_retry_config(task_id, config)
    print("✅ Created retry config")

    # Retrieve config
    retrieved = db.get_retry_config(task_id)
    assert retrieved is not None, "Config should exist"
    assert retrieved.max_retries == 5
    assert retrieved.current_retry_count == 2
    assert retrieved.strategy == RetryStrategy.EXPONENTIAL
    assert retrieved.base_delay_seconds == 120
    assert retrieved.backoff_multiplier == 2.5
    assert retrieved.failure_type == FailureType.RESOURCE
    assert not retrieved.escalated
    print("✅ Retrieved and verified config")

    # Update config
    config.current_retry_count = 3
    config.escalated = True
    config.escalation_reason = "Max retries exceeded"
    config.updated_at = datetime.now()

    db.update_retry_config(task_id, config)
    print("✅ Updated retry config")

    # Retrieve updated config
    updated = db.get_retry_config(task_id)
    assert updated is not None
    assert updated.current_retry_count == 3
    assert updated.escalated
    assert updated.escalation_reason == "Max retries exceeded"
    print("✅ Retrieved and verified updated config")

    # Test non-existent config
    non_existent = db.get_retry_config("non-existent-id")
    assert non_existent is None
    print("✅ Non-existent config returns None")

    db_path.unlink()
    print("\n✅ All persistence tests passed")


def test_escalated_tasks_query():
    """Test querying for escalated tasks."""
    print("\n=== Testing Escalated Tasks Query ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)
    handler = RetryHandler(db)

    # Create tasks
    task1 = Task(
        id=str(uuid.uuid4()),
        title="Normal Task",
        description="Should not be escalated",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task1)

    task2 = Task(
        id=str(uuid.uuid4()),
        title="Escalated Task 1",
        description="Should be escalated",
        priority=TaskPriority.A,
        phase=TaskPhase.TESTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task2)

    task3 = Task(
        id=str(uuid.uuid4()),
        title="Escalated Task 2",
        description="Should also be escalated",
        priority=TaskPriority.A,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task3)

    # Escalate task2 and task3
    handler.handle_failure(task2, "Test failed: critical error", TaskPhase.TESTING)
    handler.handle_failure(task3, "Unauthorized access denied", TaskPhase.IMPLEMENTING)

    # Query escalated tasks
    escalated_tasks = db.get_escalated_tasks()
    escalated_ids = [t.id for t in escalated_tasks]

    assert task2.id in escalated_ids, "task2 should be escalated"
    assert task3.id in escalated_ids, "task3 should be escalated"
    assert task1.id not in escalated_ids, "task1 should not be escalated"

    print(f"✅ Found {len(escalated_tasks)} escalated tasks")
    for task in escalated_tasks:
        print(f"   - {task.title} ({task.phase.value})")

    db_path.unlink()
    print("\n✅ All escalation query tests passed")


def test_trace_event_logging():
    """Test that retry events are logged to trace_events table."""
    print("\n=== Testing Trace Event Logging ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)
    handler = RetryHandler(db)

    # Create a task
    task = Task(
        id=str(uuid.uuid4()),
        title="Test Task",
        description="Task for testing trace events",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
        status=TaskStatus.RUNNING,
    )
    db.create_task(task)

    # Trigger a retry
    handler.handle_failure(
        task=task,
        error="Connection timeout",
        phase=TaskPhase.IMPLEMENTING,
    )

    # Query trace events
    events = db.get_trace_events(task_id=task.id)
    assert len(events) > 0, "Should have trace events"

    # Find retry event
    retry_event = None
    for event in events:
        if event.event_type == TraceEventType.TASK_RETRIED:
            retry_event = event
            break

    assert retry_event is not None, "Should have TASK_RETRIED event"
    assert retry_event.task_id == task.id
    assert "Retry scheduled" in retry_event.message
    assert "failure_type" in retry_event.details
    assert "strategy" in retry_event.details

    print(f"✅ Found retry trace event: {retry_event.message}")
    print(f"   Details: {retry_event.details}")

    db_path.unlink()
    print("\n✅ All trace event tests passed")


def test_default_configs():
    """Test that default retry configs are properly defined."""
    print("\n=== Testing Default Retry Configs ===")

    # Verify all failure types have defaults
    for failure_type in FailureType:
        config = DEFAULT_RETRY_CONFIGS.get(failure_type)
        assert config is not None, f"Missing default config for {failure_type}"
        print(f"✅ {failure_type.value}: {config.strategy.value}, max_retries={config.max_retries}")

    # Verify NO_RETRY types have 0 retries
    for failure_type in [FailureType.VALIDATION, FailureType.PERMANENT]:
        config = DEFAULT_RETRY_CONFIGS[failure_type]
        assert config.max_retries == 0, f"{failure_type} should have 0 retries"
        assert config.strategy == RetryStrategy.NO_RETRY

    # Verify DEPENDENCY has high retry count
    dep_config = DEFAULT_RETRY_CONFIGS[FailureType.DEPENDENCY]
    assert dep_config.max_retries >= 20, "DEPENDENCY should have high retry count"
    assert dep_config.strategy == RetryStrategy.DEPENDENCY_WAIT

    print("\n✅ All default config tests passed")


def test_database_stats():
    """Test that retry configs are included in database stats."""
    print("\n=== Testing Database Stats ===")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    db = OrchestrationDatabase(db_path)
    handler = RetryHandler(db)

    # Create tasks and trigger retries
    for i in range(3):
        task = Task(
            id=str(uuid.uuid4()),
            title=f"Test Task {i+1}",
            description="Task for stats testing",
            priority=TaskPriority.B,
            phase=TaskPhase.IMPLEMENTING,
            status=TaskStatus.RUNNING,
        )
        db.create_task(task)

        if i < 2:
            # First two are transient (retry)
            handler.handle_failure(task, "Connection timeout", TaskPhase.IMPLEMENTING)
        else:
            # Last one is validation (escalate)
            handler.handle_failure(task, "Test failed", TaskPhase.IMPLEMENTING)

    # Get stats
    stats = db.get_stats()

    assert "total_retry_configs" in stats
    assert stats["total_retry_configs"] == 3
    print(f"✅ Total retry configs: {stats['total_retry_configs']}")

    assert "escalated_tasks" in stats
    assert stats["escalated_tasks"] == 1
    print(f"✅ Escalated tasks: {stats['escalated_tasks']}")

    db_path.unlink()
    print("\n✅ All database stats tests passed")


def main():
    """Run all tests."""
    print("=" * 70)
    print("RETRY HANDLER TEST SUITE")
    print("=" * 70)

    test_failure_classification()
    test_retry_strategy_mapping()
    test_exponential_backoff()
    test_retry_decision_logic()
    test_retry_config_persistence()
    test_escalated_tasks_query()
    test_trace_event_logging()
    test_default_configs()
    test_database_stats()

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    main()
