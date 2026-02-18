"""Execution history storage.

Provides SQLite-based storage for tracking agent execution history,
including success rates, timing, and error data.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from cortex.runtime.config import get_config

logger = structlog.get_logger()


def _json_serial(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "name"):  # Enum fallback
        return obj.name
    return str(obj)  # Fallback to string representation


class ExecutionHistory:
    """Store and query agent execution history."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize execution history storage.

        Args:
            db_path: Path to SQLite database. If None, uses config default.
        """
        if db_path is None:
            config = get_config()
            db_path = str(config.execution_history_db)

        self.db_path = db_path
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Executions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                success INTEGER NOT NULL,
                message TEXT,
                result_data TEXT,
                error_data TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes for common queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_id ON executions(agent_id)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_created_at ON executions(created_at)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_status ON executions(status)
        """
        )

        conn.commit()
        conn.close()

    def record_execution(
        self,
        agent_id: str,
        status: str,
        start_time: datetime,
        end_time: Optional[datetime],
        duration_seconds: Optional[float],
        success: bool,
        message: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Record an agent execution.

        Args:
            agent_id: ID of the agent that executed
            status: Execution status (completed, failed, etc.)
            start_time: When execution started
            end_time: When execution ended
            duration_seconds: Total execution duration
            success: Whether execution was successful
            message: Optional status message
            result_data: Optional result data dict
            error_data: Optional error data dict

        Returns:
            The execution record ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO executions (
                agent_id, status, start_time, end_time, duration_seconds,
                success, message, result_data, error_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                agent_id,
                status,
                start_time.isoformat(),
                end_time.isoformat() if end_time else None,
                duration_seconds,
                1 if success else 0,
                message,
                json.dumps(result_data, default=_json_serial) if result_data else None,
                json.dumps(error_data, default=_json_serial) if error_data else None,
            ),
        )

        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(
            "execution_recorded",
            agent_id=agent_id,
            execution_id=execution_id,
            success=success,
        )
        return execution_id

    def get_recent_executions(
        self, limit: int = 50, agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent executions.

        Args:
            limit: Maximum number of executions to return
            agent_id: Optional filter by agent ID

        Returns:
            List of execution records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if agent_id:
            cursor.execute(
                """
                SELECT * FROM executions
                WHERE agent_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (agent_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM executions
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        executions = []
        for row in rows:
            exec_dict = dict(row)
            # Parse JSON fields
            if exec_dict.get("result_data"):
                exec_dict["result_data"] = json.loads(exec_dict["result_data"])
            if exec_dict.get("error_data"):
                exec_dict["error_data"] = json.loads(exec_dict["error_data"])
            # Convert success integer to boolean
            exec_dict["success"] = bool(exec_dict["success"])
            executions.append(exec_dict)

        return executions

    def get_execution(self, execution_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific execution by ID.

        Args:
            execution_id: The execution record ID

        Returns:
            Execution record or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        exec_dict = dict(row)
        # Parse JSON fields
        if exec_dict.get("result_data"):
            exec_dict["result_data"] = json.loads(exec_dict["result_data"])
        if exec_dict.get("error_data"):
            exec_dict["error_data"] = json.loads(exec_dict["error_data"])
        # Convert success integer to boolean
        exec_dict["success"] = bool(exec_dict["success"])

        return exec_dict

    def get_agent_statistics(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics for a specific agent.

        Args:
            agent_id: The agent ID

        Returns:
            Statistics dict with counts, rates, and timing
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total executions
        cursor.execute("SELECT COUNT(*) FROM executions WHERE agent_id = ?", (agent_id,))
        total = cursor.fetchone()[0]

        # Successful executions
        cursor.execute(
            """
            SELECT COUNT(*) FROM executions
            WHERE agent_id = ? AND success = 1
        """,
            (agent_id,),
        )
        successful = cursor.fetchone()[0]

        # Failed executions
        cursor.execute(
            """
            SELECT COUNT(*) FROM executions
            WHERE agent_id = ? AND success = 0
        """,
            (agent_id,),
        )
        failed = cursor.fetchone()[0]

        # Average duration
        cursor.execute(
            """
            SELECT AVG(duration_seconds) FROM executions
            WHERE agent_id = ? AND duration_seconds IS NOT NULL
        """,
            (agent_id,),
        )
        avg_duration = cursor.fetchone()[0]

        # Last execution
        cursor.execute(
            """
            SELECT created_at FROM executions
            WHERE agent_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (agent_id,),
        )
        last_execution = cursor.fetchone()
        last_execution_time = last_execution[0] if last_execution else None

        conn.close()

        return {
            "agent_id": agent_id,
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "average_duration_seconds": avg_duration,
            "last_execution": last_execution_time,
        }

    def cleanup_old_executions(self, days_to_keep: int = 30) -> int:
        """Remove executions older than specified days.

        Args:
            days_to_keep: Number of days of history to retain

        Returns:
            Number of records deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM executions
            WHERE created_at < datetime('now', '-' || ? || ' days')
        """,
            (days_to_keep,),
        )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(
            "old_executions_cleaned",
            deleted_count=deleted_count,
            days_to_keep=days_to_keep,
        )
        return deleted_count
