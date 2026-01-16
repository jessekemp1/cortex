"""Integration adapter for Cortex intelligence with Cortex runtime.

Provides the bridge between Cortex's recommendation engine and the
runtime executor for scheduled agent execution.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

# Try to import runtime components
try:
    from cortex.runtime.agents.builtin.task import TaskAgent
    from cortex.runtime.config import get_config
    from cortex.runtime.executor import RuntimeExecutor

    RUNTIME_AVAILABLE = True
except ImportError:
    RUNTIME_AVAILABLE = False
    RuntimeExecutor = None
    TaskAgent = None

logger = structlog.get_logger()

# Flag indicating if runtime is available
LOCAL_ORCHESTRATOR_AVAILABLE = RUNTIME_AVAILABLE


class CortexLocalOrchestratorIntegration:
    """Integration adapter for Cortex -> Runtime executor.

    Provides methods to schedule recommendations as agents and
    query the runtime for scheduled actions.
    """

    def __init__(self, root_dir: Optional[Path] = None):
        """Initialize the integration.

        Args:
            root_dir: Root directory for workspace
        """
        self.root_dir = root_dir or Path("/Users/jesse.kemp/Dev")
        self._executor: Optional[RuntimeExecutor] = None
        self._adapter: Optional["RecommendationToAgentAdapter"] = None

    @property
    def adapter(self) -> Optional["RecommendationToAgentAdapter"]:
        """Get or create the recommendation adapter."""
        if self._adapter is None:
            self._adapter = RecommendationToAgentAdapter(self)
        return self._adapter

    @property
    def executor(self) -> Optional[RuntimeExecutor]:
        """Get or create the runtime executor."""
        if self._executor is None and RUNTIME_AVAILABLE:
            try:
                config = get_config()
                self._executor = RuntimeExecutor(config)
            except Exception as e:
                logger.warning("runtime_executor_init_failed", error=str(e))
        return self._executor

    def is_available(self) -> bool:
        """Check if runtime is available.

        Returns:
            True if runtime can be used
        """
        return RUNTIME_AVAILABLE

    def schedule_recommendation(self, recommendation: Any, schedule: str = "0 8 * * *") -> bool:
        """Schedule a recommendation to be executed by the runtime.

        Args:
            recommendation: Cortex recommendation to schedule
            schedule: Cron schedule string

        Returns:
            True if successfully scheduled
        """
        if not self.is_available() or not self.executor:
            return False

        try:
            # Extract recommendation details
            rec_id = getattr(recommendation, "id", "rec_unknown")
            title = getattr(recommendation, "title", "Unknown")
            description = getattr(recommendation, "description", "")

            # Create a task agent for the recommendation
            def execute_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
                """Execute the scheduled recommendation."""
                return {
                    "recommendation_id": rec_id,
                    "title": title,
                    "status": "executed",
                    "context": context,
                }

            agent = TaskAgent(
                agent_id=f"cortex_rec_{rec_id}",
                name=f"Cortex: {title}",
                description=description,
                task_func=execute_recommendation,
            )

            self.executor.register_agent(agent, schedule=schedule)
            logger.info(
                "recommendation_scheduled",
                rec_id=rec_id,
                schedule=schedule,
            )
            return True

        except Exception as e:
            logger.error("schedule_recommendation_failed", error=str(e))
            return False

    def list_scheduled_actions(self) -> List[Dict[str, Any]]:
        """List all scheduled actions in the runtime.

        Returns:
            List of scheduled action info dicts
        """
        if not self.is_available() or not self.executor:
            return []

        try:
            # Get all agents and filter for Cortex ones
            agents = self.executor.list_agents()
            return [a for a in agents if a.get("agent_id", "").startswith("cortex_")]
        except Exception as e:
            logger.error("list_scheduled_actions_failed", error=str(e))
            return []

    def trigger_action(
        self, agent_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Manually trigger a scheduled action.

        Args:
            agent_id: ID of the agent to trigger
            context: Optional execution context

        Returns:
            Execution result or None if failed
        """
        if not self.is_available() or not self.executor:
            return None

        try:
            result = self.executor.trigger_agent(agent_id, context)
            return result.model_dump()
        except Exception as e:
            logger.error("trigger_action_failed", agent_id=agent_id, error=str(e))
            return None


class RecommendationToAgentAdapter:
    """Adapter to convert Cortex recommendations into runtime agents."""

    def __init__(self, integration: Optional[CortexLocalOrchestratorIntegration] = None):
        """Initialize the adapter.

        Args:
            integration: Optional integration instance
        """
        self.integration = integration or CortexLocalOrchestratorIntegration()

    def to_agent(self, recommendation: Any) -> Optional[Dict[str, Any]]:
        """Convert a Cortex recommendation to an agent configuration.

        Args:
            recommendation: Cortex recommendation

        Returns:
            Agent configuration dict or None
        """
        if not self.integration.is_available():
            return None

        rec_id = getattr(recommendation, "id", "rec_unknown")
        title = getattr(recommendation, "title", "Unknown")
        description = getattr(recommendation, "description", "")

        return {
            "agent_id": f"cortex_rec_{rec_id}",
            "name": f"Cortex: {title}",
            "description": description,
            "type": "task",
        }

    def to_schedule(self, recommendation: Any) -> str:
        """Generate a cron schedule string for a recommendation.

        Args:
            recommendation: Cortex recommendation

        Returns:
            Cron schedule string
        """
        # Default to daily at 8 AM
        # Could be enhanced based on priority/type
        priority = getattr(recommendation, "priority", "medium")
        if priority in ("high", "critical"):
            return "0 7 * * *"  # 7 AM daily for high priority
        return "0 8 * * *"  # 8 AM daily for normal priority

    def register_recommendation(self, recommendation: Any, schedule: str = "0 8 * * *") -> bool:
        """Register a recommendation as a scheduled agent.

        Args:
            recommendation: Cortex recommendation
            schedule: Cron schedule string

        Returns:
            True if successfully registered
        """
        return self.integration.schedule_recommendation(recommendation, schedule)
