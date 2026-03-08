"""
Result collector — aggregates dispatch results and records outcomes.

Responsibilities:
  - Collect DispatchResults from parallel dispatches
  - Record model outcomes for future routing optimization
  - Generate execution summaries
  - Persist results to ~/.cortex/orchestration/
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cortex.supervisor.dispatch import DispatchResult

log = logging.getLogger(__name__)

_DEFAULT_RESULTS_DIR = Path.home() / ".cortex" / "orchestration" / "runs"
_DEFAULT_OUTCOMES_PATH = Path.home() / ".cortex" / "orchestration" / "model_outcomes.jsonl"


@dataclass
class BatchSummary:
    """Aggregated summary for a batch of dispatches."""

    total: int
    succeeded: int
    failed: int
    total_tokens: int
    total_duration_seconds: float
    model_breakdown: dict[str, int]  # model_tier -> count
    errors: list[str]


class ResultCollector:
    """Collects :class:`DispatchResult` instances and persists outcomes.

    Usage::

        collector = ResultCollector()
        collector.collect(result_a)
        collector.collect(result_b)
        summary = collector.get_summary()
        path = collector.persist()
    """

    def __init__(
        self,
        results_dir: Path | None = None,
        outcomes_path: Path | None = None,
    ) -> None:
        self._results_dir = results_dir or _DEFAULT_RESULTS_DIR
        self._outcomes_path = outcomes_path or _DEFAULT_OUTCOMES_PATH
        self._results: list[DispatchResult] = []

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect(self, result: DispatchResult) -> None:
        """Add a single :class:`DispatchResult` to the current batch."""
        self._results.append(result)

    def collect_batch(self, results: list[DispatchResult]) -> BatchSummary:
        """Add multiple results and return a summary of the full batch."""
        for r in results:
            self._results.append(r)
        return self.get_summary()

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        result: DispatchResult,
        quality_score: float | None = None,
    ) -> None:
        """Append an outcome entry to ``model_outcomes.jsonl``.

        This feeds the routing optimiser so future dispatches can learn which
        model tier works best for each task type.
        """
        model_tier = _tier_from_model_id(result.model_used)
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "work_item_id": result.work_item_id,
            "model_tier": model_tier,
            "model_id": result.model_used,
            "success": result.success,
            "quality_score": quality_score,
            "tokens_used": result.tokens_used,
            "duration_seconds": result.duration_seconds,
        }
        self._outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        with self._outcomes_path.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
        log.debug("recorded outcome: work_item=%s model=%s", result.work_item_id, model_tier)

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def get_summary(self) -> BatchSummary:
        """Build and return a :class:`BatchSummary` for collected results."""
        succeeded = sum(1 for r in self._results if r.success)
        failed = sum(1 for r in self._results if not r.success)
        total_tokens = sum(r.tokens_used for r in self._results)
        total_duration = sum(r.duration_seconds for r in self._results)

        breakdown: dict[str, int] = {}
        for r in self._results:
            tier = _tier_from_model_id(r.model_used)
            breakdown[tier] = breakdown.get(tier, 0) + 1

        errors = [r.error for r in self._results if r.error]

        return BatchSummary(
            total=len(self._results),
            succeeded=succeeded,
            failed=failed,
            total_tokens=total_tokens,
            total_duration_seconds=round(total_duration, 3),
            model_breakdown=breakdown,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self) -> Path:
        """Write results and summary to disk. Returns the run directory path."""
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = self._results_dir / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        # results.json — full result list
        results_path = run_dir / "results.json"
        results_data = [_dispatch_result_to_dict(r) for r in self._results]
        results_path.write_text(json.dumps(results_data, indent=2) + "\n")

        # summary.json
        summary_path = run_dir / "summary.json"
        summary = self.get_summary()
        summary_path.write_text(json.dumps(asdict(summary), indent=2) + "\n")

        log.info("persisted %d results to %s", len(self._results), run_dir)
        return run_dir

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset the collector for the next batch."""
        self._results.clear()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _tier_from_model_id(model_id: str) -> str:
    """Extract model tier (opus/sonnet/haiku) from a model ID string."""
    model_lower = model_id.lower()
    for tier in ("opus", "sonnet", "haiku"):
        if tier in model_lower:
            return tier
    return "unknown"


def _dispatch_result_to_dict(result: DispatchResult) -> dict:
    """Serialise a :class:`DispatchResult` to a plain dict."""
    return {
        "work_item_id": result.work_item_id,
        "success": result.success,
        "output": result.output,
        "model_used": result.model_used,
        "tokens_used": result.tokens_used,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
        "checkpoint_id": result.checkpoint_id,
    }
