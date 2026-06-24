#!/usr/bin/env python3
"""
Integration tests for the Cortex Conductor.

Covers:
- ConductorBatchModels compatibility with AnthropicBatchModels
- End-to-end cost tracking through the call() pipeline
- Batch + interactive cost unification
- Import fallback behavior
- route() -> call() delegation flow
- Fallback provider on primary failure
- Cost tracking on fallback path
"""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.conductor import (
    RoutingDecision,
    async_call,
    call,
    get_budget_remaining,
    get_costs,
    get_savings,
    route,
)
from cortex.conductor.cost_tracker import CostTracker
from cortex.conductor.providers.base import (
    CompletionResponse,
    ProviderError,
)

# Try to import ConductorBatchModels; fall back to AnthropicBatchModels
# if batch_models.py doesn't exist yet.
try:
    from cortex.conductor.batch_models import ConductorBatchModels
except ImportError:
    ConductorBatchModels = None  # type: ignore[assignment,misc]

from cortex.batch.model_policy import AnthropicBatchModels


# Valid Anthropic model ID pattern: must be a string containing "claude" or be
# a recognized Anthropic model family prefix.
ANTHROPIC_MODEL_PATTERN = re.compile(r"^claude-")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tracker(tmp_path: Path) -> CostTracker:
    """Create a CostTracker with temp directory for test isolation."""
    return CostTracker(state_dir=tmp_path, daily_budget=20.0)


@pytest.fixture
def mock_provider():
    """Create a mock provider that returns a valid CompletionResponse."""
    provider = MagicMock()
    provider.complete.return_value = CompletionResponse(
        content="Test response",
        model="llama-3.1-8b-instant",
        provider="groq",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost_usd=0.000005,
        latency_ms=150.0,
    )
    return provider


@pytest.fixture
def mock_fallback_provider():
    """Create a mock fallback provider that returns a valid response."""
    provider = MagicMock()
    provider.complete.return_value = CompletionResponse(
        content="Fallback response",
        model="claude-sonnet-4-20250514",
        provider="anthropic",
        input_tokens=100,
        output_tokens=60,
        total_tokens=160,
        cost_usd=0.001200,
        latency_ms=2500.0,
    )
    return provider


@pytest.fixture
def failing_provider():
    """Create a mock provider that raises ProviderError."""
    provider = MagicMock()
    provider.complete.side_effect = ProviderError("groq", 500, "Internal server error")
    return provider


# ---------------------------------------------------------------------------
# 1. ConductorBatchModels compatibility
# ---------------------------------------------------------------------------


class TestConductorBatchModelsCompatibility:
    """Test that ConductorBatchModels is a drop-in replacement for AnthropicBatchModels."""

    def _get_batch_models_class(self):
        """Return ConductorBatchModels if available, else AnthropicBatchModels."""
        if ConductorBatchModels is not None:
            return ConductorBatchModels
        # Fall back to AnthropicBatchModels to validate the interface contract
        return AnthropicBatchModels

    def test_batch_models_has_default(self):
        """ConductorBatchModels exposes .default like AnthropicBatchModels."""
        cls = self._get_batch_models_class()
        models = cls()
        assert hasattr(models, "default")
        assert isinstance(models.default, str)
        assert len(models.default) > 0

    def test_batch_models_has_fast(self):
        """ConductorBatchModels exposes .fast attribute."""
        cls = self._get_batch_models_class()
        models = cls()
        assert hasattr(models, "fast")
        assert isinstance(models.fast, str)
        assert len(models.fast) > 0

    def test_batch_models_has_premium(self):
        """ConductorBatchModels exposes .premium attribute."""
        cls = self._get_batch_models_class()
        models = cls()
        assert hasattr(models, "premium")
        assert isinstance(models.premium, str)
        assert len(models.premium) > 0

    def test_batch_models_get_model(self):
        """get_model() returns valid model IDs for all task types."""
        cls = self._get_batch_models_class()
        models = cls()
        task_types = [
            "default",
            "fast",
            "classification",
            "simple",
            "premium",
            "complex",
            "analysis",
            "recommendation",
            "learning",
            "briefing",
        ]
        for task_type in task_types:
            model_id = models.get_model(task_type)
            assert isinstance(model_id, str), f"get_model('{task_type}') should return str"
            assert len(model_id) > 0, f"get_model('{task_type}') should return non-empty string"

    def test_batch_models_for_learning(self):
        """for_learning() returns a model ID string."""
        cls = self._get_batch_models_class()
        models = cls()
        result = models.for_learning()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_batch_models_for_briefing(self):
        """for_briefing() returns a model ID string."""
        cls = self._get_batch_models_class()
        models = cls()
        result = models.for_briefing()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_batch_models_for_research(self):
        """for_research() returns a model ID string."""
        cls = self._get_batch_models_class()
        models = cls()
        result = models.for_research()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_batch_models_returns_anthropic_models(self):
        """All returned model IDs are valid Anthropic models (batch API requirement).

        Anthropic batch API only accepts Anthropic model IDs, so every model
        returned by the batch models class must start with 'claude-'.
        """
        cls = self._get_batch_models_class()
        models = cls()

        all_model_ids = {
            models.default,
            models.fast,
            models.premium,
            models.for_learning(),
            models.for_briefing(),
            models.for_research(),
        }
        # Also check get_model() for all known task types
        for task_type in ["default", "fast", "premium", "learning", "briefing"]:
            all_model_ids.add(models.get_model(task_type))

        for model_id in all_model_ids:
            assert ANTHROPIC_MODEL_PATTERN.match(model_id), (
                f"Model '{model_id}' does not look like a valid Anthropic model "
                f"(expected to start with 'claude-')"
            )


# ---------------------------------------------------------------------------
# 2. Cost tracking end-to-end
# ---------------------------------------------------------------------------


class TestCostTrackingEndToEnd:
    """End-to-end tests for cost tracking through the call() pipeline."""

    def test_cost_tracking_records_to_jsonl(self, tmp_path: Path, mock_provider):
        """call() records cost to JSONL file via CostTracker."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            response = call("Hello", use_case="classification")

        assert response.content == "Test response"

        # Verify JSONL file was written
        assert tracker.costs_file.exists()
        lines = tracker.costs_file.read_text().strip().split("\n")
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["provider"] == "groq"
        assert entry["cost_usd"] == 0.000005
        assert entry["input_tokens"] == 100
        assert entry["output_tokens"] == 50
        assert entry["use_case"] == "classification"

    def test_cost_tracking_accumulates_daily(self, tmp_path: Path, mock_provider):
        """Multiple calls accumulate in daily totals."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            call("First call", use_case="classification")
            call("Second call", use_case="classification")
            call("Third call", use_case="classification")

        spend = tracker.get_daily_spend()
        assert spend["total"] == pytest.approx(0.000015, abs=1e-9)
        assert spend["groq"] == pytest.approx(0.000015, abs=1e-9)

        # Verify 3 lines in JSONL
        lines = tracker.costs_file.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_cost_tracking_per_provider(self, tmp_path: Path):
        """get_costs() breaks down by provider."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        # Record costs from two different providers
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.000005,
            use_case="classification",
        )
        tracker.record(
            provider="xai",
            model="grok-3-fast",
            input_tokens=2000,
            output_tokens=500,
            cost_usd=0.000650,
            use_case="research",
        )

        spend = tracker.get_daily_spend()

        assert "groq" in spend
        assert "xai" in spend
        assert spend["groq"] == pytest.approx(0.000005, abs=1e-9)
        assert spend["xai"] == pytest.approx(0.000650, abs=1e-9)
        assert spend["total"] == pytest.approx(0.000655, abs=1e-9)

    def test_savings_calculation(self, tmp_path: Path):
        """get_savings() compares actual cost to Anthropic baseline."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        # Classification on Groq (very cheap) vs Anthropic baseline (haiku: $1/$5)
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=10_000,
            output_tokens=500,
            cost_usd=0.00054,
            use_case="classification",
        )

        report = tracker.get_savings_report()

        # Anthropic haiku baseline: (10000 * 1.0 + 500 * 5.0) / 1_000_000 = 0.0125
        expected_anthro = (10_000 * 1.0 + 500 * 5.0) / 1_000_000
        assert report["anthropic_equivalent"] == pytest.approx(expected_anthro, abs=1e-9)
        assert report["actual_spend"] == pytest.approx(0.00054, abs=1e-9)
        assert report["savings_usd"] > 0
        assert report["savings_pct"] > 0
        assert report["total_calls"] == 1

    def test_budget_remaining_decreases(self, tmp_path: Path, mock_provider):
        """get_budget_remaining() decreases after recording costs."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        initial_budget = tracker.get_budget_remaining()
        assert initial_budget == 20.0

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            call("Test call", use_case="classification")

        remaining = tracker.get_budget_remaining()
        assert remaining < initial_budget
        assert remaining == pytest.approx(20.0 - 0.000005, abs=1e-9)


# ---------------------------------------------------------------------------
# 3. Batch cost recording
# ---------------------------------------------------------------------------


class TestBatchCostRecording:
    """Tests for batch cost integration with CostTracker."""

    def test_batch_cost_recording(self, tmp_path: Path):
        """Batch costs can be recorded to CostTracker directly."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        # Simulate what ConductorBatchModels.record_batch_cost() would do
        tracker.record(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            input_tokens=50_000,
            output_tokens=10_000,
            cost_usd=0.30,
            use_case="learning",
            latency_ms=0.0,  # Batch has no real-time latency
        )

        spend = tracker.get_daily_spend()
        assert spend["anthropic"] == pytest.approx(0.30, abs=1e-6)
        assert spend["total"] == pytest.approx(0.30, abs=1e-6)

    def test_batch_and_interactive_costs_unified(self, tmp_path: Path):
        """Batch and interactive costs appear in same get_costs() output."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=100.0)

        # Interactive call (Groq)
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.000005,
            use_case="classification",
            latency_ms=150.0,
        )

        # Batch call (Anthropic)
        tracker.record(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            input_tokens=50_000,
            output_tokens=10_000,
            cost_usd=0.30,
            use_case="learning",
            latency_ms=0.0,
        )

        spend = tracker.get_daily_spend()

        # Both providers present
        assert "groq" in spend
        assert "anthropic" in spend

        # Total includes both
        expected_total = 0.000005 + 0.30
        assert spend["total"] == pytest.approx(expected_total, abs=1e-6)

        # Savings report also includes both
        report = tracker.get_savings_report()
        assert report["total_calls"] == 2
        assert "classification" in report["by_use_case"]
        assert "learning" in report["by_use_case"]


# ---------------------------------------------------------------------------
# 4. Import fallback
# ---------------------------------------------------------------------------


class TestImportFallback:
    """Tests for import fallback behavior."""

    def test_conductor_import_fallback(self):
        """When ConductorBatchModels is unavailable, AnthropicBatchModels works.

        The batch pipeline should continue to function using AnthropicBatchModels
        if batch_models.py has not been created yet. This test verifies that the
        existing AnthropicBatchModels satisfies the same interface contract.
        """
        # AnthropicBatchModels must always be importable
        models = AnthropicBatchModels()

        # Core attributes
        assert hasattr(models, "default")
        assert hasattr(models, "fast")
        assert hasattr(models, "premium")

        # Core methods
        assert hasattr(models, "get_model")
        assert hasattr(models, "for_learning")
        assert hasattr(models, "for_briefing")
        assert hasattr(models, "for_research")

        # All return strings
        assert isinstance(models.get_model("default"), str)
        assert isinstance(models.for_learning(), str)
        assert isinstance(models.for_briefing(), str)
        assert isinstance(models.for_research(), str)

    def test_anthropic_batch_models_interface_matches_spec(self):
        """AnthropicBatchModels has all methods that ConductorBatchModels would need."""
        models = AnthropicBatchModels()

        # Verify all task types return without error
        task_types = [
            "default",
            "fast",
            "classification",
            "simple",
            "premium",
            "complex",
            "analysis",
            "recommendation",
            "learning",
            "briefing",
        ]
        for task_type in task_types:
            result = models.get_model(task_type)
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# 5. Delegation flow
# ---------------------------------------------------------------------------


class TestDelegationFlow:
    """Tests for route() -> call() flow and fallback behavior."""

    def test_route_then_call_flow(self, tmp_path: Path, mock_provider):
        """route() -> call() flow: routing decision feeds into provider selection."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        # First, verify route() returns a valid decision
        decision = route("Classify this text", use_case="classification")
        assert isinstance(decision, RoutingDecision)
        assert decision.provider in ("groq", "xai", "minimax", "anthropic", "openai", "deepseek")
        assert len(decision.model_id) > 0
        assert len(decision.fallback_provider) > 0

        # Then verify call() uses the routing to create a provider and execute
        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            response = call("Classify this text", use_case="classification")

        assert response.content == "Test response"
        assert response.provider == "groq"

        # Verify cost was tracked
        spend = tracker.get_daily_spend()
        assert spend["total"] > 0

    def test_fallback_triggers_on_provider_error(
        self, tmp_path: Path, failing_provider, mock_fallback_provider
    ):
        """When primary provider fails, fallback provider is tried."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        call_count = 0

        def side_effect_create_provider(provider_name: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: return failing provider (primary)
                return failing_provider
            else:
                # Second call: return working fallback
                return mock_fallback_provider

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch(
                "cortex.conductor.caller._create_provider", side_effect=side_effect_create_provider
            ),
        ):
            response = call("Test prompt", use_case="classification")

        # Should have gotten fallback response
        assert response.content == "Fallback response"
        assert response.provider == "anthropic"

        # Both providers were attempted
        assert call_count == 2

    def test_cost_tracked_on_fallback(
        self, tmp_path: Path, failing_provider, mock_fallback_provider
    ):
        """Fallback call still records cost correctly."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        call_count = 0

        def side_effect_create_provider(provider_name: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return failing_provider
            else:
                return mock_fallback_provider

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch(
                "cortex.conductor.caller._create_provider", side_effect=side_effect_create_provider
            ),
        ):
            call("Test prompt", use_case="research")

        # Cost should be recorded from the fallback provider
        spend = tracker.get_daily_spend()
        assert spend["total"] == pytest.approx(0.001200, abs=1e-6)
        assert spend["anthropic"] == pytest.approx(0.001200, abs=1e-6)

        # Savings report should show the fallback call
        report = tracker.get_savings_report()
        assert report["total_calls"] == 1
        assert report["actual_spend"] == pytest.approx(0.001200, abs=1e-6)

    def test_both_providers_fail_raises_error(self, tmp_path: Path, failing_provider):
        """When both primary and fallback fail, ProviderError is raised."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=failing_provider),
        ):
            with pytest.raises(ProviderError) as exc_info:
                call("Test prompt", use_case="classification")

            # Error message should mention both primary and fallback
            assert "Primary" in str(exc_info.value) or "Fallback" in str(exc_info.value)

    def test_call_with_provider_override(self, tmp_path: Path, mock_provider):
        """provider_override and model_override bypass routing."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch(
                "cortex.conductor.caller._create_provider", return_value=mock_provider
            ) as mock_create,
        ):
            response = call(
                "Test prompt",
                provider_override="groq",
                model_override="llama-3.1-8b-instant",
            )

        assert response.content == "Test response"
        # Provider was created with the override name
        mock_create.assert_called_with("groq")

    def test_call_with_system_message(self, tmp_path: Path, mock_provider):
        """call() passes system message to provider."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            call(
                "Classify this",
                use_case="classification",
                system="You are a classifier.",
            )

        # Verify system message was included in the call
        call_args = mock_provider.complete.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        assert len(messages) == 2  # system + user
        assert messages[0].role == "system"
        assert messages[0].content == "You are a classifier."
        assert messages[1].role == "user"

    def test_route_returns_valid_decision_for_all_use_cases(self):
        """route() returns a valid RoutingDecision for all known use cases."""
        use_cases = [
            "architecture",
            "interactive_coding",
            "classification",
            "long_context",
            "research",
            "quick_qa",
            "code_review",
            "test_generation",
            "documentation",
            "security_audit",
            "pattern_learning",
        ]
        for use_case in use_cases:
            decision = route(f"Test for {use_case}", use_case=use_case)
            assert isinstance(decision, RoutingDecision), (
                f"route() should return RoutingDecision for use_case='{use_case}'"
            )
            assert decision.provider, f"No provider for use_case='{use_case}'"
            assert decision.model_id, f"No model_id for use_case='{use_case}'"
            assert decision.fallback_provider, f"No fallback for use_case='{use_case}'"
            assert decision.fallback_model_id, f"No fallback model for use_case='{use_case}'"
            assert 0.0 <= decision.confidence <= 1.0


# ---------------------------------------------------------------------------
# 6. Default route fallback
# ---------------------------------------------------------------------------


class TestDefaultRouteFallback:
    """Tests for the fallback routing path when ConductorRouter is unavailable."""

    def test_fallback_route_returns_routing_decision(self):
        """Fallback route returns a RoutingDecision for any use case."""
        with patch("cortex.conductor.caller._get_router", return_value=None):
            decision = route("Test task", use_case="classification")
        assert isinstance(decision, RoutingDecision)
        assert decision.provider == "groq"
        assert decision.model_id == "llama-3.1-8b-instant"

    def test_fallback_route_unknown_use_case(self):
        """Unknown use case falls back to quick_qa entry."""
        with patch("cortex.conductor.caller._get_router", return_value=None):
            decision = route("Something unknown", use_case="nonexistent")
        assert isinstance(decision, RoutingDecision)
        # Falls back to quick_qa from ROUTING_TABLE
        assert decision.provider == "groq"

    def test_fallback_route_has_fallback(self):
        """Fallback route always includes a fallback provider."""
        with patch("cortex.conductor.caller._get_router", return_value=None):
            decision = route("Test", use_case="research")
        assert decision.fallback_provider
        assert decision.fallback_model_id


# ---------------------------------------------------------------------------
# 7. Module-level API coherence
# ---------------------------------------------------------------------------


class TestModuleAPICoherence:
    """Verify the public module API functions work together."""

    def test_get_costs_returns_dict(self):
        """get_costs() returns a dict even with no data."""
        with patch("cortex.conductor.caller._get_cost_tracker") as mock_get_tracker:
            mock_tracker = MagicMock()
            mock_tracker.get_daily_spend.return_value = {"total": 0.0}
            mock_get_tracker.return_value = mock_tracker

            costs = get_costs()

        assert isinstance(costs, dict)
        assert "total" in costs

    def test_get_savings_returns_dict(self):
        """get_savings() returns a dict even with no data."""
        with patch("cortex.conductor.caller._get_cost_tracker") as mock_get_tracker:
            mock_tracker = MagicMock()
            mock_tracker.get_savings_report.return_value = {
                "actual_spend": 0.0,
                "anthropic_equivalent": 0.0,
                "savings_usd": 0.0,
                "savings_pct": 0.0,
                "total_calls": 0,
                "by_use_case": {},
            }
            mock_get_tracker.return_value = mock_tracker

            savings = get_savings()

        assert isinstance(savings, dict)
        assert "actual_spend" in savings
        assert "savings_usd" in savings

    def test_get_budget_remaining_returns_float(self):
        """get_budget_remaining() returns a float."""
        with patch("cortex.conductor.caller._get_cost_tracker") as mock_get_tracker:
            mock_tracker = MagicMock()
            mock_tracker.get_budget_remaining.return_value = 20.0
            mock_get_tracker.return_value = mock_tracker

            remaining = get_budget_remaining()

        assert isinstance(remaining, float)
        assert remaining >= 0.0

    def test_full_lifecycle_route_call_track(self, tmp_path: Path, mock_provider):
        """Full lifecycle: route -> call -> verify costs -> check savings."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        # 1. Route
        decision = route("Classify this ticket", use_case="classification")
        assert isinstance(decision, RoutingDecision)

        # 2. Call
        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            response = call("Classify this ticket", use_case="classification")

        assert response.content == "Test response"

        # 3. Verify costs
        spend = tracker.get_daily_spend()
        assert spend["total"] > 0
        assert "groq" in spend

        # 4. Check savings
        report = tracker.get_savings_report()
        assert report["total_calls"] == 1
        assert report["actual_spend"] > 0
        # Groq should be cheaper than Anthropic for classification
        assert report["savings_usd"] > 0
        assert report["savings_pct"] > 0

        # 5. Budget should have decreased
        remaining = tracker.get_budget_remaining()
        assert remaining < 20.0


class TestAsyncCall:
    """Tests for the async_call() API."""

    @pytest.fixture
    def mock_async_provider(self):
        """Provider mock with async_complete returning a CompletionResponse."""
        provider = MagicMock()

        async def _async_complete(**kwargs):
            return CompletionResponse(
                content="Async test response",
                model="llama-3.1-8b-instant",
                provider="groq",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                latency_ms=50.0,
                cost_usd=0.0009,
            )

        provider.async_complete = _async_complete
        return provider

    @pytest.mark.asyncio
    async def test_async_call_basic(self, tmp_path: Path, mock_async_provider):
        """async_call() routes and executes without blocking."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_async_provider),
        ):
            response = await async_call("Classify this", use_case="classification")

        assert response.content == "Async test response"
        assert response.provider == "groq"
        assert tracker.get_daily_spend()["total"] > 0

    @pytest.mark.asyncio
    async def test_async_call_fallback_on_failure(self, tmp_path: Path, mock_async_provider):
        """async_call() falls back when primary provider raises."""

        async def _failing_async(**kwargs):
            raise ProviderError("groq", 500, "Service unavailable")

        failing_provider = MagicMock()
        failing_provider.async_complete = _failing_async

        call_count = 0

        def side_effect_create(name):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return failing_provider
            return mock_async_provider

        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", side_effect=side_effect_create),
        ):
            response = await async_call("Classify this", use_case="classification")

        assert response.content == "Async test response"

    @pytest.mark.asyncio
    async def test_async_call_records_costs(self, tmp_path: Path, mock_async_provider):
        """async_call() records cost to the tracker like sync call()."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_async_provider),
        ):
            await async_call("Test", use_case="quick_qa")

        spend = tracker.get_daily_spend()
        assert spend["total"] == pytest.approx(0.0009, abs=1e-6)

    @pytest.mark.asyncio
    async def test_async_call_with_overrides(self, tmp_path: Path, mock_async_provider):
        """async_call() respects provider and model overrides."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch(
                "cortex.conductor.caller._create_provider", return_value=mock_async_provider
            ) as mock_create,
        ):
            await async_call(
                "Test",
                provider_override="groq",
                model_override="llama-3.1-8b-instant",
            )

        mock_create.assert_called_with("groq")


class TestRetryBackoff:
    """Tests for retry logic on transient errors."""

    @pytest.fixture
    def success_response(self):
        return CompletionResponse(
            content="OK",
            model="llama-3.1-8b-instant",
            provider="groq",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            latency_ms=50.0,
            cost_usd=0.0009,
        )

    def test_sync_retry_on_429(self, tmp_path: Path, success_response):
        """Sync call retries on 429 rate limit and succeeds."""
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = [
            ProviderError("groq", 429, "Rate limit exceeded"),
            success_response,
        ]
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
            patch("cortex.conductor.caller.time.sleep"),
        ):
            response = call("Test", use_case="classification")

        assert response.content == "OK"
        assert mock_provider.complete.call_count == 2

    def test_sync_no_retry_on_401(self, tmp_path: Path):
        """Sync call does NOT retry on 401 (not transient)."""
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = ProviderError("groq", 401, "Unauthorized")
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
        ):
            with pytest.raises(ProviderError, match="Unauthorized"):
                call("Test", use_case="classification")

        # Called once for primary, once for fallback — no retries on either
        assert mock_provider.complete.call_count == 2

    def test_sync_retry_exhausted_raises(self, tmp_path: Path):
        """After max retries, the error propagates to fallback."""
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = ProviderError("groq", 429, "Rate limit")
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
            patch("cortex.conductor.caller.time.sleep"),
        ):
            with pytest.raises(ProviderError):
                call("Test", use_case="classification")

        # 3 attempts on primary + 3 on fallback = 6
        assert mock_provider.complete.call_count == 6

    @pytest.mark.asyncio
    async def test_async_retry_on_503(self, tmp_path: Path, success_response):
        """Async call retries on 503 service unavailable."""

        call_count = 0

        async def _async_complete(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("groq", 503, "Service unavailable")
            return success_response

        mock_provider = MagicMock()
        mock_provider.async_complete = _async_complete
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
            patch("cortex.conductor.caller.asyncio.sleep", new_callable=AsyncMock),
        ):
            response = await async_call("Test", use_case="classification")

        assert response.content == "OK"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry_uses_asyncio_sleep(self, tmp_path: Path, success_response):
        """Async retry uses asyncio.sleep (non-blocking), not time.sleep."""

        call_count = 0

        async def _async_complete(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("groq", 429, "Rate limit")
            return success_response

        mock_provider = MagicMock()
        mock_provider.async_complete = _async_complete
        tracker = CostTracker(state_dir=tmp_path, daily_budget=20.0)

        with (
            patch("cortex.conductor.caller._get_cost_tracker", return_value=tracker),
            patch("cortex.conductor.caller._create_provider", return_value=mock_provider),
            patch("cortex.conductor.caller.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await async_call("Test", use_case="classification")

        mock_sleep.assert_called_once_with(1.0)
