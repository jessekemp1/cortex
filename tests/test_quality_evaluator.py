"""Tests for the quality evaluator (Phase 2).

Tests:
  - Failed dispatch → 0.0
  - Empty output → low score
  - Refusal signals → low score
  - Structured output → high score
  - Task-type-specific checks (code needs code blocks)
  - Dimension scores returned correctly
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from cortex.supervisor.quality_evaluator import QualityEvaluation, QualityEvaluator


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class MockDispatchResult:
    success: bool
    output: str
    task_type: str = "research"
    error: Optional[str] = None


@dataclass
class MockWorkItem:
    task_type: str = "research"
    description: str = "Analyze the authentication patterns in the codebase"


@pytest.fixture
def evaluator() -> QualityEvaluator:
    return QualityEvaluator(use_ai_judge=False)


# ---------------------------------------------------------------------------
# Tests: Overall scoring
# ---------------------------------------------------------------------------


class TestHeuristicScoring:
    def test_failed_dispatch_scores_zero(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(success=False, output="", error="timeout")
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert eval_.overall_score == 0.0
        assert eval_.evaluator == "heuristic"

    def test_empty_output_scores_very_low(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(success=True, output="")
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert eval_.overall_score <= 0.15

    def test_short_output_scores_low(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(success=True, output="OK")
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert eval_.overall_score < 0.4

    def test_refusal_scores_low(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(
            success=True,
            output="I cannot complete this task. I need more context to proceed.",
        )
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert eval_.overall_score < 0.4

    def test_structured_output_scores_high(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(
            success=True,
            output=(
                "# Authentication Analysis\n\n"
                "## Findings\n\n"
                "The codebase uses JWT tokens for authentication.\n\n"
                "```python\ndef verify_token(token):\n    return jwt.decode(token)\n```\n\n"
                "## Recommendations\n\n"
                "1. Add token rotation\n2. Implement refresh tokens\n\n"
                "In summary, the authentication patterns are solid but need refresh token support."
            ),
        )
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert eval_.overall_score >= 0.6

    def test_moderate_output(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(
            success=True,
            output=(
                "The authentication system uses session-based tokens stored in cookies. "
                "The main middleware is in auth.py. It validates tokens on each request. "
                "The token expiry is set to 24 hours. No refresh mechanism exists."
            ),
        )
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert 0.3 <= eval_.overall_score <= 0.8


# ---------------------------------------------------------------------------
# Tests: Dimension scores
# ---------------------------------------------------------------------------


class TestDimensionScores:
    def test_dimensions_present(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(success=True, output="Some output text here")
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        # Heuristic dimensions: success, length, structure, refusal
        assert "success" in eval_.dimensions
        assert "length" in eval_.dimensions
        assert "structure" in eval_.dimensions
        assert "refusal" in eval_.dimensions

    def test_all_dimensions_in_range(self, evaluator: QualityEvaluator) -> None:
        result = MockDispatchResult(success=True, output="Test output with some content")
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        for dim, score in eval_.dimensions.items():
            assert 0.0 <= score <= 1.0, f"{dim} score {score} out of range"


# ---------------------------------------------------------------------------
# Tests: Task-type specific
# ---------------------------------------------------------------------------


class TestTaskTypeSpecific:
    def test_code_task_without_code_blocks_penalized(self, evaluator: QualityEvaluator) -> None:
        """Implementation tasks should have code blocks."""
        work_item = MockWorkItem(task_type="implement")
        result = MockDispatchResult(
            success=True,
            output="You should add a function that validates the input and returns the result.",
            task_type="implement",
        )
        eval_ = evaluator.evaluate_heuristic(work_item, result)

        # Same content but WITH code blocks should score higher
        result_with_code = MockDispatchResult(
            success=True,
            output=(
                "Here's the implementation:\n\n"
                "```python\ndef validate(input):\n    return True\n```\n\n"
                "This validates the input and returns the result."
            ),
            task_type="implement",
        )
        eval_with_code = evaluator.evaluate_heuristic(work_item, result_with_code)
        assert eval_with_code.overall_score > eval_.overall_score


# ---------------------------------------------------------------------------
# Tests: QualityEvaluation dataclass
# ---------------------------------------------------------------------------


class TestQualityEvaluation:
    def test_default_values(self) -> None:
        eval_ = QualityEvaluation(overall_score=0.5)
        assert eval_.dimensions == {}
        assert eval_.rationale == ""
        assert eval_.evaluator == "heuristic"

    def test_score_clamped(self, evaluator: QualityEvaluator) -> None:
        """Scores should always be in [0.0, 1.0]."""
        result = MockDispatchResult(success=True, output="x" * 5000)
        eval_ = evaluator.evaluate_heuristic(MockWorkItem(), result)
        assert 0.0 <= eval_.overall_score <= 1.0


# ---------------------------------------------------------------------------
# Tests: AI judge
# ---------------------------------------------------------------------------


class TestAIJudge:
    def test_ai_judge_disabled_returns_none(self) -> None:
        import asyncio

        evaluator = QualityEvaluator(use_ai_judge=False)
        result = MockDispatchResult(success=True, output="Good output here.")
        eval_ = asyncio.run(evaluator.evaluate_ai_judge(MockWorkItem(), result))
        assert eval_ is None

    def test_ai_judge_enabled_handles_import_error(self) -> None:
        """AI judge should gracefully handle missing QualityJudge."""
        import asyncio
        from unittest.mock import patch

        evaluator = QualityEvaluator(use_ai_judge=True)
        result = MockDispatchResult(success=True, output="Good output here.")

        # Even with use_ai_judge=True, if the import fails it returns None
        with patch.dict("sys.modules", {"intelligence.evaluation.quality_judge": None}):
            eval_ = asyncio.run(evaluator.evaluate_ai_judge(MockWorkItem(), result))
            # May return None (import failure) or a result — both are acceptable
            if eval_ is not None:
                assert isinstance(eval_, QualityEvaluation)
                assert eval_.evaluator == "ai_judge"

    def test_ai_judge_skips_failed_results(self) -> None:
        import asyncio

        evaluator = QualityEvaluator(use_ai_judge=True)
        result = MockDispatchResult(success=False, output="Error")
        eval_ = asyncio.run(evaluator.evaluate_ai_judge(MockWorkItem(), result))
        assert eval_ is None
