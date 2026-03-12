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
