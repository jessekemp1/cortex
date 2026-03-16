"""
Quality evaluator — replaces fragile _estimate_quality() with real signal.

Two evaluation modes:
  1. Heuristic (sync, <1ms): improved output analysis with task-type-specific checks
  2. AI Judge (async, background): uses haiku-tier model for nuanced evaluation

The heuristic runs inline on every dispatch. The AI judge fires asynchronously
after the heuristic completes, updating the outcome record when done.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class QualityEvaluation:
    """Result of a quality evaluation."""

    overall_score: float  # 0.0-1.0
    dimensions: Dict[str, float] = field(default_factory=dict)  # correctness, completeness, etc.
    rationale: str = ""
    evaluator: str = "heuristic"  # "heuristic" | "ai_judge"


class QualityEvaluator:
    """Replaces _estimate_quality() with multi-signal quality assessment.

    Heuristic scoring signals:
      - Response/prompt length ratio (too short = low quality)
      - Task-type-specific checks (code tasks need code blocks)
      - Error pattern detection (refusals, hedging, apologies)
      - Structured output signals (JSON, tables, headings)
      - Completeness signals (action items, conclusions)
    """

    def __init__(self, use_ai_judge: bool = False) -> None:
        self._use_ai_judge = use_ai_judge

    def evaluate_heuristic(
        self,
        work_item: Any,
        result: Any,
    ) -> QualityEvaluation:
        """Fast synchronous evaluation based on output analysis.

        Args:
            work_item: The original WorkItem
            result: The DispatchResult

        Returns:
            QualityEvaluation with overall_score 0.0-1.0
        """
        if not result.success:
            return QualityEvaluation(
                overall_score=0.0,
                dimensions={"correctness": 0.0, "completeness": 0.0},
                rationale="Dispatch failed",
                evaluator="heuristic",
            )

        output = result.output.strip()
        if not output:
            return QualityEvaluation(
                overall_score=0.1,
                dimensions={"correctness": 0.1, "completeness": 0.0},
                rationale="Empty output",
                evaluator="heuristic",
            )

        lower = output.lower()
        length = len(output)
        task_type = getattr(work_item, "task_type", "")

        # Dimension scores
        correctness = self._score_correctness(output, lower, task_type)
        completeness = self._score_completeness(output, lower, length)
        relevance = self._score_relevance(output, lower, work_item)
        structure = self._score_structure(output, length)

        # Weighted overall
        overall = 0.35 * correctness + 0.25 * completeness + 0.25 * relevance + 0.15 * structure

        dimensions = {
            "correctness": round(correctness, 3),
            "completeness": round(completeness, 3),
            "relevance": round(relevance, 3),
            "structure": round(structure, 3),
        }

        rationale_parts = []
        if correctness < 0.4:
            rationale_parts.append("low correctness (refusal/error signals)")
        if completeness < 0.4:
            rationale_parts.append("low completeness (short output)")
        if structure > 0.7:
            rationale_parts.append("well-structured output")
        rationale = "; ".join(rationale_parts) if rationale_parts else "moderate quality"

        return QualityEvaluation(
            overall_score=round(min(max(overall, 0.0), 1.0), 3),
            dimensions=dimensions,
            rationale=rationale,
            evaluator="heuristic",
        )

    async def evaluate_ai_judge(
        self,
        work_item: Any,
        result: Any,
    ) -> Optional[QualityEvaluation]:
        """Async AI evaluation using haiku-tier model via QualityJudge.

        Falls back to None (caller should use heuristic) on any failure.
        This is a background enhancement — never blocks dispatch.

        Uses the existing QualityJudge from intelligence/evaluation/ to get
        a 4-dimension evaluation. Adapts its PatternScore (1-5 discrete scale)
        into our QualityEvaluation (0.0-1.0 continuous dimensions).
        """
        if not self._use_ai_judge:
            return None

        try:
            from intelligence.evaluation.quality_judge import QualityJudge

            judge = QualityJudge()

            # Build evaluation payload matching QualityJudge's expected format
            task_type = getattr(work_item, "task_type", "unknown")
            description = getattr(work_item, "description", "")
            output = getattr(result, "output", "")
            success = getattr(result, "success", False)

            if not success or not output:
                return None  # Not worth AI evaluation on failures

            pattern = {
                "id": getattr(work_item, "id", "unknown"),
                "title": f"{task_type}: {description[:100]}",
                "description": output[:2000],  # Truncate to control cost
                "context": {"task_type": task_type, "success": success},
            }

            score = await judge.evaluate_pattern(pattern, description)

            # Adapt 1-5 discrete scores to 0.0-1.0 continuous
            dimensions = {
                "correctness": (score.accuracy - 1) / 4.0,
                "completeness": (score.specificity - 1) / 4.0,
                "relevance": (score.relevance - 1) / 4.0,
                "structure": (score.actionability - 1) / 4.0,
            }

            return QualityEvaluation(
                overall_score=round(score.overall, 3),
                dimensions=dimensions,
                rationale=score.rationale,
                evaluator="ai_judge",
            )

        except ImportError:
            log.debug("QualityJudge not available; using heuristic")
            return None
        except Exception as exc:
            log.warning("AI judge evaluation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Scoring dimensions
    # ------------------------------------------------------------------

    def _score_correctness(self, output: str, lower: str, task_type: str) -> float:
        """Correctness: absence of refusal/error signals, presence of expected content."""
        score = 0.7  # Baseline

        # Refusal signals
        refusal_phrases = [
            "cannot complete",
            "need more context",
            "need additional information",
            "unable to",
            "please provide",
            "i need clarification",
            "insufficient input",
            "i don't have access",
            "i cannot",
        ]
        refusal_count = sum(1 for p in refusal_phrases if p in lower)
        if refusal_count >= 2:
            return 0.1
        if refusal_count == 1:
            score -= 0.3

        # Error/hedging signals
        hedging = ["i'm not sure", "i think maybe", "this might not work"]
        if any(h in lower for h in hedging):
            score -= 0.15

        # Task-type-specific: code tasks should have code blocks
        code_types = {"implement", "fix", "refactor", "feature", "test"}
        if task_type in code_types and "```" not in output:
            score -= 0.2

        return max(score, 0.0)

    def _score_completeness(self, output: str, lower: str, length: int) -> float:
        """Completeness: is the response substantive enough?"""
        if length < 30:
            return 0.1
        if length < 100:
            return 0.3
        if length < 300:
            return 0.5

        # Check for conclusion/summary signals
        conclusion_signals = ["in summary", "conclusion", "next steps", "to summarize"]
        has_conclusion = any(s in lower for s in conclusion_signals)

        score = 0.7
        if has_conclusion:
            score += 0.15
        if length > 1000:
            score += 0.1

        return min(score, 1.0)

    def _score_relevance(self, output: str, lower: str, work_item: Any) -> float:
        """Relevance: does the output relate to the task?"""
        description = getattr(work_item, "description", "")
        if not description:
            return 0.6

        # Simple word overlap check
        desc_words = set(description.lower().split())
        output_words = set(lower.split())
        if not desc_words:
            return 0.6

        overlap = len(desc_words & output_words) / len(desc_words)
        return min(0.4 + overlap * 0.6, 1.0)

    def _score_structure(self, output: str, length: int) -> float:
        """Structure: is the output well-organized?"""
        signals = 0
        if "```" in output:
            signals += 1
        if output.count("#") >= 2:
            signals += 1
        if any(c in output for c in ["|---", "| ---"]):
            signals += 1
        if any(output.lstrip().startswith(f"{i}.") for i in range(1, 6)):
            signals += 1
        if length > 500:
            signals += 1

        return min(signals / 3.0, 1.0)
