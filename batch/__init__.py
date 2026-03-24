"""
Cortex Batch API Integration

Provides batch processing capabilities for research queue and other async operations.
All features are optional and default to disabled for safety.

Core modules (no external dependencies):
- SubscriptionOptimizer: Track and optimize subscription token utilization
- UtilizationLearningEngine: Closed-loop learning for utilization patterns
- RequestRouter: Route requests to batch or interactive processing
- check_utilization: Convenience hook for session integration

Batch processors (require anthropic SDK):
- BatchAPIClient, ResearchBatcher, RecommendationBatcher, etc.
"""

# Core modules — always available (stdlib only)
from .subscription_optimizer import SubscriptionOptimizer, check_utilization
from .utilization_learning import UtilizationLearningEngine
from .routing_framework import RequestRouter, RouteDecision, RouteType

# Batch processors — require anthropic SDK, import gracefully
try:
    from .batch_api_client import (
        BatchAPIClient,
        BatchAPIError,
        BatchRequest,
        BatchResult,
        BatchResultError,
        BatchSubmissionError,
        BatchTimeoutError,
    )
    from .batch_config import BatchConfig
    from .batch_fallback import BatchFallback
    from .briefing_batcher import BriefingContext, InsightBatcher, RecommendationBatcher
    from .learning_batcher import LearningBatcher, LearningContext
    from .research_batcher import ResearchBatcher
    from .weather_batcher import WeatherBackfillBatcher, WeatherBackfillContext

    _BATCH_API_AVAILABLE = True
except ImportError:
    _BATCH_API_AVAILABLE = False

__all__ = [
    # Always available
    "SubscriptionOptimizer",
    "check_utilization",
    "UtilizationLearningEngine",
    "RequestRouter",
    "RouteDecision",
    "RouteType",
    # Available when anthropic SDK installed
    "BatchAPIClient",
    "BatchRequest",
    "BatchResult",
    "BatchAPIError",
    "BatchSubmissionError",
    "BatchTimeoutError",
    "BatchResultError",
    "BatchConfig",
    "BatchFallback",
    "ResearchBatcher",
    "RecommendationBatcher",
    "InsightBatcher",
    "BriefingContext",
    "LearningBatcher",
    "LearningContext",
    "WeatherBackfillBatcher",
    "WeatherBackfillContext",
]
