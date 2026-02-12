"""
Context Optimizer: Lost-in-the-Middle optimization for LLM prompts.

Research shows LLMs attend more to the beginning and end of context,
"losing" information in the middle. This module reorders context items
for optimal attention distribution.

Based on: "AI Engineering" by Chip Huyen, Chapter 4 (Prompt Engineering)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CategoryType(str, Enum):
    """Context item categories with priority rankings."""

    INSTRUCTION = "instruction"  # System instructions - highest priority
    EXAMPLE = "example"  # Few-shot examples - high priority
    DATA = "data"  # Retrieved context/data - medium priority
    HISTORY = "history"  # Conversation history - lowest priority


@dataclass
class ContextItem:
    """A piece of context with importance metadata."""

    content: str
    importance: float  # 0.0-1.0, higher = more important
    category: CategoryType  # Category determines positioning
    tokens: Optional[int] = None  # Estimated token count
    source: Optional[str] = None  # Source identifier (file, API, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def __post_init__(self):
        """Validate and normalize importance score."""
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError(f"Importance must be in [0.0, 1.0], got {self.importance}")

        # Auto-estimate tokens if not provided
        if self.tokens is None:
            self.tokens = self._estimate_tokens(self.content)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (4 chars per token average)."""
        return len(text) // 4


@dataclass
class OptimizationStrategy:
    """Configuration for context optimization strategy."""

    # Position attention weights from research
    start_weight: float = 1.0  # Full attention
    middle_weight: float = 0.6  # Reduced attention
    end_weight: float = 0.9  # High attention (recency)

    # Category priorities (higher = more important)
    category_priority: Dict[CategoryType, float] = field(
        default_factory=lambda: {
            CategoryType.INSTRUCTION: 1.0,  # Critical - always at start
            CategoryType.EXAMPLE: 0.8,  # Important - near start
            CategoryType.DATA: 0.6,  # Medium - at end (recency)
            CategoryType.HISTORY: 0.4,  # Low - in middle (acceptable loss)
        }
    )

    # Distribution ratios (how to split items across positions)
    start_ratio: float = 0.33  # Top 1/3 to start
    middle_ratio: float = 0.33  # Bottom 1/3 to middle
    end_ratio: float = 0.34  # Middle 1/3 to end

    # Whether to add position markers
    use_markers: bool = True

    # Separator between items
    separator: str = "\n\n"


class ContextOptimizer:
    """Optimize context ordering for LLM attention patterns."""

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        strategy: Optional[OptimizationStrategy] = None,
    ):
        """
        Initialize context optimizer.

        Args:
            max_tokens: Optional token limit for context
            strategy: Optimization strategy (uses default if None)
        """
        self.max_tokens = max_tokens
        self.strategy = strategy or OptimizationStrategy()

    def optimize_context(self, items: List[ContextItem]) -> List[ContextItem]:
        """
        Reorder context items for optimal LLM attention.

        Strategy:
        - High importance items → START (highest attention)
        - Medium importance items → END (high attention, recency)
        - Low importance items → MIDDLE (acceptable attention loss)

        Args:
            items: List of context items to optimize

        Returns:
            Reordered list optimized for attention
        """
        if not items:
            return []

        # Too few items to optimize
        if len(items) <= 3:
            return sorted(items, key=lambda x: x.importance, reverse=True)

        # Sort by importance (descending)
        sorted_items = sorted(items, key=lambda x: x.importance, reverse=True)

        # Calculate split points - dividing items into thirds by importance
        n = len(sorted_items)
        # Top third (highest importance) → START
        # Middle third (medium importance) → END
        # Bottom third (lowest importance) → MIDDLE (lost attention acceptable)

        third = n // 3
        remainder = n % 3

        # Distribute remainder to end (most benefit from extra items)
        start_count = third
        end_count = third + remainder

        # Most important third → START
        start_items = sorted_items[:start_count]

        # Middle importance third → END (recency helps)
        end_items = sorted_items[start_count : start_count + end_count]

        # Least important third → MIDDLE (will lose attention)
        middle_items = sorted_items[start_count + end_count :]

        # Combine: start + middle + end
        return start_items + middle_items + end_items

    def optimize_by_category(self, items: List[ContextItem]) -> List[ContextItem]:
        """
        Reorder based on category priorities.

        Order: instructions → examples → history → data
        This puts critical info at start, retrieved context at end.

        Within each category, items are sorted by importance.

        Args:
            items: List of context items to optimize

        Returns:
            Reordered list optimized by category
        """
        if not items:
            return []

        # Group by category
        by_category: Dict[CategoryType, List[ContextItem]] = {cat: [] for cat in CategoryType}

        for item in items:
            by_category[item.category].append(item)

        # Sort within each category by importance
        for category_items in by_category.values():
            category_items.sort(key=lambda x: x.importance, reverse=True)

        # Combine in priority order:
        # 1. Instructions (start - critical)
        # 2. Examples (start - important for few-shot)
        # 3. Data (end - benefits from recency)
        # 4. History (middle - least important)

        result = []
        result.extend(by_category[CategoryType.INSTRUCTION])
        result.extend(by_category[CategoryType.EXAMPLE])
        result.extend(by_category[CategoryType.HISTORY])
        result.extend(by_category[CategoryType.DATA])

        return result

    def add_position_markers(self, items: List[ContextItem]) -> List[ContextItem]:
        """
        Add markers to help LLM attention.

        Markers:
        - [IMPORTANT] for critical items (importance >= 0.8)
        - [CONTEXT] for retrieved data
        - Section numbers for structure

        Args:
            items: List of context items

        Returns:
            Items with markers added to content
        """
        marked_items = []

        for i, item in enumerate(items, 1):
            content = item.content
            markers = []

            # Add category marker first
            if item.category == CategoryType.INSTRUCTION:
                markers.append("[INSTRUCTION]")
            elif item.category == CategoryType.EXAMPLE:
                markers.append(f"[EXAMPLE {i}]")
            elif item.category == CategoryType.DATA:
                markers.append("[CONTEXT]")
            # History gets no category marker unless important

            # Add importance marker
            if item.importance >= 0.8:
                markers.append("[IMPORTANT]")

            # Apply markers
            if markers:
                content = " ".join(markers) + " " + content

            # Create new item with marked content
            marked_item = ContextItem(
                content=content,
                importance=item.importance,
                category=item.category,
                tokens=item.tokens,
                source=item.source,
                metadata=item.metadata,
            )
            marked_items.append(marked_item)

        return marked_items

    def format_context(
        self,
        items: List[ContextItem],
        include_markers: bool = True,
        separator: Optional[str] = None,
    ) -> str:
        """
        Format optimized context items into a single string.

        Args:
            items: List of context items to format
            include_markers: Whether to add position markers
            separator: String to use between items (uses strategy default if None)

        Returns:
            Formatted context string
        """
        if not items:
            return ""

        # Add markers if requested
        if include_markers and self.strategy.use_markers:
            items = self.add_position_markers(items)

        # Use provided separator or default
        sep = separator if separator is not None else self.strategy.separator

        # Join items
        return sep.join(item.content for item in items)

    def truncate_to_limit(
        self,
        items: List[ContextItem],
        max_tokens: Optional[int] = None,
    ) -> List[ContextItem]:
        """
        Truncate context to fit token limit.

        Strategy: Remove from middle (lowest attention) first.
        Preserves start and end items as much as possible.

        Args:
            items: List of context items
            max_tokens: Token limit (uses instance limit if None)

        Returns:
            Truncated list fitting within token limit
        """
        limit = max_tokens or self.max_tokens
        if not limit or not items:
            return items

        # Calculate total tokens
        total_tokens = sum(item.tokens or 0 for item in items)

        if total_tokens <= limit:
            return items  # Already within limit

        # Need to truncate - remove from middle
        # Calculate split points (assume items already optimized)
        n = len(items)
        start_count = int(n * self.strategy.start_ratio)
        end_count = int(n * self.strategy.end_ratio)

        # Keep start and end items, truncate middle
        start_items = items[:start_count]
        end_items = items[-end_count:] if end_count > 0 else []
        middle_items = items[start_count : len(items) - end_count]

        # Calculate tokens for start and end
        start_tokens = sum(item.tokens or 0 for item in start_items)
        end_tokens = sum(item.tokens or 0 for item in end_items)
        remaining_tokens = limit - start_tokens - end_tokens

        # Add middle items until we hit the limit
        kept_middle = []
        middle_tokens = 0

        for item in middle_items:
            item_tokens = item.tokens or 0
            if middle_tokens + item_tokens <= remaining_tokens:
                kept_middle.append(item)
                middle_tokens += item_tokens
            else:
                break

        return start_items + kept_middle + end_items

    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (4 chars per token average).

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return ContextItem._estimate_tokens(text)


def optimize_prompt_context(
    context_items: List[Dict],
    max_tokens: Optional[int] = None,
    strategy: str = "importance",
    include_markers: bool = True,
) -> str:
    """
    Convenience function to optimize context for a prompt.

    Args:
        context_items: List of dicts with 'content', 'importance', 'category'
                      Optional: 'tokens', 'source', 'metadata'
        max_tokens: Optional token limit
        strategy: Optimization strategy - "importance" or "category"
        include_markers: Whether to add position markers

    Returns:
        Optimized context string ready for LLM prompt

    Example:
        >>> context = [
        ...     {"content": "System instructions...", "importance": 1.0, "category": "instruction"},
        ...     {"content": "Example 1...", "importance": 0.8, "category": "example"},
        ...     {"content": "Retrieved data...", "importance": 0.6, "category": "data"},
        ... ]
        >>> optimized = optimize_prompt_context(context, max_tokens=1000)
    """
    # Convert dicts to ContextItem objects
    items = []
    for item_dict in context_items:
        # Handle string category or CategoryType enum
        category = item_dict.get("category", "data")
        if isinstance(category, str):
            category = CategoryType(category)

        item = ContextItem(
            content=item_dict["content"],
            importance=item_dict.get("importance", 0.5),
            category=category,
            tokens=item_dict.get("tokens"),
            source=item_dict.get("source"),
            metadata=item_dict.get("metadata", {}),
        )
        items.append(item)

    # Create optimizer
    optimizer = ContextOptimizer(max_tokens=max_tokens)

    # Apply optimization strategy
    if strategy == "importance":
        optimized = optimizer.optimize_context(items)
    elif strategy == "category":
        optimized = optimizer.optimize_by_category(items)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    # Truncate if needed
    if max_tokens:
        optimized = optimizer.truncate_to_limit(optimized, max_tokens)

    # Format and return
    return optimizer.format_context(optimized, include_markers=include_markers)
