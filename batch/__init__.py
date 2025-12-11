"""
Cortex Batch API Integration

Provides batch processing capabilities for research queue and other async operations.
All features are optional and default to disabled for safety.

Features:
- Research queue batching: Process multiple research requests in one batch
- Morning briefing batching: Batch recommendation generation (Phase 2)
- Learning system batching: Batch insights generation (Phase 3)
"""

from .batch_api_client import (
    BatchAPIClient,
    BatchRequest,
    BatchResult,
    BatchAPIError,
    BatchSubmissionError,
    BatchTimeoutError,
    BatchResultError,
)

from .batch_config import BatchConfig
from .batch_fallback import BatchFallback
from .research_batcher import ResearchBatcher

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
]
