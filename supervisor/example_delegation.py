#!/usr/bin/env python3
"""
Example usage of Supervisor Delegation.

Demonstrates:
- Creating work items
- Routing tasks to specialized agents
- Monitoring agent load
- Handling capacity constraints
"""

from supervisor.core import CortexSupervisor
from supervisor.delegator import AgentCapability, DelegationPolicy
from supervisor.models import WorkItem, WorkItemPriority


def example_basic_routing():
    """Basic example: Route tasks to agents."""
    print("=" * 60)
    print("Example 1: Basic Task Routing")
    print("=" * 60)

    supervisor = CortexSupervisor()

    # Create work items for different task types
    work_items = [
        WorkItem(
            id="sec-001",
            source="github_alert",
            task_type="security",
            description="Review authentication flow for SQL injection",
            priority=WorkItemPriority.CRITICAL,
        ),
        WorkItem(
            id="test-001",
            source="coverage_report",
            task_type="test",
            description="Add integration tests for payment API",
            priority=WorkItemPriority.HIGH,
        ),
        WorkItem(
            id="quality-001",
            source="code_review",
            task_type="pattern",
            description="Detect circular dependencies in module structure",
            priority=WorkItemPriority.MEDIUM,
        ),
    ]

    print("\nRouting tasks to agents...")
    for work_item in work_items:
        routed = supervisor.delegator.route_task(work_item)
        if routed:
            print(f"  ✓ {work_item.id} [{work_item.task_type}] → {routed.target.value}")
        else:
            print(f"  ✗ {work_item.id} [{work_item.task_type}] → No capacity (queued)")

    # Show delegation status
    print("\nAgent Status:")
    stats = supervisor.get_delegation_summary()
    for agent_name, load in stats["agent_loads"].items():
        status = "🟢 AVAILABLE" if load["available"] else "🔴 AT CAPACITY"
        print(f"  {agent_name:25} {load['current_tasks']}/{load['max_concurrent']} {status}")

    print(f"\nOverall Capacity: {stats['capacity_percentage']:.1f}% used")


def example_capacity_management():
    """Example: Handle capacity constraints."""
    print("\n" + "=" * 60)
    print("Example 2: Capacity Management")
    print("=" * 60)

    supervisor = CortexSupervisor()

    # Create multiple security tasks (security_analyst max_concurrent=2)
    print("\nCreating 4 security tasks (agent capacity = 2)...")
    for i in range(4):
        work_item = WorkItem(
            id=f"sec-{i:03d}",
            source="security_scan",
            task_type="security",
            description=f"Security analysis task {i}",
            priority=WorkItemPriority.HIGH,
        )

        routed = supervisor.delegator.route_task(work_item)
        if routed:
            print(f"  ✓ sec-{i:03d} routed successfully")
        else:
            print(f"  ✗ sec-{i:03d} WAITING (agent at capacity)")

    # Show current status
    load = supervisor.delegator.get_agent_status("security_analyst")
    print(f"\nSecurity Analyst: {load.current_tasks}/{load.max_concurrent} tasks")
    print(f"Available capacity: {load.available_capacity}")

    # Complete a task to free capacity
    print("\nCompleting one task to free capacity...")
    supervisor.delegator.complete_task("security_analyst")

    load = supervisor.delegator.get_agent_status("security_analyst")
    print(f"Security Analyst: {load.current_tasks}/{load.max_concurrent} tasks")
    print(f"Available capacity: {load.available_capacity}")


def example_custom_policy():
    """Example: Use custom delegation policy."""
    print("\n" + "=" * 60)
    print("Example 3: Custom Delegation Policy")
    print("=" * 60)

    # Create custom policy with only test and quality agents
    custom_policy = DelegationPolicy(
        allowed_delegations={
            "test_specialist": AgentCapability(
                name="test_specialist",
                task_types={"test", "qa", "validation", "coverage"},
                max_concurrent=5,
                estimated_tokens=8000,
            ),
            "quality_guru": AgentCapability(
                name="quality_guru",
                task_types={"pattern", "quality", "complexity", "review"},
                max_concurrent=3,
                estimated_tokens=10000,
            ),
        },
        require_approval={"quality"},  # Quality work needs approval
        max_batch_size=15,
    )

    supervisor = CortexSupervisor(delegation_policy=custom_policy)

    print("\nCustom policy has 2 agents:")
    stats = supervisor.get_delegation_summary()
    for agent_name in stats["agent_loads"].keys():
        print(f"  - {agent_name}")

    # Route tasks
    tasks = [
        ("test", "test_specialist"),
        ("quality", "quality_guru"),
        ("security", "SHELL (no capable agent)"),
    ]

    print("\nRouting tasks with custom policy:")
    for task_type, expected_route in tasks:
        work_item = WorkItem(
            id=f"task-{task_type}",
            source="test",
            task_type=task_type,
            description=f"Sample {task_type} task",
        )
        routed = supervisor.delegator.route_task(work_item)
        if routed:
            actual_route = "AI agent" if routed.target.value == "ai_batch" else "SHELL"
            print(f"  {task_type:15} → {actual_route}")


def example_load_balancing():
    """Example: Load balancing across agents."""
    print("\n" + "=" * 60)
    print("Example 4: Load Balancing")
    print("=" * 60)

    supervisor = CortexSupervisor()

    # Create 10 test tasks
    print("\nRouting 10 test tasks...")
    for i in range(10):
        work_item = WorkItem(
            id=f"test-{i:03d}",
            source="test_suite",
            task_type="test",
            description=f"Test task {i}",
        )
        routed = supervisor.delegator.route_task(work_item)
        if routed:
            print(f"  ✓ Task {i:2d} routed", end="")
        else:
            print(f"  ✗ Task {i:2d} WAITING", end="")

        # Show load percentage after every 3 tasks
        if (i + 1) % 3 == 0:
            load = supervisor.delegator.get_agent_status("test_engineer")
            print(f" | Load: {load.load_percentage*100:.0f}%")
        else:
            print()

    # Final statistics
    print("\nFinal Statistics:")
    stats = supervisor.get_delegation_summary()
    print(f"  Total capacity: {stats['total_capacity']} tasks")
    print(f"  Total used: {stats['total_used']} tasks")
    print(f"  Capacity percentage: {stats['capacity_percentage']:.1f}%")
    print(f"  Available agents: {stats['available_agents']}/{stats['total_agents']}")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "SUPERVISOR DELEGATION EXAMPLES" + " " * 17 + "║")
    print("╚" + "═" * 58 + "╝")

    try:
        example_basic_routing()
        example_capacity_management()
        example_custom_policy()
        example_load_balancing()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
