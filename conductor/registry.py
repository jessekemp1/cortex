#!/usr/bin/env python3
"""
Provider Registry — builds ModelSpec/ProviderConfig from config.py.

Single source of truth lives in config.py. This module provides
typed dataclass wrappers used by the router and other consumers.
"""

from typing import Dict, List

try:
    from cortex.conductor.config import PROVIDERS
    from cortex.conductor.models import ModelSpec, ProviderConfig
except ImportError:
    from .config import PROVIDERS  # type: ignore[no-redef]
    from .models import ModelSpec, ProviderConfig  # type: ignore[no-redef]


def _build_registry() -> Dict[str, ProviderConfig]:
    """Build typed ProviderConfig objects from config.PROVIDERS."""
    result: Dict[str, ProviderConfig] = {}

    for name, prov in PROVIDERS.items():
        models: Dict[str, ModelSpec] = {}
        for model_id, m in prov.get("models", {}).items():
            models[model_id] = ModelSpec(
                model_id=model_id,
                display_name=m["display_name"],
                input_cost_per_mtok=m["input_cost"],
                output_cost_per_mtok=m["output_cost"],
                max_context=m["max_context"],
                max_output=m["max_output"],
                speed_tier=m["speed"],
                strengths=m.get("strengths", []),
            )

        max_ctx = max((m.max_context for m in models.values()), default=0)

        result[name] = ProviderConfig(
            name=name,
            api_key_env=prov["env_var"],
            base_url=prov["base_url"],
            models=models,
            max_context=max_ctx,
            supports_batch=prov.get("supports_batch", False),
        )

    return result


# Module-level singleton
_REGISTRY: Dict[str, ProviderConfig] = _build_registry()


def get_provider(name: str) -> ProviderConfig:
    """Get a provider config by name. Raises KeyError if not found."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown provider '{name}'. Available: {available}")
    return _REGISTRY[name]


def get_all_providers() -> Dict[str, ProviderConfig]:
    """Get all registered providers."""
    return dict(_REGISTRY)


def get_model_spec(provider_name: str, model_id: str) -> ModelSpec:
    """Look up a specific model spec by provider and model ID."""
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
    """Return all (provider, model_id, display_name) tuples."""
    result = []
    for provider_name, provider in sorted(_REGISTRY.items()):
        for model_id, spec in sorted(provider.models.items()):
            result.append((provider_name, model_id, spec.display_name))
    return result
