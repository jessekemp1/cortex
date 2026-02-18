"""
Command Workflow Tracker for Cortex

Tracks slash command usage patterns and learns which workflows succeed.
Integrates with the interaction learning system to provide command-aware recommendations.
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class CommandType(Enum):
    """Categories of slash commands."""

    # Core workflow
    INVESTIGATE = "investigate"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    PR = "pr"

    # Anti-patterns
    SHIP = "ship"
    DEBUG = "debug"

    # Testing
    TEST = "test"
    TEST_QUICK = "test-quick"
    TEST_ALL = "test-all"
    FIX = "fix"

    # Daily
    BRIEFING = "briefing"
    NEXT = "next"
    STATUS = "status"

    # Specialized
    DATABRICKS = "databricks"
    PRODUCT = "product"
    RESEARCH = "research"

    # Other
    OTHER = "other"


# Command to workflow phase mapping
WORKFLOW_PHASES = {
    CommandType.INVESTIGATE: 1,
    CommandType.PLAN: 2,
    CommandType.IMPLEMENT: 3,
    CommandType.REVIEW: 4,
    CommandType.PR: 5,
}

# Command patterns for detection
COMMAND_PATTERNS = [
    (r"^/investigate\b", CommandType.INVESTIGATE),
    (r"^/plan\b", CommandType.PLAN),
    (r"^/implement\b", CommandType.IMPLEMENT),
    (r"^/review\b", CommandType.REVIEW),
    (r"^/pr\b", CommandType.PR),
    (r"^/ship\b", CommandType.SHIP),
    (r"^/debug\b", CommandType.DEBUG),
    (r"^/test-quick\b", CommandType.TEST_QUICK),
    (r"^/test-all\b", CommandType.TEST_ALL),
    (r"^/test\b", CommandType.TEST),
    (r"^/fix\b", CommandType.FIX),
    (r"^/briefing\b", CommandType.BRIEFING),
    (r"^/next\b", CommandType.NEXT),
    (r"^/status\b", CommandType.STATUS),
    (r"^/databricks\b", CommandType.DATABRICKS),
    (r"^/product\b", CommandType.PRODUCT),
    (r"^/research\b", CommandType.RESEARCH),
]


@dataclass
class CommandExecution:
    """Record of a command execution."""

    command: CommandType
    timestamp: datetime
    session_id: str
    project: Optional[str] = None
    arguments: Optional[str] = None
    outcome: Optional[str] = None  # success, partial, failed, unknown
    duration_seconds: Optional[float] = None


@dataclass
class WorkflowPattern:
    """A detected workflow pattern (sequence of commands)."""

    pattern_id: str
    commands: list[CommandType]
    frequency: int = 1
    success_rate: float = 0.0
    avg_duration_minutes: float = 0.0
    projects: list[str] = field(default_factory=list)
    last_seen: datetime = field(default_factory=datetime.now)

    def to_string(self) -> str:
        """Return human-readable workflow string."""
        return " → ".join(f"/{c.value}" for c in self.commands)


class CommandTracker:
    """
    Tracks command usage and extracts workflow patterns.

    Integrates with Cortex to:
    1. Detect slash commands in prompts
    2. Track command sequences per session
    3. Learn successful workflow patterns
    4. Provide command suggestions for /next
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cortex" / "command_tracking.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # In-memory session tracking
        self._current_session: Optional[str] = None
        self._session_commands: list[CommandExecution] = []

    def _init_db(self):
        """Initialize SQLite database for command tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Command executions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS command_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                project TEXT,
                arguments TEXT,
                outcome TEXT DEFAULT 'unknown',
                duration_seconds REAL
            )
        """
        )

        # Workflow patterns table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_patterns (
                pattern_id TEXT PRIMARY KEY,
                commands TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                total_duration_minutes REAL DEFAULT 0,
                projects TEXT DEFAULT '[]',
                last_seen TEXT,
                created_at TEXT
            )
        """
        )

        # Command success rates table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS command_stats (
                command TEXT PRIMARY KEY,
                total_executions INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                avg_duration_seconds REAL DEFAULT 0,
                last_used TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def detect_command(self, prompt: str) -> Optional[tuple[CommandType, str]]:
        """
        Detect if a prompt contains a slash command.

        Returns (CommandType, arguments) or None if no command detected.
        """
        prompt = prompt.strip()

        for pattern, cmd_type in COMMAND_PATTERNS:
            match = re.match(pattern, prompt, re.IGNORECASE)
            if match:
                # Extract arguments (everything after the command)
                args = prompt[match.end() :].strip()
                return (cmd_type, args)

        # Check for generic slash command
        if prompt.startswith("/"):
            return (CommandType.OTHER, prompt)

        return None

    def track_command(
        self,
        command: CommandType,
        session_id: str,
        project: Optional[str] = None,
        arguments: Optional[str] = None,
    ) -> CommandExecution:
        """Record a command execution."""
        execution = CommandExecution(
            command=command,
            timestamp=datetime.now(),
            session_id=session_id,
            project=project,
            arguments=arguments,
        )

        # Track in current session
        if self._current_session != session_id:
            self._finalize_session()
            self._current_session = session_id
            self._session_commands = []

        self._session_commands.append(execution)

        # Persist to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO command_executions
            (command, timestamp, session_id, project, arguments)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                command.value,
                execution.timestamp.isoformat(),
                session_id,
                project,
                arguments,
            ),
        )

        # Update command stats
        cursor.execute(
            """
            INSERT INTO command_stats (command, total_executions, last_used)
            VALUES (?, 1, ?)
            ON CONFLICT(command) DO UPDATE SET
                total_executions = total_executions + 1,
                last_used = excluded.last_used
        """,
            (command.value, execution.timestamp.isoformat()),
        )

        conn.commit()
        conn.close()

        return execution

    def record_outcome(
        self,
        session_id: str,
        command: CommandType,
        outcome: str,
        duration_seconds: Optional[float] = None,
    ):
        """Record the outcome of a command execution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Update most recent execution of this command in session
        cursor.execute(
            """
            UPDATE command_executions
            SET outcome = ?, duration_seconds = ?
            WHERE session_id = ? AND command = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (outcome, duration_seconds, session_id, command.value),
        )

        # Update success stats
        if outcome == "success":
            cursor.execute(
                """
                UPDATE command_stats
                SET success_count = success_count + 1
                WHERE command = ?
            """,
                (command.value,),
            )

        conn.commit()
        conn.close()

    def _finalize_session(self):
        """Extract workflow patterns from completed session."""
        if not self._session_commands or len(self._session_commands) < 2:
            return

        # Extract workflow patterns (sequences of 2+ commands)
        patterns = self._extract_patterns(self._session_commands)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for pattern in patterns:
            pattern_key = "_".join(c.command.value for c in pattern)
            commands_json = json.dumps([c.command.value for c in pattern])

            # Check if pattern succeeded (last command had success outcome)
            success = pattern[-1].outcome == "success"

            # Calculate duration
            if len(pattern) >= 2:
                duration = (pattern[-1].timestamp - pattern[0].timestamp).total_seconds() / 60
            else:
                duration = 0

            # Get project
            project = pattern[0].project or "unknown"

            cursor.execute(
                """
                INSERT INTO workflow_patterns
                (pattern_id, commands, frequency, success_count, failure_count,
                 total_duration_minutes, projects, last_seen, created_at)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pattern_id) DO UPDATE SET
                    frequency = frequency + 1,
                    success_count = success_count + excluded.success_count,
                    failure_count = failure_count + excluded.failure_count,
                    total_duration_minutes = total_duration_minutes + excluded.total_duration_minutes,
                    projects = excluded.projects,
                    last_seen = excluded.last_seen
            """,
                (
                    pattern_key,
                    commands_json,
                    1 if success else 0,
                    0 if success else 1,
                    duration,
                    json.dumps([project]),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )

        conn.commit()
        conn.close()

    def _extract_patterns(
        self,
        commands: list[CommandExecution],
        min_length: int = 2,
        max_length: int = 5,
    ) -> list[list[CommandExecution]]:
        """Extract workflow patterns from command sequence."""
        patterns = []

        # Sliding window for different pattern lengths
        for length in range(min_length, min(max_length + 1, len(commands) + 1)):
            for i in range(len(commands) - length + 1):
                window = commands[i : i + length]

                # Check if this looks like a workflow (sequential phases)
                if self._is_workflow_pattern(window):
                    patterns.append(window)

        return patterns

    def _is_workflow_pattern(self, commands: list[CommandExecution]) -> bool:
        """Check if command sequence looks like intentional workflow."""
        if len(commands) < 2:
            return False

        # Check time proximity (all within 2 hours)
        total_time = (commands[-1].timestamp - commands[0].timestamp).total_seconds()
        if total_time > 7200:  # 2 hours
            return False

        # Check if it follows workflow phase order
        phases = [WORKFLOW_PHASES.get(c.command, 0) for c in commands]
        phases = [p for p in phases if p > 0]  # Only core workflow commands

        if len(phases) >= 2:
            # Should be generally increasing (allows some backtracking)
            increases = sum(1 for i in range(len(phases) - 1) if phases[i + 1] >= phases[i])
            return increases >= len(phases) // 2

        return True  # Non-workflow commands are still valid patterns

    def get_workflow_suggestions(
        self,
        current_command: Optional[CommandType] = None,
        project: Optional[str] = None,
        limit: int = 3,
    ) -> list[dict]:
        """
        Get suggested next commands based on successful patterns.

        Used by /next to provide command-aware recommendations.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        suggestions = []

        if current_command:
            # Find patterns that start with or contain current command
            cursor.execute(
                """
                SELECT pattern_id, commands, frequency, success_count,
                       failure_count, total_duration_minutes
                FROM workflow_patterns
                WHERE commands LIKE ?
                ORDER BY
                    CAST(success_count AS REAL) / (success_count + failure_count + 1) DESC,
                    frequency DESC
                LIMIT ?
            """,
                (f'%"{current_command.value}"%', limit * 2),
            )
        else:
            # Get most successful patterns overall
            cursor.execute(
                """
                SELECT pattern_id, commands, frequency, success_count,
                       failure_count, total_duration_minutes
                FROM workflow_patterns
                ORDER BY
                    CAST(success_count AS REAL) / (success_count + failure_count + 1) DESC,
                    frequency DESC
                LIMIT ?
            """,
                (limit * 2,),
            )

        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            pattern_id, commands_json, freq, success, failure, duration = row
            commands = json.loads(commands_json)

            # Calculate success rate
            total = success + failure
            success_rate = success / total if total > 0 else 0.5

            # Find next command in sequence after current
            next_cmd = None
            if current_command:
                try:
                    idx = commands.index(current_command.value)
                    if idx < len(commands) - 1:
                        next_cmd = commands[idx + 1]
                except ValueError:
                    pass

            suggestions.append(
                {
                    "pattern": " → ".join(f"/{c}" for c in commands),
                    "next_command": f"/{next_cmd}" if next_cmd else None,
                    "success_rate": success_rate,
                    "frequency": freq,
                    "avg_duration_min": duration / freq if freq > 0 else 0,
                }
            )

        # Deduplicate and limit
        seen = set()
        unique = []
        for s in suggestions:
            key = s["pattern"]
            if key not in seen:
                seen.add(key)
                unique.append(s)
                if len(unique) >= limit:
                    break

        return unique

    def get_command_stats(self) -> dict:
        """Get overall command usage statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT command, total_executions, success_count, avg_duration_seconds
            FROM command_stats
            ORDER BY total_executions DESC
        """
        )

        rows = cursor.fetchall()
        conn.close()

        stats = {}
        for cmd, total, success, duration in rows:
            stats[cmd] = {
                "total": total,
                "success_rate": success / total if total > 0 else 0,
                "avg_duration_sec": duration,
            }

        return stats

    def suggest_for_context(
        self,
        project: Optional[str] = None,
        recent_commands: Optional[list[str]] = None,
        task_type: Optional[str] = None,
    ) -> dict:
        """
        Suggest a command workflow based on current context.

        Returns recommendation with command sequence and rationale.
        """
        # Default workflow for new features
        default_workflow = [
            CommandType.INVESTIGATE,
            CommandType.PLAN,
            CommandType.IMPLEMENT,
            CommandType.REVIEW,
            CommandType.PR,
        ]

        # Determine starting point
        if recent_commands:
            # Find where they are in workflow
            last_cmd = recent_commands[-1].lstrip("/")
            try:
                last_type = CommandType(last_cmd)
                phase = WORKFLOW_PHASES.get(last_type, 0)

                if phase > 0 and phase < 5:
                    # Suggest next phase
                    next_cmds = [c for c in default_workflow if WORKFLOW_PHASES.get(c, 0) > phase]
                    if next_cmds:
                        return {
                            "suggested_command": f"/{next_cmds[0].value}",
                            "full_workflow": " → ".join(f"/{c.value}" for c in next_cmds),
                            "rationale": f"Continue workflow from /{last_cmd}",
                            "confidence": 0.85,
                        }
            except ValueError:
                pass

        # Check for task-type specific workflows
        if task_type:
            task_lower = task_type.lower()

            if "bug" in task_lower or "fix" in task_lower:
                return {
                    "suggested_command": "/debug",
                    "full_workflow": "/debug → /test → /commit",
                    "rationale": "Bug fixing workflow",
                    "confidence": 0.8,
                }

            if "ship" in task_lower or "mvp" in task_lower:
                return {
                    "suggested_command": "/ship",
                    "full_workflow": "/ship",
                    "rationale": "Force MVP delivery (2hr limit)",
                    "confidence": 0.9,
                }

        # Default: start investigation
        return {
            "suggested_command": "/investigate",
            "full_workflow": " → ".join(f"/{c.value}" for c in default_workflow),
            "rationale": "Standard feature development workflow",
            "confidence": 0.75,
        }


# Singleton instance
_tracker: Optional[CommandTracker] = None


def get_tracker() -> CommandTracker:
    """Get or create the command tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = CommandTracker()
    return _tracker
