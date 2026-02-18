#!/usr/bin/env python3
"""
Context Optimizer Demo - Lost-in-the-Middle Optimization

Demonstrates how to use the context optimizer in practice.
Shows before/after examples and integration patterns.
"""

from context_optimizer import (
    CategoryType,
    ContextItem,
    ContextOptimizer,
    optimize_prompt_context,
)


def demo_basic_usage():
    """Demo: Basic usage of context optimizer."""
    print("=" * 60)
    print("DEMO 1: Basic Context Optimization")
    print("=" * 60)

    # Create context items with varying importance
    items = [
        ContextItem(
            content="You are a helpful AI assistant for software development.",
            importance=1.0,
            category=CategoryType.INSTRUCTION,
        ),
        ContextItem(
            content="Example: User asks 'how to handle errors' -> Suggest try/except with logging",
            importance=0.8,
            category=CategoryType.EXAMPLE,
        ),
        ContextItem(
            content="User has been working on error handling for 2 hours",
            importance=0.3,
            category=CategoryType.HISTORY,
        ),
        ContextItem(
            content="Pattern found: AsyncIO error handling requires different approach",
            importance=0.7,
            category=CategoryType.DATA,
        ),
        ContextItem(
            content="Related pattern: Circuit breaker for API calls",
            importance=0.6,
            category=CategoryType.DATA,
        ),
    ]

    # Optimize using importance-based strategy
    optimizer = ContextOptimizer()
    optimized = optimizer.optimize_context(items)

    print("\nOriginal order:")
    for i, item in enumerate(items, 1):
        print(f"  {i}. [{item.category.value}] (imp={item.importance}) {item.content[:50]}...")

    print("\nOptimized order (importance-based):")
    for i, item in enumerate(optimized, 1):
        position = "START" if i <= 2 else "MIDDLE" if i <= 3 else "END"
        print(
            f"  {i}. [{position}] [{item.category.value}] (imp={item.importance}) {item.content[:50]}..."
        )

    print("\nFormatted with markers:")
    formatted = optimizer.format_context(optimized, include_markers=True)
    print(formatted[:300] + "...")


def demo_category_optimization():
    """Demo: Category-based optimization for structured prompts."""
    print("\n" + "=" * 60)
    print("DEMO 2: Category-Based Optimization")
    print("=" * 60)

    # Simulate a briefing generation scenario
    context_items = [
        {
            "content": "Generate a daily briefing with priorities, blockers, and quick wins.",
            "importance": 1.0,
            "category": "instruction",
        },
        {
            "content": "Current date: 2026-02-01, Time: Morning (9:15 AM)",
            "importance": 0.9,
            "category": "data",
        },
        {
            "content": "Active goals: Complete Vortex integration (A), Review Alpha Arena tests (B)",
            "importance": 0.8,
            "category": "data",
        },
        {
            "content": "Example briefing: 'Priority: Complete API integration. Blocker: Missing test data.'",
            "importance": 0.8,
            "category": "example",
        },
        {
            "content": "Recent activity: 5 commits to cortex, 2 to vortex in last 24h",
            "importance": 0.6,
            "category": "data",
        },
        {
            "content": "Previous briefings showed pattern of morning focus on complex tasks",
            "importance": 0.4,
            "category": "history",
        },
    ]

    # Use convenience function with category strategy
    result = optimize_prompt_context(
        context_items,
        max_tokens=500,
        strategy="category",
        include_markers=True,
    )

    print("\nCategory-optimized context:")
    print(result)

    print("\n✓ Instructions and examples at START (high attention)")
    print("✓ Data at END (benefits from recency)")
    print("✓ History in MIDDLE (lowest importance)")


def demo_token_truncation():
    """Demo: Token limit handling."""
    print("\n" + "=" * 60)
    print("DEMO 3: Token Limit Truncation")
    print("=" * 60)

    # Create many context items that exceed limit
    items = [
        ContextItem(
            content=f"Important instruction: {i}" * 20,
            importance=1.0,
            category=CategoryType.INSTRUCTION,
        )
        for i in range(2)
    ]

    # Add many data items
    for i in range(10):
        items.append(
            ContextItem(
                content=f"Data item {i}: " + "Some retrieved context " * 10,
                importance=0.5,
                category=CategoryType.DATA,
            )
        )

    optimizer = ContextOptimizer(max_tokens=300)
    print(f"\nTotal items: {len(items)}")
    print(f"Total tokens: {sum(item.tokens for item in items)}")

    # Optimize and truncate
    optimized = optimizer.optimize_context(items)
    truncated = optimizer.truncate_to_limit(optimized, max_tokens=300)

    print(f"After optimization & truncation: {len(truncated)} items")
    print(f"Final tokens: {sum(item.tokens for item in truncated)}")
    print("\n✓ Preserved high-importance items at START and END")
    print("✓ Dropped middle items to fit token budget")


def demo_briefing_integration():
    """Demo: Integration pattern for briefing.py."""
    print("\n" + "=" * 60)
    print("DEMO 4: Briefing.py Integration Pattern")
    print("=" * 60)

    print("\nIntegration code example:")
    print(
        """
    # In briefing.py, before generating prompt:

    from cortex.intelligence.context_optimizer import optimize_prompt_context

    # Assemble context items with importance scores
    context_items = [
        {
            "content": system_instructions,
            "importance": 1.0,
            "category": "instruction",
        },
        {
            "content": f"Current date: {date}",
            "importance": 0.9,
            "category": "data",
        },
        {
            "content": goals_summary,
            "importance": 0.8,
            "category": "data",
        },
        {
            "content": recent_activity,
            "importance": 0.6,
            "category": "data",
        },
        {
            "content": temporal_context,
            "importance": 0.5,
            "category": "data",
        },
    ]

    # Optimize context before sending to LLM
    optimized_context = optimize_prompt_context(
        context_items,
        max_tokens=2000,  # Claude's context window
        strategy="category",  # Instructions first, then data
        include_markers=True,  # Add [IMPORTANT] markers
    )

    # Use optimized context in prompt
    prompt = f"{optimized_context}\\n\\nGenerate the daily briefing."
    response = llm.generate(prompt)
    """
    )

    print("✓ High-value context at START and END")
    print("✓ Automatic token management")
    print("✓ Markers help LLM attention")


def demo_bridge_integration():
    """Demo: Integration pattern for bridge.py."""
    print("\n" + "=" * 60)
    print("DEMO 5: Bridge.py Integration Pattern")
    print("=" * 60)

    print("\nIntegration code example:")
    print(
        """
    # In bridge.py get_context() method:

    from cortex.intelligence.context_optimizer import (
        ContextItem,
        CategoryType,
        ContextOptimizer,
    )

    def get_context(self, query: str, limit: int = 5) -> List[Dict]:
        # Get predictions from context intelligence
        predictions = self.context_intel.predict_context(
            keywords=query.split(),
            limit=limit * 2,  # Get extra, will optimize later
        )

        # Convert to ContextItem objects with importance
        context_items = []
        for pred in predictions:
            item = ContextItem(
                content=f"{pred.title}: {pred.description}",
                importance=pred.confidence,  # Use confidence as importance
                category=CategoryType.DATA,
                source=str(pred.file_path) if pred.file_path else None,
            )
            context_items.append(item)

        # Add query as instruction
        query_item = ContextItem(
            content=f"Query: {query}",
            importance=1.0,
            category=CategoryType.INSTRUCTION,
        )
        context_items.insert(0, query_item)

        # Optimize context ordering
        optimizer = ContextOptimizer(max_tokens=1000)
        optimized = optimizer.optimize_context(context_items)

        # Return optimized items (limit to requested count)
        return [
            {
                "content": item.content,
                "importance": item.importance,
                "source": item.source,
            }
            for item in optimized[:limit]
        ]
    """
    )

    print("✓ Highest confidence patterns at START")
    print("✓ Query context preserved")
    print("✓ Seamless integration with existing code")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║  Context Optimizer Demo: Lost-in-the-Middle Optimization  ║")
    print("╚" + "=" * 58 + "╝")

    demo_basic_usage()
    demo_category_optimization()
    demo_token_truncation()
    demo_briefing_integration()
    demo_bridge_integration()

    print("\n" + "=" * 60)
    print("SUCCESS: All demos completed")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("  1. High-importance items → START (full attention)")
    print("  2. Medium-importance items → END (recency benefit)")
    print("  3. Low-importance items → MIDDLE (acceptable loss)")
    print("  4. Category-based ordering for structured prompts")
    print("  5. Automatic token truncation preserves critical info")
    print("\nNext Steps:")
    print("  - Integrate into briefing.py for daily briefings")
    print("  - Integrate into bridge.py for context queries")
    print("  - Add optional optimization to prompt templates")
    print("  - A/B test optimized vs. unoptimized contexts")


if __name__ == "__main__":
    main()
