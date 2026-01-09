"""Data models for Cortex runtime.

Defines the core data structures for agent execution,
status tracking, and event handling.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(str, Enum):
    """Trigger type for agent execution."""

    SCHEDULED = "scheduled"
    EVENT = "event"
    MANUAL = "manual"


class AgentResult(BaseModel):
    """Result of agent execution."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class WebhookEvent(BaseModel):
    """Webhook event payload."""

    event_type: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskSchedule(BaseModel):
    """Schedule configuration for a task."""

    agent_id: str
    cron_expression: str
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None


class AgentMetadata(BaseModel):
    """Metadata for an agent."""

    agent_id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    schedule: Optional[str] = None
    webhook_path: Optional[str] = None
