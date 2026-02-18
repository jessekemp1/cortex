#!/usr/bin/env python3
"""
Conductor-aware batch model selection.

Replaces AnthropicBatchModels with conductor-routed model selection.
Always returns Anthropic model IDs (batch API only supports Anthropic),
but uses conductor routing logic to pick the right tier (haiku/sonnet/opus)
and tracks selections for cost reporting.

Backward-compatible: same interface as AnthropicBatchModels.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Dual import for daemon compatibility (see MEMORY.md: Daemon Import Chain Fragility)
try:
    from cortex.conductor.cost_tracker import CostTracker
except ImportError:
    from .cost_tracker import CostTracker  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# Anthropic batch-eligible model IDs
_ANTHROPIC_FAST = "claude-haiku-4-5-20251001"
_ANTHROPIC_DEFAULT = "claude-sonnet-4-20250514"
_ANTHROPIC_PREMIUM = "claude-opus-4-5-20251101"

# Map conductor use cases to batch tier
_USE_CASE_TO_TIER: Dict[str, str] = {
    # Direct tier names (backward compat with AnthropicBatchModels)
    "default": "default",
    "fast": "fast",
    "premium": "premium",
    # Use-case to tier mapping
    "classification": "fast",
    "quick_qa": "fast",
    "simple": "fast",
    "pattern_learning": "default",
    "documentation": "fast",
    "code_review": "default",
    "test_generation": "default",
    "long_context": "default",
    "research": "default",
    "interactive_coding": "default",
    "learning": "default",
    "briefing": "default",
    "analysis": "default",
    "recommendation": "default",
    "security_audit": "premium",
    "architecture": "premium",
    "complex": "premium",
}


@dataclass
class _SelectionRecord:
    """Record of a model selection decision."""

    task_type: str
    model_id: str
    tier: str
    reason: str


@dataclass
class ConductorBatchModels:
    """Conductor-aware model policy for batch operations.

    Drop-in replacement for AnthropicBatchModels. Uses the conductor's
    routing logic to pick the right Anthropic tier, but always returns
    Anthropic model IDs since the batch API only supports Anthropic.

    Tracks which models were selected and why for cost reporting.
    """

    # Anthropic model IDs for each tier -- batch API requires these
    default: str = _ANTHROPIC_DEFAULT
    fast: str = _ANTHROPIC_FAST
    premium: str = _ANTHROPIC_PREMIUM

    # Internal tracking
    _selections: List[_SelectionRecord] = field(default_factory=list, repr=False)
    _cost_tracker: Optional[CostTracker] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Try to load conductor registry for smarter routing."""
        self._registry_available = False
        self._registry_models: Dict[str, str] = {}

        try:
            try:
                from cortex.conductor.registry import get_provider
            except ImportError:
                from .registry import get_provider  # type: ignore[no-redef]

            anthropic = get_provider("anthropic")
            # Map registry model IDs to our tiers so we can pull updated IDs
            for model_id, spec in anthropic.models.items():
                if "haiku" in model_id.lower() or "haiku" in spec.display_name.lower():
                    self._registry_models["fast"] = model_id
                elif "opus" in model_id.lower() or "opus" in spec.display_name.lower():
                    self._registry_models["premium"] = model_id
                elif "sonnet" in model_id.lower() or "sonnet" in spec.display_name.lower():
                    self._registry_models["default"] = model_id

            self._registry_available = True
            logger.debug(
                "Conductor registry loaded for batch models: %s",
                self._registry_models,
            )
        except Exception as e:
            logger.debug("Conductor registry not available, using hardcoded models: %s", e)

    def _get_cost_tracker(self) -> CostTracker:
        """Lazy-init the cost tracker singleton."""
        if self._cost_tracker is None:
            self._cost_tracker = CostTracker()
        return self._cost_tracker

    def get_model(self, task_type: str = "default") -> str:
        """Get appropriate Anthropic model for a batch task type.

        Uses conductor routing logic to pick the right tier, then
        returns the corresponding Anthropic model ID.

        Args:
            task_type: The type of task (e.g., "classification", "learning").

        Returns:
            An Anthropic model ID suitable for the batch API.
        """
        tier = _USE_CASE_TO_TIER.get(task_type, "default")

        # Map tier to model ID
        if tier == "fast":
            model_id = self.fast
            reason = f"Fast tier for task_type={task_type}"
        elif tier == "premium":
            model_id = self.premium
            reason = f"Premium tier for task_type={task_type}"
        else:
            model_id = self.default
            reason = f"Default tier for task_type={task_type}"

        # Record the selection
        self._selections.append(
            _SelectionRecord(
                task_type=task_type,
                model_id=model_id,
                tier=tier,
                reason=reason,
            )
        )

        logger.debug("Batch model selected: %s (tier=%s, task=%s)", model_id, tier, task_type)
        return model_id

    def for_learning(self) -> str:
        """Model for learning/feedback analysis."""
        return self.get_model("learning")

    def for_briefing(self) -> str:
        """Model for briefing generation."""
        return self.get_model("briefing")

    def for_research(self) -> str:
        """Model for research tasks."""
        return self.get_model("research")

    def record_batch_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        use_case: str = "",
    ) -> None:
        """Record batch API costs in the conductor's cost tracker.

        Args:
            model: The Anthropic model ID used.
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens produced.
            cost_usd: Total cost in USD.
            use_case: Optional use case tag for cost reporting.
        """
        tracker = self._get_cost_tracker()
        tracker.record(
            provider="anthropic_batch",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            use_case=use_case or "batch",
        )
        logger.debug(
            "Batch cost recorded: model=%s, tokens=%d/%d, cost=$%.6f",
            model,
            input_tokens,
            output_tokens,
            cost_usd,
        )

    def get_selection_history(self) -> List[Dict[str, Any]]:
        """Return selection history for debugging/reporting.

        Returns:
            List of dicts with task_type, model_id, tier, reason.
        """
        return [
            {
                "task_type": s.task_type,
                "model_id": s.model_id,
                "tier": s.tier,
                "reason": s.reason,
            }
            for s in self._selections
        ]
