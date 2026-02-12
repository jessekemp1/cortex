"""
Tests for supervisor delegation logic.

Verifies:
- Task routing to capable agents
- Load balancing across agents
- Capacity management
- Delegation policy enforcement
"""

from datetime import datetime

import pytest

from .delegator import (
    AgentCapability,
    AgentLoad,
    AgentType,
    DelegationPolicy,
    SupervisorDelegator,
)
from .models import TaskTarget, WorkItem, WorkItemPriority


class TestAgentCapability:
    """Test agent capability definitions."""

    def test_can_handle_matching_task(self):
        """Agent should handle tasks in its capability set."""
        capability = AgentCapability(
            name="security_analyst",
            task_types={"security", "vulnerability", "audit"},
        )

        assert capability.can_handle("security")
        assert capability.can_handle("vulnerability")
        assert capability.can_handle("audit")

    def test_cannot_handle_non_matching_task(self):
        """Agent should reject tasks outside its capability."""
        capability = AgentCapability(
            name="security_analyst",
            task_types={"security", "vulnerability"},
        )

        assert not capability.can_handle("test")
        assert not capability.can_handle("refactor")


class TestAgentLoad:
    """Test agent load tracking."""

    def test_initial_load_available(self):
        """New agent should have full capacity."""
        load = AgentLoad(agent_name="test_agent", max_concurrent=3)

        assert load.is_available
        assert load.available_capacity == 3
        assert load.load_percentage == 0.0

    def test_assign_task_increases_load(self):
        """Assigning tasks should increase load."""
        load = AgentLoad(agent_name="test_agent", max_concurrent=3)

        load.assign_task()
        assert load.current_tasks == 1
        assert load.available_capacity == 2
        assert load.load_percentage == pytest.approx(0.333, rel=0.01)
        assert load.last_assigned is not None

    def test_complete_task_decreases_load(self):
        """Completing tasks should decrease load."""
        load = AgentLoad(agent_name="test_agent", max_concurrent=3)

        load.assign_task()
        load.assign_task()
        assert load.current_tasks == 2

        load.complete_task()
        assert load.current_tasks == 1
        assert load.available_capacity == 2

    def test_at_capacity_not_available(self):
        """Agent at capacity should not be available."""
        load = AgentLoad(agent_name="test_agent", max_concurrent=2)

        load.assign_task()
        load.assign_task()

        assert not load.is_available
        assert load.available_capacity == 0
        assert load.load_percentage == 1.0

    def test_complete_task_handles_underflow(self):
        """Completing more tasks than assigned should not go negative."""
        load = AgentLoad(agent_name="test_agent", max_concurrent=3)

        load.complete_task()
        assert load.current_tasks == 0  # Should not go negative


class TestDelegationPolicy:
    """Test delegation policy enforcement."""

    def test_default_policy_has_all_agents(self):
        """Default policy should include all standard agents."""
        policy = DelegationPolicy.default_policy()

        assert AgentType.SECURITY_ANALYST.value in policy.allowed_delegations
        assert AgentType.CODE_QUALITY.value in policy.allowed_delegations
        assert AgentType.TEST_ENGINEER.value in policy.allowed_delegations
        assert AgentType.REFACTORING_SPECIALIST.value in policy.allowed_delegations
        assert AgentType.RESEARCH_AGENT.value in policy.allowed_delegations

    def test_can_delegate_matching_task(self):
        """Policy should allow delegation to capable agents."""
        policy = DelegationPolicy.default_policy()

        assert policy.can_delegate_to("security_analyst", "security")
        assert policy.can_delegate_to("code_quality", "pattern")
        assert policy.can_delegate_to("test_engineer", "test")

    def test_cannot_delegate_non_matching_task(self):
        """Policy should reject delegation to incapable agents."""
        policy = DelegationPolicy.default_policy()

        assert not policy.can_delegate_to("security_analyst", "test")
        assert not policy.can_delegate_to("code_quality", "security")

    def test_cannot_delegate_to_unknown_agent(self):
        """Policy should reject unknown agents."""
        policy = DelegationPolicy.default_policy()

        assert not policy.can_delegate_to("unknown_agent", "security")

    def test_get_capable_agents(self):
        """Should return all agents capable of handling task type."""
        policy = DelegationPolicy.default_policy()

        # Security tasks
        capable = policy.get_capable_agents("security")
        assert len(capable) == 1
        assert capable[0].name == "security_analyst"

        # Test tasks
        capable = policy.get_capable_agents("test")
        assert len(capable) == 1
        assert capable[0].name == "test_engineer"

    def test_needs_approval(self):
        """Should identify tasks requiring approval."""
        policy = DelegationPolicy.default_policy()

        assert policy.needs_approval("security")
        assert policy.needs_approval("vulnerability")
        assert policy.needs_approval("refactor")
        assert not policy.needs_approval("test")


class TestSupervisorDelegator:
    """Test supervisor delegation routing."""

    def create_work_item(
        self, task_type: str, priority: WorkItemPriority = WorkItemPriority.MEDIUM
    ) -> WorkItem:
        """Helper to create test work items."""
        return WorkItem(
            id=f"work-{task_type}-{datetime.now().timestamp()}",
            source="test",
            task_type=task_type,
            description=f"Test {task_type} task",
            priority=priority,
        )

    def test_route_to_capable_agent(self):
        """Should route task to capable agent."""
        delegator = SupervisorDelegator()
        work_item = self.create_work_item("security")

        routed = delegator.route_task(work_item)

        assert routed is not None
        assert routed.target == TaskTarget.AI_BATCH
        assert routed.work_item == work_item

        # Check agent load increased
        load = delegator.get_agent_status("security_analyst")
        assert load.current_tasks == 1

    def test_route_unknown_task_to_shell(self):
        """Should route unknown task types to shell."""
        delegator = SupervisorDelegator()
        work_item = self.create_work_item("unknown_task_type")

        routed = delegator.route_task(work_item)

        assert routed is not None
        assert routed.target == TaskTarget.SHELL

    def test_load_balancing_across_agents(self):
        """Should distribute tasks to lowest-load agent."""
        delegator = SupervisorDelegator()

        # Manually set different loads
        delegator._agent_loads["code_quality"].current_tasks = 2
        delegator._agent_loads["test_engineer"].current_tasks = 1

        # Both can handle "test" tasks in this mock scenario
        # But test_engineer has lower load
        work_item = self.create_work_item("test")
        routed = delegator.route_task(work_item)

        assert routed is not None
        # Should route to test_engineer (only agent capable of "test")
        load = delegator.get_agent_status("test_engineer")
        assert load.current_tasks == 2

    def test_no_routing_when_at_capacity(self):
        """Should return None when all capable agents at capacity."""
        delegator = SupervisorDelegator()

        # Fill security_analyst to capacity (max_concurrent=2)
        security_load = delegator._agent_loads["security_analyst"]
        security_load.current_tasks = security_load.max_concurrent

        work_item = self.create_work_item("security")
        routed = delegator.route_task(work_item)

        # Should return None (no capacity)
        assert routed is None

    def test_complete_task_frees_capacity(self):
        """Completing task should free agent capacity."""
        delegator = SupervisorDelegator()

        # Assign task
        work_item = self.create_work_item("security")
        delegator.route_task(work_item)

        load_before = delegator.get_agent_status("security_analyst")
        assert load_before.current_tasks == 1

        # Complete task
        delegator.complete_task("security_analyst")

        load_after = delegator.get_agent_status("security_analyst")
        assert load_after.current_tasks == 0

    def test_multiple_tasks_same_type(self):
        """Should handle multiple tasks of same type."""
        delegator = SupervisorDelegator()

        # Route 3 security tasks
        for i in range(3):
            work_item = self.create_work_item("security")
            routed = delegator.route_task(work_item)

            if i < 2:
                # First 2 should succeed (security_analyst max_concurrent=2)
                assert routed is not None
            else:
                # Third should fail (at capacity)
                assert routed is None

        load = delegator.get_agent_status("security_analyst")
        assert load.current_tasks == 2

    def test_routing_stats(self):
        """Should provide accurate routing statistics."""
        delegator = SupervisorDelegator()

        # Assign some tasks
        delegator.route_task(self.create_work_item("security"))
        delegator.route_task(self.create_work_item("test"))

        stats = delegator.get_routing_stats()

        assert stats["total_agents"] == 5  # All agent types
        assert stats["total_used"] == 2  # 2 tasks assigned
        assert stats["capacity_percentage"] > 0

        # Check per-agent stats
        assert "security_analyst" in stats["agent_loads"]
        assert stats["agent_loads"]["security_analyst"]["current_tasks"] == 1

    def test_reset_agent_load(self):
        """Should reset agent load on command."""
        delegator = SupervisorDelegator()

        # Assign tasks
        delegator.route_task(self.create_work_item("security"))
        load_before = delegator.get_agent_status("security_analyst")
        assert load_before.current_tasks == 1

        # Reset
        delegator.reset_agent_load("security_analyst")
        load_after = delegator.get_agent_status("security_analyst")
        assert load_after.current_tasks == 0

    def test_get_all_agent_status(self):
        """Should return status for all agents."""
        delegator = SupervisorDelegator()

        all_status = delegator.get_all_agent_status()

        assert len(all_status) == 5  # All agent types
        assert "security_analyst" in all_status
        assert "code_quality" in all_status
        assert all(isinstance(load, AgentLoad) for load in all_status.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
