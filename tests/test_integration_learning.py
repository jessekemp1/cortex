"""Tests for learning and adaptation"""

import sys
from pathlib import Path


# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.feedback_loop import FeedbackLoop
from integration.history_analyzer import ExecutionHistoryAnalyzer


def test_history_analyzer_import():
    """Test that history analyzer can be imported"""
    assert ExecutionHistoryAnalyzer is not None


def test_feedback_loop_import():
    """Test that feedback loop can be imported"""
    assert FeedbackLoop is not None


def test_analyzer_initialization():
    """Test analyzer can be initialized"""
    analyzer = ExecutionHistoryAnalyzer()
    assert analyzer is not None
    # Should handle missing history gracefully
    assert isinstance(analyzer.is_available(), bool)


def test_feedback_loop_initialization():
    """Test feedback loop can be initialized"""
    feedback = FeedbackLoop()
    assert feedback is not None


def test_get_learning_metrics():
    """Test learning metrics can be retrieved"""
    feedback = FeedbackLoop()
    metrics = feedback.get_learning_metrics()
    assert isinstance(metrics, dict)
    assert "available" in metrics
