"""Tests for automated outcome detection."""

import tempfile
from pathlib import Path

import pytest
from cortex.v2.learning.outcomes import (
    OutcomeDetector,
    OutcomeSource,
    OutcomeType,
)


@pytest.fixture
def detector():
    """Create a temporary outcome detector."""
    with tempfile.TemporaryDirectory() as tmpdir:
        d = OutcomeDetector(data_dir=Path(tmpdir))
        yield d


class TestOutcomeDetector:
    """Test OutcomeDetector class."""

    def test_record_git_outcome(self, detector):
        """Test recording a git commit outcome."""
        outcome = detector.record_git_outcome(
            commit_hash="abc12345",
            message="Fix authentication bug in login flow",
            branch="main",
            files_changed=3,
            project="VortexV2",
        )

        assert outcome.id == "git_abc12345"
        assert outcome.source == OutcomeSource.GIT_COMMIT
        assert outcome.outcome_type == OutcomeType.SUCCESS  # "fix" detected
        assert outcome.project == "VortexV2"
        assert outcome.context["branch"] == "main"

    def test_analyze_success_patterns(self, detector):
        """Test detecting success patterns in commit messages."""
        # "fix" should indicate success
        outcome_type, confidence = detector._analyze_commit_message(
            "Fix memory leak in worker pool"
        )
        assert outcome_type == OutcomeType.SUCCESS
        assert confidence >= 0.5

        # "complete" should indicate success
        outcome_type, confidence = detector._analyze_commit_message(
            "Complete user authentication module"
        )
        assert outcome_type == OutcomeType.SUCCESS

        # "Closes #123" should indicate success
        outcome_type, confidence = detector._analyze_commit_message(
            "Add rate limiting, closes #123"
        )
        assert outcome_type == OutcomeType.SUCCESS

    def test_analyze_failure_patterns(self, detector):
        """Test detecting failure patterns in commit messages."""
        # "revert" should indicate failure
        outcome_type, confidence = detector._analyze_commit_message(
            "Revert 'Add new caching layer'"
        )
        assert outcome_type == OutcomeType.FAILURE

        # "broken" should indicate failure
        outcome_type, confidence = detector._analyze_commit_message(
            "Fix broken tests from previous commit"
        )
        assert outcome_type == OutcomeType.FAILURE

    def test_analyze_partial_patterns(self, detector):
        """Test detecting partial/WIP patterns."""
        # "WIP" should indicate in_progress
        outcome_type, confidence = detector._analyze_commit_message("WIP: Authentication refactor")
        assert outcome_type == OutcomeType.IN_PROGRESS

        # "part 1" should indicate in_progress
        outcome_type, confidence = detector._analyze_commit_message(
            "Database migration part 1 of 3"
        )
        assert outcome_type == OutcomeType.IN_PROGRESS

    def test_analyze_unknown_patterns(self, detector):
        """Test handling unknown patterns."""
        outcome_type, confidence = detector._analyze_commit_message("Update dependencies")
        assert outcome_type == OutcomeType.UNKNOWN
        assert confidence < 0.5

    def test_record_ci_outcome(self, detector):
        """Test recording CI/CD outcome."""
        outcome = detector.record_ci_outcome(
            repo="owner/VortexV2",
            workflow="tests",
            conclusion="success",
            commit="abc12345",
            branch="main",
            duration_ms=45000,
        )

        assert outcome.source == OutcomeSource.CI_PIPELINE
        assert outcome.outcome_type == OutcomeType.SUCCESS
        assert outcome.confidence >= 0.9
        assert outcome.project == "VortexV2"

    def test_record_test_outcome(self, detector):
        """Test recording test run outcome."""
        # All passing
        outcome = detector.record_test_outcome(
            project="VortexV2", passed=50, failed=0, skipped=2, duration_seconds=10.5
        )
        assert outcome.outcome_type == OutcomeType.SUCCESS

        # Some failures
        outcome = detector.record_test_outcome(project="VortexV2", passed=45, failed=5, skipped=0)
        assert outcome.outcome_type == OutcomeType.PARTIAL

        # More failures than passes
        outcome = detector.record_test_outcome(project="VortexV2", passed=10, failed=40, skipped=0)
        assert outcome.outcome_type == OutcomeType.FAILURE

    def test_get_recent_outcomes(self, detector):
        """Test querying recent outcomes."""
        detector.record_git_outcome(
            commit_hash="abc1",
            message="Fix bug",
            branch="main",
            files_changed=1,
            project="ProjectA",
        )
        detector.record_git_outcome(
            commit_hash="abc2",
            message="Add feature",
            branch="main",
            files_changed=1,
            project="ProjectB",
        )

        all_outcomes = detector.get_recent_outcomes()
        assert len(all_outcomes) == 2

        project_a = detector.get_recent_outcomes(project="ProjectA")
        assert len(project_a) == 1
        assert project_a[0].project == "ProjectA"

    def test_get_outcome_stats(self, detector):
        """Test outcome statistics."""
        detector.record_git_outcome("a", "Fix bug", "main", 1, "P")
        detector.record_git_outcome("b", "Add feature", "main", 1, "P")
        detector.record_git_outcome("c", "Revert bad change", "main", 1, "P")

        stats = detector.get_outcome_stats()
        assert stats["total"] == 3
        assert stats["by_source"]["git_commit"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
