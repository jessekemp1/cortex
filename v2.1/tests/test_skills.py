"""Tests for auto skill extraction."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from cortex.v2.learning.skills import (
    SkillExtractor,
    SkillSequence,
    ExtractedSkill
)
from cortex.v2.learning.outcomes import (
    DetectedOutcome,
    OutcomeDetector,
    OutcomeType,
    OutcomeSource
)


@pytest.fixture
def extractor():
    """Create a SkillExtractor instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        detector = OutcomeDetector(data_dir=Path(tmpdir))
        yield SkillExtractor(detector=detector)


@pytest.fixture
def sample_sequence():
    """Create a sample skill sequence with successful ending."""
    now = datetime.utcnow()
    outcomes = [
        DetectedOutcome(
            id="git_abc123",
            source=OutcomeSource.GIT_COMMIT,
            outcome_type=OutcomeType.IN_PROGRESS,
            confidence=0.7,
            project="TestProject",
            timestamp=now - timedelta(minutes=60),
            context={"message": "feat: Add user authentication", "commit_hash": "abc123"}
        ),
        DetectedOutcome(
            id="git_def456",
            source=OutcomeSource.GIT_COMMIT,
            outcome_type=OutcomeType.IN_PROGRESS,
            confidence=0.7,
            project="TestProject",
            timestamp=now - timedelta(minutes=45),
            context={"message": "feat: Add login form", "commit_hash": "def456"}
        ),
        DetectedOutcome(
            id="git_ghi789",
            source=OutcomeSource.GIT_COMMIT,
            outcome_type=OutcomeType.IN_PROGRESS,
            confidence=0.7,
            project="TestProject",
            timestamp=now - timedelta(minutes=30),
            context={"message": "feat: Add JWT token validation", "commit_hash": "ghi789"}
        ),
        DetectedOutcome(
            id="git_jkl012",
            source=OutcomeSource.GIT_COMMIT,
            outcome_type=OutcomeType.SUCCESS,
            confidence=0.9,
            project="TestProject",
            timestamp=now - timedelta(minutes=15),
            context={"message": "feat: Complete auth implementation", "commit_hash": "jkl012"}
        ),
    ]
    return SkillSequence(
        outcomes=outcomes,
        start_time=outcomes[0].timestamp,
        end_time=outcomes[-1].timestamp,
        project="TestProject",
        files_touched={"auth.py", "login.py", "jwt.py"}
    )


class TestSkillSequence:
    """Test SkillSequence dataclass."""

    def test_duration_minutes(self, sample_sequence):
        """Duration should be calculated correctly."""
        # Sequence spans 45 minutes (60 - 15)
        assert sample_sequence.duration_minutes == 45

    def test_commit_messages(self, sample_sequence):
        """Should extract commit messages."""
        messages = sample_sequence.commit_messages
        assert len(messages) == 4
        assert "Add user authentication" in messages[0]

    def test_ends_with_success(self, sample_sequence):
        """Should detect SUCCESS ending."""
        assert sample_sequence.ends_with_success is True

    def test_ends_with_failure(self):
        """Should detect non-SUCCESS ending."""
        outcomes = [
            DetectedOutcome(
                id="git_1",
                source=OutcomeSource.GIT_COMMIT,
                outcome_type=OutcomeType.FAILURE,
                confidence=0.7,
                project="Test",
                context={"message": "revert: Broken"}
            )
        ]
        seq = SkillSequence(
            outcomes=outcomes,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            project="Test"
        )
        assert seq.ends_with_success is False


class TestSkillExtractor:
    """Test SkillExtractor class."""

    def test_detect_sequences_min_commits(self, extractor):
        """Should require minimum 3 commits."""
        now = datetime.utcnow()
        outcomes = [
            DetectedOutcome(
                id="git_1",
                source=OutcomeSource.GIT_COMMIT,
                outcome_type=OutcomeType.SUCCESS,
                confidence=0.9,
                project="Test",
                timestamp=now,
                context={"message": "One commit"}
            ),
            DetectedOutcome(
                id="git_2",
                source=OutcomeSource.GIT_COMMIT,
                outcome_type=OutcomeType.SUCCESS,
                confidence=0.9,
                project="Test",
                timestamp=now + timedelta(minutes=5),
                context={"message": "Two commits"}
            ),
        ]
        sequences = extractor.detect_sequences(outcomes)
        assert len(sequences) == 0  # Not enough commits

    def test_detect_sequences_time_gap(self, extractor):
        """Should break on time gap > 30 minutes."""
        now = datetime.utcnow()
        outcomes = [
            DetectedOutcome(
                id=f"git_{i}",
                source=OutcomeSource.GIT_COMMIT,
                outcome_type=OutcomeType.SUCCESS if i == 2 else OutcomeType.IN_PROGRESS,
                confidence=0.9,
                project="Test",
                timestamp=now + timedelta(minutes=i * 10),
                context={"message": f"Commit {i}"}
            )
            for i in range(3)
        ]
        # Add a commit after a big gap
        outcomes.append(DetectedOutcome(
            id="git_far",
            source=OutcomeSource.GIT_COMMIT,
            outcome_type=OutcomeType.SUCCESS,
            confidence=0.9,
            project="Test",
            timestamp=now + timedelta(minutes=90),
            context={"message": "Far away commit"}
        ))

        sequences = extractor.detect_sequences(outcomes)
        # Should only detect one sequence (first 3)
        assert len(sequences) == 1
        assert len(sequences[0].outcomes) == 3

    def test_detect_sequences_success_required(self, extractor):
        """Should only include sequences ending with SUCCESS."""
        now = datetime.utcnow()
        outcomes = [
            DetectedOutcome(
                id=f"git_{i}",
                source=OutcomeSource.GIT_COMMIT,
                outcome_type=OutcomeType.FAILURE if i == 2 else OutcomeType.IN_PROGRESS,
                confidence=0.7,
                project="Test",
                timestamp=now + timedelta(minutes=i * 5),
                context={"message": f"Commit {i}"}
            )
            for i in range(3)
        ]
        sequences = extractor.detect_sequences(outcomes)
        assert len(sequences) == 0  # Ends with FAILURE, not included

    def test_sequence_to_skill(self, extractor, sample_sequence):
        """Should convert sequence to skill."""
        skill = extractor.sequence_to_skill(sample_sequence)

        assert skill is not None
        assert skill.project == "TestProject"
        assert len(skill.steps) == 4
        assert skill.duration_minutes == 45
        assert skill.confidence >= 0.5

    def test_sequence_to_skill_requires_success(self, extractor):
        """Should return None for non-successful sequences."""
        outcomes = [
            DetectedOutcome(
                id=f"git_{i}",
                source=OutcomeSource.GIT_COMMIT,
                outcome_type=OutcomeType.FAILURE,
                confidence=0.7,
                project="Test",
                timestamp=datetime.utcnow() + timedelta(minutes=i * 5),
                context={"message": f"Commit {i}"}
            )
            for i in range(3)
        ]
        seq = SkillSequence(
            outcomes=outcomes,
            start_time=outcomes[0].timestamp,
            end_time=outcomes[-1].timestamp,
            project="Test"
        )
        skill = extractor.sequence_to_skill(seq)
        assert skill is None

    def test_generate_title_with_verb_and_topic(self, extractor):
        """Should generate title from verb and topic."""
        messages = [
            "Add user authentication",
            "Add login endpoint",
            "Add auth middleware",
        ]
        title = extractor.generate_title(messages)
        assert "add" in title.lower() or "auth" in title.lower()

    def test_generate_title_conventional_commits(self, extractor):
        """Should handle conventional commit prefixes."""
        messages = [
            "feat(auth): implement JWT validation",
            "feat(auth): add refresh tokens",
            "fix(auth): correct token expiry",
        ]
        title = extractor.generate_title(messages)
        # Should extract topic from the messages
        assert title  # Has a title
        assert "feat(" not in title.lower()  # Prefix removed

    def test_generate_title_fallback(self, extractor):
        """Should fall back to first message if no patterns match."""
        messages = [
            "Random message with no clear topic",
        ]
        title = extractor.generate_title(messages)
        assert title == "Random message with no clear topic"

    def test_merge_similar_deduplicates(self, extractor):
        """Should merge skills with similar titles."""
        skills = [
            ExtractedSkill(
                id="skill_1",
                title="Add Authentication",
                steps=["Step 1"],
                source_commits=["abc"],
                project="Test",
                confidence=0.8,
                duration_minutes=30,
                files_touched=["auth.py"]
            ),
            ExtractedSkill(
                id="skill_2",
                title="Add Authentication",  # Same title
                steps=["Step 2"],
                source_commits=["def"],
                project="Test",
                confidence=0.7,
                duration_minutes=45,
                files_touched=["auth2.py"]
            ),
        ]
        merged = extractor.merge_similar(skills)
        assert len(merged) == 1

    def test_extract_steps_cleans_messages(self, extractor):
        """Should clean commit message prefixes."""
        messages = [
            "feat(api): Add new endpoint #123",
            "fix: Correct validation",
            "chore: Update dependencies",
        ]
        # Access private method for testing
        steps = extractor._extract_steps(messages)

        assert len(steps) == 3
        assert not any("feat(" in s.lower() for s in steps)
        assert not any("#123" in s for s in steps)
        # First letter should be capitalized
        assert steps[0][0].isupper()

    def test_calculate_confidence(self, extractor, sample_sequence):
        """Confidence should increase with more commits."""
        # More commits = higher confidence
        confidence = extractor._calculate_confidence(sample_sequence)
        assert 0.5 < confidence < 1.0

        # Create a smaller sequence
        small_seq = SkillSequence(
            outcomes=sample_sequence.outcomes[:3],
            start_time=sample_sequence.outcomes[0].timestamp,
            end_time=sample_sequence.outcomes[2].timestamp,
            project="Test"
        )
        small_conf = extractor._calculate_confidence(small_seq)

        # Larger sequence should have equal or higher confidence
        assert confidence >= small_conf


class TestExtractedSkill:
    """Test ExtractedSkill dataclass."""

    def test_to_dict(self):
        """Should serialize to dictionary."""
        skill = ExtractedSkill(
            id="skill_abc",
            title="Add Auth",
            steps=["Step 1", "Step 2"],
            source_commits=["abc123"],
            project="Test",
            confidence=0.8,
            duration_minutes=30,
            files_touched=["auth.py"]
        )
        d = skill.to_dict()

        assert d["id"] == "skill_abc"
        assert d["title"] == "Add Auth"
        assert len(d["steps"]) == 2
        assert d["confidence"] == 0.8


class TestSkillExtractionE2E:
    """End-to-end skill extraction tests."""

    def test_full_extraction_flow(self):
        """Test complete flow from outcomes to extracted skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = OutcomeDetector(data_dir=Path(tmpdir))
            extractor = SkillExtractor(detector=detector)

            now = datetime.utcnow()

            # Record a sequence of commits
            for i, msg in enumerate([
                "feat: Start API implementation",
                "feat: Add endpoints",
                "feat: Add validation",
                "feat: Complete API with tests"
            ]):
                detector.record_git_outcome(
                    commit_hash=f"hash{i}",
                    message=msg,
                    branch="main",
                    files_changed=3,
                    project="APIProject"
                )
                # Manually set timestamp for testing
                detector._outcomes[-1].timestamp = now + timedelta(minutes=i * 10)

            # Make last one SUCCESS
            detector._outcomes[-1].outcome_type = OutcomeType.SUCCESS

            # Extract skills
            skills = extractor.extract_from_recent(days=1, project="APIProject")

            # Should extract at least one skill
            assert len(skills) >= 1
            skill = skills[0]
            assert skill.project == "APIProject"
            assert len(skill.steps) >= 3
            print(f"Extracted skill: {skill.title}")
            print(f"Steps: {skill.steps}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
