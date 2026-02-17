#!/usr/bin/env python3
"""
Cortex Conductor - Multi-Provider AI Model Router

Routes AI requests to the optimal provider+model based on use case,
cost, latency, and capability. Tracks spending and enforces budgets.

Usage:
    from cortex.conductor import route, call, get_costs

    # Just get routing recommendation
    decision = route("classify this request", use_case="classification")

    # Route AND execute
    response = call("What category is this?", use_case="classification")

    # Check spending
    costs = get_costs()

    # Savings vs Anthropic-only
    savings = get_savings()
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _load_dotenv() -> None:
    """Load API keys from cortex/.env if not already in environment."""
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


# Handle both package imports and daemon-context relative imports.
# Daemon processes may have unpredictable sys.path configurations.
# See MEMORY.md: "Daemon Import Chain Fragility"
try:
    from cortex.conductor.models import RoutingDecision, RoutingRequest
    from cortex.conductor.cost_tracker import CostTracker
    from cortex.conductor.providers.base import (
        ChatMessage,
        CompletionResponse,
        ProviderError,
    )
except ImportError:
    from .models import RoutingDecision, RoutingRequest  # type: ignore[no-redef]
    from .cost_tracker import CostTracker  # type: ignore[no-redef]
    from .providers.base import (  # type: ignore[no-redef]
        ChatMessage,
        CompletionResponse,
        ProviderError,
    )

logger = logging.getLogger(__name__)

# Module-level singletons (lazy-initialized)
_cost_tracker: Optional[CostTracker] = None
_router: Optional[Any] = None  # ConductorRouter, once router.py exists


def _get_cost_tracker() -> CostTracker:
    """Get or create the module-level CostTracker singleton."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def _get_router() -> Any:
    """Get or create the module-level ConductorRouter singleton.

    Returns None if router module is not yet implemented.
    """
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

# Map provider name -> (module_attr, env_var, default_base_url, default_model)
_PROVIDER_REGISTRY: Dict[str, Dict[str, str]] = {
    "groq": {
        "env": "GROQ_API_KEY",
        "default_model": "llama-3.1-8b-instant",
    },
    "xai": {
        "env": "XAI_API_KEY",
        "default_model": "grok-3-fast",
    },
    "minimax": {
        "env": "MINIMAX_API_KEY",
        "default_model": "MiniMax-M1-80k",
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
    "deepseek": {
        "env": "DEEPSEEK_API_KEY",
        "fallback_env": "OPENAI_API_KEY",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
    },
}


def _create_provider(provider_name: str) -> Any:
    """Instantiate a provider client by name.

    API keys are loaded from environment variables. DeepSeek falls
    back to OPENAI_API_KEY if DEEPSEEK_API_KEY is not set.

    Raises:
        ProviderError: If the required API key is not set.
        ImportError: If the provider module is not available.
    """
    try:
        try:
            from cortex.conductor.providers import (
                GroqProvider,
                XAIProvider,
                MiniMaxProvider,
                OpenAIProvider,
            )
        except ImportError:
            from .providers import (  # type: ignore[no-redef]
                GroqProvider,
                XAIProvider,
                MiniMaxProvider,
                OpenAIProvider,
            )
    except ImportError as e:
        raise ImportError(f"Provider module not available: {e}") from e

    # Try to import AnthropicProvider; it may not exist yet
    AnthropicProvider = None
    try:
        try:
            from cortex.conductor.providers.anthropic_provider import AnthropicProvider  # type: ignore[no-redef]
        except ImportError:
            from .providers.anthropic_provider import AnthropicProvider  # type: ignore[no-redef]
    except (ImportError, ModuleNotFoundError):
        pass

    info = _PROVIDER_REGISTRY.get(provider_name)
    if info is None:
        raise ProviderError(provider_name, 0, f"Unknown provider: {provider_name}")

    env_var = info["env"]
    api_key = os.environ.get(env_var, "")

    # DeepSeek fallback
    if not api_key and "fallback_env" in info:
        api_key = os.environ.get(info["fallback_env"], "")

    if not api_key:
        raise ProviderError(provider_name, 0, f"{env_var} not set (provider: {provider_name})")

    if provider_name == "groq":
        return GroqProvider(api_key=api_key)
    elif provider_name == "xai":
        return XAIProvider(api_key=api_key)
    elif provider_name == "minimax":
        return MiniMaxProvider(api_key=api_key)
    elif provider_name == "openai":
        return OpenAIProvider(api_key=api_key)
    elif provider_name == "deepseek":
        base_url = info.get("base_url", "https://api.deepseek.com")
        return OpenAIProvider(api_key=api_key, base_url=base_url)
    elif provider_name == "anthropic":
        if AnthropicProvider is None:
            raise ProviderError("anthropic", 0, "AnthropicProvider module not available")
        return AnthropicProvider(api_key=api_key)
    else:
        raise ProviderError(provider_name, 0, f"No client for provider: {provider_name}")


def _default_route(
    task_description: str,
    use_case: str = "",
    context_tokens: int = 0,
    batch_eligible: bool = False,
    priority: str = "medium",
) -> RoutingDecision:
    """Fallback routing when ConductorRouter is not available.

    Uses simple rule-based matching: maps use cases to the cheapest
    capable provider. This is intentionally conservative -- the real
    ConductorRouter will do better once implemented.
    """
    # Use-case to (provider, model) mapping -- cheapest capable option
    USE_CASE_MAP: Dict[str, tuple[str, str, str]] = {
        "classification": ("groq", "llama-3.1-8b-instant", "Llama 3.1 8B"),
        "quick_qa": ("groq", "llama-3.1-8b-instant", "Llama 3.1 8B"),
        "pattern_learning": ("groq", "llama-3.1-8b-instant", "Llama 3.1 8B"),
        "documentation": ("groq", "llama-3.1-8b-instant", "Llama 3.1 8B"),
        "code_review": ("deepseek", "deepseek-chat", "DeepSeek Chat"),
        "test_generation": ("deepseek", "deepseek-chat", "DeepSeek Chat"),
        "long_context": ("xai", "grok-3-fast", "Grok 3 Fast"),
        "research": ("xai", "grok-3-fast", "Grok 3 Fast"),
        "interactive_coding": ("deepseek", "deepseek-chat", "DeepSeek Chat"),
        "security_audit": ("anthropic", "claude-sonnet-4-20250514", "Sonnet 4"),
        "architecture": ("anthropic", "claude-sonnet-4-20250514", "Sonnet 4"),
    }

    provider, model_id, display = USE_CASE_MAP.get(
        use_case,
        ("groq", "llama-3.1-8b-instant", "Llama 3.1 8B"),
    )

    # Determine fallback
    fallback_provider = "anthropic" if provider != "anthropic" else "openai"
    fallback_model = (
        "claude-sonnet-4-20250514" if fallback_provider == "anthropic" else "gpt-4o-mini"
    )

    return RoutingDecision(
        provider=provider,
        model_id=model_id,
        display_name=display,
        reasoning=f"Default routing for use_case={use_case or 'general'}",
        estimated_cost=0.0,
        fallback_provider=fallback_provider,
        fallback_model_id=fallback_model,
        confidence=0.7,
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
    """Get optimal provider+model for a task.

    If ConductorRouter is available, delegates to it. Otherwise uses
    a simple rule-based fallback.

    Args:
        task_description: Free-text description of the task.
        use_case: Explicit use case (e.g., "classification", "code_review").
        context_tokens: Estimated input token count.
        batch_eligible: Whether the request can be batched.
        priority: "high", "medium", or "low".

    Returns:
        A RoutingDecision with provider, model, reasoning, and fallback.
    """
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

    return _default_route(
        task_description=task_description,
        use_case=use_case,
        context_tokens=context_tokens,
        batch_eligible=batch_eligible,
        priority=priority,
    )


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

    This is the primary integration point for the conductor:
    1. Routes to get the best provider+model (or uses overrides).
    2. Instantiates the provider client.
    3. Executes the completion.
    4. Records cost via CostTracker.
    5. On failure, retries with the fallback provider.

    Args:
        prompt: The user prompt text.
        use_case: Use case for routing (e.g., "classification").
        system: Optional system message.
        model_override: Force a specific model ID (bypasses routing).
        provider_override: Force a specific provider (bypasses routing).
        max_tokens: Maximum output tokens.
        temperature: Sampling temperature.

    Returns:
        CompletionResponse with content, tokens, cost, and latency.

    Raises:
        ProviderError: If both primary and fallback providers fail.
    """
    tracker = _get_cost_tracker()

    # Step 1: Determine provider + model
    if provider_override and model_override:
        decision = RoutingDecision(
            provider=provider_override,
            model_id=model_override,
            display_name=model_override,
            reasoning="Manual override",
            estimated_cost=0.0,
            fallback_provider="anthropic",
            fallback_model_id="claude-sonnet-4-20250514",
            confidence=1.0,
        )
    else:
        decision = route(prompt, use_case=use_case)
        if provider_override:
            decision.provider = provider_override
        if model_override:
            decision.model_id = model_override

    # Step 2: Build messages
    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))

    # Step 3: Try primary provider
    primary_error: Optional[Exception] = None
    try:
        provider_client = _create_provider(decision.provider)
        response = provider_client.complete(
            messages=messages,
            model=decision.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Step 4: Record cost
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

    except (ProviderError, ImportError, Exception) as e:
        primary_error = e
        logger.warning(
            "Primary provider %s failed: %s. Trying fallback %s.",
            decision.provider,
            e,
            decision.fallback_provider,
        )

    # Step 5: Try fallback provider
    try:
        fallback_client = _create_provider(decision.fallback_provider)
        response = fallback_client.complete(
            messages=messages,
            model=decision.fallback_model_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Record cost for fallback
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

    except Exception as fallback_error:
        logger.error(
            "Fallback provider %s also failed: %s",
            decision.fallback_provider,
            fallback_error,
        )
        # Re-raise the primary error with fallback context
        raise ProviderError(
            decision.provider,
            0,
            f"Primary ({decision.provider}): {primary_error}; "
            f"Fallback ({decision.fallback_provider}): {fallback_error}",
        ) from primary_error


def get_costs(date: Optional[str] = None) -> Dict[str, float]:
    """Get daily spending by provider.

    Args:
        date: ISO date string (YYYY-MM-DD). Defaults to today UTC.

    Returns:
        Dict mapping provider name to total spend, plus a "total" key.
    """
    return _get_cost_tracker().get_daily_spend(date=date)


def get_savings() -> Dict[str, Any]:
    """Get savings report vs Anthropic-only routing.

    Returns:
        Dict with actual_spend, anthropic_equivalent, savings_usd,
        savings_pct, and per-use-case breakdown.
    """
    return _get_cost_tracker().get_savings_report()


def get_budget_remaining() -> float:
    """Get remaining daily budget in USD."""
    return _get_cost_tracker().get_budget_remaining()


__all__ = [
    "route",
    "call",
    "get_costs",
    "get_savings",
    "get_budget_remaining",
    "CostTracker",
    "RoutingDecision",
    "RoutingRequest",
    "ChatMessage",
    "CompletionResponse",
    "ProviderError",
]
