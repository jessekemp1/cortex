#!/usr/bin/env python3
"""
Tests for Cortex Learning System
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from feedback import FeedbackLogger
from learning import LearningSystem


@pytest.fixture
def temp_outcomes_file():
    """Create a temporary outcomes file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    yield temp_path
    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def learning_system(feedback_logger):
    """Create a learning system that uses the same temp files as feedback_logger."""
    # Create a new LearningSystem that shares the same FeedbackLogger
    learning_sys = LearningSystem(outcomes_file=feedback_logger.outcomes_file)
    # Replace its feedback_logger with our shared one
    learning_sys.feedback_logger = feedback_logger
    return learning_sys


@pytest.fixture
def feedback_logger(temp_outcomes_file):
    """Create a feedback logger with temp file."""
    # Also need a temp feedback.json file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        temp_feedback = Path(f.name)
    logger = FeedbackLogger(log_file=temp_feedback, outcomes_file=temp_outcomes_file)
    yield logger
    # Cleanup
    temp_feedback.unlink(missing_ok=True)


def test_empty_outcomes(learning_system):
    """Test metrics with no outcomes."""
    accuracy = learning_system.calculate_recommendation_accuracy()
    assert accuracy == 0.0

    patterns = learning_system.get_outcome_patterns()
    assert patterns == {}

    calibration = learning_system.get_confidence_calibration()
    assert calibration == {}


def test_recommendation_accuracy(feedback_logger, learning_system):
    """Test recommendation accuracy calculation."""
    # Add some outcomes
    feedback_logger.log_outcome(
        recommendation_id="rec1",
        recommendation_title="Fix blocker",
        recommendation_type="blocker_resolution",
        priority="A",
        confidence=0.8,
        followed=True,
        outcome="success",
    )

    feedback_logger.log_outcome(
        recommendation_id="rec2",
        recommendation_title="Update docs",
        recommendation_type="goal_progress",
        priority="B",
        confidence=0.7,
        followed=True,
        outcome="partial",
    )

    feedback_logger.log_outcome(
        recommendation_id="rec3",
        recommendation_title="Refactor code",
        recommendation_type="optimization",
        priority="C",
        confidence=0.6,
        followed=True,
        outcome="failed",
    )

    # 1 success + 0.5 partial = 1.5 / 3 = 0.5
    accuracy = learning_system.calculate_recommendation_accuracy()
    assert accuracy == 0.5


def test_outcome_patterns(feedback_logger, learning_system):
    """Test outcome pattern analysis."""
    # Add outcomes for different types
    for i in range(3):
        feedback_logger.log_outcome(
            recommendation_id=f"rec{i}",
            recommendation_title="Blocker fix",
            recommendation_type="blocker_resolution",
            priority="A",
            confidence=0.8,
            followed=True,
            outcome="success",
        )

    feedback_logger.log_outcome(
        recommendation_id="rec4",
        recommendation_title="Goal work",
        recommendation_type="goal_progress",
        priority="B",
        confidence=0.7,
        followed=True,
        outcome="partial",
    )

    patterns = learning_system.get_outcome_patterns()

    # Check blocker_resolution pattern
    assert "blocker_resolution" in patterns
    blocker_pattern = patterns["blocker_resolution"]
    assert blocker_pattern["total"] == 3
    assert blocker_pattern["followed"] == 3
    assert blocker_pattern["success_rate"] == 1.0  # All successful
    assert (
        abs(blocker_pattern["avg_confidence"] - 0.8) < 0.001
    )  # Allow floating point variance

    # Check goal_progress pattern
    assert "goal_progress" in patterns
    goal_pattern = patterns["goal_progress"]
    assert goal_pattern["total"] == 1
    assert goal_pattern["followed"] == 1
    assert goal_pattern["success_rate"] == 0.5  # Partial = 0.5


def test_confidence_calibration(feedback_logger, learning_system):
    """Test confidence calibration analysis."""
    # High confidence, successful
    feedback_logger.log_outcome(
        recommendation_id="rec1",
        recommendation_title="High conf success",
        recommendation_type="blocker_resolution",
        priority="A",
        confidence=0.9,
        followed=True,
        outcome="success",
    )

    # Medium confidence, partial
    feedback_logger.log_outcome(
        recommendation_id="rec2",
        recommendation_title="Med conf partial",
        recommendation_type="goal_progress",
        priority="B",
        confidence=0.6,
        followed=True,
        outcome="partial",
    )

    # Low confidence, failed
    feedback_logger.log_outcome(
        recommendation_id="rec3",
        recommendation_title="Low conf fail",
        recommendation_type="optimization",
        priority="C",
        confidence=0.3,
        followed=True,
        outcome="failed",
    )

    calibration = learning_system.get_confidence_calibration()

    assert "high (0.8-1.0)" in calibration
    assert calibration["high (0.8-1.0)"] == 1.0  # 100% success

    assert "medium (0.5-0.8)" in calibration
    assert calibration["medium (0.5-0.8)"] == 0.5  # Partial = 0.5

    assert "low (0.0-0.5)" in calibration
    assert calibration["low (0.0-0.5)"] == 0.0  # Failed


def test_adjust_confidence_no_history(learning_system):
    """Test confidence adjustment with no historical data."""
    adjusted, explanation = learning_system.adjust_confidence_based_on_history(
        recommendation_type="unknown_type", base_confidence=0.7
    )

    assert adjusted == 0.7  # No change
    assert "No historical data" in explanation


def test_adjust_confidence_limited_data(feedback_logger, learning_system):
    """Test confidence adjustment with limited data."""
    # Add only 2 outcomes (threshold is 3)
    for i in range(2):
        feedback_logger.log_outcome(
            recommendation_id=f"rec{i}",
            recommendation_title="Test",
            recommendation_type="test_type",
            priority="A",
            confidence=0.8,
            followed=True,
            outcome="success",
        )

    adjusted, explanation = learning_system.adjust_confidence_based_on_history(
        recommendation_type="test_type", base_confidence=0.7
    )

    assert adjusted == 0.7  # No change with limited data
    assert "Limited data (2 outcomes)" in explanation


def test_adjust_confidence_with_history(feedback_logger, learning_system):
    """Test confidence adjustment with sufficient historical data."""
    # Add 5 outcomes with 80% success rate
    for i in range(4):
        feedback_logger.log_outcome(
            recommendation_id=f"rec{i}",
            recommendation_title="Test",
            recommendation_type="test_type",
            priority="A",
            confidence=0.8,
            followed=True,
            outcome="success",
        )

    feedback_logger.log_outcome(
        recommendation_id="rec5",
        recommendation_title="Test",
        recommendation_type="test_type",
        priority="A",
        confidence=0.8,
        followed=True,
        outcome="failed",
    )

    # Base confidence 0.6, historical success 0.8
    # Weight = min(0.4, 5/20) = 0.25
    # Adjusted = 0.6 * 0.75 + 0.8 * 0.25 = 0.45 + 0.2 = 0.65
    adjusted, explanation = learning_system.adjust_confidence_based_on_history(
        recommendation_type="test_type", base_confidence=0.6
    )

    assert 0.64 < adjusted < 0.66  # Allow small floating point variance
    assert "5 previous outcomes" in explanation
    assert "80%" in explanation


def test_get_learning_metrics_comprehensive(feedback_logger, learning_system):
    """Test comprehensive learning metrics."""
    # Add various outcomes
    feedback_logger.log_outcome(
        recommendation_id="rec1",
        recommendation_title="Success",
        recommendation_type="blocker_resolution",
        priority="A",
        confidence=0.9,
        followed=True,
        outcome="success",
    )

    feedback_logger.log_outcome(
        recommendation_id="rec2",
        recommendation_title="Partial",
        recommendation_type="goal_progress",
        priority="B",
        confidence=0.7,
        followed=True,
        outcome="partial",
    )

    feedback_logger.log_outcome(
        recommendation_id="rec3",
        recommendation_title="Failed",
        recommendation_type="optimization",
        priority="C",
        confidence=0.5,
        followed=True,
        outcome="failed",
    )

    feedback_logger.log_outcome(
        recommendation_id="rec4",
        recommendation_title="Not followed",
        recommendation_type="goal_progress",
        priority="B",
        confidence=0.6,
        followed=False,
        outcome="unknown",
    )

    metrics = learning_system.get_learning_metrics()

    assert metrics.total_outcomes == 4
    assert metrics.followed_count == 3
    assert metrics.success_rate == 1 / 3  # 1 success out of 3 followed
    assert metrics.partial_rate == 1 / 3  # 1 partial out of 3 followed
    assert metrics.failed_rate == 1 / 3  # 1 failed out of 3 followed
    assert metrics.recommendation_accuracy == 0.5  # (1 + 0.5) / 3

    assert len(metrics.confidence_calibration) == 3
    assert len(metrics.outcome_patterns) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
