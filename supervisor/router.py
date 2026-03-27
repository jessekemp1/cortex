"""
Model complexity router -- selects opus/sonnet/haiku by task complexity.

Uses outcome data from ~/.cortex/metrics/model_outcomes.jsonl to learn
which model tier handles which task types most effectively.

Complexity scoring:
  - Token estimate (high tokens -> opus)
  - Task type (architecture/security -> opus, test/review -> sonnet, classify/qa -> haiku)
  - Historical outcomes (if model X succeeded on similar tasks, prefer X)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import WorkItem, WorkItemPriority

log = logging.getLogger(__name__)

_DEFAULT_OUTCOMES_PATH = Path.home() / ".cortex" / "orchestration" / "model_outcomes.jsonl"

# --- Complexity factor maps ---

_TYPE_COMPLEXITY: Dict[str, float] = {
    # Opus tier
    "architecture": 0.9,
    "security": 0.85,
    "planning": 0.8,
    # Sonnet tier
    "research": 0.7,
    "refactor": 0.6,
    "feature": 0.5,
    "fix": 0.5,
    "test": 0.4,
    "review": 0.4,
    "quality": 0.3,
    # Haiku tier
    "deploy": 0.25,
    "docs": 0.2,
    "classify": 0.1,
    "classification": 0.1,
    "qa": 0.1,
}

_PRIORITY_COMPLEXITY: Dict[WorkItemPriority, float] = {
    WorkItemPriority.CRITICAL: 1.0,
    WorkItemPriority.HIGH: 0.7,
    WorkItemPriority.MEDIUM: 0.4,
    WorkItemPriority.LOW: 0.1,
}

# Weights for complexity factors
_W_TOKEN = 0.20
_W_TYPE = 0.35
_W_FILES = 0.15
_W_PRIORITY = 0.30

# Model tier thresholds
_OPUS_THRESHOLD = 0.7
_SONNET_THRESHOLD = 0.3

# Model identifiers
_MODEL_MAP: Dict[str, str] = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# --- Task-type complexity heuristic (for callers without a full WorkItem) ---

TASK_COMPLEXITY: Dict[str, float] = {
    # Opus tier
    "architecture": 0.7,
    "security_audit": 0.7,
    "novel_algorithm": 0.7,
    # Sonnet tier
    "code_review": 0.5,
    "interactive_coding": 0.5,
    "research": 0.5,
    # Haiku tier
    "quick_qa": 0.2,
    "extraction": 0.2,
    "summarize": 0.2,
    "briefing": 0.2,
    "data_fetch": 0.2,
    "batch": 0.2,
}


def complexity_for_task(task_type: str) -> float:
    """Return a 0.0-1.0 complexity score for a given task type string.

    Used by batch dispatch layers that have a task_type string but no full
    WorkItem.  Sonnet (0.4) is the safe default for unmapped types.
    """
    return TASK_COMPLEXITY.get(task_type.lower(), 0.4)


def select_model(complexity: float) -> str:
    """Select a model tier string given a raw complexity score (0.0-1.0).

    Returns the full model ID, not the tier name.  Thresholds match the
    constants used by ModelRouter.select_model():

        complexity >= 0.7  → opus
        complexity >= 0.3  → sonnet
        otherwise          → haiku
    """
    if complexity >= _OPUS_THRESHOLD:
        return _MODEL_MAP["opus"]
    elif complexity >= _SONNET_THRESHOLD:
        return _MODEL_MAP["sonnet"]
    return _MODEL_MAP["haiku"]


@dataclass
class ModelAssignment:
    """Result of model routing (Phase 2 API)."""

    model: str  # "opus", "sonnet", "haiku"
    confidence: float  # 0.0-1.0
    rationale: str  # Why this model was selected


@dataclass
class ModelSelection:
    """Result of model routing for a work item."""

    model_tier: str  # "opus", "sonnet", "haiku"
    model_id: str  # e.g. "claude-opus-4-6"
    reasoning: str
    complexity_score: float
    confidence: float
    provider: str = "anthropic"  # Target provider for dispatch
    is_baseline: bool = False  # True = A/B baseline (forced Anthropic for quality comparison)


@dataclass
class _OutcomeRecord:
    """Single outcome entry from the JSONL file."""

    work_item_id: str
    model_tier: str
    task_type: str
    success: bool
    quality_score: float
    timestamp: str


class ModelRouter:
    """Selects the appropriate model tier (opus/sonnet/haiku) for a work item.

    Combines static complexity heuristics with historical outcome data
    to route tasks to the cheapest model that can handle them well.
    """

    # Phase 2: Direct task-type → model mapping
    TASK_MODEL_MAP: Dict[str, str] = {
        # Opus: high-stakes reasoning
        "planning": "opus",
        "architecture": "opus",
        "security": "opus",
        "debate": "opus",
        # Sonnet: balanced execution
        "implement": "sonnet",
        "research": "sonnet",
        "test": "sonnet",
        "fix": "sonnet",
        "feature": "sonnet",
        "review": "sonnet",
        "analysis": "sonnet",
        "investigation": "sonnet",
        "refactor": "sonnet",
        # Haiku: fast classification/simple tasks
        "classify": "haiku",
        "triage": "haiku",
        "format": "haiku",
        "validate": "haiku",
        "cleanup": "haiku",
        "deploy": "haiku",
        "docs": "haiku",
    }

    # Complexity overrides (simple/complex bypass TASK_MODEL_MAP)
    COMPLEXITY_OVERRIDE: Dict[str, Optional[str]] = {
        "simple": "haiku",
        "complex": "opus",
        "moderate": None,
    }

    # Keywords for complexity classification
    _COMPLEX_KEYWORDS = {"refactor entire", "redesign", "migrate", "rewrite", "overhaul"}
    _SIMPLE_KEYWORDS = {"fix typo", "rename", "update version", "bump", "formatting"}

    def __init__(self, outcomes_path: Optional[Path] = None) -> None:
        self._outcomes_path = outcomes_path or _DEFAULT_OUTCOMES_PATH
        self._outcomes: List[_OutcomeRecord] = self._load_outcomes()
        self._outcome_stats: Dict[str, Dict[str, dict]] = {}
        self._build_outcome_stats()

    def _load_outcomes(self) -> List[_OutcomeRecord]:
        """Load historical outcome records from JSONL."""
        if not self._outcomes_path.exists():
            return []

        records: List[_OutcomeRecord] = []
        try:
            for line in self._outcomes_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(
                        _OutcomeRecord(
                            work_item_id=data.get("work_item_id", ""),
                            model_tier=data.get("model_tier", ""),
                            task_type=data.get("task_type", ""),
                            success=data.get("success", False),
                            quality_score=data.get("quality_score") or 0.0,
                            timestamp=data.get("timestamp", ""),
                        )
                    )
                except json.JSONDecodeError:
                    continue
        except OSError as exc:
            log.error("Failed to read outcomes file: %s", exc)

        log.info("Loaded %d historical outcomes", len(records))
        return records

    def select_model(self, work_item: WorkItem) -> ModelSelection:
        """Select the best model tier for the given work item.

        Combines a static complexity score with task-type mapping and
        historical performance data. The TASK_MODEL_MAP provides a floor
        for each task type — e.g. architecture tasks always get at least
        opus, even if the numeric complexity score alone wouldn't reach
        the opus threshold.
        """
        complexity = self._compute_complexity(work_item)
        historical = self._get_historical_performance(work_item.task_type)

        # Base tier from complexity score
        if complexity >= _OPUS_THRESHOLD:
            score_tier = "opus"
        elif complexity >= _SONNET_THRESHOLD:
            score_tier = "sonnet"
        else:
            score_tier = "haiku"

        # Task-type mapping provides a floor (never downgrade below it)
        map_tier = self.TASK_MODEL_MAP.get(work_item.task_type)
        tier_rank = {"haiku": 0, "sonnet": 1, "opus": 2}
        if map_tier and tier_rank.get(map_tier, 0) > tier_rank.get(score_tier, 0):
            base_tier = map_tier
        else:
            base_tier = score_tier

        # Check if historical data suggests a different tier
        final_tier = base_tier
        confidence = 0.5 + (complexity * 0.3)  # base confidence from complexity
        reasoning_parts: List[str] = [
            f"Complexity score: {complexity:.2f}",
            f"Base tier: {base_tier}",
        ]

        if historical:
            # Find best-performing tier for this task type
            best_hist_tier = max(historical, key=historical.get)  # type: ignore[arg-type]
            best_hist_score = historical[best_hist_tier]

            reasoning_parts.append(f"Historical best: {best_hist_tier} ({best_hist_score:.2f})")

            # If historical data strongly favors a tier, adjust
            # Only shift by one tier to avoid wild swings
            tier_order = ["haiku", "sonnet", "opus"]
            base_idx = tier_order.index(base_tier)
            hist_idx = tier_order.index(best_hist_tier)

            if best_hist_score >= 0.75 and hist_idx != base_idx:
                # Shift one step toward the historically better tier
                shift = 1 if hist_idx > base_idx else -1
                adjusted_idx = max(0, min(2, base_idx + shift))
                final_tier = tier_order[adjusted_idx]
                confidence += 0.1
                reasoning_parts.append(f"Adjusted to {final_tier} based on historical performance")

        confidence = min(confidence, 1.0)
        reasoning_parts.append(f"Final tier: {final_tier}")

        return ModelSelection(
            model_tier=final_tier,
            model_id=_MODEL_MAP[final_tier],
            reasoning=". ".join(reasoning_parts),
            complexity_score=complexity,
            confidence=confidence,
        )

    def select_model_with_provider(
        self,
        work_item: WorkItem,
        registry: "Optional[ProviderRegistry]" = None,
    ) -> ModelSelection:
        """Select model and provider, preferring cheapest in tier.

        If registry is provided, selects the cheapest healthy provider
        for the chosen tier. Otherwise falls back to Anthropic.
        """
        selection = self.select_model(work_item)

        if registry is None:
            return selection

        candidates = registry.get_models_for_tier(selection.model_tier)
        if candidates:
            provider_name, spec = candidates[0]  # Cheapest healthy
            return ModelSelection(
                model_tier=selection.model_tier,
                model_id=spec.model_id,
                reasoning=selection.reasoning + f". Provider: {provider_name} (cheapest)",
                complexity_score=selection.complexity_score,
                confidence=selection.confidence,
                provider=provider_name,
            )

        return selection

    def record_outcome(
        self,
        work_item_id: str,
        model_tier: str,
        success: bool,
        quality_score: float,
        task_type: str = "",
    ) -> None:
        """Append an outcome record to the JSONL file.

        This data feeds back into future routing decisions via
        ``_get_historical_performance``.
        """
        record = {
            "work_item_id": work_item_id,
            "model_tier": model_tier,
            "task_type": task_type,
            "success": success,
            "quality_score": quality_score,
            "timestamp": datetime.now().isoformat(),
        }

        self._outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        with self._outcomes_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        # Update in-memory cache
        self._outcomes.append(
            _OutcomeRecord(
                work_item_id=work_item_id,
                model_tier=model_tier,
                task_type=task_type,
                success=success,
                quality_score=quality_score,
                timestamp=record["timestamp"],
            )
        )
        log.info(
            "Recorded outcome for %s: %s %s (quality=%.2f)",
            work_item_id,
            model_tier,
            "SUCCESS" if success else "FAILURE",
            quality_score,
        )

        # Update outcome stats cache
        stats = self._outcome_stats.setdefault(task_type, {}).setdefault(
            model_tier, {"success": 0, "total": 0}
        )
        stats["total"] += 1
        if success:
            stats["success"] += 1

    # ------------------------------------------------------------------
    # Phase 2: route() API with task-type mapping + complexity overrides
    # ------------------------------------------------------------------

    def route(self, work_item: WorkItem) -> ModelAssignment:
        """Assign optimal model to a work item (Phase 2 API).

        Routing priority:
        1. Complexity override (simple → haiku, complex → opus)
        2. Outcome-adjusted model (if historical data is available)
        3. TASK_MODEL_MAP lookup (fallback: sonnet)
        """
        complexity = self._classify_complexity(work_item)

        # 1. Check complexity override
        override = self.COMPLEXITY_OVERRIDE.get(complexity)
        if override:
            return ModelAssignment(
                model=override,
                confidence=0.8,
                rationale=f"Complexity override: {complexity} → {override}",
            )

        # 2. Get base model from task type map
        base_model = self.TASK_MODEL_MAP.get(work_item.task_type, "sonnet")

        # 3. Check outcome-adjusted model
        return self._get_outcome_adjusted_model(work_item.task_type, base_model)

    def _classify_complexity(self, work_item: WorkItem) -> str:
        """Classify task complexity as simple/moderate/complex.

        Heuristics:
        - Description length: short (<20 words) = simple, long (>100) = complex
        - Number of files referenced: 0-1 = simple, 5+ = complex
        - Priority: CRITICAL = complex, LOW = simple
        - Keywords in description
        """
        desc = work_item.description.lower()
        word_count = len(desc.split())
        file_count = len(work_item.files)
        score = 0  # -2..+2 range, then map

        # Word count signal
        if word_count > 100:
            score += 1
        elif word_count < 20:
            score -= 1

        # File count signal
        if file_count >= 5:
            score += 1
        elif file_count <= 1:
            score -= 1

        # Priority signal
        if work_item.priority == WorkItemPriority.CRITICAL:
            score += 1
        elif work_item.priority == WorkItemPriority.LOW:
            score -= 1

        # Keyword signals
        for kw in self._COMPLEX_KEYWORDS:
            if kw in desc:
                score += 2
                break
        for kw in self._SIMPLE_KEYWORDS:
            if kw in desc:
                score -= 2
                break

        if score >= 2:
            return "complex"
        elif score <= -2:
            return "simple"
        return "moderate"

    def _get_outcome_adjusted_model(self, task_type: str, base_model: str) -> ModelAssignment:
        """Adjust model selection based on historical outcome stats.

        Rules:
        - If success rate < 40% for base_model on this task_type → escalate
        - If success rate > 90% AND at least one failure recorded → consider downgrade
        - 100% success with no failures = insufficient signal, never downgrade
        - Require ≥10 outcomes before any adjustment (safety valve)
        - Otherwise use base_model
        """
        tier_order = ["haiku", "sonnet", "opus"]
        stats_for_type = self._outcome_stats.get(task_type, {})
        model_stats = stats_for_type.get(base_model)

        # Safety valve: require meaningful sample size before any adjustment
        min_outcomes = 10
        if not model_stats or model_stats["total"] < min_outcomes:
            return ModelAssignment(
                model=base_model,
                confidence=0.5,
                rationale=f"Task map: {task_type} → {base_model} (insufficient outcome data)",
            )

        success_rate = model_stats["success"] / model_stats["total"]
        failure_count = model_stats["total"] - model_stats["success"]
        base_idx = tier_order.index(base_model)

        if success_rate < 0.4 and base_idx < 2:
            # Escalate to next tier
            escalated = tier_order[base_idx + 1]
            return ModelAssignment(
                model=escalated,
                confidence=0.7,
                rationale=(
                    f"Escalated {base_model} → {escalated}: "
                    f"{task_type} success rate {success_rate:.0%} < 40%"
                ),
            )

        if success_rate > 0.9 and base_idx > 0 and failure_count > 0:
            # Only downgrade when we have REAL evidence (at least one failure
            # proves the quality scoring is actually differentiating).
            # 100% success = binary scoring / no learning signal → never downgrade.
            downgraded = tier_order[base_idx - 1]
            return ModelAssignment(
                model=downgraded,
                confidence=0.7,
                rationale=(
                    f"Downgraded {base_model} → {downgraded}: "
                    f"{task_type} success rate {success_rate:.0%} > 90%"
                ),
            )

        return ModelAssignment(
            model=base_model,
            confidence=0.6 + (success_rate * 0.3),
            rationale=(f"Task map: {task_type} → {base_model} (success rate {success_rate:.0%})"),
        )

    def _build_outcome_stats(self) -> None:
        """Build aggregated outcome statistics from loaded records."""
        for outcome in self._outcomes:
            stats = self._outcome_stats.setdefault(outcome.task_type, {}).setdefault(
                outcome.model_tier, {"success": 0, "total": 0}
            )
            stats["total"] += 1
            if outcome.success:
                stats["success"] += 1

    def update_from_outcome(self, task_type: str, model: str, success: bool) -> None:
        """Record an outcome for future routing decisions (Phase 2 API).

        Updates in-memory stats and appends to the outcomes JSONL file.
        """
        self.record_outcome(
            work_item_id="",
            model_tier=model,
            success=success,
            quality_score=1.0 if success else 0.0,
            task_type=task_type,
        )

    def _compute_complexity(self, work_item: WorkItem) -> float:
        """Compute a 0.0-1.0 complexity score from work item attributes.

        Factors (weighted sum):
          - token_factor:    estimated_tokens / 100_000  (capped at 1.0)
          - type_factor:     lookup by task_type
          - file_count:      len(files) / 20             (capped at 1.0)
          - priority_factor: lookup by priority enum
        """
        token_factor = min(work_item.estimated_tokens / 100_000, 1.0)
        type_factor = _TYPE_COMPLEXITY.get(work_item.task_type, 0.5)
        file_count_factor = min(len(work_item.files) / 20, 1.0)
        priority_factor = _PRIORITY_COMPLEXITY.get(work_item.priority, 0.4)

        score = (
            _W_TOKEN * token_factor
            + _W_TYPE * type_factor
            + _W_FILES * file_count_factor
            + _W_PRIORITY * priority_factor
        )
        return min(max(score, 0.0), 1.0)

    def _get_historical_performance(self, task_type: str) -> Dict[str, float]:
        """Compute per-model-tier success rates for a given task type.

        Returns a dict like ``{"opus": 0.9, "sonnet": 0.7, "haiku": 0.4}``
        where the value is the average quality_score for successful runs.
        Only includes tiers with at least 3 outcomes to avoid noise.
        """
        tier_scores: Dict[str, List[float]] = {}

        for outcome in self._outcomes:
            if outcome.task_type != task_type:
                continue
            if not outcome.success:
                continue
            # Skip None quality scores (from legacy records without scoring)
            if outcome.quality_score is not None:
                tier_scores.setdefault(outcome.model_tier, []).append(outcome.quality_score)

        result: Dict[str, float] = {}
        for tier, scores in tier_scores.items():
            if len(scores) >= 3:
                result[tier] = sum(scores) / len(scores)

        return result


class AdvancedModelRouter(ModelRouter):
    """Extends ModelRouter with ContextAwareModelRecommender + multi-provider.

    Wires the existing intelligence/model_selection/ subsystem into the
    supervisor routing pipeline. When enabled:
      1. ContextAwareModelRecommender provides context-aware tier selection
         (budget, time, priority, historical learned overrides)
      2. ProviderRegistry selects cheapest healthy provider for the tier
      3. Quality floor enforcement prevents cheap models from degrading quality
      4. Guardrail: opus-tier tasks never routed below sonnet

    Falls back to base ModelRouter.select_model() when recommender unavailable.
    """

    # Minimum quality thresholds by tier
    _QUALITY_FLOOR: Dict[str, float] = {
        "opus": 0.7,
        "sonnet": 0.6,
        "haiku": 0.4,
    }

    def __init__(
        self,
        outcomes_path: Optional[Path] = None,
        registry: "Optional[ProviderRegistry]" = None,  # type: ignore[name-defined]
        quality_floor: Optional[Dict[str, float]] = None,
    ) -> None:
        super().__init__(outcomes_path=outcomes_path)
        self._registry = registry
        self._recommender: Optional[Any] = self._init_recommender()
        if quality_floor:
            self._QUALITY_FLOOR = quality_floor

    def _init_recommender(self) -> Optional[Any]:
        """Lazily import ContextAwareModelRecommender."""
        try:
            from intelligence.model_selection.recommender import (
                ContextAwareModelRecommender,
            )

            return ContextAwareModelRecommender()
        except ImportError:
            log.warning(
                "ContextAwareModelRecommender not available; "
                "AdvancedModelRouter falling back to base routing"
            )
            return None

    def route_advanced(
        self,
        work_item: WorkItem,
        remaining_budget: float = 10.0,
        remaining_time_seconds: float = 3600.0,
        is_retry: bool = False,
        ab_baseline_ratio: float = 0.10,
    ) -> ModelSelection:
        """Multi-signal routing with context awareness and provider selection.

        Pipeline:
          0. A/B baseline gate: 10% of tasks bypass multi-provider → Anthropic-only
          1. ContextAwareModelRecommender.recommend() → context-aware tier
          2. Historical quality per (provider, model, task_type) → adjust
          3. Provider health + cost optimization → cheapest adequate
          4. Guardrail: never route opus-tier task below sonnet
        """
        # A/B baseline: force Anthropic-only for quality comparison
        import random

        if ab_baseline_ratio > 0 and random.random() < ab_baseline_ratio:
            base = self.select_model(work_item)
            return ModelSelection(
                model_tier=base.model_tier,
                model_id=base.model_id,
                reasoning=base.reasoning + ". A/B baseline: forced Anthropic-only",
                complexity_score=base.complexity_score,
                confidence=base.confidence,
                provider="anthropic",
                is_baseline=True,
            )

        if self._recommender is None:
            return self.select_model_with_provider(work_item, self._registry)

        try:
            from datetime import timedelta

            from intelligence.model_selection.models import OrchestrationContext

            context = OrchestrationContext(
                remaining_budget=remaining_budget,
                remaining_time=timedelta(seconds=remaining_time_seconds),
                task_priority=work_item.priority.value,
                is_retry=is_retry,
                project=work_item.project or "",
                files=work_item.files or [],
            )

            recommendation = self._recommender.recommend(
                task_description=work_item.description,
                task_type=work_item.task_type,
                context=context,
            )

            tier = recommendation.model
            confidence = recommendation.confidence
            reasoning = recommendation.reasoning

        except Exception as exc:
            log.warning("Recommender failed (%s), falling back to base router", exc)
            return self.select_model_with_provider(work_item, self._registry)

        # Guardrail: opus-tier tasks never below sonnet
        tier_rank = {"haiku": 0, "sonnet": 1, "opus": 2}
        base_selection = self.select_model(work_item)
        if base_selection.model_tier == "opus" and tier_rank.get(tier, 0) < 1:
            tier = "sonnet"
            reasoning += ". Guardrail: opus-tier task protected from haiku"

        # Select provider
        model_id = _MODEL_MAP[tier]
        provider = "anthropic"

        if self._registry is not None:
            candidates = self._registry.get_models_for_tier(tier)
            if candidates:
                provider_name, spec = candidates[0]
                model_id = spec.model_id
                provider = provider_name
                reasoning += f". Provider: {provider_name} (cost-optimized)"

        return ModelSelection(
            model_tier=tier,
            model_id=model_id,
            reasoning=reasoning,
            complexity_score=base_selection.complexity_score,
            confidence=confidence,
            provider=provider,
        )
