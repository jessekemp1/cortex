"""
Supervisor Delegation Logic - Intelligent task routing to specialized agents.

Routes tasks to capable agents based on:
- Task type matching to agent capabilities
- Agent capacity and current load
- Load balancing across available agents
- Delegation policy enforcement
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set

from .models import RoutedTask, TaskTarget, WorkItem


class AgentType(str, Enum):
    """Types of specialized agents available for delegation."""

    SECURITY_ANALYST = "security_analyst"
    CODE_QUALITY = "code_quality"
    TEST_ENGINEER = "test_engineer"
    REFACTORING_SPECIALIST = "refactoring_specialist"
    RESEARCH_AGENT = "research_agent"


@dataclass
class AgentCapability:
    """
    Defines what a specific agent type can do.

    Attributes:
        name: Agent type name (e.g., "security_analyst")
        task_types: Set of task types this agent can handle
        max_concurrent: Maximum concurrent tasks this agent can handle
        estimated_tokens: Typical token usage per task for this agent
    """

    name: str
    task_types: Set[str]
    max_concurrent: int = 3
    estimated_tokens: int = 8000  # Conservative estimate for most analysis tasks

    def can_handle(self, task_type: str) -> bool:
        """Check if this agent can handle the given task type."""
        return task_type in self.task_types


@dataclass
class AgentLoad:
    """
    Tracks current load for an agent.

    Attributes:
        agent_name: Name of the agent
        current_tasks: Number of currently assigned tasks
        max_concurrent: Maximum concurrent tasks allowed
        last_assigned: Timestamp of last task assignment
    """

    agent_name: str
    current_tasks: int = 0
    max_concurrent: int = 3
    last_assigned: Optional[datetime] = None

    @property
    def available_capacity(self) -> int:
        """Number of additional tasks this agent can accept."""
        return max(0, self.max_concurrent - self.current_tasks)

    @property
    def is_available(self) -> bool:
        """Check if agent has capacity for more tasks."""
        return self.current_tasks < self.max_concurrent

    @property
    def load_percentage(self) -> float:
        """Current load as percentage (0.0 to 1.0)."""
        if self.max_concurrent == 0:
            return 1.0
        return self.current_tasks / self.max_concurrent

    def assign_task(self) -> None:
        """Increment load when assigning a task."""
        self.current_tasks += 1
        self.last_assigned = datetime.now()

    def complete_task(self) -> None:
        """Decrement load when task completes."""
        self.current_tasks = max(0, self.current_tasks - 1)


@dataclass
class DelegationPolicy:
    """
    Defines allowed delegation paths for the supervisor.

    Prevents free-for-all delegation by explicitly defining which agents
    the supervisor can delegate to and what they can do.

    Attributes:
        allowed_delegations: Map of agent_name -> AgentCapability
        require_approval: Task types that require human approval before delegation
        max_batch_size: Maximum tasks to delegate in a single batch
    """

    allowed_delegations: Dict[str, AgentCapability] = field(default_factory=dict)
    require_approval: Set[str] = field(default_factory=set)
    max_batch_size: int = 10

    @classmethod
    def default_policy(cls) -> "DelegationPolicy":
        """
        Create default delegation policy with standard agent capabilities.

        Default agents:
        - security_analyst: security, vulnerability, audit tasks
        - code_quality: pattern, quality, complexity analysis
        - test_engineer: test, coverage, validation work
        - refactoring_specialist: refactor, cleanup tasks
        - research_agent: research, benchmarking, investigation
        """
        capabilities = {
            AgentType.SECURITY_ANALYST.value: AgentCapability(
                name=AgentType.SECURITY_ANALYST.value,
                task_types={"security", "vulnerability", "audit", "auth", "encryption"},
                max_concurrent=2,  # Security analysis is expensive
                estimated_tokens=12000,
            ),
            AgentType.CODE_QUALITY.value: AgentCapability(
                name=AgentType.CODE_QUALITY.value,
                task_types={"pattern", "quality", "complexity", "analysis", "review"},
                max_concurrent=4,  # Code review is lighter
                estimated_tokens=8000,
            ),
            AgentType.TEST_ENGINEER.value: AgentCapability(
                name=AgentType.TEST_ENGINEER.value,
                task_types={"test", "coverage", "validation", "qa", "integration"},
                max_concurrent=3,
                estimated_tokens=10000,
            ),
            AgentType.REFACTORING_SPECIALIST.value: AgentCapability(
                name=AgentType.REFACTORING_SPECIALIST.value,
                task_types={"refactor", "cleanup", "optimization", "restructure"},
                max_concurrent=2,  # Refactoring needs focus
                estimated_tokens=15000,
            ),
            AgentType.RESEARCH_AGENT.value: AgentCapability(
                name=AgentType.RESEARCH_AGENT.value,
                task_types={"research", "benchmarking", "investigation", "discovery"},
                max_concurrent=3,
                estimated_tokens=10000,
            ),
        }

        # Security and refactoring tasks should be reviewed by human
        require_approval = {"security", "vulnerability", "refactor"}

        return cls(
            allowed_delegations=capabilities,
            require_approval=require_approval,
            max_batch_size=10,
        )

    def can_delegate_to(self, agent_name: str, task_type: str) -> bool:
        """Check if delegation is allowed for this agent/task combination."""
        capability = self.allowed_delegations.get(agent_name)
        if capability is None:
            return False
        return capability.can_handle(task_type)

    def needs_approval(self, task_type: str) -> bool:
        """Check if this task type requires human approval."""
        return task_type in self.require_approval

    def get_capable_agents(self, task_type: str) -> List[AgentCapability]:
        """Get all agents capable of handling this task type."""
        return [
            capability
            for capability in self.allowed_delegations.values()
            if capability.can_handle(task_type)
        ]


class SupervisorDelegator:
    """
    Routes tasks to specialized agents based on capability and load.

    The delegator implements intelligent routing:
    1. Find agents capable of handling the task type
    2. Check agent capacity (max_concurrent limit)
    3. Select agent with lowest current load
    4. Track load (increment on assign, decrement on complete)

    This prevents overloading any single agent and distributes work efficiently.
    """

    def __init__(self, policy: Optional[DelegationPolicy] = None):
        """
        Initialize the delegator.

        Args:
            policy: Delegation policy (uses default if None)
        """
        self.policy = policy or DelegationPolicy.default_policy()

        # Track agent load (agent_name -> AgentLoad)
        self._agent_loads: Dict[str, AgentLoad] = {}

        # Initialize load tracking for all agents in policy
        for agent_name, capability in self.policy.allowed_delegations.items():
            self._agent_loads[agent_name] = AgentLoad(
                agent_name=agent_name,
                max_concurrent=capability.max_concurrent,
            )

    def route_task(self, work_item: WorkItem) -> Optional[RoutedTask]:
        """
        Route a work item to the best available agent.

        Routing logic:
        1. Find agents capable of handling task_type
        2. Filter to agents with available capacity
        3. Select agent with lowest load percentage
        4. If no agents available, return None (task queued for later)

        Args:
            work_item: Work item to route

        Returns:
            RoutedTask with assigned agent, or None if no capacity
        """
        task_type = work_item.task_type

        # Get capable agents
        capable_agents = self.policy.get_capable_agents(task_type)
        if not capable_agents:
            # No agents can handle this task type - route to shell by default
            return RoutedTask(
                work_item=work_item,
                target=TaskTarget.SHELL,
                priority=work_item.priority.value,
                estimated_tokens=work_item.estimated_tokens,
            )

        # Filter to available agents
        available_agents = [
            agent for agent in capable_agents if self._agent_loads[agent.name].is_available
        ]

        if not available_agents:
            # All capable agents at capacity - task must wait
            return None

        # Select agent with lowest load
        selected_agent = min(
            available_agents,
            key=lambda agent: self._agent_loads[agent.name].load_percentage,
        )

        # Track assignment
        self._agent_loads[selected_agent.name].assign_task()

        # Create routed task targeting AI batch (agents are AI workers)
        return RoutedTask(
            work_item=work_item,
            target=TaskTarget.AI_BATCH,
            priority=work_item.priority.value,
            estimated_tokens=selected_agent.estimated_tokens,
        )

    def complete_task(self, agent_name: str) -> None:
        """
        Mark a task as completed, freeing up agent capacity.

        Args:
            agent_name: Name of agent that completed the task
        """
        if agent_name in self._agent_loads:
            self._agent_loads[agent_name].complete_task()

    def get_agent_status(self, agent_name: str) -> Optional[AgentLoad]:
        """
        Get current load status for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentLoad with current status, or None if agent not found
        """
        return self._agent_loads.get(agent_name)

    def get_all_agent_status(self) -> Dict[str, AgentLoad]:
        """Get load status for all agents."""
        return self._agent_loads.copy()

    def reset_agent_load(self, agent_name: str) -> None:
        """
        Reset agent load to zero (useful for recovery/cleanup).

        Args:
            agent_name: Name of agent to reset
        """
        if agent_name in self._agent_loads:
            self._agent_loads[agent_name].current_tasks = 0

    def get_routing_stats(self) -> Dict[str, any]:
        """
        Get delegation statistics.

        Returns:
            Dictionary with routing statistics
        """
        total_capacity = sum(load.max_concurrent for load in self._agent_loads.values())
        total_used = sum(load.current_tasks for load in self._agent_loads.values())

        available_agents = sum(1 for load in self._agent_loads.values() if load.is_available)
        busy_agents = len(self._agent_loads) - available_agents

        return {
            "total_agents": len(self._agent_loads),
            "available_agents": available_agents,
            "busy_agents": busy_agents,
            "total_capacity": total_capacity,
            "total_used": total_used,
            "capacity_percentage": (total_used / total_capacity * 100) if total_capacity > 0 else 0,
            "agent_loads": {
                name: {
                    "current_tasks": load.current_tasks,
                    "max_concurrent": load.max_concurrent,
                    "load_percentage": load.load_percentage * 100,
                    "available": load.is_available,
                }
                for name, load in self._agent_loads.items()
            },
        }
