"""
Claude Session Absorber - Real-Time Interaction Feedback Loop

Extends the Context Absorber to capture Claude Code interactions in real-time.
This enables Cortex to learn from:
- User prompts and patterns
- Tool usage and outcomes
- Implicit feedback (corrections, follow-ups, etc.)
- Session flow and context switches

Integration with Claude Code via hooks:
- UserPromptSubmit -> PROMPT_RECEIVED
- PreToolUse -> TOOL_STARTED
- PostToolUse -> TOOL_COMPLETED
- Stop -> RESPONSE_COMPLETED
- SessionEnd -> SESSION_ENDED
"""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .absorber import Signal, SignalSource, SignalType

logger = logging.getLogger(__name__)


class InteractionSignalType(Enum):
    """Extended signal types for Claude Code interactions."""

    # Core interaction signals
    PROMPT_RECEIVED = "prompt_received"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    RESPONSE_COMPLETED = "response_completed"
    SESSION_ENDED = "session_ended"

    # Implicit feedback signals (derived)
    USER_CORRECTION = "user_correction"  # User corrects Claude's output
    USER_FOLLOWUP = "user_followup"  # User asks follow-up (ambiguity detected)
    USER_APPROVAL = "user_approval"  # User accepts/proceeds (implicit success)
    CONTEXT_SWITCH = "context_switch"  # User changes topic/project
    ERROR_RECOVERY = "error_recovery"  # Tool failed, then succeeded
    PATTERN_REPEATED = "pattern_repeated"  # Similar prompt/action seen before


@dataclass
class InteractionSignal(Signal):
    """Extended signal with interaction-specific metadata."""

    interaction_type: Optional[InteractionSignalType] = None
    session_id: Optional[str] = None
    prompt_hash: Optional[str] = None  # For deduplication/pattern matching
    tool_name: Optional[str] = None
    tool_success: Optional[bool] = None
    response_length: Optional[int] = None
    context_relevance: Optional[float] = None  # 0-1 score

    def to_dict(self) -> Dict:
        base = super().to_dict()
        base.update(
            {
                "interaction_type": (
                    self.interaction_type.value if self.interaction_type else None
                ),
                "session_id": self.session_id,
                "prompt_hash": self.prompt_hash,
                "tool_name": self.tool_name,
                "tool_success": self.tool_success,
                "response_length": self.response_length,
                "context_relevance": self.context_relevance,
            }
        )
        return base


@dataclass
class InteractionPattern:
    """A detected interaction pattern that can inform future recommendations."""

    pattern_id: str
    pattern_type: str  # "prompt_pattern", "tool_sequence", "correction_pattern"
    description: str
    frequency: int
    success_rate: float
    last_seen: datetime
    examples: List[Dict[str, Any]] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "success_rate": self.success_rate,
            "last_seen": self.last_seen.isoformat(),
            "examples": self.examples[-5:],  # Keep last 5 examples
            "projects": list(set(self.projects)),
        }


class ClaudeSessionSource(SignalSource):
    """
    Signal source that captures Claude Code interactions via hooks.

    Receives data from hooks and transforms it into signals for the absorber.
    Also maintains a session transcript for context.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".cortex" / "claude_sessions.db"
        self._running = False
        self._signals: List[InteractionSignal] = []
        self._lock = Lock()
        self._current_session: Optional[str] = None
        self._session_context: Dict[str, Any] = {}
        self._prompt_history: List[Dict] = []  # Recent prompts for pattern detection
        self._init_db()

    @property
    def name(self) -> str:
        return "ClaudeSessionSource"

    def _init_db(self) -> None:
        """Initialize SQLite database for interaction storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        # Interactions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                interaction_type TEXT NOT NULL,
                project TEXT,
                payload TEXT NOT NULL,
                prompt_hash TEXT,
                tool_name TEXT,
                tool_success INTEGER,
                processed INTEGER DEFAULT 0
            )
        """
        )

        # Patterns table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                description TEXT,
                frequency INTEGER DEFAULT 1,
                success_rate REAL DEFAULT 0.5,
                last_seen TEXT,
                examples TEXT,
                projects TEXT
            )
        """
        )

        # Session summaries for cross-session learning
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                project TEXT,
                start_time TEXT,
                end_time TEXT,
                prompt_count INTEGER,
                tool_count INTEGER,
                success_rate REAL,
                key_topics TEXT,
                lessons TEXT
            )
        """
        )

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(interaction_type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_interactions_project ON interactions(project)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type)")

        conn.commit()
        conn.close()

    def start(self) -> None:
        """Start capturing Claude Code interactions."""
        self._running = True
        logger.info("ClaudeSessionSource started")

    def stop(self) -> None:
        """Stop capturing interactions."""
        self._running = False
        # Summarize current session if any
        if self._current_session:
            self._summarize_session(self._current_session)
        logger.info("ClaudeSessionSource stopped")

    def get_signals(self) -> List[Signal]:
        """Get pending interaction signals."""
        with self._lock:
            signals = self._signals.copy()
            self._signals.clear()
        return signals

    @property
    def is_running(self) -> bool:
        return self._running

    # === Hook Receivers ===

    def on_prompt_received(
        self, session_id: str, prompt: str, cwd: str, metadata: Optional[Dict] = None
    ) -> InteractionSignal:
        """
        Called by UserPromptSubmit hook when user sends a prompt.

        Analyzes prompt for:
        - Pattern matching (similar to past prompts)
        - Implicit feedback (corrections, follow-ups)
        - Context switches
        """
        import uuid

        prompt_hash = hashlib.sha256(prompt.lower().strip().encode()).hexdigest()[:16]
        project = self._detect_project(cwd)

        # Detect implicit feedback from prompt content
        interaction_type = self._classify_prompt(prompt)

        signal = InteractionSignal(
            id=f"int_{uuid.uuid4().hex[:8]}",
            type=SignalType.COMMAND_EXECUTED,  # Use existing type for compatibility
            timestamp=datetime.now(),
            source="claude_session",
            payload={
                "prompt": prompt[:1000],  # Truncate for storage
                "prompt_full_length": len(prompt),
                "cwd": cwd,
            },
            project=project,
            metadata=metadata,
            interaction_type=interaction_type,
            session_id=session_id,
            prompt_hash=prompt_hash,
        )

        # Check for patterns
        similar_prompts = self._find_similar_prompts(prompt_hash, prompt)
        if similar_prompts:
            signal.metadata = signal.metadata or {}
            signal.metadata["similar_prompts"] = len(similar_prompts)
            signal.metadata["is_pattern"] = True

        # Store and buffer
        self._store_interaction(signal)
        self._prompt_history.append(
            {
                "hash": prompt_hash,
                "prompt": prompt[:500],
                "timestamp": signal.timestamp,
                "project": project,
            }
        )

        # Keep last 100 prompts in memory
        if len(self._prompt_history) > 100:
            self._prompt_history = self._prompt_history[-100:]

        with self._lock:
            self._signals.append(signal)

        return signal

    def on_tool_started(
        self, session_id: str, tool_name: str, tool_input: Dict, cwd: str
    ) -> InteractionSignal:
        """Called by PreToolUse hook when tool execution starts."""
        import uuid

        signal = InteractionSignal(
            id=f"int_{uuid.uuid4().hex[:8]}",
            type=SignalType.COMMAND_EXECUTED,
            timestamp=datetime.now(),
            source="claude_session",
            payload={
                "tool_name": tool_name,
                "tool_input": self._sanitize_payload(tool_input),
                "cwd": cwd,
            },
            project=self._detect_project(cwd),
            interaction_type=InteractionSignalType.TOOL_STARTED,
            session_id=session_id,
            tool_name=tool_name,
        )

        self._store_interaction(signal)
        with self._lock:
            self._signals.append(signal)

        return signal

    def on_tool_completed(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict,
        tool_response: Dict,
        success: bool,
        cwd: str,
    ) -> InteractionSignal:
        """
        Called by PostToolUse hook after tool execution completes.

        Tracks tool success/failure for pattern learning.
        """
        import uuid

        signal = InteractionSignal(
            id=f"int_{uuid.uuid4().hex[:8]}",
            type=SignalType.COMMAND_EXECUTED,
            timestamp=datetime.now(),
            source="claude_session",
            payload={
                "tool_name": tool_name,
                "tool_input": self._sanitize_payload(tool_input),
                "tool_response_summary": self._summarize_response(tool_response),
                "success": success,
                "cwd": cwd,
            },
            project=self._detect_project(cwd),
            interaction_type=InteractionSignalType.TOOL_COMPLETED,
            session_id=session_id,
            tool_name=tool_name,
            tool_success=success,
        )

        # Update tool success patterns
        self._update_tool_pattern(tool_name, success, self._detect_project(cwd))

        self._store_interaction(signal)
        with self._lock:
            self._signals.append(signal)

        return signal

    def on_response_completed(
        self, session_id: str, cwd: str, metadata: Optional[Dict] = None
    ) -> InteractionSignal:
        """Called by Stop hook when Claude finishes responding."""
        import uuid

        signal = InteractionSignal(
            id=f"int_{uuid.uuid4().hex[:8]}",
            type=SignalType.COMMAND_EXECUTED,
            timestamp=datetime.now(),
            source="claude_session",
            payload={
                "cwd": cwd,
                "response_completed": True,
            },
            project=self._detect_project(cwd),
            metadata=metadata,
            interaction_type=InteractionSignalType.RESPONSE_COMPLETED,
            session_id=session_id,
        )

        self._store_interaction(signal)
        with self._lock:
            self._signals.append(signal)

        return signal

    def on_session_ended(self, session_id: str, reason: str, cwd: str) -> InteractionSignal:
        """
        Called by SessionEnd hook when session terminates.

        Triggers session summarization and cross-session learning.
        """
        import uuid

        signal = InteractionSignal(
            id=f"int_{uuid.uuid4().hex[:8]}",
            type=SignalType.COMMAND_EXECUTED,
            timestamp=datetime.now(),
            source="claude_session",
            payload={
                "reason": reason,
                "cwd": cwd,
            },
            project=self._detect_project(cwd),
            interaction_type=InteractionSignalType.SESSION_ENDED,
            session_id=session_id,
        )

        # Summarize and learn from session
        self._summarize_session(session_id)

        self._store_interaction(signal)
        with self._lock:
            self._signals.append(signal)

        return signal

    # === Pattern Detection ===

    def _classify_prompt(self, prompt: str) -> InteractionSignalType:
        """Classify prompt for implicit feedback detection."""
        prompt_lower = prompt.lower().strip()

        # Correction indicators
        correction_phrases = [
            "no, ",
            "that's wrong",
            "actually,",
            "i meant",
            "not what i",
            "try again",
            "that didn't work",
            "wrong file",
            "undo",
            "revert",
            "go back",
            "that broke",
        ]
        if any(phrase in prompt_lower for phrase in correction_phrases):
            return InteractionSignalType.USER_CORRECTION

        # Follow-up indicators (potential ambiguity)
        followup_phrases = [
            "what about",
            "can you also",
            "and then",
            "but what if",
            "why did",
            "explain",
            "show me",
            "how does",
        ]
        if any(phrase in prompt_lower for phrase in followup_phrases):
            return InteractionSignalType.USER_FOLLOWUP

        # Approval indicators
        approval_phrases = [
            "looks good",
            "perfect",
            "thanks",
            "great",
            "yes",
            "that works",
            "commit",
            "push",
            "ship it",
            "done",
        ]
        if any(phrase in prompt_lower for phrase in approval_phrases):
            return InteractionSignalType.USER_APPROVAL

        return InteractionSignalType.PROMPT_RECEIVED

    def _find_similar_prompts(self, prompt_hash: str, prompt: str) -> List[Dict]:
        """Find similar past prompts for pattern detection."""
        # Check exact hash match first
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT payload, project, timestamp
            FROM interactions
            WHERE prompt_hash = ?
            ORDER BY timestamp DESC
            LIMIT 5
        """,
            (prompt_hash,),
        )

        similar = []
        for row in cursor.fetchall():
            similar.append(
                {
                    "payload": json.loads(row[0]),
                    "project": row[1],
                    "timestamp": row[2],
                }
            )

        conn.close()
        return similar

    def _update_tool_pattern(self, tool_name: str, success: bool, project: str) -> None:
        """Update tool usage patterns based on outcomes."""
        pattern_id = f"tool_{tool_name}"

        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT frequency, success_rate, projects FROM patterns WHERE pattern_id = ?",
            (pattern_id,),
        )
        row = cursor.fetchone()

        if row:
            freq = row[0] + 1
            # Rolling average of success rate
            old_rate = row[1]
            new_rate = (old_rate * (freq - 1) + (1.0 if success else 0.0)) / freq
            projects = json.loads(row[2] or "[]")
            if project and project not in projects:
                projects.append(project)

            cursor.execute(
                """
                UPDATE patterns
                SET frequency = ?, success_rate = ?, last_seen = ?, projects = ?
                WHERE pattern_id = ?
            """,
                (
                    freq,
                    new_rate,
                    datetime.now().isoformat(),
                    json.dumps(projects),
                    pattern_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO patterns (pattern_id, pattern_type, description, frequency,
                                       success_rate, last_seen, projects)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    pattern_id,
                    "tool_usage",
                    f"Usage pattern for {tool_name}",
                    1,
                    1.0 if success else 0.0,
                    datetime.now().isoformat(),
                    json.dumps([project] if project else []),
                ),
            )

        conn.commit()
        conn.close()

    def _summarize_session(self, session_id: str) -> None:
        """Summarize a session for cross-session learning."""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        # Get session interactions
        cursor.execute(
            """
            SELECT interaction_type, tool_name, tool_success, payload, project
            FROM interactions
            WHERE session_id = ?
            ORDER BY timestamp
        """,
            (session_id,),
        )

        interactions = cursor.fetchall()
        if not interactions:
            conn.close()
            return

        # Calculate metrics
        prompt_count = sum(1 for i in interactions if i[0] == "prompt_received")
        tool_count = sum(1 for i in interactions if i[0] == "tool_completed")
        successful_tools = sum(1 for i in interactions if i[0] == "tool_completed" and i[2])
        success_rate = successful_tools / tool_count if tool_count > 0 else 0

        # Extract key topics from prompts
        projects = set(i[4] for i in interactions if i[4])

        # Store summary
        cursor.execute(
            """
            INSERT OR REPLACE INTO session_summaries
            (session_id, project, start_time, end_time, prompt_count,
             tool_count, success_rate, key_topics, lessons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_id,
                list(projects)[0] if projects else None,
                (interactions[0][3] if interactions else None),  # First timestamp from payload
                datetime.now().isoformat(),
                prompt_count,
                tool_count,
                success_rate,
                json.dumps(list(projects)),
                json.dumps([]),  # Lessons to be populated by learning system
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Session {session_id} summarized: {prompt_count} prompts, "
            f"{tool_count} tools, {success_rate:.1%} success"
        )

    # === Utility Methods ===

    def _detect_project(self, cwd: str) -> Optional[str]:
        """Detect project name from working directory."""
        if not cwd:
            return None
        path = Path(cwd)
        # Look for common project indicators
        for part in reversed(path.parts):
            if part not in ("src", "lib", "test", "tests", "docs", "."):
                return part
        return path.name

    def _sanitize_payload(self, payload: Dict) -> Dict:
        """Sanitize payload to remove sensitive data and truncate large values."""
        sanitized = {}
        sensitive_keys = ["password", "secret", "token", "key", "credential"]

        for key, value in payload.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + f"... [truncated, {len(value)} chars total]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_payload(value)
            else:
                sanitized[key] = value

        return sanitized

    def _summarize_response(self, response: Dict) -> Dict:
        """Create a summary of tool response for storage."""
        summary = {}
        if isinstance(response, dict):
            summary["success"] = response.get("success", True)
            summary["has_error"] = "error" in str(response).lower()
            if "filePath" in response:
                summary["file_path"] = response["filePath"]
            if "output" in response and isinstance(response["output"], str):
                summary["output_length"] = len(response["output"])
        return summary

    def _store_interaction(self, signal: InteractionSignal) -> None:
        """Store interaction in SQLite database."""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO interactions
            (id, timestamp, session_id, interaction_type, project, payload,
             prompt_hash, tool_name, tool_success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                signal.id,
                signal.timestamp.isoformat(),
                signal.session_id,
                signal.interaction_type.value if signal.interaction_type else None,
                signal.project,
                json.dumps(signal.payload),
                signal.prompt_hash,
                signal.tool_name,
                (1 if signal.tool_success else 0 if signal.tool_success is False else None),
            ),
        )

        conn.commit()
        conn.close()

    # === Query Methods ===

    def get_patterns(
        self, pattern_type: Optional[str] = None, min_frequency: int = 3
    ) -> List[InteractionPattern]:
        """Get detected interaction patterns."""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        query = """
            SELECT pattern_id, pattern_type, description, frequency,
                   success_rate, last_seen, examples, projects
            FROM patterns
            WHERE frequency >= ?
        """
        params = [min_frequency]

        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)

        query += " ORDER BY frequency DESC LIMIT 50"
        cursor.execute(query, params)

        patterns = []
        for row in cursor.fetchall():
            patterns.append(
                InteractionPattern(
                    pattern_id=row[0],
                    pattern_type=row[1],
                    description=row[2],
                    frequency=row[3],
                    success_rate=row[4],
                    last_seen=(datetime.fromisoformat(row[5]) if row[5] else datetime.now()),
                    examples=json.loads(row[6]) if row[6] else [],
                    projects=json.loads(row[7]) if row[7] else [],
                )
            )

        conn.close()
        return patterns

    def get_session_history(self, project: Optional[str] = None, days: int = 30) -> List[Dict]:
        """Get recent session summaries for a project."""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        if project:
            cursor.execute(
                """
                SELECT * FROM session_summaries
                WHERE project = ? AND start_time > ?
                ORDER BY start_time DESC
            """,
                (project, cutoff),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM session_summaries
                WHERE start_time > ?
                ORDER BY start_time DESC
            """,
                (cutoff,),
            )

        columns = [d[0] for d in cursor.description]
        sessions = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return sessions

    def get_tool_success_rates(self) -> Dict[str, Dict]:
        """Get success rates for all tools."""
        patterns = self.get_patterns(pattern_type="tool_usage", min_frequency=1)
        return {
            p.pattern_id.replace("tool_", ""): {
                "frequency": p.frequency,
                "success_rate": p.success_rate,
                "projects": p.projects,
            }
            for p in patterns
        }

    def get_implicit_feedback_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get statistics on implicit feedback signals."""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute(
            """
            SELECT interaction_type, COUNT(*) as count
            FROM interactions
            WHERE timestamp > ? AND interaction_type IN (?, ?, ?, ?)
            GROUP BY interaction_type
        """,
            (
                cutoff,
                InteractionSignalType.USER_CORRECTION.value,
                InteractionSignalType.USER_FOLLOWUP.value,
                InteractionSignalType.USER_APPROVAL.value,
                InteractionSignalType.PROMPT_RECEIVED.value,
            ),
        )

        stats = dict(cursor.fetchall())

        total_prompts = stats.get(InteractionSignalType.PROMPT_RECEIVED.value, 0)
        corrections = stats.get(InteractionSignalType.USER_CORRECTION.value, 0)
        approvals = stats.get(InteractionSignalType.USER_APPROVAL.value, 0)

        conn.close()

        return {
            "total_prompts": total_prompts,
            "corrections": corrections,
            "approvals": approvals,
            "correction_rate": corrections / total_prompts if total_prompts > 0 else 0,
            "approval_rate": approvals / total_prompts if total_prompts > 0 else 0,
            "implicit_success_signal": (
                approvals / (approvals + corrections) if (approvals + corrections) > 0 else 0.5
            ),
        }
