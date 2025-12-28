"""
Batch Task Queue - Persistent task scheduling and execution tracking.

Manages scheduled batch tasks with:
- SQLite persistence
- Task state management
- Execution tracking
- Capacity-aware scheduling
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import uuid


class TaskState(Enum):
    """Task execution states."""
    PENDING = "pending"  # Task created, not yet scheduled
    SCHEDULED = "scheduled"  # Scheduled for future execution
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # Manually cancelled


@dataclass
class BatchTask:
    """A batch task with scheduling and execution metadata."""
    task_id: str
    task_type: str  # test, build, deploy, etc.
    command: str  # Command to execute
    description: str
    priority: str  # immediate, high, normal, low

    # Scheduling
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_time: Optional[datetime] = None

    # Execution tracking
    state: TaskState = TaskState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error_message: str = ""

    # Metadata
    estimated_duration_minutes: float = 10.0
    actual_duration_seconds: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'command': self.command,
            'description': self.description,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'state': self.state.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'error_message': self.error_message,
            'estimated_duration_minutes': self.estimated_duration_minutes,
            'actual_duration_seconds': self.actual_duration_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'metadata': json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchTask':
        """Create from dictionary."""
        return cls(
            task_id=data['task_id'],
            task_type=data['task_type'],
            command=data['command'],
            description=data['description'],
            priority=data['priority'],
            created_at=datetime.fromisoformat(data['created_at']),
            scheduled_time=datetime.fromisoformat(data['scheduled_time']) if data['scheduled_time'] else None,
            state=TaskState(data['state']),
            started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
            exit_code=data['exit_code'],
            stdout=data['stdout'],
            stderr=data['stderr'],
            error_message=data['error_message'],
            estimated_duration_minutes=data['estimated_duration_minutes'],
            actual_duration_seconds=data['actual_duration_seconds'],
            retry_count=data['retry_count'],
            max_retries=data['max_retries'],
            metadata=json.loads(data['metadata']) if data['metadata'] else {},
        )


class BatchTaskQueue:
    """
    Persistent task queue with scheduling and execution tracking.

    Uses SQLite for persistence with WAL mode for concurrent access.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize task queue.

        Args:
            db_path: Path to SQLite database (defaults to ~/.cortex/batch_queue.db)
        """
        if db_path is None:
            cortex_dir = Path.home() / ".cortex"
            cortex_dir.mkdir(exist_ok=True)
            db_path = cortex_dir / "batch_queue.db"

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS batch_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                command TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT NOT NULL,
                scheduled_time TEXT,
                state TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                exit_code INTEGER,
                stdout TEXT,
                stderr TEXT,
                error_message TEXT,
                estimated_duration_minutes REAL,
                actual_duration_seconds REAL,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_state
            ON batch_tasks(state)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_time
            ON batch_tasks(scheduled_time)
        """)

        conn.commit()
        conn.close()

    def add_task(
        self,
        command: str,
        task_type: str = "general",
        description: str = "",
        priority: str = "normal",
        scheduled_time: Optional[datetime] = None,
        estimated_duration_minutes: float = 10.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BatchTask:
        """
        Add a new batch task to the queue.

        Args:
            command: Shell command to execute
            task_type: Type of task (test, build, deploy, etc.)
            description: Human-readable description
            priority: Priority level (immediate, high, normal, low)
            scheduled_time: When to run (None = run ASAP)
            estimated_duration_minutes: Expected duration
            metadata: Additional metadata

        Returns:
            Created BatchTask
        """
        task = BatchTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            command=command,
            description=description,
            priority=priority,
            scheduled_time=scheduled_time,
            state=TaskState.SCHEDULED if scheduled_time else TaskState.PENDING,
            estimated_duration_minutes=estimated_duration_minutes,
            metadata=metadata or {},
        )

        conn = sqlite3.connect(self.db_path)
        task_dict = task.to_dict()

        conn.execute("""
            INSERT INTO batch_tasks VALUES (
                :task_id, :task_type, :command, :description, :priority,
                :created_at, :scheduled_time, :state, :started_at, :completed_at,
                :exit_code, :stdout, :stderr, :error_message,
                :estimated_duration_minutes, :actual_duration_seconds,
                :retry_count, :max_retries, :metadata
            )
        """, task_dict)

        conn.commit()
        conn.close()

        return task

    def get_task(self, task_id: str) -> Optional[BatchTask]:
        """Get task by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM batch_tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return BatchTask.from_dict(dict(row))
        return None

    def get_pending_tasks(self) -> List[BatchTask]:
        """Get all pending tasks (not yet scheduled)."""
        return self._get_tasks_by_state(TaskState.PENDING)

    def get_scheduled_tasks(self, before: Optional[datetime] = None) -> List[BatchTask]:
        """
        Get scheduled tasks that are ready to run.

        Args:
            before: Get tasks scheduled before this time (default: now)

        Returns:
            List of tasks ready to execute
        """
        if before is None:
            before = datetime.now()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT * FROM batch_tasks
            WHERE state = 'scheduled' AND scheduled_time <= ?
            ORDER BY priority DESC, scheduled_time ASC
        """, (before.isoformat(),))

        tasks = [BatchTask.from_dict(dict(row)) for row in cursor.fetchall()]
        conn.close()

        return tasks

    def get_running_tasks(self) -> List[BatchTask]:
        """Get currently running tasks."""
        return self._get_tasks_by_state(TaskState.RUNNING)

    def _get_tasks_by_state(self, state: TaskState) -> List[BatchTask]:
        """Get tasks by state."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM batch_tasks WHERE state = ?",
            (state.value,)
        )
        tasks = [BatchTask.from_dict(dict(row)) for row in cursor.fetchall()]
        conn.close()

        return tasks

    def update_task_state(
        self,
        task_id: str,
        state: TaskState,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        exit_code: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
        error_message: str = ""
    ):
        """Update task state and execution details."""
        conn = sqlite3.connect(self.db_path)

        updates = {"state": state.value}
        if started_at:
            updates["started_at"] = started_at.isoformat()
        if completed_at:
            updates["completed_at"] = completed_at.isoformat()
        if exit_code is not None:
            updates["exit_code"] = exit_code
        if stdout:
            updates["stdout"] = stdout
        if stderr:
            updates["stderr"] = stderr
        if error_message:
            updates["error_message"] = error_message

        # Calculate actual duration if both times available
        if started_at and completed_at:
            duration = (completed_at - started_at).total_seconds()
            updates["actual_duration_seconds"] = duration

        set_clause = ", ".join(f"{k} = :{k}" for k in updates.keys())
        updates["task_id"] = task_id

        conn.execute(
            f"UPDATE batch_tasks SET {set_clause} WHERE task_id = :task_id",
            updates
        )
        conn.commit()
        conn.close()

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.

        Returns:
            True if cancelled, False if task not found or already completed
        """
        task = self.get_task(task_id)
        if not task:
            return False

        if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            return False

        self.update_task_state(task_id, TaskState.CANCELLED)
        return True

    def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed task.

        Returns:
            True if retried, False if max retries exceeded or task not failed
        """
        task = self.get_task(task_id)
        if not task:
            return False

        if task.state != TaskState.FAILED:
            return False

        if task.retry_count >= task.max_retries:
            return False

        # Reset task to pending and increment retry count
        # Clear scheduled_time so it gets rescheduled
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE batch_tasks
            SET state = 'pending', retry_count = retry_count + 1,
                scheduled_time = NULL, started_at = NULL, completed_at = NULL,
                exit_code = NULL, stdout = '', stderr = '', error_message = ''
            WHERE task_id = ?
        """, (task_id,))
        conn.commit()
        conn.close()

        return True

    def get_task_history(
        self,
        limit: int = 100,
        task_type: Optional[str] = None,
        state: Optional[TaskState] = None
    ) -> List[BatchTask]:
        """
        Get task history.

        Args:
            limit: Maximum tasks to return
            task_type: Filter by task type
            state: Filter by state

        Returns:
            List of tasks ordered by created_at desc
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM batch_tasks WHERE 1=1"
        params = []

        if task_type:
            query += " AND task_type = ?"
            params.append(task_type)

        if state:
            query += " AND state = ?"
            params.append(state.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        tasks = [BatchTask.from_dict(dict(row)) for row in cursor.fetchall()]
        conn.close()

        return tasks

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        conn = sqlite3.connect(self.db_path)

        stats = {}

        # Count by state
        cursor = conn.execute("""
            SELECT state, COUNT(*) as count
            FROM batch_tasks
            GROUP BY state
        """)
        for row in cursor:
            stats[f"{row[0]}_count"] = row[1]

        # Average duration by task type
        cursor = conn.execute("""
            SELECT task_type, AVG(actual_duration_seconds) as avg_duration
            FROM batch_tasks
            WHERE actual_duration_seconds IS NOT NULL
            GROUP BY task_type
        """)
        avg_durations = {}
        for row in cursor:
            avg_durations[row[0]] = row[1]
        stats["avg_duration_by_type"] = avg_durations

        # Success rate
        cursor = conn.execute("""
            SELECT
                SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed
            FROM batch_tasks
            WHERE state IN ('completed', 'failed')
        """)
        row = cursor.fetchone()
        if row[0] or row[1]:
            total = (row[0] or 0) + (row[1] or 0)
            stats["success_rate"] = (row[0] or 0) / total if total > 0 else 0
        else:
            stats["success_rate"] = 0

        conn.close()
        return stats

    def cleanup_old_tasks(self, days: int = 30):
        """Delete completed/failed tasks older than N days."""
        cutoff = datetime.now() - timedelta(days=days)

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            DELETE FROM batch_tasks
            WHERE state IN ('completed', 'failed', 'cancelled')
            AND completed_at < ?
        """, (cutoff.isoformat(),))
        conn.commit()
        conn.close()
