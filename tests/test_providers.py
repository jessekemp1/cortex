"""Tests for the multi-provider registry (Phase 1).

Tests:
  - Config loading from YAML
  - Default Anthropic-only fallback
  - Circuit breaker (3 failures → open, backoff → half-open)
  - Tier-based model lookup with cost sorting
  - API key validation
  - Offline mode transitions
  - Cost estimation
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.supervisor.providers import (
    ModelSpec,
    ProviderConfig,
    ProviderRegistry,
    _CB_BACKOFF_SECONDS,
    _CB_FAILURE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_YAML = """\
providers:
  anthropic:
    api_key_env: ANTHROPIC_API_KEY
    supports_batch: true
    models:
      claude-opus-4-6:
        tier: opus
        cost_input: 15.0
        cost_output: 75.0
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
  ollama:
    type: local
    api_key_env: ""
    priority: -1
    models:
      llama3.1-8b:
        tier: haiku
        cost_input: 0.0
        cost_output: 0.0
        supports_tools: false
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    p = tmp_path / "providers.yaml"
    p.write_text(SAMPLE_YAML)
    return p


@pytest.fixture
def registry(config_file: Path) -> ProviderRegistry:
    """Registry loaded with sample config and all API keys present."""
    env = {
        "ANTHROPIC_API_KEY": "sk-test-anthropic",  # pragma: allowlist secret
        "DEEPSEEK_API_KEY": "sk-test-deepseek",  # pragma: allowlist secret
        "GROQ_API_KEY": "gsk-test-groq",  # pragma: allowlist secret
    }
    with patch.dict(os.environ, env, clear=False):
        return ProviderRegistry(config_path=config_file)


@pytest.fixture
def registry_no_keys(config_file: Path) -> ProviderRegistry:
    """Registry with no API keys in environment."""
    env = {
        "ANTHROPIC_API_KEY": "",
        "DEEPSEEK_API_KEY": "",
        "GROQ_API_KEY": "",
    }
    with patch.dict(os.environ, env, clear=False):
        return ProviderRegistry(config_path=config_file)


# ---------------------------------------------------------------------------
# Tests: Config loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def test_loads_providers_from_yaml(self, registry: ProviderRegistry) -> None:
        providers = registry.get_all_providers()
        assert "anthropic" in providers
        assert "deepseek" in providers
        assert "groq" in providers
        assert "ollama" in providers

    def test_loads_models(self, registry: ProviderRegistry) -> None:
        anthropic = registry.get_provider("anthropic")
        assert anthropic is not None
        assert "claude-opus-4-6" in anthropic.models
        assert "claude-sonnet-4-6" in anthropic.models

    def test_model_spec_fields(self, registry: ProviderRegistry) -> None:
        anthropic = registry.get_provider("anthropic")
        assert anthropic is not None
        opus = anthropic.models["claude-opus-4-6"]
        assert opus.tier == "opus"
        assert opus.cost_input_per_1m == 15.0
        assert opus.cost_output_per_1m == 75.0

    def test_missing_config_falls_back_to_defaults(self, tmp_path: Path) -> None:
        """No config file → Anthropic-only defaults."""
        env = {"ANTHROPIC_API_KEY": "test"}  # pragma: allowlist secret
        with patch.dict(os.environ, env, clear=False):
            reg = ProviderRegistry(config_path=tmp_path / "nonexistent.yaml")
        providers = reg.get_all_providers()
        assert len(providers) == 1
        assert "anthropic" in providers

    def test_empty_config_falls_back_to_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("")
        env = {"ANTHROPIC_API_KEY": "test"}  # pragma: allowlist secret
        with patch.dict(os.environ, env, clear=False):
            reg = ProviderRegistry(config_path=p)
        assert "anthropic" in reg.get_all_providers()

    def test_local_provider_type(self, registry: ProviderRegistry) -> None:
        ollama = registry.get_provider("ollama")
        assert ollama is not None
        assert ollama.provider_type == "local"


# ---------------------------------------------------------------------------
# Tests: API key validation
# ---------------------------------------------------------------------------


class TestKeyValidation:
    def test_missing_key_disables_provider(self, registry_no_keys: ProviderRegistry) -> None:
        """Providers without API keys should be disabled."""
        deepseek = registry_no_keys.get_provider("deepseek")
        assert deepseek is not None
        assert not deepseek.enabled

    def test_local_provider_not_disabled(self, registry_no_keys: ProviderRegistry) -> None:
        """Local providers (ollama) should not be disabled for missing keys."""
        ollama = registry_no_keys.get_provider("ollama")
        assert ollama is not None
        assert ollama.enabled  # Local providers don't need keys


# ---------------------------------------------------------------------------
# Tests: Tier lookup
# ---------------------------------------------------------------------------


class TestTierLookup:
    def test_get_models_for_tier_returns_sorted_by_cost(self, registry: ProviderRegistry) -> None:
        """Models returned cheapest-first within tier."""
        sonnet_models = registry.get_models_for_tier("sonnet")
        assert len(sonnet_models) >= 2
        # DeepSeek ($0.14+$0.28) should come before Anthropic ($3+$15)
        costs = [s.cost_input_per_1m + s.cost_output_per_1m for _, s in sonnet_models]
        assert costs == sorted(costs)

    def test_get_models_for_tier_excludes_disabled(
        self, registry_no_keys: ProviderRegistry
    ) -> None:
        """Disabled providers should not appear in tier lookup."""
        sonnet_models = registry_no_keys.get_models_for_tier("sonnet")
        provider_names = [pname for pname, _ in sonnet_models]
        assert "deepseek" not in provider_names

    def test_get_models_for_unknown_tier(self, registry: ProviderRegistry) -> None:
        models = registry.get_models_for_tier("nonexistent")
        assert models == []


# ---------------------------------------------------------------------------
# Tests: Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_healthy_by_default(self, registry: ProviderRegistry) -> None:
        assert registry.is_healthy("anthropic")
        assert registry.is_healthy("nonexistent_provider")

    def test_single_failure_stays_healthy(self, registry: ProviderRegistry) -> None:
        registry.mark_failure("deepseek", "deepseek-chat", "timeout")
        assert registry.is_healthy("deepseek")

    def test_consecutive_failures_trips_breaker(self, registry: ProviderRegistry) -> None:
        for _ in range(_CB_FAILURE_THRESHOLD):
            registry.mark_failure("deepseek", "deepseek-chat", "timeout")
        assert not registry.is_healthy("deepseek")

    def test_success_resets_breaker(self, registry: ProviderRegistry) -> None:
        for _ in range(_CB_FAILURE_THRESHOLD):
            registry.mark_failure("deepseek", "deepseek-chat", "timeout")
        assert not registry.is_healthy("deepseek")

        registry.mark_success("deepseek", "deepseek-chat")
        assert registry.is_healthy("deepseek")

    def test_backoff_auto_recovery(self, registry: ProviderRegistry) -> None:
        """After backoff period, breaker goes half-open."""
        for _ in range(_CB_FAILURE_THRESHOLD):
            registry.mark_failure("groq", "groq/llama-3.1-8b-instant", "500")

        assert not registry.is_healthy("groq")

        # Simulate backoff elapsed
        cb = registry._circuit_breakers["groq"]
        cb.last_failure_time = time.monotonic() - _CB_BACKOFF_SECONDS - 1
        assert registry.is_healthy("groq")

    def test_tripped_breaker_excludes_from_tier_lookup(self, registry: ProviderRegistry) -> None:
        """Tripped provider's models should not appear in tier results."""
        # Trip deepseek
        for _ in range(_CB_FAILURE_THRESHOLD):
            registry.mark_failure("deepseek", "deepseek/deepseek-chat", "error")

        sonnet_models = registry.get_models_for_tier("sonnet")
        provider_names = [pname for pname, _ in sonnet_models]
        assert "deepseek" not in provider_names


# ---------------------------------------------------------------------------
# Tests: Offline mode
# ---------------------------------------------------------------------------


class TestOfflineMode:
    def test_enter_offline_disables_api_providers(self, registry: ProviderRegistry) -> None:
        registry.enter_offline_mode()
        assert registry.offline_mode
        assert not registry.get_provider("anthropic").enabled
        assert not registry.get_provider("deepseek").enabled
        # Local provider stays enabled
        assert registry.get_provider("ollama").enabled

    def test_exit_offline_restores_state(self, registry: ProviderRegistry) -> None:
        registry.enter_offline_mode()
        registry.exit_offline_mode()
        assert not registry.offline_mode
        assert registry.get_provider("anthropic").enabled

    def test_double_enter_offline_is_idempotent(self, registry: ProviderRegistry) -> None:
        registry.enter_offline_mode()
        registry.enter_offline_mode()
        assert registry.offline_mode
        registry.exit_offline_mode()
        assert registry.get_provider("anthropic").enabled


# ---------------------------------------------------------------------------
# Tests: Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_anthropic_cost(self, registry: ProviderRegistry) -> None:
        cost = registry.estimate_cost(
            "anthropic",
            "claude-opus-4-6",
            input_tokens=1000,
            output_tokens=500,
        )
        # 15.0 * 1000/1M + 75.0 * 500/1M = 0.015 + 0.0375 = 0.0525
        assert abs(cost - 0.0525) < 0.001

    def test_unknown_provider_returns_zero(self, registry: ProviderRegistry) -> None:
        cost = registry.estimate_cost("unknown", "unknown-model", 1000, 1000)
        assert cost == 0.0

    def test_local_model_cost_is_zero(self, registry: ProviderRegistry) -> None:
        cost = registry.estimate_cost("ollama", "ollama/llama3.1-8b", 10000, 5000)
        assert cost == 0.0
