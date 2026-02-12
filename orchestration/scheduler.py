"""
Task scheduler for routing between batch and realtime execution.

Routes tasks based on priority level and deadline constraints:
- Priority A (critical): Always realtime
- Priority B (important): Batch if deadline > 4 hours
- Priority C (background): Always batch
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .task import Task, TaskPriority, TaskStatus
from .task_queue import TaskQueue


class SchedulingDecision:
    """Result of scheduling decision"""

    def __init__(
        self,
        task: Task,
        execution_mode: str,
        reason: str,
        estimated_completion: Optional[datetime] = None,
    ):
        self.task = task
        self.execution_mode = execution_mode  # "realtime" or "batch"
        self.reason = reason
        self.estimated_completion = estimated_completion

    def __repr__(self) -> str:
        return f"<SchedulingDecision {self.task.id} -> {self.execution_mode}: {self.reason}>"


class TaskScheduler:
    """
    Routes tasks between batch and realtime execution.

    Routing Rules:
    1. Priority A (critical): Always realtime, immediate execution
    2. Priority B (important):
       - Realtime if deadline < 4 hours
       - Batch if deadline >= 4 hours or no deadline
    3. Priority C (background): Always batch, overnight execution

    Additionally considers:
    - Urgent flag (deadline < 2 hours): Forces realtime
    - Token budget: May defer to batch if realtime budget low
    - Batch capacity: May route to realtime if batch queue full
    """

    # Scheduling thresholds
    URGENT_THRESHOLD_HOURS = 2.0  # Force realtime if deadline within 2h
    BATCH_ELIGIBLE_HOURS = 4.0  # B tasks batch-eligible if deadline > 4h
    BATCH_PROCESSING_TIME_HOURS = 12.0  # Assume 12h for batch completion

    def __init__(self, queue: Optional[TaskQueue] = None):
        """
        Initialize scheduler.

        Args:
            queue: TaskQueue instance. Creates new one if not provided.
        """
        self.queue = queue or TaskQueue()

    def schedule(self, task: Task) -> SchedulingDecision:
        """
        Determine execution mode for task.

        Args:
            task: Task to schedule

        Returns:
            SchedulingDecision with routing choice
        """
        # Rule 1: Urgent tasks always go realtime
        if task.is_urgent:
            decision = SchedulingDecision(
                task=task,
                execution_mode="realtime",
                reason=f"Urgent deadline ({task.hours_until_deadline:.1f}h remaining)",
                estimated_completion=datetime.now() + timedelta(minutes=30),
            )
            return decision

        # Rule 2: Priority A always realtime
        if task.priority == TaskPriority.A:
            decision = SchedulingDecision(
                task=task,
                execution_mode="realtime",
                reason="Priority A (critical) requires immediate execution",
                estimated_completion=datetime.now() + timedelta(minutes=30),
            )
            return decision

        # Rule 3: Priority C always batch
        if task.priority == TaskPriority.C:
            decision = SchedulingDecision(
                task=task,
                execution_mode="batch",
                reason="Priority C (background) routed to batch for cost savings",
                estimated_completion=datetime.now()
                + timedelta(hours=self.BATCH_PROCESSING_TIME_HOURS),
            )
            return decision

        # Rule 4: Priority B - decide based on deadline
        if task.priority == TaskPriority.B:
            hours_until_deadline = task.hours_until_deadline

            # No deadline: default to batch
            if hours_until_deadline is None:
                decision = SchedulingDecision(
                    task=task,
                    execution_mode="batch",
                    reason="Priority B with no deadline - batch for cost savings",
                    estimated_completion=datetime.now()
                    + timedelta(hours=self.BATCH_PROCESSING_TIME_HOURS),
                )
                return decision

            # Deadline too tight for batch: go realtime
            if hours_until_deadline < self.BATCH_ELIGIBLE_HOURS:
                decision = SchedulingDecision(
                    task=task,
                    execution_mode="realtime",
                    reason=f"Priority B with tight deadline ({hours_until_deadline:.1f}h)",
                    estimated_completion=datetime.now() + timedelta(minutes=30),
                )
                return decision

            # Sufficient time: route to batch
            decision = SchedulingDecision(
                task=task,
                execution_mode="batch",
                reason=f"Priority B with sufficient deadline ({hours_until_deadline:.1f}h) - batch eligible",
                estimated_completion=datetime.now()
                + timedelta(hours=self.BATCH_PROCESSING_TIME_HOURS),
            )
            return decision

        # Fallback: realtime
        decision = SchedulingDecision(
            task=task,
            execution_mode="realtime",
            reason="Fallback to realtime (unknown priority)",
            estimated_completion=datetime.now() + timedelta(minutes=30),
        )
        return decision

    def enqueue_and_schedule(self, task: Task) -> SchedulingDecision:
        """
        Schedule task and add to queue.

        Args:
            task: Task to schedule

        Returns:
            SchedulingDecision
        """
        # Make scheduling decision
        decision = self.schedule(task)

        # Update task with execution mode but keep status as PENDING
        # (will be marked SCHEDULED when actually assigned to worker/batch)
        task.execution_mode = decision.execution_mode

        # Add to queue
        self.queue.enqueue(task)

        return decision

    def get_next_realtime_task(self) -> Optional[Task]:
        """
        Get next task for realtime execution.

        Returns:
            Task if available, None if no realtime tasks ready
        """
        # Get all ready tasks
        ready_tasks = self.queue.get_ready_tasks()

        # Filter for realtime-scheduled tasks
        realtime_tasks = [t for t in ready_tasks if t.execution_mode == "realtime"]

        if not realtime_tasks:
            return None

        # Return highest priority
        return realtime_tasks[0]

    def get_next_batch_tasks(self, limit: int = 10) -> List[Task]:
        """
        Get batch-eligible tasks for submission.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of tasks ready for batch submission
        """
        # Get all ready tasks
        ready_tasks = self.queue.get_ready_tasks()

        # Filter for batch-scheduled tasks
        batch_tasks = [t for t in ready_tasks if t.execution_mode == "batch"]

        return batch_tasks[:limit]

    def rebalance_queue(self) -> Dict[str, Any]:
        """
        Re-evaluate scheduling decisions for pending tasks.

        Useful when:
        - Deadlines approaching (may need to promote to realtime)
        - Batch capacity changes
        - Token budget changes

        Returns:
            Dict with rebalancing stats
        """
        pending_tasks = self.queue.get_all(status=TaskStatus.PENDING)

        promoted_to_realtime = 0
        demoted_to_batch = 0

        for task in pending_tasks:
            old_mode = task.execution_mode

            # Re-evaluate
            decision = self.schedule(task)
            new_mode = decision.execution_mode

            if old_mode != new_mode:
                task.mark_scheduled(new_mode)
                self.queue.update(task)

                if new_mode == "realtime":
                    promoted_to_realtime += 1
                else:
                    demoted_to_batch += 1

        return {
            "total_pending": len(pending_tasks),
            "promoted_to_realtime": promoted_to_realtime,
            "demoted_to_batch": demoted_to_batch,
            "unchanged": len(pending_tasks) - promoted_to_realtime - demoted_to_batch,
        }

    def get_scheduling_stats(self) -> Dict[str, Any]:
        """
        Get queue stats broken down by execution mode.

        Returns:
            Dict with scheduling statistics
        """
        # Get all pending tasks (scheduled but not yet running)
        all_tasks = self.queue.get_all(status=TaskStatus.PENDING)

        realtime_count = len([t for t in all_tasks if t.execution_mode == "realtime"])
        batch_count = len([t for t in all_tasks if t.execution_mode == "batch"])
        unscheduled = len([t for t in all_tasks if t.execution_mode is None])

        # Breakdown by priority
        by_priority = {}
        for priority in TaskPriority:
            priority_tasks = [t for t in all_tasks if t.priority == priority]
            by_priority[priority.value] = {
                "total": len(priority_tasks),
                "realtime": len([t for t in priority_tasks if t.execution_mode == "realtime"]),
                "batch": len([t for t in priority_tasks if t.execution_mode == "batch"]),
            }

        # Urgent tasks
        urgent_tasks = [t for t in all_tasks if t.is_urgent]

        return {
            "total_pending": len(all_tasks),
            "realtime": realtime_count,
            "batch": batch_count,
            "unscheduled": unscheduled,
            "by_priority": by_priority,
            "urgent": len(urgent_tasks),
        }

    def estimate_batch_cost_savings(self) -> Dict[str, Any]:
        """
        Estimate cost savings from batch routing.

        Assumes 50% cost reduction for batch vs realtime.

        Returns:
            Dict with cost estimates
        """
        # Get all pending tasks
        all_tasks = self.queue.get_all(status=TaskStatus.PENDING)

        batch_tasks = [t for t in all_tasks if t.execution_mode == "batch"]
        total_batch_tokens = sum(t.total_estimated_tokens for t in batch_tasks)

        # Rough cost estimate (Opus pricing)
        # $15/M input tokens, $75/M output tokens
        # Average: ~$20/M tokens for mixed workload
        realtime_cost_per_million = 20.0
        batch_cost_per_million = 10.0  # 50% discount

        realtime_cost = (total_batch_tokens / 1_000_000) * realtime_cost_per_million
        batch_cost = (total_batch_tokens / 1_000_000) * batch_cost_per_million
        savings = realtime_cost - batch_cost

        return {
            "batch_tasks": len(batch_tasks),
            "total_tokens": total_batch_tokens,
            "realtime_cost_usd": round(realtime_cost, 2),
            "batch_cost_usd": round(batch_cost, 2),
            "savings_usd": round(savings, 2),
            "savings_pct": 50.0,
        }
