"""
Process metrics tracker with SQLite persistence.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    Anomaly,
    AnomalyType,
    ProcessCategory,
    ProcessSnapshot,
    ResourceMetric,
)


class ProcessTracker:
    """
    Persistent process metric tracking using SQLite.

    Thread-safe storage at ~/.cortex/process_metrics.db
    """

    def __init__(self, db_path: Optional[Path] = None, retention_days: int = 90):
        """
        Initialize the tracker.

        Args:
            db_path: Path to SQLite database (default: ~/.cortex/process_metrics.db)
            retention_days: Number of days to retain data (default: 90)
        """
        if db_path is None:
            cortex_dir = Path.home() / ".cortex"
            cortex_dir.mkdir(exist_ok=True)
            db_path = cortex_dir / "process_metrics.db"

        self.db_path = db_path
        self.retention_days = retention_days
        self._local = threading.local()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False, timeout=30.0
            )
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            # Row factory for dict-like access
            self._local.conn.row_factory = sqlite3.Row

        return self._local.conn

    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise

    def _init_database(self):
        """Initialize database schema."""
        with self._transaction() as cursor:
            # Resource snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resource_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_cpu_percent REAL NOT NULL,
                    available_memory_mb REAL NOT NULL,
                    total_memory_mb REAL NOT NULL,
                    process_count INTEGER NOT NULL,
                    ai_tool_cpu REAL DEFAULT 0.0,
                    ai_tool_memory REAL DEFAULT 0.0,
                    dev_service_cpu REAL DEFAULT 0.0,
                    dev_service_memory REAL DEFAULT 0.0,
                    docker_cpu REAL DEFAULT 0.0,
                    docker_memory_mb REAL DEFAULT 0.0
                )
            """)

            # Process history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS process_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    cpu_percent REAL NOT NULL,
                    memory_mb REAL NOT NULL,
                    status TEXT NOT NULL,
                    command TEXT,
                    port INTEGER,
                    parent_pid INTEGER,
                    username TEXT,
                    num_threads INTEGER DEFAULT 1
                )
            """)

            # Anomalies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    process_name TEXT NOT NULL,
                    process_pid INTEGER NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # Patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    last_seen TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_snapshots_timestamp
                ON resource_snapshots(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_process_history_timestamp
                ON process_history(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_process_history_category
                ON process_history(category)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp
                ON anomalies(timestamp)
            """)

    def record_snapshot(self, resource_metric: ResourceMetric, processes: List[ProcessSnapshot]):
        """
        Record a snapshot of resources and processes.

        Args:
            resource_metric: System-wide resource metrics
            processes: List of process snapshots
        """
        with self._transaction() as cursor:
            # Insert resource snapshot
            cursor.execute(
                """
                INSERT INTO resource_snapshots (
                    timestamp, total_cpu_percent, available_memory_mb,
                    total_memory_mb, process_count, ai_tool_cpu,
                    ai_tool_memory, dev_service_cpu, dev_service_memory,
                    docker_cpu, docker_memory_mb
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    resource_metric.timestamp.isoformat(),
                    resource_metric.total_cpu_percent,
                    resource_metric.available_memory_mb,
                    resource_metric.total_memory_mb,
                    resource_metric.process_count,
                    resource_metric.ai_tool_cpu,
                    resource_metric.ai_tool_memory,
                    resource_metric.dev_service_cpu,
                    resource_metric.dev_service_memory,
                    resource_metric.docker_cpu,
                    resource_metric.docker_memory_mb,
                ),
            )

            # Insert process snapshots (sample to avoid bloat)
            # Only store interesting processes: AI tools, dev services, high resource
            interesting_processes = [
                p
                for p in processes
                if p.category
                in (
                    ProcessCategory.AI_TOOL,
                    ProcessCategory.DEV_SERVICE,
                    ProcessCategory.BACKGROUND_AGENT,
                    ProcessCategory.CONTAINER,
                )
                or p.cpu_percent > 10.0
                or p.memory_mb > 500.0
            ]

            for proc in interesting_processes:
                cursor.execute(
                    """
                    INSERT INTO process_history (
                        timestamp, pid, name, category, cpu_percent,
                        memory_mb, status, command, port, parent_pid,
                        username, num_threads
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        resource_metric.timestamp.isoformat(),
                        proc.pid,
                        proc.name,
                        proc.category.value,
                        proc.cpu_percent,
                        proc.memory_mb,
                        proc.status.value,
                        proc.command,
                        proc.port,
                        proc.parent_pid,
                        proc.username,
                        proc.num_threads,
                    ),
                )

    def record_anomaly(self, anomaly: Anomaly):
        """
        Record a detected anomaly.

        Args:
            anomaly: Anomaly object
        """
        with self._transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO anomalies (
                    timestamp, process_name, process_pid, anomaly_type,
                    severity, description, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    anomaly.timestamp.isoformat(),
                    anomaly.process_name,
                    anomaly.process_pid,
                    anomaly.anomaly_type.value,
                    anomaly.severity,
                    anomaly.description,
                    json.dumps(anomaly.metadata),
                ),
            )

    def get_utilization_history(self, hours: int = 24) -> List[ResourceMetric]:
        """
        Get resource utilization history.

        Args:
            hours: Number of hours to retrieve

        Returns:
            List of ResourceMetric objects
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT * FROM resource_snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """,
                (cutoff,),
            )

            rows = cursor.fetchall()

        return [
            ResourceMetric(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                total_cpu_percent=row["total_cpu_percent"],
                available_memory_mb=row["available_memory_mb"],
                total_memory_mb=row["total_memory_mb"],
                process_count=row["process_count"],
                ai_tool_cpu=row["ai_tool_cpu"] or 0.0,
                ai_tool_memory=row["ai_tool_memory"] or 0.0,
                dev_service_cpu=row["dev_service_cpu"] or 0.0,
                dev_service_memory=row["dev_service_memory"] or 0.0,
                docker_cpu=row["docker_cpu"] or 0.0,
                docker_memory_mb=row["docker_memory_mb"] or 0.0,
            )
            for row in rows
        ]

    def get_process_patterns(self, category: ProcessCategory, hours: int = 24) -> Dict[str, Any]:
        """
        Get process patterns for a category.

        Args:
            category: Process category to analyze
            hours: Number of hours to analyze

        Returns:
            Dictionary with pattern insights
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT
                    name,
                    AVG(cpu_percent) as avg_cpu,
                    AVG(memory_mb) as avg_memory,
                    MAX(cpu_percent) as max_cpu,
                    MAX(memory_mb) as max_memory,
                    COUNT(*) as sample_count
                FROM process_history
                WHERE category = ? AND timestamp >= ?
                GROUP BY name
                ORDER BY avg_cpu DESC
            """,
                (category.value, cutoff),
            )

            rows = cursor.fetchall()

        return {
            row["name"]: {
                "avg_cpu": row["avg_cpu"],
                "avg_memory": row["avg_memory"],
                "max_cpu": row["max_cpu"],
                "max_memory": row["max_memory"],
                "sample_count": row["sample_count"],
            }
            for row in rows
        }

    def get_recent_anomalies(self, hours: int = 24) -> List[Anomaly]:
        """
        Get recent anomalies.

        Args:
            hours: Number of hours to retrieve

        Returns:
            List of Anomaly objects
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT * FROM anomalies
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """,
                (cutoff,),
            )

            rows = cursor.fetchall()

        return [
            Anomaly(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                process_name=row["process_name"],
                process_pid=row["process_pid"],
                anomaly_type=AnomalyType(row["anomaly_type"]),
                severity=row["severity"],
                description=row["description"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    def get_hourly_stats(self, days: int = 7) -> Dict[int, Dict[str, float]]:
        """
        Get average resource usage by hour of day.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary mapping hour (0-23) to stats
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT
                    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                    AVG(total_cpu_percent) as avg_cpu,
                    AVG(total_memory_mb - available_memory_mb) as avg_memory_used
                FROM resource_snapshots
                WHERE timestamp >= ?
                GROUP BY hour
                ORDER BY hour
            """,
                (cutoff,),
            )

            rows = cursor.fetchall()

        return {
            row["hour"]: {
                "avg_cpu": row["avg_cpu"],
                "avg_memory_used": row["avg_memory_used"],
            }
            for row in rows
        }

    def cleanup_old_data(self, days: Optional[int] = None):
        """
        Clean up old data beyond retention period.

        Args:
            days: Number of days to retain (default: use retention_days)
        """
        if days is None:
            days = self.retention_days

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._transaction() as cursor:
            # Clean up old snapshots
            cursor.execute(
                """
                DELETE FROM resource_snapshots
                WHERE timestamp < ?
            """,
                (cutoff,),
            )

            # Clean up old process history
            cursor.execute(
                """
                DELETE FROM process_history
                WHERE timestamp < ?
            """,
                (cutoff,),
            )

            # Clean up old anomalies
            cursor.execute(
                """
                DELETE FROM anomalies
                WHERE timestamp < ?
            """,
                (cutoff,),
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database stats
        """
        with self._transaction() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM resource_snapshots")
            snapshot_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM process_history")
            process_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM anomalies")
            anomaly_count = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
                FROM resource_snapshots
            """)
            time_range = cursor.fetchone()

        return {
            "snapshot_count": snapshot_count,
            "process_history_count": process_count,
            "anomaly_count": anomaly_count,
            "oldest_data": time_range["oldest"],
            "newest_data": time_range["newest"],
            "db_path": str(self.db_path),
        }
