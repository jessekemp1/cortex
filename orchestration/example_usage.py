#!/usr/bin/env python3
"""
Example usage patterns for Cortex orchestration system.

Demonstrates:
1. Creating tasks with different priorities
2. Dependency management
3. Batch vs realtime routing
4. Integration with existing batch system
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.scheduler import TaskScheduler
from orchestration.task import Task, TaskPriority
from orchestration.task_queue import TaskQueue


def example_basic_usage():
    """Basic task creation and scheduling"""
    print("\n" + "=" * 60)
    print("Example 1: Basic Task Creation and Scheduling")
    print("=" * 60 + "\n")

    scheduler = TaskScheduler()

    # Critical task - immediate realtime
    critical = Task(
        id="critical-1",
        title="Fix production outage",
        description="Database connection pool exhausted, users can't login",
        priority=TaskPriority.A,
    )

    decision = scheduler.enqueue_and_schedule(critical)
    print(f"✓ {critical.title}")
    print(f"  Priority: {critical.priority.value}")
    print(f"  Routed to: {decision.execution_mode}")
    print(f"  Reason: {decision.reason}\n")

    # Important with tight deadline - realtime
    urgent = Task(
        id="urgent-1",
        title="Prepare demo environment",
        description="Client meeting in 2 hours, need working demo",
        priority=TaskPriority.B,
        deadline=datetime.now() + timedelta(hours=2),
    )

    decision = scheduler.enqueue_and_schedule(urgent)
    print(f"✓ {urgent.title}")
    print(f"  Priority: {urgent.priority.value}")
    print(f"  Deadline: {urgent.hours_until_deadline:.1f}h")
    print(f"  Routed to: {decision.execution_mode}")
    print(f"  Reason: {decision.reason}\n")

    # Important with relaxed deadline - batch
    batch_eligible = Task(
        id="batch-1",
        title="Security audit",
        description="Comprehensive security scan of codebase",
        priority=TaskPriority.B,
        deadline=datetime.now() + timedelta(hours=24),
    )

    decision = scheduler.enqueue_and_schedule(batch_eligible)
    print(f"✓ {batch_eligible.title}")
    print(f"  Priority: {batch_eligible.priority.value}")
    print(f"  Deadline: {batch_eligible.hours_until_deadline:.1f}h")
    print(f"  Routed to: {decision.execution_mode}")
    print(f"  Reason: {decision.reason}\n")

    # Background task - always batch
    background = Task(
        id="background-1",
        title="Update documentation",
        description="Generate API docs and update README files",
        priority=TaskPriority.C,
    )

    decision = scheduler.enqueue_and_schedule(background)
    print(f"✓ {background.title}")
    print(f"  Priority: {background.priority.value}")
    print(f"  Routed to: {decision.execution_mode}")
    print(f"  Reason: {decision.reason}\n")

    # Show stats
    stats = scheduler.get_scheduling_stats()
    savings = scheduler.estimate_batch_cost_savings()

    print("📊 Queue Statistics:")
    print(f"  Total tasks: {stats['total_pending']}")
    print(f"  Realtime: {stats['realtime']}")
    print(f"  Batch: {stats['batch']}")
    print(f"  Estimated savings: ${savings['savings_usd']:.2f} (50%)\n")


def example_dependency_management():
    """Tasks with dependencies"""
    print("\n" + "=" * 60)
    print("Example 2: Dependency Management")
    print("=" * 60 + "\n")

    queue = TaskQueue()

    # Create a chain: setup -> test -> deploy
    setup = Task(
        id="setup-env",
        title="Setup test environment",
        description="Create test database, load fixtures, configure services",
        priority=TaskPriority.B,
    )

    test = Task(
        id="run-tests",
        title="Run integration tests",
        description="Execute full test suite against test environment",
        priority=TaskPriority.B,
        blocked_by=["setup-env"],
    )

    deploy = Task(
        id="deploy-prod",
        title="Deploy to production",
        description="Deploy verified build to production servers",
        priority=TaskPriority.A,
        blocked_by=["run-tests"],
    )

    # Set up dependency relationships
    setup.blocks = ["run-tests"]
    test.blocks = ["deploy-prod"]

    # Enqueue all
    queue.enqueue(setup)
    queue.enqueue(test)
    queue.enqueue(deploy)

    print("Task chain created: setup -> test -> deploy\n")

    # Only setup is ready
    ready = queue.get_ready_tasks()
    print(f"Ready to execute: {len(ready)} task(s)")
    for task in ready:
        print(f"  - {task.title} ({task.id})")

    blocked = queue.get_blocked_tasks()
    print(f"\nBlocked: {len(blocked)} task(s)")
    for task in blocked:
        print(f"  - {task.title} (waiting on: {', '.join(task.blocked_by)})")

    print("\n➡️  Simulating task completion...\n")

    # Complete setup
    queue.complete_task("setup-env", result="Test environment ready")
    print("✓ Completed: Setup test environment")

    # Now test is ready
    ready = queue.get_ready_tasks()
    print(f"\nReady to execute: {len(ready)} task(s)")
    for task in ready:
        print(f"  - {task.title} ({task.id})")

    # Complete test
    queue.complete_task("run-tests", result="All tests passed")
    print("\n✓ Completed: Run integration tests")

    # Now deploy is ready
    ready = queue.get_ready_tasks()
    print(f"\nReady to execute: {len(ready)} task(s)")
    for task in ready:
        print(f"  - {task.title} ({task.id})")

    print()


def example_cost_optimization():
    """Demonstrate batch routing for cost savings"""
    print("\n" + "=" * 60)
    print("Example 3: Cost Optimization with Batch Routing")
    print("=" * 60 + "\n")

    scheduler = TaskScheduler()

    # Add several background tasks
    tasks = [
        Task(
            id=f"analysis-{i}",
            title=f"Code quality analysis {i}",
            description="x" * 10000,  # Large task ~2500 tokens
            priority=TaskPriority.C,
        )
        for i in range(5)
    ]

    print("Adding 5 large background tasks...\n")

    for task in tasks:
        decision = scheduler.enqueue_and_schedule(task)
        print(
            f"✓ {task.title}: {task.total_estimated_tokens:,} tokens -> {decision.execution_mode}"
        )

    savings = scheduler.estimate_batch_cost_savings()

    print("\n💰 Cost Analysis:")
    print(f"  Batch tasks: {savings['batch_tasks']}")
    print(f"  Total tokens: {savings['total_tokens']:,}")
    print(f"  Realtime cost: ${savings['realtime_cost_usd']:.2f}")
    print(f"  Batch cost: ${savings['batch_cost_usd']:.2f}")
    print(f"  Savings: ${savings['savings_usd']:.2f} (50% discount)")
    print("\n📊 By routing these tasks to batch API, you save 50% on API costs!")
    print()


def example_rebalancing():
    """Rebalancing as deadlines approach"""
    print("\n" + "=" * 60)
    print("Example 4: Queue Rebalancing")
    print("=" * 60 + "\n")

    scheduler = TaskScheduler()

    # Add B task with 6-hour deadline (batch-eligible)
    task = Task(
        id="rebalance-1",
        title="Database migration",
        description="Migrate data to new schema",
        priority=TaskPriority.B,
        deadline=datetime.now() + timedelta(hours=6),
    )

    decision = scheduler.enqueue_and_schedule(task)
    print("Initial routing:")
    print(f"  Task: {task.title}")
    print(f"  Deadline: {task.hours_until_deadline:.1f}h")
    print(f"  Mode: {decision.execution_mode}")
    print(f"  Reason: {decision.reason}\n")

    # Simulate time passing - deadline now 3 hours away
    print("⏰ Simulating time passing... deadline now 3 hours away\n")
    task.deadline = datetime.now() + timedelta(hours=3)

    # Rebalance queue
    stats = scheduler.rebalance_queue()

    print("Rebalancing results:")
    print(f"  Total tasks: {stats['total_pending']}")
    print(f"  Promoted to realtime: {stats['promoted_to_realtime']}")
    print(f"  Demoted to batch: {stats['demoted_to_batch']}")
    print(f"  Unchanged: {stats['unchanged']}\n")

    # Check new routing
    updated_task = scheduler.queue.get("rebalance-1")
    print("Updated routing:")
    print(f"  Task: {updated_task.title}")
    print(f"  Deadline: {updated_task.hours_until_deadline:.1f}h")
    print(f"  Mode: {updated_task.execution_mode}")
    print("  Reason: Deadline too tight for batch (< 4h threshold)\n")


def example_integration_with_batch_api():
    """Integration with existing batch system"""
    print("\n" + "=" * 60)
    print("Example 5: Integration with Batch API System")
    print("=" * 60 + "\n")

    scheduler = TaskScheduler()

    # Add batch-eligible tasks
    for i in range(3):
        task = Task(
            id=f"batch-job-{i}",
            title=f"Pattern analysis {i}",
            description=f"Analyze code patterns in module {i}",
            priority=TaskPriority.C,
            prompt=f"Analyze all Python files in module_{i}/ for common patterns and anti-patterns",
            source="pattern",
            project="VortexV2",
        )
        scheduler.enqueue_and_schedule(task)

    # Get tasks for batch submission
    batch_tasks = scheduler.get_next_batch_tasks(limit=10)

    print(f"Found {len(batch_tasks)} tasks ready for batch submission:\n")

    for task in batch_tasks:
        print(f"Task: {task.title}")
        print(f"  ID: {task.id}")
        print(f"  Project: {task.project}")
        print(f"  Tokens: {task.total_estimated_tokens:,}")
        print(f"  Prompt: {task.prompt[:60]}...")
        print()

    print("These tasks can be submitted to:")
    print("  1. Anthropic Batch API (via batch/batch_scheduler.py)")
    print("  2. Cortex batch orchestrator (via batch/orchestrator.py)")
    print()


def main():
    """Run all examples"""
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║     CORTEX ORCHESTRATION SYSTEM - EXAMPLES          ║")
    print("╚══════════════════════════════════════════════════════╝")

    # Clear queue before examples
    queue = TaskQueue()
    queue.clear()

    # Run examples
    example_basic_usage()
    queue.clear()

    example_dependency_management()
    queue.clear()

    example_cost_optimization()
    queue.clear()

    example_rebalancing()
    queue.clear()

    example_integration_with_batch_api()
    queue.clear()

    print("\n✓ Examples complete!")
    print("\nNext steps:")
    print("  1. Try the CLI: python orchestration/cli.py --help")
    print("  2. Run tests: pytest orchestration/test_queue_system.py -v")
    print("  3. Build supervisor/worker agents on top of this infrastructure")
    print()


if __name__ == "__main__":
    main()
