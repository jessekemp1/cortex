#!/usr/bin/env python3
"""Tests for TaskRouter hypothesis scoring and confidence calibration."""

from intelligence.task_router import TaskRouter


def test_calibrate_confidence_dampens_unseen_state():
    router = TaskRouter()
    state = "other|other|morning|B"
    raw = 0.9
    calibrated = router.calibrate_confidence(raw, state)
    assert 0.05 <= calibrated <= 0.95
    assert calibrated < raw


def test_score_hypothesis_returns_q_score_and_calibrated_confidence():
    router = TaskRouter()
    scored = router.score_hypothesis(
        project="cortex",
        task_type="investigation",
        priority="A",
        context="investigate runtime latency regression",
    )
    assert "action" in scored
    assert "q_score" in scored
    assert "raw_confidence" in scored
    assert "confidence" in scored
    assert scored["confidence"] <= scored["raw_confidence"]

