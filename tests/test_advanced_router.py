"""Tests for AdvancedModelRouter (Phase 2 wiring).

Tests:
  - Falls back to base ModelRouter when recommender unavailable
  - Wires ContextAwareModelRecommender when available
  - Opus guardrail: opus-tier tasks never below sonnet
  - Provider selection integration
  - Context parameters (budget, time, retry) passed through
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.supervisor.models import WorkItemPriority
from cortex.supervisor.router import AdvancedModelRouter, ModelRouter, ModelSelection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def router(tmp_path: Path) -> AdvancedModelRouter:
    """Router without recommender (import will fail in test env)."""
    return AdvancedModelRouter(outcomes_path=tmp_path / "outcomes.jsonl")


def _make_work_item(**overrides):
    """Create a mock WorkItem for routing."""
    from cortex.supervisor.models import WorkItem, WorkItemPriority

    defaults = {
        "id": "test-item",
        "source": "test",
        "task_type": "architecture",
        "description": "Design a new authentication system with JWT tokens",
        "project": "cortex",
        "files": ["auth.py", "middleware.py"],
        "priority": WorkItemPriority.HIGH,
        "estimated_tokens": 50000,
    }
    defaults.update(overrides)
    return WorkItem(**defaults)


# ---------------------------------------------------------------------------
# Tests: Inheritance
# ---------------------------------------------------------------------------


class TestAdvancedRouterInheritance:
    def test_is_model_router(self, router: AdvancedModelRouter) -> None:
        assert isinstance(router, ModelRouter)

    def test_select_model_still_works(self, router: AdvancedModelRouter) -> None:
        """Base select_model() must still work (backward compat)."""
        item = _make_work_item()
        selection = router.select_model(item)
        assert selection.model_tier in ("haiku", "sonnet", "opus")
        assert selection.model_id
        assert selection.confidence > 0

    def test_select_model_with_provider_still_works(self, router: AdvancedModelRouter) -> None:
        item = _make_work_item()
        selection = router.select_model_with_provider(item)
        assert selection.provider == "anthropic"

    def test_route_still_works(self, router: AdvancedModelRouter) -> None:
        item = _make_work_item()
        assignment = router.route(item)
        assert assignment.model in ("haiku", "sonnet", "opus")


# ---------------------------------------------------------------------------
# Tests: Fallback behavior (no recommender)
# ---------------------------------------------------------------------------


class TestAdvancedRouterFallback:
    def test_route_advanced_without_recommender(self, router: AdvancedModelRouter) -> None:
        """When recommender is None, falls back to base routing."""
        router._recommender = None
        item = _make_work_item()
        selection = router.route_advanced(item)
        assert isinstance(selection, ModelSelection)
        assert selection.model_tier in ("haiku", "sonnet", "opus")

    def test_route_advanced_with_failed_recommender(self, router: AdvancedModelRouter) -> None:
        """When recommender.recommend() raises, falls back gracefully."""
        mock_rec = MagicMock()
        mock_rec.recommend.side_effect = RuntimeError("broken")
        router._recommender = mock_rec

        item = _make_work_item()
        selection = router.route_advanced(item)
        assert isinstance(selection, ModelSelection)
        assert selection.model_tier in ("haiku", "sonnet", "opus")


# ---------------------------------------------------------------------------
# Tests: With mocked recommender
# ---------------------------------------------------------------------------


class TestAdvancedRouterWithRecommender:
    def _mock_recommender(self, model="sonnet", confidence=0.8):
        """Create a mock ContextAwareModelRecommender."""
        mock = MagicMock()
        recommendation = MagicMock()
        recommendation.model = model
        recommendation.confidence = confidence
        recommendation.reasoning = f"Test recommendation: {model}"
        mock.recommend.return_value = recommendation
        return mock

    def test_uses_recommender_tier(self, router: AdvancedModelRouter) -> None:
        router._recommender = self._mock_recommender(model="opus", confidence=0.9)
        item = _make_work_item()
        selection = router.route_advanced(item, ab_baseline_ratio=0)
        assert selection.model_tier == "opus"
        assert selection.confidence == 0.9

    def test_sonnet_recommendation(self, router: AdvancedModelRouter) -> None:
        router._recommender = self._mock_recommender(model="sonnet")
        item = _make_work_item(task_type="test")
        selection = router.route_advanced(item, ab_baseline_ratio=0)
        assert selection.model_tier == "sonnet"

    def test_haiku_recommendation(self, router: AdvancedModelRouter) -> None:
        router._recommender = self._mock_recommender(model="haiku")
        item = _make_work_item(
            task_type="classify",
            description="List all TODO comments",
            estimated_tokens=1000,
            priority=WorkItemPriority.LOW,
        )
        selection = router.route_advanced(item, ab_baseline_ratio=0)
        assert selection.model_tier == "haiku"

    def test_recommender_receives_context(self, router: AdvancedModelRouter) -> None:
        mock = self._mock_recommender()
        router._recommender = mock
        item = _make_work_item()

        router.route_advanced(
            item,
            remaining_budget=2.5,
            remaining_time_seconds=900.0,
            is_retry=True,
            ab_baseline_ratio=0,
        )

        mock.recommend.assert_called_once()
        call_kwargs = mock.recommend.call_args
        assert call_kwargs.kwargs["task_description"] == item.description
        assert call_kwargs.kwargs["task_type"] == item.task_type


# ---------------------------------------------------------------------------
# Tests: Opus guardrail
# ---------------------------------------------------------------------------


class TestOpusGuardrail:
    def test_opus_task_not_downgraded_to_haiku(self, router: AdvancedModelRouter) -> None:
        """Opus-tier tasks (architecture) must never route below sonnet."""
        router._recommender = MagicMock()
        rec = MagicMock()
        rec.model = "haiku"  # Recommender says haiku
        rec.confidence = 0.8
        rec.reasoning = "Budget constraint"
        router._recommender.recommend.return_value = rec

        item = _make_work_item(task_type="architecture")
        selection = router.route_advanced(item, ab_baseline_ratio=0)

        # Base router would select opus for architecture
        # Guardrail should prevent haiku, upgrade to at least sonnet
        assert selection.model_tier in ("sonnet", "opus")
        assert "Guardrail" in selection.reasoning

    def test_non_opus_task_can_be_haiku(self, router: AdvancedModelRouter) -> None:
        """Non-opus tasks can be routed to haiku without guardrail."""
        router._recommender = MagicMock()
        rec = MagicMock()
        rec.model = "haiku"
        rec.confidence = 0.8
        rec.reasoning = "Simple classification"
        router._recommender.recommend.return_value = rec

        item = _make_work_item(task_type="classify")
        selection = router.route_advanced(item, ab_baseline_ratio=0)
        assert selection.model_tier == "haiku"


# ---------------------------------------------------------------------------
# Tests: Provider integration
# ---------------------------------------------------------------------------


class TestProviderIntegration:
    def test_with_registry(self, router: AdvancedModelRouter) -> None:
        """When registry provided, selects cheapest provider."""
        from cortex.supervisor.providers import ModelSpec

        mock_registry = MagicMock()
        mock_spec = ModelSpec(
            model_id="deepseek-chat",
            tier="sonnet",
            cost_input_per_1m=0.14,
            cost_output_per_1m=0.28,
        )
        mock_registry.get_models_for_tier.return_value = [("deepseek", mock_spec)]
        router._registry = mock_registry
        router._recommender = MagicMock()
        rec = MagicMock()
        rec.model = "sonnet"
        rec.confidence = 0.85
        rec.reasoning = "Standard routing"
        router._recommender.recommend.return_value = rec

        item = _make_work_item(task_type="research")
        selection = router.route_advanced(item, ab_baseline_ratio=0)

        assert selection.provider == "deepseek"
        assert selection.model_id == "deepseek-chat"
        assert "cost-optimized" in selection.reasoning

    def test_without_registry_uses_anthropic(self, router: AdvancedModelRouter) -> None:
        router._recommender = MagicMock()
        rec = MagicMock()
        rec.model = "sonnet"
        rec.confidence = 0.8
        rec.reasoning = "Standard"
        router._recommender.recommend.return_value = rec

        item = _make_work_item(task_type="test")
        selection = router.route_advanced(item, ab_baseline_ratio=0)
        assert selection.provider == "anthropic"


# ---------------------------------------------------------------------------
# Tests: Quality floor config
# ---------------------------------------------------------------------------


class TestQualityFloor:
    def test_default_floors(self) -> None:
        router = AdvancedModelRouter()
        assert router._QUALITY_FLOOR["opus"] == 0.7
        assert router._QUALITY_FLOOR["sonnet"] == 0.6
        assert router._QUALITY_FLOOR["haiku"] == 0.4

    def test_custom_floors(self) -> None:
        router = AdvancedModelRouter(quality_floor={"opus": 0.8, "sonnet": 0.5, "haiku": 0.3})
        assert router._QUALITY_FLOOR["opus"] == 0.8
        assert router._QUALITY_FLOOR["sonnet"] == 0.5


# ---------------------------------------------------------------------------
# Tests: A/B Baseline
# ---------------------------------------------------------------------------


class TestABBaseline:
    """10% of tasks should route Anthropic-only for quality comparison."""

    def test_baseline_ratio_zero_never_triggers(self, router: AdvancedModelRouter) -> None:
        """ab_baseline_ratio=0 means no baseline tasks."""
        item = _make_work_item(task_type="research")
        for _ in range(50):
            selection = router.route_advanced(item, ab_baseline_ratio=0.0)
            assert not selection.is_baseline

    def test_baseline_ratio_one_always_triggers(self, router: AdvancedModelRouter) -> None:
        """ab_baseline_ratio=1.0 means all tasks are baseline."""
        item = _make_work_item(task_type="research")
        for _ in range(20):
            selection = router.route_advanced(item, ab_baseline_ratio=1.0)
            assert selection.is_baseline
            assert selection.provider == "anthropic"
            assert "A/B baseline" in selection.reasoning

    def test_baseline_uses_anthropic_model_ids(self, router: AdvancedModelRouter) -> None:
        """Baseline tasks must use Claude model IDs."""
        item = _make_work_item(task_type="fix")
        selection = router.route_advanced(item, ab_baseline_ratio=1.0)
        assert selection.model_id.startswith("claude-")

    def test_baseline_preserves_tier(self, router: AdvancedModelRouter) -> None:
        """Baseline should pick the same tier as normal routing."""
        # architecture task → opus tier
        item = _make_work_item(task_type="architecture", estimated_tokens=50000)
        selection = router.route_advanced(item, ab_baseline_ratio=1.0)
        assert selection.model_tier == "opus"
        assert selection.is_baseline

    def test_model_selection_has_is_baseline_field(self) -> None:
        """ModelSelection dataclass includes is_baseline with default False."""
        s = ModelSelection(
            model_tier="sonnet",
            model_id="claude-sonnet-4-6",
            reasoning="test",
            complexity_score=0.5,
            confidence=0.8,
        )
        assert s.is_baseline is False

    def test_baseline_tagged_in_model_selection(self) -> None:
        """Explicitly setting is_baseline=True works."""
        s = ModelSelection(
            model_tier="sonnet",
            model_id="claude-sonnet-4-6",
            reasoning="test",
            complexity_score=0.5,
            confidence=0.8,
            is_baseline=True,
        )
        assert s.is_baseline is True
