"""
Batch Task Executor - Executes scheduled batch tasks.

Handles:
- Task execution with timeout
- Output capture (stdout/stderr)
- Error handling and retries
- Capacity checking before execution
- Concurrent task execution
- AI task dispatch via Anthropic Batch API (not subprocess)
"""

import logging
import os
import sqlite3
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .batch_queue import BatchTask, BatchTaskQueue, TaskState

# Task types that should be dispatched to the Anthropic API, not subprocess.
# These tasks have prompts in the 'command' field, not shell commands.
AI_TASK_TYPES = frozenset(
    {
        "research",
        "analysis",
        "planning",
        "investigation",
        "review",
        "security",
        "documentation",
        "pattern",
        "recommendation",
        "bandwidth_experiment",
    }
)


def _load_api_key() -> Optional[str]:
    """
    Load Anthropic API key from environment or secrets file.

    Checks in order:
    1. ANTHROPIC_API_KEY environment variable
    2. ~/.cortex/secrets/anthropic_batch_key file (used by .envrc)

    Returns:
        API key string or None if not found.
    """
    # 1. Environment variable (set by .envrc or launchd plist)
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key

    # 2. Secrets file (same source as .envrc uses)
    secrets_file = Path.home() / ".cortex" / "secrets" / "anthropic_batch_key"
    if secrets_file.exists():
        try:
            key = secrets_file.read_text().strip()
            if key:
                return key
        except (IOError, OSError):
            pass

    return None


def _is_shell_command(command: str) -> bool:
    """
    Heuristic to detect whether a command string is a shell command vs an AI prompt.

    Shell commands typically start with a known executable or path.
    AI prompts start with natural language words like "Plan", "Research", etc.

    Args:
        command: The command/prompt string to classify.

    Returns:
        True if this looks like a shell command, False if it looks like a prompt.
    """
    if not command or not command.strip():
        return False

    stripped = command.strip()

    # Shell commands start with known patterns
    shell_indicators = [
        "cd ",
        "python",
        "pytest",
        "pip ",
        "npm ",
        "node ",
        "echo ",
        "cat ",
        "grep ",
        "find ",
        "ls ",
        "mkdir ",
        "rm ",
        "cp ",
        "mv ",
        "chmod ",
        "git ",
        "docker ",
        "make ",
        "bash ",
        "sh ",
        "zsh ",
        "/",  # absolute path
        "./",  # relative path
        "export ",
        "source ",
        "curl ",
        "wget ",
    ]

    for indicator in shell_indicators:
        if stripped.startswith(indicator):
            return True

    # If the first word looks like a file path, it's a command.
    # Skip bracket-prefixed strings like "[TODO/FIXME analysis: ...]"
    # which are section headers in AI prompts, not paths.
    first_word = stripped.split()[0] if stripped.split() else ""
    if not first_word.startswith("["):
        if "/" in first_word or first_word.endswith(".py") or first_word.endswith(".sh"):
            return True

    return False


class BatchExecutor:
    """
    Executes batch tasks with capacity awareness and error handling.

    Routes tasks to the correct backend:
    - Shell tasks (task_type in known shell types, or command looks like a shell command)
      are executed via subprocess.run().
    - AI tasks (task_type in AI_TASK_TYPES, or command looks like a prompt)
      are dispatched to the Anthropic Messages API.
    """

    def __init__(
        self,
        queue: BatchTaskQueue,
        process_monitor: Optional[Any] = None,
        max_concurrent: int = 3,
        timeout_seconds: int = 3600,
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

    def _is_ai_task(self, task: BatchTask) -> bool:
        """
        Determine if a task should be dispatched to the Anthropic API
        rather than executed as a shell command.

        Uses two signals:
        1. task_type is in AI_TASK_TYPES (explicit routing)
        2. The command field does not look like a shell command (fallback heuristic)

        Args:
            task: The batch task to classify.

        Returns:
            True if the task should go to the Anthropic API.
        """
        # Explicit task type check
        if task.task_type in AI_TASK_TYPES:
            return True

        # Heuristic: if the command doesn't look like a shell command, it's a prompt
        if not _is_shell_command(task.command):
            self.logger.warning(
                f"Task {task.task_id} (type={task.task_type}) has non-shell command, "
                f"routing to AI API. First 60 chars: {task.command[:60]!r}"
            )
            return True

        return False

    def _execute_ai_task(self, task: BatchTask) -> bool:
        """
        Execute an AI task by sending the prompt to the Anthropic Messages API.

        Uses the synchronous (non-batch) Messages API for individual task execution.
        The task's 'command' field contains the prompt text, and 'description' provides
        context for logging.

        Args:
            task: BatchTask with prompt text in the command field.

        Returns:
            True if the API call succeeded, False otherwise.
        """
        started_at = datetime.now()
        self.queue.update_task_state(task.task_id, TaskState.RUNNING, started_at=started_at)

        try:
            # Load API key
            api_key = _load_api_key()
            if not api_key:
                error_msg = (
                    "ANTHROPIC_API_KEY not available. Set the environment variable or "
                    "create ~/.cortex/secrets/anthropic_batch_key"
                )
                self.logger.error(f"Task {task.task_id}: {error_msg}")
                self.queue.update_task_state(
                    task.task_id,
                    TaskState.FAILED,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    error_message=error_msg,
                )
                return False

            # Import anthropic SDK
            try:
                import anthropic
            except ImportError:
                error_msg = "anthropic SDK not installed. Install with: pip install anthropic"
                self.logger.error(f"Task {task.task_id}: {error_msg}")
                self.queue.update_task_state(
                    task.task_id,
                    TaskState.FAILED,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    error_message=error_msg,
                )
                return False

            # Create client and send request
            client = anthropic.Anthropic(api_key=api_key)
            prompt = task.command  # The "command" field contains the prompt for AI tasks

            self.logger.info(
                f"Task {task.task_id}: Sending to Anthropic API "
                f"(type={task.task_type}, prompt_len={len(prompt)})"
            )

            # Use model from batch config or default
            model = os.getenv("CORTEX_BATCH_MODEL", "claude-sonnet-4-20250514")

            message = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract response text
            response_text = ""
            for block in message.content:
                if hasattr(block, "text"):
                    response_text += block.text

            completed_at = datetime.now()

            # Store result in stdout field (reusing existing schema)
            self.queue.update_task_state(
                task.task_id,
                TaskState.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                exit_code=0,
                stdout=response_text[:10000],  # Limit to 10KB
                stderr="",
            )

            self.logger.info(
                f"Task {task.task_id} completed via API "
                f"(response_len={len(response_text)}, "
                f"input_tokens={message.usage.input_tokens}, "
                f"output_tokens={message.usage.output_tokens})"
            )

            # Trigger dependent tasks (V2a batch orchestration)
            self.queue.trigger_dependent_tasks(task.task_id)

            return True

        except Exception as e:
            completed_at = datetime.now()
            error_msg = f"Anthropic API error: {e}"
            self.queue.update_task_state(
                task.task_id,
                TaskState.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error_message=error_msg,
            )
            self.logger.error(f"Task {task.task_id} failed with API exception: {e}")

            # Attempt retry if within limits
            if task.retry_count + 1 <= task.max_retries:
                self.logger.info(
                    f"Retrying task {task.task_id} (retry {task.retry_count + 1}/{task.max_retries})"
                )
                self.queue.retry_task(task.task_id)

            return False

    def execute_task(
        self,
        task: BatchTask,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """
        Execute a single task. Routes to the correct backend:
        - AI tasks -> Anthropic Messages API
        - Shell tasks -> subprocess.run()

        Args:
            task: BatchTask to execute
            cwd: Working directory for execution (shell tasks only)
            env: Environment variables (shell tasks only)
            timeout: Execution timeout in seconds

        Returns:
            True if successful, False otherwise
        """
        # SECURITY: Input validation
        # Validate command is not empty
        if not task.command or (isinstance(task.command, str) and not task.command.strip()):
            self.logger.error(f"Task {task.task_id}: Empty command")
            self.queue.update_task_state(
                task.task_id, TaskState.FAILED, error_message="Empty command not allowed"
            )
            return False

        # Route AI tasks to the Anthropic API instead of subprocess
        if self._is_ai_task(task):
            return self._execute_ai_task(task)

        # === Shell task execution below ===

        # Validate timeout is reasonable
        if timeout is None:
            timeout = self.timeout_seconds
        if timeout < 0 or timeout > 86400:  # Max 24 hours
            self.logger.error(f"Task {task.task_id}: Invalid timeout {timeout}s (must be 0-86400)")
            self.queue.update_task_state(
                task.task_id, TaskState.FAILED, error_message=f"Invalid timeout {timeout}s"
            )
            return False

        # Validate working directory if provided
        if cwd is not None:
            cwd_path = Path(cwd).resolve()
            if not cwd_path.exists():
                self.logger.error(f"Task {task.task_id}: Working directory does not exist: {cwd}")
                self.queue.update_task_state(
                    task.task_id,
                    TaskState.FAILED,
                    error_message=f"Working directory not found: {cwd}",
                )
                return False
            if not cwd_path.is_dir():
                self.logger.error(
                    f"Task {task.task_id}: Working directory is not a directory: {cwd}"
                )
                self.queue.update_task_state(
                    task.task_id,
                    TaskState.FAILED,
                    error_message=f"Working directory is not a directory: {cwd}",
                )
                return False

        # Sanitize environment variables if provided
        if env is not None:
            # Validate env var names (alphanumeric + underscore only)
            import re

            for key in env.keys():
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                    self.logger.error(
                        f"Task {task.task_id}: Invalid environment variable name: {key}"
                    )
                    self.queue.update_task_state(
                        task.task_id,
                        TaskState.FAILED,
                        error_message=f"Invalid environment variable name: {key}",
                    )
                    return False

        # Update state to running
        started_at = datetime.now()
        self.queue.update_task_state(task.task_id, TaskState.RUNNING, started_at=started_at)

        try:
            # Execute command - SECURITY: Use shell=False to prevent command injection
            # Parse command string into list for safe execution
            import shlex

            command_list = (
                shlex.split(task.command) if isinstance(task.command, str) else task.command
            )

            result = subprocess.run(
                command_list,
                shell=False,  # CRITICAL: Never use shell=True with user input
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
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
                    stderr=result.stderr[:10000],
                )
                self.logger.info(f"Task {task.task_id} completed successfully")

                # Trigger dependent tasks (V2a batch orchestration)
                self.queue.trigger_dependent_tasks(task.task_id)

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
                    error_message=f"Command failed with exit code {result.returncode}",
                )
                self.logger.error(f"Task {task.task_id} failed with exit code {result.returncode}")

                # Attempt retry if within limits
                # Note: retry_task() will increment retry_count, so check if current + 1 <= max
                if task.retry_count + 1 <= task.max_retries:
                    self.logger.info(
                        f"Retrying task {task.task_id} (retry {task.retry_count + 1}/{task.max_retries})"
                    )
                    self.queue.retry_task(task.task_id)
                else:
                    self.logger.error(
                        f"Task {task.task_id} failed permanently after {task.max_retries} retries"
                    )

                return False

        except subprocess.TimeoutExpired:
            completed_at = datetime.now()
            self.queue.update_task_state(
                task.task_id,
                TaskState.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error_message=f"Task timed out after {timeout} seconds",
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
                error_message=str(e),
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
        if self.process_monitor and hasattr(self.process_monitor, "scheduler"):
            from .scheduler import SchedulingPriority, TaskType

            try:
                task_type = (
                    TaskType(task.task_type)
                    if task.task_type in [t.value for t in TaskType]
                    else TaskType.GENERAL
                )
                priority = (
                    SchedulingPriority(task.priority)
                    if task.priority in [p.value for p in SchedulingPriority]
                    else SchedulingPriority.NORMAL
                )

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
        on_complete: Optional[Callable[[BatchTask, bool], None]] = None,
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
        Now dependency-aware: only executes tasks whose dependencies are met.

        Returns:
            Dictionary with execution summary
        """
        # Get tasks with dependencies met (V2a batch orchestration)
        tasks_ready = self.queue.get_next_available_tasks()
        # Also check scheduled tasks with time-based scheduling
        scheduled_tasks = self.queue.get_scheduled_tasks()

        # Combine both lists, removing duplicates
        all_ready_tasks = {t.task_id: t for t in tasks_ready + scheduled_tasks}.values()

        results = {
            "total_ready": len(all_ready_tasks),
            "executed": 0,
            "deferred": 0,
            "failed_capacity_check": 0,
            "tasks": [],
        }

        for task in all_ready_tasks:
            # Check if we can execute
            can_execute, reason = self.can_execute_now(task)

            if can_execute:
                # Execute asynchronously
                self.execute_task_async(task)
                results["executed"] += 1
                results["tasks"].append(
                    {
                        "task_id": task.task_id,
                        "description": task.description,
                        "status": "executing",
                        "reason": reason,
                    }
                )
            else:
                # Defer task - reschedule for later
                results["deferred"] += 1
                results["failed_capacity_check"] += 1
                results["tasks"].append(
                    {
                        "task_id": task.task_id,
                        "description": task.description,
                        "status": "deferred",
                        "reason": reason,
                    }
                )
                self.logger.info(f"Deferring task {task.task_id}: {reason}")

        return results

    def schedule_pending_tasks(self, max_per_cycle: int = 5) -> Dict[str, Any]:
        """
        Schedule pending tasks using capacity-aware scheduling.

        Processes at most max_per_cycle tasks to avoid blocking the
        daemon loop. Remaining tasks are scheduled in subsequent cycles.

        Args:
            max_per_cycle: Maximum tasks to schedule per cycle (default: 5)

        Returns:
            Dictionary with scheduling summary
        """
        if not self.process_monitor or not hasattr(self.process_monitor, "scheduler"):
            return {"error": "ProcessMonitor scheduler not available", "scheduled": 0}

        pending_tasks = self.queue.get_pending_tasks()
        scheduler = self.process_monitor.scheduler

        results = {"total_pending": len(pending_tasks), "scheduled": 0, "tasks": []}

        for task in pending_tasks[:max_per_cycle]:
            # Use capacity scheduler to determine optimal time
            from .scheduler import SchedulingPriority, TaskType

            try:
                task_type = (
                    TaskType(task.task_type)
                    if task.task_type in [t.value for t in TaskType]
                    else TaskType.GENERAL
                )
                priority = (
                    SchedulingPriority(task.priority)
                    if task.priority in [p.value for p in SchedulingPriority]
                    else SchedulingPriority.NORMAL
                )

                scheduled = scheduler.schedule_task(
                    task_id=task.task_id,
                    task_type=task_type,
                    priority=priority,
                    estimated_duration_minutes=task.estimated_duration_minutes,
                )

                # Update task with scheduled time
                conn = sqlite3.connect(self.queue.db_path)
                conn.execute(
                    """
                    UPDATE batch_tasks
                    SET scheduled_time = ?, state = 'scheduled'
                    WHERE task_id = ?
                """,
                    (scheduled.recommended_start_time.isoformat(), task.task_id),
                )
                conn.commit()
                conn.close()

                results["scheduled"] += 1
                results["tasks"].append(
                    {
                        "task_id": task.task_id,
                        "description": task.description,
                        "scheduled_time": scheduled.recommended_start_time.isoformat(),
                        "reason": scheduled.scheduling_reason,
                    }
                )

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

        cycle = 0
        while not self._shutdown_event.is_set():
            cycle += 1
            try:
                # Update session cache for fast startup (lightweight operation)
                try:
                    import sys
                    from pathlib import Path

                    cortex_root = Path(__file__).parent.parent.parent
                    if str(cortex_root) not in sys.path:
                        sys.path.insert(0, str(cortex_root))
                    from session_cache import update_session_cache

                    update_session_cache()
                    self.logger.debug("Session cache updated")
                except Exception as cache_error:
                    self.logger.debug(f"Session cache update failed: {cache_error}")

                # EXECUTE FIRST: Process scheduled tasks that are ready
                # This runs before scheduling to avoid being blocked by slow scheduling
                process_results = self.process_scheduled_tasks()
                if process_results["executed"] > 0:
                    self.logger.info(f"Executed {process_results['executed']} tasks")

                if process_results["deferred"] > 0:
                    self.logger.info(
                        f"Deferred {process_results['deferred']} tasks due to capacity"
                    )

                # THEN SCHEDULE: Move pending tasks to scheduled (max 5 per cycle)
                schedule_results = self.schedule_pending_tasks()
                if schedule_results.get("scheduled", 0) > 0:
                    self.logger.info(f"Scheduled {schedule_results['scheduled']} tasks")

                # Heartbeat every 10 cycles (~10 min) for daemon health monitoring
                if cycle % 10 == 0:
                    pending = schedule_results.get("total_pending", 0)
                    running = len(self._running_tasks)
                    self.logger.info(
                        f"Heartbeat: cycle={cycle}, running={running}, "
                        f"pending={pending}, ready={process_results.get('total_ready', 0)}"
                    )

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
            "running_tasks": len(self._running_tasks),
            "max_concurrent": self.max_concurrent,
            "shutdown": self._shutdown_event.is_set(),
            "running_task_ids": list(self._running_tasks.keys()),
        }
