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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from cortex.supervisor.dispatch import DispatchResult

log = logging.getLogger(__name__)

_DEFAULT_RESULTS_DIR = Path.home() / ".cortex" / "orchestration" / "runs"
_DEFAULT_OUTCOMES_PATH = Path.home() / ".cortex" / "orchestration" / "model_outcomes.jsonl"


@dataclass
class VerificationEvidence:
    """Structured evidence of verification quality for a dispatched task.

    Score breakdown (0-100):
      - tests_ran:        up to 20 pts (10+ tests = max)
      - tests_relevant:   20 pts
      - assertion_depth:  up to 32 pts  (L0=none … L4=golden baseline match)
      - regression_free:  20 pts
      - golden_match:      8 pts

    Interpretation:
      score >= 60  → verified, proceed
      40 <= score < 60 → flag for human review
      score < 40   → auto-reject, re-queue with different approach
    """

    tests_ran: int = 0  # how many tests actually executed
    tests_relevant: bool = False  # test-orchestrator confirmed coverage
    assertion_depth: int = 0  # L0-L4 (existence → regression detection)
    golden_match: bool = False  # output matches known-good baseline
    regression_free: bool = False  # no existing tests broken
    human_required: bool = False  # risk level demands spot-check

    @property
    def score(self) -> float:
        """0-100 verification quality score."""
        s = 0.0
        s += min(self.tests_ran, 10) * 2.0  # up to 20 pts
        s += 20.0 if self.tests_relevant else 0.0
        s += self.assertion_depth * 8.0  # up to 32 pts (L4=32)
        s += 20.0 if self.regression_free else 0.0
        s += 8.0 if self.golden_match else 0.0
        return round(min(s, 100.0), 1)

    @property
    def needs_review(self) -> bool:
        """Score below 60 or human explicitly required."""
        return self.score < 60.0 or self.human_required

    @property
    def auto_reject(self) -> bool:
        """Score below 40 — re-queue with different approach."""
        return self.score < 40.0

    def to_dict(self) -> dict:
        return {
            "tests_ran": self.tests_ran,
            "tests_relevant": self.tests_relevant,
            "assertion_depth": self.assertion_depth,
            "golden_match": self.golden_match,
            "regression_free": self.regression_free,
            "human_required": self.human_required,
            "score": self.score,
            "needs_review": self.needs_review,
            "auto_reject": self.auto_reject,
        }


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
    flagged_for_review: int = 0  # results where verification.needs_review
    auto_rejected: int = 0  # results where verification.auto_reject


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
        self._evidence: dict[str, VerificationEvidence] = {}  # work_item_id -> evidence

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect(self, result: DispatchResult) -> None:
        """Add a single :class:`DispatchResult` to the current batch."""
        self._results.append(result)

    def collect_batch(
        self,
        results: list[DispatchResult],
        evidence: list[VerificationEvidence] | None = None,
    ) -> BatchSummary:
        """Add multiple results and return a summary of the full batch.

        Args:
            results: Dispatch results to collect.
            evidence: Optional per-result verification evidence (parallel list).
                      If provided, flagged/rejected counts are updated in the summary.
        """
        for i, r in enumerate(results):
            self._results.append(r)
            if evidence and i < len(evidence):
                self._evidence[r.work_item_id] = evidence[i]
        return self.get_summary()

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        result: DispatchResult,
        quality_score: float | None = None,
        is_baseline: bool = False,
        evidence: VerificationEvidence | None = None,
    ) -> None:
        """Append an outcome entry to ``model_outcomes.jsonl``.

        This feeds the routing optimiser so future dispatches can learn which
        model tier works best for each task type.

        Args:
            is_baseline: True if this task was part of the A/B baseline
                (forced Anthropic-only for quality comparison).
            evidence: Optional verification evidence. When present, verification
                quality is persisted alongside the outcome so routing can learn
                which task types produce trustworthy outputs.
        """
        ev = evidence or self._evidence.get(result.work_item_id)
        model_tier = _tier_from_model_id(result.model_used)
        entry: dict = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "work_item_id": result.work_item_id,
            "model_tier": model_tier,
            "model_id": result.model_used,
            "task_type": result.task_type,
            "success": result.success,
            "quality_score": quality_score,
            "tokens_used": result.tokens_used,
            "duration_seconds": result.duration_seconds,
            "provider": getattr(result, "provider", "anthropic"),
            "cost_usd": getattr(result, "cost_usd", 0.0),
            "is_baseline": is_baseline,
        }
        if ev is not None:
            entry["verification"] = ev.to_dict()
        self._outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        with self._outcomes_path.open("a", encoding="utf-8") as fh:
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

        flagged = sum(
            1
            for r in self._results
            if (ev := self._evidence.get(r.work_item_id)) and ev.needs_review
        )
        rejected = sum(
            1
            for r in self._results
            if (ev := self._evidence.get(r.work_item_id)) and ev.auto_reject
        )

        return BatchSummary(
            total=len(self._results),
            succeeded=succeeded,
            failed=failed,
            total_tokens=total_tokens,
            total_duration_seconds=round(total_duration, 3),
            model_breakdown=breakdown,
            errors=errors,
            flagged_for_review=flagged,
            auto_rejected=rejected,
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
        self._evidence.clear()

    def attach_evidence(self, work_item_id: str, evidence: VerificationEvidence) -> None:
        """Attach verification evidence to a previously collected result.

        Useful when verification runs asynchronously after dispatch.
        """
        self._evidence[work_item_id] = evidence
        log.debug("evidence attached: work_item=%s score=%.1f", work_item_id, evidence.score)


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
        "task_type": result.task_type,
        "tokens_used": result.tokens_used,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
        "checkpoint_id": result.checkpoint_id,
    }
