"""
Integration tests for supervisor delegation.

Verifies the CortexSupervisor correctly integrates with SupervisorDelegator.
"""

import pytest

from .core import CortexSupervisor
from .delegator import AgentCapability, DelegationPolicy
from .models import WorkItem, WorkItemPriority


class TestSupervisorDelegatorIntegration:
    """Test integration between CortexSupervisor and SupervisorDelegator."""

    def test_supervisor_initializes_with_delegator(self):
        """Supervisor should initialize with delegator component."""
        supervisor = CortexSupervisor()

        assert supervisor.delegator is not None
        assert supervisor.delegator.policy is not None

    def test_supervisor_uses_custom_delegation_policy(self):
        """Supervisor should accept custom delegation policy."""
        # Create custom policy with limited agents
        custom_policy = DelegationPolicy(
            allowed_delegations={
                "test_only": AgentCapability(
                    name="test_only",
                    task_types={"test"},
                    max_concurrent=1,
                )
            }
        )

        supervisor = CortexSupervisor(delegation_policy=custom_policy)

        # Check policy was applied
        assert len(supervisor.delegator.policy.allowed_delegations) == 1
        assert "test_only" in supervisor.delegator.policy.allowed_delegations

    def test_get_delegation_summary(self):
        """Supervisor should provide delegation summary."""
        supervisor = CortexSupervisor()

        summary = supervisor.get_delegation_summary()

        # Check summary structure
        assert "total_agents" in summary
        assert "available_agents" in summary
        assert "total_capacity" in summary
        assert "agent_loads" in summary

        # Default policy has 5 agents
        assert summary["total_agents"] == 5

    def test_delegation_after_routing_tasks(self):
        """Delegation summary should reflect routed tasks."""
        supervisor = CortexSupervisor()

        # Create and route some work items
        work_items = [
            WorkItem(
                id="work-1",
                source="test",
                task_type="security",
                description="Security audit",
            ),
            WorkItem(
                id="work-2",
                source="test",
                task_type="test",
                description="Test coverage",
            ),
        ]

        # Route tasks through delegator
        for work_item in work_items:
            supervisor.delegator.route_task(work_item)

        # Check delegation summary
        summary = supervisor.get_delegation_summary()

        assert summary["total_used"] == 2
        assert summary["capacity_percentage"] > 0

        # Check specific agents
        security_load = summary["agent_loads"]["security_analyst"]
        assert security_load["current_tasks"] == 1

        test_load = summary["agent_loads"]["test_engineer"]
        assert test_load["current_tasks"] == 1

    def test_complete_task_updates_delegation(self):
        """Completing tasks should update delegation state."""
        supervisor = CortexSupervisor()

        # Route a task
        work_item = WorkItem(
            id="work-1",
            source="test",
            task_type="security",
            description="Security audit",
        )
        supervisor.delegator.route_task(work_item)

        # Check agent loaded
        summary_before = supervisor.get_delegation_summary()
        assert summary_before["agent_loads"]["security_analyst"]["current_tasks"] == 1

        # Complete the task
        supervisor.delegator.complete_task("security_analyst")

        # Check agent freed
        summary_after = supervisor.get_delegation_summary()
        assert summary_after["agent_loads"]["security_analyst"]["current_tasks"] == 0

    def test_multiple_supervisors_independent_delegation(self):
        """Multiple supervisors should have independent delegation state."""
        supervisor1 = CortexSupervisor()
        supervisor2 = CortexSupervisor()

        # Route task in supervisor1
        work_item = WorkItem(
            id="work-1",
            source="test",
            task_type="security",
            description="Security audit",
        )
        supervisor1.delegator.route_task(work_item)

        # Check supervisor1 has load
        summary1 = supervisor1.get_delegation_summary()
        assert summary1["agent_loads"]["security_analyst"]["current_tasks"] == 1

        # Check supervisor2 has no load
        summary2 = supervisor2.get_delegation_summary()
        assert summary2["agent_loads"]["security_analyst"]["current_tasks"] == 0

    def test_delegation_with_priority_work_items(self):
        """Delegation should handle different priority work items."""
        supervisor = CortexSupervisor()

        work_items = [
            WorkItem(
                id="work-critical",
                source="test",
                task_type="security",
                description="Critical security issue",
                priority=WorkItemPriority.CRITICAL,
            ),
            WorkItem(
                id="work-low",
                source="test",
                task_type="test",
                description="Low priority test",
                priority=WorkItemPriority.LOW,
            ),
        ]

        # Route both tasks
        for work_item in work_items:
            routed = supervisor.delegator.route_task(work_item)
            assert routed is not None

        # Check both were routed
        summary = supervisor.get_delegation_summary()
        assert summary["total_used"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
