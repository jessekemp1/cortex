"""
SQLite database for Cortex orchestration system.

Provides persistent storage for:
- Tasks (unified task model)
- Worker states (agent capacity tracking)
- Trace events (audit trail)
- Validation criteria (test requirements)
- Anti-pattern alerts (validated-but-undeployed detection)

Schema designed for performance with proper indexes for common queries.

Database location: ~/.cortex/orchestration.db
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import (
    ExecutionBackend,
    Task,
    TaskPhase,
    TaskPriority,
    TaskStatus,
    TraceEvent,
    TraceEventType,
    ValidationCriteria,
    WorkerRole,
    WorkerState,
)

logger = logging.getLogger(__name__)


class OrchestrationDatabase:
    """
    SQLite database for orchestration system.

    Features:
    - WAL mode for concurrent access
    - Automatic schema migration
    - Batch operations for performance
    - Proper indexes for common queries
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database (defaults to ~/.cortex/orchestration.db)
        """
        if db_path is None:
            cortex_dir = Path.home() / ".cortex"
            cortex_dir.mkdir(exist_ok=True)
            db_path = cortex_dir / "orchestration.db"

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema with all tables and indexes."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Tasks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                deadline TEXT,
                phase TEXT NOT NULL,
                status TEXT NOT NULL,
                blocked_by TEXT DEFAULT '[]',
                blocks TEXT DEFAULT '[]',
                prompt TEXT,
                context TEXT DEFAULT '{}',
                files_affected TEXT DEFAULT '[]',
                estimated_input_tokens INTEGER DEFAULT 0,
                estimated_output_tokens INTEGER DEFAULT 4000,
                actual_input_tokens INTEGER DEFAULT 0,
                actual_output_tokens INTEGER DEFAULT 0,
                execution_mode TEXT,
                execution_backend TEXT,
                batch_id TEXT,
                assigned_agent TEXT,
                result TEXT,
                error TEXT,
                validation_passed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                tags TEXT DEFAULT '[]',
                source TEXT,
                project TEXT
            )
        """)

        # Validation criteria table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validation_criteria (
                task_id TEXT PRIMARY KEY,
                requires_unit_tests INTEGER DEFAULT 0,
                requires_integration_tests INTEGER DEFAULT 0,
                requires_e2e_tests INTEGER DEFAULT 0,
                min_coverage_percent REAL,
                test_commands TEXT DEFAULT '[]',
                success_patterns TEXT DEFAULT '[]',
                failure_patterns TEXT DEFAULT '[]',
                required_files TEXT DEFAULT '[]',
                max_execution_seconds INTEGER,
                custom_validator TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)

        # Worker state table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS worker_states (
                worker_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                max_concurrent_tasks INTEGER DEFAULT 3,
                current_task_count INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                unavailable_reason TEXT,
                total_tasks_completed INTEGER DEFAULT 0,
                total_tasks_failed INTEGER DEFAULT 0,
                average_task_duration_minutes REAL DEFAULT 0.0,
                assigned_task_ids TEXT DEFAULT '[]',
                specialties TEXT DEFAULT '[]',
                last_task_started_at TEXT,
                last_task_completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Trace events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                task_id TEXT,
                worker_id TEXT,
                message TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                phase TEXT,
                backend TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(worker_id) REFERENCES worker_states(worker_id) ON DELETE SET NULL
            )
        """)

        # Retry configs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retry_configs (
                task_id TEXT PRIMARY KEY,
                max_retries INTEGER DEFAULT 3,
                current_retry_count INTEGER DEFAULT 0,
                strategy TEXT NOT NULL,
                base_delay_seconds INTEGER DEFAULT 60,
                backoff_multiplier REAL DEFAULT 2.0,
                max_delay_seconds INTEGER DEFAULT 3600,
                last_retry_at TEXT,
                failure_type TEXT,
                escalated INTEGER DEFAULT 0,
                escalation_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)

        # Anti-pattern alerts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anti_pattern_alerts (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                project TEXT NOT NULL,
                validated_item TEXT NOT NULL,
                validation_source TEXT NOT NULL,
                validation_date TEXT NOT NULL,
                production_item TEXT,
                production_source TEXT,
                improvement_metrics TEXT DEFAULT '{}',
                recommendation_priority TEXT,
                evidence TEXT DEFAULT '[]',
                suggested_action TEXT NOT NULL,
                estimated_effort TEXT,
                blocking_factors TEXT DEFAULT '[]',
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                resolution_notes TEXT
            )
        """)

        # Anomalies table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                anomaly_id TEXT PRIMARY KEY,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                metric_value REAL NOT NULL,
                threshold_value REAL NOT NULL,
                affected_entities TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                remediation TEXT NOT NULL,
                auto_actionable INTEGER DEFAULT 0,
                auto_action_command TEXT,
                first_seen TEXT,
                occurrence_count INTEGER DEFAULT 1
            )
        """)

        # Create indexes for performance
        indexes = [
            # Task indexes
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_phase ON tasks(phase)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_execution_backend ON tasks(execution_backend)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_agent ON tasks(assigned_agent)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project)",
            # Worker indexes
            "CREATE INDEX IF NOT EXISTS idx_workers_role ON worker_states(role)",
            "CREATE INDEX IF NOT EXISTS idx_workers_available ON worker_states(is_available)",
            # Trace event indexes
            "CREATE INDEX IF NOT EXISTS idx_trace_events_timestamp ON trace_events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_trace_events_task_id ON trace_events(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_trace_events_worker_id ON trace_events(worker_id)",
            "CREATE INDEX IF NOT EXISTS idx_trace_events_type ON trace_events(event_type)",
            # Retry config indexes
            "CREATE INDEX IF NOT EXISTS idx_retry_configs_escalated ON retry_configs(escalated)",
            "CREATE INDEX IF NOT EXISTS idx_retry_configs_failure_type ON retry_configs(failure_type)",
            # Anomaly indexes
            "CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type)",
            "CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity)",
            "CREATE INDEX IF NOT EXISTS idx_anomalies_detected_at ON anomalies(detected_at)",
            # Anti-pattern alert indexes
            "CREATE INDEX IF NOT EXISTS idx_alerts_project ON anti_pattern_alerts(project)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON anti_pattern_alerts(severity)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON anti_pattern_alerts(resolved_at)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_pattern_type ON anti_pattern_alerts(pattern_type)",
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

        conn.commit()
        conn.close()

        logger.info(f"Initialized orchestration database: {self.db_path}")

    # ==================== Task Operations ====================

    def create_task(self, task: Task, validation: Optional[ValidationCriteria] = None) -> None:
        """
        Create a new task in the database.

        Args:
            task: Task to create
            validation: Optional validation criteria for the task
        """
        conn = sqlite3.connect(self.db_path)

        task_dict = task.to_dict()
        # Add execution_backend field (not in base Task model)
        task_dict["execution_backend"] = None

        conn.execute(
            """
            INSERT INTO tasks VALUES (
                :id, :title, :description, :priority, :deadline, :phase, :status,
                :blocked_by, :blocks, :prompt, :context, :files_affected,
                :estimated_input_tokens, :estimated_output_tokens,
                :actual_input_tokens, :actual_output_tokens,
                :execution_mode, :execution_backend, :batch_id, :assigned_agent,
                :result, :error, :validation_passed,
                :created_at, :started_at, :completed_at, :tags, :source, :project
            )
        """,
            {
                **task_dict,
                "blocked_by": json.dumps(task.blocked_by),
                "blocks": json.dumps(task.blocks),
                "context": json.dumps(task.context),
                "files_affected": json.dumps(task.files_affected),
                "tags": json.dumps(task.tags),
            },
        )

        # Add validation criteria if provided
        if validation:
            self._save_validation_criteria(conn, task.id, validation)

        conn.commit()
        conn.close()

    def _save_validation_criteria(
        self, conn: sqlite3.Connection, task_id: str, validation: ValidationCriteria
    ) -> None:
        """Save validation criteria for a task."""
        val_dict = validation.to_dict()
        conn.execute(
            """
            INSERT OR REPLACE INTO validation_criteria VALUES (
                :task_id, :requires_unit_tests, :requires_integration_tests,
                :requires_e2e_tests, :min_coverage_percent, :test_commands,
                :success_patterns, :failure_patterns, :required_files,
                :max_execution_seconds, :custom_validator
            )
        """,
            {
                "task_id": task_id,
                **val_dict,
                "requires_unit_tests": int(val_dict["requires_unit_tests"]),
                "requires_integration_tests": int(val_dict["requires_integration_tests"]),
                "requires_e2e_tests": int(val_dict["requires_e2e_tests"]),
                "test_commands": json.dumps(val_dict["test_commands"]),
                "success_patterns": json.dumps(val_dict["success_patterns"]),
                "failure_patterns": json.dumps(val_dict["failure_patterns"]),
                "required_files": json.dumps(val_dict["required_files"]),
            },
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_task(dict(row))
        return None

    def get_validation_criteria(self, task_id: str) -> Optional[ValidationCriteria]:
        """Get validation criteria for a task."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT * FROM validation_criteria WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            row_dict = dict(row)
            # Parse JSON fields
            row_dict["test_commands"] = json.loads(row_dict["test_commands"])
            row_dict["success_patterns"] = json.loads(row_dict["success_patterns"])
            row_dict["failure_patterns"] = json.loads(row_dict["failure_patterns"])
            row_dict["required_files"] = json.loads(row_dict["required_files"])
            # Convert booleans (SQLite stores as INTEGER 0/1)
            row_dict["requires_unit_tests"] = bool(row_dict.get("requires_unit_tests", 0))
            row_dict["requires_integration_tests"] = bool(
                row_dict.get("requires_integration_tests", 0)
            )
            row_dict["requires_e2e_tests"] = bool(row_dict.get("requires_e2e_tests", 0))
            # Remove task_id from dict
            row_dict.pop("task_id", None)
            return ValidationCriteria.from_dict(row_dict)
        return None

    def update_task(self, task: Task) -> None:
        """Update an existing task."""
        conn = sqlite3.connect(self.db_path)

        task_dict = task.to_dict()

        conn.execute(
            """
            UPDATE tasks SET
                title = :title,
                description = :description,
                priority = :priority,
                deadline = :deadline,
                phase = :phase,
                status = :status,
                blocked_by = :blocked_by,
                blocks = :blocks,
                prompt = :prompt,
                context = :context,
                files_affected = :files_affected,
                estimated_input_tokens = :estimated_input_tokens,
                estimated_output_tokens = :estimated_output_tokens,
                actual_input_tokens = :actual_input_tokens,
                actual_output_tokens = :actual_output_tokens,
                execution_mode = :execution_mode,
                batch_id = :batch_id,
                assigned_agent = :assigned_agent,
                result = :result,
                error = :error,
                validation_passed = :validation_passed,
                started_at = :started_at,
                completed_at = :completed_at,
                tags = :tags,
                source = :source,
                project = :project
            WHERE id = :id
        """,
            {
                **task_dict,
                "blocked_by": json.dumps(task.blocked_by),
                "blocks": json.dumps(task.blocks),
                "context": json.dumps(task.context),
                "files_affected": json.dumps(task.files_affected),
                "tags": json.dumps(task.tags),
            },
        )

        conn.commit()
        conn.close()

    def update_task_phase(self, task_id: str, phase: TaskPhase) -> None:
        """Update task phase (convenience method)."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE tasks SET phase = ? WHERE id = ?",
            (phase.value, task_id),
        )
        conn.commit()
        conn.close()

    def update_task_execution_backend(self, task_id: str, backend: ExecutionBackend) -> None:
        """Update task execution backend."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE tasks SET execution_backend = ? WHERE id = ?",
            (backend.value, task_id),
        )
        conn.commit()
        conn.close()

    def get_ready_tasks(self, limit: int = 50) -> List[Task]:
        """
        Get tasks ready to execute (not blocked, not terminal).

        Returns tasks that:
        - Status is PENDING
        - Not blocked by dependencies
        - Ordered by priority (A > B > C) and created_at
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = 'pending'
            AND phase NOT IN ('completed', 'failed')
            ORDER BY
                CASE priority
                    WHEN 'A' THEN 1
                    WHEN 'B' THEN 2
                    WHEN 'C' THEN 3
                    ELSE 4
                END,
                created_at ASC
            LIMIT ?
        """,
            (limit,),
        )

        tasks = [self._row_to_task(dict(row)) for row in cursor.fetchall()]
        conn.close()

        # Filter out blocked tasks (those with non-empty blocked_by)
        ready_tasks = [t for t in tasks if not t.is_blocked]
        return ready_tasks

    def get_blocked_tasks(self) -> List[Task]:
        """Get tasks that are blocked by dependencies."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT * FROM tasks
            WHERE status IN ('pending', 'blocked')
            AND phase NOT IN ('completed', 'failed')
        """)

        tasks = [self._row_to_task(dict(row)) for row in cursor.fetchall()]
        conn.close()

        # Filter to only those with dependencies
        blocked_tasks = [t for t in tasks if t.is_blocked]
        return blocked_tasks

    def get_running_tasks(self) -> List[Task]:
        """Get currently running tasks."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM tasks WHERE status = 'running' ORDER BY started_at ASC"
        )

        tasks = [self._row_to_task(dict(row)) for row in cursor.fetchall()]
        conn.close()
        return tasks

    def get_completed_task_ids(self) -> Set[str]:
        """Get set of completed task IDs (for dependency checking)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT id FROM tasks WHERE phase = 'completed' AND status = 'completed'"
        )
        task_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return task_ids

    def unblock_dependent_tasks(self, completed_task_id: str) -> List[str]:
        """
        Unblock tasks that depend on the completed task.

        Returns list of task IDs that were unblocked.
        """
        blocked_tasks = self.get_blocked_tasks()
        unblocked_ids = []

        for task in blocked_tasks:
            if completed_task_id in task.blocked_by:
                task.unblock(completed_task_id)
                self.update_task(task)
                unblocked_ids.append(task.id)

        return unblocked_ids

    def get_tasks_by_status(self, status: TaskStatus, limit: int = 100) -> List[Task]:
        """Get tasks by status."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status.value, limit),
        )

        tasks = [self._row_to_task(dict(row)) for row in cursor.fetchall()]
        conn.close()
        return tasks

    def get_tasks_by_phase(self, phase: TaskPhase, limit: int = 100) -> List[Task]:
        """Get tasks by phase."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM tasks WHERE phase = ? ORDER BY created_at DESC LIMIT ?",
            (phase.value, limit),
        )

        tasks = [self._row_to_task(dict(row)) for row in cursor.fetchall()]
        conn.close()
        return tasks

    def _row_to_task(self, row: Dict[str, Any]) -> Task:
        """Convert database row to Task object."""
        # Parse JSON fields
        row["blocked_by"] = json.loads(row.get("blocked_by", "[]"))
        row["blocks"] = json.loads(row.get("blocks", "[]"))
        row["context"] = json.loads(row.get("context", "{}"))
        row["files_affected"] = json.loads(row.get("files_affected", "[]"))
        row["tags"] = json.loads(row.get("tags", "[]"))

        # Convert booleans
        row["validation_passed"] = bool(row.get("validation_passed", 0))

        # Remove execution_backend field (not in Task model)
        row.pop("execution_backend", None)

        return Task.from_dict(row)

    # ==================== Worker Operations ====================

    def create_worker(self, worker: WorkerState) -> None:
        """Create a new worker in the database."""
        conn = sqlite3.connect(self.db_path)

        worker_dict = worker.to_dict()

        conn.execute(
            """
            INSERT INTO worker_states VALUES (
                :worker_id, :role, :max_concurrent_tasks, :current_task_count,
                :is_available, :unavailable_reason, :total_tasks_completed,
                :total_tasks_failed, :average_task_duration_minutes,
                :assigned_task_ids, :specialties, :last_task_started_at,
                :last_task_completed_at, :created_at, :updated_at
            )
        """,
            {
                **worker_dict,
                "is_available": int(worker.is_available),
                "assigned_task_ids": json.dumps(worker.assigned_task_ids),
                "specialties": json.dumps(worker.specialties),
            },
        )

        conn.commit()
        conn.close()

    def get_worker(self, worker_id: str) -> Optional[WorkerState]:
        """Get worker by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT * FROM worker_states WHERE worker_id = ?", (worker_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_worker(dict(row))
        return None

    def update_worker(self, worker: WorkerState) -> None:
        """Update an existing worker."""
        conn = sqlite3.connect(self.db_path)

        worker_dict = worker.to_dict()

        conn.execute(
            """
            UPDATE worker_states SET
                role = :role,
                max_concurrent_tasks = :max_concurrent_tasks,
                current_task_count = :current_task_count,
                is_available = :is_available,
                unavailable_reason = :unavailable_reason,
                total_tasks_completed = :total_tasks_completed,
                total_tasks_failed = :total_tasks_failed,
                average_task_duration_minutes = :average_task_duration_minutes,
                assigned_task_ids = :assigned_task_ids,
                specialties = :specialties,
                last_task_started_at = :last_task_started_at,
                last_task_completed_at = :last_task_completed_at,
                updated_at = :updated_at
            WHERE worker_id = :worker_id
        """,
            {
                **worker_dict,
                "is_available": int(worker.is_available),
                "assigned_task_ids": json.dumps(worker.assigned_task_ids),
                "specialties": json.dumps(worker.specialties),
            },
        )

        conn.commit()
        conn.close()

    def get_available_workers(self, role: Optional[WorkerRole] = None) -> List[WorkerState]:
        """Get available workers, optionally filtered by role."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        if role:
            cursor = conn.execute(
                """
                SELECT * FROM worker_states
                WHERE is_available = 1 AND role = ?
                ORDER BY current_task_count ASC
            """,
                (role.value,),
            )
        else:
            cursor = conn.execute("""
                SELECT * FROM worker_states
                WHERE is_available = 1
                ORDER BY current_task_count ASC
            """)

        workers = [self._row_to_worker(dict(row)) for row in cursor.fetchall()]
        conn.close()
        return workers

    def _row_to_worker(self, row: Dict[str, Any]) -> WorkerState:
        """Convert database row to WorkerState object."""
        # Parse JSON fields
        row["assigned_task_ids"] = json.loads(row.get("assigned_task_ids", "[]"))
        row["specialties"] = json.loads(row.get("specialties", "[]"))

        # Convert boolean
        row["is_available"] = bool(row.get("is_available", 1))

        return WorkerState.from_dict(row)

    # ==================== Trace Event Operations ====================

    def add_trace_event(self, event: TraceEvent) -> None:
        """Add a trace event to the audit log."""
        conn = sqlite3.connect(self.db_path)

        event_dict = event.to_dict()

        conn.execute(
            """
            INSERT INTO trace_events VALUES (
                :event_id, :event_type, :timestamp, :task_id, :worker_id,
                :message, :details, :phase, :backend
            )
        """,
            event_dict,
        )

        conn.commit()
        conn.close()

    def get_trace_events(
        self,
        task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        event_type: Optional[TraceEventType] = None,
        limit: int = 100,
    ) -> List[TraceEvent]:
        """Get trace events with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM trace_events WHERE 1=1"
        params = []

        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)

        if worker_id:
            query += " AND worker_id = ?"
            params.append(worker_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        events = [TraceEvent.from_dict(dict(row)) for row in cursor.fetchall()]
        conn.close()

        return events

    # ==================== Migration from existing databases ====================

    def migrate_from_batch_queue(self, batch_queue_db_path: Path) -> int:
        """
        Migrate tasks from existing batch_queue.db.

        Args:
            batch_queue_db_path: Path to existing batch_queue.db

        Returns:
            Number of tasks migrated
        """
        if not batch_queue_db_path.exists():
            logger.warning(f"Batch queue database not found: {batch_queue_db_path}")
            return 0

        source_conn = sqlite3.connect(batch_queue_db_path)
        source_conn.row_factory = sqlite3.Row

        cursor = source_conn.execute("SELECT * FROM batch_tasks")
        migrated = 0

        for row in cursor.fetchall():
            row_dict = dict(row)

            # Map BatchTask fields to Task fields
            task = Task(
                id=row_dict["task_id"],
                title=row_dict["description"][:100],  # Truncate for title
                description=row_dict["description"],
                priority=self._map_priority(row_dict["priority"]),
                phase=self._map_task_state_to_phase(row_dict["state"]),
                status=self._map_task_state_to_status(row_dict["state"]),
                created_at=datetime.fromisoformat(row_dict["created_at"]),
                started_at=(
                    datetime.fromisoformat(row_dict["started_at"])
                    if row_dict["started_at"]
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(row_dict["completed_at"])
                    if row_dict["completed_at"]
                    else None
                ),
                context={
                    "command": row_dict["command"],
                    "task_type": row_dict["task_type"],
                    "exit_code": row_dict.get("exit_code"),
                    "stdout": row_dict.get("stdout", ""),
                    "stderr": row_dict.get("stderr", ""),
                },
                tags=[row_dict["task_type"]],
                source="batch_migration",
            )

            try:
                self.create_task(task)
                migrated += 1
            except sqlite3.IntegrityError:
                # Task already exists, skip
                pass

        source_conn.close()
        logger.info(f"Migrated {migrated} tasks from batch_queue.db")
        return migrated

    def _map_priority(self, old_priority: str) -> TaskPriority:
        """Map old priority strings to new TaskPriority enum."""
        mapping = {
            "immediate": TaskPriority.A,
            "high": TaskPriority.A,
            "normal": TaskPriority.B,
            "low": TaskPriority.C,
        }
        return mapping.get(old_priority, TaskPriority.B)

    def _map_task_state_to_phase(self, state: str) -> TaskPhase:
        """Map old TaskState to new TaskPhase."""
        mapping = {
            "pending": TaskPhase.QUEUED,
            "scheduled": TaskPhase.QUEUED,
            "running": TaskPhase.IMPLEMENTING,
            "completed": TaskPhase.COMPLETED,
            "failed": TaskPhase.FAILED,
            "cancelled": TaskPhase.FAILED,
        }
        return mapping.get(state, TaskPhase.QUEUED)

    def _map_task_state_to_status(self, state: str) -> TaskStatus:
        """Map old TaskState to new TaskStatus."""
        mapping = {
            "pending": TaskStatus.PENDING,
            "scheduled": TaskStatus.SCHEDULED,
            "running": TaskStatus.RUNNING,
            "completed": TaskStatus.COMPLETED,
            "failed": TaskStatus.FAILED,
            "cancelled": TaskStatus.FAILED,
        }
        return mapping.get(state, TaskStatus.PENDING)

    # ==================== Anomaly Operations ====================

    def save_anomalies(self, anomalies: List[Any]) -> None:
        """
        Save anomalies to database.

        Args:
            anomalies: List of OrchestrationAnomaly objects
        """
        conn = sqlite3.connect(self.db_path)

        for anomaly in anomalies:
            anomaly_dict = anomaly.to_dict()

            conn.execute(
                """
                INSERT OR REPLACE INTO anomalies VALUES (
                    :anomaly_id, :anomaly_type, :severity, :detected_at,
                    :title, :description, :metric_value, :threshold_value,
                    :affected_entities, :metadata, :remediation,
                    :auto_actionable, :auto_action_command,
                    :first_seen, :occurrence_count
                )
            """,
                anomaly_dict,
            )

        conn.commit()
        conn.close()

    def get_recent_anomalies(self, days: int = 7) -> List[Any]:
        """
        Get recent anomalies from database.

        Args:
            days: Number of days to look back

        Returns:
            List of OrchestrationAnomaly objects
        """
        from datetime import timedelta

        from .anomaly_detector import OrchestrationAnomaly

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = conn.execute(
            """
            SELECT * FROM anomalies
            WHERE detected_at >= ?
            ORDER BY detected_at DESC
        """,
            (cutoff,),
        )

        anomalies = [OrchestrationAnomaly.from_dict(dict(row)) for row in cursor.fetchall()]
        conn.close()

        return anomalies

    def get_anomaly_trend(self, anomaly_type: str, days: int) -> Dict[str, Any]:
        """
        Get trend data for a specific anomaly type.

        Args:
            anomaly_type: Type of anomaly (as string)
            days: Number of days to analyze

        Returns:
            Dictionary with trend statistics
        """
        from datetime import timedelta

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        # Get count by day
        cursor = conn.execute(
            """
            SELECT
                DATE(detected_at) as day,
                COUNT(*) as count,
                AVG(metric_value) as avg_metric,
                MAX(severity) as max_severity
            FROM anomalies
            WHERE anomaly_type = ? AND detected_at >= ?
            GROUP BY DATE(detected_at)
            ORDER BY day ASC
        """,
            (anomaly_type, cutoff),
        )

        daily_data = [dict(row) for row in cursor.fetchall()]

        # Get overall stats
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total_occurrences,
                COUNT(DISTINCT anomaly_id) as unique_anomalies,
                AVG(metric_value) as avg_metric_value,
                MIN(detected_at) as first_occurrence,
                MAX(detected_at) as last_occurrence
            FROM anomalies
            WHERE anomaly_type = ? AND detected_at >= ?
        """,
            (anomaly_type, cutoff),
        )

        overall_stats = dict(cursor.fetchone())

        conn.close()

        return {
            "anomaly_type": anomaly_type,
            "days_analyzed": days,
            "daily_data": daily_data,
            "overall_stats": overall_stats,
        }

    # ==================== Statistics ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)

        stats = {}

        # Task counts by status
        cursor = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM tasks
            GROUP BY status
        """)
        stats["tasks_by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Task counts by phase
        cursor = conn.execute("""
            SELECT phase, COUNT(*) as count
            FROM tasks
            GROUP BY phase
        """)
        stats["tasks_by_phase"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Worker counts
        cursor = conn.execute("SELECT COUNT(*) FROM worker_states")
        stats["total_workers"] = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM worker_states WHERE is_available = 1")
        stats["available_workers"] = cursor.fetchone()[0]

        # Trace event count
        cursor = conn.execute("SELECT COUNT(*) FROM trace_events")
        stats["total_trace_events"] = cursor.fetchone()[0]

        # Retry config counts
        cursor = conn.execute("SELECT COUNT(*) FROM retry_configs")
        stats["total_retry_configs"] = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM retry_configs WHERE escalated = 1")
        stats["escalated_tasks"] = cursor.fetchone()[0]

        conn.close()
        return stats

    # ==================== Retry Config Operations ====================

    def create_retry_config(self, task_id: str, config: "RetryConfig") -> None:
        """
        Create a retry configuration for a task.

        Args:
            task_id: Task identifier
            config: RetryConfig to save
        """

        conn = sqlite3.connect(self.db_path)

        config_dict = config.to_dict()

        conn.execute(
            """
            INSERT INTO retry_configs VALUES (
                :task_id, :max_retries, :current_retry_count, :strategy,
                :base_delay_seconds, :backoff_multiplier, :max_delay_seconds,
                :last_retry_at, :failure_type, :escalated, :escalation_reason,
                :created_at, :updated_at
            )
        """,
            {
                "task_id": task_id,
                **config_dict,
                "escalated": 1 if config.escalated else 0,
            },
        )

        conn.commit()
        conn.close()

        logger.debug(f"Created retry config for task {task_id}")

    def get_retry_config(self, task_id: str) -> Optional["RetryConfig"]:
        """
        Get retry configuration for a task.

        Args:
            task_id: Task identifier

        Returns:
            RetryConfig if exists, None otherwise
        """
        from .retry_handler import RetryConfig  # Import here to avoid circular dependency

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT * FROM retry_configs WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        # Convert row to dict
        data = dict(row)
        data["escalated"] = bool(data["escalated"])

        return RetryConfig.from_dict(data)

    def update_retry_config(self, task_id: str, config: "RetryConfig") -> None:
        """
        Update retry configuration for a task.

        Args:
            task_id: Task identifier
            config: Updated RetryConfig
        """

        conn = sqlite3.connect(self.db_path)

        config_dict = config.to_dict()

        conn.execute(
            """
            UPDATE retry_configs SET
                max_retries = :max_retries,
                current_retry_count = :current_retry_count,
                strategy = :strategy,
                base_delay_seconds = :base_delay_seconds,
                backoff_multiplier = :backoff_multiplier,
                max_delay_seconds = :max_delay_seconds,
                last_retry_at = :last_retry_at,
                failure_type = :failure_type,
                escalated = :escalated,
                escalation_reason = :escalation_reason,
                updated_at = :updated_at
            WHERE task_id = :task_id
        """,
            {
                "task_id": task_id,
                **config_dict,
                "escalated": 1 if config.escalated else 0,
            },
        )

        conn.commit()
        conn.close()

        logger.debug(f"Updated retry config for task {task_id}")

    def get_escalated_tasks(self) -> List[Task]:
        """
        Get all tasks that have been escalated for human intervention.

        Returns:
            List of escalated tasks
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT t.* FROM tasks t
            JOIN retry_configs rc ON t.id = rc.task_id
            WHERE rc.escalated = 1
            ORDER BY rc.updated_at DESC
        """)

        tasks = []
        for row in cursor.fetchall():
            task = self._row_to_task(dict(row))
            tasks.append(task)

        conn.close()
        return tasks

    # ==================== Anti-Pattern Alert Operations ====================

    def create_anti_pattern_alert(self, alert) -> None:
        """
        Create a new anti-pattern alert.

        Args:
            alert: AntiPatternAlert to create
        """
        conn = sqlite3.connect(self.db_path)

        alert_dict = alert.to_dict()

        conn.execute(
            """
            INSERT OR REPLACE INTO anti_pattern_alerts VALUES (
                :id, :pattern_type, :severity, :project, :validated_item,
                :validation_source, :validation_date, :production_item,
                :production_source, :improvement_metrics, :recommendation_priority,
                :evidence, :suggested_action, :estimated_effort,
                :blocking_factors, :detected_at, :resolved_at, :resolution_notes
            )
        """,
            alert_dict,
        )

        conn.commit()
        conn.close()

    def get_anti_pattern_alerts(
        self, project: Optional[str] = None, unresolved_only: bool = True
    ) -> List:
        """
        Get anti-pattern alerts, optionally filtered by project.

        Args:
            project: Filter by project name (optional)
            unresolved_only: Only return unresolved alerts (default True)

        Returns:
            List of AntiPatternAlert objects
        """
        # Import here to avoid circular dependency
        from .anti_pattern_detector import AntiPatternAlert

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM anti_pattern_alerts WHERE 1=1"
        params = []

        if project:
            query += " AND project = ?"
            params.append(project)

        if unresolved_only:
            query += " AND resolved_at IS NULL"

        query += " ORDER BY severity DESC, detected_at DESC"

        cursor = conn.execute(query, params)
        alerts = [AntiPatternAlert.from_dict(dict(row)) for row in cursor.fetchall()]
        conn.close()

        return alerts

    def resolve_anti_pattern_alert(self, alert_id: str, notes: str) -> None:
        """
        Mark an anti-pattern alert as resolved.

        Args:
            alert_id: Alert ID to resolve
            notes: Resolution notes
        """
        conn = sqlite3.connect(self.db_path)

        conn.execute(
            """
            UPDATE anti_pattern_alerts
            SET resolved_at = ?, resolution_notes = ?
            WHERE id = ?
        """,
            (datetime.now().isoformat(), notes, alert_id),
        )

        conn.commit()
        conn.close()
