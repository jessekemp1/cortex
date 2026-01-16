"""
Batch Optimization Module
Implements intelligence for maximizing token usage and efficient bin-packing of requests.
"""

import math
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class TokenEstimator:
    """Estimates token counts for text strings."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self._encoding = None
        self._setup_encoding()

    def _setup_encoding(self):
        """Try to setup tiktoken encoding, fallback to approximation if failed."""
        try:
            import tiktoken

            # Map Claude models to cl100k_base (closest approximation for now)
            self._encoding = tiktoken.get_encoding("cl100k_base")
            self.mode = "tiktoken"
        except ImportError:
            self._encoding = None
            self.mode = "approximation"
            logger.warning("tiktoken_not_found_using_approximation")

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0

        if self.mode == "tiktoken" and self._encoding:
            try:
                return len(self._encoding.encode(text))
            except Exception:
                # Fallback on error
                return self._approximate(text)
        else:
            return self._approximate(text)

    def _approximate(self, text: str) -> int:
        """Approximate tokens (rough heuristic: 4 chars ~= 1 token)."""
        return math.ceil(len(text) / 4)


class BatchBucket:
    """Represents a single batch request to be submitted."""

    def __init__(self, max_items: int = 10000, max_total_tokens: int = 200000):
        self.max_items = max_items
        self.max_total_tokens = max_total_tokens
        self.items: List[Dict[str, Any]] = []
        self.current_tokens = 0

    @property
    def is_full(self) -> bool:
        return len(self.items) >= self.max_items or self.current_tokens >= self.max_total_tokens

    def can_fit(self, item_tokens: int) -> bool:
        """Check if an item with given tokens can fit."""
        if len(self.items) >= self.max_items:
            return False
        if self.current_tokens + item_tokens > self.max_total_tokens:
            return False
        return True

    def add(self, item: Dict[str, Any], tokens: int):
        """Add item to bucket."""
        self.items.append(item)
        self.current_tokens += tokens


class BatchOptimizer:
    """Optimizes list of pending items into efficient batches."""

    def __init__(self, token_estimator: Optional[TokenEstimator] = None):
        self.estimator = token_estimator or TokenEstimator()

    def optimize(
        self,
        items: List[Dict[str, Any]],
        max_batch_size: int = 10000,
        token_budget: int = 200000,
    ) -> List[List[Dict[str, Any]]]:
        """
        Pack items into optimized batches using First-Fit Decreasing algorithm.

        Args:
            items: List of dictionary items (must have 'prompt' key)
            max_batch_size: Max items per batch
            token_budget: Max tokens per batch

        Returns:
            List of batches (each batch is a list of items)
        """
        # 1. Calculate tokens for all items
        item_costs = []
        for item in items:
            prompt = item.get("prompt", "")
            cost = self.estimator.count(prompt)
            # Add overhead (approx 10 tokens for JSON structure/roles)
            cost += 10
            item_costs.append((item, cost))

        # 2. Sort by size (Descending)
        # This is the "Decreasing" part of First-Fit Decreasing
        item_costs.sort(key=lambda x: x[1], reverse=True)

        # 3. Pack into buckets
        buckets: List[BatchBucket] = []

        for item, cost in item_costs:
            placed = False

            # Try to fit in existing buckets (First-Fit)
            for bucket in buckets:
                if bucket.can_fit(cost):
                    bucket.add(item, cost)
                    placed = True
                    break

            # If didn't fit, create new bucket
            if not placed:
                new_bucket = BatchBucket(max_items=max_batch_size, max_total_tokens=token_budget)
                # Check if item itself is too big for a single empty bucket
                if not new_bucket.can_fit(cost):
                    logger.warning(
                        "item_too_large_skipped",
                        item_id=item.get("id"),
                        cost=cost,
                        limit=token_budget,
                    )
                    continue

                new_bucket.add(item, cost)
                buckets.append(new_bucket)

        # 4. Extract items from buckets
        result_batches = [b.items for b in buckets]

        logger.info(
            "optimization_complete",
            input_items=len(items),
            output_batches=len(result_batches),
            efficiency=(
                f"{len(items)/len(result_batches):.1f} items/batch" if result_batches else "0"
            ),
        )

        return result_batches
