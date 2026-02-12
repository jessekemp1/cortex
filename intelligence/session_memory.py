#!/usr/bin/env python3
"""
Cortex Session Memory - Persistent context across Claude Code sessions.

Ported from Moltbot's memory system, adapted for Cortex intelligence.
Stores user preferences, session summaries, and learnings across time.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SessionEntry:
    """A session memory entry."""

    timestamp: datetime
    session_type: str  # "work", "eod", "briefing", "manual"
    summary: str
    outcomes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "session_type": self.session_type,
            "summary": self.summary,
            "outcomes": self.outcomes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_type=data["session_type"],
            summary=data["summary"],
            outcomes=data.get("outcomes", []),
            metadata=data.get("metadata", {}),
        )


class SessionMemory:
    """
    Persistent session context across Claude Code invocations.

    Features:
    - Remember user preferences (coding style, commit messages, etc.)
    - Store session summaries for context building
    - Track outcomes across sessions
    - Provide recent context for recommendations

    Storage:
    - ~/.cortex/session_memory.jsonl - Session logs
    - ~/.cortex/preferences.json - User preferences
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        """Initialize session memory."""
        if memory_dir is None:
            memory_dir = Path.home() / ".cortex"

        memory_dir.mkdir(parents=True, exist_ok=True)

        self.memory_file = memory_dir / "session_memory.jsonl"
        self.preferences_file = memory_dir / "preferences.json"

    # =========================================================================
    # Session Logs
    # =========================================================================

    def append_session(
        self,
        summary: str,
        session_type: str = "work",
        outcomes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Append session summary to memory log.

        Args:
            summary: Brief description of session work
            session_type: "work", "eod", "briefing", "manual"
            outcomes: List of outcomes/results from session
            metadata: Additional context (project, duration, etc.)
        """
        entry = SessionEntry(
            timestamp=datetime.now(),
            session_type=session_type,
            summary=summary,
            outcomes=outcomes or [],
            metadata=metadata or {},
        )

        with open(self.memory_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def get_recent_sessions(
        self, days: int = 7, session_type: Optional[str] = None
    ) -> List[SessionEntry]:
        """
        Get recent session entries.

        Args:
            days: Number of days to look back
            session_type: Filter by session type (optional)

        Returns:
            List of SessionEntry objects
        """
        if not self.memory_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        sessions = []

        with open(self.memory_file, "r") as f:
            for line in f:
                entry = SessionEntry.from_dict(json.loads(line))

                # Filter by date
                if entry.timestamp < cutoff:
                    continue

                # Filter by type
                if session_type and entry.session_type != session_type:
                    continue

                sessions.append(entry)

        return sorted(sessions, key=lambda x: x.timestamp, reverse=True)

    def get_session_context(self, days: int = 7) -> str:
        """
        Get formatted session context for LLM consumption.

        Args:
            days: Number of days to look back

        Returns:
            Formatted context string
        """
        sessions = self.get_recent_sessions(days=days)

        if not sessions:
            return "No recent session history."

        lines = [f"Session History (last {days} days):\n"]

        for session in sessions:
            date_str = session.timestamp.strftime("%Y-%m-%d")
            lines.append(f"• {date_str} ({session.session_type}): {session.summary}")

            if session.outcomes:
                for outcome in session.outcomes:
                    lines.append(f"  → {outcome}")

        return "\n".join(lines)

    # =========================================================================
    # Preferences
    # =========================================================================

    def remember(self, key: str, value: Any, category: str = "general"):
        """
        Save a user preference.

        Args:
            key: Preference key (e.g., "commit_style", "test_framework")
            value: Preference value
            category: Grouping category (e.g., "git", "testing", "general")
        """
        prefs = self._load_preferences()

        if category not in prefs:
            prefs[category] = {}

        prefs[category][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }

        self._save_preferences(prefs)

    def recall(self, key: str, category: str = "general", default: Any = None) -> Any:
        """
        Retrieve a user preference.

        Args:
            key: Preference key
            category: Grouping category
            default: Default value if not found

        Returns:
            Preference value or default
        """
        prefs = self._load_preferences()

        if category not in prefs:
            return default

        if key not in prefs[category]:
            return default

        return prefs[category][key]["value"]

    def get_all_preferences(self) -> Dict[str, Dict[str, Any]]:
        """Get all stored preferences."""
        return self._load_preferences()

    def forget(self, key: str, category: str = "general"):
        """
        Remove a preference.

        Args:
            key: Preference key
            category: Grouping category
        """
        prefs = self._load_preferences()

        if category in prefs and key in prefs[category]:
            del prefs[category][key]
            self._save_preferences(prefs)

    def _load_preferences(self) -> Dict[str, Dict[str, Any]]:
        """Load preferences from disk."""
        if not self.preferences_file.exists():
            return {}

        with open(self.preferences_file, "r") as f:
            return json.load(f)

    def _save_preferences(self, prefs: Dict[str, Dict[str, Any]]):
        """Save preferences to disk."""
        with open(self.preferences_file, "w") as f:
            json.dump(prefs, f, indent=2)

    # =========================================================================
    # Utility
    # =========================================================================

    def clear_old_sessions(self, days: int = 90):
        """
        Clear session logs older than specified days.

        Args:
            days: Keep sessions newer than this
        """
        if not self.memory_file.exists():
            return

        cutoff = datetime.now() - timedelta(days=days)
        kept_sessions = []

        with open(self.memory_file, "r") as f:
            for line in f:
                entry = SessionEntry.from_dict(json.loads(line))
                if entry.timestamp >= cutoff:
                    kept_sessions.append(entry)

        # Rewrite file with kept sessions
        with open(self.memory_file, "w") as f:
            for entry in kept_sessions:
                f.write(json.dumps(entry.to_dict()) + "\n")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if not self.memory_file.exists():
            return {
                "total_sessions": 0,
                "oldest_session": None,
                "newest_session": None,
                "preferences_count": 0,
            }

        sessions = []
        with open(self.memory_file, "r") as f:
            for line in f:
                sessions.append(SessionEntry.from_dict(json.loads(line)))

        prefs = self._load_preferences()
        pref_count = sum(len(cat) for cat in prefs.values())

        return {
            "total_sessions": len(sessions),
            "oldest_session": min(s.timestamp for s in sessions).isoformat() if sessions else None,
            "newest_session": max(s.timestamp for s in sessions).isoformat() if sessions else None,
            "preferences_count": pref_count,
        }


# =============================================================================
# CLI Integration
# =============================================================================


def main():
    """CLI for testing session memory."""
    import sys

    memory = SessionMemory()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  session_memory.py remember <key> <value>")
        print("  session_memory.py recall <key>")
        print("  session_memory.py log <summary>")
        print("  session_memory.py context")
        print("  session_memory.py stats")
        return

    command = sys.argv[1]

    if command == "remember":
        key = sys.argv[2]
        value = sys.argv[3]
        memory.remember(key, value)
        print(f"✓ Remembered: {key} = {value}")

    elif command == "recall":
        key = sys.argv[2]
        value = memory.recall(key)
        print(f"{key} = {value}")

    elif command == "log":
        summary = " ".join(sys.argv[2:])
        memory.append_session(summary)
        print(f"✓ Logged session: {summary}")

    elif command == "context":
        print(memory.get_session_context())

    elif command == "stats":
        stats = memory.get_stats()
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
