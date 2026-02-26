"""
Batch Retriever — Polls SUBMITTED tasks and downloads results when complete.

Replaces the result-retrieval logic in queue_manager.monitor_and_update_status()
with a unified SQLite-first approach. Groups tasks by api_batch_id and checks
each batch once per cycle.

Key features:
- Reads SUBMITTED tasks from BatchTaskQueue SQLite
- Polls Anthropic API for batch completion
- Downloads JSONL results and extracts response text
- Stores results as JSON files for morning processor
- Updates SQLite with completion status, tokens, and result text
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrievalStats:
    """Stats returned from a retrieval cycle."""

    checked_at: str = ""
    batches_checked: int = 0
    batches_completed: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    results_saved: int = 0
    errors: List[str] = field(default_factory=list)


class BatchRetriever:
    """Polls SUBMITTED tasks, downloads results when batches complete."""

    def __init__(
        self,
        queue=None,
        client=None,
        results_dir: Optional[Path] = None,
    ):
        if queue is None:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue

            queue = BatchTaskQueue()
        if client is None:
            from batch.batch_api_client import BatchAPIClient

            client = BatchAPIClient()
        if results_dir is None:
            results_dir = Path.home() / ".cortex" / "batch" / "results"

        self.queue = queue
        self.client = client
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def retrieve_completed(self) -> RetrievalStats:
        """Main entry point: check SUBMITTED batches, download results.

        Groups tasks by api_batch_id so each Anthropic batch is only
        checked once, even if it contains multiple tasks.
        """
        stats = RetrievalStats(checked_at=datetime.now().isoformat())

        submitted = self.queue.get_submitted_tasks()
        if not submitted:
            return stats

        # Group by api_batch_id
        batches: Dict[str, list] = {}
        for task in submitted:
            bid = task.api_batch_id
            if bid:
                batches.setdefault(bid, []).append(task)

        stats.batches_checked = len(batches)

        for batch_id, tasks in batches.items():
            try:
                status = self.client.get_batch_status(batch_id)
                batch_status = status["status"]

                if batch_status in ("ended", "completed"):
                    self._process_completed_batch(batch_id, tasks, status, stats)
                elif batch_status in ("failed", "expired", "canceled", "canceling"):
                    self._process_failed_batch(batch_id, tasks, batch_status, stats)
                else:
                    # Still processing — log progress
                    counts = status.get("request_counts", {})
                    pct = status.get("progress_percentage", 0)
                    logger.debug(
                        f"Batch {batch_id}: {pct}% "
                        f"({counts.get('succeeded', 0)} done, "
                        f"{counts.get('processing', 0)} processing)"
                    )

            except Exception as e:
                stats.errors.append(f"{batch_id}: {e}")
                logger.error(f"Error checking batch {batch_id}: {e}")

        return stats

    def _process_completed_batch(
        self, batch_id: str, tasks: list, status: dict, stats: RetrievalStats
    ):
        """Download results for a completed batch and update SQLite."""
        stats.batches_completed += 1

        # Build lookup: api_custom_id -> task
        task_lookup: Dict[str, object] = {}
        for task in tasks:
            if task.api_custom_id:
                task_lookup[task.api_custom_id] = task

        try:
            batch_results = self.client._retrieve_batch_results(batch_id)

            for result in batch_results:
                task = task_lookup.get(result.custom_id)
                if not task:
                    logger.warning(f"Result custom_id {result.custom_id} has no matching task")
                    continue

                # Extract response text
                response_text = self._extract_response_text(result)
                input_tokens, output_tokens = self._extract_token_counts(result)

                # Save result file
                result_file = self._save_result(task, batch_id, result, response_text)

                if result.status == "succeeded":
                    self.queue.mark_completed_with_result(
                        task.task_id,
                        result_text=response_text,
                        result_file=str(result_file),
                        token_input=input_tokens,
                        token_output=output_tokens,
                    )
                    stats.tasks_completed += 1
                    stats.results_saved += 1
                    logger.info(
                        f"Task {task.task_id} completed ({input_tokens}+{output_tokens} tokens)"
                    )
                else:
                    from intelligence.process_monitor.batch_queue import TaskState

                    self.queue.update_task_state(
                        task.task_id,
                        TaskState.FAILED,
                        error_message=f"Batch result status: {result.status}",
                    )
                    stats.tasks_failed += 1

            # Handle tasks with no matching result (shouldn't happen, but defensive)
            matched_ids = {r.custom_id for r in batch_results}
            for task in tasks:
                if task.api_custom_id and task.api_custom_id not in matched_ids:
                    from intelligence.process_monitor.batch_queue import TaskState

                    self.queue.update_task_state(
                        task.task_id,
                        TaskState.FAILED,
                        error_message=f"No result found in batch {batch_id}",
                    )
                    stats.tasks_failed += 1

        except Exception as e:
            logger.error(f"Failed to retrieve results for batch {batch_id}: {e}")
            stats.errors.append(f"Result retrieval: {e}")

    def _process_failed_batch(
        self, batch_id: str, tasks: list, batch_status: str, stats: RetrievalStats
    ):
        """Mark all tasks in a failed/expired batch as FAILED."""
        from intelligence.process_monitor.batch_queue import TaskState

        for task in tasks:
            self.queue.update_task_state(
                task.task_id,
                TaskState.FAILED,
                error_message=f"Batch {batch_status}: {batch_id}",
            )
            stats.tasks_failed += 1

        logger.warning(f"Batch {batch_id} {batch_status} — {len(tasks)} tasks marked FAILED")

    def _extract_response_text(self, result) -> str:
        """Extract text from an Anthropic batch result."""
        result_obj = result.result
        if isinstance(result_obj, dict):
            if result_obj.get("type") == "succeeded":
                msg = result_obj.get("message", {})
                content = msg.get("content", [])
                return "".join(b.get("text", "") for b in content if b.get("type") == "text")
        return ""

    def _extract_token_counts(self, result) -> tuple:
        """Extract input/output token counts from a result."""
        result_obj = result.result
        if isinstance(result_obj, dict) and result_obj.get("type") == "succeeded":
            msg = result_obj.get("message", {})
            usage = msg.get("usage", {})
            return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        return 0, 0

    def _save_result(self, task, batch_id: str, result, response_text: str) -> Path:
        """Save result JSON to results directory for morning processor."""
        result_data = {
            "job_id": task.task_id,
            "batch_id": batch_id,
            "title": task.description,
            "status": result.status,
            "completed_at": datetime.now().isoformat(),
            "source": task.metadata.get("source", "batch"),
            "type": task.task_type,
            "response_text": response_text,
        }

        # Include raw result for detailed analysis
        if isinstance(result.result, dict):
            result_data["result"] = result.result

        result_file = self.results_dir / f"{task.task_id}_{batch_id}.json"
        result_file.write_text(json.dumps(result_data, indent=2, default=str))
        return result_file
