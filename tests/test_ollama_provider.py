"""
Tests for Ollama local provider configuration and routing.

Tests:
- Ollama config exists in PROVIDERS with required fields
- Routing table includes Ollama for classification
- Zero cost for local provider
- Circuit breaker trips on unreachable Ollama
- Routing fallback when Ollama unavailable
"""

import pytest


class TestOllamaConfig:
    """Tests for Ollama provider configuration in conductor/config.py."""

    def test_ollama_in_providers(self):
        from conductor.config import PROVIDERS

        assert "ollama" in PROVIDERS

    def test_ollama_has_required_fields(self):
        from conductor.config import PROVIDERS

        ollama = PROVIDERS["ollama"]
        assert ollama["base_url"] == "http://localhost:11434/v1"
        assert ollama["api_type"] == "openai_compat"
        assert ollama["supports_batch"] is False
        assert ollama["provider_type"] == "local"
        assert ollama["priority"] == -1

    def test_ollama_has_models(self):
        from conductor.config import PROVIDERS

        models = PROVIDERS["ollama"]["models"]
        assert "llama4-scout" in models

    def test_llama4_scout_config(self):
        from conductor.config import PROVIDERS

        scout = PROVIDERS["ollama"]["models"]["llama4-scout"]
        assert scout["display_name"] == "Llama 4 Scout (Local)"
        assert scout["input_cost"] == 0.0
        assert scout["output_cost"] == 0.0
        assert scout["max_context"] == 131_072
        assert "classification" in scout["strengths"]
        assert "quick_qa" in scout["strengths"]

    def test_ollama_zero_cost(self):
        """Verify cost is $0 for local provider."""
        from conductor.config import PROVIDERS, get_pricing

        pricing = get_pricing("ollama")
        for model_id, (input_cost, output_cost) in pricing.items():
            assert input_cost == 0.0, f"{model_id} has non-zero input cost"
            assert output_cost == 0.0, f"{model_id} has non-zero output cost"


class TestOllamaRouting:
    """Tests for Ollama in the routing table."""

    def test_classification_routes_to_ollama_fallback(self):
        from conductor.config import ROUTING_TABLE

        entry = ROUTING_TABLE["classification"]
        # classification: primary=groq, fallback=ollama
        assert entry[2] == "ollama"  # fallback_provider
        assert entry[3] == "llama4-scout"  # fallback_model

    def test_ollama_env_var_empty(self):
        """Local providers don't need API keys."""
        from conductor.config import PROVIDERS

        assert PROVIDERS["ollama"]["env_var"] == ""


class TestOllamaCircuitBreaker:
    """Tests for circuit breaker behavior with Ollama."""

    def test_circuit_breaker_trips_on_failures(self):
        from supervisor.providers import ProviderRegistry

        # Use a non-existent YAML to get default config
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            # Write minimal config with ollama
            config_path.write_text("""
providers:
  ollama:
    api_key_env: ""
    base_url: "http://localhost:11434/v1"
    type: local
    priority: -1
    models:
      llama4-scout:
        tier: haiku
        max_tokens: 8192
        cost_input: 0.0
        cost_output: 0.0
        task_affinity: [classification, quick_qa]
""")
            registry = ProviderRegistry(config_path=config_path)

            # Should be healthy initially
            assert registry.is_healthy("ollama") is True

            # Simulate 3 failures
            registry.mark_failure("ollama", "llama4-scout", "connection refused")
            registry.mark_failure("ollama", "llama4-scout", "connection refused")
            registry.mark_failure("ollama", "llama4-scout", "connection refused")

            # Circuit breaker should trip
            assert registry.is_healthy("ollama") is False

    def test_circuit_breaker_recovers_on_success(self):
        from supervisor.providers import ProviderRegistry

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            config_path.write_text("""
providers:
  ollama:
    api_key_env: ""
    base_url: "http://localhost:11434/v1"
    type: local
    priority: -1
    models:
      llama4-scout:
        tier: haiku
""")
            registry = ProviderRegistry(config_path=config_path)

            # Trip the breaker
            for _ in range(3):
                registry.mark_failure("ollama", "llama4-scout", "error")
            assert registry.is_healthy("ollama") is False

            # Success resets
            registry.mark_success("ollama", "llama4-scout")
            assert registry.is_healthy("ollama") is True

    def test_local_provider_no_api_key_validation(self):
        """Local providers should not be disabled for missing API keys."""
        from supervisor.providers import ProviderRegistry

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "providers.yaml"
            config_path.write_text("""
providers:
  ollama:
    api_key_env: ""
    base_url: "http://localhost:11434/v1"
    type: local
    models:
      llama4-scout:
        tier: haiku
""")
            registry = ProviderRegistry(config_path=config_path)
            provider = registry.get_provider("ollama")
            assert provider is not None
            assert provider.enabled is True
