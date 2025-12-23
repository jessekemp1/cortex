"""Cortex Knowledge Database - SQLite-based persistent storage."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import Goal, Task, Blocker, Progress, Status, TaskStatus, Priority

SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    priority TEXT CHECK(priority IN ('A', 'B', 'C')) DEFAULT 'B',
    status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'blocked')) DEFAULT 'pending',
    project TEXT,
    success_criteria TEXT,
    deadline TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal_id TEXT REFERENCES goals(id),
    title TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'in_progress', 'completed')) DEFAULT 'pending',
    source TEXT,
    source_file TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS blockers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id TEXT REFERENCES goals(id),
    project TEXT,
    description TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id TEXT,
    task_id TEXT,
    action TEXT NOT NULL,
    notes TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_goal_id ON tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_blockers_project ON blockers(project);
CREATE INDEX IF NOT EXISTS idx_blockers_goal_id ON blockers(goal_id);
CREATE INDEX IF NOT EXISTS idx_progress_goal_id ON progress(goal_id);
"""


class CortexDB:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".cortex" / "cortex.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add_goal(self, goal: Goal) -> Goal:
        now = datetime.now().isoformat()
        goal.created_at = goal.created_at or now
        goal.updated_at = now
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO goals (id, title, priority, status, project, success_criteria, deadline, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (goal.id, goal.title,
                 goal.priority.value if isinstance(goal.priority, Priority) else goal.priority,
                 goal.status.value if isinstance(goal.status, Status) else goal.status,
                 goal.project, goal.success_criteria, goal.deadline, goal.created_at, goal.updated_at))
        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row:
                return Goal.from_dict(dict(row))
        return None

    def list_goals(self, priority: Optional[str] = None, status: Optional[str] = None, project: Optional[str] = None) -> List[Goal]:
        query = "SELECT * FROM goals WHERE 1=1"
        params = []
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if status:
            query += " AND status = ?"
            params.append(status)
        if project:
            query += " AND project = ?"
            params.append(project)
        query += " ORDER BY priority ASC, created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Goal.from_dict(dict(row)) for row in rows]

    def update_goal(self, goal_id: str, **kwargs) -> Optional[Goal]:
        if not kwargs:
            return self.get_goal(goal_id)
        kwargs["updated_at"] = datetime.now().isoformat()
        if "priority" in kwargs and isinstance(kwargs["priority"], Priority):
            kwargs["priority"] = kwargs["priority"].value
        if "status" in kwargs and isinstance(kwargs["status"], Status):
            kwargs["status"] = kwargs["status"].value
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [goal_id]
        with self._get_connection() as conn:
            conn.execute(f"UPDATE goals SET {set_clause} WHERE id = ?", values)
        return self.get_goal(goal_id)

    def delete_goal(self, goal_id: str) -> bool:
        with self._get_connection() as conn:
            result = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            return result.rowcount > 0

    def add_task(self, task: Task) -> Task:
        task.created_at = task.created_at or datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (id, goal_id, title, status, source, source_file, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task.id, task.goal_id, task.title,
                 task.status.value if isinstance(task.status, TaskStatus) else task.status,
                 task.source, task.source_file, task.created_at, task.completed_at))
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return Task.from_dict(dict(row))
        return None

    def list_tasks(self, goal_id: Optional[str] = None, status: Optional[str] = None) -> List[Task]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        if goal_id:
            query += " AND goal_id = ?"
            params.append(goal_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Task.from_dict(dict(row)) for row in rows]

    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        if not kwargs:
            return self.get_task(task_id)
        if "status" in kwargs and isinstance(kwargs["status"], TaskStatus):
            kwargs["status"] = kwargs["status"].value
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [task_id]
        with self._get_connection() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        return self.get_task(task_id)

    def complete_task(self, task_id: str) -> Optional[Task]:
        return self.update_task(task_id, status="completed", completed_at=datetime.now().isoformat())

    def delete_task(self, task_id: str) -> bool:
        with self._get_connection() as conn:
            result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return result.rowcount > 0

    def add_blocker(self, blocker: Blocker) -> Blocker:
        blocker.created_at = blocker.created_at or datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO blockers (goal_id, project, description, resolved, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?)",
                (blocker.goal_id, blocker.project, blocker.description, 1 if blocker.resolved else 0, blocker.created_at, blocker.resolved_at))
            blocker.id = cursor.lastrowid
        return blocker

    def get_blocker(self, blocker_id: int) -> Optional[Blocker]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM blockers WHERE id = ?", (blocker_id,)).fetchone()
            if row:
                return Blocker.from_dict(dict(row))
        return None

    def list_blockers(self, project: Optional[str] = None, goal_id: Optional[str] = None, include_resolved: bool = False) -> List[Blocker]:
        query = "SELECT * FROM blockers WHERE 1=1"
        params = []
        if not include_resolved:
            query += " AND resolved = 0"
        if project:
            query += " AND project = ?"
            params.append(project)
        if goal_id:
            query += " AND goal_id = ?"
            params.append(goal_id)
        query += " ORDER BY created_at DESC"
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Blocker.from_dict(dict(row)) for row in rows]

    def resolve_blocker(self, blocker_id: int) -> Optional[Blocker]:
        with self._get_connection() as conn:
            conn.execute("UPDATE blockers SET resolved = 1, resolved_at = ? WHERE id = ?", (datetime.now().isoformat(), blocker_id))
        return self.get_blocker(blocker_id)

    def delete_blocker(self, blocker_id: int) -> bool:
        with self._get_connection() as conn:
            result = conn.execute("DELETE FROM blockers WHERE id = ?", (blocker_id,))
            return result.rowcount > 0

    def add_progress(self, progress: Progress) -> Progress:
        progress.timestamp = progress.timestamp or datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO progress (goal_id, task_id, action, notes, timestamp) VALUES (?, ?, ?, ?, ?)",
                (progress.goal_id, progress.task_id, progress.action, progress.notes, progress.timestamp))
            progress.id = cursor.lastrowid
        return progress

    def list_progress(self, goal_id: Optional[str] = None, task_id: Optional[str] = None, limit: int = 50) -> List[Progress]:
        query = "SELECT * FROM progress WHERE 1=1"
        params = []
        if goal_id:
            query += " AND goal_id = ?"
            params.append(goal_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        query += f" ORDER BY timestamp DESC LIMIT {limit}"
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Progress.from_dict(dict(row)) for row in rows]

    def get_goal_summary(self) -> dict:
        with self._get_connection() as conn:
            priority_counts = {}
            for row in conn.execute("SELECT priority, COUNT(*) as count FROM goals GROUP BY priority"):
                priority_counts[row["priority"]] = row["count"]
            status_counts = {}
            for row in conn.execute("SELECT status, COUNT(*) as count FROM goals GROUP BY status"):
                status_counts[row["status"]] = row["count"]
            blocker_count = conn.execute("SELECT COUNT(*) as count FROM blockers WHERE resolved = 0").fetchone()["count"]
            return {
                "by_priority": priority_counts,
                "by_status": status_counts,
                "active_blockers": blocker_count,
                "total_goals": sum(priority_counts.values()),
            }

    def get_goal_with_tasks(self, goal_id: str) -> Optional[dict]:
        goal = self.get_goal(goal_id)
        if not goal:
            return None
        tasks = self.list_tasks(goal_id=goal_id)
        blockers = self.list_blockers(goal_id=goal_id)
        progress = self.list_progress(goal_id=goal_id, limit=10)
        return {
            "goal": goal.to_dict(),
            "tasks": [t.to_dict() for t in tasks],
            "blockers": [b.to_dict() for b in blockers],
            "recent_progress": [p.to_dict() for p in progress],
            "task_completion": f"{sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)}/{len(tasks)}",
        }


_db: Optional[CortexDB] = None

def get_db() -> CortexDB:
    global _db
    if _db is None:
        _db = CortexDB()
    return _db
