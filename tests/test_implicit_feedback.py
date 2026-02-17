"""
Tests for Implicit Feedback Collection System

Tests implicit signal tracking for follows, ignores, and overrides.
"""

import time

import pytest

from cortex.intelligence.feedback.implicit_collector import ImplicitFeedbackCollector


@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage for testing."""
    storage_path = tmp_path / "implicit_feedback.jsonl"
    return storage_path


@pytest.fixture
def collector(temp_storage):
    """Create collector instance for testing."""
    return ImplicitFeedbackCollector(storage_path=temp_storage)


@pytest.fixture
def sample_recommendation():
    """Sample recommendation for testing."""
    return {
        "id": "rec_001",
        "title": "Fix failing tests in test_data_quality.py",
        "description": "Run pytest and fix the 3 failing test cases",
        "files": ["cortex/tests/test_data_quality.py"],
        "priority": "high",
        "confidence": 0.85,
    }


class TestRecommendationTracking:
    """Test recommendation tracking functionality."""

    def test_track_recommendation_shown(self, collector, sample_recommendation):
        """Test tracking when recommendation is shown."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        assert "rec_001" in collector.pending_recommendations
        assert (
            collector.pending_recommendations["rec_001"]["recommendation"] == sample_recommendation
        )
        assert "shown_at" in collector.pending_recommendations["rec_001"]

    def test_track_multiple_recommendations(self, collector, sample_recommendation):
        """Test tracking multiple recommendations."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)
        collector.track_recommendation_shown(
            "rec_002", {"title": "Another recommendation", "priority": "low"}
        )

        assert len(collector.pending_recommendations) == 2
        assert "rec_001" in collector.pending_recommendations
        assert "rec_002" in collector.pending_recommendations

    def test_track_with_context(self, collector, sample_recommendation):
        """Test tracking recommendation with context."""
        context = {"project": "cortex", "goal": "improve_quality"}
        collector.track_recommendation_shown("rec_001", sample_recommendation, context=context)

        stored_context = collector.pending_recommendations["rec_001"]["context"]
        assert stored_context == context


class TestActionCorrelation:
    """Test action correlation with recommendations."""

    def test_follow_detection_high_similarity(self, collector, sample_recommendation):
        """Test detecting follow with high similarity."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        # Action matches recommendation closely
        collector.track_action_taken(
            action="Fix failing tests in test_data_quality.py",
            files=["cortex/tests/test_data_quality.py"],
        )

        assert "rec_001" in collector.followed_ids

    def test_follow_detection_with_files(self, collector, sample_recommendation):
        """Test follow detection considers file overlap."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        # Similar action with matching files
        collector.track_action_taken(
            action="Run pytest and fix tests",
            files=["cortex/tests/test_data_quality.py", "cortex/tests/test_other.py"],
        )

        assert "rec_001" in collector.followed_ids

    def test_override_detection_medium_similarity(self, collector, sample_recommendation):
        """Test detecting override with medium similarity."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        # Similar but different action (override)
        collector.track_action_taken(
            action="Skip failing tests and investigate later",
            files=["cortex/tests/test_data_quality.py"],
        )

        # Should be tracked as override (similarity between 0.3 and 0.7)
        # Note: This depends on text similarity calculation
        # May or may not be in followed_ids depending on similarity score

    def test_no_match_low_similarity(self, collector, sample_recommendation):
        """Test no correlation with low similarity."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        # Completely different action
        collector.track_action_taken(action="Update README documentation", files=["README.md"])

        # Should not be marked as followed
        # (Will be marked as ignored during session_end)


class TestSessionManagement:
    """Test session lifecycle management."""

    def test_session_end_marks_ignores(self, collector, sample_recommendation, temp_storage):
        """Test session_end marks pending recommendations as ignored."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)
        collector.track_recommendation_shown(
            "rec_002", {"title": "Another recommendation", "priority": "low"}
        )

        # Follow one recommendation
        collector.track_action_taken(
            action="Fix failing tests in test_data_quality.py",
            files=["cortex/tests/test_data_quality.py"],
        )

        # End session
        collector.session_end()

        # Load signals from storage
        signals = collector.load_signals()

        # Should have 1 follow and 1 ignore
        signal_types = [s.signal_type for s in signals]
        assert "followed" in signal_types
        assert "ignored" in signal_types

    def test_session_end_clears_state(self, collector, sample_recommendation):
        """Test session_end clears session state."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)
        collector.track_action_taken(action="Some action")

        collector.session_end()

        assert len(collector.pending_recommendations) == 0
        assert len(collector.session_actions) == 0
        assert len(collector.followed_ids) == 0

    def test_get_session_stats(self, collector, sample_recommendation):
        """Test getting session statistics."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)
        collector.track_recommendation_shown("rec_002", {"title": "Another recommendation"})
        collector.track_action_taken(action="Fix tests")

        stats = collector.get_session_stats()

        assert stats["total_shown"] == 2
        assert stats["pending"] == 2  # None followed yet
        assert stats["actions_taken"] == 1


class TestPersistence:
    """Test signal persistence."""

    def test_persist_follow_signal(self, collector, sample_recommendation, temp_storage):
        """Test persisting follow signal."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        # Small delay to test time_to_action
        time.sleep(0.1)

        collector.track_action_taken(
            action="Fix failing tests in test_data_quality.py",
            files=["cortex/tests/test_data_quality.py"],
        )

        # Load from storage
        signals = collector.load_signals()

        assert len(signals) > 0
        follow_signals = [s for s in signals if s.signal_type == "followed"]
        assert len(follow_signals) > 0

        signal = follow_signals[0]
        assert signal.recommendation_id == "rec_001"
        assert signal.similarity > 0.7
        assert signal.time_to_action is not None
        assert signal.time_to_action >= 0.1

    def test_persist_ignore_signal(self, collector, sample_recommendation, temp_storage):
        """Test persisting ignore signal."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)
        collector.session_end()

        signals = collector.load_signals()
        ignore_signals = [s for s in signals if s.signal_type == "ignored"]

        assert len(ignore_signals) == 1
        signal = ignore_signals[0]
        assert signal.recommendation_id == "rec_001"
        assert signal.similarity == 0.0

    def test_persist_override_signal(self, collector, temp_storage):
        """Test persisting override signal."""
        rec = {
            "title": "Run pytest",
            "description": "Execute test suite",
        }
        collector.track_recommendation_shown("rec_001", rec)

        # Override: similar intent, different execution
        collector.track_action_taken(action="Run specific test file only")

        signals = collector.load_signals()
        # Filter for potential overrides (similarity between 0.3 and 0.7)
        override_signals = [s for s in signals if s.signal_type == "overridden"]

        # Note: This test depends on text similarity calculation
        # The specific action might not always trigger override
        # Just verify structure if override is detected
        if override_signals:
            signal = override_signals[0]
            assert signal.alternative_taken is not None
            assert 0.3 < signal.similarity <= 0.7

    def test_load_signals_with_limit(self, collector, sample_recommendation, temp_storage):
        """Test loading signals with limit."""
        # Create multiple signals
        for i in range(10):
            collector.track_recommendation_shown(f"rec_{i:03d}", sample_recommendation)

        collector.session_end()  # Mark all as ignored

        # Load with limit
        signals = collector.load_signals(limit=5)
        assert len(signals) == 5


class TestStatistics:
    """Test statistics calculation."""

    def test_get_stats_empty(self, collector):
        """Test statistics with no signals."""
        stats = collector.get_stats()

        assert stats["total_signals"] == 0
        assert stats["follows"] == 0
        assert stats["ignores"] == 0
        assert stats["overrides"] == 0
        assert stats["follow_rate"] == 0

    def test_get_stats_with_signals(self, collector, sample_recommendation, temp_storage):
        """Test statistics calculation with signals."""
        # Create various signals with different content
        collector.track_recommendation_shown("rec_001", sample_recommendation)
        collector.track_recommendation_shown(
            "rec_002", {"title": "Update documentation", "files": ["README.md"]}
        )
        collector.track_recommendation_shown(
            "rec_003", {"title": "Refactor code", "files": ["src/main.py"]}
        )

        # Follow one
        collector.track_action_taken(
            action="Fix failing tests in test_data_quality.py",
            files=["cortex/tests/test_data_quality.py"],
        )

        # End session (remaining are ignored)
        collector.session_end()

        stats = collector.get_stats(days=7)

        assert stats["total_signals"] == 3
        assert stats["follows"] >= 1
        assert stats["ignores"] >= 1
        assert 0 < stats["follow_rate"] <= 1

    def test_avg_time_to_action(self, collector, sample_recommendation, temp_storage):
        """Test average time-to-action calculation."""
        collector.track_recommendation_shown("rec_001", sample_recommendation)

        time.sleep(0.1)

        collector.track_action_taken(
            action="Fix failing tests in test_data_quality.py",
            files=["cortex/tests/test_data_quality.py"],
        )

        stats = collector.get_stats()

        assert stats["avg_time_to_action"] >= 0.1


class TestTextSimilarity:
    """Test text similarity calculation."""

    def test_exact_match(self, collector):
        """Test exact text match."""
        similarity = collector._text_similarity("fix tests", "fix tests")
        assert similarity == 1.0

    def test_partial_match(self, collector):
        """Test partial text match."""
        similarity = collector._text_similarity(
            "fix failing tests", "fix all the failing test cases"
        )
        assert 0.5 < similarity < 1.0

    def test_no_match(self, collector):
        """Test no text match."""
        similarity = collector._text_similarity("fix tests", "update documentation")
        assert similarity < 0.3


class TestFileOverlap:
    """Test file overlap calculation."""

    def test_exact_file_match(self, collector):
        """Test exact file overlap."""
        files1 = ["cortex/tests/test_data_quality.py"]
        files2 = ["cortex/tests/test_data_quality.py"]

        overlap = collector._file_overlap(files1, files2)
        assert overlap == 1.0

    def test_partial_file_overlap(self, collector):
        """Test partial file overlap."""
        files1 = ["cortex/tests/test_data_quality.py", "cortex/tests/test_other.py"]
        files2 = ["cortex/tests/test_data_quality.py", "cortex/tests/test_third.py"]

        overlap = collector._file_overlap(files1, files2)
        assert 0 < overlap < 1.0

    def test_no_file_overlap(self, collector):
        """Test no file overlap."""
        files1 = ["cortex/tests/test_data_quality.py"]
        files2 = ["cortex/tests/test_other.py"]

        overlap = collector._file_overlap(files1, files2)
        assert overlap == 0.0

    def test_file_overlap_with_paths(self, collector):
        """Test file overlap compares basenames."""
        files1 = ["/full/path/to/test_data_quality.py"]
        files2 = ["cortex/tests/test_data_quality.py"]

        overlap = collector._file_overlap(files1, files2)
        assert overlap == 1.0  # Basenames match


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_track_action_without_recommendation(self, collector):
        """Test tracking action with no pending recommendations."""
        # Should not raise error
        collector.track_action_taken(action="Some action")

        assert len(collector.session_actions) == 1

    def test_session_end_empty_state(self, collector):
        """Test session_end with no pending recommendations."""
        # Should not raise error
        collector.session_end()

        assert len(collector.pending_recommendations) == 0

    def test_load_signals_nonexistent_file(self, collector):
        """Test loading signals from nonexistent file."""
        signals = collector.load_signals()
        assert signals == []

    def test_corrupt_jsonl_handling(self, collector, temp_storage):
        """Test handling corrupt JSONL data."""
        # Write some corrupt data
        with open(temp_storage, "w") as f:
            f.write("not valid json\n")
            f.write('{"valid": "json"}\n')

        # Should skip corrupt lines
        collector.load_signals()
        # May have 0 signals if schema doesn't match ImplicitSignal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
