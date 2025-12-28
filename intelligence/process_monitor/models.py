"""
Data models for process monitoring system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class ProcessCategory(str, Enum):
    """Category for process classification."""
    AI_TOOL = "ai_tool"                    # Claude, Ollama, Copilot, etc.
    DEV_SERVICE = "dev_service"            # Uvicorn, Streamlit, Postgres, etc.
    BACKGROUND_AGENT = "background_agent"  # LaunchAgents, batch jobs, cron
    CONTAINER = "container"                # Docker, Colima
    BUILD_TOOL = "build_tool"              # pytest, npm, expo, etc.
    SYSTEM = "system"                      # System processes
    OTHER = "other"                        # Uncategorized


class ProcessStatus(str, Enum):
    """Process status."""
    RUNNING = "running"
    SLEEPING = "sleeping"
    ZOMBIE = "zombie"
    STOPPED = "stopped"
    DISK_SLEEP = "disk_sleep"


class AnomalyType(str, Enum):
    """Types of process anomalies."""
    CPU_SPIKE = "cpu_spike"
    MEMORY_LEAK = "memory_leak"
    ZOMBIE_PROCESS = "zombie_process"
    SERVICE_DOWN = "service_down"
    IDLE_WASTE = "idle_waste"
    UNUSUAL_BEHAVIOR = "unusual_behavior"


class WasteType(str, Enum):
    """Types of resource waste."""
    IDLE_SERVICE = "idle_service"
    ORPHANED_CONTAINER = "orphaned_container"
    ZOMBIE_PROCESS = "zombie_process"
    DUPLICATE_PROCESS = "duplicate_process"
    HIGH_MEMORY_IDLE = "high_memory_idle"


@dataclass
class ProcessSnapshot:
    """Snapshot of a single process at a point in time."""
    pid: int
    name: str
    category: ProcessCategory
    cpu_percent: float
    memory_mb: float
    status: ProcessStatus
    start_time: datetime
    command: str
    port: Optional[int] = None
    parent_pid: Optional[int] = None
    username: Optional[str] = None
    num_threads: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pid": self.pid,
            "name": self.name,
            "category": self.category.value,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "command": self.command,
            "port": self.port,
            "parent_pid": self.parent_pid,
            "username": self.username,
            "num_threads": self.num_threads,
        }


@dataclass
class ResourceMetric:
    """System-wide resource metrics at a point in time."""
    timestamp: datetime
    total_cpu_percent: float
    available_memory_mb: float
    total_memory_mb: float
    process_count: int
    ai_tool_cpu: float = 0.0
    ai_tool_memory: float = 0.0
    dev_service_cpu: float = 0.0
    dev_service_memory: float = 0.0
    docker_memory_mb: float = 0.0
    docker_cpu: float = 0.0

    @property
    def memory_usage_percent(self) -> float:
        """Calculate memory usage percentage."""
        if self.total_memory_mb == 0:
            return 0.0
        used = self.total_memory_mb - self.available_memory_mb
        return (used / self.total_memory_mb) * 100

    @property
    def cpu_available_percent(self) -> float:
        """Calculate available CPU percentage."""
        return max(0.0, 100.0 - self.total_cpu_percent)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_cpu_percent": self.total_cpu_percent,
            "available_memory_mb": self.available_memory_mb,
            "total_memory_mb": self.total_memory_mb,
            "memory_usage_percent": self.memory_usage_percent,
            "cpu_available_percent": self.cpu_available_percent,
            "process_count": self.process_count,
            "ai_tool_cpu": self.ai_tool_cpu,
            "ai_tool_memory": self.ai_tool_memory,
            "dev_service_cpu": self.dev_service_cpu,
            "dev_service_memory": self.dev_service_memory,
            "docker_memory_mb": self.docker_memory_mb,
            "docker_cpu": self.docker_cpu,
        }


@dataclass
class Anomaly:
    """Detected process anomaly."""
    timestamp: datetime
    process_name: str
    process_pid: int
    anomaly_type: AnomalyType
    severity: str  # CRITICAL, WARNING, INFO
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "process_name": self.process_name,
            "process_pid": self.process_pid,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class WasteItem:
    """Identified resource waste."""
    process_name: str
    process_pid: int
    waste_type: WasteType
    resource_cost: str  # Human-readable cost (e.g., "2.5 GB RAM", "15% CPU")
    recommendation: str
    auto_actionable: bool = False  # Can we auto-fix this?
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "process_name": self.process_name,
            "process_pid": self.process_pid,
            "waste_type": self.waste_type.value,
            "resource_cost": self.resource_cost,
            "recommendation": self.recommendation,
            "auto_actionable": self.auto_actionable,
            "metadata": self.metadata,
        }


@dataclass
class UtilizationInsights:
    """System utilization pattern insights."""
    peak_hours: List[int]  # Hours of day with highest utilization
    idle_hours: List[int]  # Hours of day with lowest utilization
    avg_cpu_by_hour: Dict[int, float]  # Average CPU by hour of day
    avg_memory_by_hour: Dict[int, float]  # Average memory by hour of day
    capacity_headroom: float  # Average available capacity percentage

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "peak_hours": self.peak_hours,
            "idle_hours": self.idle_hours,
            "avg_cpu_by_hour": self.avg_cpu_by_hour,
            "avg_memory_by_hour": self.avg_memory_by_hour,
            "capacity_headroom": self.capacity_headroom,
        }


@dataclass
class AIToolInsights:
    """AI tool usage insights."""
    tool_name: str
    usage_hours: float  # Total hours active
    idle_hours: float  # Total hours idle but running
    avg_cpu: float  # Average CPU when active
    avg_memory: float  # Average memory usage
    cost_estimate: Optional[str] = None  # Estimated cost (for API-based tools)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "usage_hours": self.usage_hours,
            "idle_hours": self.idle_hours,
            "avg_cpu": self.avg_cpu,
            "avg_memory": self.avg_memory,
            "cost_estimate": self.cost_estimate,
        }


@dataclass
class DevPatterns:
    """Development workflow patterns."""
    active_coding_hours: List[int]  # Hours when coding activity is high
    testing_hours: List[int]  # Hours when tests are frequently run
    build_frequency: float  # Average builds per day
    deployment_times: List[datetime]  # Recent deployment timestamps

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "active_coding_hours": self.active_coding_hours,
            "testing_hours": self.testing_hours,
            "build_frequency": self.build_frequency,
            "deployment_times": [dt.isoformat() for dt in self.deployment_times],
        }


@dataclass
class Optimization:
    """Resource optimization suggestion."""
    title: str
    description: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    estimated_savings: str  # Human-readable savings estimate
    action_type: str  # STOP_SERVICE, SCHEDULE_TASK, ADJUST_LIMITS, etc.
    action_command: Optional[str] = None  # Command to execute
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "estimated_savings": self.estimated_savings,
            "action_type": self.action_type,
            "action_command": self.action_command,
            "metadata": self.metadata,
        }


@dataclass
class CapacityForecast:
    """Capacity forecast for task scheduling."""
    task_type: str  # TEST, BUILD, DEPLOY, AI_INFERENCE, etc.
    best_time_to_run: datetime
    expected_duration_minutes: float
    resource_availability: float  # 0-100 percentage
    confidence: float  # 0-1 confidence in forecast
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_type": self.task_type,
            "best_time_to_run": self.best_time_to_run.isoformat(),
            "expected_duration_minutes": self.expected_duration_minutes,
            "resource_availability": self.resource_availability,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
