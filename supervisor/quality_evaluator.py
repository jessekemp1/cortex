"""Quality evaluation for supervisor task outputs.

Provides heuristic scoring of task results without requiring
external AI judge calls.
"""

import re
from dataclasses import dataclass
from typing import Any

# Patterns that indicate refusal / non-answers
_REFUSAL_PATTERNS = re.compile(
    r"(?i)(I cannot|I can't|I'm unable|I am unable|please provide more|"
    r"I don't have enough|not able to complete)",
)

# Structured output signals (markdown headings, code blocks, tables)
_STRUCTURE_PATTERNS = [
    re.compile(r"^#{1,3}\s", re.MULTILINE),   # markdown headings
    re.compile(r"```\w*\n", re.MULTILINE),     # code blocks
    re.compile(r"\|.*\|.*\|", re.MULTILINE),   # tables
]


@dataclass
class EvaluationResult:
    """Result of a quality evaluation."""
    overall_score: float
    detail: str = ""


class QualityEvaluator:
    """Evaluate the quality of task execution results.

    Uses heuristic rules (exit codes, output length, error patterns)
    to score results without needing an external AI judge.
    """

    def __init__(self, *, use_ai_judge: bool = False):
        self.use_ai_judge = use_ai_judge

    def evaluate_heuristic(self, work_item: Any, result: Any) -> EvaluationResult:
        """Score a task result using heuristic rules.

        Args:
            work_item: The work item that was executed.
            result: The execution result.

        Returns:
            EvaluationResult with an overall_score between 0.0 and 1.0.
        """
        success = getattr(result, "success", False)
        if not success:
            return EvaluationResult(overall_score=0.0, detail="task failed")

        output = getattr(result, "output", "") or ""

        # Short output (< 20 chars) — low confidence
        if len(output) < 20:
            return EvaluationResult(overall_score=0.2, detail="very short output")

        # Refusal patterns — penalize heavily
        if _REFUSAL_PATTERNS.search(output):
            return EvaluationResult(overall_score=0.3, detail="refusal detected")

        # Count structural signals
        structure_hits = sum(
            1 for pat in _STRUCTURE_PATTERNS if pat.search(output)
        )

        if structure_hits >= 2:
            score = 0.9
        elif structure_hits == 1:
            score = 0.7
        elif len(output) > 100:
            score = 0.6
        else:
            score = 0.5

        return EvaluationResult(overall_score=score, detail="heuristic")
