"""Morning Briefing Agent - Cortex-Powered Daily Status Report.

Provides a full morning briefing integrating:
- Cortex recommendation engine (strategic next actions)
- Cortex learning system (confidence calibration from outcomes)
- Golden Spec Method alignment
- Local-orchestrator execution history (feedback loop)
"""

from typing import Any, Dict

import structlog
from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.models import AgentResult

logger = structlog.get_logger()


class BriefingAgent(BaseAgent):
    """Cortex-powered morning briefing agent.

    Follows Golden Spec Method phases:
    - Phase 1: Deep Understanding (portfolio state, system health)
    - Phase 2-3: Outcomes (priority actions, blockers)
    - Phase 4-5: Solution alignment (recommended focus, alternatives)
    - Phase 7: Verification (learning from execution history)
    """

    def __init__(self):
        super().__init__(
            agent_id="morning_briefing",
            name="Cortex Morning Briefing",
            description="Cortex-powered daily briefing with strategic recommendations",
            metadata=AgentMetadata(
                version="2.0.0",
                author="jesse.kemp",
                description="Full-featured morning briefing using Cortex recommendation engine",
                tags=["daily", "cortex", "strategic", "learning"],
            ),
        )

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute the Cortex-powered morning briefing.

        Args:
            context: Execution context

        Returns:
            AgentResult with briefing data
        """
        try:
            # Import cortex briefing module
            from dataclasses import asdict

            from cortex.briefing import BriefingData, generate_daily_briefing

            briefing: BriefingData = generate_daily_briefing()

            # Convert dataclass to dict for serialization
            briefing_dict = asdict(briefing)
            # Convert datetime to ISO string for JSON serialization
            if "generated_at" in briefing_dict and briefing_dict["generated_at"]:
                briefing_dict["generated_at"] = briefing_dict["generated_at"].isoformat()

            # Extract key metrics for message
            active_count = len(briefing.active_projects)
            blocker_count = len(briefing.blockers)
            action_count = len(briefing.priority_actions)

            # Get top priority action if available
            focus = "No recommendations"
            if briefing.priority_actions:
                top_action = briefing.priority_actions[0]
                focus = top_action.get("title", top_action.get("description", "Check priorities"))

            message = (
                f"Morning briefing generated. "
                f"{active_count} active projects, {action_count} priority actions, "
                f"{blocker_count} blockers. Focus: {focus}"
            )

            return AgentResult(success=True, message=message, data=briefing_dict)

        except ImportError as e:
            logger.warning("cortex_briefing_not_available", error=str(e))
            return AgentResult(
                success=False,
                message="Cortex briefing module not available",
                data={"error": str(e)},
            )
        except Exception as e:
            logger.error("briefing_execution_failed", error=str(e))
            return AgentResult(
                success=False,
                message=f"Briefing failed: {str(e)}",
                data={"error": str(e)},
            )
