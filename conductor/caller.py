"""
Conductor execution engine.

Contains route(), call(), provider factory, cost wrappers, and singleton
management. Extracted from __init__.py to keep the package facade thin.
"""

import logging
import os
from typing import Any, Dict, Optional

try:
    from cortex.conductor.config import PROVIDERS, ROUTING_TABLE, get_pricing
    from cortex.conductor.models import RoutingDecision, RoutingRequest
    from cortex.conductor.cost_tracker import CostTracker
    from cortex.conductor.providers.base import (
        ChatMessage,
        CompletionResponse,
        ProviderError,
    )
except ImportError:
    from .config import PROVIDERS, ROUTING_TABLE, get_pricing  # type: ignore[no-redef]
    from .models import RoutingDecision, RoutingRequest  # type: ignore[no-redef]
    from .cost_tracker import CostTracker  # type: ignore[no-redef]
    from .providers.base import (  # type: ignore[no-redef]
        ChatMessage,
        CompletionResponse,
        ProviderError,
    )


def _load_dotenv() -> None:
    """Load API keys from cortex/.env if not already in environment."""
    from pathlib import Path

    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and not os.environ.get(key):
            os.environ[key] = value


_load_dotenv()

logger = logging.getLogger(__name__)

# Module-level singletons (lazy-initialized)
_cost_tracker: Optional[CostTracker] = None
_router: Optional[Any] = None


def _get_cost_tracker() -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def _get_router() -> Any:
    global _router
    if _router is None:
        try:
            try:
                from cortex.conductor.router import ConductorRouter
            except ImportError:
                from .router import ConductorRouter  # type: ignore[no-redef]
            _router = ConductorRouter()
        except (ImportError, ModuleNotFoundError):
            logger.debug("ConductorRouter not available; using default routing")
            _router = None
    return _router


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def _create_provider(provider_name: str) -> Any:
    """Instantiate a provider client by name, using config.py as source of truth."""
    info = PROVIDERS.get(provider_name)
    if info is None:
        raise ProviderError(provider_name, 0, f"Unknown provider: {provider_name}")

    env_var = info["env_var"]
    api_key = os.environ.get(env_var, "")
    if not api_key and "fallback_env" in info:
        api_key = os.environ.get(info["fallback_env"], "")
    if not api_key:
        raise ProviderError(provider_name, 0, f"{env_var} not set (provider: {provider_name})")

    if info["api_type"] == "anthropic":
        try:
            from cortex.conductor.providers.anthropic_provider import AnthropicProvider
        except ImportError:
            from .providers.anthropic_provider import AnthropicProvider  # type: ignore[no-redef]
        return AnthropicProvider(api_key=api_key, base_url=info["base_url"])
    else:
        try:
            from cortex.conductor.providers.openai_compat import OpenAICompatProvider
        except ImportError:
            from .providers.openai_compat import OpenAICompatProvider  # type: ignore[no-redef]
        return OpenAICompatProvider(
            provider_name=provider_name,
            api_key=api_key,
            base_url=info["base_url"],
            pricing=get_pricing(provider_name),
            timeout=info.get("timeout", 120.0),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def route(
    task_description: str,
    use_case: str = "",
    context_tokens: int = 0,
    batch_eligible: bool = False,
    priority: str = "medium",
) -> RoutingDecision:
    """Get optimal provider+model for a task."""
    router = _get_router()

    if router is not None:
        request = RoutingRequest(
            task_description=task_description,
            use_case=use_case,
            context_tokens=context_tokens,
            batch_eligible=batch_eligible,
            priority=priority,
        )
        return router.route(request)

    # Fallback: use ROUTING_TABLE directly
    rt = ROUTING_TABLE.get(
        use_case,
        ROUTING_TABLE.get(
            "quick_qa",
            ("groq", "llama-3.1-8b-instant", "anthropic", "claude-haiku-4-5-20251001"),
        ),
    )
    return RoutingDecision(
        provider=rt[0],
        model_id=rt[1],
        display_name=rt[1],
        reasoning=f"Default routing for use_case={use_case or 'general'}",
        estimated_cost=0.0,
        fallback_provider=rt[2],
        fallback_model_id=rt[3],
        confidence=0.7,
    )


def _execute_and_record(
    provider_name: str,
    model_id: str,
    messages: list,
    use_case: str,
    max_tokens: int,
    temperature: float,
    tracker: CostTracker,
) -> CompletionResponse:
    """Execute a completion and record the cost. Raises on failure."""
    provider_client = _create_provider(provider_name)
    response = provider_client.complete(
        messages=messages,
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    tracker.record(
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        use_case=use_case,
        latency_ms=response.latency_ms,
    )
    return response


async def _async_execute_and_record(
    provider_name: str,
    model_id: str,
    messages: list,
    use_case: str,
    max_tokens: int,
    temperature: float,
    tracker: CostTracker,
) -> CompletionResponse:
    """Async execute a completion and record the cost. Raises on failure."""
    provider_client = _create_provider(provider_name)
    response = await provider_client.async_complete(
        messages=messages,
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    tracker.record(
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        use_case=use_case,
        latency_ms=response.latency_ms,
    )
    return response


def call(
    prompt: str,
    use_case: str = "",
    system: str = "",
    model_override: Optional[str] = None,
    provider_override: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> CompletionResponse:
    """Route and execute a request through the optimal provider.

    1. Routes to get the best provider+model (or uses overrides).
    2. Instantiates the provider client.
    3. Executes the completion and records cost.
    4. On failure, retries with the fallback provider.
    """
    tracker = _get_cost_tracker()

    # Determine provider + model
    if provider_override and model_override:
        decision = RoutingDecision(
            provider=provider_override,
            model_id=model_override,
            display_name=model_override,
            reasoning="Manual override",
            estimated_cost=0.0,
            fallback_provider="anthropic",
            fallback_model_id="claude-sonnet-4-5-20250929",
            confidence=1.0,
        )
    else:
        decision = route(prompt, use_case=use_case)
        if provider_override:
            decision.provider = provider_override
        if model_override:
            decision.model_id = model_override

    # Build messages
    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    # Try primary provider
    primary_error: Optional[Exception] = None
    try:
        return _execute_and_record(
            decision.provider,
            decision.model_id,
            messages,
            use_case,
            max_tokens,
            temperature,
            tracker,
        )
    except (ProviderError, ImportError, Exception) as e:
        primary_error = e
        logger.warning(
            "Primary provider %s failed: %s. Trying fallback %s.",
            decision.provider,
            e,
            decision.fallback_provider,
        )

    # Try fallback provider
    try:
        return _execute_and_record(
            decision.fallback_provider,
            decision.fallback_model_id,
            messages,
            use_case,
            max_tokens,
            temperature,
            tracker,
        )
    except Exception as fallback_error:
        logger.error(
            "Fallback provider %s also failed: %s",
            decision.fallback_provider,
            fallback_error,
        )
        raise ProviderError(
            decision.provider,
            0,
            f"Primary ({decision.provider}): {primary_error}; "
            f"Fallback ({decision.fallback_provider}): {fallback_error}",
        ) from primary_error


async def async_call(
    prompt: str,
    use_case: str = "",
    system: str = "",
    model_override: Optional[str] = None,
    provider_override: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> CompletionResponse:
    """Async version of call(). Routes and executes without blocking the event loop."""
    tracker = _get_cost_tracker()

    if provider_override and model_override:
        decision = RoutingDecision(
            provider=provider_override,
            model_id=model_override,
            display_name=model_override,
            reasoning="Manual override",
            estimated_cost=0.0,
            fallback_provider="anthropic",
            fallback_model_id="claude-sonnet-4-5-20250929",
            confidence=1.0,
        )
    else:
        decision = route(prompt, use_case=use_case)
        if provider_override:
            decision.provider = provider_override
        if model_override:
            decision.model_id = model_override

    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    primary_error: Optional[Exception] = None
    try:
        return await _async_execute_and_record(
            decision.provider,
            decision.model_id,
            messages,
            use_case,
            max_tokens,
            temperature,
            tracker,
        )
    except (ProviderError, ImportError, Exception) as e:
        primary_error = e
        logger.warning(
            "Primary provider %s failed: %s. Trying fallback %s.",
            decision.provider,
            e,
            decision.fallback_provider,
        )

    try:
        return await _async_execute_and_record(
            decision.fallback_provider,
            decision.fallback_model_id,
            messages,
            use_case,
            max_tokens,
            temperature,
            tracker,
        )
    except Exception as fallback_error:
        logger.error(
            "Fallback provider %s also failed: %s",
            decision.fallback_provider,
            fallback_error,
        )
        raise ProviderError(
            decision.provider,
            0,
            f"Primary ({decision.provider}): {primary_error}; "
            f"Fallback ({decision.fallback_provider}): {fallback_error}",
        ) from primary_error


def get_costs(date: Optional[str] = None) -> Dict[str, float]:
    """Get daily spending by provider."""
    return _get_cost_tracker().get_daily_spend(date=date)


def get_savings() -> Dict[str, Any]:
    """Get savings report vs Anthropic-only routing."""
    return _get_cost_tracker().get_savings_report()


def get_budget_remaining() -> float:
    """Get remaining daily budget in USD."""
    return _get_cost_tracker().get_budget_remaining()
