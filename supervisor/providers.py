"""
Multi-provider registry — manages provider configs, health, and circuit breakers.

Loads provider definitions from ~/.cortex/providers.yaml (user-editable).
Tracks per-provider health via circuit breaker pattern:
  3 consecutive failures → 5min backoff → auto-recover on success.

Supports both API providers (Anthropic, DeepSeek, Groq) and local providers
(Ollama, LM Studio) for offline operation.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path.home() / ".cortex" / "providers.yaml"

# Circuit breaker constants
_CB_FAILURE_THRESHOLD = 3  # Consecutive failures before tripping
_CB_BACKOFF_SECONDS = 300  # 5 minutes


@dataclass
class ModelSpec:
    """Specification for a single model from a provider."""

    model_id: str  # LiteLLM model string: "deepseek/deepseek-chat"
    tier: str  # "haiku" | "sonnet" | "opus"
    max_tokens: int = 4096
    supports_tools: bool = True
    cost_input_per_1m: float = 0.0  # $ per 1M input tokens
    cost_output_per_1m: float = 0.0  # $ per 1M output tokens
    task_affinity: List[str] = field(default_factory=list)  # e.g. ["code", "reasoning"]


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str  # "anthropic", "deepseek", "groq", "ollama"
    api_key_env: str  # Environment variable name for API key
    base_url: Optional[str] = None  # For OpenAI-compatible endpoints
    models: Dict[str, ModelSpec] = field(default_factory=dict)
    max_concurrent: int = 5
    supports_tools: bool = True
    supports_batch: bool = False
    enabled: bool = True
    provider_type: str = "api"  # "api" or "local"
    priority: int = 0  # Lower = preferred fallback. Negative = last resort (local).


@dataclass
class _CircuitBreaker:
    """Per-provider circuit breaker state."""

    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False  # True = tripped, rejecting requests


class ProviderRegistry:
    """Loads provider configs, validates API keys, tracks health.

    Usage::

        registry = ProviderRegistry()
        models = registry.get_models_for_tier("sonnet")
        # → [("deepseek", ModelSpec(...)), ("anthropic", ModelSpec(...))]
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._providers: Dict[str, ProviderConfig] = {}
        self._circuit_breakers: Dict[str, _CircuitBreaker] = {}
        self._offline_mode = False
        self._original_enabled: Dict[str, bool] = {}

        if config_path is None:
            self._load_env()
        self._load_config()
        self._validate_keys()

    @staticmethod
    def _load_env() -> None:
        """Load .env file from cortex project root if available.

        Checks cortex/.env and ~/.cortex/.env for API keys that
        aren't already in the environment.
        """
        env_paths = [
            Path.home() / "Dev" / "cortex" / ".env",
            Path.home() / ".cortex" / ".env",
        ]
        for env_path in env_paths:
            if not env_path.exists():
                continue
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    # Don't overwrite existing env vars
                    if key and not os.environ.get(key):
                        os.environ[key] = value
            except OSError:
                continue

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def offline_mode(self) -> bool:
        return self._offline_mode

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Look up a provider by name."""
        return self._providers.get(name)

    def get_models_for_tier(self, tier: str) -> List[Tuple[str, ModelSpec]]:
        """Return (provider_name, ModelSpec) pairs for a tier, sorted by cost ascending.

        Only returns models from enabled, healthy providers.
        """
        candidates: List[Tuple[str, ModelSpec, float]] = []

        for pname, pconfig in self._providers.items():
            if not pconfig.enabled:
                continue
            if not self.is_healthy(pname):
                continue
            for model_name, spec in pconfig.models.items():
                if spec.tier == tier:
                    cost = spec.cost_input_per_1m + spec.cost_output_per_1m
                    candidates.append((pname, spec, cost))

        # Sort by cost ascending (cheapest first)
        candidates.sort(key=lambda x: x[2])
        return [(pname, spec) for pname, spec, _ in candidates]

    def get_all_providers(self) -> Dict[str, ProviderConfig]:
        """Return all registered providers."""
        return dict(self._providers)

    def mark_failure(self, provider: str, model_id: str, error: str) -> None:  # noqa: ARG002
        """Record a failure. 3 consecutive failures trips the circuit breaker."""
        cb = self._circuit_breakers.setdefault(provider, _CircuitBreaker())
        cb.consecutive_failures += 1
        cb.last_failure_time = time.monotonic()

        if cb.consecutive_failures >= _CB_FAILURE_THRESHOLD:
            cb.is_open = True
            log.warning(
                "Circuit breaker OPEN for %s (%s): %d consecutive failures. "
                "Backing off for %ds. Last error: %s",
                provider,
                model_id,
                cb.consecutive_failures,
                _CB_BACKOFF_SECONDS,
                error[:200],
            )

    def mark_success(self, provider: str, model_id: str) -> None:  # noqa: ARG002
        """Reset failure counter on success."""
        cb = self._circuit_breakers.get(provider)
        if cb:
            if cb.is_open:
                log.info("Circuit breaker CLOSED for %s: recovered after success", provider)
            cb.consecutive_failures = 0
            cb.is_open = False

    def is_healthy(self, provider: str) -> bool:
        """Check circuit breaker state. Auto-recovers after backoff period."""
        cb = self._circuit_breakers.get(provider)
        if cb is None:
            return True
        if not cb.is_open:
            return True
        # Check if backoff period has elapsed → half-open (allow one attempt)
        elapsed = time.monotonic() - cb.last_failure_time
        if elapsed >= _CB_BACKOFF_SECONDS:
            log.info(
                "Circuit breaker HALF-OPEN for %s: backoff elapsed (%.0fs), allowing attempt",
                provider,
                elapsed,
            )
            return True
        return False

    def enter_offline_mode(self) -> None:
        """Disable all API providers. Enable only local providers."""
        if self._offline_mode:
            return
        self._offline_mode = True
        self._original_enabled = {n: p.enabled for n, p in self._providers.items()}
        for name, config in self._providers.items():
            if config.provider_type == "api":
                config.enabled = False
            elif config.provider_type == "local":
                config.enabled = True
        log.warning("OFFLINE MODE: All API providers disabled. Using local models only.")

    def exit_offline_mode(self) -> None:
        """Re-enable providers using original config state."""
        if not self._offline_mode:
            return
        self._offline_mode = False
        for name, enabled in self._original_enabled.items():
            if name in self._providers:
                self._providers[name].enabled = enabled
        self._original_enabled.clear()
        log.info("Online mode restored. API providers re-enabled.")

    def detect_connectivity(self) -> bool:
        """Quick check: can we reach any API provider?

        Tries a lightweight HTTP HEAD against each API provider's base URL.
        Returns True if any provider responds within 3s.
        """
        try:
            import httpx
        except ImportError:
            return True  # Can't check, assume online

        for name, config in self._providers.items():
            if config.provider_type != "api" or not config.enabled:
                continue
            url = config.base_url or "https://api.anthropic.com"
            try:
                resp = httpx.head(url, timeout=3.0, follow_redirects=True)
                if resp.status_code < 500:
                    return True
            except Exception:
                continue
        return False

    def estimate_cost(
        self, provider: str, model_id: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost in USD for a dispatch."""
        pconfig = self._providers.get(provider)
        if not pconfig:
            return 0.0
        for spec in pconfig.models.values():
            if spec.model_id == model_id:
                return (
                    spec.cost_input_per_1m * input_tokens / 1_000_000
                    + spec.cost_output_per_1m * output_tokens / 1_000_000
                )
        return 0.0

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load provider config from YAML file."""
        if not self._config_path.exists():
            log.info("No providers config at %s, using Anthropic-only defaults", self._config_path)
            self._providers = self._default_anthropic_provider()
            return

        try:
            import yaml
        except ImportError:
            log.warning("PyYAML not available, using Anthropic-only defaults")
            self._providers = self._default_anthropic_provider()
            return

        try:
            raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("Failed to parse %s: %s — using defaults", self._config_path, exc)
            self._providers = self._default_anthropic_provider()
            return

        if not raw or "providers" not in raw:
            self._providers = self._default_anthropic_provider()
            return

        for pname, pdata in raw["providers"].items():
            models: Dict[str, ModelSpec] = {}
            for mname, mdata in (pdata.get("models") or {}).items():
                models[mname] = ModelSpec(
                    model_id=self._build_model_id(pname, mname),
                    tier=mdata.get("tier", "sonnet"),
                    max_tokens=mdata.get("max_tokens", 4096),
                    supports_tools=mdata.get("supports_tools", True),
                    cost_input_per_1m=mdata.get("cost_input", 0.0),
                    cost_output_per_1m=mdata.get("cost_output", 0.0),
                    task_affinity=mdata.get("task_affinity", []),
                )

            self._providers[pname] = ProviderConfig(
                name=pname,
                api_key_env=pdata.get("api_key_env", ""),
                base_url=pdata.get("base_url"),
                models=models,
                max_concurrent=pdata.get("max_concurrent", 5),
                supports_tools=pdata.get("supports_tools", True),
                supports_batch=pdata.get("supports_batch", False),
                enabled=pdata.get("enabled", True),
                provider_type=pdata.get("type", "api"),
                priority=pdata.get("priority", 0),
            )

        log.info(
            "Loaded %d providers: %s",
            len(self._providers),
            ", ".join(self._providers.keys()),
        )

    def _validate_keys(self) -> None:
        """Check that required API keys exist in environment. Disable providers without keys."""
        for name, config in self._providers.items():
            if config.provider_type == "local":
                continue  # Local providers don't need API keys
            if not config.api_key_env:
                continue
            if not os.environ.get(config.api_key_env):
                config.enabled = False
                log.warning(
                    "Provider %s disabled: %s not set in environment",
                    name,
                    config.api_key_env,
                )

    @staticmethod
    def _build_model_id(provider: str, model_name: str) -> str:
        """Build a LiteLLM-compatible model ID string.

        Anthropic models pass through as-is (handled by anthropic SDK).
        Others get prefixed for LiteLLM: "deepseek/deepseek-chat".
        """
        if provider == "anthropic":
            return model_name  # "claude-opus-4-6" etc.
        if provider == "ollama":
            return f"ollama/{model_name}"
        if provider == "groq":
            return f"groq/{model_name}"
        # Default: provider/model format for LiteLLM
        return f"{provider}/{model_name}"

    @staticmethod
    def _default_anthropic_provider() -> Dict[str, ProviderConfig]:
        """Fallback: Anthropic-only provider config."""
        return {
            "anthropic": ProviderConfig(
                name="anthropic",
                api_key_env="ANTHROPIC_API_KEY",  # pragma: allowlist secret
                models={
                    "claude-opus-4-6": ModelSpec(
                        model_id="claude-opus-4-6",
                        tier="opus",
                        cost_input_per_1m=15.0,
                        cost_output_per_1m=75.0,
                    ),
                    "claude-sonnet-4-6": ModelSpec(
                        model_id="claude-sonnet-4-6",
                        tier="sonnet",
                        cost_input_per_1m=3.0,
                        cost_output_per_1m=15.0,
                    ),
                    "claude-haiku-4-5-20251001": ModelSpec(
                        model_id="claude-haiku-4-5-20251001",
                        tier="haiku",
                        cost_input_per_1m=0.25,
                        cost_output_per_1m=1.25,
                    ),
                },
                supports_batch=True,
            )
        }
