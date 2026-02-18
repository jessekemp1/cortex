"""
Storage layer for the Work Absorber system.

Provides SQLite persistence with caching for:
- Work signals (raw detections)
- Work items (consolidated work)
- Progress entries (plan progress)
- Plan drifts (gaps detected)
- Absorption reports (audit trail)
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    AbsorptionReport,
    DriftType,
    PlanDrift,
    ProgressEntry,
    WorkItem,
    WorkSignal,
    WorkSignalType,
    WorkStatus,
)

logger = logging.getLogger(__name__)


class WorkAbsorberStorage:
    """
    Persistence layer for Work Absorber.

    Uses SQLite for durability with in-memory caching for performance.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        cache_ttl: int = 3600,
    ):
        """
        Initialize storage.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.cortex/work_absorber.db
            cache_ttl: Cache time-to-live in seconds (default 1 hour)
        """
        self.db_path = db_path or Path.home() / ".cortex" / "work_absorber.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl

        # In-memory cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                -- Work signals (raw detections)
                CREATE TABLE IF NOT EXISTS work_signals (
                    id TEXT PRIMARY KEY,
                    signal_type TEXT NOT NULL,
                    source_path TEXT,
                    project TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    metadata TEXT,
                    commit_hash TEXT,
                    author TEXT,
                    files_changed TEXT,
                    achievements TEXT,
                    scope TEXT,
                    batch_id TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    processed INTEGER DEFAULT 0,
                    absorbed_into TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Work items (consolidated)
                CREATE TABLE IF NOT EXISTS work_items (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    first_seen TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    signal_ids TEXT,
                    signal_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'detected',
                    plan_step_id TEXT,
                    correlation_confidence REAL DEFAULT 0.0,
                    files_touched TEXT,
                    estimated_effort_hours REAL DEFAULT 0.0,
                    tags TEXT,
                    scope TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Progress entries
                CREATE TABLE IF NOT EXISTS progress_entries (
                    id TEXT PRIMARY KEY,
                    work_item_id TEXT NOT NULL,
                    plan_step_id TEXT,
                    project TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    progress_delta REAL DEFAULT 0.0,
                    cumulative_progress REAL DEFAULT 0.0,
                    evidence_type TEXT,
                    evidence_summary TEXT,
                    evidence_path TEXT,
                    confidence REAL DEFAULT 0.8,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (work_item_id) REFERENCES work_items(id)
                );

                -- Plan drift tracking
                CREATE TABLE IF NOT EXISTS plan_drifts (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    drift_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'info',
                    plan_step_id TEXT,
                    work_item_id TEXT,
                    description TEXT,
                    suggested_action TEXT,
                    resolved INTEGER DEFAULT 0,
                    resolved_at TEXT,
                    resolution_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Absorption reports (audit trail)
                CREATE TABLE IF NOT EXISTS absorption_reports (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    signals_detected INTEGER DEFAULT 0,
                    signals_absorbed INTEGER DEFAULT 0,
                    work_items_created INTEGER DEFAULT 0,
                    work_items_updated INTEGER DEFAULT 0,
                    correlations_made INTEGER DEFAULT 0,
                    drifts_detected INTEGER DEFAULT 0,
                    by_project TEXT,
                    errors TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Sync state (for incremental absorption)
                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_signals_project ON work_signals(project);
                CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON work_signals(timestamp);
                CREATE INDEX IF NOT EXISTS idx_signals_type ON work_signals(signal_type);
                CREATE INDEX IF NOT EXISTS idx_items_project ON work_items(project);
                CREATE INDEX IF NOT EXISTS idx_items_status ON work_items(status);
                CREATE INDEX IF NOT EXISTS idx_progress_project ON progress_entries(project);
                CREATE INDEX IF NOT EXISTS idx_progress_plan_step ON progress_entries(plan_step_id);
                CREATE INDEX IF NOT EXISTS idx_drifts_project ON plan_drifts(project);
                CREATE INDEX IF NOT EXISTS idx_drifts_resolved ON plan_drifts(resolved);
            """
            )

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
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

    # ─────────────────────────────────────────────────────────────────
    # Work Signal Operations
    # ─────────────────────────────────────────────────────────────────

    def save_signal(self, signal: WorkSignal) -> bool:
        """Save a work signal to the database."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO work_signals
                    (id, signal_type, source_path, project, timestamp, title, description,
                     metadata, commit_hash, author, files_changed, achievements, scope,
                     batch_id, tokens_used, processed, absorbed_into)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        signal.id,
                        signal.signal_type.value,
                        signal.source_path,
                        signal.project,
                        signal.timestamp.isoformat(),
                        signal.title,
                        signal.description,
                        json.dumps(signal.metadata),
                        signal.commit_hash,
                        signal.author,
                        json.dumps(signal.files_changed),
                        json.dumps(signal.achievements),
                        signal.scope,
                        signal.batch_id,
                        signal.tokens_used,
                        1 if signal.processed else 0,
                        signal.absorbed_into,
                    ),
                )
            self._invalidate_cache("signals")
            return True
        except Exception as e:
            logger.error(f"Failed to save signal {signal.id}: {e}")
            return False

    def save_signals_batch(self, signals: List[WorkSignal]) -> int:
        """Save multiple signals in a batch. Returns count saved."""
        saved = 0
        with self._get_connection() as conn:
            for signal in signals:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO work_signals
                        (id, signal_type, source_path, project, timestamp, title, description,
                         metadata, commit_hash, author, files_changed, achievements, scope,
                         batch_id, tokens_used, processed, absorbed_into)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            signal.id,
                            signal.signal_type.value,
                            signal.source_path,
                            signal.project,
                            signal.timestamp.isoformat(),
                            signal.title,
                            signal.description,
                            json.dumps(signal.metadata),
                            signal.commit_hash,
                            signal.author,
                            json.dumps(signal.files_changed),
                            json.dumps(signal.achievements),
                            signal.scope,
                            signal.batch_id,
                            signal.tokens_used,
                            1 if signal.processed else 0,
                            signal.absorbed_into,
                        ),
                    )
                    saved += 1
                except Exception as e:
                    logger.warning(f"Failed to save signal {signal.id}: {e}")
        self._invalidate_cache("signals")
        return saved

    def get_signal(self, signal_id: str) -> Optional[WorkSignal]:
        """Get a signal by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM work_signals WHERE id = ?", (signal_id,)).fetchone()
            if row:
                return self._row_to_signal(row)
        return None

    def get_signals_since(self, since: datetime, project: Optional[str] = None) -> List[WorkSignal]:
        """Get signals since a timestamp, optionally filtered by project."""
        cache_key = f"signals_since_{since.isoformat()}_{project or 'all'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM work_signals WHERE timestamp >= ? AND project = ? ORDER BY timestamp DESC",
                    (since.isoformat(), project),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM work_signals WHERE timestamp >= ? ORDER BY timestamp DESC",
                    (since.isoformat(),),
                ).fetchall()

        signals = [self._row_to_signal(row) for row in rows]
        self._set_cached(cache_key, signals)
        return signals

    def get_unprocessed_signals(self) -> List[WorkSignal]:
        """Get signals that haven't been processed yet."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM work_signals WHERE processed = 0 ORDER BY timestamp"
            ).fetchall()
        return [self._row_to_signal(row) for row in rows]

    def mark_signal_processed(self, signal_id: str, work_item_id: str) -> bool:
        """Mark a signal as processed and absorbed into a work item."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE work_signals SET processed = 1, absorbed_into = ? WHERE id = ?",
                (work_item_id, signal_id),
            )
        self._invalidate_cache("signals")
        return True

    def _row_to_signal(self, row: sqlite3.Row) -> WorkSignal:
        """Convert a database row to a WorkSignal."""
        return WorkSignal(
            id=row["id"],
            signal_type=WorkSignalType(row["signal_type"]),
            source_path=row["source_path"],
            project=row["project"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            title=row["title"] or "",
            description=row["description"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            commit_hash=row["commit_hash"],
            author=row["author"],
            files_changed=(json.loads(row["files_changed"]) if row["files_changed"] else []),
            achievements=json.loads(row["achievements"]) if row["achievements"] else [],
            scope=row["scope"],
            batch_id=row["batch_id"],
            tokens_used=row["tokens_used"] or 0,
            processed=bool(row["processed"]),
            absorbed_into=row["absorbed_into"],
        )

    # ─────────────────────────────────────────────────────────────────
    # Work Item Operations
    # ─────────────────────────────────────────────────────────────────

    def save_work_item(self, item: WorkItem) -> bool:
        """Save a work item to the database."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO work_items
                    (id, project, title, description, first_seen, last_activity,
                     signal_ids, signal_count, status, plan_step_id, correlation_confidence,
                     files_touched, estimated_effort_hours, tags, scope, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        item.id,
                        item.project,
                        item.title,
                        item.description,
                        item.first_seen.isoformat(),
                        item.last_activity.isoformat(),
                        json.dumps(item.signal_ids),
                        item.signal_count,
                        item.status.value,
                        item.plan_step_id,
                        item.correlation_confidence,
                        json.dumps(item.files_touched),
                        item.estimated_effort_hours,
                        json.dumps(item.tags),
                        item.scope,
                        json.dumps(item.metadata),
                        datetime.now().isoformat(),
                    ),
                )
            self._invalidate_cache("items")
            return True
        except Exception as e:
            logger.error(f"Failed to save work item {item.id}: {e}")
            return False

    def get_work_item(self, item_id: str) -> Optional[WorkItem]:
        """Get a work item by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            if row:
                return self._row_to_work_item(row)
        return None

    def get_work_items_by_project(self, project: str) -> List[WorkItem]:
        """Get all work items for a project."""
        cache_key = f"items_project_{project}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM work_items WHERE project = ? ORDER BY last_activity DESC",
                (project,),
            ).fetchall()

        items = [self._row_to_work_item(row) for row in rows]
        self._set_cached(cache_key, items)
        return items

    def get_work_items_by_status(self, status: WorkStatus) -> List[WorkItem]:
        """Get work items by status."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM work_items WHERE status = ? ORDER BY last_activity DESC",
                (status.value,),
            ).fetchall()
        return [self._row_to_work_item(row) for row in rows]

    def get_orphaned_work_items(self) -> List[WorkItem]:
        """Get work items with no plan correlation."""
        return self.get_work_items_by_status(WorkStatus.ORPHANED)

    def get_all_work_items(self, limit: int = 100) -> List[WorkItem]:
        """Get all work items, ordered by last activity."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM work_items ORDER BY last_activity DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_work_item(row) for row in rows]

    def get_work_items_since(self, since: datetime) -> List[WorkItem]:
        """Get work items active since a timestamp."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM work_items WHERE last_activity >= ? ORDER BY last_activity DESC",
                (since.isoformat(),),
            ).fetchall()
        return [self._row_to_work_item(row) for row in rows]

    def _row_to_work_item(self, row: sqlite3.Row) -> WorkItem:
        """Convert a database row to a WorkItem."""
        return WorkItem(
            id=row["id"],
            project=row["project"],
            title=row["title"],
            description=row["description"] or "",
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_activity=datetime.fromisoformat(row["last_activity"]),
            signal_ids=json.loads(row["signal_ids"]) if row["signal_ids"] else [],
            signal_count=row["signal_count"] or 0,
            status=WorkStatus(row["status"]),
            plan_step_id=row["plan_step_id"],
            correlation_confidence=row["correlation_confidence"] or 0.0,
            files_touched=(json.loads(row["files_touched"]) if row["files_touched"] else []),
            estimated_effort_hours=row["estimated_effort_hours"] or 0.0,
            tags=json.loads(row["tags"]) if row["tags"] else [],
            scope=row["scope"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    # ─────────────────────────────────────────────────────────────────
    # Progress Entry Operations
    # ─────────────────────────────────────────────────────────────────

    def save_progress(self, entry: ProgressEntry) -> bool:
        """Save a progress entry."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO progress_entries
                    (id, work_item_id, plan_step_id, project, timestamp,
                     progress_delta, cumulative_progress, evidence_type,
                     evidence_summary, evidence_path, confidence, verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry.id,
                        entry.work_item_id,
                        entry.plan_step_id,
                        entry.project,
                        entry.timestamp.isoformat(),
                        entry.progress_delta,
                        entry.cumulative_progress,
                        entry.evidence_type,
                        entry.evidence_summary,
                        entry.evidence_path,
                        entry.confidence,
                        1 if entry.verified else 0,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save progress entry {entry.id}: {e}")
            return False

    def get_progress_for_plan_step(self, plan_step_id: str) -> List[ProgressEntry]:
        """Get all progress entries for a plan step."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM progress_entries WHERE plan_step_id = ? ORDER BY timestamp",
                (plan_step_id,),
            ).fetchall()
        return [self._row_to_progress(row) for row in rows]

    def get_progress_for_project(self, project: str) -> List[ProgressEntry]:
        """Get all progress entries for a project."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM progress_entries WHERE project = ? ORDER BY timestamp DESC",
                (project,),
            ).fetchall()
        return [self._row_to_progress(row) for row in rows]

    def _row_to_progress(self, row: sqlite3.Row) -> ProgressEntry:
        """Convert a database row to a ProgressEntry."""
        return ProgressEntry(
            id=row["id"],
            work_item_id=row["work_item_id"],
            plan_step_id=row["plan_step_id"],
            project=row["project"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            progress_delta=row["progress_delta"] or 0.0,
            cumulative_progress=row["cumulative_progress"] or 0.0,
            evidence_type=row["evidence_type"] or "",
            evidence_summary=row["evidence_summary"] or "",
            evidence_path=row["evidence_path"],
            confidence=row["confidence"] or 0.8,
            verified=bool(row["verified"]),
        )

    # ─────────────────────────────────────────────────────────────────
    # Plan Drift Operations
    # ─────────────────────────────────────────────────────────────────

    def save_drift(self, drift: PlanDrift) -> bool:
        """Save a plan drift."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO plan_drifts
                    (id, project, detected_at, drift_type, severity,
                     plan_step_id, work_item_id, description, suggested_action,
                     resolved, resolved_at, resolution_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        drift.id,
                        drift.project,
                        drift.detected_at.isoformat(),
                        drift.drift_type.value,
                        drift.severity,
                        drift.plan_step_id,
                        drift.work_item_id,
                        drift.description,
                        drift.suggested_action,
                        1 if drift.resolved else 0,
                        drift.resolved_at.isoformat() if drift.resolved_at else None,
                        drift.resolution_notes,
                    ),
                )
            self._invalidate_cache("drifts")
            return True
        except Exception as e:
            logger.error(f"Failed to save drift {drift.id}: {e}")
            return False

    def get_unresolved_drifts(self, project: Optional[str] = None) -> List[PlanDrift]:
        """Get unresolved drifts, optionally filtered by project."""
        cache_key = f"drifts_unresolved_{project or 'all'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        with self._get_connection() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM plan_drifts WHERE resolved = 0 AND project = ? ORDER BY detected_at DESC",
                    (project,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM plan_drifts WHERE resolved = 0 ORDER BY detected_at DESC"
                ).fetchall()

        drifts = [self._row_to_drift(row) for row in rows]
        self._set_cached(cache_key, drifts)
        return drifts

    def resolve_drift(self, drift_id: str, notes: str = "") -> bool:
        """Mark a drift as resolved."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE plan_drifts SET resolved = 1, resolved_at = ?, resolution_notes = ? WHERE id = ?",
                (datetime.now().isoformat(), notes, drift_id),
            )
        self._invalidate_cache("drifts")
        return True

    def _row_to_drift(self, row: sqlite3.Row) -> PlanDrift:
        """Convert a database row to a PlanDrift."""
        return PlanDrift(
            id=row["id"],
            project=row["project"],
            detected_at=datetime.fromisoformat(row["detected_at"]),
            drift_type=DriftType(row["drift_type"]),
            severity=row["severity"] or "info",
            plan_step_id=row["plan_step_id"],
            work_item_id=row["work_item_id"],
            description=row["description"] or "",
            suggested_action=row["suggested_action"] or "",
            resolved=bool(row["resolved"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None
            ),
            resolution_notes=row["resolution_notes"] or "",
        )

    # ─────────────────────────────────────────────────────────────────
    # Absorption Report Operations
    # ─────────────────────────────────────────────────────────────────

    def save_report(self, report: AbsorptionReport) -> bool:
        """Save an absorption report."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO absorption_reports
                    (id, started_at, completed_at, signals_detected, signals_absorbed,
                     work_items_created, work_items_updated, correlations_made,
                     drifts_detected, by_project, errors)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        report.id,
                        report.started_at.isoformat(),
                        report.completed_at.isoformat(),
                        report.signals_detected,
                        report.signals_absorbed,
                        report.work_items_created,
                        report.work_items_updated,
                        report.correlations_made,
                        report.drifts_detected,
                        json.dumps(report.by_project),
                        json.dumps(report.errors),
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save report {report.id}: {e}")
            return False

    def get_latest_report(self) -> Optional[AbsorptionReport]:
        """Get the most recent absorption report."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM absorption_reports ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()
            if row:
                return AbsorptionReport(
                    id=row["id"],
                    started_at=datetime.fromisoformat(row["started_at"]),
                    completed_at=datetime.fromisoformat(row["completed_at"]),
                    signals_detected=row["signals_detected"] or 0,
                    signals_absorbed=row["signals_absorbed"] or 0,
                    work_items_created=row["work_items_created"] or 0,
                    work_items_updated=row["work_items_updated"] or 0,
                    correlations_made=row["correlations_made"] or 0,
                    drifts_detected=row["drifts_detected"] or 0,
                    by_project=(json.loads(row["by_project"]) if row["by_project"] else {}),
                    errors=json.loads(row["errors"]) if row["errors"] else [],
                )
        return None

    # ─────────────────────────────────────────────────────────────────
    # Sync State Operations
    # ─────────────────────────────────────────────────────────────────

    def get_last_absorption_time(self) -> Optional[datetime]:
        """Get the timestamp of the last absorption run."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM sync_state WHERE key = 'last_absorption'"
            ).fetchone()
            if row and row["value"]:
                return datetime.fromisoformat(row["value"])
        return None

    def set_last_absorption_time(self, timestamp: datetime) -> None:
        """Set the timestamp of the last absorption run."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_state (key, value, updated_at)
                VALUES ('last_absorption', ?, ?)
            """,
                (timestamp.isoformat(), datetime.now().isoformat()),
            )

    def get_sync_state(self, key: str) -> Optional[str]:
        """Get a sync state value."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
            if row:
                return row["value"]
        return None

    def set_sync_state(self, key: str, value: str) -> None:
        """Set a sync state value."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_state (key, value, updated_at)
                VALUES (?, ?, ?)
            """,
                (key, value, datetime.now().isoformat()),
            )

    # ─────────────────────────────────────────────────────────────────
    # Cache Operations
    # ─────────────────────────────────────────────────────────────────

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get a value from cache if not expired."""
        if key in self._cache:
            timestamp = self._cache_timestamps.get(key)
            if timestamp and (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Set a value in cache."""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()

    def _invalidate_cache(self, prefix: str = "") -> None:
        """Invalidate cache entries matching a prefix."""
        if prefix:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

    # ─────────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with self._get_connection() as conn:
            signal_count = conn.execute("SELECT COUNT(*) FROM work_signals").fetchone()[0]
            item_count = conn.execute("SELECT COUNT(*) FROM work_items").fetchone()[0]
            drift_count = conn.execute(
                "SELECT COUNT(*) FROM plan_drifts WHERE resolved = 0"
            ).fetchone()[0]

            # By project
            project_stats = {}
            rows = conn.execute(
                """
                SELECT project, COUNT(*) as count FROM work_items GROUP BY project
            """
            ).fetchall()
            for row in rows:
                project_stats[row["project"]] = row["count"]

        return {
            "total_signals": signal_count,
            "total_work_items": item_count,
            "unresolved_drifts": drift_count,
            "by_project": project_stats,
            "last_absorption": self.get_last_absorption_time(),
        }
