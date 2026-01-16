"""Auto-extract reusable skills from successful outcome sequences.

The key insight: sequences of 3+ related commits ending in SUCCESS
represent implicit skills that developers repeat but don't document.
This module detects and extracts those patterns.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from .outcomes import DetectedOutcome, OutcomeDetector, OutcomeSource, OutcomeType

if TYPE_CHECKING:
    from ..memory.store import TypedMemoryStore


@dataclass
class SkillSequence:
    """A sequence of related outcomes that may represent a skill."""

    outcomes: List[DetectedOutcome]
    start_time: datetime
    end_time: datetime
    project: str
    files_touched: Set[str] = field(default_factory=set)

    @property
    def duration_minutes(self) -> int:
        """Total duration of the sequence in minutes."""
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)

    @property
    def commit_messages(self) -> List[str]:
        """Get all commit messages from outcomes."""
        return [
            o.context.get("message", "")
            for o in self.outcomes
            if o.source == OutcomeSource.GIT_COMMIT
        ]

    @property
    def ends_with_success(self) -> bool:
        """Check if sequence ends with a SUCCESS outcome."""
        if not self.outcomes:
            return False
        return self.outcomes[-1].outcome_type == OutcomeType.SUCCESS


@dataclass
class ExtractedSkill:
    """A skill extracted from outcome sequences."""

    id: str
    title: str
    steps: List[str]
    source_commits: List[str]
    project: str
    confidence: float
    duration_minutes: int
    files_touched: List[str]
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "steps": self.steps,
            "source_commits": self.source_commits,
            "project": self.project,
            "confidence": self.confidence,
            "duration_minutes": self.duration_minutes,
            "files_touched": self.files_touched,
            "extracted_at": self.extracted_at.isoformat(),
        }


class SkillExtractor:
    """Extract skills from outcome sequences.

    Algorithm:
    1. Get outcomes from last N days, sort by timestamp
    2. Group by project
    3. Sliding window: commits within 30min of each other
    4. Check file overlap (>30% common files)
    5. Must end with SUCCESS
    6. Minimum 3 commits
    """

    # Minimum commits to form a skill
    MIN_COMMITS = 3

    # Maximum time gap between commits (minutes)
    MAX_TIME_GAP_MINUTES = 30

    # Minimum file overlap ratio to consider commits related
    MIN_FILE_OVERLAP = 0.3

    # Common verbs for title generation
    ACTION_VERBS = {
        "add": ["add", "implement", "create", "build", "introduce"],
        "fix": ["fix", "resolve", "repair", "correct", "patch"],
        "update": ["update", "modify", "change", "adjust", "refactor"],
        "remove": ["remove", "delete", "clean", "drop"],
        "improve": ["improve", "enhance", "optimize", "boost"],
    }

    def __init__(
        self,
        detector: Optional[OutcomeDetector] = None,
        store: Optional["TypedMemoryStore"] = None,
        data_dir: Optional[Path] = None,
    ):
        """Initialize skill extractor.

        Args:
            detector: OutcomeDetector to read outcomes from
            store: TypedMemoryStore to save skills to
            data_dir: Directory for data (used if detector not provided)
        """
        if data_dir is None:
            data_dir = Path.home() / ".claude" / "v2"

        self.detector = detector or OutcomeDetector(data_dir=data_dir)
        self.store = store

    def extract_from_recent(
        self, days: int = 7, project: Optional[str] = None
    ) -> List[ExtractedSkill]:
        """Extract skills from recent outcomes.

        Args:
            days: Look back this many days
            project: Filter by project (optional)

        Returns:
            List of extracted skills
        """
        # Get recent outcomes
        outcomes = self.detector.get_recent_outcomes(
            project=project, days=days, source=OutcomeSource.GIT_COMMIT
        )

        if not outcomes:
            return []

        # Group by project
        by_project: Dict[str, List[DetectedOutcome]] = {}
        for o in outcomes:
            by_project.setdefault(o.project, []).append(o)

        # Detect sequences and extract skills
        skills = []
        for proj, proj_outcomes in by_project.items():
            sequences = self.detect_sequences(proj_outcomes)
            for seq in sequences:
                skill = self.sequence_to_skill(seq)
                if skill:
                    skills.append(skill)

        # Merge similar skills
        skills = self.merge_similar(skills)

        return skills

    def detect_sequences(self, outcomes: List[DetectedOutcome]) -> List[SkillSequence]:
        """Detect sequences of related commits.

        Args:
            outcomes: List of outcomes (should be for single project)

        Returns:
            List of detected sequences
        """
        if len(outcomes) < self.MIN_COMMITS:
            return []

        # Sort by timestamp (oldest first)
        sorted_outcomes = sorted(outcomes, key=lambda o: o.timestamp)

        sequences = []
        current_sequence: List[DetectedOutcome] = []
        current_files: Set[str] = set()

        for outcome in sorted_outcomes:
            # Get files from this outcome
            outcome_files = self._get_files_from_outcome(outcome)

            # Check if this outcome continues the current sequence
            if current_sequence:
                last = current_sequence[-1]
                time_gap = (outcome.timestamp - last.timestamp).total_seconds() / 60

                # Check time gap
                if time_gap > self.MAX_TIME_GAP_MINUTES:
                    # Save current sequence if valid
                    if len(current_sequence) >= self.MIN_COMMITS:
                        seq = self._create_sequence(current_sequence, current_files)
                        if seq.ends_with_success:
                            sequences.append(seq)

                    # Start new sequence
                    current_sequence = [outcome]
                    current_files = outcome_files
                    continue

                # Check file overlap (if we have files)
                if current_files and outcome_files:
                    overlap = len(current_files & outcome_files) / len(
                        current_files | outcome_files
                    )
                    if overlap < self.MIN_FILE_OVERLAP:
                        # Low overlap - save current and start new
                        if len(current_sequence) >= self.MIN_COMMITS:
                            seq = self._create_sequence(current_sequence, current_files)
                            if seq.ends_with_success:
                                sequences.append(seq)

                        current_sequence = [outcome]
                        current_files = outcome_files
                        continue

                # Continue current sequence
                current_sequence.append(outcome)
                current_files |= outcome_files
            else:
                # Start new sequence
                current_sequence = [outcome]
                current_files = outcome_files

        # Don't forget last sequence
        if len(current_sequence) >= self.MIN_COMMITS:
            seq = self._create_sequence(current_sequence, current_files)
            if seq.ends_with_success:
                sequences.append(seq)

        return sequences

    def _get_files_from_outcome(self, outcome: DetectedOutcome) -> Set[str]:
        """Extract files touched from outcome context."""
        files = set()
        context = outcome.context or {}

        # From git commit
        if "files" in context:
            files.update(context["files"])

        # Files might be encoded in message sometimes
        message = context.get("message", "")
        file_pattern = r"[\w/]+\.(py|js|ts|tsx|jsx|go|rs|java|rb)"
        files.update(re.findall(file_pattern, message))

        return files

    def _create_sequence(self, outcomes: List[DetectedOutcome], files: Set[str]) -> SkillSequence:
        """Create a SkillSequence from outcomes."""
        return SkillSequence(
            outcomes=outcomes,
            start_time=outcomes[0].timestamp,
            end_time=outcomes[-1].timestamp,
            project=outcomes[0].project,
            files_touched=files,
        )

    def sequence_to_skill(self, seq: SkillSequence) -> Optional[ExtractedSkill]:
        """Convert a sequence to an extracted skill.

        Args:
            seq: Skill sequence to convert

        Returns:
            ExtractedSkill if conversion successful, None otherwise
        """
        if not seq.ends_with_success:
            return None

        if len(seq.outcomes) < self.MIN_COMMITS:
            return None

        # Generate title
        title = self.generate_title(seq.commit_messages)

        # Extract steps from commit messages
        steps = self._extract_steps(seq.commit_messages)

        # Get commit hashes
        commits = [o.context.get("commit_hash", o.id) for o in seq.outcomes]

        # Calculate confidence based on sequence quality
        confidence = self._calculate_confidence(seq)

        return ExtractedSkill(
            id=f"skill_{uuid.uuid4().hex[:8]}",
            title=title,
            steps=steps,
            source_commits=commits,
            project=seq.project,
            confidence=confidence,
            duration_minutes=seq.duration_minutes,
            files_touched=list(seq.files_touched),
        )

    def generate_title(self, messages: List[str]) -> str:
        """Generate a readable title from commit messages.

        Args:
            messages: List of commit messages

        Returns:
            Generated title
        """
        if not messages:
            return "Untitled Skill"

        # Find the primary action verb
        verb = self._extract_primary_verb(messages)

        # Find common nouns/topics
        topic = self._extract_topic(messages)

        # Combine
        if verb and topic:
            return f"{verb.title()} {topic}"
        elif topic:
            return f"Implement {topic}"
        else:
            # Fall back to first message, cleaned up
            first = messages[0]
            # Remove common prefixes
            first = re.sub(
                r"^(feat|fix|chore|docs|refactor|test|style)(\(.+?\))?:\s*",
                "",
                first,
                flags=re.I,
            )
            return first[:50] if len(first) > 50 else first

    def _extract_primary_verb(self, messages: List[str]) -> Optional[str]:
        """Extract the primary action verb from messages."""
        verb_counts: Dict[str, int] = {}

        for msg in messages:
            msg_lower = msg.lower()
            for canonical, variants in self.ACTION_VERBS.items():
                for variant in variants:
                    if re.search(rf"\b{variant}\b", msg_lower):
                        verb_counts[canonical] = verb_counts.get(canonical, 0) + 1
                        break

        if verb_counts:
            return max(verb_counts, key=verb_counts.get)
        return None

    def _extract_topic(self, messages: List[str]) -> Optional[str]:
        """Extract the main topic from messages."""
        # Common patterns to find the topic
        topic_patterns = [
            r"\b(api|auth|user|login|signup|dashboard|report|config|test|db|database|cache|queue|worker|payment|order|cart|search|notification|email|webhook|scheduler)\b",
            r"\b(\w+)(?:service|handler|controller|manager|provider|client|adapter)\b",
        ]

        topic_counts: Dict[str, int] = {}

        for msg in messages:
            msg_lower = msg.lower()
            for pattern in topic_patterns:
                matches = re.findall(pattern, msg_lower)
                for match in matches:
                    if len(match) > 2:  # Skip very short matches
                        topic_counts[match] = topic_counts.get(match, 0) + 1

        if topic_counts:
            return max(topic_counts, key=topic_counts.get)
        return None

    def _extract_steps(self, messages: List[str]) -> List[str]:
        """Extract steps from commit messages.

        Clean up messages to form readable steps.
        """
        steps = []
        for msg in messages:
            # Clean conventional commit prefixes
            clean = re.sub(
                r"^(feat|fix|chore|docs|refactor|test|style)(\(.+?\))?:\s*",
                "",
                msg,
                flags=re.I,
            )
            # Clean ticket references
            clean = re.sub(r"\s*#\d+\s*", "", clean)
            # Capitalize first letter
            if clean:
                clean = clean[0].upper() + clean[1:]
                steps.append(clean)

        return steps

    def _calculate_confidence(self, seq: SkillSequence) -> float:
        """Calculate confidence score for extracted skill.

        Higher confidence when:
        - More commits in sequence
        - Higher file overlap
        - Shorter time span
        - Clear success outcome
        """
        confidence = 0.5  # Base confidence

        # More commits = higher confidence (up to 0.2 bonus)
        commit_bonus = min(0.2, len(seq.outcomes) * 0.04)
        confidence += commit_bonus

        # Success ending = confidence boost
        if seq.ends_with_success:
            confidence += 0.15

        # Files touched suggests coherent work
        if seq.files_touched:
            confidence += 0.1

        # Reasonable duration (not too long, not instant)
        duration = seq.duration_minutes
        if 5 < duration < 120:  # 5 min to 2 hours
            confidence += 0.05

        return min(0.95, confidence)

    def merge_similar(self, skills: List[ExtractedSkill]) -> List[ExtractedSkill]:
        """Merge skills that appear to be duplicates.

        Args:
            skills: List of skills to deduplicate

        Returns:
            Deduplicated list
        """
        if len(skills) <= 1:
            return skills

        merged = []
        seen_titles: Set[str] = set()

        for skill in skills:
            # Normalize title for comparison
            normalized = skill.title.lower().strip()

            if normalized not in seen_titles:
                seen_titles.add(normalized)
                merged.append(skill)
            else:
                # Could merge steps here in future
                pass

        return merged

    def save_as_skill(self, extracted: ExtractedSkill) -> "Skill":
        """Save an extracted skill to the TypedMemoryStore.

        Args:
            extracted: The extracted skill to save

        Returns:
            The saved Skill object
        """
        from ..memory.types import Skill

        if not self.store:
            raise ValueError("TypedMemoryStore required to save skills")

        skill = Skill.create(
            title=extracted.title,
            steps=extracted.steps,
            estimated_time=f"{extracted.duration_minutes} minutes",
            difficulty=self._estimate_difficulty(extracted),
            projects=[extracted.project],
        )
        skill.confidence = extracted.confidence
        skill.tags = ["auto-extracted", "from-commits"]

        self.store.add(skill)
        return skill

    def _estimate_difficulty(self, extracted: ExtractedSkill) -> str:
        """Estimate skill difficulty based on extracted data."""
        # Simple heuristics
        if extracted.duration_minutes < 30 and len(extracted.steps) < 5:
            return "easy"
        elif extracted.duration_minutes > 120 or len(extracted.steps) > 10:
            return "hard"
        else:
            return "medium"
