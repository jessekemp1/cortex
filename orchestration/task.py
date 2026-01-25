"""
Task dataclass for Cortex orchestration.

Represents a single unit of work that flows through the agent workflow:
queued → investigating → planning → implementing → testing → completed/failed
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class TaskPhase(str, Enum):
    """Task execution phases matching agent workflow"""
    QUEUED = "queued"
    INVESTIGATING = "investigating"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """
    Priority levels determining execution routing:
    - A (critical): Always realtime, immediate execution
    - B (important): Batch-eligible if deadline allows (>4 hours)
    - C (background): Batch-only, overnight processing
    """
    A = "A"  # Critical - realtime only
    B = "B"  # Important - batch-eligible
    C = "C"  # Background - batch-only


class TaskStatus(str, Enum):
    """Task lifecycle status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """
    A task in the Cortex orchestration system.

    Tracks work from queuing through completion, with support for
    dependency management, phase transitions, and cost estimation.
    """

    # Core identification
    id: str
    title: str
    description: str

    # Priority and routing
    priority: TaskPriority
    deadline: Optional[datetime] = None

    # Workflow state
    phase: TaskPhase = TaskPhase.QUEUED
    status: TaskStatus = TaskStatus.PENDING

    # Dependencies
    blocked_by: List[str] = field(default_factory=list)  # Task IDs that must complete first
    blocks: List[str] = field(default_factory=list)      # Task IDs that depend on this

    # Execution context
    prompt: Optional[str] = None           # Actual prompt for agent/batch
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context
    files_affected: List[str] = field(default_factory=list)

    # Cost estimation (rough tokens based on description length)
    estimated_input_tokens: int = field(default=0)
    estimated_output_tokens: int = field(default=4000)  # Generous default
    actual_input_tokens: int = field(default=0)
    actual_output_tokens: int = field(default=0)

    # Execution tracking
    execution_mode: Optional[str] = None   # "realtime" or "batch"
    batch_id: Optional[str] = None         # If batch-routed
    assigned_agent: Optional[str] = None   # If realtime-routed

    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    validation_passed: bool = False

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None           # "goal", "pattern", "security", etc.
    project: Optional[str] = None

    def __post_init__(self):
        """Calculate initial token estimate if not provided"""
        if self.estimated_input_tokens == 0:
            # Rough estimate: 4 chars per token
            desc_tokens = len(self.description) // 4
            prompt_tokens = len(self.prompt or "") // 4
            context_tokens = len(str(self.context)) // 4
            self.estimated_input_tokens = desc_tokens + prompt_tokens + context_tokens

    @property
    def total_estimated_tokens(self) -> int:
        """Total estimated tokens (input + output)"""
        return self.estimated_input_tokens + self.estimated_output_tokens

    @property
    def total_actual_tokens(self) -> int:
        """Total actual tokens used (if completed)"""
        return self.actual_input_tokens + self.actual_output_tokens

    @property
    def is_blocked(self) -> bool:
        """Check if task is blocked by dependencies"""
        return len(self.blocked_by) > 0

    @property
    def is_completed(self) -> bool:
        """Check if task completed successfully"""
        return self.status == TaskStatus.COMPLETED and self.phase == TaskPhase.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if task failed"""
        return self.status == TaskStatus.FAILED or self.phase == TaskPhase.FAILED

    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state (completed or failed)"""
        return self.is_completed or self.is_failed

    @property
    def hours_until_deadline(self) -> Optional[float]:
        """Hours remaining until deadline (None if no deadline)"""
        if self.deadline is None:
            return None
        delta = self.deadline - datetime.now()
        return delta.total_seconds() / 3600

    @property
    def is_urgent(self) -> bool:
        """Check if deadline is within 2 hours"""
        hours = self.hours_until_deadline
        return hours is not None and hours <= 2.0

    def advance_phase(self) -> None:
        """Advance to next phase in workflow"""
        phase_order = [
            TaskPhase.QUEUED,
            TaskPhase.INVESTIGATING,
            TaskPhase.PLANNING,
            TaskPhase.IMPLEMENTING,
            TaskPhase.TESTING,
            TaskPhase.COMPLETED,
        ]

        if self.phase in phase_order:
            current_idx = phase_order.index(self.phase)
            if current_idx < len(phase_order) - 1:
                self.phase = phase_order[current_idx + 1]

                # Update status when entering terminal phase
                if self.phase == TaskPhase.COMPLETED:
                    self.status = TaskStatus.COMPLETED
                    self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error message"""
        self.phase = TaskPhase.FAILED
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def mark_started(self) -> None:
        """Mark task as started"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_scheduled(self, execution_mode: str) -> None:
        """Mark task as scheduled for execution"""
        self.status = TaskStatus.SCHEDULED
        self.execution_mode = execution_mode

    def unblock(self, completed_task_id: str) -> None:
        """Remove dependency when blocking task completes"""
        if completed_task_id in self.blocked_by:
            self.blocked_by.remove(completed_task_id)

        # Update status if no longer blocked
        if not self.is_blocked and self.status == TaskStatus.BLOCKED:
            self.status = TaskStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "phase": self.phase.value,
            "status": self.status.value,
            "blocked_by": self.blocked_by,
            "blocks": self.blocks,
            "prompt": self.prompt,
            "context": self.context,
            "files_affected": self.files_affected,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "actual_input_tokens": self.actual_input_tokens,
            "actual_output_tokens": self.actual_output_tokens,
            "execution_mode": self.execution_mode,
            "batch_id": self.batch_id,
            "assigned_agent": self.assigned_agent,
            "result": self.result,
            "error": self.error,
            "validation_passed": self.validation_passed,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "source": self.source,
            "project": self.project,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task from dict (deserialize from storage)"""
        # Convert datetime strings back to datetime objects
        for field_name in ["deadline", "created_at", "started_at", "completed_at"]:
            if data.get(field_name):
                data[field_name] = datetime.fromisoformat(data[field_name])

        # Convert enum strings to enums
        data["priority"] = TaskPriority(data["priority"])
        data["phase"] = TaskPhase(data["phase"])
        data["status"] = TaskStatus(data["status"])

        return cls(**data)
