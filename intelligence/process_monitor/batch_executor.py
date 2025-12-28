"""
Batch Task Executor - Executes scheduled batch tasks.

Handles:
- Task execution with timeout
- Output capture (stdout/stderr)
- Error handling and retries
- Capacity checking before execution
- Concurrent task execution
"""

import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
import time
import logging
import sqlite3

from .batch_queue import BatchTaskQueue, BatchTask, TaskState


class BatchExecutor:
    """
    Executes batch tasks with capacity awareness and error handling.
    """

    def __init__(
        self,
        queue: BatchTaskQueue,
        process_monitor: Optional[Any] = None,
        max_concurrent: int = 3,
        timeout_seconds: int = 3600
    ):
        """
        Initialize batch executor.

        Args:
            queue: BatchTaskQueue instance
            process_monitor: ProcessMonitor for capacity checking
            max_concurrent: Maximum concurrent task executions
            timeout_seconds: Default timeout for task execution
        """
        self.queue = queue
        self.process_monitor = process_monitor
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds

        self._running_tasks: Dict[str, threading.Thread] = {}
        self._shutdown_event = threading.Event()

        # Setup logging
        self.logger = logging.getLogger("BatchExecutor")

    @property
    def _shutdown(self) -> bool:
        """Backward compatibility property for shutdown state."""
        return self._shutdown_event.is_set()

    def execute_task(
        self,
        task: BatchTask,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Execute a single task.

        Args:
            task: BatchTask to execute
            cwd: Working directory for execution
            env: Environment variables
            timeout: Execution timeout in seconds

        Returns:
            True if successful, False otherwise
        """
        if timeout is None:
            timeout = self.timeout_seconds

        # Update state to running
        started_at = datetime.now()
        self.queue.update_task_state(
            task.task_id,
            TaskState.RUNNING,
            started_at=started_at
        )

        try:
            # Execute command
            result = subprocess.run(
                task.command,
                shell=True,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            completed_at = datetime.now()

            # Update task with results
            if result.returncode == 0:
                self.queue.update_task_state(
                    task.task_id,
                    TaskState.COMPLETED,
                    started_at=started_at,
                    completed_at=completed_at,
                    exit_code=result.returncode,
                    stdout=result.stdout[:10000],  # Limit to 10KB
                    stderr=result.stderr[:10000]
                )
                self.logger.info(f"Task {task.task_id} completed successfully")
                return True
            else:
                # Non-zero exit code = failure
                self.queue.update_task_state(
                    task.task_id,
                    TaskState.FAILED,
                    started_at=started_at,
                    completed_at=completed_at,
                    exit_code=result.returncode,
                    stdout=result.stdout[:10000],
                    stderr=result.stderr[:10000],
                    error_message=f"Command failed with exit code {result.returncode}"
                )
                self.logger.error(f"Task {task.task_id} failed with exit code {result.returncode}")

                # Attempt retry if within limits
                # Note: retry_task() will increment retry_count, so check if current + 1 <= max
                if task.retry_count + 1 <= task.max_retries:
                    self.logger.info(f"Retrying task {task.task_id} (retry {task.retry_count + 1}/{task.max_retries})")
                    self.queue.retry_task(task.task_id)
                else:
                    self.logger.error(f"Task {task.task_id} failed permanently after {task.max_retries} retries")

                return False

        except subprocess.TimeoutExpired:
            completed_at = datetime.now()
            self.queue.update_task_state(
                task.task_id,
                TaskState.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error_message=f"Task timed out after {timeout} seconds"
            )
            self.logger.error(f"Task {task.task_id} timed out")
            return False

        except Exception as e:
            completed_at = datetime.now()
            self.queue.update_task_state(
                task.task_id,
                TaskState.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error_message=str(e)
            )
            self.logger.error(f"Task {task.task_id} failed with exception: {e}")
            return False

    def can_execute_now(self, task: BatchTask) -> tuple[bool, str]:
        """
        Check if task can execute based on capacity.

        Args:
            task: Task to check

        Returns:
            (can_execute, reason) tuple
        """
        # Check concurrent task limit
        if len(self._running_tasks) >= self.max_concurrent:
            return False, f"Max concurrent tasks ({self.max_concurrent}) reached"

        # Check capacity if process monitor available
        if self.process_monitor and hasattr(self.process_monitor, 'scheduler'):
            from .scheduler import TaskType, SchedulingPriority

            try:
                task_type = TaskType(task.task_type) if task.task_type in [t.value for t in TaskType] else TaskType.GENERAL
                priority = SchedulingPriority(task.priority) if task.priority in [p.value for p in SchedulingPriority] else SchedulingPriority.NORMAL

                can_run, reason = self.process_monitor.scheduler.can_run_now(task_type, priority)
                return can_run, reason
            except Exception as e:
                self.logger.warning(f"Capacity check failed: {e}, allowing execution")
                return True, "Capacity check unavailable, allowing execution"

        # No process monitor, allow execution
        return True, "No capacity checking configured"

    def execute_task_async(
        self,
        task: BatchTask,
        on_complete: Optional[Callable[[BatchTask, bool], None]] = None
    ):
        """
        Execute task asynchronously in a separate thread.

        Args:
            task: Task to execute
            on_complete: Callback function(task, success) called when complete
        """
        def run():
            try:
                success = self.execute_task(task)
                if on_complete:
                    on_complete(task, success)
            finally:
                # Remove from running tasks
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]

        thread = threading.Thread(target=run, daemon=True)
        self._running_tasks[task.task_id] = thread
        thread.start()

    def process_scheduled_tasks(self) -> Dict[str, Any]:
        """
        Process all scheduled tasks that are ready to run.

        Returns:
            Dictionary with execution summary
        """
        tasks_ready = self.queue.get_scheduled_tasks()

        results = {
            'total_ready': len(tasks_ready),
            'executed': 0,
            'deferred': 0,
            'failed_capacity_check': 0,
            'tasks': []
        }

        for task in tasks_ready:
            # Check if we can execute
            can_execute, reason = self.can_execute_now(task)

            if can_execute:
                # Execute asynchronously
                self.execute_task_async(task)
                results['executed'] += 1
                results['tasks'].append({
                    'task_id': task.task_id,
                    'description': task.description,
                    'status': 'executing',
                    'reason': reason
                })
            else:
                # Defer task - reschedule for later
                results['deferred'] += 1
                results['failed_capacity_check'] += 1
                results['tasks'].append({
                    'task_id': task.task_id,
                    'description': task.description,
                    'status': 'deferred',
                    'reason': reason
                })
                self.logger.info(f"Deferring task {task.task_id}: {reason}")

        return results

    def schedule_pending_tasks(self) -> Dict[str, Any]:
        """
        Schedule pending tasks using capacity-aware scheduling.

        Returns:
            Dictionary with scheduling summary
        """
        if not self.process_monitor or not hasattr(self.process_monitor, 'scheduler'):
            return {
                'error': 'ProcessMonitor scheduler not available',
                'scheduled': 0
            }

        pending_tasks = self.queue.get_pending_tasks()
        scheduler = self.process_monitor.scheduler

        results = {
            'total_pending': len(pending_tasks),
            'scheduled': 0,
            'tasks': []
        }

        for task in pending_tasks:
            # Use capacity scheduler to determine optimal time
            from .scheduler import TaskType, SchedulingPriority

            try:
                task_type = TaskType(task.task_type) if task.task_type in [t.value for t in TaskType] else TaskType.GENERAL
                priority = SchedulingPriority(task.priority) if task.priority in [p.value for p in SchedulingPriority] else SchedulingPriority.NORMAL

                scheduled = scheduler.schedule_task(
                    task_id=task.task_id,
                    task_type=task_type,
                    priority=priority,
                    estimated_duration_minutes=task.estimated_duration_minutes
                )

                # Update task with scheduled time
                conn = sqlite3.connect(self.queue.db_path)
                conn.execute("""
                    UPDATE batch_tasks
                    SET scheduled_time = ?, state = 'scheduled'
                    WHERE task_id = ?
                """, (scheduled.recommended_start_time.isoformat(), task.task_id))
                conn.commit()
                conn.close()

                results['scheduled'] += 1
                results['tasks'].append({
                    'task_id': task.task_id,
                    'description': task.description,
                    'scheduled_time': scheduled.recommended_start_time.isoformat(),
                    'reason': scheduled.scheduling_reason
                })

            except Exception as e:
                self.logger.error(f"Failed to schedule task {task.task_id}: {e}")

        return results

    def run_scheduler_daemon(self, interval_seconds: int = 60):
        """
        Run scheduler daemon that processes tasks periodically.

        Args:
            interval_seconds: How often to check for tasks (default: 60s)
        """
        self.logger.info(f"Starting scheduler daemon (interval: {interval_seconds}s)")

        while not self._shutdown_event.is_set():
            try:
                # Schedule any pending tasks
                schedule_results = self.schedule_pending_tasks()
                if schedule_results.get('scheduled', 0) > 0:
                    self.logger.info(f"Scheduled {schedule_results['scheduled']} tasks")

                # Process scheduled tasks that are ready
                process_results = self.process_scheduled_tasks()
                if process_results['executed'] > 0:
                    self.logger.info(f"Executed {process_results['executed']} tasks")

                if process_results['deferred'] > 0:
                    self.logger.info(f"Deferred {process_results['deferred']} tasks due to capacity")

            except Exception as e:
                self.logger.error(f"Scheduler daemon error: {e}")

            # Wait until next check (interruptible by shutdown event)
            self._shutdown_event.wait(timeout=interval_seconds)

        self.logger.info("Scheduler daemon stopped")

    def shutdown(self):
        """Shutdown the executor and wait for running tasks."""
        self.logger.info("Shutting down executor...")
        self._shutdown_event.set()

        # Wait for running tasks to complete
        for task_id, thread in self._running_tasks.items():
            self.logger.info(f"Waiting for task {task_id} to complete...")
            thread.join(timeout=30)

        self.logger.info("Executor shutdown complete")

    def get_status(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            'running_tasks': len(self._running_tasks),
            'max_concurrent': self.max_concurrent,
            'shutdown': self._shutdown_event.is_set(),
            'running_task_ids': list(self._running_tasks.keys()),
        }
