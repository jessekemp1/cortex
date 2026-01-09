"""System agents for handling Claude Batches.

These agents run on schedules to process the batch queue
and handle results from completed batches.
"""

from typing import TYPE_CHECKING, Any, Dict

import structlog

from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.batch.client import AnthropicBatchClient
from cortex.runtime.models import AgentResult

if TYPE_CHECKING:
    from cortex.runtime.executor import RuntimeExecutor

logger = structlog.get_logger()


class BatchProcessorAgent(BaseAgent):
    """System Agent: Runs hourly (or on trigger).

    Role: Aggregates pending items from queue and submits a Batch to Anthropic.
    """

    def __init__(self, executor: "RuntimeExecutor"):
        """Initialize the batch processor.

        Args:
            executor: The runtime executor instance
        """
        super().__init__(
            agent_id="system_batch_processor",
            name="Batch Processor (Night Shift)",
            description="Aggregates queue items into Batches",
            metadata=AgentMetadata(version="1.0", tags=["system", "batch"]),
        )
        self.executor = executor
        self.client = AnthropicBatchClient()

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute batch processing.

        Args:
            context: Execution context

        Returns:
            AgentResult with batch submission details
        """
        if not hasattr(self.executor, "batch_manager"):
            return AgentResult(
                success=False, message="BatchManager not initialized", data={}
            )

        manager = self.executor.batch_manager

        # 1. Get Pending Items
        items = manager.get_pending_items(limit=100)
        if not items:
            return AgentResult(
                success=True, message="No pending items to batch", data={"count": 0}
            )

        # 2. Prepare Items for Client
        client_items = []
        for item in items:
            client_items.append(
                {"custom_id": str(item["id"]), "prompt": item["prompt"]}
            )

        logger.info("batch_processor_submitting", count=len(items))

        # 3. Submit Batch via Client
        try:
            batch_resp = self.client.create_batch(client_items)
            batch_id = batch_resp["batch_id"]

            # 4. Update Database
            item_ids = [item["id"] for item in items]
            manager.mark_items_processing(item_ids, batch_id)
            manager.track_batch(batch_id, status="in_progress")

            return AgentResult(
                success=True,
                message=f"Created batch {batch_id} with {len(items)} items",
                data={"batch_id": batch_id, "item_count": len(items)},
            )
        except Exception as e:
            logger.error("batch_submission_fatal_error", error=str(e))
            return AgentResult(
                success=False, message=f"Batch submission failed: {str(e)}"
            )


class ResultHandlerAgent(BaseAgent):
    """System Agent: Runs every 15m.

    Role: Checks active batches. If complete, downloads results and triggers callbacks.
    """

    def __init__(self, executor: "RuntimeExecutor"):
        """Initialize the result handler.

        Args:
            executor: The runtime executor instance
        """
        super().__init__(
            agent_id="system_result_handler",
            name="Batch Result Handler",
            description="Checks status and delivers results",
            metadata=AgentMetadata(version="1.0", tags=["system", "batch"]),
        )
        self.executor = executor
        self.client = AnthropicBatchClient()

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Check batch status and deliver results.

        Args:
            context: Execution context

        Returns:
            AgentResult with processing summary
        """
        if not hasattr(self.executor, "batch_manager"):
            return AgentResult(
                success=False, message="BatchManager not initialized", data={}
            )

        manager = self.executor.batch_manager

        # 1. Get Active Batches
        batches = manager.get_active_batches()
        if not batches:
            return AgentResult(
                success=True, message="No active batches", data={"count": 0}
            )

        processed_count = 0

        for batch in batches:
            batch_id = batch["batch_id"]

            # 2. Check Status
            try:
                remote_batch = self.client.get_batch(batch_id)
                status = remote_batch.get("status")

                if status == "ended":
                    # 3. Download Results
                    results = self.client.get_results(batch_id)

                    # 4. Trigger Callbacks
                    original_items = manager.get_callbacks_for_batch(batch_id)
                    results_map = {r["custom_id"]: r["result_text"] for r in results}

                    for item in original_items:
                        callback_id = item["callback_agent_id"]
                        prompt = item["prompt"]
                        item_id_key = str(item["id"])

                        result_text = results_map.get(item_id_key, "")

                        # Fallback for simulation mode
                        if not result_text and batch_id.startswith("msgbatch_sim_"):
                            result_text = (
                                f"[Batch Result] Processed prompt: {prompt[:20]}..."
                            )

                        if result_text:
                            try:
                                trigger_context = {
                                    "source": "batch_system",
                                    "original_prompt": prompt,
                                    "batch_result": result_text,
                                }
                                logger.info(
                                    "triggering_callback",
                                    agent_id=callback_id,
                                    context_keys=list(trigger_context.keys()),
                                )
                                self.executor.trigger_agent(callback_id, trigger_context)
                            except Exception as e:
                                logger.error(
                                    "batch_callback_failed",
                                    agent_id=callback_id,
                                    error=str(e),
                                )

                    # 5. Mark Complete
                    manager.update_batch_status(
                        batch_id, "ended", result_file_id="processed"
                    )
                    processed_count += 1

            except Exception as e:
                logger.error("batch_processing_error", batch_id=batch_id, error=str(e))
                continue

        return AgentResult(
            success=True,
            message=f"Processed {processed_count} batches",
            data={"processed": processed_count},
        )
