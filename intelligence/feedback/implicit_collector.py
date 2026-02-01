"""
Implicit Feedback Collector - Automatic tracking of user behavior

Collects implicit feedback signals from user interactions:
- Follows: User executes recommended action
- Ignores: User sees recommendation but doesn't act
- Overrides: User modifies recommendation before executing
- Time-to-action: How long from seeing to executing

Part of AI Engineering Improvements (Improvement 3).
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class ImplicitSignal:
    """Single implicit feedback signal."""

    timestamp: str
    recommendation_id: str
    signal_type: str  # "followed", "ignored", "overridden"
    similarity: float  # How closely action matched recommendation (0-1)
    time_to_action: Optional[float] = None  # Seconds from shown to acted
    alternative_taken: Optional[str] = None  # What user did instead (for overrides)
    context: Dict = field(default_factory=dict)


class ImplicitFeedbackCollector:
    """Collects implicit feedback signals from user behavior."""

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize the implicit feedback collector.

        Args:
            storage_path: Path to store implicit feedback signals (JSONL format)
        """
        if storage_path is None:
            storage_path = Path.home() / ".cortex" / "implicit_feedback.jsonl"

        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory state for current session
        self.pending_recommendations = {}  # id -> {rec, shown_at, context}
        self.session_actions = []  # Track all actions in this session
        self.followed_ids = set()  # Track which recommendations were followed

    def track_recommendation_shown(
        self, rec_id: str, recommendation: Dict, context: Optional[Dict] = None
    ):
        """
        Track when a recommendation is displayed to user.

        Args:
            rec_id: Unique recommendation identifier
            recommendation: The recommendation dict (with title, description, etc.)
            context: Optional context (project, goal, etc.)
        """
        self.pending_recommendations[rec_id] = {
            "recommendation": recommendation,
            "shown_at": datetime.now(),
            "context": context or self._capture_context(),
        }

    def track_action_taken(
        self, action: str, files: Optional[List[str]] = None, context: Optional[Dict] = None
    ):
        """
        Track user actions and correlate with pending recommendations.

        Args:
            action: Description of action taken (e.g., command, file edit)
            files: Files involved in the action
            context: Additional context about the action
        """
        action_time = datetime.now()
        files = files or []
        context = context or {}

        # Record action for session history
        self.session_actions.append(
            {"action": action, "files": files, "context": context, "timestamp": action_time}
        )

        # Correlate with pending recommendations
        for rec_id, rec_data in list(self.pending_recommendations.items()):
            similarity = self._action_matches_recommendation(action, files, rec_data)

            if similarity > 0.7:
                # High similarity = follow
                time_to_action = (action_time - rec_data["shown_at"]).total_seconds()
                self._log_follow(rec_id, similarity, time_to_action, rec_data)
                self.followed_ids.add(rec_id)

            elif 0.3 < similarity <= 0.7:
                # Medium similarity = override (similar intent, different execution)
                self._log_override(rec_id, action, similarity, rec_data)
                self.followed_ids.add(rec_id)  # Still followed in spirit

    def session_end(self):
        """
        Mark un-acted recommendations as ignored.
        Call this at end of session or after timeout period.
        """
        for rec_id, rec_data in self.pending_recommendations.items():
            if rec_id not in self.followed_ids:
                self._log_ignore(rec_id, rec_data)

        # Clear session state
        self.pending_recommendations.clear()
        self.session_actions.clear()
        self.followed_ids.clear()

    def get_session_stats(self) -> Dict:
        """Get statistics for current session."""
        total_shown = len(self.pending_recommendations) + len(self.followed_ids)
        return {
            "total_shown": total_shown,
            "followed": len(self.followed_ids),
            "pending": len(self.pending_recommendations),
            "actions_taken": len(self.session_actions),
        }

    def load_signals(self, limit: Optional[int] = None) -> List[ImplicitSignal]:
        """
        Load stored implicit signals from disk.

        Args:
            limit: Maximum number of signals to load (most recent)

        Returns:
            List of ImplicitSignal objects
        """
        if not self.storage_path.exists():
            return []

        signals = []
        with open(self.storage_path, "r") as f:
            lines = f.readlines()
            if limit:
                lines = lines[-limit:]

            for line in lines:
                try:
                    data = json.loads(line)
                    signals.append(ImplicitSignal(**data))
                except (json.JSONDecodeError, TypeError):
                    continue

        return signals

    def get_stats(self, days: int = 7) -> Dict:
        """
        Get statistics for implicit feedback over time period.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with counts and rates for different signal types
        """
        signals = self.load_signals()
        if not signals:
            return {
                "total_signals": 0,
                "follows": 0,
                "ignores": 0,
                "overrides": 0,
                "avg_time_to_action": 0,
                "follow_rate": 0,
            }

        # Filter to time period
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_signals = [
            s
            for s in signals
            if datetime.fromisoformat(s.timestamp).timestamp() > cutoff
        ]

        if not recent_signals:
            return {
                "total_signals": 0,
                "follows": 0,
                "ignores": 0,
                "overrides": 0,
                "avg_time_to_action": 0,
                "follow_rate": 0,
            }

        # Count by type
        follows = [s for s in recent_signals if s.signal_type == "followed"]
        ignores = [s for s in recent_signals if s.signal_type == "ignored"]
        overrides = [s for s in recent_signals if s.signal_type == "overridden"]

        # Calculate average time-to-action for follows
        times = [s.time_to_action for s in follows if s.time_to_action is not None]
        avg_time = sum(times) / len(times) if times else 0

        return {
            "total_signals": len(recent_signals),
            "follows": len(follows),
            "ignores": len(ignores),
            "overrides": len(overrides),
            "avg_time_to_action": avg_time,
            "follow_rate": (len(follows) + len(overrides)) / len(recent_signals)
            if recent_signals
            else 0,
        }

    # --- Private Methods ---

    def _capture_context(self) -> Dict:
        """Capture current session context."""
        return {
            "timestamp": datetime.now().isoformat(),
            "pending_count": len(self.pending_recommendations),
            "actions_count": len(self.session_actions),
        }

    def _action_matches_recommendation(
        self, action: str, files: List[str], rec_data: Dict
    ) -> float:
        """
        Calculate similarity between action and recommendation.

        Uses multiple signals:
        1. Text similarity between action and recommendation title/description
        2. File overlap (if recommendation mentions specific files)
        3. Command/keyword matching

        Returns:
            Similarity score 0-1
        """
        recommendation = rec_data["recommendation"]

        # Get recommendation text (title + description)
        rec_text = recommendation.get("title", "")
        if "description" in recommendation:
            rec_text += " " + recommendation["description"]

        # Calculate text similarity
        text_similarity = self._text_similarity(action.lower(), rec_text.lower())

        # Calculate file overlap if files are involved
        file_similarity = 0.0
        if files and "files" in recommendation:
            rec_files = recommendation["files"]
            if rec_files:
                file_similarity = self._file_overlap(files, rec_files)

        # Weighted combination (favor text similarity)
        if file_similarity > 0:
            return 0.6 * text_similarity + 0.4 * file_similarity
        else:
            return text_similarity

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher."""
        return SequenceMatcher(None, text1, text2).ratio()

    def _file_overlap(self, files1: List[str], files2: List[str]) -> float:
        """
        Calculate file overlap similarity.

        Compares file basenames (not full paths) for flexibility.
        """
        if not files1 or not files2:
            return 0.0

        # Get basenames
        basenames1 = {Path(f).name for f in files1}
        basenames2 = {Path(f).name for f in files2}

        # Calculate Jaccard similarity
        intersection = basenames1 & basenames2
        union = basenames1 | basenames2

        return len(intersection) / len(union) if union else 0.0

    def _is_modification_of(self, action: str, rec_data: Dict) -> bool:
        """
        Check if action is a modification/override of recommendation.

        True if action is similar but not identical (0.3 < similarity <= 0.7).
        """
        recommendation = rec_data["recommendation"]
        rec_text = recommendation.get("title", "")

        similarity = self._text_similarity(action.lower(), rec_text.lower())
        return 0.3 < similarity <= 0.7

    def _log_follow(self, rec_id: str, similarity: float, time_to_action: float, rec_data: Dict):
        """Log a follow signal."""
        signal = ImplicitSignal(
            timestamp=datetime.now().isoformat(),
            recommendation_id=rec_id,
            signal_type="followed",
            similarity=similarity,
            time_to_action=time_to_action,
            context=rec_data.get("context", {}),
        )
        self._persist_signal(signal)

    def _log_ignore(self, rec_id: str, rec_data: Dict):
        """Log an ignore signal."""
        signal = ImplicitSignal(
            timestamp=datetime.now().isoformat(),
            recommendation_id=rec_id,
            signal_type="ignored",
            similarity=0.0,
            context=rec_data.get("context", {}),
        )
        self._persist_signal(signal)

    def _log_override(self, rec_id: str, action: str, similarity: float, rec_data: Dict):
        """Log an override signal."""
        signal = ImplicitSignal(
            timestamp=datetime.now().isoformat(),
            recommendation_id=rec_id,
            signal_type="overridden",
            similarity=similarity,
            time_to_action=(datetime.now() - rec_data["shown_at"]).total_seconds(),
            alternative_taken=action,
            context=rec_data.get("context", {}),
        )
        self._persist_signal(signal)

    def _persist_signal(self, signal: ImplicitSignal):
        """Persist signal to disk in JSONL format."""
        with open(self.storage_path, "a") as f:
            f.write(json.dumps(asdict(signal)) + "\n")
