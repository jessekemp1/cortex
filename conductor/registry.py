#!/usr/bin/env python3
"""
Provider Registry.

Contains all provider configurations with real model IDs, costs,
and capabilities. Single source of truth for the conductor.
"""

from typing import Dict, List

try:
    from cortex.conductor.models import ModelSpec, ProviderConfig
except ImportError:
    from .models import ModelSpec, ProviderConfig  # type: ignore[no-redef]


def _build_registry() -> Dict[str, ProviderConfig]:
    """Build the complete provider registry. Called once at module load."""

    providers: Dict[str, ProviderConfig] = {}

    # ── Groq ──────────────────────────────────────────────────────────
    providers["groq"] = ProviderConfig(
        name="groq",
        api_key_env="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        max_context=131_072,
        supports_batch=False,
        models={
            "llama-3.1-8b-instant": ModelSpec(
                model_id="llama-3.1-8b-instant",
                display_name="Groq Llama 8B",
                input_cost_per_mtok=0.05,
                output_cost_per_mtok=0.08,
                max_context=131_072,
                max_output=8_192,
                speed_tier="fast",
                strengths=["classification"],
            ),
            "openai/gpt-oss-20b": ModelSpec(
                model_id="openai/gpt-oss-20b",
                display_name="Groq GPT-OSS 20B",
                input_cost_per_mtok=0.075,
                output_cost_per_mtok=0.30,
                max_context=131_072,
                max_output=16_384,
                speed_tier="fast",
                strengths=["qa", "classification"],
            ),
        },
    )

    # ── xAI ───────────────────────────────────────────────────────────
    providers["xai"] = ProviderConfig(
        name="xai",
        api_key_env="XAI_API_KEY",
        base_url="https://api.x.ai/v1",
        max_context=2_000_000,
        supports_batch=False,
        models={
            "grok-3-fast": ModelSpec(
                model_id="grok-3-fast",
                display_name="Grok 4.1 Fast",
                input_cost_per_mtok=0.20,
                output_cost_per_mtok=0.50,
                max_context=2_000_000,
                max_output=131_072,
                speed_tier="fast",
                strengths=["long_context", "research"],
            ),
            "grok-code-fast-1": ModelSpec(
                model_id="grok-code-fast-1",
                display_name="Grok Code Fast 1",
                input_cost_per_mtok=0.20,
                output_cost_per_mtok=1.50,
                max_context=131_072,
                max_output=131_072,
                speed_tier="fast",
                strengths=["code", "interactive_coding", "test_generation"],
            ),
        },
    )

    # ── MiniMax ───────────────────────────────────────────────────────
    providers["minimax"] = ProviderConfig(
        name="minimax",
        api_key_env="MINIMAX_API_KEY",
        base_url="https://api.minimax.chat/v1",
        max_context=1_000_000,
        supports_batch=True,
        models={
            "MiniMax-M1-80k": ModelSpec(
                model_id="MiniMax-M1-80k",
                display_name="MiniMax M2.5",
                input_cost_per_mtok=0.30,
                output_cost_per_mtok=1.20,
                max_context=1_000_000,
                max_output=80_000,
                speed_tier="medium",
                strengths=["code", "code_review", "test_generation", "long_context"],
            ),
        },
    )

    # ── Anthropic ─────────────────────────────────────────────────────
    providers["anthropic"] = ProviderConfig(
        name="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        max_context=200_000,
        supports_batch=True,
        models={
            "claude-opus-4-6": ModelSpec(
                model_id="claude-opus-4-6",
                display_name="Opus 4.6",
                input_cost_per_mtok=15.0,
                output_cost_per_mtok=75.0,
                max_context=200_000,
                max_output=32_000,
                speed_tier="slow",
                strengths=["architecture", "security", "security_audit"],
            ),
            "claude-sonnet-4-5-20250929": ModelSpec(
                model_id="claude-sonnet-4-5-20250929",
                display_name="Sonnet 4.5",
                input_cost_per_mtok=3.0,
                output_cost_per_mtok=15.0,
                max_context=200_000,
                max_output=16_384,
                speed_tier="fast",
                strengths=["interactive_coding", "code"],
            ),
            "claude-haiku-4-5-20251001": ModelSpec(
                model_id="claude-haiku-4-5-20251001",
                display_name="Haiku 4.5",
                input_cost_per_mtok=1.0,
                output_cost_per_mtok=5.0,
                max_context=200_000,
                max_output=8_192,
                speed_tier="fast",
                strengths=["qa", "quick_qa"],
            ),
        },
    )

    # ── OpenAI ────────────────────────────────────────────────────────
    providers["openai"] = ProviderConfig(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        max_context=400_000,
        supports_batch=True,
        models={
            "gpt-5": ModelSpec(
                model_id="gpt-5",
                display_name="GPT-5",
                input_cost_per_mtok=2.50,
                output_cost_per_mtok=20.0,
                max_context=400_000,
                max_output=32_768,
                speed_tier="medium",
                strengths=["reasoning", "research", "architecture"],
            ),
            "gpt-5-nano": ModelSpec(
                model_id="gpt-5-nano",
                display_name="GPT-5 Nano",
                input_cost_per_mtok=0.10,
                output_cost_per_mtok=0.80,
                max_context=128_000,
                max_output=16_384,
                speed_tier="fast",
                strengths=["classification"],
            ),
        },
    )

    # ── DeepSeek ──────────────────────────────────────────────────────
    providers["deepseek"] = ProviderConfig(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        max_context=128_000,
        supports_batch=False,
        models={
            "deepseek-chat": ModelSpec(
                model_id="deepseek-chat",
                display_name="DeepSeek V3.2",
                input_cost_per_mtok=0.28,
                output_cost_per_mtok=0.42,
                max_context=128_000,
                max_output=16_384,
                speed_tier="medium",
                strengths=["pattern_learning", "research", "documentation"],
            ),
        },
    )

    return providers


# Module-level singleton
_REGISTRY: Dict[str, ProviderConfig] = _build_registry()


def get_provider(name: str) -> ProviderConfig:
    """
    Get a provider config by name.

    Args:
        name: Provider name (e.g., "groq", "anthropic")

    Returns:
        ProviderConfig for the requested provider

    Raises:
        KeyError: If provider not found
    """
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown provider '{name}'. Available: {available}")
    return _REGISTRY[name]


def get_all_providers() -> Dict[str, ProviderConfig]:
    """
    Get all registered providers.

    Returns:
        Dict mapping provider name -> ProviderConfig
    """
    return dict(_REGISTRY)


def get_model_spec(provider_name: str, model_id: str) -> ModelSpec:
    """
    Look up a specific model spec by provider and model ID.

    Args:
        provider_name: Provider name (e.g., "anthropic")
        model_id: Model ID (e.g., "claude-opus-4-6")

    Returns:
        ModelSpec for the requested model

    Raises:
        KeyError: If provider or model not found
    """
    provider = get_provider(provider_name)
    model = provider.get_model(model_id)
    if model is None:
        available = ", ".join(provider.list_models())
        raise KeyError(
            f"Unknown model '{model_id}' for provider '{provider_name}'. Available: {available}"
        )
    return model


def list_providers() -> List[str]:
    """Return sorted list of all provider names."""
    return sorted(_REGISTRY.keys())


def list_all_models() -> List[tuple[str, str, str]]:
    """
    Return all (provider, model_id, display_name) tuples.

    Useful for discovery and debugging.
    """
    result = []
    for provider_name, provider in sorted(_REGISTRY.items()):
        for model_id, spec in sorted(provider.models.items()):
            result.append((provider_name, model_id, spec.display_name))
    return result
