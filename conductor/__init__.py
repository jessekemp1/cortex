"""
Cortex Conductor - Multi-Provider AI Model Router

Routes AI requests to the optimal provider+model based on use case,
cost, latency, and capability. Tracks spending and enforces budgets.

Usage:
    from cortex.conductor import route, call, async_call, get_costs

    # Just get routing recommendation
    decision = route("classify this request", use_case="classification")

    # Route AND execute (sync)
    response = call("What category is this?", use_case="classification")

    # Route AND execute (async — native httpx.AsyncClient, no thread pool)
    response = await async_call("What category is this?", use_case="classification")

    # Check spending
    costs = get_costs()
"""

# Re-export public API from caller module
try:
    from cortex.conductor.caller import (
        _create_provider,
        _get_cost_tracker,
        _get_router,
        async_call,
        call,
        get_budget_remaining,
        get_costs,
        get_savings,
        route,
    )
    from cortex.conductor.models import RoutingDecision, RoutingRequest
    from cortex.conductor.cost_tracker import CostTracker
    from cortex.conductor.providers.base import (
        ChatMessage,
        CompletionResponse,
        ProviderError,
    )
except ImportError:
    from .caller import (  # type: ignore[no-redef]
        _create_provider,
        _get_cost_tracker,
        _get_router,
        async_call,
        call,
        get_budget_remaining,
        get_costs,
        get_savings,
        route,
    )
    from .models import RoutingDecision, RoutingRequest  # type: ignore[no-redef]
    from .cost_tracker import CostTracker  # type: ignore[no-redef]
    from .providers.base import (  # type: ignore[no-redef]
        ChatMessage,
        CompletionResponse,
        ProviderError,
    )

__all__ = [
    "route",
    "call",
    "async_call",
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
