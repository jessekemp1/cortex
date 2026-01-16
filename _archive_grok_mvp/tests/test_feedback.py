#!/usr/bin/env python3
"""
Tests for Feedback Logger (Golden Spec: Phase 7 Verification)
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from feedback import FeedbackLogger


def test_feedback_logger_initialization():
    """Test feedback logger can be initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "feedback.json"
        logger = FeedbackLogger(log_file=log_file)
        assert logger.log_file == log_file
        assert log_file.exists()


def test_log_feedback():
    """Test logging feedback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "feedback.json"
        logger = FeedbackLogger(log_file=log_file)

        logger.log_feedback(action_title="Test Action", useful=True, notes="This was helpful")

        # Verify entry was written
        assert log_file.exists()
        with open(log_file, "r") as f:
            entries = json.load(f)
            assert len(entries) == 1
            assert entries[0]["action_title"] == "Test Action"
            assert entries[0]["useful"]
            assert entries[0]["notes"] == "This was helpful"


def test_log_quick():
    """Test quick log entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "feedback.json"
        logger = FeedbackLogger(log_file=log_file)

        logger.log_quick("Test note")

        with open(log_file, "r") as f:
            entries = json.load(f)
            assert len(entries) == 1
            assert entries[0]["action_title"] == "Note"
            assert entries[0]["notes"] == "Test note"


def test_get_stats():
    """Test feedback statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "feedback.json"
        logger = FeedbackLogger(log_file=log_file)

        # Add some entries
        logger.log_feedback("Action 1", useful=True)
        logger.log_feedback("Action 2", useful=True)
        logger.log_feedback("Action 3", useful=False)

        stats = logger.get_stats()

        assert stats["total_entries"] == 3
        assert stats["useful_count"] == 2
        assert stats["not_useful_count"] == 1
        assert stats["useful_rate"] == pytest.approx(2 / 3, abs=0.01)


def test_get_recent():
    """Test getting recent entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "feedback.json"
        logger = FeedbackLogger(log_file=log_file)

        # Add multiple entries
        for i in range(5):
            logger.log_feedback(f"Action {i}", useful=True)

        recent = logger.get_recent(limit=3)
        assert len(recent) == 3
        assert recent[-1]["action_title"] == "Action 4"  # Most recent
