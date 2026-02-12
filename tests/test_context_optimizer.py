"""
Tests for Context Optimizer (Lost-in-the-Middle optimization).

Tests cover:
- Importance-based ordering
- Category-based ordering
- Position markers
- Token truncation
- Integration with real prompts
"""

import pytest
from cortex.intelligence.context_optimizer import (
    CategoryType,
    ContextItem,
    ContextOptimizer,
    OptimizationStrategy,
    optimize_prompt_context,
)


class TestContextItem:
    """Test ContextItem dataclass."""

    def test_context_item_creation(self):
        """Test creating a context item with required fields."""
        item = ContextItem(
            content="Test content",
            importance=0.8,
            category=CategoryType.INSTRUCTION,
        )

        assert item.content == "Test content"
        assert item.importance == 0.8
        assert item.category == CategoryType.INSTRUCTION
        assert item.tokens is not None  # Auto-estimated
        assert item.source is None

    def test_context_item_token_estimation(self):
        """Test automatic token estimation."""
        item = ContextItem(
            content="A" * 100,  # 100 chars
            importance=0.5,
            category=CategoryType.DATA,
        )

        # Should estimate ~25 tokens (100 / 4)
        assert item.tokens == 25

    def test_context_item_validation(self):
        """Test importance validation."""
        # Valid importance
        ContextItem(content="test", importance=0.0, category=CategoryType.DATA)
        ContextItem(content="test", importance=1.0, category=CategoryType.DATA)

        # Invalid importance
        with pytest.raises(ValueError):
            ContextItem(content="test", importance=1.5, category=CategoryType.DATA)

        with pytest.raises(ValueError):
            ContextItem(content="test", importance=-0.1, category=CategoryType.DATA)


class TestContextOptimizer:
    """Test ContextOptimizer main functionality."""

    def test_optimizer_initialization(self):
        """Test creating optimizer with custom strategy."""
        strategy = OptimizationStrategy(use_markers=False)
        optimizer = ContextOptimizer(max_tokens=1000, strategy=strategy)

        assert optimizer.max_tokens == 1000
        assert optimizer.strategy == strategy
        assert not optimizer.strategy.use_markers

    def test_optimize_empty_list(self):
        """Test optimizing empty context list."""
        optimizer = ContextOptimizer()
        result = optimizer.optimize_context([])

        assert result == []

    def test_optimize_few_items(self):
        """Test optimizing with 3 or fewer items (no optimization needed)."""
        items = [
            ContextItem("Low", 0.3, CategoryType.HISTORY),
            ContextItem("High", 0.9, CategoryType.INSTRUCTION),
            ContextItem("Med", 0.6, CategoryType.DATA),
        ]

        optimizer = ContextOptimizer()
        result = optimizer.optimize_context(items)

        # Should just sort by importance (descending)
        assert len(result) == 3
        assert result[0].importance == 0.9
        assert result[1].importance == 0.6
        assert result[2].importance == 0.3


class TestImportanceBasedOrdering:
    """Test importance-based context ordering."""

    def test_optimize_by_importance(self):
        """Test that high importance goes to start/end, low to middle."""
        items = [
            ContextItem("Item 1", 0.9, CategoryType.DATA),  # High
            ContextItem("Item 2", 0.8, CategoryType.DATA),  # High
            ContextItem("Item 3", 0.7, CategoryType.DATA),  # High
            ContextItem("Item 4", 0.6, CategoryType.DATA),  # Medium
            ContextItem("Item 5", 0.5, CategoryType.DATA),  # Medium
            ContextItem("Item 6", 0.4, CategoryType.DATA),  # Low
            ContextItem("Item 7", 0.3, CategoryType.DATA),  # Low
            ContextItem("Item 8", 0.2, CategoryType.DATA),  # Low
            ContextItem("Item 9", 0.1, CategoryType.DATA),  # Low
        ]

        optimizer = ContextOptimizer()
        result = optimizer.optimize_context(items)

        assert len(result) == 9

        # Start items (top 33%) should be high importance (0.7-0.9)
        start_items = result[:3]
        # All start items should be from the top importance group
        start_importances = [item.importance for item in start_items]
        assert all(imp >= 0.7 for imp in start_importances)

        # Middle items should be low importance (0.1-0.4)
        middle_items = result[3:6]
        middle_importances = [item.importance for item in middle_items]
        # Middle should have lower importance on average
        assert all(imp <= 0.5 for imp in middle_importances)

        # End items should be medium importance (0.5-0.6)
        end_items = result[6:]
        end_importances = [item.importance for item in end_items]
        # End should be mid-range
        assert all(0.4 <= imp <= 0.7 for imp in end_importances)

    def test_importance_distribution(self):
        """Test that importance-based ordering respects start/middle/end ratios."""
        items = [
            ContextItem(f"Item {i}", importance=(10 - i) / 10.0, category=CategoryType.DATA)
            for i in range(10)
        ]

        optimizer = ContextOptimizer()
        result = optimizer.optimize_context(items)

        # Check distribution ratios (33%, 33%, 34%)
        assert len(result) == 10
        int(10 * 0.33)
        int(10 * 0.33)

        # First 3 should be highest importance
        assert result[0].importance >= 0.8
        assert result[1].importance >= 0.8
        assert result[2].importance >= 0.8


class TestCategoryBasedOrdering:
    """Test category-based context ordering."""

    def test_optimize_by_category(self):
        """Test category-based ordering: instructions → examples → history → data."""
        items = [
            ContextItem("Data 1", 0.6, CategoryType.DATA),
            ContextItem("Instruction 1", 0.9, CategoryType.INSTRUCTION),
            ContextItem("History 1", 0.4, CategoryType.HISTORY),
            ContextItem("Example 1", 0.8, CategoryType.EXAMPLE),
            ContextItem("Data 2", 0.7, CategoryType.DATA),
            ContextItem("Instruction 2", 1.0, CategoryType.INSTRUCTION),
        ]

        optimizer = ContextOptimizer()
        result = optimizer.optimize_by_category(items)

        # Check category order
        categories = [item.category for item in result]
        assert categories == [
            CategoryType.INSTRUCTION,
            CategoryType.INSTRUCTION,
            CategoryType.EXAMPLE,
            CategoryType.HISTORY,
            CategoryType.DATA,
            CategoryType.DATA,
        ]

    def test_category_sorting_within_category(self):
        """Test that items within each category are sorted by importance."""
        items = [
            ContextItem("Instruction Low", 0.7, CategoryType.INSTRUCTION),
            ContextItem("Instruction High", 0.9, CategoryType.INSTRUCTION),
            ContextItem("Example Low", 0.6, CategoryType.EXAMPLE),
            ContextItem("Example High", 0.8, CategoryType.EXAMPLE),
        ]

        optimizer = ContextOptimizer()
        result = optimizer.optimize_by_category(items)

        # Instructions first, sorted by importance
        assert result[0].content == "Instruction High"
        assert result[1].content == "Instruction Low"

        # Then examples, sorted by importance
        assert result[2].content == "Example High"
        assert result[3].content == "Example Low"


class TestPositionMarkers:
    """Test position marker addition."""

    def test_add_markers_important_items(self):
        """Test [IMPORTANT] marker for high-importance items."""
        items = [
            ContextItem("Critical info", 0.9, CategoryType.DATA),
            ContextItem("Normal info", 0.5, CategoryType.DATA),
        ]

        optimizer = ContextOptimizer()
        marked = optimizer.add_position_markers(items)

        assert "[IMPORTANT]" in marked[0].content
        assert "[IMPORTANT]" not in marked[1].content

    def test_add_markers_categories(self):
        """Test category-specific markers."""
        items = [
            ContextItem("System instruction", 0.9, CategoryType.INSTRUCTION),
            ContextItem("Example code", 0.8, CategoryType.EXAMPLE),
            ContextItem("Retrieved data", 0.6, CategoryType.DATA),
            ContextItem("Chat history", 0.4, CategoryType.HISTORY),
        ]

        optimizer = ContextOptimizer()
        marked = optimizer.add_position_markers(items)

        assert "[INSTRUCTION]" in marked[0].content
        assert "[EXAMPLE 2]" in marked[1].content  # Second item in list gets number 2
        assert "[CONTEXT]" in marked[2].content
        # History gets no special marker unless importance >= 0.8

    def test_format_with_markers(self):
        """Test formatting context with markers included."""
        items = [
            ContextItem("Instruction", 0.9, CategoryType.INSTRUCTION),
            ContextItem("Data", 0.6, CategoryType.DATA),
        ]

        optimizer = ContextOptimizer()
        formatted = optimizer.format_context(items, include_markers=True)

        assert "[INSTRUCTION]" in formatted
        assert "[IMPORTANT]" in formatted
        assert "[CONTEXT]" in formatted

    def test_format_without_markers(self):
        """Test formatting context without markers."""
        items = [
            ContextItem("Instruction", 0.9, CategoryType.INSTRUCTION),
            ContextItem("Data", 0.6, CategoryType.DATA),
        ]

        optimizer = ContextOptimizer()
        formatted = optimizer.format_context(items, include_markers=False)

        assert "[INSTRUCTION]" not in formatted
        assert "[IMPORTANT]" not in formatted
        assert "[CONTEXT]" not in formatted
        assert "Instruction" in formatted
        assert "Data" in formatted


class TestTokenTruncation:
    """Test token limit truncation."""

    def test_truncate_no_limit(self):
        """Test truncation with no limit (no-op)."""
        items = [
            ContextItem("A" * 400, 0.9, CategoryType.INSTRUCTION),  # ~100 tokens
            ContextItem("B" * 400, 0.5, CategoryType.DATA),  # ~100 tokens
        ]

        optimizer = ContextOptimizer()  # No max_tokens
        result = optimizer.truncate_to_limit(items)

        assert len(result) == 2

    def test_truncate_within_limit(self):
        """Test truncation when already within limit."""
        items = [
            ContextItem("A" * 100, 0.9, CategoryType.INSTRUCTION),  # ~25 tokens
            ContextItem("B" * 100, 0.5, CategoryType.DATA),  # ~25 tokens
        ]

        optimizer = ContextOptimizer(max_tokens=100)
        result = optimizer.truncate_to_limit(items)

        assert len(result) == 2  # All items kept

    def test_truncate_over_limit(self):
        """Test truncation when over limit (removes middle items)."""
        # Create items with sufficient tokens to force truncation
        items = [
            ContextItem("Start 1" * 100, 0.9, CategoryType.INSTRUCTION),  # ~50 tokens
            ContextItem("Start 2" * 100, 0.8, CategoryType.EXAMPLE),  # ~50 tokens
            ContextItem("Middle 1" * 100, 0.5, CategoryType.HISTORY),  # ~50 tokens
            ContextItem("Middle 2" * 100, 0.4, CategoryType.HISTORY),  # ~50 tokens
            ContextItem("End 1" * 100, 0.7, CategoryType.DATA),  # ~50 tokens
            ContextItem("End 2" * 100, 0.6, CategoryType.DATA),  # ~50 tokens
        ]

        optimizer = ContextOptimizer(max_tokens=150)  # Only room for ~3 items

        # Optimize first to get start/middle/end distribution
        optimized = optimizer.optimize_context(items)
        result = optimizer.truncate_to_limit(optimized, max_tokens=150)

        # Should keep start and end items, drop some middle
        assert len(result) < len(items)

    def test_truncate_preserves_start_and_end(self):
        """Test that truncation preserves start and end items."""
        # Create optimized items (manually arranged)
        start_item = ContextItem("START" * 100, 0.9, CategoryType.INSTRUCTION)  # ~100 tokens
        middle_items = [
            ContextItem(f"MIDDLE{i}" * 50, 0.3, CategoryType.HISTORY)  # ~50 tokens each
            for i in range(10)
        ]
        end_item = ContextItem("END" * 100, 0.7, CategoryType.DATA)  # ~100 tokens

        items = [start_item] + middle_items + [end_item]

        optimizer = ContextOptimizer(max_tokens=300)  # Only room for start, end, and 2 middle
        result = optimizer.truncate_to_limit(items)

        # Start and end should be preserved
        assert result[0].content.startswith("START")
        assert result[-1].content.startswith("END")

        # Some middle items dropped
        assert len(result) < len(items)


class TestIntegration:
    """Test integration with real prompt scenarios."""

    def test_optimize_prompt_context_convenience_function(self):
        """Test convenience function with dict input."""
        context_items = [
            {
                "content": "You are a helpful assistant.",
                "importance": 1.0,
                "category": "instruction",
            },
            {
                "content": "Example: User asks 'hello' -> respond 'Hi there!'",
                "importance": 0.8,
                "category": "example",
            },
            {
                "content": "User message history: ...",
                "importance": 0.4,
                "category": "history",
            },
            {
                "content": "Retrieved context: ...",
                "importance": 0.6,
                "category": "data",
            },
        ]

        result = optimize_prompt_context(context_items, strategy="category")

        # Should format as string
        assert isinstance(result, str)

        # Instructions should be first
        assert result.index("helpful assistant") < result.index("Example:")

        # Data should be after instructions and examples
        assert result.index("Retrieved context") > result.index("Example:")

    def test_optimize_briefing_context(self):
        """Test optimization for briefing generation scenario."""
        # Simulate briefing.py context assembly
        context_items = [
            {
                "content": "Generate a daily briefing with priorities and blockers.",
                "importance": 1.0,
                "category": "instruction",
            },
            {
                "content": "Current date: 2026-02-01",
                "importance": 0.9,
                "category": "data",
            },
            {
                "content": "Active goals: Goal 1 (in progress), Goal 2 (pending)",
                "importance": 0.8,
                "category": "data",
            },
            {
                "content": "Recent commits: 5 commits in cortex, 2 in vortex",
                "importance": 0.6,
                "category": "data",
            },
            {
                "content": "Previous briefings from last week...",
                "importance": 0.3,
                "category": "history",
            },
        ]

        result = optimize_prompt_context(context_items, max_tokens=500, strategy="importance")

        assert isinstance(result, str)
        assert len(result) > 0

        # Critical instruction should be first (markers are [INSTRUCTION] [IMPORTANT])
        assert result.startswith("[INSTRUCTION] [IMPORTANT]")

    def test_optimize_bridge_context_query(self):
        """Test optimization for bridge.py context queries."""
        # Simulate bridge.py get_context() scenario
        context_items = [
            {
                "content": "Search knowledge base for relevant patterns matching the query.",
                "importance": 1.0,
                "category": "instruction",
            },
            {
                "content": "Query: error handling patterns for async operations",
                "importance": 0.9,
                "category": "data",
            },
            {
                "content": "Pattern 1: Try/except with logging...",
                "importance": 0.7,
                "category": "data",
            },
            {
                "content": "Pattern 2: Circuit breaker pattern...",
                "importance": 0.7,
                "category": "data",
            },
            {
                "content": "Pattern 3: Retry with exponential backoff...",
                "importance": 0.6,
                "category": "data",
            },
        ]

        result = optimize_prompt_context(context_items, max_tokens=400, strategy="category")

        # Should preserve all patterns but optimize order
        assert "Pattern 1" in result
        assert "Pattern 2" in result
        assert "Pattern 3" in result

    def test_optimize_with_token_limit(self):
        """Test that token limiting works in real scenario."""
        # Create many context items that exceed limit
        context_items = [
            {
                "content": "INSTRUCTION: " + "A" * 200,  # ~50 tokens
                "importance": 1.0,
                "category": "instruction",
            }
        ]

        # Add many data items
        for i in range(20):
            context_items.append(
                {
                    "content": f"Data item {i}: " + "B" * 100,  # ~25 tokens each
                    "importance": 0.5,
                    "category": "data",
                }
            )

        # Total: ~550 tokens, limit to 200
        result = optimize_prompt_context(
            context_items, max_tokens=200, strategy="importance", include_markers=False
        )

        # Should truncate but keep instruction
        assert "INSTRUCTION" in result

        # Should have dropped some data items
        data_count = result.count("Data item")
        assert data_count < 20


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_content(self):
        """Test handling of empty content."""
        item = ContextItem("", 0.5, CategoryType.DATA)
        assert item.tokens == 0

    def test_very_long_content(self):
        """Test handling of very long content."""
        long_text = "A" * 10000  # 10k chars
        item = ContextItem(long_text, 0.5, CategoryType.DATA)
        assert item.tokens == 2500  # 10000 / 4

    def test_custom_strategy(self):
        """Test using custom optimization strategy."""
        strategy = OptimizationStrategy(
            start_ratio=0.5,  # Half at start
            middle_ratio=0.25,  # Quarter in middle
            end_ratio=0.25,  # Quarter at end
            use_markers=False,
        )

        items = [
            ContextItem(f"Item {i}", importance=(10 - i) / 10.0, category=CategoryType.DATA)
            for i in range(8)
        ]

        optimizer = ContextOptimizer(strategy=strategy)
        result = optimizer.optimize_context(items)

        # Should respect custom ratios
        assert len(result) == 8

    def test_estimate_tokens_method(self):
        """Test token estimation utility method."""
        optimizer = ContextOptimizer()

        assert optimizer.estimate_tokens("") == 0
        assert optimizer.estimate_tokens("test") == 1  # 4 chars / 4 = 1
        assert optimizer.estimate_tokens("a" * 100) == 25  # 100 / 4 = 25
