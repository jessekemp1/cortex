"""
Comprehensive data models for Cortex orchestration system.

Unifies concepts from:
- batch/orchestrator.py (JobState, APIJob, LocalJob)
- intelligence/process_monitor/batch_queue.py (BatchTask)
- batch/intelligent_orchestrator.py (BatchWorkItem)
- orchestration/task.py (Task, TaskPhase)

Design Philosophy:
- Single unified Task model (already defined in task.py)
- ExecutionBackend enum distinguishes local vs API vs realtime execution
- ValidationCriteria encapsulates test requirements and success patterns
- WorkerState tracks agent capacity and load
- TraceEvent provides audit trail for all decisions
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Re-export core task models from task.py
from .task import Task


class ExecutionBackend(str, Enum):
    """
    Backend execution system for tasks.

    Determines how and where a task is executed:
    - LOCAL_SYNC: Immediate local shell execution (ProcessMonitor, foreground)
    - LOCAL_BATCH: Scheduled local execution (ProcessMonitor, background queue)
    - API_BATCH: Anthropic Batch API (overnight processing)
    - API_REALTIME: Anthropic Messages API (immediate processing)
    """

    LOCAL_SYNC = "local_sync"  # Shell command, immediate
    LOCAL_BATCH = "local_batch"  # Shell command, queued
    API_BATCH = "api_batch"  # LLM analysis, overnight
    API_REALTIME = "api_realtime"  # LLM analysis, immediate


class WorkerRole(str, Enum):
    """Agent roles in the orchestration system."""

    SUPERVISOR = "supervisor"  # Delegates and monitors
    INVESTIGATOR = "investigator"  # Analyzes and researches
    PLANNER = "planner"  # Designs solutions
    IMPLEMENTER = "implementer"  # Writes code
    TESTER = "tester"  # Validates quality
    REVIEWER = "reviewer"  # Code review


class TraceEventType(str, Enum):
    """Types of trace events for audit logging."""

    TASK_CREATED = "task_created"
    TASK_SCHEDULED = "task_scheduled"
    TASK_STARTED = "task_started"
    TASK_PHASE_CHANGED = "task_phase_changed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRIED = "task_retried"
    TASK_BLOCKED = "task_blocked"
    TASK_UNBLOCKED = "task_unblocked"
    WORKER_ASSIGNED = "worker_assigned"
    WORKER_CAPACITY_CHANGED = "worker_capacity_changed"
    BACKEND_SELECTED = "backend_selected"
    VALIDATION_RUN = "validation_run"
    DECISION_MADE = "decision_made"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class ValidationCriteria:
    """
    Test requirements and success patterns for task validation.

    Defines what must pass before a task is considered complete.
    """

    # Test requirements
    requires_unit_tests: bool = False
    requires_integration_tests: bool = False
    requires_e2e_tests: bool = False

    # Test coverage targets
    min_coverage_percent: Optional[float] = None  # e.g., 80.0

    # Required test commands (must all pass)
    test_commands: List[str] = field(default_factory=list)

    # Success patterns (regex patterns to find in output)
    success_patterns: List[str] = field(default_factory=list)

    # Failure patterns (if found, validation fails)
    failure_patterns: List[str] = field(default_factory=list)

    # File validation (files that must exist after task completion)
    required_files: List[str] = field(default_factory=list)

    # Performance requirements
    max_execution_seconds: Optional[int] = None

    # Custom validation logic
    custom_validator: Optional[str] = None  # Path to custom validator script

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "requires_unit_tests": self.requires_unit_tests,
            "requires_integration_tests": self.requires_integration_tests,
            "requires_e2e_tests": self.requires_e2e_tests,
            "min_coverage_percent": self.min_coverage_percent,
            "test_commands": self.test_commands,
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns,
            "required_files": self.required_files,
            "max_execution_seconds": self.max_execution_seconds,
            "custom_validator": self.custom_validator,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationCriteria":
        """Deserialize from dict."""
        return cls(**data)

    def is_empty(self) -> bool:
        """Check if no validation criteria are specified."""
        return (
            not self.requires_unit_tests
            and not self.requires_integration_tests
            and not self.requires_e2e_tests
            and not self.test_commands
            and not self.success_patterns
            and not self.required_files
            and self.custom_validator is None
        )


@dataclass
class WorkerState:
    """
    Tracks state and capacity of an agent/worker in the system.

    Used by supervisor to make delegation decisions.
    """

    # Identity
    worker_id: str
    role: WorkerRole

    # Capacity tracking
    max_concurrent_tasks: int = 3  # Max tasks this worker can handle
    current_task_count: int = 0  # Current active tasks

    # Availability
    is_available: bool = True
    unavailable_reason: Optional[str] = None

    # Performance metrics
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    average_task_duration_minutes: float = 0.0

    # Current load
    assigned_task_ids: List[str] = field(default_factory=list)

    # Specialization (optional tags for routing)
    specialties: List[str] = field(default_factory=list)  # e.g., ["python", "testing", "apis"]

    # Timestamps
    last_task_started_at: Optional[datetime] = None
    last_task_completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def capacity_percent(self) -> float:
        """Current capacity utilization (0-100)."""
        if self.max_concurrent_tasks == 0:
            return 100.0
        return (self.current_task_count / self.max_concurrent_tasks) * 100.0

    @property
    def is_at_capacity(self) -> bool:
        """Check if worker is at max capacity."""
        return self.current_task_count >= self.max_concurrent_tasks

    @property
    def can_accept_task(self) -> bool:
        """Check if worker can accept a new task."""
        return self.is_available and not self.is_at_capacity

    @property
    def success_rate(self) -> float:
        """Task success rate (0-1)."""
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 0.0
        return self.total_tasks_completed / total

    def assign_task(self, task_id: str) -> None:
        """Assign a task to this worker."""
        if task_id not in self.assigned_task_ids:
            self.assigned_task_ids.append(task_id)
            self.current_task_count += 1
            self.last_task_started_at = datetime.now()
            self.updated_at = datetime.now()

    def complete_task(self, task_id: str, success: bool, duration_minutes: float) -> None:
        """Mark task as completed and update metrics."""
        if task_id in self.assigned_task_ids:
            self.assigned_task_ids.remove(task_id)
            self.current_task_count = max(0, self.current_task_count - 1)

            if success:
                self.total_tasks_completed += 1
            else:
                self.total_tasks_failed += 1

            # Update average duration (exponential moving average)
            alpha = 0.3  # Weight for new observation
            if self.average_task_duration_minutes == 0:
                self.average_task_duration_minutes = duration_minutes
            else:
                self.average_task_duration_minutes = (
                    alpha * duration_minutes + (1 - alpha) * self.average_task_duration_minutes
                )

            self.last_task_completed_at = datetime.now()
            self.updated_at = datetime.now()

    def mark_unavailable(self, reason: str) -> None:
        """Mark worker as unavailable."""
        self.is_available = False
        self.unavailable_reason = reason
        self.updated_at = datetime.now()

    def mark_available(self) -> None:
        """Mark worker as available."""
        self.is_available = True
        self.unavailable_reason = None
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "worker_id": self.worker_id,
            "role": self.role.value,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "current_task_count": self.current_task_count,
            "is_available": self.is_available,
            "unavailable_reason": self.unavailable_reason,
            "total_tasks_completed": self.total_tasks_completed,
            "total_tasks_failed": self.total_tasks_failed,
            "average_task_duration_minutes": self.average_task_duration_minutes,
            "assigned_task_ids": self.assigned_task_ids,
            "specialties": self.specialties,
            "last_task_started_at": (
                self.last_task_started_at.isoformat() if self.last_task_started_at else None
            ),
            "last_task_completed_at": (
                self.last_task_completed_at.isoformat() if self.last_task_completed_at else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerState":
        """Deserialize from dict."""
        # Convert datetime strings
        for field_name in [
            "last_task_started_at",
            "last_task_completed_at",
            "created_at",
            "updated_at",
        ]:
            if data.get(field_name):
                data[field_name] = datetime.fromisoformat(data[field_name])

        # Convert enum
        data["role"] = WorkerRole(data["role"])

        return cls(**data)


@dataclass
class TraceEvent:
    """
    Audit trail entry for orchestration decisions and events.

    Records all significant actions for debugging and analysis.
    """

    # Event identity
    event_id: str
    event_type: TraceEventType
    timestamp: datetime = field(default_factory=datetime.now)

    # Context
    task_id: Optional[str] = None
    worker_id: Optional[str] = None

    # Event data
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    phase: Optional[str] = None  # Task phase when event occurred
    backend: Optional[str] = None  # Execution backend if relevant

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "message": self.message,
            "details": json.dumps(self.details),
            "phase": self.phase,
            "backend": self.backend,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceEvent":
        """Deserialize from dict."""
        # Convert datetime
        if data.get("timestamp"):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        # Convert enum
        data["event_type"] = TraceEventType(data["event_type"])

        # Parse JSON details
        if isinstance(data.get("details"), str):
            data["details"] = json.loads(data["details"]) if data["details"] else {}

        return cls(**data)

    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]",
            f"{self.event_type.value}:",
            self.message,
        ]

        if self.task_id:
            parts.append(f"(task: {self.task_id})")
        if self.worker_id:
            parts.append(f"(worker: {self.worker_id})")

        return " ".join(parts)


# Helper functions for creating common trace events


def create_task_event(
    event_type: TraceEventType,
    task: Task,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> TraceEvent:
    """Create a trace event for a task action."""
    import uuid

    return TraceEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        task_id=task.id,
        message=message,
        details=details or {},
        phase=task.phase.value,
    )


def create_worker_event(
    event_type: TraceEventType,
    worker: WorkerState,
    message: str,
    task_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> TraceEvent:
    """Create a trace event for a worker action."""
    import uuid

    return TraceEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        worker_id=worker.worker_id,
        task_id=task_id,
        message=message,
        details=details or {},
    )


def create_decision_event(
    message: str,
    task_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> TraceEvent:
    """Create a trace event for a routing/scheduling decision."""
    import uuid

    return TraceEvent(
        event_id=str(uuid.uuid4()),
        event_type=TraceEventType.DECISION_MADE,
        task_id=task_id,
        message=message,
        details=details or {},
    )
