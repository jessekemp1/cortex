"""
Capacity-Aware Scheduler - Uses ProcessMonitor to optimize task timing.

Provides intelligent scheduling recommendations based on:
- Current resource availability
- Historical usage patterns
- Task resource requirements
- Optimal execution windows
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import CapacityForecast


class TaskType(Enum):
    """Types of tasks that can be scheduled."""

    TEST = "test"
    BUILD = "build"
    DEPLOY = "deploy"
    AI_INFERENCE = "ai_inference"
    HEAVY_COMPUTATION = "heavy_computation"
    BATCH_PROCESSING = "batch_processing"
    GENERAL = "general"


class SchedulingPriority(Enum):
    """Priority levels for scheduling."""

    IMMEDIATE = "immediate"  # Run now regardless of capacity
    HIGH = "high"  # Run ASAP, but consider capacity
    NORMAL = "normal"  # Run when capacity available
    LOW = "low"  # Run during idle times only


@dataclass
class ScheduledTask:
    """A task with scheduling metadata."""

    task_id: str
    task_type: TaskType
    priority: SchedulingPriority
    estimated_cpu_percent: float = 50.0
    estimated_memory_mb: float = 1000.0
    estimated_duration_minutes: float = 10.0

    # Scheduling results
    recommended_start_time: Optional[datetime] = None
    capacity_forecast: Optional[CapacityForecast] = None
    can_run_now: bool = False
    scheduling_reason: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapacityScheduler:
    """
    Intelligent task scheduler based on resource capacity.

    Uses ProcessMonitor to analyze:
    - Current resource availability
    - Historical usage patterns
    - Idle time windows
    - Resource capacity headroom
    """

    def __init__(self, process_monitor):
        """
        Initialize the scheduler.

        Args:
            process_monitor: ProcessMonitor instance
        """
        self.monitor = process_monitor

        # Minimum resource thresholds for different task types
        # CPU thresholds: AI_INFERENCE lowered because batch AI tasks are
        # remote API calls (Anthropic), not local computation. The daemon's
        # own monitoring overhead (~30-50% CPU) was causing all tasks to defer.
        self.min_cpu_percent = {
            TaskType.TEST: 30.0,
            TaskType.BUILD: 40.0,
            TaskType.DEPLOY: 50.0,
            TaskType.AI_INFERENCE: 15.0,
            TaskType.HEAVY_COMPUTATION: 70.0,
            TaskType.BATCH_PROCESSING: 50.0,
            TaskType.GENERAL: 20.0,
        }

        self.min_memory_mb = {
            TaskType.TEST: 2000.0,
            TaskType.BUILD: 3000.0,
            TaskType.DEPLOY: 1000.0,
            TaskType.AI_INFERENCE: 4000.0,
            TaskType.HEAVY_COMPUTATION: 8000.0,
            TaskType.BATCH_PROCESSING: 4000.0,
            TaskType.GENERAL: 1000.0,
        }

    def can_run_now(
        self,
        task_type: TaskType,
        priority: SchedulingPriority = SchedulingPriority.NORMAL,
    ) -> tuple[bool, str]:
        """
        Check if a task can run now based on current capacity.

        Args:
            task_type: Type of task
            priority: Task priority

        Returns:
            (can_run, reason) tuple
        """
        # Get current resource status
        status = self.monitor.get_status()
        cpu_available = status["cpu_available"]
        memory_available_mb = status["memory_available_mb"]

        # IMMEDIATE priority always runs
        if priority == SchedulingPriority.IMMEDIATE:
            return True, "IMMEDIATE priority - running regardless of capacity"

        # Check CPU threshold
        min_cpu = self.min_cpu_percent.get(task_type, 30.0)
        if cpu_available < min_cpu:
            return (
                False,
                f"Insufficient CPU: {cpu_available:.1f}% available (need {min_cpu:.1f}%)",
            )

        # Check memory threshold
        min_memory = self.min_memory_mb.get(task_type, 1000.0)
        if memory_available_mb < min_memory:
            return (
                False,
                f"Insufficient memory: {memory_available_mb:.1f}MB available (need {min_memory:.1f}MB)",
            )

        # HIGH priority runs if minimum thresholds met
        if priority == SchedulingPriority.HIGH:
            return (
                True,
                f"HIGH priority - capacity available (CPU: {cpu_available:.1f}%, Memory: {memory_available_mb:.0f}MB)",
            )

        # For NORMAL priority, prefer better capacity headroom
        if cpu_available < min_cpu * 1.5:  # Want 50% more than minimum
            if priority == SchedulingPriority.LOW:
                return (
                    False,
                    f"LOW priority - waiting for more capacity (current: {cpu_available:.1f}%)",
                )
            # NORMAL can run but suggest deferring
            return True, f"Can run but capacity is tight (CPU: {cpu_available:.1f}%)"

        # Good capacity available
        return (
            True,
            f"Good capacity available (CPU: {cpu_available:.1f}%, Memory: {memory_available_mb:.0f}MB)",
        )

    def get_optimal_time(self, task_type: TaskType) -> CapacityForecast:
        """
        Get optimal time to run a task.

        Args:
            task_type: Type of task

        Returns:
            CapacityForecast with recommended timing
        """
        return self.monitor.optimizer.get_capacity_forecast(task_type.value)

    def schedule_task(
        self,
        task_id: str,
        task_type: TaskType,
        priority: SchedulingPriority = SchedulingPriority.NORMAL,
        estimated_cpu_percent: float = 50.0,
        estimated_memory_mb: float = 1000.0,
        estimated_duration_minutes: float = 10.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduledTask:
        """
        Schedule a task based on capacity.

        Args:
            task_id: Unique task identifier
            task_type: Type of task
            priority: Scheduling priority
            estimated_cpu_percent: Estimated CPU usage
            estimated_memory_mb: Estimated memory usage
            estimated_duration_minutes: Estimated duration
            metadata: Optional task metadata

        Returns:
            ScheduledTask with scheduling recommendation
        """
        # Check if can run now
        can_run, reason = self.can_run_now(task_type, priority)

        # Get capacity forecast
        forecast = self.get_optimal_time(task_type)

        # Determine recommended start time
        if can_run and priority in [
            SchedulingPriority.IMMEDIATE,
            SchedulingPriority.HIGH,
        ]:
            recommended_time = datetime.now()
            scheduling_reason = f"Running immediately - {reason}"
        elif can_run and forecast.best_time_to_run <= datetime.now() + timedelta(minutes=5):
            recommended_time = datetime.now()
            scheduling_reason = f"Running now - {reason}"
        else:
            recommended_time = forecast.best_time_to_run
            scheduling_reason = f"Deferring - {forecast.reasoning}"

        return ScheduledTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            estimated_cpu_percent=estimated_cpu_percent,
            estimated_memory_mb=estimated_memory_mb,
            estimated_duration_minutes=estimated_duration_minutes,
            recommended_start_time=recommended_time,
            capacity_forecast=forecast,
            can_run_now=can_run,
            scheduling_reason=scheduling_reason,
            metadata=metadata or {},
        )

    def schedule_multiple(self, tasks: List[Dict[str, Any]]) -> List[ScheduledTask]:
        """
        Schedule multiple tasks optimally.

        Args:
            tasks: List of task dictionaries with keys: task_id, task_type, priority, etc.

        Returns:
            List of ScheduledTask objects sorted by recommended start time
        """
        scheduled_tasks = []

        for task_dict in tasks:
            scheduled = self.schedule_task(
                task_id=task_dict["task_id"],
                task_type=TaskType(task_dict.get("task_type", "general")),
                priority=SchedulingPriority(task_dict.get("priority", "normal")),
                estimated_cpu_percent=task_dict.get("estimated_cpu_percent", 50.0),
                estimated_memory_mb=task_dict.get("estimated_memory_mb", 1000.0),
                estimated_duration_minutes=task_dict.get("estimated_duration_minutes", 10.0),
                metadata=task_dict.get("metadata"),
            )
            scheduled_tasks.append(scheduled)

        # Sort by priority (immediate first) then by recommended time
        priority_order = {
            SchedulingPriority.IMMEDIATE: 0,
            SchedulingPriority.HIGH: 1,
            SchedulingPriority.NORMAL: 2,
            SchedulingPriority.LOW: 3,
        }

        scheduled_tasks.sort(
            key=lambda t: (
                priority_order.get(t.priority, 4),
                t.recommended_start_time or datetime.max,
            )
        )

        return scheduled_tasks

    def get_idle_windows(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get idle time windows suitable for batch processing.

        Args:
            hours: Number of hours to look ahead

        Returns:
            List of idle window dictionaries
        """
        insights = self.monitor.analyzer.analyze_utilization_patterns(days=hours // 24 or 1)

        windows = []
        current_hour = datetime.now().hour

        for idle_hour in insights.idle_hours:
            # Calculate start time
            now = datetime.now()
            start_time = now.replace(hour=idle_hour, minute=0, second=0, microsecond=0)

            # If hour has passed, it's tomorrow
            if idle_hour <= current_hour:
                start_time += timedelta(days=1)

            windows.append(
                {
                    "start_time": start_time,
                    "hour": idle_hour,
                    "expected_cpu_available": insights.capacity_headroom,
                    "suitable_for": ["TEST", "BUILD", "BATCH_PROCESSING"],
                }
            )

        return windows

    def suggest_batch_schedule(
        self,
        batch_tasks: List[Dict[str, Any]],
        earliest_start: Optional[datetime] = None,
        latest_finish: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Suggest optimal schedule for batch tasks.

        Args:
            batch_tasks: List of tasks to schedule
            earliest_start: Earliest allowed start time
            latest_finish: Latest allowed finish time

        Returns:
            Dictionary with batch schedule
        """
        earliest_start = earliest_start or datetime.now()
        latest_finish = latest_finish or datetime.now() + timedelta(hours=24)

        # Get idle windows
        idle_windows = self.get_idle_windows(hours=24)

        # Filter windows within time constraints
        valid_windows = [
            w for w in idle_windows if earliest_start <= w["start_time"] <= latest_finish
        ]

        if not valid_windows:
            return {
                "can_schedule": False,
                "reason": "No idle windows available in the requested timeframe",
                "recommended_action": "Extend deadline or reduce task count",
            }

        # Estimate total duration
        total_duration = sum(t.get("estimated_duration_minutes", 10.0) for t in batch_tasks)

        # Find best window (earliest with enough capacity)
        best_window = valid_windows[0]

        return {
            "can_schedule": True,
            "recommended_start": best_window["start_time"],
            "window_hour": best_window["hour"],
            "total_duration_minutes": total_duration,
            "estimated_finish": best_window["start_time"] + timedelta(minutes=total_duration),
            "capacity_available": best_window["expected_cpu_available"],
            "task_count": len(batch_tasks),
            "reasoning": f"Idle window at {best_window['hour']:02d}:00 with {best_window['expected_cpu_available']:.0f}% capacity available",
        }

    def detect_task_type_from_description(self, description: str) -> TaskType:
        """
        Detect task type from description text.

        Args:
            description: Task description or title

        Returns:
            Detected TaskType
        """
        description_lower = description.lower()

        # Test-related
        if any(
            keyword in description_lower
            for keyword in ["test", "pytest", "unittest", "spec", "coverage"]
        ):
            return TaskType.TEST

        # Build-related
        if any(
            keyword in description_lower
            for keyword in ["build", "compile", "webpack", "docker", "package"]
        ):
            return TaskType.BUILD

        # Deploy-related
        if any(
            keyword in description_lower for keyword in ["deploy", "release", "publish", "ship"]
        ):
            return TaskType.DEPLOY

        # AI-related
        if any(
            keyword in description_lower
            for keyword in ["ai", "ml", "model", "inference", "llm", "claude"]
        ):
            return TaskType.AI_INFERENCE

        # Batch-related
        if any(
            keyword in description_lower
            for keyword in ["batch", "bulk", "migration", "import", "export"]
        ):
            return TaskType.BATCH_PROCESSING

        # Heavy computation
        if any(
            keyword in description_lower
            for keyword in ["analyze", "process", "compute", "calculate", "benchmark"]
        ):
            return TaskType.HEAVY_COMPUTATION

        return TaskType.GENERAL
