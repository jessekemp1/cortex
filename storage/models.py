"""Cortex Storage Models"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class Status(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Goal:
    id: str
    title: str
    priority: Priority = Priority.B
    status: Status = Status.PENDING
    project: Optional[str] = None
    success_criteria: Optional[str] = None
    deadline: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": (
                self.priority.value if isinstance(self.priority, Priority) else self.priority
            ),
            "status": (self.status.value if isinstance(self.status, Status) else self.status),
            "project": self.project,
            "success_criteria": self.success_criteria,
            "deadline": self.deadline,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        return cls(
            id=data["id"],
            title=data["title"],
            priority=Priority(data["priority"]) if data.get("priority") else Priority.B,
            status=Status(data["status"]) if data.get("status") else Status.PENDING,
            project=data.get("project"),
            success_criteria=data.get("success_criteria"),
            deadline=data.get("deadline"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Task:
    id: str
    title: str
    goal_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    source: Optional[str] = None
    source_file: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "goal_id": self.goal_id,
            "status": (self.status.value if isinstance(self.status, TaskStatus) else self.status),
            "source": self.source,
            "source_file": self.source_file,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            goal_id=data.get("goal_id"),
            status=(TaskStatus(data["status"]) if data.get("status") else TaskStatus.PENDING),
            source=data.get("source"),
            source_file=data.get("source_file"),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class Blocker:
    id: Optional[int] = None
    goal_id: Optional[str] = None
    project: Optional[str] = None
    description: str = ""
    resolved: bool = False
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "project": self.project,
            "description": self.description,
            "resolved": self.resolved,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Blocker":
        return cls(
            id=data.get("id"),
            goal_id=data.get("goal_id"),
            project=data.get("project"),
            description=data.get("description", ""),
            resolved=bool(data.get("resolved", False)),
            created_at=data.get("created_at"),
            resolved_at=data.get("resolved_at"),
        )


@dataclass
class Progress:
    id: Optional[int] = None
    goal_id: Optional[str] = None
    task_id: Optional[str] = None
    action: str = ""
    notes: str = ""
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "task_id": self.task_id,
            "action": self.action,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Progress":
        return cls(
            id=data.get("id"),
            goal_id=data.get("goal_id"),
            task_id=data.get("task_id"),
            action=data.get("action", ""),
            notes=data.get("notes", ""),
            timestamp=data.get("timestamp"),
        )
