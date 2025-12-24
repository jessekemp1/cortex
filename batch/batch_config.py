#!/usr/bin/env python3
"""
Batch API Configuration

Manages feature flags and batch settings.
All features default to DISABLED for safety.
"""

import os


class BatchConfig:
    """Configuration for batch API features"""

    # Feature flags - all default to False for safety
    @classmethod
    def is_batch_enabled(cls, feature: str = "research") -> bool:
        """
        Check if batch API is enabled for a feature.

        Args:
            feature: "research", "recommendations", "learning", "decisions"

        Returns:
            bool: True if enabled, False if disabled (default)
        """
        env_var = f"CORTEX_BATCH_{feature.upper()}_ENABLED"
        enabled = os.getenv(env_var, "false").lower() == "true"
        return enabled

    @classmethod
    def is_any_batch_enabled(cls) -> bool:
        """Check if any batch feature is enabled"""
        return any(
            cls.is_batch_enabled(f)
            for f in ["research", "recommendations", "learning", "decisions"]
        )

    # Batch settings - conservative defaults
    @classmethod
    def get_max_requests(cls) -> int:
        """Max requests per batch (API limit: 10,000)"""
        return int(os.getenv("CORTEX_BATCH_MAX_REQUESTS", "10000"))

    @classmethod
    def get_timeout_minutes(cls) -> int:
        """Max wait time for batch results (default: 24 hours)"""
        return int(os.getenv("CORTEX_BATCH_TIMEOUT_MINUTES", "1440"))

    @classmethod
    def get_retry_attempts(cls) -> int:
        """Number of retries on failure"""
        return int(os.getenv("CORTEX_BATCH_RETRY_ATTEMPTS", "3"))

    @classmethod
    def should_fallback_on_error(cls) -> bool:
        """Should fall back to sequential on batch error?"""
        return os.getenv("CORTEX_BATCH_FALLBACK_ON_ERROR", "true").lower() == "true"

    @classmethod
    def get_poll_interval(cls) -> int:
        """Batch polling interval in seconds"""
        return int(os.getenv("CORTEX_BATCH_POLL_INTERVAL", "5"))

    @classmethod
    def get_min_items_for_batch(cls, feature: str = "research") -> int:
        """Minimum number of items to warrant batch processing"""
        return int(os.getenv("CORTEX_BATCH_MIN_ITEMS", "1"))

    @classmethod
    def get_cache_hours(cls) -> int:
        """Cache batch results for N hours"""
        return int(os.getenv("CORTEX_BATCH_CACHE_HOURS", "24"))
