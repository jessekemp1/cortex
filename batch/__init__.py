"""
Cortex Batch API Integration

Provides batch processing capabilities for research queue and other async operations.
All features are optional and default to disabled for safety.

Batch Processors:
- Research queue batching: Process multiple research requests in one batch (Phase 1)
- Morning briefing batching: Batch recommendation + insight generation (Phase 2)
- Learning system batching: Batch insights generation with file caching (Phase 3)
"""

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

__all__ = [
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
