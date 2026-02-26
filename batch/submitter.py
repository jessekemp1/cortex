"""
Batch Submitter — Reads PENDING AI tasks from SQLite and submits to Anthropic Batch API.

Replaces the JSON-based submission path in queue_manager.py with a unified
SQLite-first approach. All task types (review, research, analysis, etc.)
flow through this single submitter.

Key features:
- Reads from BatchTaskQueue SQLite (single source of truth)
- Groups tasks into Anthropic batch submissions
- Circuit breaker: rate limits (429) trip, validation errors (400) skip individual tasks
- Model selection via model_policy.py
- Budget enforcement via budget_enforcer.py
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _sanitize_batch_id(raw_id: str) -> str:
    """Sanitize an ID for Anthropic API (^[a-zA-Z0-9_-]{1,64}$)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", raw_id)[:64]


@dataclass
class SubmissionStats:
    """Stats returned from a submission cycle."""

    checked_at: str = ""
    tasks_submitted: int = 0
    tasks_pending: int = 0
    batches_created: int = 0
    capacity_available: int = 0
    circuit_breaker_open: bool = False
    budget_exhausted: bool = False
    errors: List[str] = field(default_factory=list)


class BatchSubmitter:
    """Reads PENDING AI tasks from SQLite and submits to Anthropic Batch API."""

    def __init__(
        self,
        queue=None,
        client=None,
        model_policy=None,
        max_concurrent_batches: int = 5,
        max_requests_per_batch: int = 10_000,
        max_consecutive_failures: int = 3,
        circuit_cooldown_minutes: int = 60,
    ):
        # Lazy imports to avoid import-time side effects
        if queue is None:
            from intelligence.process_monitor.batch_queue import BatchTaskQueue

            queue = BatchTaskQueue()
        if client is None:
            from batch.batch_api_client import BatchAPIClient

            client = BatchAPIClient()
        if model_policy is None:
            from batch.model_policy import AnthropicBatchModels

            model_policy = AnthropicBatchModels()

        self.queue = queue
        self.client = client
        self.model_policy = model_policy
        self.max_concurrent = max_concurrent_batches
        self.max_per_batch = max_requests_per_batch

        # Circuit breaker state
        self._consecutive_failures = 0
        self._max_consecutive_failures = max_consecutive_failures
        self._circuit_cooldown_minutes = circuit_cooldown_minutes
        self._circuit_open_until: Optional[datetime] = None

    def submit_pending(self) -> SubmissionStats:
        """Main entry point: pick up PENDING tasks from SQLite, submit to API.

        Returns stats about what was submitted.
        """
        stats = SubmissionStats(checked_at=datetime.now().isoformat())

        # 1. Circuit breaker check
        if self._is_circuit_open():
            stats.circuit_breaker_open = True
            remaining = (self._circuit_open_until - datetime.now()).total_seconds() / 60
            logger.warning(f"Circuit breaker OPEN — {remaining:.0f} min remaining")
            return stats

        # 2. Budget check
        try:
            from batch.budget_enforcer import BudgetEnforcer

            enforcer = BudgetEnforcer()
            budget = enforcer.check_budget()
            if budget.over_budget:
                stats.budget_exhausted = True
                logger.info("Budget exhausted, skipping submission")
                return stats
        except Exception as e:
            logger.debug(f"Budget check unavailable: {e}")

        # 3. Capacity check — count active batches on Anthropic
        try:
            active_batches = self.client.list_batches(limit=20)
            active_count = sum(
                1 for b in active_batches if b["status"] in ("in_progress", "validating")
            )
            available = max(0, self.max_concurrent - active_count)
            stats.capacity_available = available
        except Exception as e:
            logger.warning(f"Could not check capacity: {e}")
            available = 1  # Assume at least 1 slot

        if available == 0:
            stats.tasks_pending = self.queue.get_pending_api_count()
            logger.info("No capacity available")
            return stats

        # 4. Get pending AI tasks from SQLite
        tasks = self.queue.get_pending_api_tasks(limit=self.max_per_batch)
        stats.tasks_pending = len(tasks)

        if not tasks:
            logger.debug("No pending API tasks")
            return stats

        # 5. Build and submit batch
        try:
            batch_requests, custom_id_map = self._build_batch_requests(tasks)
            if not batch_requests:
                return stats

            # Determine model (use first task's type for the batch description)
            model = self.model_policy.get_model(tasks[0].task_type)

            # Submit to Anthropic
            task_types = {t.task_type for t in tasks}
            description = f"Cortex batch: {len(tasks)} tasks ({', '.join(sorted(task_types))})"
            batch_id = self.client.submit_batch(requests=batch_requests, description=description)

            # Mark all tasks as SUBMITTED in SQLite
            task_ids = [t.task_id for t in tasks]
            self.queue.mark_submitted(task_ids, batch_id, custom_id_map, model)

            stats.tasks_submitted = len(tasks)
            stats.batches_created = 1
            self._consecutive_failures = 0  # Reset on success

            logger.info(
                f"Submitted {len(tasks)} tasks as batch {batch_id} "
                f"(model={model}, types={sorted(task_types)})"
            )

        except Exception as e:
            error_str = str(e).lower()
            stats.errors.append(str(e))
            logger.error(f"Batch submission failed: {e}")

            is_rate_limit = any(
                kw in error_str for kw in ["usage limit", "rate limit", "budget", "429"]
            )
            is_validation = "400" in error_str or "invalid_request" in error_str

            if is_rate_limit and not is_validation:
                self._consecutive_failures += 1
                logger.warning(
                    f"Rate/budget error ({self._consecutive_failures}/"
                    f"{self._max_consecutive_failures})"
                )
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._trip_circuit_breaker()
            elif is_validation:
                # Mark individual tasks as failed, don't trip breaker
                from intelligence.process_monitor.batch_queue import TaskState

                for task in tasks:
                    self.queue.update_task_state(
                        task.task_id,
                        TaskState.FAILED,
                        error_message=f"Validation error: {e}",
                    )
                logger.warning("Validation error — tasks marked FAILED, breaker not tripped")

        return stats

    def _build_batch_requests(self, tasks):
        """Convert BatchTask objects into BatchRequest list for the API.

        Returns (requests, custom_id_map) where custom_id_map maps task_id -> sanitized_id.
        """
        from batch.batch_api_client import BatchRequest

        requests = []
        custom_id_map: Dict[str, str] = {}

        for task in tasks:
            custom_id = _sanitize_batch_id(task.task_id)
            custom_id_map[task.task_id] = custom_id

            # The prompt is stored in the command field
            prompt = task.command
            if not prompt:
                logger.warning(f"Task {task.task_id} has no prompt, skipping")
                continue

            # Select model based on task type
            model = self.model_policy.get_model(task.task_type)

            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": task.metadata.get("max_tokens", 8192),
            }

            # Optional system prompt
            system = task.metadata.get("system_prompt")
            if system:
                params["system"] = system

            requests.append(BatchRequest(custom_id=custom_id, params=params))

        return requests, custom_id_map

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is blocking submissions."""
        if self._circuit_open_until is None:
            return False
        if datetime.now() >= self._circuit_open_until:
            logger.info("Circuit breaker cooldown expired, resetting")
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return False
        return True

    def _trip_circuit_breaker(self):
        """Trip the circuit breaker after consecutive rate-limit failures."""
        self._circuit_open_until = datetime.now() + timedelta(
            minutes=self._circuit_cooldown_minutes
        )
        logger.error(
            f"Circuit breaker TRIPPED after {self._consecutive_failures} failures. "
            f"Pausing for {self._circuit_cooldown_minutes} min "
            f"until {self._circuit_open_until.strftime('%H:%M')}"
        )
