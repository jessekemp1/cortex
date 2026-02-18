"""Research Agent - Batch-powered research workflows.

Specialized agent for executing research tasks via the Batch API,
suitable for complex, time-consuming research operations.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import structlog

from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.models import AgentResult

if TYPE_CHECKING:
    from cortex.runtime.executor import RuntimeExecutor

logger = structlog.get_logger()


class ResearchAgent(BaseAgent):
    """Research Agent for batch-powered research workflows.

    Submits research tasks to the Batch Queue for overnight processing.
    """

    def __init__(
        self,
        agent_id: str = "research_agent_01",
        executor: Optional["RuntimeExecutor"] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="Research Agent (Night Shift)",
            description="Batch-powered research and analysis engine",
            metadata=AgentMetadata(
                version="1.0",
                tags=["research", "night_shift", "batch"],
            ),
        )
        self.executor = executor

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute research task.

        Args:
            context: Execution context with 'topic' and optional 'sources'

        Returns:
            AgentResult with research status or findings
        """
        start_time = datetime.now()

        # Check for batch callback
        batch_result = context.get("batch_result")
        if batch_result:
            return self._handle_research_completion(context, batch_result, start_time)

        # Submit new research request
        return self._submit_research_request(context, start_time)

    def _submit_research_request(
        self, context: Dict[str, Any], start_time: datetime
    ) -> AgentResult:
        """Submit a new research request to the Batch System."""
        topic = context.get("topic", "")
        sources = context.get("sources", [])
        depth = context.get("depth", "standard")

        if not topic:
            return AgentResult(
                success=False,
                message="No research topic provided",
            )

        logger.info("research_request_received", topic=topic, sources=sources)

        # Construct research prompt
        prompt = (
            f"RESEARCH TASK:\n"
            f"Topic: {topic}\n"
            f"Depth: {depth}\n"
            f"Sources: {sources if sources else 'General research'}\n\n"
            f"Please provide a comprehensive analysis with sources."
        )

        # Enqueue to batch system
        if self.executor and hasattr(self.executor, "batch_manager"):
            try:
                item_id = self.executor.batch_manager.enqueue(prompt, self.agent_id)
                return AgentResult(
                    success=True,
                    message=f"Research task enqueued: {topic[:50]}...",
                    data={"item_id": item_id, "status": "batched", "topic": topic},
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            except Exception as e:
                logger.error("research_enqueue_failed", error=str(e))
                return AgentResult(
                    success=False,
                    message=f"Failed to enqueue research: {str(e)}",
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
        else:
            return AgentResult(
                success=False,
                message="Batch manager not available",
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

    def _handle_research_completion(
        self, context: Dict[str, Any], result: str, start_time: datetime
    ) -> AgentResult:
        """Handle completed research from the Night Shift."""
        original_topic = context.get("original_prompt", "")

        logger.info("research_completed", result_preview=result[:100])

        return AgentResult(
            success=True,
            message="Research completed (Night Shift)",
            data={
                "findings": result,
                "original_topic": original_topic,
                "source": "batch_system",
            },
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
