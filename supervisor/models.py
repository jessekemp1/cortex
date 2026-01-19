"""
Data models for the Cortex Supervisor.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskTarget(Enum):
    """Execution target for a routed task."""

    SHELL = "shell"  # Execute via BatchExecutor (subprocess)
    AI_BATCH = "ai_batch"  # Submit to Anthropic Batch API


class WorkItemPriority(Enum):
    """Priority levels for work items."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class WorkItem:
    """A unit of work discovered by the supervisor."""

    id: str  # Unique identifier
    source: str  # Where this came from (recommendation, alert, orphan, etc.)
    task_type: str  # Type of task (test, research, analysis, etc.)
    description: str  # Human-readable description

    # Execution details
    command: Optional[str] = None  # Shell command (for shell tasks)
    prompt: Optional[str] = None  # AI prompt (for AI tasks)
    system_prompt: Optional[str] = None  # System prompt for AI

    # Metadata
    project: Optional[str] = None
    priority: WorkItemPriority = WorkItemPriority.MEDIUM
    confidence: float = 0.5  # How confident we are this is valuable work
    estimated_tokens: int = 0  # Estimated tokens for AI tasks

    # Context
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def priority_score(self) -> float:
        """Numeric priority for sorting (higher = more important)."""
        priority_weights = {
            WorkItemPriority.CRITICAL: 4.0,
            WorkItemPriority.HIGH: 3.0,
            WorkItemPriority.MEDIUM: 2.0,
            WorkItemPriority.LOW: 1.0,
        }
        return priority_weights.get(self.priority, 2.0) * self.confidence


@dataclass
class RoutedTask:
    """A work item that has been routed to an execution target."""

    work_item: WorkItem
    target: TaskTarget
    priority: str
    estimated_tokens: int = 0

    def as_shell_task(self) -> Dict[str, Any]:
        """Convert to BatchTaskQueue.add_task() kwargs."""
        return {
            "command": self.work_item.command,
            "task_type": self.work_item.task_type,
            "description": self.work_item.description,
            "priority": self.priority,
            "metadata": {
                "source": self.work_item.source,
                "work_item_id": self.work_item.id,
                **self.work_item.metadata,
            },
        }

    def as_ai_request(self) -> Dict[str, Any]:
        """Convert to BatchAPIClient request format."""
        return {
            "custom_id": self.work_item.id,
            "params": {
                "messages": [{"role": "user", "content": self.work_item.prompt}],
                "system": self.work_item.system_prompt or "",
                "max_tokens": 4096,
            },
        }


@dataclass
class TickResult:
    """Result of a single supervisor tick."""

    timestamp: datetime = field(default_factory=datetime.now)

    # Work discovery
    work_discovered: int = 0
    work_items: List[WorkItem] = field(default_factory=list)

    # Shell execution
    shell_tasks_started: int = 0
    shell_tasks_completed: int = 0
    shell_task_ids: List[str] = field(default_factory=list)

    # AI batching
    ai_tasks_queued: int = 0
    ai_batch_submitted: bool = False
    ai_batch_id: Optional[str] = None
    ai_results_received: int = 0

    # Health
    tasks_healed: int = 0
    healed_task_ids: List[str] = field(default_factory=list)

    # Errors
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "work_discovered": self.work_discovered,
            "shell_tasks_started": self.shell_tasks_started,
            "shell_tasks_completed": self.shell_tasks_completed,
            "shell_task_ids": self.shell_task_ids,
            "ai_tasks_queued": self.ai_tasks_queued,
            "ai_batch_submitted": self.ai_batch_submitted,
            "ai_batch_id": self.ai_batch_id,
            "ai_results_received": self.ai_results_received,
            "tasks_healed": self.tasks_healed,
            "healed_task_ids": self.healed_task_ids,
            "errors": self.errors,
        }

    def summary(self) -> str:
        """One-line summary for logging."""
        parts = []
        if self.work_discovered:
            parts.append(f"discovered={self.work_discovered}")
        if self.shell_tasks_started:
            parts.append(f"shell_started={self.shell_tasks_started}")
        if self.tasks_healed:
            parts.append(f"healed={self.tasks_healed}")
        if self.ai_batch_submitted:
            parts.append(f"ai_batch={self.ai_batch_id[:8]}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return " | ".join(parts) if parts else "no_action"
