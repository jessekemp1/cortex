#!/usr/bin/env python3
"""
Batch API Fallback Handler

Provides graceful degradation from batch to sequential processing.
"""

import logging
from typing import Any, Callable, List, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Generic return type


class BatchFallback:
    """Handles fallback from batch to sequential processing"""

    @staticmethod
    def process_with_fallback(
        items: List[Any],
        batch_processor: Callable,
        sequential_processor: Callable,
        feature: str = "unknown",
    ) -> Any:
        """
        Process items with automatic fallback.

        Flow:
        1. Try batch processor if batch is enabled
        2. On error, fall back to sequential
        3. Log all fallbacks for monitoring

        Args:
            items: Items to process
            batch_processor: Function that processes via batch API
            sequential_processor: Function that processes sequentially
            feature: Feature name for logging

        Returns:
            Result from either batch or sequential processor

        Raises:
            Exception: If both batch and sequential processing fail
        """
        from batch_config import BatchConfig

        feature_display = feature.title()

        # Step 1: Check if batch is enabled
        if not BatchConfig.is_batch_enabled(feature):
            logger.debug(f"{feature_display}: Batch disabled, using sequential")
            return sequential_processor(items)

        # Step 2: Try batch processing
        try:
            logger.info(f"{feature_display}: Processing {len(items)} items via batch API")
            result = batch_processor(items)
            logger.info(f"{feature_display}: Batch completed successfully")
            return result

        except Exception as e:
            logger.warning(
                f"{feature_display}: Batch processing failed ({type(e).__name__}: {e}), "
                f"falling back to sequential"
            )

            # Step 3: Fall back to sequential
            if not BatchConfig.should_fallback_on_error():
                logger.error(f"{feature_display}: Fallback disabled, re-raising exception")
                raise

            try:
                logger.debug(f"{feature_display}: Executing sequential processing")
                result = sequential_processor(items)
                logger.info(f"{feature_display}: Sequential processing completed")
                return result

            except Exception as seq_error:
                logger.error(
                    f"{feature_display}: Both batch and sequential processing failed. "
                    f"Sequential error: {type(seq_error).__name__}: {seq_error}"
                )
                raise

    @staticmethod
    def safe_batch_call(batch_func: Callable, sequential_func: Callable, *args, **kwargs) -> Any:
        """
        Wrapper for single function call with batch/sequential fallback.

        Usage:
            result = BatchFallback.safe_batch_call(
                batch_generate_recommendations,
                sequential_generate_recommendations,
                projects=projects,
                goals=goals
            )
        """
        from batch_config import BatchConfig

        if not BatchConfig.should_fallback_on_error():
            # No fallback, just call batch
            return batch_func(*args, **kwargs)

        try:
            return batch_func(*args, **kwargs)
        except Exception as e:
            logger.warning(
                f"Batch call failed: {type(e).__name__}: {e}, falling back to sequential"
            )
            return sequential_func(*args, **kwargs)
