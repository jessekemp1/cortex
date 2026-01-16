"""
Metric Tracker for Cortex Intelligence Stack - Layer 3 Warning System.

This module provides persistent metric tracking with SQLite storage,
enabling trend analysis and degradation detection across projects.

Architecture:
    MetricTracker → SQLite DB → TrendAnalyzer → AlertGenerator

Usage:
    tracker = MetricTracker()
    tracker.track_coverage("cortex", 34.5, {"test_files": 41})
    metrics = tracker.get_metrics("cortex", "coverage", days=7)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Supported metric types for tracking."""

    COVERAGE = "coverage"
    VIOLATIONS = "violations"
    COMMITS = "commits"
    FILE_CHANGES = "file_changes"


@dataclass
class Metric:
    """Represents a single metric data point."""

    id: int | None
    project: str
    metric_type: MetricType
    metric_value: float
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metric to dictionary representation."""
        return {
            "id": self.id,
            "project": self.project,
            "metric_type": self.metric_type.value,
            "metric_value": self.metric_value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: tuple) -> Metric:
        """Create Metric from database row."""
        id_, project, metric_type, metric_value, timestamp_str, metadata_json = row

        # Parse timestamp
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            timestamp = timestamp_str

        # Ensure timezone awareness
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Parse metadata
        metadata = json.loads(metadata_json) if metadata_json else {}

        return cls(
            id=id_,
            project=project,
            metric_type=MetricType(metric_type),
            metric_value=float(metric_value),
            timestamp=timestamp,
            metadata=metadata,
        )


class MetricTrackerError(Exception):
    """Base exception for metric tracker errors."""

    pass


class DatabaseError(MetricTrackerError):
    """Database operation failed."""

    pass


class ValidationError(MetricTrackerError):
    """Invalid metric data."""

    pass


class MetricTracker:
    """
    Persistent metric tracking with SQLite storage.

    Provides thread-safe metric storage and retrieval for the
    Cortex Warning System. Tracks test coverage, lint violations,
    commit frequency, and file change patterns.

    Attributes:
        db_path: Path to SQLite database file.

    Example:
        >>> tracker = MetricTracker()
        >>> tracker.track_coverage("myproject", 85.5, {"test_files": 20})
        >>> metrics = tracker.get_metrics("myproject", MetricType.COVERAGE, days=7)
        >>> for m in metrics:
        ...     print(f"{m.timestamp}: {m.metric_value}%")
    """

    # SQL statements
    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            metric_value REAL NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT,
            UNIQUE(project, metric_type, timestamp)
        )
    """

    _CREATE_INDEX_SQL = """
        CREATE INDEX IF NOT EXISTS idx_project_type_time 
        ON metrics(project, metric_type, timestamp)
    """

    _CREATE_PROJECT_INDEX_SQL = """
        CREATE INDEX IF NOT EXISTS idx_project 
        ON metrics(project)
    """

    _INSERT_SQL = """
        INSERT INTO metrics (project, metric_type, metric_value, timestamp, metadata)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project, metric_type, timestamp) 
        DO UPDATE SET metric_value = excluded.metric_value,
                      metadata = excluded.metadata
    """

    _SELECT_SQL = """
        SELECT id, project, metric_type, metric_value, timestamp, metadata
        FROM metrics
        WHERE project = ? AND metric_type = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    """

    _SELECT_LATEST_SQL = """
        SELECT id, project, metric_type, metric_value, timestamp, metadata
        FROM metrics
        WHERE project = ? AND metric_type = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """

    _SELECT_ALL_PROJECTS_SQL = """
        SELECT DISTINCT project FROM metrics
    """

    _DELETE_OLD_SQL = """
        DELETE FROM metrics WHERE timestamp < ?
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        retention_days: int = 90,
    ) -> None:
        """
        Initialize the metric tracker.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.cortex/metrics.db
            retention_days: Days to retain metrics before cleanup. Default 90.

        Raises:
            DatabaseError: If database initialization fails.
        """
        if db_path is None:
            cortex_dir = Path.home() / ".cortex"
            cortex_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = cortex_dir / "metrics.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.retention_days = retention_days
        self._local = threading.local()

        # Initialize database schema
        self._init_database()

        logger.debug(f"MetricTracker initialized with database: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection.

        Returns:
            SQLite connection for current thread.

        Raises:
            DatabaseError: If connection fails.
        """
        if not hasattr(self._local, "connection") or self._local.connection is None:
            try:
                self._local.connection = sqlite3.connect(
                    str(self.db_path),
                    timeout=30.0,
                    isolation_level="DEFERRED",
                )
                # Enable foreign keys and WAL mode for better concurrency
                self._local.connection.execute("PRAGMA foreign_keys = ON")
                self._local.connection.execute("PRAGMA journal_mode = WAL")
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to connect to database: {e}") from e

        return self._local.connection

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for database transactions.

        Yields:
            Database cursor within transaction.

        Raises:
            DatabaseError: If transaction fails.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Transaction failed: {e}") from e
        finally:
            cursor.close()

    def _init_database(self) -> None:
        """
        Initialize database schema.

        Creates tables and indexes if they don't exist.

        Raises:
            DatabaseError: If schema creation fails.
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(self._CREATE_TABLE_SQL)
                cursor.execute(self._CREATE_INDEX_SQL)
                cursor.execute(self._CREATE_PROJECT_INDEX_SQL)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {e}") from e

    def _validate_project(self, project: str) -> None:
        """Validate project name."""
        if not project or not isinstance(project, str):
            raise ValidationError("Project name must be a non-empty string")
        if len(project) > 255:
            raise ValidationError("Project name too long (max 255 characters)")

    def _validate_metric_value(self, value: float, metric_type: MetricType) -> None:
        """Validate metric value based on type."""
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Metric value must be numeric, got {type(value)}")

        if metric_type == MetricType.COVERAGE:
            if not 0 <= value <= 100:
                raise ValidationError(f"Coverage must be 0-100%, got {value}")
        elif metric_type in (MetricType.VIOLATIONS, MetricType.COMMITS):
            if value < 0:
                raise ValidationError(f"Count cannot be negative, got {value}")

    def _now_utc(self) -> datetime:
        """Get current UTC timestamp."""
        return datetime.now(timezone.utc)

    def _track_metric(
        self,
        project: str,
        metric_type: MetricType,
        value: float,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Metric:
        """
        Internal method to track any metric type.

        Args:
            project: Project identifier.
            metric_type: Type of metric.
            value: Metric value.
            metadata: Optional additional context.
            timestamp: Optional timestamp (defaults to now UTC).

        Returns:
            The tracked Metric object.

        Raises:
            ValidationError: If data is invalid.
            DatabaseError: If storage fails.
        """
        # Validate inputs
        self._validate_project(project)
        self._validate_metric_value(value, metric_type)

        # Prepare data
        if timestamp is None:
            timestamp = self._now_utc()
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        metadata = metadata or {}
        metadata_json = json.dumps(metadata)
        timestamp_str = timestamp.isoformat()

        # Store metric
        try:
            with self._transaction() as cursor:
                cursor.execute(
                    self._INSERT_SQL,
                    (project, metric_type.value, value, timestamp_str, metadata_json),
                )
                metric_id = cursor.lastrowid
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to store metric: {e}") from e

        metric = Metric(
            id=metric_id,
            project=project,
            metric_type=metric_type,
            metric_value=value,
            timestamp=timestamp,
            metadata=metadata,
        )

        logger.debug(
            f"Tracked {metric_type.value} for {project}: {value} " f"(metadata: {metadata})"
        )

        return metric

    def track_coverage(
        self,
        project: str,
        coverage_pct: float,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Metric:
        """
        Track test coverage percentage for a project.

        Args:
            project: Project identifier (e.g., "cortex", "VortexV2").
            coverage_pct: Test coverage percentage (0-100).
            metadata: Optional context (e.g., {"test_files": 41, "total_lines": 5000}).
            timestamp: Optional timestamp (defaults to now UTC).

        Returns:
            The tracked Metric object.

        Raises:
            ValidationError: If coverage is not 0-100.
            DatabaseError: If storage fails.

        Example:
            >>> tracker.track_coverage("cortex", 34.5, {"test_files": 41})
        """
        return self._track_metric(
            project=project,
            metric_type=MetricType.COVERAGE,
            value=coverage_pct,
            metadata=metadata,
            timestamp=timestamp,
        )

    def track_violations(
        self,
        project: str,
        count: int,
        linter: str | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Metric:
        """
        Track lint violation count for a project.

        Args:
            project: Project identifier.
            count: Number of lint violations.
            linter: Linter name (e.g., "ruff", "flake8", "eslint").
            metadata: Optional context (e.g., {"error_count": 5, "warning_count": 7}).
            timestamp: Optional timestamp (defaults to now UTC).

        Returns:
            The tracked Metric object.

        Raises:
            ValidationError: If count is negative.
            DatabaseError: If storage fails.

        Example:
            >>> tracker.track_violations("cortex", 12, linter="ruff")
        """
        metadata = metadata or {}
        if linter:
            metadata["linter"] = linter

        return self._track_metric(
            project=project,
            metric_type=MetricType.VIOLATIONS,
            value=float(count),
            metadata=metadata,
            timestamp=timestamp,
        )

    def track_commits(
        self,
        project: str,
        count: int,
        timeframe: str = "24h",
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Metric:
        """
        Track commit frequency for a project.

        Args:
            project: Project identifier.
            count: Number of commits in timeframe.
            timeframe: Time period (e.g., "24h", "7d", "30d").
            metadata: Optional context (e.g., {"authors": ["alice", "bob"]}).
            timestamp: Optional timestamp (defaults to now UTC).

        Returns:
            The tracked Metric object.

        Raises:
            ValidationError: If count is negative.
            DatabaseError: If storage fails.

        Example:
            >>> tracker.track_commits("VortexV2", 5, timeframe="24h")
        """
        metadata = metadata or {}
        metadata["timeframe"] = timeframe

        return self._track_metric(
            project=project,
            metric_type=MetricType.COMMITS,
            value=float(count),
            metadata=metadata,
            timestamp=timestamp,
        )

    def track_file_changes(
        self,
        project: str,
        file_path: str,
        uncommitted_hours: float,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> Metric:
        """
        Track uncommitted file changes for critical files.

        Args:
            project: Project identifier.
            file_path: Path to the file being tracked.
            uncommitted_hours: Hours since file was modified but not committed.
            metadata: Optional context (e.g., {"is_critical": True, "lines_changed": 50}).
            timestamp: Optional timestamp (defaults to now UTC).

        Returns:
            The tracked Metric object.

        Raises:
            ValidationError: If hours is negative.
            DatabaseError: If storage fails.

        Example:
            >>> tracker.track_file_changes("cortex", "main.py", 48.5,
            ...                            {"is_critical": True})
        """
        if uncommitted_hours < 0:
            raise ValidationError(f"Uncommitted hours cannot be negative: {uncommitted_hours}")

        metadata = metadata or {}
        metadata["file_path"] = file_path

        return self._track_metric(
            project=project,
            metric_type=MetricType.FILE_CHANGES,
            value=uncommitted_hours,
            metadata=metadata,
            timestamp=timestamp,
        )

    def get_metrics(
        self,
        project: str,
        metric_type: MetricType | str,
        days: int = 7,
    ) -> list[Metric]:
        """
        Retrieve metrics for a project within a time range.

        Args:
            project: Project identifier.
            metric_type: Type of metric to retrieve.
            days: Number of days to look back (default 7).

        Returns:
            List of Metric objects, ordered by timestamp ascending.

        Raises:
            ValidationError: If parameters are invalid.
            DatabaseError: If query fails.

        Example:
            >>> metrics = tracker.get_metrics("cortex", MetricType.COVERAGE, days=30)
            >>> for m in metrics:
            ...     print(f"{m.timestamp.date()}: {m.metric_value}%")
        """
        self._validate_project(project)

        if isinstance(metric_type, str):
            try:
                metric_type = MetricType(metric_type)
            except ValueError:
                raise ValidationError(f"Invalid metric type: {metric_type}")

        if days < 1:
            raise ValidationError(f"Days must be positive, got {days}")

        # Calculate cutoff timestamp
        cutoff = self._now_utc() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        try:
            with self._transaction() as cursor:
                cursor.execute(
                    self._SELECT_SQL,
                    (project, metric_type.value, cutoff_str),
                )
                rows = cursor.fetchall()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to query metrics: {e}") from e

        return [Metric.from_row(row) for row in rows]

    def get_latest_metric(
        self,
        project: str,
        metric_type: MetricType | str,
    ) -> Metric | None:
        """
        Get the most recent metric of a type for a project.

        Args:
            project: Project identifier.
            metric_type: Type of metric to retrieve.

        Returns:
            Most recent Metric or None if no metrics exist.

        Raises:
            ValidationError: If parameters are invalid.
            DatabaseError: If query fails.

        Example:
            >>> latest = tracker.get_latest_metric("cortex", MetricType.COVERAGE)
            >>> if latest:
            ...     print(f"Current coverage: {latest.metric_value}%")
        """
        self._validate_project(project)

        if isinstance(metric_type, str):
            try:
                metric_type = MetricType(metric_type)
            except ValueError:
                raise ValidationError(f"Invalid metric type: {metric_type}")

        try:
            with self._transaction() as cursor:
                cursor.execute(
                    self._SELECT_LATEST_SQL,
                    (project, metric_type.value),
                )
                row = cursor.fetchone()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to query latest metric: {e}") from e

        return Metric.from_row(row) if row else None

    def get_all_projects(self) -> list[str]:
        """
        Get list of all projects with tracked metrics.

        Returns:
            List of project names.

        Raises:
            DatabaseError: If query fails.
        """
        try:
            with self._transaction() as cursor:
                cursor.execute(self._SELECT_ALL_PROJECTS_SQL)
                rows = cursor.fetchall()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to query projects: {e}") from e

        return [row[0] for row in rows]

    def cleanup_old_metrics(self, days: int | None = None) -> int:
        """
        Remove metrics older than retention period.

        Args:
            days: Days to retain (defaults to self.retention_days).

        Returns:
            Number of metrics deleted.

        Raises:
            DatabaseError: If deletion fails.
        """
        if days is None:
            days = self.retention_days

        cutoff = self._now_utc() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        try:
            with self._transaction() as cursor:
                cursor.execute(self._DELETE_OLD_SQL, (cutoff_str,))
                deleted = cursor.rowcount
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to cleanup old metrics: {e}") from e

        logger.info(f"Cleaned up {deleted} metrics older than {days} days")
        return deleted

    def get_metric_summary(
        self,
        project: str,
        metric_type: MetricType | str,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        Get summary statistics for a metric.

        Args:
            project: Project identifier.
            metric_type: Type of metric.
            days: Number of days to analyze.

        Returns:
            Dictionary with min, max, avg, count, first, last values.

        Example:
            >>> summary = tracker.get_metric_summary("cortex", MetricType.COVERAGE, 30)
            >>> print(f"Coverage range: {summary['min']}% - {summary['max']}%")
        """
        metrics = self.get_metrics(project, metric_type, days)

        if not metrics:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "first": None,
                "last": None,
                "delta": None,
            }

        values = [m.metric_value for m in metrics]

        return {
            "count": len(metrics),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "first": metrics[0].metric_value,
            "last": metrics[-1].metric_value,
            "delta": metrics[-1].metric_value - metrics[0].metric_value,
        }

    def close(self) -> None:
        """
        Close database connection for current thread.

        Should be called when done with tracker in a thread.
        """
        if hasattr(self._local, "connection") and self._local.connection:
            try:
                self._local.connection.close()
            except sqlite3.Error:
                pass
            self._local.connection = None

    def __enter__(self) -> MetricTracker:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close connection."""
        self.close()


# Convenience function for quick access
_default_tracker: MetricTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> MetricTracker:
    """
    Get or create the default MetricTracker instance.

    Thread-safe singleton accessor for the global tracker.

    Returns:
        The default MetricTracker instance.

    Example:
        >>> from metric_tracker import get_tracker
        >>> tracker = get_tracker()
        >>> tracker.track_coverage("myproject", 85.0)
    """
    global _default_tracker

    if _default_tracker is None:
        with _tracker_lock:
            if _default_tracker is None:
                _default_tracker = MetricTracker()

    return _default_tracker


if __name__ == "__main__":
    # Demo usage
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metrics.db"

        with MetricTracker(db_path) as tracker:
            # Track some metrics
            print("Tracking metrics...")

            tracker.track_coverage("cortex", 34.5, {"test_files": 41})
            tracker.track_coverage("cortex", 32.0, {"test_files": 40})
            tracker.track_violations("cortex", 12, linter="ruff")
            tracker.track_commits("VortexV2", 5, timeframe="24h")
            tracker.track_file_changes("cortex", "main.py", 48.5, {"is_critical": True})

            # Query metrics
            print("\nCoverage metrics for cortex:")
            for m in tracker.get_metrics("cortex", MetricType.COVERAGE, days=7):
                print(f"  {m.timestamp}: {m.metric_value}%")

            # Get summary
            print("\nCoverage summary:")
            summary = tracker.get_metric_summary("cortex", MetricType.COVERAGE, days=7)
            print(f"  Count: {summary['count']}")
            print(f"  Range: {summary['min']}% - {summary['max']}%")
            print(f"  Delta: {summary['delta']}%")

            # List projects
            print(f"\nTracked projects: {tracker.get_all_projects()}")

            print("\n✅ MetricTracker demo complete!")
