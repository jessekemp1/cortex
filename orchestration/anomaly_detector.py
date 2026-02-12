"""
Active project anomaly detection system for Cortex orchestration.

Provides 7 specialized detectors for identifying orchestration inefficiencies:
1. ContextSwitchingDetector - Too many active projects
2. PlanningGapDetector - Active projects without active goals
3. StuckTasksDetector - Tasks stalled in same phase too long
4. DependencyDeadlockDetector - Circular dependency chains
5. ResourceWasteDetector - Idle workers with queued tasks
6. PriorityInversionDetector - High priority blocked by low priority
7. BatchInefficiencyDetector - Underutilized batch queue

Architecture:
- Abstract base class AnomalyDetector with pluggable detectors
- OrchestrationAnomalyManager orchestrates detection and deduplication
- Database persistence for anomaly tracking and trending
"""

import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .database import OrchestrationDatabase
from .models import TaskPriority, TaskStatus


class AnomalyType(str, Enum):
    """Types of orchestration anomalies."""

    CONTEXT_SWITCHING_RISK = "context_switching_risk"
    PLANNING_GAP = "planning_gap"
    STUCK_TASKS = "stuck_tasks"
    DEPENDENCY_DEADLOCK = "dependency_deadlock"
    RESOURCE_WASTE = "resource_waste"
    PRIORITY_INVERSION = "priority_inversion"
    BATCH_INEFFICIENCY = "batch_inefficiency"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""

    CRITICAL = "CRITICAL"  # Requires immediate action
    WARNING = "WARNING"  # Should be addressed soon
    INFO = "INFO"  # Good to know, low urgency


@dataclass
class OrchestrationAnomaly:
    """
    Detected anomaly in orchestration system.

    Includes severity, description, metrics, and actionable remediation.
    """

    # Identity
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    detected_at: datetime = field(default_factory=datetime.now)

    # Description
    title: str = ""
    description: str = ""

    # Metrics
    metric_value: float = 0.0  # Current metric value
    threshold_value: float = 0.0  # Threshold that triggered detection

    # Context
    affected_entities: List[str] = field(default_factory=list)  # Task IDs, project names, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Remediation
    remediation: str = ""  # Human-readable action to take
    auto_actionable: bool = False  # Can this be auto-remediated?
    auto_action_command: Optional[str] = None  # CLI command for auto-remediation

    # Tracking
    first_seen: Optional[datetime] = None  # When first detected (for recurring anomalies)
    occurrence_count: int = 1  # How many times seen

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "detected_at": self.detected_at.isoformat(),
            "title": self.title,
            "description": self.description,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "affected_entities": json.dumps(self.affected_entities),
            "metadata": json.dumps(self.metadata),
            "remediation": self.remediation,
            "auto_actionable": int(self.auto_actionable),
            "auto_action_command": self.auto_action_command,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "occurrence_count": self.occurrence_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationAnomaly":
        """Deserialize from dict."""
        # Convert datetime strings
        if data.get("detected_at"):
            data["detected_at"] = datetime.fromisoformat(data["detected_at"])
        if data.get("first_seen"):
            data["first_seen"] = datetime.fromisoformat(data["first_seen"])

        # Convert enums
        data["anomaly_type"] = AnomalyType(data["anomaly_type"])
        data["severity"] = AnomalySeverity(data["severity"])

        # Parse JSON fields
        if isinstance(data.get("affected_entities"), str):
            data["affected_entities"] = json.loads(data["affected_entities"])
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])

        # Convert boolean
        data["auto_actionable"] = bool(data.get("auto_actionable", 0))

        return cls(**data)


class AnomalyDetector(ABC):
    """
    Abstract base class for anomaly detectors.

    Each detector focuses on one specific type of orchestration issue.
    """

    @property
    @abstractmethod
    def anomaly_type(self) -> AnomalyType:
        """Type of anomaly this detector identifies."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the detector."""
        pass

    @abstractmethod
    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """
        Detect anomalies based on current orchestration state.

        Args:
            db: Database connection for querying tasks/workers
            context: Additional context (active_projects, goals, etc.)

        Returns:
            List of detected anomalies
        """
        pass

    def calculate_severity(
        self,
        metric_value: float,
        threshold_value: float,
        context: Dict[str, Any],
    ) -> AnomalySeverity:
        """
        Calculate severity based on metric value and context.

        Override in subclasses for custom severity logic.

        Args:
            metric_value: Current metric value
            threshold_value: Threshold that triggered detection
            context: Additional context for severity calculation

        Returns:
            Severity level
        """
        # Default logic: simple threshold-based
        if metric_value >= threshold_value * 2:
            return AnomalySeverity.CRITICAL
        elif metric_value >= threshold_value * 1.5:
            return AnomalySeverity.WARNING
        else:
            return AnomalySeverity.INFO


class ContextSwitchingDetector(AnomalyDetector):
    """
    Detects excessive context switching risk from too many active projects.

    Thresholds:
    - INFO: >10 active projects
    - WARNING: >15 active projects OR >70% of portfolio active
    - CRITICAL: >20 active projects OR >85% of portfolio active
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.CONTEXT_SWITCHING_RISK

    @property
    def name(self) -> str:
        return "Context Switching Risk Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect excessive active projects."""
        active_projects = context.get("active_projects", 0)
        total_projects = context.get("total_projects", 0)

        # Calculate percentage if total is known
        active_pct = (active_projects / total_projects * 100) if total_projects > 0 else 0

        # Check thresholds
        if active_projects <= 10 and active_pct < 70:
            return []

        # Determine severity
        if active_projects > 20 or active_pct > 85:
            severity = AnomalySeverity.CRITICAL
        elif active_projects > 15 or active_pct > 70:
            severity = AnomalySeverity.WARNING
        else:
            severity = AnomalySeverity.INFO

        # Build description
        if total_projects > 0:
            description = (
                f"{active_projects} active projects ({active_pct:.0f}% of {total_projects} total). "
                f"High context-switching overhead may reduce velocity."
            )
        else:
            description = (
                f"{active_projects} active projects. "
                f"High context-switching overhead may reduce velocity."
            )

        anomaly = OrchestrationAnomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type=self.anomaly_type,
            severity=severity,
            title=f"High context-switching risk: {active_projects} active projects",
            description=description,
            metric_value=float(active_projects),
            threshold_value=15.0,
            affected_entities=[],  # Would need project names from context
            metadata={
                "active_projects": active_projects,
                "total_projects": total_projects,
                "active_percentage": active_pct,
            },
            remediation="Review active projects and move non-critical work to backlog or pause status",
            auto_actionable=False,  # Requires human judgment
            auto_action_command=None,
        )

        return [anomaly]


class PlanningGapDetector(AnomalyDetector):
    """
    Detects planning gaps: active projects without active goals.

    Thresholds (time since last goal activated):
    - INFO: <24 hours gap
    - WARNING: 24-48 hours gap
    - CRITICAL: >48 hours gap
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.PLANNING_GAP

    @property
    def name(self) -> str:
        return "Planning Gap Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect planning gaps."""
        active_projects = context.get("active_projects", 0)
        goals_in_progress = context.get("goals_in_progress", 0)
        goals_pending = context.get("goals_pending", 0)
        last_goal_activated = context.get("last_goal_activated")  # datetime or None

        # Only flag if we have active projects but no goals in progress
        if active_projects == 0 or goals_in_progress > 0:
            return []

        # Must have pending goals to be actionable
        if goals_pending == 0:
            return []

        # Calculate gap duration
        if last_goal_activated:
            gap_hours = (datetime.now() - last_goal_activated).total_seconds() / 3600
        else:
            gap_hours = 999  # Unknown, treat as very long gap

        # Determine severity
        if gap_hours > 48:
            severity = AnomalySeverity.CRITICAL
        elif gap_hours > 24:
            severity = AnomalySeverity.WARNING
        else:
            severity = AnomalySeverity.INFO

        anomaly = OrchestrationAnomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type=self.anomaly_type,
            severity=severity,
            title=f"Planning gap: {active_projects} active projects, 0 active goals",
            description=(
                f"{active_projects} active projects but no goals in progress. "
                f"{goals_pending} pending goals waiting. Gap: {gap_hours:.1f} hours."
            ),
            metric_value=gap_hours,
            threshold_value=24.0,
            affected_entities=[],
            metadata={
                "active_projects": active_projects,
                "goals_in_progress": goals_in_progress,
                "goals_pending": goals_pending,
                "gap_hours": gap_hours,
            },
            remediation=f"Run `/briefing` to review {goals_pending} pending goals and activate next priority",
            auto_actionable=True,  # Could auto-suggest goal
            auto_action_command="/briefing",
        )

        return [anomaly]


class StuckTasksDetector(AnomalyDetector):
    """
    Detects tasks stuck in same phase for too long.

    Thresholds:
    - INFO: >48 hours in same phase
    - WARNING: >72 hours in same phase
    - CRITICAL: >72 hours AND priority A
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.STUCK_TASKS

    @property
    def name(self) -> str:
        return "Stuck Tasks Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect tasks stuck in same phase."""
        anomalies = []

        # Get all non-terminal tasks
        non_terminal_statuses = [
            TaskStatus.PENDING,
            TaskStatus.SCHEDULED,
            TaskStatus.RUNNING,
            TaskStatus.BLOCKED,
        ]

        all_tasks = []
        for status in non_terminal_statuses:
            all_tasks.extend(db.get_tasks_by_status(status, limit=1000))

        now = datetime.now()

        for task in all_tasks:
            # Check how long task has been in current phase
            # Use started_at for running tasks, created_at for pending
            if task.started_at:
                time_in_phase = now - task.started_at
            else:
                time_in_phase = now - task.created_at

            hours_in_phase = time_in_phase.total_seconds() / 3600

            # Check thresholds
            if hours_in_phase < 48:
                continue

            # Determine severity
            if hours_in_phase > 72 and task.priority == TaskPriority.A:
                severity = AnomalySeverity.CRITICAL
            elif hours_in_phase > 72:
                severity = AnomalySeverity.WARNING
            else:
                severity = AnomalySeverity.INFO

            anomaly = OrchestrationAnomaly(
                anomaly_id=str(uuid.uuid4()),
                anomaly_type=self.anomaly_type,
                severity=severity,
                title=f"Task stuck in {task.phase.value}: {task.title[:50]}",
                description=(
                    f"Task '{task.title}' stuck in {task.phase.value} phase for {hours_in_phase:.1f} hours. "
                    f"Priority: {task.priority.value}, Status: {task.status.value}"
                ),
                metric_value=hours_in_phase,
                threshold_value=48.0,
                affected_entities=[task.id],
                metadata={
                    "task_id": task.id,
                    "task_title": task.title,
                    "phase": task.phase.value,
                    "priority": task.priority.value,
                    "hours_in_phase": hours_in_phase,
                },
                remediation=(
                    f"Task stuck in {task.phase.value} - consider breaking down, escalating, or unblocking"
                ),
                auto_actionable=False,  # Requires investigation
                auto_action_command=None,
            )

            anomalies.append(anomaly)

        return anomalies


class DependencyDeadlockDetector(AnomalyDetector):
    """
    Detects circular dependency chains using DFS cycle detection.

    Thresholds:
    - INFO: Cycle length <3 tasks
    - WARNING: Cycle length 3-5 tasks
    - CRITICAL: Cycle length >5 OR contains priority A task
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.DEPENDENCY_DEADLOCK

    @property
    def name(self) -> str:
        return "Dependency Deadlock Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect circular dependencies."""
        anomalies = []

        # Get all blocked tasks
        blocked_tasks = db.get_blocked_tasks()

        # Build dependency graph
        task_map = {task.id: task for task in blocked_tasks}

        # DFS to find cycles
        visited: Set[str] = set()
        recursion_stack: Set[str] = set()
        path: List[str] = []

        def dfs_find_cycle(task_id: str) -> Optional[List[str]]:
            """Find cycle starting from task_id."""
            if task_id in recursion_stack:
                # Found cycle
                cycle_start = path.index(task_id)
                return path[cycle_start:] + [task_id]

            if task_id in visited:
                return None

            visited.add(task_id)
            recursion_stack.add(task_id)
            path.append(task_id)

            task = task_map.get(task_id)
            if task:
                for blocked_by_id in task.blocked_by:
                    if blocked_by_id in task_map:  # Only follow blocked tasks
                        cycle = dfs_find_cycle(blocked_by_id)
                        if cycle:
                            return cycle

            path.pop()
            recursion_stack.remove(task_id)
            return None

        # Find all cycles
        detected_cycles: Set[str] = set()  # Track cycle fingerprints to avoid duplicates

        for task_id in task_map.keys():
            if task_id not in visited:
                cycle = dfs_find_cycle(task_id)
                if cycle:
                    # Create fingerprint (sorted to avoid duplicate detection)
                    cycle_fingerprint = "-".join(sorted(cycle[:-1]))  # Remove duplicate end node

                    if cycle_fingerprint not in detected_cycles:
                        detected_cycles.add(cycle_fingerprint)

                        # Get task details
                        cycle_tasks = [task_map[tid] for tid in cycle[:-1] if tid in task_map]
                        cycle_length = len(cycle_tasks)

                        # Check if any task is priority A
                        has_priority_a = any(t.priority == TaskPriority.A for t in cycle_tasks)

                        # Determine severity
                        if cycle_length > 5 or has_priority_a:
                            severity = AnomalySeverity.CRITICAL
                        elif cycle_length >= 3:
                            severity = AnomalySeverity.WARNING
                        else:
                            severity = AnomalySeverity.INFO

                        # Build description
                        task_titles = [t.title[:30] for t in cycle_tasks]
                        cycle_description = " -> ".join(task_titles) + " -> (cycle)"

                        anomaly = OrchestrationAnomaly(
                            anomaly_id=str(uuid.uuid4()),
                            anomaly_type=self.anomaly_type,
                            severity=severity,
                            title=f"Circular dependency: {cycle_length} tasks in deadlock",
                            description=(
                                f"Circular dependency detected: {cycle_description}. "
                                f"None of these tasks can complete."
                            ),
                            metric_value=float(cycle_length),
                            threshold_value=3.0,
                            affected_entities=[t.id for t in cycle_tasks],
                            metadata={
                                "cycle_task_ids": [t.id for t in cycle_tasks],
                                "cycle_length": cycle_length,
                                "has_priority_a": has_priority_a,
                            },
                            remediation=(
                                f"Break circular dependency by removing one blocking relationship. "
                                f"Suggested: unblock {cycle_tasks[0].title[:30]}"
                            ),
                            auto_actionable=True,  # Could auto-suggest removal
                            auto_action_command=None,  # Would need task ID parameter
                        )

                        anomalies.append(anomaly)

        return anomalies


class ResourceWasteDetector(AnomalyDetector):
    """
    Detects idle workers with queued tasks ready to execute.

    Thresholds:
    - INFO: <30% workers idle
    - WARNING: 30-50% workers idle with ready tasks
    - CRITICAL: >50% workers idle with ready tasks
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.RESOURCE_WASTE

    @property
    def name(self) -> str:
        return "Resource Waste Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect idle workers with ready tasks."""
        # Get worker state
        available_workers = db.get_available_workers()
        total_workers = context.get("total_workers", len(available_workers))

        if total_workers == 0:
            return []

        # Count idle workers (available with no tasks)
        idle_workers = [w for w in available_workers if w.current_task_count == 0]
        idle_count = len(idle_workers)

        # Get ready tasks
        ready_tasks = db.get_ready_tasks(limit=100)
        ready_count = len(ready_tasks)

        # Only flag if we have idle workers AND ready tasks
        if idle_count == 0 or ready_count == 0:
            return []

        # Calculate idle percentage
        idle_pct = (idle_count / total_workers * 100) if total_workers > 0 else 0

        # Determine severity
        if idle_pct > 50 and ready_count > 0:
            severity = AnomalySeverity.CRITICAL
        elif idle_pct > 30 and ready_count > 0:
            severity = AnomalySeverity.WARNING
        else:
            severity = AnomalySeverity.INFO

        anomaly = OrchestrationAnomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type=self.anomaly_type,
            severity=severity,
            title=f"Resource waste: {idle_count} idle workers, {ready_count} ready tasks",
            description=(
                f"{idle_count} of {total_workers} workers ({idle_pct:.0f}%) are idle "
                f"while {ready_count} tasks are ready to execute."
            ),
            metric_value=idle_pct,
            threshold_value=30.0,
            affected_entities=[w.worker_id for w in idle_workers],
            metadata={
                "idle_workers": idle_count,
                "total_workers": total_workers,
                "idle_percentage": idle_pct,
                "ready_tasks": ready_count,
            },
            remediation=f"Trigger supervisor delegation to assign {min(idle_count, ready_count)} tasks",
            auto_actionable=True,  # Could auto-trigger delegation
            auto_action_command="/next",  # Simplified, real command would be more specific
        )

        return [anomaly]


class PriorityInversionDetector(AnomalyDetector):
    """
    Detects high-priority tasks blocked by low-priority tasks.

    Priority gap: A=1, B=2, C=3

    Thresholds:
    - INFO: Gap=1, blocked <12 hours (A blocked by B)
    - WARNING: Gap=1, blocked >12 hours OR Gap=2, blocked <24 hours
    - CRITICAL: Gap≥2, blocked >24 hours (A blocked by C)
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.PRIORITY_INVERSION

    @property
    def name(self) -> str:
        return "Priority Inversion Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect priority inversions."""
        anomalies = []

        # Get all blocked tasks
        blocked_tasks = db.get_blocked_tasks()

        # Build task map for quick lookup
        all_tasks_list = []
        for status in [
            TaskStatus.PENDING,
            TaskStatus.SCHEDULED,
            TaskStatus.RUNNING,
            TaskStatus.BLOCKED,
        ]:
            all_tasks_list.extend(db.get_tasks_by_status(status, limit=1000))

        task_map = {task.id: task for task in all_tasks_list}

        # Priority to numeric
        priority_map = {
            TaskPriority.A: 1,
            TaskPriority.B: 2,
            TaskPriority.C: 3,
        }

        now = datetime.now()

        for task in blocked_tasks:
            task_priority = priority_map.get(task.priority, 3)

            # Check each blocker
            for blocker_id in task.blocked_by:
                blocker = task_map.get(blocker_id)
                if not blocker:
                    continue

                blocker_priority = priority_map.get(blocker.priority, 3)

                # Check for inversion (lower priority number = higher priority)
                if task_priority < blocker_priority:
                    gap = blocker_priority - task_priority

                    # Calculate how long task has been blocked
                    blocked_hours = (now - task.created_at).total_seconds() / 3600

                    # Determine severity
                    if gap >= 2 and blocked_hours > 24:
                        severity = AnomalySeverity.CRITICAL
                    elif gap >= 2 or (gap == 1 and blocked_hours > 12):
                        severity = AnomalySeverity.WARNING
                    elif gap == 1 and blocked_hours < 12:
                        severity = AnomalySeverity.INFO
                    else:
                        continue  # Not significant

                    anomaly = OrchestrationAnomaly(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type=self.anomaly_type,
                        severity=severity,
                        title=(
                            f"Priority inversion: {task.priority.value} task blocked by "
                            f"{blocker.priority.value} task"
                        ),
                        description=(
                            f"Task '{task.title[:40]}' (priority {task.priority.value}) blocked by "
                            f"'{blocker.title[:40]}' (priority {blocker.priority.value}) for {blocked_hours:.1f}h"
                        ),
                        metric_value=float(gap),
                        threshold_value=1.0,
                        affected_entities=[task.id, blocker_id],
                        metadata={
                            "blocked_task_id": task.id,
                            "blocker_task_id": blocker_id,
                            "blocked_priority": task.priority.value,
                            "blocker_priority": blocker.priority.value,
                            "priority_gap": gap,
                            "blocked_hours": blocked_hours,
                        },
                        remediation=(
                            f"Elevate blocker priority from {blocker.priority.value} to "
                            f"{task.priority.value} or unblock dependency"
                        ),
                        auto_actionable=True,  # Could auto-elevate priority
                        auto_action_command=None,  # Would need task ID parameter
                    )

                    anomalies.append(anomaly)

        return anomalies


class BatchInefficiencyDetector(AnomalyDetector):
    """
    Detects underutilized batch queue or misrouted tasks.

    Thresholds:
    - INFO: >50% batch utilization
    - WARNING: 30-50% utilization OR 2+ realtime-should-be-batch tasks
    - CRITICAL: <30% utilization with 5+ wasted realtime tasks
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.BATCH_INEFFICIENCY

    @property
    def name(self) -> str:
        return "Batch Inefficiency Detector"

    def detect(
        self,
        db: OrchestrationDatabase,
        context: Dict[str, Any],
    ) -> List[OrchestrationAnomaly]:
        """Detect batch queue inefficiencies."""
        # Get batch queue stats from context
        batch_capacity = context.get("batch_capacity", 100)
        batch_queued = context.get("batch_queued", 0)
        batch_utilization_pct = (batch_queued / batch_capacity * 100) if batch_capacity > 0 else 0

        # Check for tasks that should be batch but are realtime
        # (This would require analyzing task characteristics)
        # For now, use context hint if provided
        misrouted_count = context.get("misrouted_realtime_tasks", 0)

        # Only flag if utilization is low OR we have misrouted tasks
        if batch_utilization_pct > 50 and misrouted_count == 0:
            return []

        # Determine severity
        if batch_utilization_pct < 30 and misrouted_count >= 5:
            severity = AnomalySeverity.CRITICAL
        elif batch_utilization_pct < 50 or misrouted_count >= 2:
            severity = AnomalySeverity.WARNING
        else:
            severity = AnomalySeverity.INFO

        # Build description
        issues = []
        if batch_utilization_pct < 50:
            issues.append(f"batch queue at {batch_utilization_pct:.0f}% utilization")
        if misrouted_count > 0:
            issues.append(f"{misrouted_count} realtime tasks should be batch")

        description = " and ".join(issues).capitalize()

        anomaly = OrchestrationAnomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type=self.anomaly_type,
            severity=severity,
            title=f"Batch inefficiency: {batch_utilization_pct:.0f}% utilization",
            description=(
                f"{description}. " f"Batch queue: {batch_queued}/{batch_capacity} tasks queued."
            ),
            metric_value=batch_utilization_pct,
            threshold_value=50.0,
            affected_entities=[],
            metadata={
                "batch_capacity": batch_capacity,
                "batch_queued": batch_queued,
                "batch_utilization_pct": batch_utilization_pct,
                "misrouted_count": misrouted_count,
            },
            remediation=(
                "Review task routing rules. Consider re-routing non-urgent analysis tasks to batch queue."
            ),
            auto_actionable=True,  # Could auto-reroute tasks
            auto_action_command="/batch-orchestrate",
        )

        return [anomaly]


class OrchestrationAnomalyManager:
    """
    Manages all anomaly detectors and coordinates detection.

    Features:
    - Registers all 7 detectors
    - Runs detection across all detectors
    - Deduplicates anomalies using fingerprinting
    - Tracks historical occurrences
    - Provides trending analysis
    """

    def __init__(self, db: OrchestrationDatabase, enable_alerts: bool = True):
        """Initialize manager with database connection."""
        self.db = db
        self.detectors: List[AnomalyDetector] = []
        self.enable_alerts = enable_alerts

        # Initialize alert manager (lazy load to avoid circular imports)
        self._alert_manager = None

        # Register all detectors
        self._register_detectors()

    def _register_detectors(self) -> None:
        """Register all anomaly detectors."""
        self.detectors = [
            ContextSwitchingDetector(),
            PlanningGapDetector(),
            StuckTasksDetector(),
            DependencyDeadlockDetector(),
            ResourceWasteDetector(),
            PriorityInversionDetector(),
            BatchInefficiencyDetector(),
        ]

    def detect_all(self, context: Dict[str, Any]) -> List[OrchestrationAnomaly]:
        """
        Run all detectors and return sorted anomalies.

        Args:
            context: Additional context for detection (active_projects, goals, etc.)

        Returns:
            List of anomalies sorted by severity (CRITICAL, WARNING, INFO)
        """
        all_anomalies = []

        # Run each detector
        for detector in self.detectors:
            try:
                anomalies = detector.detect(self.db, context)
                all_anomalies.extend(anomalies)
            except Exception as e:
                # Log error but continue with other detectors
                print(f"Error in {detector.name}: {e}")

        # Deduplicate and track occurrences
        deduplicated = self._deduplicate_and_track(all_anomalies)

        # Sort by severity (CRITICAL > WARNING > INFO)
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.WARNING: 1,
            AnomalySeverity.INFO: 2,
        }

        deduplicated.sort(key=lambda a: (severity_order[a.severity], a.detected_at), reverse=False)

        # Save to database
        self.db.save_anomalies(deduplicated)

        # Send alerts for CRITICAL anomalies (if enabled)
        if self.enable_alerts:
            self._send_alerts(deduplicated)

        return deduplicated

    def _deduplicate_and_track(
        self,
        anomalies: List[OrchestrationAnomaly],
    ) -> List[OrchestrationAnomaly]:
        """
        Deduplicate anomalies and track historical occurrences.

        Uses fingerprinting to identify recurring anomalies.
        """
        # Get recent anomalies from database (last 7 days)
        recent_anomalies = self.db.get_recent_anomalies(days=7)

        # Build fingerprint map for recent anomalies
        fingerprint_map: Dict[str, OrchestrationAnomaly] = {}
        for anomaly in recent_anomalies:
            fingerprint = self._get_fingerprint(anomaly)
            # Keep most recent occurrence
            if (
                fingerprint not in fingerprint_map
                or anomaly.detected_at > fingerprint_map[fingerprint].detected_at
            ):
                fingerprint_map[fingerprint] = anomaly

        # Process new anomalies
        deduplicated = []
        seen_fingerprints: Set[str] = set()

        for anomaly in anomalies:
            fingerprint = self._get_fingerprint(anomaly)

            # Skip if already processed in this batch
            if fingerprint in seen_fingerprints:
                continue

            seen_fingerprints.add(fingerprint)

            # Check if this is a recurring anomaly
            if fingerprint in fingerprint_map:
                existing = fingerprint_map[fingerprint]
                # Update occurrence count and first_seen
                anomaly.first_seen = existing.first_seen or existing.detected_at
                anomaly.occurrence_count = existing.occurrence_count + 1
            else:
                # New anomaly
                anomaly.first_seen = anomaly.detected_at
                anomaly.occurrence_count = 1

            deduplicated.append(anomaly)

        return deduplicated

    def _get_fingerprint(self, anomaly: OrchestrationAnomaly) -> str:
        """
        Generate fingerprint for anomaly deduplication.

        Fingerprint includes:
        - Anomaly type
        - Affected entities (sorted)
        - Key metadata (varies by type)
        """
        # Base fingerprint
        parts = [
            anomaly.anomaly_type.value,
        ]

        # Add sorted affected entities
        if anomaly.affected_entities:
            parts.append("-".join(sorted(anomaly.affected_entities[:5])))  # Limit to 5

        # Add type-specific metadata
        if anomaly.anomaly_type == AnomalyType.CONTEXT_SWITCHING_RISK:
            # Use threshold bucket (10-15, 15-20, >20)
            active = anomaly.metadata.get("active_projects", 0)
            bucket = "10-15" if active <= 15 else "15-20" if active <= 20 else ">20"
            parts.append(bucket)

        elif anomaly.anomaly_type == AnomalyType.STUCK_TASKS:
            # Include task ID since each stuck task is unique
            parts.append(anomaly.metadata.get("task_id", "unknown"))

        elif anomaly.anomaly_type == AnomalyType.DEPENDENCY_DEADLOCK:
            # Cycle fingerprint already in affected_entities
            pass

        elif anomaly.anomaly_type == AnomalyType.PRIORITY_INVERSION:
            # Include both task IDs
            parts.append(anomaly.metadata.get("blocked_task_id", ""))
            parts.append(anomaly.metadata.get("blocker_task_id", ""))

        # Generate hash
        fingerprint_str = "|".join(parts)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]

    def get_anomaly_trend(
        self,
        anomaly_type: AnomalyType,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get historical trend for a specific anomaly type.

        Args:
            anomaly_type: Type of anomaly to analyze
            days: Number of days to analyze

        Returns:
            Dictionary with trend data
        """
        return self.db.get_anomaly_trend(anomaly_type, days)

    def _send_alerts(self, anomalies: List[OrchestrationAnomaly]) -> None:
        """
        Send alerts for CRITICAL anomalies via alert manager.

        Args:
            anomalies: List of detected anomalies
        """
        # Lazy import to avoid circular dependencies
        if self._alert_manager is None:
            try:
                from notifications.alert_manager import AlertManager

                self._alert_manager = AlertManager()
            except ImportError:
                # Alert manager not available, skip notifications
                return

        # Send alerts for CRITICAL anomalies only
        for anomaly in anomalies:
            if anomaly.severity == AnomalySeverity.CRITICAL:
                try:
                    self._alert_manager.send_alert(
                        title=anomaly.title,
                        message=f"{anomaly.description}\n\nRemediation: {anomaly.remediation}",
                        severity="CRITICAL",
                        source="anomaly_detector",
                        metadata={
                            "anomaly_id": anomaly.anomaly_id,
                            "anomaly_type": anomaly.anomaly_type.value,
                            "affected_entities": anomaly.affected_entities,
                            "auto_actionable": anomaly.auto_actionable,
                            "auto_action_command": anomaly.auto_action_command,
                        },
                    )
                except Exception as e:
                    # Don't fail anomaly detection if alerts fail
                    print(f"Failed to send alert for anomaly {anomaly.anomaly_id}: {e}")
