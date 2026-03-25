"""Tests for learning and adaptation"""

import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.feedback_loop import FeedbackLoop
from integration.history_analyzer import ExecutionHistoryAnalyzer


def test_history_analyzer_import():
    """Test that history analyzer can be imported and has required methods."""
    assert ExecutionHistoryAnalyzer is not None
    assert callable(getattr(ExecutionHistoryAnalyzer, "is_available", None))


def test_feedback_loop_import():
    """Test that feedback loop can be imported and has required methods."""
    assert FeedbackLoop is not None
    assert callable(getattr(FeedbackLoop, "get_learning_metrics", None))


def test_analyzer_initialization():
    """Test analyzer can be initialized and reports availability."""
    analyzer = ExecutionHistoryAnalyzer()
    available = analyzer.is_available()
    assert isinstance(available, bool)


def test_feedback_loop_initialization():
    """Test feedback loop initializes and returns metrics."""
    feedback = FeedbackLoop()
    metrics = feedback.get_learning_metrics()
    assert isinstance(metrics, dict)


def test_get_learning_metrics():
    """Test learning metrics contain expected keys."""
    feedback = FeedbackLoop()
    metrics = feedback.get_learning_metrics()
    assert isinstance(metrics, dict)
    assert "available" in metrics


# ---------------------------------------------------------------------------
# E2E Learning Loop Tests
# ---------------------------------------------------------------------------


def _make_outcome(
    outcome: str,
    followed: bool = True,
    recommendation_type: str = "goal_progress",
    confidence: float = 0.8,
    domain: str = "aidev",
):
    """Create a fake OutcomeEntry for testing without hitting disk."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from feedback import OutcomeEntry

    return OutcomeEntry(
        recommendation_id="test-rec-001",
        recommendation_title="Test recommendation",
        recommendation_type=recommendation_type,
        outcome=outcome,
        followed=followed,
        confidence=confidence,
        domain=domain,
        context={},
        notes="",
        priority="medium",
        timestamp="2026-03-23T00:00:00",
    )


def test_learning_loop_accuracy_calculates(monkeypatch):
    """calculate_recommendation_accuracy() returns > 0 when followed outcomes exist."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from learning import LearningSystem

    successes = [_make_outcome("success") for _ in range(6)]
    failures = [_make_outcome("failed") for _ in range(2)]
    outcomes = successes + failures

    ls = LearningSystem()
    monkeypatch.setattr(ls.feedback_logger, "load_outcomes", lambda: outcomes)

    accuracy = ls.calculate_recommendation_accuracy()
    assert accuracy > 0.0, "Accuracy should be > 0 with followed success outcomes"
    assert accuracy <= 1.0, "Accuracy cannot exceed 1.0"
    # 6 success / 8 followed = 0.75 unweighted
    assert accuracy == pytest.approx(0.75, abs=0.01)


def test_learning_loop_confidence_adjustment(monkeypatch):
    """adjust_confidence_based_on_history() modifies confidence when history exists."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from learning import LearningSystem

    # Seed 5 followed successes for goal_progress → high historical success
    outcomes = [_make_outcome("success", recommendation_type="goal_progress") for _ in range(5)]
    ls = LearningSystem()
    monkeypatch.setattr(ls.feedback_logger, "load_outcomes", lambda: outcomes)

    adjusted, explanation = ls.adjust_confidence_based_on_history("goal_progress", 0.5)

    assert isinstance(adjusted, float)
    assert 0.0 <= adjusted <= 1.0
    assert isinstance(explanation, str)
    assert len(explanation) > 0
    # With 5 successes, adjusted should be >= base (history pulls it up)
    assert adjusted >= 0.5, f"Confidence should increase with good history, got {adjusted}"


def test_learning_loop_no_history_uses_calibrated_weight(monkeypatch):
    """adjust_confidence_based_on_history() falls back to calibrated weight with no data."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from learning import LearningSystem

    ls = LearningSystem()
    monkeypatch.setattr(ls.feedback_logger, "load_outcomes", lambda: [])

    adjusted, explanation = ls.adjust_confidence_based_on_history("goal_progress", 0.7)

    assert isinstance(adjusted, float)
    assert 0.0 <= adjusted <= 1.0
    assert "calibrated weight" in explanation.lower() or "weight" in explanation.lower()


def test_learning_loop_domain_filter(monkeypatch):
    """calculate_recommendation_accuracy() domain filter scopes correctly."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from learning import LearningSystem

    aidev_outcomes = [_make_outcome("success", domain="aidev") for _ in range(4)]
    dbx_outcomes = [_make_outcome("failed", domain="databricks") for _ in range(4)]
    ls = LearningSystem()
    monkeypatch.setattr(ls.feedback_logger, "load_outcomes", lambda: aidev_outcomes + dbx_outcomes)

    aidev_acc = ls.calculate_recommendation_accuracy(domain="aidev")
    dbx_acc = ls.calculate_recommendation_accuracy(domain="databricks")

    assert aidev_acc == pytest.approx(1.0, abs=0.01), "All aidev outcomes are success"
    assert dbx_acc == pytest.approx(0.0, abs=0.01), "All databricks outcomes are failed"


import pytest
