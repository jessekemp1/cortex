"""
Data models for the Work Absorber system.

Core entities:
- WorkSignal: Raw work detection from any source
- WorkItem: Consolidated work (may combine multiple signals)
- ProgressEntry: Progress record against plan steps
- PlanDrift: Gap between planned and actual work
- AbsorptionReport: Summary of an absorption cycle
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class WorkSignalType(Enum):
    """Types of work signals that can be detected."""

    GIT_COMMIT = "git_commit"
    COMPLETION_DOC = "completion_doc"
    BATCH_RESULT = "batch_result"
    FILE_CHANGE = "file_change"
    PLAN_UPDATE = "plan_update"


class WorkStatus(Enum):
    """Status of work items in the absorption pipeline."""

    DETECTED = "detected"  # Signal detected, not yet processed
    ABSORBED = "absorbed"  # Processed and integrated
    CORRELATED = "correlated"  # Linked to a plan item
    ORPHANED = "orphaned"  # No plan correlation found


class DriftType(Enum):
    """Types of drift between plans and actual work."""

    UNPLANNED_WORK = "unplanned_work"  # Work done not in plan
    STALE_PLAN = "stale_plan"  # Plan item with no activity
    SCOPE_CREEP = "scope_creep"  # Work exceeds plan scope
    BLOCKED = "blocked"  # Plan item explicitly blocked
    EARLY_COMPLETION = "early_completion"  # Completed ahead of schedule


@dataclass
class WorkSignal:
    """
    A raw work signal from any source (git, docs, batch, etc.).

    This is the atomic unit of work detection - one commit, one doc,
    one batch result, etc.
    """

    id: str
    signal_type: WorkSignalType
    source_path: str  # File path, repo path, or URL
    project: str
    timestamp: datetime

    # Core content
    title: str
    description: str = ""

    # Flexible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Git-specific fields
    commit_hash: Optional[str] = None
    author: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)

    # Completion doc fields
    achievements: List[str] = field(default_factory=list)
    scope: Optional[str] = None  # "feature", "bugfix", "refactor", etc.

    # Batch result fields
    batch_id: Optional[str] = None
    tokens_used: int = 0

    # Processing state
    processed: bool = False
    absorbed_into: Optional[str] = None  # WorkItem ID if absorbed

    @classmethod
    def generate_id(cls, signal_type: WorkSignalType, source: str, timestamp: datetime) -> str:
        """Generate a deterministic ID for deduplication."""
        content = f"{signal_type.value}:{source}:{timestamp.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "signal_type": self.signal_type.value,
            "source_path": self.source_path,
            "project": self.project,
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata,
            "commit_hash": self.commit_hash,
            "author": self.author,
            "files_changed": self.files_changed,
            "achievements": self.achievements,
            "scope": self.scope,
            "batch_id": self.batch_id,
            "tokens_used": self.tokens_used,
            "processed": self.processed,
            "absorbed_into": self.absorbed_into,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkSignal":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            signal_type=WorkSignalType(data["signal_type"]),
            source_path=data["source_path"],
            project=data["project"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            title=data["title"],
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            commit_hash=data.get("commit_hash"),
            author=data.get("author"),
            files_changed=data.get("files_changed", []),
            achievements=data.get("achievements", []),
            scope=data.get("scope"),
            batch_id=data.get("batch_id"),
            tokens_used=data.get("tokens_used", 0),
            processed=data.get("processed", False),
            absorbed_into=data.get("absorbed_into"),
        )


@dataclass
class WorkItem:
    """
    A consolidated work item that may combine multiple signals.

    Represents a logical unit of work (e.g., "Implemented batch scheduler")
    that may span multiple commits, docs, etc.
    """

    id: str
    project: str
    title: str
    description: str = ""

    # Temporal tracking
    first_seen: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Source tracking
    signal_ids: List[str] = field(default_factory=list)
    signal_count: int = 0

    # Status and correlation
    status: WorkStatus = WorkStatus.DETECTED
    plan_step_id: Optional[str] = None  # Correlated plan step
    correlation_confidence: float = 0.0

    # Impact assessment
    files_touched: List[str] = field(default_factory=list)
    estimated_effort_hours: float = 0.0

    # Categorization
    tags: List[str] = field(default_factory=list)
    scope: Optional[str] = None  # "feature", "bugfix", "refactor", etc.

    # Flexible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_signal(self, signal: WorkSignal) -> None:
        """Add a signal to this work item."""
        if signal.id not in self.signal_ids:
            self.signal_ids.append(signal.id)
            self.signal_count = len(self.signal_ids)

            # Update timestamps
            if signal.timestamp < self.first_seen:
                self.first_seen = signal.timestamp
            if signal.timestamp > self.last_activity:
                self.last_activity = signal.timestamp

            # Merge files
            for f in signal.files_changed:
                if f not in self.files_touched:
                    self.files_touched.append(f)

            # Merge achievements as description
            if signal.achievements:
                if self.description:
                    self.description += "\n"
                self.description += "\n".join(f"- {a}" for a in signal.achievements)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "project": self.project,
            "title": self.title,
            "description": self.description,
            "first_seen": self.first_seen.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "signal_ids": self.signal_ids,
            "signal_count": self.signal_count,
            "status": self.status.value,
            "plan_step_id": self.plan_step_id,
            "correlation_confidence": self.correlation_confidence,
            "files_touched": self.files_touched,
            "estimated_effort_hours": self.estimated_effort_hours,
            "tags": self.tags,
            "scope": self.scope,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkItem":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            project=data["project"],
            title=data["title"],
            description=data.get("description", ""),
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            signal_ids=data.get("signal_ids", []),
            signal_count=data.get("signal_count", 0),
            status=WorkStatus(data.get("status", "detected")),
            plan_step_id=data.get("plan_step_id"),
            correlation_confidence=data.get("correlation_confidence", 0.0),
            files_touched=data.get("files_touched", []),
            estimated_effort_hours=data.get("estimated_effort_hours", 0.0),
            tags=data.get("tags", []),
            scope=data.get("scope"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ProgressEntry:
    """
    A progress record for tracking against plan steps.

    Links work items to plan steps with evidence.
    """

    id: str
    work_item_id: str
    plan_step_id: Optional[str]
    project: str
    timestamp: datetime

    # Progress data
    progress_delta: float = 0.0  # 0.0 to 1.0 increment
    cumulative_progress: float = 0.0  # Total progress for step

    # Evidence
    evidence_type: str = ""  # "commit", "doc", "batch", etc.
    evidence_summary: str = ""
    evidence_path: Optional[str] = None

    # Quality indicators
    confidence: float = 0.8
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "work_item_id": self.work_item_id,
            "plan_step_id": self.plan_step_id,
            "project": self.project,
            "timestamp": self.timestamp.isoformat(),
            "progress_delta": self.progress_delta,
            "cumulative_progress": self.cumulative_progress,
            "evidence_type": self.evidence_type,
            "evidence_summary": self.evidence_summary,
            "evidence_path": self.evidence_path,
            "confidence": self.confidence,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressEntry":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            work_item_id=data["work_item_id"],
            plan_step_id=data.get("plan_step_id"),
            project=data["project"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            progress_delta=data.get("progress_delta", 0.0),
            cumulative_progress=data.get("cumulative_progress", 0.0),
            evidence_type=data.get("evidence_type", ""),
            evidence_summary=data.get("evidence_summary", ""),
            evidence_path=data.get("evidence_path"),
            confidence=data.get("confidence", 0.8),
            verified=data.get("verified", False),
        )


@dataclass
class PlanDrift:
    """
    Tracks drift between plans and actual work.

    Identifies gaps like unplanned work, stale plans, scope creep, etc.
    """

    id: str
    project: str
    detected_at: datetime
    drift_type: DriftType

    # Severity
    severity: str = "info"  # "info", "warning", "critical"

    # References
    plan_step_id: Optional[str] = None
    work_item_id: Optional[str] = None

    # Details
    description: str = ""
    suggested_action: str = ""

    # Resolution tracking
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: str = ""

    def resolve(self, notes: str = "") -> None:
        """Mark this drift as resolved."""
        self.resolved = True
        self.resolved_at = datetime.now()
        self.resolution_notes = notes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "project": self.project,
            "detected_at": self.detected_at.isoformat(),
            "drift_type": self.drift_type.value,
            "severity": self.severity,
            "plan_step_id": self.plan_step_id,
            "work_item_id": self.work_item_id,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanDrift":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            project=data["project"],
            detected_at=datetime.fromisoformat(data["detected_at"]),
            drift_type=DriftType(data["drift_type"]),
            severity=data.get("severity", "info"),
            plan_step_id=data.get("plan_step_id"),
            work_item_id=data.get("work_item_id"),
            description=data.get("description", ""),
            suggested_action=data.get("suggested_action", ""),
            resolved=data.get("resolved", False),
            resolved_at=(
                datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None
            ),
            resolution_notes=data.get("resolution_notes", ""),
        )


@dataclass
class AbsorptionReport:
    """
    Summary of an absorption cycle.

    Provides metrics and audit trail for each absorption run.
    """

    id: str
    started_at: datetime
    completed_at: datetime

    # Counts
    signals_detected: int = 0
    signals_absorbed: int = 0
    work_items_created: int = 0
    work_items_updated: int = 0
    correlations_made: int = 0
    drifts_detected: int = 0

    # By project breakdown
    by_project: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Errors encountered
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Calculate duration of the absorption cycle."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success(self) -> bool:
        """Whether the absorption completed without critical errors."""
        return len(self.errors) == 0

    def add_project_stats(self, project: str, signals: int, items: int, correlations: int) -> None:
        """Add statistics for a project."""
        self.by_project[project] = {
            "signals": signals,
            "work_items": items,
            "correlations": correlations,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "signals_detected": self.signals_detected,
            "signals_absorbed": self.signals_absorbed,
            "work_items_created": self.work_items_created,
            "work_items_updated": self.work_items_updated,
            "correlations_made": self.correlations_made,
            "drifts_detected": self.drifts_detected,
            "by_project": self.by_project,
            "errors": self.errors,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AbsorptionReport":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]),
            signals_detected=data.get("signals_detected", 0),
            signals_absorbed=data.get("signals_absorbed", 0),
            work_items_created=data.get("work_items_created", 0),
            work_items_updated=data.get("work_items_updated", 0),
            correlations_made=data.get("correlations_made", 0),
            drifts_detected=data.get("drifts_detected", 0),
            by_project=data.get("by_project", {}),
            errors=data.get("errors", []),
        )

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Absorption Report: {self.id}",
            f"Duration: {self.duration_seconds:.1f}s",
            f"Signals: {self.signals_detected} detected, {self.signals_absorbed} absorbed",
            f"Work Items: {self.work_items_created} new, {self.work_items_updated} updated",
            f"Correlations: {self.correlations_made}",
            f"Drifts: {self.drifts_detected}",
        ]

        if self.by_project:
            lines.append("\nBy Project:")
            for project, stats in sorted(self.by_project.items()):
                lines.append(
                    f"  {project}: {stats.get('signals', 0)} signals, {stats.get('work_items', 0)} items"
                )

        if self.errors:
            lines.append(f"\nErrors ({len(self.errors)}):")
            for error in self.errors[:5]:
                lines.append(f"  - {error}")

        return "\n".join(lines)
