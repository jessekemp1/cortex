#!/usr/bin/env python3
"""
Converx Feedback Logger - Captures user feedback for verification loop

Implements Phase 7 (Success Verification) of Golden Spec Method.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FeedbackEntry:
    """Single feedback entry."""

    timestamp: str
    action_id: Optional[str]  # Recommendation ID if available
    action_title: str
    useful: bool  # Was the recommendation useful?
    notes: Optional[str] = None  # Optional notes
    actual_outcome: Optional[str] = None  # What actually happened


class FeedbackLogger:
    """Logs user feedback for system calibration."""

    def __init__(self, log_file: Optional[Path] = None):
        if log_file is None:
            # Default to ~/.converx/feedback.json
            home = Path.home()
            log_dir = home / ".converx"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "feedback.json"

        self.log_file = log_file
        self._ensure_log_exists()

    def _ensure_log_exists(self):
        """Ensure log file exists with empty array."""
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w") as f:
                json.dump([], f)

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
