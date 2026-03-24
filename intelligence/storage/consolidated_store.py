#!/usr/bin/env python3
"""
Consolidated Outcome Store - Single SQLite database for all outcome data.

Replaces the scattered outcome storage (feedback.json, outcomes.jsonl,
model_outcomes.jsonl, workflow_outcomes.jsonl, session_outcomes.jsonl)
with a single, indexed SQLite database.

Benefits:
- Single source of truth for all outcomes
- Proper indices for fast queries
- Atomic writes (no corrupt JSONL from crashed appends)
- Foreign-key-like consistency between tables
- Migration-ready schema with version tracking
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cortex.state_paths import get_cortex_dir
except ImportError:
    from state_paths import get_cortex_dir


SCHEMA_VERSION = 2


class ConsolidatedOutcomeStore:
    """
    Single SQLite database for all outcome and feedback data.

    Consolidates:
    - feedback.json → feedback_entries table
    - outcomes.jsonl → recommendation_outcomes table
    - model_outcomes.jsonl → model_outcomes table
    - workflow_outcomes.jsonl → workflow_outcomes table
    - session_outcomes.jsonl → session_outcomes table
    - implicit_feedback.jsonl → implicit_signals table
    - command_metrics (NEW) → command_metrics table
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = get_cortex_dir() / "outcomes.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize all tables with proper indices."""
        with sqlite3.connect(self.db_path) as conn:
            # Schema version tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)

            # Check if we need to initialize
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            current_version = cursor.fetchone()[0] or 0

            if current_version < 1:
                self._apply_schema_v1(conn)
            if current_version < 2:
                self._apply_schema_v2(conn)

            conn.commit()

    def _apply_schema_v1(self, conn: sqlite3.Connection):
        """Apply schema version 1."""

        # Recommendation outcomes (replaces outcomes.jsonl)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                recommendation_id TEXT NOT NULL,
                recommendation_title TEXT,
                recommendation_type TEXT,
                priority TEXT,
                confidence REAL,
                followed INTEGER,
                outcome TEXT,
                notes TEXT,
                context_json TEXT,
                quality_score REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rec_outcomes_type
            ON recommendation_outcomes(recommendation_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rec_outcomes_timestamp
            ON recommendation_outcomes(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rec_outcomes_outcome
            ON recommendation_outcomes(outcome)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rec_outcomes_rec_id
            ON recommendation_outcomes(recommendation_id)
        """)

        # Model outcomes (replaces model_outcomes.jsonl)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_id TEXT,
                task_type TEXT,
                task_description TEXT,
                model_used TEXT,
                model_recommended_by TEXT,
                complexity_classified TEXT,
                confidence REAL,
                outcome TEXT,
                tokens_used INTEGER DEFAULT 0,
                time_seconds REAL DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                project_name TEXT,
                files_json TEXT,
                context_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_outcomes_task_type
            ON model_outcomes(task_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_outcomes_timestamp
            ON model_outcomes(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_outcomes_model
            ON model_outcomes(model_used)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_outcomes_outcome
            ON model_outcomes(outcome)
        """)

        # Workflow outcomes (replaces workflow_outcomes.jsonl)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                workflow_id TEXT,
                workflow_type TEXT,
                priority TEXT,
                estimated_tasks INTEGER,
                estimated_time_minutes REAL,
                estimated_cost REAL,
                actual_tasks_completed INTEGER,
                actual_time_minutes REAL,
                actual_cost REAL,
                success_rate REAL,
                retry_count INTEGER,
                outcome TEXT,
                context_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflow_outcomes_type
            ON workflow_outcomes(workflow_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflow_outcomes_timestamp
            ON workflow_outcomes(timestamp)
        """)

        # Session outcomes (replaces session_outcomes.jsonl)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                duration_minutes REAL,
                tasks_completed INTEGER,
                total_tokens INTEGER,
                total_cost REAL,
                models_used_json TEXT,
                outcome TEXT,
                context_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_outcomes_timestamp
            ON session_outcomes(timestamp)
        """)

        # Implicit feedback signals (replaces implicit_feedback.jsonl)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS implicit_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                recommendation_id TEXT,
                signal_type TEXT,
                similarity REAL,
                time_to_action REAL,
                alternative_taken TEXT,
                context_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_implicit_signal_type
            ON implicit_signals(signal_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_implicit_timestamp
            ON implicit_signals(timestamp)
        """)

        # Command metrics (NEW - captures CLI command performance)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS command_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                command TEXT NOT NULL,
                duration_ms REAL,
                success INTEGER,
                error_message TEXT,
                tokens_used INTEGER DEFAULT 0,
                context_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cmd_metrics_command
            ON command_metrics(command)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cmd_metrics_timestamp
            ON command_metrics(timestamp)
        """)

        # Feedback entries (replaces feedback.json)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_id TEXT,
                action_title TEXT,
                useful INTEGER,
                notes TEXT,
                actual_outcome TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
            ON feedback_entries(timestamp)
        """)

        # Add missing indices for existing databases
        # (These are safe to run even if databases are separate)

        # Record version
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now().isoformat()),
        )

    def _apply_schema_v2(self, conn: sqlite3.Connection):
        """Apply schema version 2 — conversation content + corrections."""

        # Full conversation content (prompts + assistant turns)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                project TEXT,
                git_branch TEXT,
                message_index INTEGER,
                role TEXT NOT NULL,
                content_text TEXT,
                is_correction INTEGER DEFAULT 0,
                correction_target TEXT,
                tools_used_json TEXT,
                files_touched_json TEXT,
                timestamp TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_content_session
            ON conversation_content(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_content_project
            ON conversation_content(project)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_content_correction
            ON conversation_content(is_correction) WHERE is_correction = 1
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_content_timestamp
            ON conversation_content(timestamp)
        """)

        # Correction chains — paired (wrong, correction) for learning
        conn.execute("""
            CREATE TABLE IF NOT EXISTS correction_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                project TEXT,
                wrong_approach TEXT,
                user_correction TEXT,
                correct_approach TEXT,
                files_affected_json TEXT,
                correction_type TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_correction_chains_project
            ON correction_chains(project)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_correction_chains_type
            ON correction_chains(correction_type)
        """)

        # Record version
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (2, datetime.now().isoformat()),
        )

    # ──────────────────────────────────────────────
    # Conversation Content
    # ──────────────────────────────────────────────

    def store_conversation_turn(
        self,
        session_id: str,
        message_index: int,
        role: str,
        content_text: str,
        project: str = "",
        git_branch: str = "",
        is_correction: bool = False,
        correction_target: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        files_touched: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Store a single conversation turn. Returns the row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO conversation_content
                (session_id, project, git_branch, message_index, role, content_text,
                 is_correction, correction_target, tools_used_json, files_touched_json,
                 timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    project,
                    git_branch,
                    message_index,
                    role,
                    content_text,
                    int(is_correction),
                    correction_target,
                    json.dumps(tools_used) if tools_used else None,
                    json.dumps(files_touched) if files_touched else None,
                    timestamp or datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_corrections(
        self,
        project: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all correction turns, optionally filtered by project."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if project:
                rows = conn.execute(
                    """SELECT * FROM conversation_content
                       WHERE is_correction = 1 AND project = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM conversation_content
                       WHERE is_correction = 1
                       ORDER BY timestamp DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_prompts_by_project(
        self,
        project: str,
        role: str = "user",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Get conversation turns for a project."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM conversation_content
                   WHERE project = ? AND role = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (project, role, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def store_correction_chain(
        self,
        session_id: str,
        wrong_approach: str,
        user_correction: str,
        correct_approach: str = "",
        project: str = "",
        files_affected: Optional[List[str]] = None,
        correction_type: str = "general",
    ) -> int:
        """Store a correction chain (wrong → user says no → right). Returns row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO correction_chains
                (session_id, project, wrong_approach, user_correction,
                 correct_approach, files_affected_json, correction_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    project,
                    wrong_approach,
                    user_correction,
                    correct_approach,
                    json.dumps(files_affected) if files_affected else None,
                    correction_type,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_correction_chains(
        self,
        project: Optional[str] = None,
        correction_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get correction chains for learning."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM correction_chains WHERE 1=1"
            params: list = []
            if project:
                query += " AND project = ?"
                params.append(project)
            if correction_type:
                query += " AND correction_type = ?"
                params.append(correction_type)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_session_content(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all turns for a session, ordered by message_index."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM conversation_content
                   WHERE session_id = ?
                   ORDER BY message_index ASC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # Recommendation Outcomes
    # ──────────────────────────────────────────────

    def log_recommendation_outcome(
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
        quality_score: Optional[float] = None,
    ) -> int:
        """Log a recommendation outcome. Returns the row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO recommendation_outcomes
                (timestamp, recommendation_id, recommendation_title, recommendation_type,
                 priority, confidence, followed, outcome, notes, context_json, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    recommendation_id,
                    recommendation_title,
                    recommendation_type,
                    priority,
                    confidence,
                    int(followed),
                    outcome,
                    notes,
                    json.dumps(context) if context else None,
                    quality_score,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def load_recommendation_outcomes(
        self, days: int = 30, recommendation_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load recommendation outcomes from the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if recommendation_type:
                rows = conn.execute(
                    """SELECT * FROM recommendation_outcomes
                       WHERE timestamp >= ? AND recommendation_type = ?
                       ORDER BY timestamp DESC""",
                    (cutoff, recommendation_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM recommendation_outcomes
                       WHERE timestamp >= ?
                       ORDER BY timestamp DESC""",
                    (cutoff,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # Model Outcomes
    # ──────────────────────────────────────────────

    def log_model_outcome(
        self,
        task_id: str,
        task_type: str,
        task_description: str,
        model_used: str,
        outcome: str,
        tokens_used: int = 0,
        time_seconds: float = 0,
        error_count: int = 0,
        estimated_cost_usd: float = 0,
        project_name: str = "",
        files: Optional[List[str]] = None,
        model_recommended_by: str = "rules",
        complexity_classified: str = "moderate",
        confidence: float = 0.6,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Log a model outcome. Returns the row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_outcomes
                (timestamp, task_id, task_type, task_description, model_used,
                 model_recommended_by, complexity_classified, confidence, outcome,
                 tokens_used, time_seconds, error_count, estimated_cost_usd,
                 project_name, files_json, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    task_id,
                    task_type,
                    task_description[:200],
                    model_used,
                    model_recommended_by,
                    complexity_classified,
                    confidence,
                    outcome,
                    tokens_used,
                    time_seconds,
                    error_count,
                    estimated_cost_usd,
                    project_name,
                    json.dumps(files) if files else None,
                    json.dumps(context) if context else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def load_model_outcomes(
        self, days: int = 30, task_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load model outcomes from the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if task_type:
                rows = conn.execute(
                    """SELECT * FROM model_outcomes
                       WHERE timestamp >= ? AND task_type = ?
                       ORDER BY timestamp DESC""",
                    (cutoff, task_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM model_outcomes
                       WHERE timestamp >= ?
                       ORDER BY timestamp DESC""",
                    (cutoff,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────
    # Command Metrics
    # ──────────────────────────────────────────────

    def log_command_metric(
        self,
        command: str,
        duration_ms: float,
        success: bool,
        error_message: Optional[str] = None,
        tokens_used: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Log a CLI command execution metric. Returns the row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO command_metrics
                (timestamp, command, duration_ms, success, error_message,
                 tokens_used, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    command,
                    duration_ms,
                    int(success),
                    error_message,
                    tokens_used,
                    json.dumps(context) if context else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def load_command_metrics(
        self, days: int = 30, command: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load command metrics from the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if command:
                rows = conn.execute(
                    """SELECT * FROM command_metrics
                       WHERE timestamp >= ? AND command = ?
                       ORDER BY timestamp DESC""",
                    (cutoff, command),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM command_metrics
                       WHERE timestamp >= ?
                       ORDER BY timestamp DESC""",
                    (cutoff,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_command_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get aggregated command performance statistics."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT command,
                       COUNT(*) as total,
                       SUM(success) as successes,
                       AVG(duration_ms) as avg_duration_ms,
                       MAX(duration_ms) as max_duration_ms,
                       SUM(tokens_used) as total_tokens
                FROM command_metrics
                WHERE timestamp >= ?
                GROUP BY command
                ORDER BY total DESC
                """,
                (cutoff,),
            ).fetchall()
        return {row["command"]: dict(row) for row in rows}

    # ──────────────────────────────────────────────
    # Implicit Signals
    # ──────────────────────────────────────────────

    def log_implicit_signal(
        self,
        recommendation_id: str,
        signal_type: str,
        similarity: float,
        time_to_action: Optional[float] = None,
        alternative_taken: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> int:
        """Log an implicit feedback signal. Returns the row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO implicit_signals
                (timestamp, recommendation_id, signal_type, similarity,
                 time_to_action, alternative_taken, context_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    recommendation_id,
                    signal_type,
                    similarity,
                    time_to_action,
                    alternative_taken,
                    json.dumps(context) if context else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    # ──────────────────────────────────────────────
    # Feedback Entries
    # ──────────────────────────────────────────────

    def log_feedback(
        self,
        action_title: str,
        useful: bool,
        action_id: Optional[str] = None,
        notes: Optional[str] = None,
        actual_outcome: Optional[str] = None,
    ) -> int:
        """Log a feedback entry. Returns the row ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO feedback_entries
                (timestamp, action_id, action_title, useful, notes, actual_outcome)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    action_id,
                    action_title,
                    int(useful),
                    notes,
                    actual_outcome,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback_entries").fetchone()[0]
            useful = conn.execute(
                "SELECT COUNT(*) FROM feedback_entries WHERE useful = 1"
            ).fetchone()[0]
        return {
            "total_entries": total,
            "useful_count": useful,
            "not_useful_count": total - useful,
            "useful_rate": useful / total if total > 0 else 0.0,
        }

    # ──────────────────────────────────────────────
    # Migration: Import legacy data
    # ──────────────────────────────────────────────

    def migrate_legacy_data(self) -> Dict[str, int]:
        """
        Import data from legacy JSONL/JSON files into consolidated store.
        Returns count of migrated records per type.
        """
        cortex_dir = get_cortex_dir()
        counts = {}

        # Migrate feedback.json
        feedback_file = cortex_dir / "feedback.json"
        if feedback_file.exists():
            try:
                with open(feedback_file) as f:
                    entries = json.load(f)
                for entry in entries:
                    self.log_feedback(
                        action_title=entry.get("action_title", ""),
                        useful=entry.get("useful", False),
                        action_id=entry.get("action_id"),
                        notes=entry.get("notes"),
                        actual_outcome=entry.get("actual_outcome"),
                    )
                counts["feedback"] = len(entries)
            except (json.JSONDecodeError, IOError):
                counts["feedback"] = 0

        # Migrate outcomes.jsonl
        outcomes_file = cortex_dir / "outcomes.jsonl"
        if outcomes_file.exists():
            count = 0
            try:
                with open(outcomes_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        self.log_recommendation_outcome(
                            recommendation_id=data.get("recommendation_id", ""),
                            recommendation_title=data.get("recommendation_title", ""),
                            recommendation_type=data.get("recommendation_type", ""),
                            priority=data.get("priority", "C"),
                            confidence=data.get("confidence", 0.5),
                            followed=data.get("followed", False),
                            outcome=data.get("outcome", "unknown"),
                            notes=data.get("notes"),
                            context=data.get("context"),
                        )
                        count += 1
            except (json.JSONDecodeError, IOError):
                pass
            counts["recommendation_outcomes"] = count

        # Migrate model_outcomes.jsonl
        model_file = cortex_dir / "model_outcomes.jsonl"
        if model_file.exists():
            count = 0
            try:
                with open(model_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        self.log_model_outcome(
                            task_id=data.get("task_id", ""),
                            task_type=data.get("task_type", ""),
                            task_description=data.get("task_description", ""),
                            model_used=data.get("model_used", ""),
                            outcome=data.get("outcome", "unknown"),
                            tokens_used=data.get("tokens_used", 0),
                            time_seconds=data.get("time_seconds", 0),
                            error_count=data.get("error_count", 0),
                            estimated_cost_usd=data.get("estimated_cost_usd", 0),
                            project_name=data.get("project_name", ""),
                            files=data.get("files_touched"),
                            model_recommended_by=data.get("model_recommended_by", "rules"),
                            complexity_classified=data.get("complexity_classified", "moderate"),
                            confidence=data.get("confidence", 0.6),
                        )
                        count += 1
            except (json.JSONDecodeError, IOError):
                pass
            counts["model_outcomes"] = count

        # Migrate implicit_feedback.jsonl
        implicit_file = cortex_dir / "implicit_feedback.jsonl"
        if implicit_file.exists():
            count = 0
            try:
                with open(implicit_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        self.log_implicit_signal(
                            recommendation_id=data.get("recommendation_id", ""),
                            signal_type=data.get("signal_type", ""),
                            similarity=data.get("similarity", 0.0),
                            time_to_action=data.get("time_to_action"),
                            alternative_taken=data.get("alternative_taken"),
                            context=data.get("context"),
                        )
                        count += 1
            except (json.JSONDecodeError, IOError):
                pass
            counts["implicit_signals"] = count

        return counts

    # ──────────────────────────────────────────────
    # Storage Info
    # ──────────────────────────────────────────────

    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage backend information."""
        with sqlite3.connect(self.db_path) as conn:
            tables = {}
            for table in [
                "recommendation_outcomes",
                "model_outcomes",
                "workflow_outcomes",
                "session_outcomes",
                "implicit_signals",
                "command_metrics",
                "feedback_entries",
                "conversation_content",
                "correction_chains",
            ]:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    tables[table] = count
                except sqlite3.OperationalError:
                    tables[table] = 0

        return {
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "tables": tables,
            "schema_version": SCHEMA_VERSION,
        }


# ──────────────────────────────────────────────
# Singleton access
# ──────────────────────────────────────────────

_store_instance: Optional[ConsolidatedOutcomeStore] = None


def get_consolidated_store() -> ConsolidatedOutcomeStore:
    """Get the singleton consolidated store instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = ConsolidatedOutcomeStore()
    return _store_instance


def set_consolidated_store(store: ConsolidatedOutcomeStore) -> None:
    """Set the store instance (for testing)."""
    global _store_instance
    _store_instance = store
