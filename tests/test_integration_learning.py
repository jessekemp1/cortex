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
    assert callable(getattr(ExecutionHistoryAnalyzer, "get_success_rate", None))


def test_feedback_loop_import():
    """Test that feedback loop can be imported and has required methods."""
    assert FeedbackLoop is not None
    assert callable(getattr(FeedbackLoop, "get_learning_metrics", None))


def test_analyzer_initialization():
    """Test analyzer can be initialized and reports availability."""
    analyzer = ExecutionHistoryAnalyzer()
    available = analyzer.is_available()
    assert available is True or available is False  # must be actual bool, not truthy
    # Verify success rate returns a float in valid range
    rate = analyzer.get_success_rate("test_action")
    assert 0.0 <= rate <= 1.0


def test_feedback_loop_initialization():
    """Test feedback loop initializes and returns metrics with expected keys."""
    feedback = FeedbackLoop()
    metrics = feedback.get_learning_metrics()
    assert isinstance(metrics, dict)
    assert "available" in metrics
    # available must be a bool
    assert metrics["available"] is True or metrics["available"] is False


def test_get_learning_metrics():
    """Test learning metrics contain expected keys and valid values."""
    feedback = FeedbackLoop()
    metrics = feedback.get_learning_metrics()
    assert "available" in metrics
    # If available, should have additional keys
    if metrics["available"]:
        assert "total_outcomes" in metrics or "recommendations" in metrics
