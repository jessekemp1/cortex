"""
Cortex Supervisor Core - Always-on batch orchestration.

The supervisor unifies shell task execution and AI batch API calls with:
- Immediate execution (no arbitrary scheduled_time delays)
- Self-healing (detects and retries stuck tasks)
- Daemon support (start/stop/status)
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psutil
from intelligence.process_monitor.batch_executor import BatchExecutor
from intelligence.process_monitor.batch_queue import BatchTaskQueue, TaskState

from .config import SupervisorConfig
from .health import HealthMonitor
from .models import TickResult, WorkItem
from .quality_evaluator import QualityEvaluator

logger = logging.getLogger(__name__)

# Module-level evaluator instance (lazy init via _get_quality_evaluator)
_quality_evaluator: Optional[QualityEvaluator] = None
_quality_evaluator_lock = threading.Lock()


def _get_quality_evaluator() -> QualityEvaluator:
    """Lazy-init singleton QualityEvaluator (thread-safe)."""
    global _quality_evaluator
    if _quality_evaluator is None:
        with _quality_evaluator_lock:
            if _quality_evaluator is None:
                _quality_evaluator = QualityEvaluator(use_ai_judge=False)
    return _quality_evaluator


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

        # Lock for mutable shared state accessed during tick()
        self._state_lock = threading.Lock()

        # Work dedup tracking — avoid re-dispatching the same items every tick
        self._dispatched_ids: set = set()
        self._dispatched_descriptions: Dict[str, float] = {}  # description -> timestamp
        self._dispatch_ttl_seconds = 24 * 3600

        # GOALS.md file watcher (stat-based mtime polling)
        self._goals_mtime: float = 0.0

        # Daemon state
        self._shutdown_event = threading.Event()
        self._last_health_check = datetime.min
        self._last_work_discovery = datetime.min
        self._tick_count = 0
        self._started_at: Optional[datetime] = None

        # AI batch state
        self._pending_ai_tasks: List[Any] = []
        self._last_ai_batch_submission = datetime.min
        self._pending_batch_ids: List[str] = []

        # Overnight batch queue (deferred LOW-priority items for 50% cost savings)
        self._overnight_queue: List[WorkItem] = []
        self._load_overnight_state()

        # Approval gate (lazy-initialized)
        self._approval_gate = None

        # Orchestration metrics (Phase 5)
        self._metrics = self._init_metrics()

        # Restore persisted state (dispatched IDs, batch IDs, tick count)
        self._load_state()

    def tick(self) -> TickResult:
        """
        Main supervisor cycle. Called every tick_interval_seconds.

        Returns:
            TickResult with actions taken
        """
        result = TickResult(timestamp=datetime.now())  # noqa: DTZ005

        with self._state_lock:
            self._tick_count += 1

        try:
            # 1. Health check (periodic)
            if self._should_run_health_check():
                healing_actions = self.health_monitor.check_and_heal()
                result.tasks_healed = len([a for a in healing_actions if a.success])
                result.healed_task_ids = [a.issue.target_id for a in healing_actions if a.success]
                self._last_health_check = datetime.now()  # noqa: DTZ005

            # 1a. Check pending AI batches for results
            if self._pending_batch_ids:
                try:
                    received = self._check_pending_batches()
                    result.ai_results_received += received
                except Exception as e:
                    logger.error(f"Batch check failed: {e}", exc_info=True)
                    result.orchestration_errors.append(f"batch_check: {e}")

            # 1b. Work discovery (periodic)
            if self._should_run_work_discovery():
                discovered = self._discover_work()
                result.work_discovered = len(discovered)
                result.work_items = discovered
                # Dedup: skip items already dispatched or similar to dispatched
                self._cleanup_dispatched_cache()
                new_items = [
                    item
                    for item in discovered
                    if item.id not in self._dispatched_ids
                    and not self._is_recently_dispatched(item.description)
                ]
                self._pending_work_items.extend(new_items)
                self._last_work_discovery = datetime.now()  # noqa: DTZ005

            # 1c. Dispatch pending AI work items via orchestration pipeline
            if self._pending_work_items and self.config.enable_ai_batching:
                try:
                    dispatch_summary = self._dispatch_work_items()
                    result.ai_tasks_queued = dispatch_summary["queued"]
                    result.ai_tasks_dispatched = dispatch_summary["dispatched"]
                    result.ai_tasks_succeeded = dispatch_summary["succeeded"]
                    result.ai_tasks_failed = dispatch_summary["failed"]
                    result.overnight_deferred = dispatch_summary.get("overnight_deferred", 0)
                    result.orchestration_errors = dispatch_summary.get("errors", [])
                except Exception as e:
                    logger.error(f"Orchestration pipeline failed: {e}", exc_info=True)
                    result.orchestration_errors.append(str(e))

            # 1d. Submit overnight batch if in overnight window with enough items
            if self._should_submit_overnight_batch():
                try:
                    batch_id = self._submit_overnight_batch()
                    if batch_id:
                        result.overnight_batch_submitted = True
                        result.ai_batch_submitted = True
                        result.ai_batch_id = batch_id
                        logger.info(
                            f"Overnight batch submitted: {batch_id} "
                            f"({len(self._overnight_queue)} items)"
                        )
                except Exception as e:
                    logger.error(f"Overnight batch submission failed: {e}", exc_info=True)
                    result.orchestration_errors.append(f"overnight_batch: {e}")

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
                    logger.error(f"Error starting task {task.task_id[:8]}: {e}", exc_info=True)
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

        # Persist state for crash recovery
        self._save_state()

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
        elapsed = datetime.now() - self._last_health_check  # noqa: DTZ005
        return elapsed.total_seconds() >= self.config.health_check_interval_seconds

    def _should_run_work_discovery(self) -> bool:
        """Check if work discovery should run (interval OR goals changed)."""
        if not self.config.enable_work_discovery:
            return False
        # Check if GOALS.md changed (reactive, every tick)
        if self.config.watch_goals and self._goals_file_changed():
            logger.info("GOALS.md changed — triggering immediate work discovery")
            return True
        # Normal interval check
        elapsed = datetime.now() - self._last_work_discovery  # noqa: DTZ005
        return elapsed.total_seconds() >= self.config.work_discovery_interval_seconds

    def _goals_file_changed(self) -> bool:
        """Check if GOALS.md has been modified since last check."""
        from pathlib import Path

        from .intake import _find_repo_root

        root = (
            Path(os.environ.get("CORTEX_ROOT_DIR", ""))
            if os.environ.get("CORTEX_ROOT_DIR")
            else _find_repo_root()
        )
        goals_path = root / "GOALS.md"
        try:
            mtime = goals_path.stat().st_mtime
            if mtime > self._goals_mtime:
                prev = self._goals_mtime
                self._goals_mtime = mtime
                return prev > 0  # Skip first check (initialization)
        except OSError:
            pass
        return False

    def _get_intake(self):
        """Lazy-initialize WorkIntake."""
        if self._intake is None:
            from .intake import WorkIntake

            self._intake = WorkIntake()
        return self._intake

    def _get_router(self):
        """Lazy-initialize ModelRouter (or AdvancedModelRouter when multi-provider enabled)."""
        if self._router is None:
            if self.config.enable_multi_provider:
                try:
                    from .providers import ProviderRegistry
                    from .router import AdvancedModelRouter

                    registry = ProviderRegistry(config_path=self.config.providers_config_path)
                    self._router = AdvancedModelRouter(registry=registry)
                    logger.info("Initialized AdvancedModelRouter with multi-provider support")
                except Exception as exc:
                    logger.warning("AdvancedModelRouter init failed (%s), falling back", exc)
                    from .router import ModelRouter

                    self._router = ModelRouter()
            else:
                from .router import ModelRouter

                self._router = ModelRouter()
        return self._router

    def _get_dispatcher(self):
        """Lazy-initialize AgentDispatcher (or MultiProviderDispatcher when enabled)."""
        if self._dispatcher is None:
            from .dispatch import AgentDispatcher

            base_dispatcher = AgentDispatcher(dry_run=self.config.dry_run)

            if self.config.enable_multi_provider:
                try:
                    from .multi_dispatch import MultiProviderDispatcher
                    from .providers import ProviderRegistry

                    registry = ProviderRegistry(config_path=self.config.providers_config_path)
                    self._dispatcher = MultiProviderDispatcher(
                        registry=registry,
                        anthropic_dispatcher=base_dispatcher,
                    )
                    logger.info("Initialized MultiProviderDispatcher")
                except Exception as exc:
                    logger.warning("MultiProviderDispatcher init failed (%s), falling back", exc)
                    self._dispatcher = base_dispatcher
            else:
                self._dispatcher = base_dispatcher
        return self._dispatcher

    def _get_collector(self):
        """Lazy-initialize ResultCollector."""
        if self._collector is None:
            from .collector import ResultCollector

            self._collector = ResultCollector()
        return self._collector

    def _get_team_orchestrator(self):
        """Get TeamOrchestrator if enable_teams is on, else None.

        Passes the dispatcher so the team lead (Opus) can make real LLM calls
        for decomposition and synthesis.
        """
        if not self.config.enable_teams:
            return None
        try:
            from .teams import TeamOrchestrator

            dispatcher = self._get_dispatcher()
            return TeamOrchestrator(enabled=True, dispatcher=dispatcher)
        except Exception:
            return None

    @staticmethod
    def _init_metrics():
        """Initialize OrchestrationMetrics if enable_routing_analytics is on."""
        try:
            from .metrics import OrchestrationMetrics

            return OrchestrationMetrics()
        except Exception:
            return None

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

    def _dedup_work_items(self, items: List[WorkItem]) -> List[WorkItem]:
        """Filter out items that were already dispatched or are too similar."""
        from .intake import _similarity

        new_items: List[WorkItem] = []
        for item in items:
            # Exact ID match
            if item.id in self._dispatched_ids:
                continue
            # Similarity check against previously dispatched descriptions
            is_dup = False
            for desc in self._dispatched_descriptions:
                if _similarity(item.description, desc) > 0.7:
                    is_dup = True
                    break
            if not is_dup:
                new_items.append(item)
        return new_items

    def _dispatch_work_items(self) -> Dict[str, Any]:
        """Route and dispatch pending work items.

        Handles:
        - Dedup: skips items already dispatched (by ID or description similarity)
        - Shell routing: items with `command` go to BatchExecutor
        - AI dispatch: everything else goes through router → dispatcher → collector

        Returns a summary dict with keys: queued, dispatched, succeeded, failed, errors.
        """
        from .models import RoutedTask, TaskTarget

        router = self._get_router()
        dispatcher = self._get_dispatcher()
        collector = self._get_collector()
        dispatched = 0
        succeeded = 0
        failed = 0
        shell_routed = 0
        errors: List[str] = []

        # Process up to max_ai_batch_size items per tick
        batch = self._pending_work_items[: self.config.max_ai_batch_size]
        self._pending_work_items = self._pending_work_items[self.config.max_ai_batch_size :]

        # Dedup: filter out already-dispatched items
        self._cleanup_dispatched_cache()
        batch = [
            wi
            for wi in batch
            if wi.id not in self._dispatched_ids
            and not self._is_recently_dispatched(wi.description)
        ]

        # Split into shell vs AI vs overnight-deferred items
        shell_items: List[WorkItem] = []
        ai_items: List[WorkItem] = []
        deferred_count = 0
        for work_item in batch:
            if self._should_route_to_shell(work_item):
                shell_items.append(work_item)
            elif self._should_defer_overnight(work_item):
                self._overnight_queue.append(work_item)
                self._mark_dispatched(work_item)
                deferred_count += 1
                logger.info(
                    f"Deferred {work_item.id[:8]} to overnight batch "
                    f"(priority={work_item.priority.value})"
                )
            else:
                ai_items.append(work_item)

        if deferred_count:
            self._save_overnight_state()

        # Approval gate: filter AI items through policy
        gate = self._get_approval_gate()
        approved_ai_items: List[WorkItem] = []
        for work_item in ai_items:
            ok, reason = gate.check(work_item)
            if ok:
                approved_ai_items.append(work_item)
            else:
                logger.info(f"Gated {work_item.id[:8]}: {reason}")
        ai_items = approved_ai_items

        # Route shell items to BatchExecutor
        for work_item in shell_items:
            try:
                routed = RoutedTask(
                    work_item=work_item,
                    target=TaskTarget.SHELL,
                    priority=work_item.priority.value,
                )
                kwargs = routed.as_shell_task()
                self.shell_queue.add_task(**kwargs)
                shell_routed += 1
                self._mark_dispatched(work_item)
                logger.info(f"Shell-routed {work_item.id[:8]}: {work_item.command[:50]}")
            except Exception as e:
                logger.error(f"Shell routing failed for {work_item.id[:8]}: {e}")
                errors.append(f"{work_item.id[:8]}: {e}")

        # Route AI items — batch path (multiple items) or single dispatch
        from .dispatch import ModelSelection as DispatchModelSelection

        if len(ai_items) > 1 and self.config.enable_ai_batching:
            # Batch path: route all items then submit as one batch
            batch_pairs: list[tuple[WorkItem, Any]] = []
            for work_item in ai_items:
                try:
                    ms = router.select_model(work_item)
                    logger.info(
                        f"Routed {work_item.id[:8]} → {ms.model_tier} ({ms.reasoning[:60]})"
                    )
                    dispatch_ms = DispatchModelSelection(
                        model_tier=ms.model_tier,
                        model_id=ms.model_id,
                        reasoning=ms.reasoning,
                        complexity_score=ms.complexity_score,
                        confidence=ms.confidence,
                    )
                    batch_pairs.append((work_item, dispatch_ms))
                except Exception as e:
                    logger.error(f"Routing failed for {work_item.id[:8]}: {e}")
                    failed += 1
                    errors.append(f"{work_item.id[:8]}: {e}")

            if batch_pairs:
                try:
                    batch_id = dispatcher.submit_batch(batch_pairs)
                    self._pending_batch_ids.append(batch_id)
                    self._save_batch_state()
                    dispatched += len(batch_pairs)
                    for wi, _ in batch_pairs:
                        self._mark_dispatched(wi)
                    logger.info(f"Submitted AI batch {batch_id} with {len(batch_pairs)} items")
                except Exception as e:
                    logger.error(f"Batch submission failed: {e}")
                    failed += len(batch_pairs)
                    errors.append(f"batch_submit: {e}")
        else:
            # Single-dispatch path (1 item or batching disabled)
            team_orchestrator = self._get_team_orchestrator()

            for work_item in ai_items:
                try:
                    # Use AdvancedModelRouter.route_advanced() when available
                    if hasattr(router, "route_advanced"):
                        model_selection = router.route_advanced(
                            work_item,
                            ab_baseline_ratio=self.config.ab_baseline_ratio,
                        )
                    else:
                        model_selection = router.select_model(work_item)
                    logger.info(
                        f"Routed {work_item.id[:8]} → {model_selection.model_tier} "
                        f"({model_selection.reasoning[:60]})"
                    )

                    # Check if team decomposition would benefit this task
                    team_name = None
                    if team_orchestrator is not None:
                        team_name = team_orchestrator.should_use_team(
                            work_item,
                            complexity_score=model_selection.complexity_score,
                        )

                    if team_name:
                        # Team execution path
                        import asyncio

                        logger.info(f"Team dispatch: {work_item.id[:8]} → {team_name}")
                        team_result = asyncio.run(
                            team_orchestrator.execute_with_team(work_item, team_name)
                        )
                        # Convert team result to dispatch-compatible format
                        from .dispatch import DispatchResult as DR

                        result = DR(
                            work_item_id=work_item.id,
                            success=team_result.success,
                            output=team_result.synthesized_output,
                            model_used=model_selection.model_id,
                            tokens_used=team_result.total_tokens,
                            duration_seconds=0.0,
                            task_type=work_item.task_type,
                            provider=getattr(model_selection, "provider", "anthropic"),
                            cost_usd=team_result.total_cost_usd,
                        )
                    else:
                        # Standard single dispatch
                        dispatch_selection = DispatchModelSelection(
                            model_tier=model_selection.model_tier,
                            model_id=model_selection.model_id,
                            reasoning=model_selection.reasoning,
                            complexity_score=model_selection.complexity_score,
                            confidence=model_selection.confidence,
                        )
                        result = dispatcher.dispatch(work_item, dispatch_selection)

                    collector.collect(result)
                    collector.record_outcome(
                        result,
                        is_baseline=getattr(model_selection, "is_baseline", False),
                    )

                    evaluation = _get_quality_evaluator().evaluate_heuristic(
                        work_item,
                        result,
                    )
                    router.record_outcome(
                        work_item_id=work_item.id,
                        model_tier=model_selection.model_tier,
                        success=result.success,
                        quality_score=evaluation.overall_score,
                        task_type=work_item.task_type,
                    )

                    # Record metrics if available
                    if self._metrics is not None:
                        self._metrics.record_dispatch(
                            provider=getattr(result, "provider", "anthropic"),
                            model=model_selection.model_id,
                            tier=model_selection.model_tier,
                            cost=getattr(result, "cost_usd", 0.0),
                            tokens=result.tokens_used,
                            latency=result.duration_seconds,
                            quality=evaluation.overall_score,
                        )

                    dispatched += 1
                    self._mark_dispatched(work_item)

                    if result.success:
                        succeeded += 1
                    else:
                        failed += 1
                        if result.error:
                            errors.append(f"{work_item.id[:8]}: {result.error}")

                except Exception as e:
                    logger.error(f"Dispatch failed for {work_item.id[:8]}: {e}", exc_info=True)
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
            "shell_routed": shell_routed,
            "overnight_deferred": deferred_count,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # AI batch polling
    # ------------------------------------------------------------------

    def _check_pending_batches(self) -> int:
        """Poll pending AI batches and collect any completed results.

        Returns the number of results received across all completed batches.
        """
        if not self._pending_batch_ids:
            return 0

        dispatcher = self._get_dispatcher()
        collector = self._get_collector()
        router = self._get_router()
        total_received = 0
        still_pending: List[str] = []

        for batch_id in self._pending_batch_ids:
            try:
                results = dispatcher.retrieve_batch(batch_id, router=router)
                if not results:
                    # Still in progress
                    still_pending.append(batch_id)
                    continue

                # Collect completed results
                for dr in results:
                    collector.collect(dr)
                    collector.record_outcome(dr)
                total_received += len(results)

                logger.info(
                    f"Batch {batch_id[:12]} complete: {len(results)} results "
                    f"({sum(1 for r in results if r.success)} succeeded)"
                )
            except Exception as e:
                logger.error(f"Failed to retrieve batch {batch_id[:12]}: {e}")
                still_pending.append(batch_id)  # Keep it for next tick

        had_completions = len(still_pending) < len(self._pending_batch_ids)
        self._pending_batch_ids = still_pending
        if had_completions:
            self._save_batch_state()

        if total_received > 0:
            try:
                collector.persist()
                collector.clear()
            except Exception as e:
                logger.error(f"Failed to persist batch results: {e}")

        return total_received

    # ------------------------------------------------------------------
    # Overnight batch queue (50% cost savings via Anthropic Batch API)
    # ------------------------------------------------------------------

    def _should_defer_overnight(self, work_item: WorkItem) -> bool:
        """Determine if a work item should be deferred to the overnight batch.

        Criteria: overnight enabled, item is LOW priority or explicitly flagged,
        and we're NOT currently in the overnight window (if we are, dispatch now).
        """
        if not self.config.overnight_batch_enabled:
            return False
        if work_item.defer_to_batch:
            return True
        from .models import WorkItemPriority

        if work_item.priority != WorkItemPriority.LOW:
            return False
        # Don't defer if we're in the overnight window — submit immediately
        if self._in_overnight_window():
            return False
        return True

    def _in_overnight_window(self) -> bool:
        """Check if current UTC hour is within the overnight submission window."""
        hour = datetime.now(timezone.utc).hour
        return self.config.overnight_start_hour <= hour < self.config.overnight_end_hour

    def _should_submit_overnight_batch(self) -> bool:
        """Check if we should submit the overnight queue now."""
        if not self.config.overnight_batch_enabled:
            return False
        if len(self._overnight_queue) < self.config.min_items_for_overnight_batch:
            return False
        return self._in_overnight_window()

    def _submit_overnight_batch(self) -> Optional[str]:
        """Submit all queued overnight items as a single Batch API call."""
        if not self._overnight_queue:
            return None

        from .dispatch import ModelSelection as DispatchModelSelection
        from .models import RoutedTask, TaskTarget

        router = self._get_router()
        dispatcher = self._get_dispatcher()

        batch_pairs: list[tuple[WorkItem, Any]] = []
        for work_item in self._overnight_queue:
            try:
                ms = router.select_model(work_item)
                dispatch_ms = DispatchModelSelection(
                    model_tier=ms.model_tier,
                    model_id=ms.model_id,
                    reasoning=ms.reasoning,
                    complexity_score=ms.complexity_score,
                    confidence=ms.confidence,
                )
                batch_pairs.append((work_item, dispatch_ms))
            except Exception as e:
                logger.error(f"Overnight routing failed for {work_item.id[:8]}: {e}")

        if not batch_pairs:
            return None

        batch_id = dispatcher.submit_batch(batch_pairs)
        self._pending_batch_ids.append(batch_id)

        logger.info(
            f"Overnight batch {batch_id[:12]}: {len(batch_pairs)} items submitted "
            f"(~50% cost savings)"
        )

        # Clear the queue and persist
        self._overnight_queue.clear()
        self._save_overnight_state()
        self._save_batch_state()

        return batch_id

    def _load_overnight_state(self):
        """Load overnight queue and pending batch IDs from disk (survives restarts)."""
        # Overnight queue
        qf = self.config.overnight_queue_file
        if qf.exists():
            try:
                data = json.loads(qf.read_text(encoding="utf-8"))
                for item_dict in data.get("queue", []):
                    try:
                        from .models import WorkItemPriority

                        wi = WorkItem(
                            id=item_dict["id"],
                            source=item_dict["source"],
                            task_type=item_dict["task_type"],
                            description=item_dict["description"],
                            prompt=item_dict.get("prompt"),
                            system_prompt=item_dict.get("system_prompt"),
                            project=item_dict.get("project"),
                            priority=WorkItemPriority(item_dict.get("priority", "low")),
                            defer_to_batch=True,
                        )
                        self._overnight_queue.append(wi)
                    except Exception:
                        continue
                logger.info(f"Loaded {len(self._overnight_queue)} overnight queue items")
            except Exception as e:
                logger.warning(f"Failed to load overnight queue: {e}")

        # Pending batch IDs
        batch_state = self.config.state_file.parent / "pending_batches.json"
        if batch_state.exists():
            try:
                self._pending_batch_ids = json.loads(batch_state.read_text(encoding="utf-8"))
                if self._pending_batch_ids:
                    logger.info(f"Recovered {len(self._pending_batch_ids)} pending batch IDs")
            except Exception as e:
                logger.warning(f"Failed to load pending batches: {e}")

    def _save_overnight_state(self):
        """Persist overnight queue to disk."""
        qf = self.config.overnight_queue_file
        try:
            qf.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "queue": [
                    {
                        "id": wi.id,
                        "source": wi.source,
                        "task_type": wi.task_type,
                        "description": wi.description,
                        "prompt": wi.prompt,
                        "system_prompt": wi.system_prompt,
                        "project": wi.project,
                        "priority": wi.priority.value,
                    }
                    for wi in self._overnight_queue
                ],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            tmp = qf.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            tmp.rename(qf)
        except Exception as e:
            logger.error(f"Failed to save overnight queue: {e}")

    def _save_batch_state(self):
        """Persist pending batch IDs to survive restarts."""
        batch_state = self.config.state_file.parent / "pending_batches.json"
        try:
            batch_state.parent.mkdir(parents=True, exist_ok=True)
            tmp = batch_state.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._pending_batch_ids))
            tmp.rename(batch_state)
        except Exception as e:
            logger.error(f"Failed to save batch state: {e}")

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------

    def _get_approval_gate(self):
        """Lazy-initialize the ApprovalGate from config."""
        if self._approval_gate is None:
            from .approval import ApprovalGate, ApprovalPolicy

            try:
                policy = ApprovalPolicy(self.config.approval_policy)
            except ValueError:
                logger.warning(
                    f"Unknown approval_policy '{self.config.approval_policy}', "
                    "falling back to gate_high"
                )
                policy = ApprovalPolicy.GATE_HIGH

            self._approval_gate = ApprovalGate(
                policy=policy,
                approval_dir=self.config.approval_dir,
            )
        return self._approval_gate

    # ------------------------------------------------------------------
    # Full state persistence (crash recovery)
    # ------------------------------------------------------------------

    def _save_state(self):
        """Persist all transient state to disk for crash recovery."""
        from pathlib import Path

        state = {
            "dispatched_ids": list(self._dispatched_ids),
            "dispatched_descriptions": self._dispatched_descriptions,
            "pending_batch_ids": self._pending_batch_ids,
            "tick_count": self._tick_count,
            "goals_mtime": self._goals_mtime,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(str(self.config.state_file) + ".tmp")
            tmp.write_text(json.dumps(state, indent=2))
            tmp.rename(self.config.state_file)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """Restore transient state from disk after restart."""
        if not self.config.state_file.exists():
            return
        try:
            state = json.loads(self.config.state_file.read_text())
            self._dispatched_ids = set(state.get("dispatched_ids", []))
            self._dispatched_descriptions = state.get("dispatched_descriptions", {})
            self._pending_batch_ids = state.get("pending_batch_ids", [])
            self._tick_count = state.get("tick_count", 0)
            self._goals_mtime = state.get("goals_mtime", 0.0)
            logger.info(
                f"Restored state: {len(self._dispatched_ids)} dispatched IDs, "
                f"{len(self._pending_batch_ids)} pending batches, "
                f"tick #{self._tick_count}"
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to restore state: {e} — starting fresh")

    # ------------------------------------------------------------------
    # Work dedup helpers
    # ------------------------------------------------------------------

    def _mark_dispatched(self, work_item: WorkItem) -> None:
        """Record a work item as dispatched to prevent re-dispatch."""
        with self._state_lock:
            self._dispatched_ids.add(work_item.id)
            self._dispatched_descriptions[work_item.description] = time.time()

    def _is_recently_dispatched(self, description: str) -> bool:
        """Check if a similar description was recently dispatched."""
        from .intake import _similarity

        with self._state_lock:
            descs = dict(self._dispatched_descriptions)
        for past_desc in descs:
            if _similarity(description, past_desc) >= 0.7:
                return True
        return False

    def _cleanup_dispatched_cache(self) -> None:
        """Remove expired entries from dispatched tracking (TTL-based)."""
        cutoff = time.time() - self._dispatch_ttl_seconds
        with self._state_lock:
            self._dispatched_descriptions = {
                desc: ts for desc, ts in self._dispatched_descriptions.items() if ts > cutoff
            }

    @staticmethod
    def _should_route_to_shell(work_item: WorkItem) -> bool:
        """Determine if a work item should go to shell executor."""
        return bool(work_item.command)

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
        self._started_at = datetime.now()  # noqa: DTZ005

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

        # Persist orchestration metrics to disk
        if self._metrics is not None:
            try:
                self._metrics.persist()
                logger.info("Orchestration metrics persisted")
            except Exception as exc:
                logger.warning("Failed to persist metrics: %s", exc)

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
            return int(self.config.pid_file.read_text(encoding="utf-8").strip())
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
            uptime = datetime.now() - create_time  # noqa: DTZ005

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
