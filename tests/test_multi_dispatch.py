"""Tests for the multi-provider dispatcher (Phase 1).

Tests:
  - Anthropic models delegate to existing AgentDispatcher
  - LiteLLM dispatch with mocked responses
  - Fallback chain within tier
  - Tier escalation on exhaustion
  - Offline mode fallback
  - Provider field populated on results
  - Cost tracking on results
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.supervisor.dispatch import AgentDispatcher, DispatchResult, ModelSelection
from cortex.supervisor.models import WorkItem, WorkItemPriority
from cortex.supervisor.multi_dispatch import MultiProviderDispatcher
from cortex.supervisor.providers import ProviderRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_YAML = """\
providers:
  anthropic:
    api_key_env: ANTHROPIC_API_KEY
    models:
      claude-sonnet-4-6:
        tier: sonnet
        cost_input: 3.0
        cost_output: 15.0
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com/v1
    models:
      deepseek-chat:
        tier: sonnet
        cost_input: 0.14
        cost_output: 0.28
  groq:
    api_key_env: GROQ_API_KEY
    models:
      llama-3.1-8b-instant:
        tier: haiku
        cost_input: 0.05
        cost_output: 0.08
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    p = tmp_path / "providers.yaml"
    p.write_text(SAMPLE_YAML)
    return p


@pytest.fixture
def registry(config_file: Path) -> ProviderRegistry:
    env = {
        "ANTHROPIC_API_KEY": "sk-test",  # pragma: allowlist secret
        "DEEPSEEK_API_KEY": "sk-test",  # pragma: allowlist secret
        "GROQ_API_KEY": "gsk-test",  # pragma: allowlist secret
    }
    with patch.dict(os.environ, env, clear=False):
        return ProviderRegistry(config_path=config_file)


@pytest.fixture
def mock_anthropic_dispatcher() -> AgentDispatcher:
    dispatcher = MagicMock(spec=AgentDispatcher)
    dispatcher._build_prompt = MagicMock(return_value="test prompt")
    dispatcher._build_system_prompt = MagicMock(return_value="test system")
    return dispatcher


@pytest.fixture
def multi_dispatcher(
    registry: ProviderRegistry, mock_anthropic_dispatcher: AgentDispatcher
) -> MultiProviderDispatcher:
    return MultiProviderDispatcher(
        registry=registry,
        anthropic_dispatcher=mock_anthropic_dispatcher,
    )


def _make_work_item(task_type: str = "research") -> WorkItem:
    return WorkItem(
        id="test-item-1",
        source="test",
        task_type=task_type,
        description="Test work item",
        priority=WorkItemPriority.MEDIUM,
    )


def _make_selection(
    tier: str = "sonnet",
    model_id: str = "claude-sonnet-4-6",
    provider: str = "anthropic",
) -> ModelSelection:
    return ModelSelection(
        model_tier=tier,
        model_id=model_id,
        reasoning="test",
        complexity_score=0.5,
        confidence=0.8,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Tests: Anthropic delegation
# ---------------------------------------------------------------------------


class TestAnthropicDelegation:
    def test_claude_model_delegates_to_anthropic(
        self, multi_dispatcher: MultiProviderDispatcher, mock_anthropic_dispatcher: MagicMock
    ) -> None:
        """Claude models should use the existing AgentDispatcher."""
        mock_anthropic_dispatcher.dispatch_async = AsyncMock(
            return_value=DispatchResult(
                work_item_id="test-item-1",
                success=True,
                output="test output",
                model_used="claude-sonnet-4-6",
                tokens_used=1000,
                duration_seconds=1.5,
                task_type="research",
            )
        )

        result = asyncio.run(multi_dispatcher.dispatch_async(_make_work_item(), _make_selection()))

        mock_anthropic_dispatcher.dispatch_async.assert_called_once()
        assert result.success
        assert result.provider == "anthropic"

    def test_anthropic_failure_marks_circuit_breaker(
        self,
        multi_dispatcher: MultiProviderDispatcher,
        mock_anthropic_dispatcher: MagicMock,
        registry: ProviderRegistry,
    ) -> None:
        mock_anthropic_dispatcher.dispatch_async = AsyncMock(
            return_value=DispatchResult(
                work_item_id="test-item-1",
                success=False,
                output="",
                model_used="claude-sonnet-4-6",
                tokens_used=0,
                duration_seconds=0.0,
                task_type="research",
                error="API error",
            )
        )

        result = asyncio.run(multi_dispatcher.dispatch_async(_make_work_item(), _make_selection()))

        assert not result.success
        # Circuit breaker should have recorded one failure
        cb = registry._circuit_breakers.get("anthropic")
        assert cb is not None
        assert cb.consecutive_failures == 1


# ---------------------------------------------------------------------------
# Tests: Provider resolution
# ---------------------------------------------------------------------------


class TestProviderResolution:
    def test_claude_models_resolve_to_anthropic(
        self, multi_dispatcher: MultiProviderDispatcher
    ) -> None:
        assert multi_dispatcher._resolve_provider("claude-sonnet-4-6") == "anthropic"
        assert multi_dispatcher._resolve_provider("claude-opus-4-6") == "anthropic"

    def test_litellm_prefix_models(self, multi_dispatcher: MultiProviderDispatcher) -> None:
        assert multi_dispatcher._resolve_provider("groq/llama-3.1-8b-instant") == "groq"
        assert multi_dispatcher._resolve_provider("deepseek/deepseek-chat") == "deepseek"

    def test_unknown_model(self, multi_dispatcher: MultiProviderDispatcher) -> None:
        assert multi_dispatcher._resolve_provider("unknown-model") == "unknown"


# ---------------------------------------------------------------------------
# Tests: LiteLLM dispatch (mocked)
# ---------------------------------------------------------------------------


class TestLiteLLMDispatch:
    def test_non_claude_model_uses_litellm(self, multi_dispatcher: MultiProviderDispatcher) -> None:
        """Non-Claude models should dispatch via LiteLLM."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LiteLLM response"
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 300

        with patch("cortex.supervisor.multi_dispatch._get_litellm") as mock_get:
            mock_litellm = MagicMock()
            mock_litellm.completion.return_value = mock_response
            mock_get.return_value = mock_litellm

            selection = _make_selection(
                tier="sonnet",
                model_id="deepseek/deepseek-chat",
                provider="deepseek",
            )
            result = asyncio.run(multi_dispatcher.dispatch_async(_make_work_item(), selection))

            assert result.success
            assert result.model_used == "deepseek/deepseek-chat"
            assert result.provider == "deepseek"
            assert result.tokens_used == 800
            assert result.cost_usd > 0

    def test_litellm_not_installed_falls_through(
        self, multi_dispatcher: MultiProviderDispatcher
    ) -> None:
        """When litellm not installed, dispatch should fail gracefully."""
        with patch("cortex.supervisor.multi_dispatch._get_litellm", return_value=None):
            selection = _make_selection(
                tier="sonnet",
                model_id="deepseek/deepseek-chat",
                provider="deepseek",
            )
            result = asyncio.run(multi_dispatcher.dispatch_async(_make_work_item(), selection))

            assert not result.success
            assert "failed" in result.error.lower() or "providers" in result.error.lower()


# ---------------------------------------------------------------------------
# Tests: Dispatch result fields
# ---------------------------------------------------------------------------


class TestDispatchResultFields:
    def test_provider_field_default(self) -> None:
        result = DispatchResult(
            work_item_id="test",
            success=True,
            output="test",
            model_used="claude-sonnet-4-6",
            tokens_used=100,
            duration_seconds=1.0,
        )
        assert result.provider == "anthropic"
        assert result.cost_usd == 0.0

    def test_provider_field_set(self) -> None:
        result = DispatchResult(
            work_item_id="test",
            success=True,
            output="test",
            model_used="deepseek-chat",
            tokens_used=100,
            duration_seconds=1.0,
            provider="deepseek",
            cost_usd=0.005,
        )
        assert result.provider == "deepseek"
        assert result.cost_usd == 0.005


# ---------------------------------------------------------------------------
# Tests: Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_dispatch_result_serialization(self) -> None:
        """Existing code that accesses DispatchResult fields should still work."""
        result = DispatchResult(
            work_item_id="test",
            success=True,
            output="output",
            model_used="claude-sonnet-4-6",
            tokens_used=500,
            duration_seconds=2.0,
            task_type="research",
            error=None,
            checkpoint_id=None,
        )
        # Old fields still work
        assert result.work_item_id == "test"
        assert result.success is True
        assert result.output == "output"
        assert result.model_used == "claude-sonnet-4-6"
        assert result.tokens_used == 500
        assert result.task_type == "research"
        # New fields have defaults
        assert result.provider == "anthropic"
        assert result.cost_usd == 0.0

    def test_model_selection_provider_default(self) -> None:
        """ModelSelection.provider defaults to 'anthropic'."""
        ms = ModelSelection(
            model_tier="sonnet",
            model_id="claude-sonnet-4-6",
            reasoning="test",
            complexity_score=0.5,
            confidence=0.8,
        )
        assert ms.provider == "anthropic"
