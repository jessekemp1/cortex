#!/usr/bin/env python3
"""
Cortex Feedback Logger - Captures user feedback for verification loop

Implements Phase 7 (Success Verification) of Golden Spec Method.
Tracks outcomes to enable learning over time.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cortex.state_paths import get_cortex_dir

# Import quality tracking
try:
    from intelligence.quality.data_quality import DataQualityTracker
except ImportError:
    DataQualityTracker = None  # Optional dependency

# Import tiered memory for outcome updates
try:
    from intelligence.memory.tiered_memory import TieredMemory

    TIERED_MEMORY_AVAILABLE = True
except ImportError:
    TIERED_MEMORY_AVAILABLE = False
    TieredMemory = None


@dataclass
class FeedbackEntry:
    """Single feedback entry - backward compatible format."""

    timestamp: str
    action_id: Optional[str]  # Recommendation ID if available
    action_title: str
    useful: bool  # Was the recommendation useful?
    notes: Optional[str] = None  # Optional notes
    actual_outcome: Optional[str] = None  # What actually happened


@dataclass
class OutcomeEntry:
    """Structured outcome tracking for learning."""

    timestamp: str
    recommendation_id: str  # Unique ID for the recommendation
    recommendation_title: str
    recommendation_type: str  # e.g., "goal_progress", "blocker_resolution", "project_health"
    priority: str  # A, B, C
    confidence: float  # 0.0-1.0
    followed: bool  # Did user follow the recommendation?
    outcome: str  # "success", "partial", "failed", "unknown"
    notes: Optional[str] = None
    context: Optional[Dict[str, Any]] = None  # Additional context (project, goal, etc.)


class FeedbackLogger:
    """Logs user feedback for system calibration."""

    def __init__(self, log_file: Optional[Path] = None, outcomes_file: Optional[Path] = None):
        if log_file is None:
            # Default to writable cortex state dir
            log_dir = get_cortex_dir()
            log_file = log_dir / "feedback.json"
            outcomes_file = log_dir / "outcomes.jsonl"

        self.log_file = log_file
        self.outcomes_file = outcomes_file if outcomes_file else get_cortex_dir() / "outcomes.jsonl"

        # Initialize quality tracker
        self.quality_tracker = DataQualityTracker() if DataQualityTracker else None

        # Initialize tiered memory for outcome propagation
        self.tiered_memory = None
        if TIERED_MEMORY_AVAILABLE:
            try:
                self.tiered_memory = TieredMemory()
            except Exception:
                self.tiered_memory = None

    def _ensure_log_exists(self):
        """Ensure log file exists with empty array."""
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w") as f:
                json.dump([], f)

    def _ensure_outcomes_exists(self):
        """Ensure outcomes file exists (JSONL format)."""
        if not self.outcomes_file.exists():
            self.outcomes_file.parent.mkdir(parents=True, exist_ok=True)
            self.outcomes_file.touch()

    def log_feedback(
        self,
        action_title: str,
        useful: bool,
        action_id: Optional[str] = None,
        notes: Optional[str] = None,
        actual_outcome: Optional[str] = None,
    ) -> None:
        """Log feedback for a recommendation."""
        entry = FeedbackEntry(
            timestamp=datetime.now().isoformat(),
            action_id=action_id,
            action_title=action_title,
            useful=useful,
            notes=notes,
            actual_outcome=actual_outcome,
        )

        # Ensure files exist on first write (lazy init)
        self._ensure_log_exists()

        # Read existing entries
        entries = self._load_entries()

        # Add new entry
        entries.append(asdict(entry))

        # Write back
        with open(self.log_file, "w") as f:
            json.dump(entries, f, indent=2)

    def log_quick(self, message: str) -> None:
        """Quick log entry (for general notes)."""
        self.log_feedback(action_title="Note", useful=True, notes=message)

    def _load_entries(self) -> List[Dict[str, Any]]:
        """Load all feedback entries."""
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        entries = self._load_entries()

        if not entries:
            return {
                "total_entries": 0,
                "useful_count": 0,
                "not_useful_count": 0,
                "useful_rate": 0.0,
                "log_file": str(self.log_file),
            }

        useful_count = sum(1 for e in entries if e.get("useful", False))
        not_useful_count = len(entries) - useful_count

        return {
            "total_entries": len(entries),
            "useful_count": useful_count,
            "not_useful_count": not_useful_count,
            "useful_rate": useful_count / len(entries) if entries else 0.0,
            "log_file": str(self.log_file),
        }

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent feedback entries."""
        entries = self._load_entries()
        return entries[-limit:]

    def log_outcome(
        self,
        recommendation_id: str,
        recommendation_title: str,
        recommendation_type: str,
        priority: str,
        confidence: float,
        followed: bool,
        outcome: str,
        notes: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a structured outcome for learning.

        Args:
            recommendation_id: Unique ID for the recommendation
            recommendation_title: Title of the recommendation
            recommendation_type: Type (e.g., "goal_progress", "blocker_resolution")
            priority: Priority level (A, B, C)
            confidence: Confidence score 0.0-1.0
            followed: Did user follow the recommendation?
            outcome: Result - "success", "partial", "failed", "unknown"
            notes: Optional notes
            context: Additional context (project, goal, etc.)
        """
        entry = OutcomeEntry(
            timestamp=datetime.now().isoformat(),
            recommendation_id=recommendation_id,
            recommendation_title=recommendation_title,
            recommendation_type=recommendation_type,
            priority=priority,
            confidence=confidence,
            followed=followed,
            outcome=outcome,
            notes=notes,
            context=context,
        )

        # Assess quality if quality tracker is available
        if self.quality_tracker:
            quality = self.quality_tracker.assess_outcome(entry)
            self.quality_tracker.track_quality("outcome", quality)

            # Add quality score to context
            if context is None:
                context = {}
            context["quality_score"] = quality.overall_score()
            entry.context = context

        # Append to JSONL file (one entry per line)
        self._ensure_outcomes_exists()
        with open(self.outcomes_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

        # Propagate outcome to tiered memory for learning
        if self.tiered_memory:
            try:
                quality_score = context.get("quality_score", 0.5) if context else 0.5
                self.tiered_memory.update_outcome(
                    item_id=recommendation_id,
                    outcome=outcome,
                    quality_score=quality_score,
                )
            except Exception:
                pass  # Silently fail - tiered memory is optional

    def load_outcomes(self) -> List[OutcomeEntry]:
        """Load all outcome entries from JSONL file."""
        if not self.outcomes_file.exists():
            return []

        outcomes = []
        try:
            with open(self.outcomes_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        outcomes.append(OutcomeEntry(**data))
        except (json.JSONDecodeError, IOError):
            return []

        return outcomes
