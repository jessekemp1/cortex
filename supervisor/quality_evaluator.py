"""Heuristic quality evaluation for supervisor dispatch outcomes."""

import re
from dataclasses import dataclass, field
from typing import Any

REFUSAL_PATTERNS = re.compile(
    r"(?i)(I cannot|I'm unable|I can't|unable to complete|please provide more)",
)

STRUCTURE_PATTERNS = [
    re.compile(r"```"),  # code blocks
    re.compile(r"^#{1,3} ", re.MULTILINE),  # markdown headings
    re.compile(r"\|.*\|.*\|"),  # tables
    re.compile(r"^\d+\.\s", re.MULTILINE),  # numbered lists
]


@dataclass
class QualityEvaluation:
    overall_score: float
    dimensions: dict[str, float] = field(default_factory=dict)


class QualityEvaluator:
    """Evaluates work item results using heuristic signals.

    When use_ai_judge=True, could delegate to an LLM for nuanced evaluation.
    Currently only heuristic mode is implemented.
    """

    def __init__(self, use_ai_judge: bool = False):
        self.use_ai_judge = use_ai_judge

    def evaluate_heuristic(self, work_item: Any, result: Any) -> QualityEvaluation:
        """Score a dispatch result based on heuristic signals."""
        success = getattr(result, "success", False)
        output = getattr(result, "output", "") or ""

        if not success:
            return QualityEvaluation(overall_score=0.0, dimensions={"success": 0.0})

        # Start scoring successful results
        score = 0.0
        length = len(output)

        # Length signal
        if length < 20:
            length_score = 0.1
        elif length < 100:
            length_score = 0.3
        elif length < 500:
            length_score = 0.5
        else:
            length_score = 0.6

        # Refusal penalty
        refusal_score = 0.0
        if REFUSAL_PATTERNS.search(output):
            refusal_score = -0.3

        # Structure signal
        structure_hits = sum(1 for p in STRUCTURE_PATTERNS if p.search(output))
        structure_score = min(structure_hits * 0.15, 0.4)

        score = max(0.0, min(1.0, length_score + structure_score + refusal_score))

        return QualityEvaluation(
            overall_score=score,
            dimensions={
                "success": 1.0,
                "length": length_score,
                "structure": structure_score,
                "refusal": refusal_score,
            },
        )
