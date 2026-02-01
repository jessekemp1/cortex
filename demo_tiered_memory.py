#!/usr/bin/env python3
"""
Demo script for three-tier memory architecture.

Demonstrates:
1. Recording items to short-term memory
2. Accessing items and tracking access counts
3. Automatic promotion to working memory
4. Outcome recording and quality scoring
5. Session lifecycle (end_session)
6. Cross-tier querying with weighting
7. Memory statistics
"""

import sys
from datetime import datetime
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent))

from intelligence.memory.tiered_memory import MemoryItem, TieredMemory


def print_section(title: str):
    """Print section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def demo_session():
    """Demonstrate a full session lifecycle."""
    print_section("1. Initialize Tiered Memory System")

    tm = TieredMemory(short_term_max=50, working_retention_days=7)
    print("✓ Initialized with:")
    print(f"  - Short-term capacity: 50 items")
    print(f"  - Working memory retention: 7 days")
    print(f"  - Long-term memory: PatternMemory")

    print_section("2. Record Items (Session Start)")

    # Simulate recording patterns during a session
    patterns = [
        {
            "id": "error_handling_1",
            "title": "Error handling pattern",
            "description": "Try-catch with logging",
        },
        {
            "id": "api_retry_1",
            "title": "API retry pattern",
            "description": "Exponential backoff retry",
        },
        {
            "id": "cache_pattern_1",
            "title": "Cache invalidation pattern",
            "description": "LRU cache with TTL",
        },
        {
            "id": "async_pattern_1",
            "title": "Async workflow pattern",
            "description": "Async task queue with workers",
        },
        {
            "id": "db_pattern_1",
            "title": "Database migration pattern",
            "description": "Zero-downtime schema migration",
        },
    ]

    for pattern in patterns:
        item = MemoryItem(
            id=pattern["id"],
            content=pattern,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )
        tm.record(item)
        print(f"✓ Recorded: {pattern['title']}")

    stats = tm.get_stats()
    print(f"\n📊 Short-term memory: {stats['short_term']['item_count']} items")

    print_section("3. Access Patterns (During Session)")

    # Simulate frequently accessing certain patterns
    frequently_used = ["error_handling_1", "api_retry_1"]

    for _ in range(4):  # Access 4 times
        for item_id in frequently_used:
            tm.short_term.get(item_id)

    print("Accessed frequently:")
    for item_id in frequently_used:
        item = tm.short_term.get(item_id)
        if item:
            print(f"  - {item.content['title']} (accessed {item.access_count} times)")

    print_section("4. Record Outcomes")

    # Simulate outcomes for some patterns
    outcomes = [
        ("error_handling_1", "success", 0.95),
        ("api_retry_1", "success", 0.88),
        ("cache_pattern_1", "partial", 0.65),
        ("async_pattern_1", "failed", 0.30),
    ]

    for item_id, outcome, quality in outcomes:
        tm.update_outcome(item_id, outcome, quality)
        print(f"✓ {item_id}: {outcome} (quality: {quality:.2f})")

    print_section("5. Query Across Tiers")

    # Query for error handling patterns
    print("Query: 'error handling'")
    results = tm.query("error handling", limit=5)

    for item, score, tier in results:
        if tier == "short_term":
            print(f"  [{tier}] {item.content['title']}")
            print(f"    Score: {score:.3f} (1.5x tier weight)")
            print(f"    Access count: {item.access_count}")
        else:
            print(f"  [{tier}] {item.title if hasattr(item, 'title') else 'N/A'}")
            print(f"    Score: {score:.3f}")

    print_section("6. End Session (Consolidation)")

    print("Processing end-of-session consolidation...")
    tm.end_session()

    stats = tm.get_stats()
    print(f"\n✓ Short-term cleared: {stats['short_term']['item_count']} items")
    print(f"✓ Working memory: {stats['working']['item_count']} items")
    print("\nFrequently accessed items promoted to working memory:")

    # Check which items were promoted
    for item_id in frequently_used:
        item = tm.working.get(item_id)
        if item:
            print(f"  - {item.content['title']}")
            print(f"    Access count: {item.access_count}")
            print(f"    Outcome: {item.outcome}")
            print(f"    Quality: {item.quality_score:.2f}" if item.quality_score else "")

    print_section("7. Memory Statistics")

    stats = tm.get_stats()

    print("Short-Term Memory:")
    print(f"  Items: {stats['short_term']['item_count']}")
    print(f"  Capacity: {stats['short_term']['max_items']}")
    print(f"  Usage: {stats['short_term']['capacity_used']:.1%}")

    print("\nWorking Memory:")
    print(f"  Items: {stats['working']['item_count']}")
    print(f"  Items with outcomes: {stats['working']['items_with_outcomes']}")
    print(f"  Retention: {stats['working']['retention_days']} days")

    print("\nLong-Term Memory:")
    lt_stats = stats['long_term']
    print(f"  Total patterns: {lt_stats.get('total_patterns', 0)}")
    print(f"  Projects: {lt_stats.get('projects', 0)}")

    print("\nPromotion Rules:")
    pr = stats['promotion_rules']
    print(f"  Working access threshold: {pr['working_access_threshold']}")
    print(f"  Long-term quality threshold: {pr['long_term_quality_threshold']}")

    print_section("8. Cross-Session Persistence")

    print("Starting new session (new TieredMemory instance)...")
    tm2 = TieredMemory()

    print("\nRetrieving previously promoted items:")
    for item_id in frequently_used:
        item = tm2.working.get(item_id)
        if item:
            print(f"✓ Found: {item.content['title']}")
            print(f"  Last accessed: {item.last_accessed.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Access count: {item.access_count}")

    print_section("Summary")

    print("Three-Tier Memory Architecture Demonstrated:")
    print("\n✓ Short-term: Session-scoped, limited capacity, fast access")
    print("  - Holds current session items")
    print("  - LRU eviction at capacity")
    print("  - 1.5x query weight (most relevant)")

    print("\n✓ Working: 7-day retention, SQLite-backed, frequently accessed")
    print("  - Persists across sessions")
    print("  - Automatic promotion from short-term")
    print("  - 1.2x query weight")

    print("\n✓ Long-term: Permanent, indexed, historical patterns")
    print("  - Uses existing PatternMemory")
    print("  - Hybrid retrieval (BM25 + embeddings)")
    print("  - 1.0x query weight")

    print("\n✓ Automatic Promotion:")
    print("  - Short-term → Working: 2+ accesses or has outcome")
    print("  - Working → Long-term: Success + quality > 0.7")

    print("\n✓ Session Lifecycle:")
    print("  - Records items to short-term")
    print("  - Tracks access patterns")
    print("  - Updates outcomes and quality")
    print("  - Consolidates on session end")

    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60 + "\n")


def demo_query_weighting():
    """Demonstrate query weighting across tiers."""
    print_section("Query Weighting Demonstration")

    tm = TieredMemory()

    # Add identical pattern to short-term and working
    st_item = MemoryItem(
        id="st_test",
        content={"title": "test pattern", "type": "test"},
        created_at=datetime.now(),
        last_accessed=datetime.now(),
    )
    tm.short_term.add(st_item)

    wm_item = MemoryItem(
        id="wm_test",
        content={"title": "test pattern", "type": "test"},
        created_at=datetime.now(),
        last_accessed=datetime.now(),
    )
    tm.working.add(wm_item)

    print("Added identical patterns to:")
    print("  - Short-term memory (1.5x weight)")
    print("  - Working memory (1.2x weight)")

    print("\nQuery: 'test pattern'")
    results = tm.query("test pattern", limit=10)

    print("\nResults (sorted by weighted score):")
    for item, score, tier in results:
        print(f"  {tier:12} | Score: {score:.4f}")

    print("\n📊 Short-term items have 25% higher scores due to tier weighting")


if __name__ == "__main__":
    demo_session()
    print("\n")
    demo_query_weighting()
