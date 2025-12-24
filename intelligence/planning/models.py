"""
Data models for the Cortex Planning system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path


class PlanStatus(Enum):
    """Status of a plan."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class StepStatus(Enum):
    """Status of a plan step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class PlanPriority(Enum):
    """Priority level of a plan."""
    CRITICAL = 1  # Must do now
    HIGH = 2      # Should do soon
    MEDIUM = 3    # Important but not urgent
    LOW = 4       # Nice to have


@dataclass
class PlanStep:
    """
    A single step in a plan.

    Attributes:
        id: Unique step identifier
        title: Brief step description
        description: Detailed step description
        status: Current step status
        estimated_time: Estimated time in minutes
        actual_time: Actual time taken in minutes
        dependencies: IDs of steps this depends on
        files: Files to modify/create
        validation: How to validate completion
        notes: Additional notes
        started_at: When step was started
        completed_at: When step was completed
    """
    id: str
    title: str
    description: str
    status: StepStatus = StepStatus.PENDING
    estimated_time: Optional[int] = None  # minutes
    actual_time: Optional[int] = None  # minutes
    dependencies: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    validation: Optional[str] = None
    notes: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def start(self):
        """Mark step as in progress."""
        self.status = StepStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self):
        """Mark step as completed."""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now()
        if self.started_at:
            self.actual_time = int((self.completed_at - self.started_at).total_seconds() / 60)

    def skip(self, reason: str = ""):
        """Skip this step."""
        self.status = StepStatus.SKIPPED
        if reason:
            self.notes += f"\nSkipped: {reason}"

    def block(self, reason: str):
        """Block this step."""
        self.status = StepStatus.BLOCKED
        self.notes += f"\nBlocked: {reason}"

    def can_start(self, completed_steps: List[str]) -> bool:
        """Check if this step can start based on dependencies."""
        return all(dep_id in completed_steps for dep_id in self.dependencies)


@dataclass
class Plan:
    """
    A complete execution plan.

    Attributes:
        id: Unique plan identifier
        title: Plan title
        description: Plan description
        priority: Plan priority
        status: Current plan status
        steps: List of plan steps
        created_at: Creation timestamp
        started_at: When execution started
        completed_at: When execution completed
        estimated_total_time: Total estimated time
        actual_total_time: Total actual time
        tags: Categorization tags
        metadata: Additional metadata
    """
    id: str
    title: str
    description: str
    priority: PlanPriority
    status: PlanStatus = PlanStatus.DRAFT
    steps: List[PlanStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_total_time: Optional[int] = None  # minutes
    actual_total_time: Optional[int] = None  # minutes
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: PlanStep):
        """Add a step to the plan."""
        self.steps.append(step)
        self._recalculate_estimates()

    def start(self):
        """Mark plan as active."""
        self.status = PlanStatus.ACTIVE
        self.started_at = datetime.now()

    def complete(self):
        """Mark plan as completed."""
        self.status = PlanStatus.COMPLETED
        self.completed_at = datetime.now()
        if self.started_at:
            self.actual_total_time = int((self.completed_at - self.started_at).total_seconds() / 60)

    def cancel(self, reason: str = ""):
        """Cancel the plan."""
        self.status = PlanStatus.CANCELLED
        if reason:
            self.metadata['cancellation_reason'] = reason

    def block(self, reason: str):
        """Block the plan."""
        self.status = PlanStatus.BLOCKED
        self.metadata['block_reason'] = reason

    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next step that can be executed."""
        completed_ids = [s.id for s in self.steps if s.status == StepStatus.COMPLETED]

        for step in self.steps:
            if step.status == StepStatus.PENDING and step.can_start(completed_ids):
                return step

        return None

    def get_progress(self) -> Dict[str, Any]:
        """Get plan progress statistics."""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        in_progress = sum(1 for s in self.steps if s.status == StepStatus.IN_PROGRESS)
        blocked = sum(1 for s in self.steps if s.status == StepStatus.BLOCKED)

        return {
            'total_steps': total,
            'completed': completed,
            'in_progress': in_progress,
            'blocked': blocked,
            'pending': total - completed - in_progress - blocked,
            'completion_pct': (completed / total * 100) if total > 0 else 0,
            'estimated_time_remaining': self._calculate_time_remaining(),
        }

    def _recalculate_estimates(self):
        """Recalculate total estimated time."""
        self.estimated_total_time = sum(
            s.estimated_time for s in self.steps if s.estimated_time
        )

    def _calculate_time_remaining(self) -> Optional[int]:
        """Calculate estimated time remaining."""
        remaining_time = sum(
            s.estimated_time
            for s in self.steps
            if s.status in [StepStatus.PENDING, StepStatus.IN_PROGRESS] and s.estimated_time
        )
        return remaining_time if remaining_time > 0 else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary for serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority.value,
            'status': self.status.value,
            'steps': [
                {
                    'id': s.id,
                    'title': s.title,
                    'description': s.description,
                    'status': s.status.value,
                    'estimated_time': s.estimated_time,
                    'actual_time': s.actual_time,
                    'dependencies': s.dependencies,
                    'files': s.files,
                    'validation': s.validation,
                    'notes': s.notes,
                    'started_at': s.started_at.isoformat() if s.started_at else None,
                    'completed_at': s.completed_at.isoformat() if s.completed_at else None,
                    'metadata': s.metadata,
                }
                for s in self.steps
            ],
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_total_time': self.estimated_total_time,
            'actual_total_time': self.actual_total_time,
            'tags': self.tags,
            'metadata': self.metadata,
            'progress': self.get_progress(),
        }

    def to_markdown(self) -> str:
        """Convert plan to markdown format."""
        lines = [
            f"# {self.title}",
            "",
            f"**Status:** {self.status.value}",
            f"**Priority:** {self.priority.name}",
            f"**Created:** {self.created_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Description",
            "",
            self.description,
            "",
            "## Progress",
            "",
        ]

        progress = self.get_progress()
        lines.extend([
            f"- **Completed:** {progress['completed']}/{progress['total_steps']} steps ({progress['completion_pct']:.1f}%)",
            f"- **In Progress:** {progress['in_progress']}",
            f"- **Blocked:** {progress['blocked']}",
            f"- **Pending:** {progress['pending']}",
        ])

        if self.estimated_total_time:
            lines.append(f"- **Estimated Time:** {self.estimated_total_time} minutes")
        if progress['estimated_time_remaining']:
            lines.append(f"- **Time Remaining:** {progress['estimated_time_remaining']} minutes")

        lines.extend([
            "",
            "## Steps",
            "",
        ])

        for i, step in enumerate(self.steps, 1):
            status_icon = {
                StepStatus.COMPLETED: "✅",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.BLOCKED: "🚫",
                StepStatus.SKIPPED: "⏭️",
                StepStatus.PENDING: "⏸️",
            }.get(step.status, "❓")

            lines.append(f"### {i}. {status_icon} {step.title}")
            lines.append("")
            lines.append(step.description)

            if step.dependencies:
                lines.append(f"\n**Dependencies:** {', '.join(step.dependencies)}")
            if step.files:
                lines.append(f"\n**Files:** {', '.join(step.files)}")
            if step.validation:
                lines.append(f"\n**Validation:** {step.validation}")
            if step.estimated_time:
                lines.append(f"\n**Estimated Time:** {step.estimated_time} minutes")
            if step.notes:
                lines.append(f"\n**Notes:** {step.notes}")

            lines.append("")

        return "\n".join(lines)
