"""Refactor Agent - Night Shift Code Improvement.

Specialized agent for executing large-scale or non-urgent refactors
via the Batch API (overnight processing).
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import structlog

from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.models import AgentResult

if TYPE_CHECKING:
    from cortex.runtime.executor import RuntimeExecutor

logger = structlog.get_logger()


class RefactorAgent(BaseAgent):
    """Refactor Agent (Night Shift).

    Submits code improvement tasks to the Batch Queue.
    On callback, it applies the changes or returns a diff.
    """

    def __init__(
        self,
        agent_id: str = "refactor_agent_01",
        executor: Optional["RuntimeExecutor"] = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="Refactor Agent (Night Shift)",
            description="Asynchronous code refactoring engine",
            metadata=AgentMetadata(
                version="1.0",
                tags=["dev", "night_shift", "batch"],
            ),
        )
        self.executor = executor

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute refactor task.

        Args:
            context: Execution context with 'files' and 'instruction'

        Returns:
            AgentResult with refactoring status
        """
        start_time = datetime.now()

        # Check for batch callback (Night Shift result)
        batch_result = context.get("batch_result")
        if batch_result:
            return self._handle_batch_completion(context, batch_result, start_time)

        # Standard flow - submit new request
        return self._submit_refactor_request(context, start_time)

    def _submit_refactor_request(
        self, context: Dict[str, Any], start_time: datetime
    ) -> AgentResult:
        """Submit a new refactor request to the Batch System."""
        target_files = context.get("files", [])
        instruction = context.get("instruction", "Improve code quality")

        if not target_files:
            return AgentResult(success=False, message="No files provided for refactor")

        logger.info("refactor_request_received", files=target_files, instruction=instruction)

        # Construct prompt
        prompt = (
            f"REFACTOR TASK:\n"
            f"Files: {target_files}\n"
            f"Instruction: {instruction}\n\n"
            f"Please provide git-diffs."
        )

        # Enqueue to batch system
        if self.executor and hasattr(self.executor, "batch_manager"):
            try:
                item_id = self.executor.batch_manager.enqueue(prompt, self.agent_id)
                return AgentResult(
                    success=True,
                    message=f"Refactor task enqueued for {len(target_files)} files.",
                    data={"item_id": item_id, "status": "batched"},
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
            except Exception as e:
                logger.error("batch_enqueue_failed", error=str(e))
                return AgentResult(
                    success=False,
                    message=f"Failed to enqueue batch task: {str(e)}",
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )
        else:
            return AgentResult(
                success=False,
                message="Batch manager not available",
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

    def _handle_batch_completion(
        self, context: Dict[str, Any], result: str, start_time: datetime
    ) -> AgentResult:
        """Handle the result from the Night Shift."""
        original_prompt = context.get("original_prompt", "")

        logger.info("refactor_completed", result_preview=result[:50])

        return AgentResult(
            success=True,
            message="Refactor plan generated (Night Shift)",
            data={
                "diff": result,
                "original_task": original_prompt,
                "source": "batch_system",
            },
            execution_time=(datetime.now() - start_time).total_seconds(),
        )
