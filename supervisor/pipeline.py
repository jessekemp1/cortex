"""
Orchestration pipeline -- single function that chains intake -> route -> dispatch -> collect.

Usage:
    from supervisor.pipeline import run_pipeline, PipelineResult

    result = run_pipeline()                    # discover + route + dispatch
    result = run_pipeline(dry_run=True)        # discover + route only
    result = run_pipeline(work_items=[...])    # skip discovery, route + dispatch
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import SupervisorConfig
from .models import RoutedTask, TaskTarget, WorkItem

log = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """A single routing decision: work item + model assignment."""

    work_item: WorkItem
    model_tier: str  # "opus", "sonnet", "haiku"
    model_id: str  # e.g. "claude-opus-4-6"
    complexity_score: float
    confidence: float
    reasoning: str


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    # Discovery
    items_discovered: int = 0
    work_items: List[WorkItem] = field(default_factory=list)

    # Routing
    routing_decisions: List[RoutingDecision] = field(default_factory=list)

    # Dispatch
    items_dispatched: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    dry_run: bool = False

    # Errors
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary for logging."""
        parts = [f"discovered={self.items_discovered}"]
        parts.append(f"routed={len(self.routing_decisions)}")
        if self.dry_run:
            parts.append("dry_run=True")
        else:
            parts.append(f"dispatched={self.items_dispatched}")
            parts.append(f"succeeded={self.items_succeeded}")
            parts.append(f"failed={self.items_failed}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "items_discovered": self.items_discovered,
            "routing_decisions": [
                {
                    "id": rd.work_item.id,
                    "description": rd.work_item.description[:80],
                    "task_type": rd.work_item.task_type,
                    "project": rd.work_item.project or "",
                    "priority": rd.work_item.priority.value
                    if hasattr(rd.work_item.priority, "value")
                    else str(rd.work_item.priority),
                    "model_tier": rd.model_tier,
                    "model_id": rd.model_id,
                    "complexity_score": round(rd.complexity_score, 2),
                    "confidence": round(rd.confidence, 2),
                    "reasoning": rd.reasoning,
                }
                for rd in self.routing_decisions
            ],
            "items_dispatched": self.items_dispatched,
            "items_succeeded": self.items_succeeded,
            "items_failed": self.items_failed,
            "dry_run": self.dry_run,
            "errors": self.errors,
        }


def run_pipeline(
    *,
    work_items: Optional[List[WorkItem]] = None,
    dry_run: bool = False,
    config: Optional[SupervisorConfig] = None,
    goals_path: Optional[Path] = None,
    project_filter: Optional[str] = None,
) -> PipelineResult:
    """Run the full orchestration pipeline: intake -> route -> dispatch -> collect.

    Args:
        work_items: Pre-built work items (skips discovery if provided).
        dry_run: If True, route but don't dispatch. Overrides config.dry_run.
        config: SupervisorConfig (uses defaults if None).
        goals_path: Override GOALS.md path for intake.
        project_filter: Only process items matching this project name.

    Returns:
        PipelineResult with discovery, routing, and dispatch details.
    """
    from .dispatch import AgentDispatcher
    from .intake import WorkIntake
    from .router import ModelRouter

    cfg = config or SupervisorConfig()
    effective_dry_run = dry_run or cfg.dry_run
    result = PipelineResult(dry_run=effective_dry_run)

    # ── Phase 1: Intake ──────────────────────────────────────────────
    if work_items is None:
        try:
            intake = WorkIntake()
            work_items = intake.discover_all(goals_path=goals_path)
        except Exception as exc:
            log.error("Work discovery failed: %s", exc)
            result.errors.append(f"discovery: {exc}")
            return result

    # Apply project filter
    if project_filter:
        work_items = [wi for wi in work_items if wi.project == project_filter]

    result.items_discovered = len(work_items)
    result.work_items = work_items

    if not work_items:
        log.info("Pipeline: no work items found")
        return result

    # ── Phase 2: Routing ─────────────────────────────────────────────
    router = ModelRouter()
    for wi in work_items:
        try:
            selection = router.select_model(wi)
            result.routing_decisions.append(
                RoutingDecision(
                    work_item=wi,
                    model_tier=selection.model_tier,
                    model_id=selection.model_id,
                    complexity_score=selection.complexity_score,
                    confidence=selection.confidence,
                    reasoning=selection.reasoning,
                )
            )
        except Exception as exc:
            log.error("Routing failed for %s: %s", wi.id, exc)
            result.errors.append(f"routing {wi.id[:8]}: {exc}")

    log.info(
        "Pipeline: routed %d items (opus=%d sonnet=%d haiku=%d)",
        len(result.routing_decisions),
        sum(1 for rd in result.routing_decisions if rd.model_tier == "opus"),
        sum(1 for rd in result.routing_decisions if rd.model_tier == "sonnet"),
        sum(1 for rd in result.routing_decisions if rd.model_tier == "haiku"),
    )

    # ── Phase 3: Dispatch ────────────────────────────────────────────
    if effective_dry_run:
        for rd in result.routing_decisions:
            log.info(
                "[DRY RUN] %s -> %s (%s)",
                rd.work_item.description[:60],
                rd.model_tier,
                rd.model_id,
            )
        return result

    # Real dispatch
    from .collector import ResultCollector
    from .dispatch import ModelSelection as DispatchModelSelection

    dispatcher = AgentDispatcher(dry_run=False)
    collector = ResultCollector()

    for rd in result.routing_decisions:
        try:
            dispatch_selection = DispatchModelSelection(
                model_tier=rd.model_tier,
                model_id=rd.model_id,
                reasoning=rd.reasoning,
                complexity_score=rd.complexity_score,
                confidence=rd.confidence,
            )
            dispatch_result = dispatcher.dispatch(rd.work_item, dispatch_selection)
            collector.collect(dispatch_result)

            result.items_dispatched += 1
            if dispatch_result.success:
                result.items_succeeded += 1
            else:
                result.items_failed += 1
                if dispatch_result.error:
                    result.errors.append(f"{rd.work_item.id[:8]}: {dispatch_result.error}")

            # Record outcome for future routing optimization
            from .core import _estimate_quality

            quality = _estimate_quality(dispatch_result)
            router.record_outcome(
                work_item_id=rd.work_item.id,
                model_tier=rd.model_tier,
                success=dispatch_result.success,
                quality_score=quality,
                task_type=rd.work_item.task_type,
            )

        except Exception as exc:
            log.error("Dispatch failed for %s: %s", rd.work_item.id, exc)
            result.items_failed += 1
            result.errors.append(f"{rd.work_item.id[:8]}: {exc}")

    # ── Phase 4: Collect & Persist ───────────────────────────────────
    if result.items_dispatched > 0:
        try:
            collector.persist()
            summary = collector.get_summary()
            log.info(
                "Pipeline complete: %d/%d succeeded, %d tokens",
                summary.succeeded,
                summary.total,
                summary.total_tokens,
            )
        except Exception as exc:
            log.error("Failed to persist results: %s", exc)
            result.errors.append(f"persist: {exc}")

    return result
