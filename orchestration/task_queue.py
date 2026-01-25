"""
Priority task queue with SQLite persistence.

Manages FIFO queues per priority level with dependency tracking and persistence.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .task import Task, TaskPriority, TaskStatus, TaskPhase


class TaskQueue:
    """
    Priority-based task queue with SQLite persistence.

    Features:
    - Priority queues (A > B > C)
    - Dependency tracking (blocked_by/blocks relationships)
    - SQLite persistence for crash recovery
    - Task state transitions
    - Query interface for scheduling
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize task queue with SQLite backend.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.cortex/queue/tasks.db
        """
        if db_path is None:
            db_path = Path.home() / ".cortex" / "queue" / "tasks.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                deadline TEXT,
                phase TEXT NOT NULL,
                status TEXT NOT NULL,
                prompt TEXT,
                context TEXT,
                files_affected TEXT,
                estimated_input_tokens INTEGER,
                estimated_output_tokens INTEGER,
                actual_input_tokens INTEGER,
                actual_output_tokens INTEGER,
                execution_mode TEXT,
                batch_id TEXT,
                assigned_agent TEXT,
                result TEXT,
                error TEXT,
                validation_passed INTEGER,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                tags TEXT,
                source TEXT,
                project TEXT
            )
        """)

        # Dependencies table (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_dependencies (
                task_id TEXT NOT NULL,
                blocks_task_id TEXT NOT NULL,
                PRIMARY KEY (task_id, blocks_task_id),
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                FOREIGN KEY (blocks_task_id) REFERENCES tasks(id)
            )
        """)

        # Indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_priority
            ON tasks(priority, status, created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status, phase)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_deadline
            ON tasks(deadline) WHERE deadline IS NOT NULL
        """)

        conn.commit()
        conn.close()

    def enqueue(self, task: Task) -> None:
        """
        Add task to queue.

        Args:
            task: Task to enqueue
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert task
        cursor.execute("""
            INSERT OR REPLACE INTO tasks VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            task.id,
            task.title,
            task.description,
            task.priority.value,
            task.deadline.isoformat() if task.deadline else None,
            task.phase.value,
            task.status.value,
            task.prompt,
            json.dumps(task.context),
            json.dumps(task.files_affected),
            task.estimated_input_tokens,
            task.estimated_output_tokens,
            task.actual_input_tokens,
            task.actual_output_tokens,
            task.execution_mode,
            task.batch_id,
            task.assigned_agent,
            task.result,
            task.error,
            1 if task.validation_passed else 0,
            task.created_at.isoformat(),
            task.started_at.isoformat() if task.started_at else None,
            task.completed_at.isoformat() if task.completed_at else None,
            json.dumps(task.tags),
            task.source,
            task.project,
        ))

        # Insert dependencies
        cursor.execute("DELETE FROM task_dependencies WHERE task_id = ?", (task.id,))
        for blocked_task_id in task.blocks:
            cursor.execute(
                "INSERT OR IGNORE INTO task_dependencies VALUES (?, ?)",
                (task.id, blocked_task_id)
            )

        conn.commit()
        conn.close()

    def dequeue(self, priority: Optional[TaskPriority] = None) -> Optional[Task]:
        """
        Remove and return highest priority task that's ready to execute.

        Args:
            priority: Optional priority filter. If None, gets highest priority available.

        Returns:
            Task if available, None if queue empty or all tasks blocked
        """
        tasks = self.get_ready_tasks(priority=priority, limit=1)
        if not tasks:
            return None

        task = tasks[0]

        # Mark as scheduled
        task.mark_scheduled("pending")
        self.update(task)

        return task

    def peek(self, priority: Optional[TaskPriority] = None) -> Optional[Task]:
        """
        View highest priority task without removing from queue.

        Args:
            priority: Optional priority filter

        Returns:
            Task if available, None if queue empty
        """
        tasks = self.get_ready_tasks(priority=priority, limit=1)
        return tasks[0] if tasks else None

    def get(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # Load dependencies
        cursor.execute(
            "SELECT blocks_task_id FROM task_dependencies WHERE task_id = ?",
            (task_id,)
        )
        blocks = [r[0] for r in cursor.fetchall()]

        cursor.execute(
            "SELECT task_id FROM task_dependencies WHERE blocks_task_id = ?",
            (task_id,)
        )
        blocked_by = [r[0] for r in cursor.fetchall()]

        conn.close()

        return self._row_to_task(row, blocks, blocked_by)

    def update(self, task: Task) -> None:
        """
        Update existing task.

        Args:
            task: Task with updated state
        """
        self.enqueue(task)  # INSERT OR REPLACE handles updates

    def get_ready_tasks(
        self,
        priority: Optional[TaskPriority] = None,
        limit: Optional[int] = None
    ) -> List[Task]:
        """
        Get tasks ready for execution (not blocked, not running).

        Args:
            priority: Optional priority filter
            limit: Maximum number of tasks to return

        Returns:
            List of tasks ordered by priority (A > B > C) then creation time
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT t.* FROM tasks t
            LEFT JOIN task_dependencies td ON t.id = td.blocks_task_id
            LEFT JOIN tasks blocker ON td.task_id = blocker.id
                AND blocker.status NOT IN ('completed', 'failed')
            WHERE t.status = 'pending'
            AND blocker.id IS NULL  -- Not blocked by any incomplete task
        """

        params = []
        if priority:
            query += " AND t.priority = ?"
            params.append(priority.value)

        # Order by priority then creation time
        query += " GROUP BY t.id ORDER BY t.priority ASC, t.created_at ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Load tasks with dependencies
        tasks = []
        for row in rows:
            task_id = row[0]

            # Get blocks
            cursor.execute(
                "SELECT blocks_task_id FROM task_dependencies WHERE task_id = ?",
                (task_id,)
            )
            blocks = [r[0] for r in cursor.fetchall()]

            # Get blocked_by
            cursor.execute(
                "SELECT task_id FROM task_dependencies WHERE blocks_task_id = ?",
                (task_id,)
            )
            blocked_by = [r[0] for r in cursor.fetchall()]

            tasks.append(self._row_to_task(row, blocks, blocked_by))

        conn.close()
        return tasks

    def get_blocked_tasks(self) -> List[Task]:
        """
        Get tasks that are blocked by dependencies.

        Returns:
            List of blocked tasks
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tasks blocked by incomplete dependencies
        cursor.execute("""
            SELECT DISTINCT t.* FROM tasks t
            JOIN task_dependencies td ON t.id = td.blocks_task_id
            JOIN tasks blocker ON td.task_id = blocker.id
            WHERE blocker.status NOT IN ('completed', 'failed')
            AND t.status = 'pending'
        """)

        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task_id = row[0]

            cursor.execute(
                "SELECT blocks_task_id FROM task_dependencies WHERE task_id = ?",
                (task_id,)
            )
            blocks = [r[0] for r in cursor.fetchall()]

            cursor.execute(
                "SELECT task_id FROM task_dependencies WHERE blocks_task_id = ?",
                (task_id,)
            )
            blocked_by = [r[0] for r in cursor.fetchall()]

            tasks.append(self._row_to_task(row, blocks, blocked_by))

        conn.close()
        return tasks

    def get_all(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None
    ) -> List[Task]:
        """
        Get all tasks, optionally filtered.

        Args:
            status: Optional status filter
            priority: Optional priority filter

        Returns:
            List of tasks
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if priority:
            query += " AND priority = ?"
            params.append(priority.value)

        query += " ORDER BY priority ASC, created_at ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task_id = row[0]

            cursor.execute(
                "SELECT blocks_task_id FROM task_dependencies WHERE task_id = ?",
                (task_id,)
            )
            blocks = [r[0] for r in cursor.fetchall()]

            cursor.execute(
                "SELECT task_id FROM task_dependencies WHERE blocks_task_id = ?",
                (task_id,)
            )
            blocked_by = [r[0] for r in cursor.fetchall()]

            tasks.append(self._row_to_task(row, blocks, blocked_by))

        conn.close()
        return tasks

    def complete_task(self, task_id: str, result: Optional[str] = None) -> None:
        """
        Mark task as completed and unblock dependent tasks.

        Args:
            task_id: Task ID to complete
            result: Optional result data
        """
        task = self.get(task_id)
        if not task:
            return

        task.phase = TaskPhase.COMPLETED
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        if result:
            task.result = result

        self.update(task)

        # Unblock dependent tasks
        for blocked_id in task.blocks:
            blocked_task = self.get(blocked_id)
            if blocked_task:
                blocked_task.unblock(task_id)
                self.update(blocked_task)

    def fail_task(self, task_id: str, error: str) -> None:
        """
        Mark task as failed and unblock dependent tasks.

        Args:
            task_id: Task ID to fail
            error: Error message
        """
        task = self.get(task_id)
        if not task:
            return

        task.mark_failed(error)
        self.update(task)

        # Unblock dependent tasks (they can proceed despite failure)
        for blocked_id in task.blocks:
            blocked_task = self.get(blocked_id)
            if blocked_task:
                blocked_task.unblock(task_id)
                self.update(blocked_task)

    def size(self, priority: Optional[TaskPriority] = None) -> int:
        """
        Get queue size.

        Args:
            priority: Optional priority filter

        Returns:
            Number of pending tasks
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
        params = []

        if priority:
            query += " AND priority = ?"
            params.append(priority.value)

        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def clear(self) -> None:
        """Clear all tasks from queue (use with caution)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM task_dependencies")
        cursor.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dict with queue metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Overall counts
        cursor.execute("SELECT COUNT(*) FROM tasks")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        pending = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'running'")
        running = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        completed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'")
        failed = cursor.fetchone()[0]

        # By priority
        by_priority = {}
        for priority in TaskPriority:
            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE priority = ? AND status = 'pending'",
                (priority.value,)
            )
            by_priority[priority.value] = cursor.fetchone()[0]

        # Blocked count
        cursor.execute("""
            SELECT COUNT(DISTINCT t.id) FROM tasks t
            JOIN task_dependencies td ON t.id = td.blocks_task_id
            JOIN tasks blocker ON td.task_id = blocker.id
            WHERE blocker.status NOT IN ('completed', 'failed')
            AND t.status = 'pending'
        """)
        blocked = cursor.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
            "ready": pending - blocked,
            "by_priority": by_priority,
        }

    def _row_to_task(
        self,
        row: tuple,
        blocks: List[str],
        blocked_by: List[str]
    ) -> Task:
        """Convert SQLite row to Task object"""
        return Task(
            id=row[0],
            title=row[1],
            description=row[2],
            priority=TaskPriority(row[3]),
            deadline=datetime.fromisoformat(row[4]) if row[4] else None,
            phase=TaskPhase(row[5]),
            status=TaskStatus(row[6]),
            prompt=row[7],
            context=json.loads(row[8]) if row[8] else {},
            files_affected=json.loads(row[9]) if row[9] else [],
            estimated_input_tokens=row[10],
            estimated_output_tokens=row[11],
            actual_input_tokens=row[12],
            actual_output_tokens=row[13],
            execution_mode=row[14],
            batch_id=row[15],
            assigned_agent=row[16],
            result=row[17],
            error=row[18],
            validation_passed=bool(row[19]),
            created_at=datetime.fromisoformat(row[20]),
            started_at=datetime.fromisoformat(row[21]) if row[21] else None,
            completed_at=datetime.fromisoformat(row[22]) if row[22] else None,
            tags=json.loads(row[23]) if row[23] else [],
            source=row[24],
            project=row[25],
            blocks=blocks,
            blocked_by=blocked_by,
        )
