"""
Cortex Supervisor Core - Always-on batch orchestration.

The supervisor unifies shell task execution and AI batch API calls with:
- Immediate execution (no arbitrary scheduled_time delays)
- Self-healing (detects and retries stuck tasks)
- Daemon support (start/stop/status)
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil
from intelligence.process_monitor.batch_executor import BatchExecutor
from intelligence.process_monitor.batch_queue import BatchTaskQueue, TaskState

from .config import SupervisorConfig
from .health import HealthMonitor
from .models import TickResult, WorkItem

logger = logging.getLogger(__name__)


def _estimate_quality(result: Any) -> float:
    """Heuristic quality score for a dispatch result (0.0-1.0).

    Replaces the previous hardcoded 1.0/0.0 binary with signals from
    the actual output to give the router real learning signal:
    - Failed dispatch → 0.0
    - Very short output (<50 chars) → 0.2 (likely "I need more context")
    - Contains refusal signals → 0.3
    - Contains structured output (code blocks, JSON, tables) → 0.9
    - Medium-length substantive output → 0.7
    """
    if not result.success:
        return 0.0

    output = result.output.strip()
    length = len(output)

    lower = output.lower()

    # Very short AND no structured content = low quality
    if length < 50 and "```" not in output:
        return 0.2

    # Refusal / inability signals
    refusal_phrases = [
        "cannot complete",
        "need more context",
        "need additional information",
        "unable to",
        "please provide",
        "i need clarification",
        "insufficient input",
    ]
    if any(phrase in lower for phrase in refusal_phrases):
        return 0.3

    # Structured output signals (code, JSON, tables, headings)
    structured_signals = 0
    if "```" in output:
        structured_signals += 1
    if output.count("#") >= 2:
        structured_signals += 1
    if any(c in output for c in ["{", "[", "|---"]):
        structured_signals += 1
    if length > 500:
        structured_signals += 1

    if structured_signals >= 2:
        return 0.9
    if structured_signals == 1:
        return 0.7

    # Default: moderate quality
    return 0.6


class CortexSupervisor:
    """
    Main orchestrator that unifies batch execution.

    Coordinates:
    - HealthMonitor: Detects and heals stuck tasks
    - BatchTaskQueue: Shell task scheduling
    - BatchExecutor: Shell command execution
    - SupervisorDelegator: Intelligent task routing to specialized agents

    Usage:
        supervisor = CortexSupervisor()
        supervisor.run_once()  # Single tick
        supervisor.start(foreground=True)  # Daemon mode
    """

    def __init__(
        self,
        config: Optional[SupervisorConfig] = None,
    ):
        """
        Initialize the supervisor.

        Args:
            config: Supervisor configuration (uses defaults if None)
        """
        self.config = config or SupervisorConfig()

        # Core components
        self.shell_queue = BatchTaskQueue()
        self.shell_executor = BatchExecutor(queue=self.shell_queue)
        self.health_monitor = HealthMonitor(
            shell_queue=self.shell_queue,
            stale_task_hours=self.config.stale_task_hours,
            max_retries=self.config.max_retries,
        )

        # Orchestration pipeline (lazy-initialized to avoid import cost at startup)
        self._intake = None
        self._router = None
        self._dispatcher = None
        self._collector = None
        self._pending_work_items: List[WorkItem] = []

        # Daemon state
        self._shutdown_event = threading.Event()
        self._last_health_check = datetime.min
        self._last_work_discovery = datetime.min
        self._tick_count = 0
        self._started_at: Optional[datetime] = None

        # AI batch state (Phase 2)
        self._pending_ai_tasks: List[Any] = []
        self._last_ai_batch_submission = datetime.min

    def tick(self) -> TickResult:
        """
        Main supervisor cycle. Called every tick_interval_seconds.

        Returns:
            TickResult with actions taken
        """
        result = TickResult(timestamp=datetime.now())
        self._tick_count += 1

        try:
            # 1. Health check (periodic)
            if self._should_run_health_check():
                healing_actions = self.health_monitor.check_and_heal()
                result.tasks_healed = len([a for a in healing_actions if a.success])
                result.healed_task_ids = [a.issue.target_id for a in healing_actions if a.success]
                self._last_health_check = datetime.now()

            # 1b. Work discovery (periodic)
            if self._should_run_work_discovery():
                discovered = self._discover_work()
                result.work_discovered = len(discovered)
                result.work_items = discovered
                self._pending_work_items.extend(discovered)
                self._last_work_discovery = datetime.now()

            # 1c. Dispatch pending AI work items via orchestration pipeline
            if self._pending_work_items and self.config.enable_ai_batching:
                try:
                    dispatch_summary = self._dispatch_work_items()
                    result.ai_tasks_queued = dispatch_summary["queued"]
                    result.ai_tasks_dispatched = dispatch_summary["dispatched"]
                    result.ai_tasks_succeeded = dispatch_summary["succeeded"]
                    result.ai_tasks_failed = dispatch_summary["failed"]
                    result.orchestration_errors = dispatch_summary.get("errors", [])
                except Exception as e:
                    logger.error(f"Orchestration pipeline failed: {e}", exc_info=True)
                    result.orchestration_errors.append(str(e))

            # 2. Execute ready shell tasks IMMEDIATELY
            #    (ignoring scheduled_time - we run tasks as soon as dependencies are met)
            ready_tasks = self._get_ready_tasks()
            concurrent_running = len(self.shell_queue.get_running_tasks())
            available_slots = self.config.max_concurrent_shell_tasks - concurrent_running

            for task in ready_tasks[:available_slots]:
                try:
                    # Check if executor can run it
                    can_run, reason = self.shell_executor.can_execute_now(task)
                    if can_run:
                        self.shell_executor.execute_task_async(task)
                        result.shell_tasks_started += 1
                        result.shell_task_ids.append(task.task_id)
                        logger.info(f"Started task {task.task_id[:8]}: {task.description[:50]}")
                    else:
                        logger.debug(f"Cannot execute task {task.task_id[:8]}: {reason}")
                except Exception as e:
                    logger.error(f"Error starting task {task.task_id[:8]}: {e}")
                    result.errors.append(f"Task start failed: {e}")

            # 3. Check for completed tasks
            completed = self._check_completed_tasks()
            result.shell_tasks_completed = len(completed)

        except Exception as e:
            logger.error(f"Tick error: {e}", exc_info=True)
            result.errors.append(str(e))

        # Log summary
        if result.shell_tasks_started or result.tasks_healed or result.errors:
            logger.info(f"Tick #{self._tick_count}: {result.summary()}")

        return result

    def _get_ready_tasks(self) -> List[Any]:
        """
        Get tasks ready to execute.

        Ready means:
        - State is PENDING or SCHEDULED
        - All dependencies are completed
        - NOT waiting for scheduled_time (we execute immediately)
        """
        # Get tasks with dependencies met
        ready = self.shell_queue.get_next_available_tasks()

        # Also include SCHEDULED tasks that we would normally wait for
        # (The whole point is to NOT wait for scheduled_time)
        scheduled = self.shell_queue._get_tasks_by_state(TaskState.SCHEDULED)

        # Filter scheduled tasks to those with met dependencies
        completed_ids = set(
            t.task_id for t in self.shell_queue._get_tasks_by_state(TaskState.COMPLETED)
        )

        for task in scheduled:
            if task not in ready and task.can_start(completed_ids):
                ready.append(task)

        return ready

    def _check_completed_tasks(self) -> List[str]:
        """Check for recently completed tasks."""
        # This is mostly for logging/metrics
        # The executor handles completion internally
        self.shell_queue._get_tasks_by_state(TaskState.COMPLETED)
        # Could track and return newly completed since last tick
        return []

    def _should_run_health_check(self) -> bool:
        """Check if it's time for a health check."""
        if not self.config.enable_self_healing:
            return False
        elapsed = datetime.now() - self._last_health_check
        return elapsed.total_seconds() >= self.config.health_check_interval_seconds

    def _should_run_work_discovery(self) -> bool:
        """Check if it's time to discover new work."""
        if not self.config.enable_work_discovery:
            return False
        elapsed = datetime.now() - self._last_work_discovery
        return elapsed.total_seconds() >= self.config.work_discovery_interval_seconds

    def _get_intake(self):
        """Lazy-initialize WorkIntake."""
        if self._intake is None:
            from .intake import WorkIntake

            self._intake = WorkIntake()
        return self._intake

    def _get_router(self):
        """Lazy-initialize ModelRouter."""
        if self._router is None:
            from .router import ModelRouter

            self._router = ModelRouter()
        return self._router

    def _get_dispatcher(self):
        """Lazy-initialize AgentDispatcher."""
        if self._dispatcher is None:
            from .dispatch import AgentDispatcher

            self._dispatcher = AgentDispatcher()
        return self._dispatcher

    def _get_collector(self):
        """Lazy-initialize ResultCollector."""
        if self._collector is None:
            from .collector import ResultCollector

            self._collector = ResultCollector()
        return self._collector

    def _discover_work(self) -> List[WorkItem]:
        """Discover actionable work from all sources."""
        try:
            intake = self._get_intake()
            items = intake.discover_all()
            if items:
                logger.info(f"Discovered {len(items)} work items")
            return items
        except Exception as e:
            logger.error(f"Work discovery failed: {e}")
            return []

    def _dispatch_work_items(self) -> Dict[str, Any]:
        """Route and dispatch pending work items.

        Returns a summary dict with keys: queued, dispatched, succeeded, failed, errors.
        """
        router = self._get_router()
        dispatcher = self._get_dispatcher()
        collector = self._get_collector()
        dispatched = 0
        succeeded = 0
        failed = 0
        errors: List[str] = []

        # Process up to max_ai_batch_size items per tick
        batch = self._pending_work_items[: self.config.max_ai_batch_size]
        self._pending_work_items = self._pending_work_items[self.config.max_ai_batch_size :]

        for work_item in batch:
            try:
                # Route: select model
                model_selection = router.select_model(work_item)
                logger.info(
                    f"Routed {work_item.id[:8]} → {model_selection.model_tier} "
                    f"({model_selection.reasoning[:60]})"
                )

                # Dispatch: execute via agent
                from .dispatch import ModelSelection as DispatchModelSelection

                dispatch_selection = DispatchModelSelection(
                    model_tier=model_selection.model_tier,
                    model_id=model_selection.model_id,
                    reasoning=model_selection.reasoning,
                    complexity_score=model_selection.complexity_score,
                    confidence=model_selection.confidence,
                )
                result = dispatcher.dispatch(work_item, dispatch_selection)

                # Collect: record outcome
                collector.collect(result)
                collector.record_outcome(result)

                # Feed back to router for learning with heuristic quality
                quality = _estimate_quality(result)
                router.record_outcome(
                    work_item_id=work_item.id,
                    model_tier=model_selection.model_tier,
                    success=result.success,
                    quality_score=quality,
                    task_type=work_item.task_type,
                )

                dispatched += 1
                if result.success:
                    succeeded += 1
                else:
                    failed += 1
                    if result.error:
                        errors.append(f"{work_item.id[:8]}: {result.error}")

            except Exception as e:
                logger.error(f"Dispatch failed for {work_item.id[:8]}: {e}")
                failed += 1
                errors.append(f"{work_item.id[:8]}: {e}")

        # Persist batch results if any
        if dispatched > 0:
            try:
                collector.persist()
                summary = collector.get_summary()
                logger.info(
                    f"Batch complete: {summary.succeeded}/{summary.total} succeeded, "
                    f"{summary.total_tokens} tokens, {summary.total_duration_seconds}s"
                )
                collector.clear()
            except Exception as e:
                logger.error(f"Failed to persist results: {e}")
                errors.append(f"persist: {e}")

        return {
            "queued": len(batch),
            "dispatched": dispatched,
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
        }

    def orchestrate(self, work_items: Optional[List[WorkItem]] = None) -> Dict[str, Any]:
        """Run a one-shot orchestration cycle (CLI/MCP entry point).

        If work_items is None, discovers work from all sources.
        Returns summary of the orchestration run.
        """
        if work_items is None:
            work_items = self._discover_work()

        if not work_items:
            return {"status": "no_work", "items_found": 0}

        self._pending_work_items = work_items
        dispatch_summary = self._dispatch_work_items()

        return {
            "status": "completed",
            "items_found": len(work_items),
            "items_dispatched": dispatch_summary["dispatched"],
            "items_succeeded": dispatch_summary["succeeded"],
            "items_failed": dispatch_summary["failed"],
            "items_remaining": len(self._pending_work_items),
            "errors": dispatch_summary.get("errors", []),
        }

    def run_once(self) -> TickResult:
        """
        Run a single supervisor tick.

        Returns:
            TickResult with actions taken
        """
        return self.tick()

    def run_daemon(self, interval_seconds: Optional[int] = None):
        """
        Run the supervisor loop until shutdown.

        Args:
            interval_seconds: Override tick interval (uses config if None)
        """
        interval = interval_seconds or self.config.tick_interval_seconds
        self._started_at = datetime.now()

        logger.info(f"Supervisor daemon starting (interval: {interval}s)")

        while not self._shutdown_event.is_set():
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Daemon tick error: {e}", exc_info=True)

            # Interruptible wait
            self._shutdown_event.wait(timeout=interval)

        logger.info("Supervisor daemon stopped")

    def shutdown(self):
        """Signal the daemon to stop."""
        logger.info("Shutdown requested")
        self._shutdown_event.set()
        self.shell_executor.shutdown()

    # ==================== Daemon Lifecycle ====================

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def shutdown_handler(signum, frame):
            sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logger.info(f"Received {sig_name}, initiating graceful shutdown...")
            self.shutdown()

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

    def _setup_logging(self, background: bool = False):
        """Setup logging for the supervisor."""
        handlers = [logging.FileHandler(self.config.log_file)]
        if not background:
            handlers.append(logging.StreamHandler(sys.stdout))

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
            force=True,
        )

    def _write_pid_file(self):
        """Write current process PID to file."""
        pid = os.getpid()
        self.config.pid_file.write_text(str(pid))
        logger.info(f"Supervisor started with PID {pid}")

    def _remove_pid_file(self):
        """Remove PID file."""
        if self.config.pid_file.exists():
            self.config.pid_file.unlink()
            logger.info("PID file removed")

    def _read_pid_file(self) -> Optional[int]:
        """Read PID from file."""
        if not self.config.pid_file.exists():
            return None
        try:
            return int(self.config.pid_file.read_text().strip())
        except (ValueError, IOError):
            return None

    def _is_process_running(self, pid: int) -> bool:
        """Check if process with given PID is running."""
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def start(
        self, foreground: bool = True, interval_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Start the supervisor daemon.

        Args:
            foreground: Run in foreground (True) or background (False)
            interval_seconds: Override tick interval

        Returns:
            Status dictionary with success/error information
        """
        # Check if already running
        existing_pid = self._read_pid_file()
        if existing_pid and self._is_process_running(existing_pid):
            return {
                "success": False,
                "error": f"Supervisor already running with PID {existing_pid}",
                "pid": existing_pid,
            }

        # Clean up stale PID file
        if existing_pid:
            self._remove_pid_file()

        interval = interval_seconds or self.config.tick_interval_seconds

        if not foreground:
            # Fork to background
            try:
                pid = os.fork()
                if pid > 0:
                    # Parent process - return immediately
                    return {
                        "success": True,
                        "message": "Supervisor started in background",
                        "pid": pid,
                        "interval": interval,
                        "log_file": str(self.config.log_file),
                    }
            except OSError as e:
                return {"success": False, "error": f"Failed to fork process: {e}"}

            # Child process continues
            os.setsid()

            # Second fork to prevent zombie
            try:
                pid = os.fork()
                if pid > 0:
                    sys.exit(0)
            except OSError:
                sys.exit(1)

            sys.stdout.flush()
            sys.stderr.flush()

            self._setup_logging(background=True)
        else:
            self._setup_logging(background=False)

        # Setup signal handlers
        self._setup_signal_handlers()

        # Write PID file
        self._write_pid_file()

        try:
            # Run daemon loop
            self.run_daemon(interval_seconds=interval)
        except Exception as e:
            logger.error(f"Supervisor error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            self._remove_pid_file()

        return {"success": True, "message": "Supervisor stopped", "pid": os.getpid()}

    def stop(self) -> Dict[str, Any]:
        """
        Stop the supervisor daemon.

        Returns:
            Status dictionary with success/error information
        """
        pid = self._read_pid_file()

        if not pid:
            return {
                "success": False,
                "error": "Supervisor is not running (no PID file found)",
            }

        if not self._is_process_running(pid):
            self._remove_pid_file()
            return {
                "success": False,
                "error": f"Supervisor not running (stale PID file for PID {pid})",
            }

        # Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, signal.SIGTERM)

            # Wait for process to stop (up to 10 seconds)
            for _ in range(100):
                if not self._is_process_running(pid):
                    break
                time.sleep(0.1)

            if self._is_process_running(pid):
                os.kill(pid, signal.SIGKILL)
                return {
                    "success": True,
                    "message": f"Supervisor stopped (force killed PID {pid})",
                    "pid": pid,
                    "forced": True,
                }

            return {
                "success": True,
                "message": "Supervisor stopped gracefully",
                "pid": pid,
                "forced": False,
            }

        except ProcessLookupError:
            self._remove_pid_file()
            return {"success": True, "message": "Supervisor already stopped", "pid": pid}
        except PermissionError:
            return {"success": False, "error": f"Permission denied to stop PID {pid}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to stop supervisor: {e}"}

    def status(self) -> Dict[str, Any]:
        """
        Get supervisor status.

        Returns:
            Status dictionary with running state and details
        """
        pid = self._read_pid_file()

        if not pid:
            return {
                "running": False,
                "message": "Supervisor is not running",
                "pid_file": str(self.config.pid_file),
            }

        is_running = self._is_process_running(pid)

        if not is_running:
            return {
                "running": False,
                "message": f"Supervisor not running (stale PID file for PID {pid})",
                "pid": pid,
                "pid_file": str(self.config.pid_file),
            }

        # Get process info
        try:
            process = psutil.Process(pid)
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time

            # Get queue stats
            queue_stats = self.shell_queue.get_queue_stats()

            return {
                "running": True,
                "pid": pid,
                "uptime": str(uptime).split(".")[0],  # Remove microseconds
                "uptime_seconds": uptime.total_seconds(),
                "started_at": create_time.isoformat(),
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / (1024 * 1024),
                "log_file": str(self.config.log_file),
                "config": {
                    "tick_interval": self.config.tick_interval_seconds,
                    "health_interval": self.config.health_check_interval_seconds,
                    "max_concurrent": self.config.max_concurrent_shell_tasks,
                },
                "queue": queue_stats,
            }

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return {
                "running": True,
                "pid": pid,
                "error": f"Could not get process details: {e}",
            }

    def get_queue_summary(self) -> Dict[str, Any]:
        """Get a summary of the current queue state."""
        stats = self.shell_queue.get_queue_stats()

        return {
            "total_tasks": stats.get("total", 0),
            "by_state": stats.get("by_state", {}),
            "running": len(self.shell_queue.get_running_tasks()),
            "ready": len(self._get_ready_tasks()),
        }

    def get_delegation_summary(self) -> Dict[str, Any]:
        """Get a summary of agent registry and routing configuration."""
        from .agents import list_agents

        agents = list_agents()
        return {
            "agents": len(agents),
            "profiles": [
                {"name": a.name, "tier": a.preferred_model_tier, "tasks": sorted(a.task_types)}
                for a in agents
            ],
        }
