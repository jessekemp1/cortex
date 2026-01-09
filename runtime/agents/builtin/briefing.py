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
            from cortex.briefing import generate_daily_briefing

            result = generate_daily_briefing()

            if result.get("success"):
                summary = result.get("summary", {})
                focus = summary.get("recommended_focus", "No recommendation")
                decisions = summary.get("decisions_needed", 0)
                status = summary.get("system_status", "unknown")

                message = (
                    f"Morning briefing generated ({status}). "
                    f"Focus: {focus}. "
                    f"{decisions} decisions needed."
                )

                return AgentResult(success=True, message=message, data=result)
            else:
                return AgentResult(
                    success=False,
                    message=f"Failed to generate briefing: {result.get('error')}",
                    data=result,
                )

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
