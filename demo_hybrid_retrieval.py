#!/usr/bin/env python3
"""
Demo script for Hybrid Retrieval System.

Demonstrates the capabilities of the hybrid BM25 + embedding retrieval system.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent))

from intelligence.embeddings_client import EmbeddingsClient
from intelligence.memory.hybrid_retriever import HybridRetriever
from intelligence.memory.pattern_indexer import Pattern


def create_demo_patterns():
    """Create demo patterns for testing."""
    return [
        Pattern(
            id="proj1:abc123",
            project="VortexV2",
            commit_hash="abc123",
            commit_date=datetime(2024, 1, 1),
            title="Fix async database connection",
            description="Fixed database connection pool for asynchronous operations using asyncpg",
            files_changed=["db/pool.py", "db/async_client.py"],
            keywords={"async", "database", "connection", "pool", "fix", "asyncpg"},
            pattern_type="fix",
        ),
        Pattern(
            id="proj2:def456",
            project="AlphaArena",
            commit_hash="def456",
            commit_date=datetime(2024, 1, 2),
            title="Implement concurrent task processing",
            description="Added parallel task processing using asyncio and worker pools",
            files_changed=["tasks/processor.py", "tasks/queue.py"],
            keywords={"concurrent", "parallel", "async", "task", "processing", "worker"},
            pattern_type="feature",
        ),
        Pattern(
            id="proj1:ghi789",
            project="VortexV2",
            commit_hash="ghi789",
            commit_date=datetime(2024, 1, 3),
            title="Add API rate limiting middleware",
            description="Implemented rate limiting for REST API endpoints to prevent abuse",
            files_changed=["api/middleware.py", "api/limiter.py"],
            keywords={"api", "rate", "limiting", "middleware", "rest", "throttle"},
            pattern_type="feature",
        ),
        Pattern(
            id="proj3:jkl012",
            project="Cortex",
            commit_hash="jkl012",
            commit_date=datetime(2024, 1, 4),
            title="Fix memory leak in LRU cache",
            description="Fixed memory leak in LRU cache implementation by properly handling weak references",
            files_changed=["cache/lru.py"],
            keywords={"memory", "leak", "cache", "fix", "lru", "references"},
            pattern_type="fix",
        ),
        Pattern(
            id="proj4:mno345",
            project="AlphaArena",
            commit_hash="mno345",
            commit_date=datetime(2024, 1, 5),
            title="Optimize database query performance",
            description="Optimized slow database queries by adding indexes and query rewriting",
            files_changed=["models/trading.py", "db/queries.py"],
            keywords={"database", "optimize", "performance", "query", "index"},
            pattern_type="refactor",
        ),
    ]


def demo_bm25_search(retriever, query):
    """Demo BM25-only search."""
    print(f"\n{'='*80}")
    print("BM25-ONLY SEARCH (alpha=0.0)")
    print(f"Query: '{query}'")
    print(f"{'='*80}")

    results = retriever.search(query, limit=3, alpha=0.0)

    for i, (pattern, score) in enumerate(results, 1):
        print(f"\n{i}. [{score:.3f}] {pattern.project} - {pattern.title}")
        print(f"   Type: {pattern.pattern_type}")
        print(f"   Description: {pattern.description[:80]}...")
        print(f"   Keywords: {', '.join(list(pattern.keywords)[:5])}")


def demo_embedding_search(retriever, query):
    """Demo embedding-only search."""
    print(f"\n{'='*80}")
    print("EMBEDDING-ONLY SEARCH (alpha=1.0)")
    print(f"Query: '{query}'")
    print(f"{'='*80}")

    results = retriever.search(query, limit=3, alpha=1.0)

    for i, (pattern, score) in enumerate(results, 1):
        print(f"\n{i}. [{score:.3f}] {pattern.project} - {pattern.title}")
        print(f"   Type: {pattern.pattern_type}")
        print(f"   Description: {pattern.description[:80]}...")
        print(f"   Keywords: {', '.join(list(pattern.keywords)[:5])}")


def demo_hybrid_search(retriever, query):
    """Demo hybrid search."""
    print(f"\n{'='*80}")
    print("HYBRID SEARCH (alpha=0.5)")
    print(f"Query: '{query}'")
    print(f"{'='*80}")

    results = retriever.search(query, limit=3, alpha=0.5)

    for i, (pattern, score) in enumerate(results, 1):
        print(f"\n{i}. [{score:.3f}] {pattern.project} - {pattern.title}")
        print(f"   Type: {pattern.pattern_type}")
        print(f"   Description: {pattern.description[:80]}...")
        print(f"   Keywords: {', '.join(list(pattern.keywords)[:5])}")


def demo_synonym_detection(retriever):
    """Demo synonym detection via semantic search."""
    print(f"\n{'='*80}")
    print("SYNONYM DETECTION TEST")
    print(f"{'='*80}")

    # Test queries that use different terminology
    queries = [
        ("async database connection", "Direct keyword match"),
        ("asynchronous database pool", "Synonym: asynchronous = async"),
        ("concurrent processing", "Synonym: concurrent = parallel = async"),
        ("slow query optimization", "Synonym: slow query = performance = optimize"),
    ]

    for query, description in queries:
        print(f"\n{description}")
        print(f"Query: '{query}'")
        print("-" * 80)

        results = retriever.search(query, limit=2, alpha=0.7)  # Favor embeddings

        for i, (pattern, score) in enumerate(results, 1):
            print(f"  {i}. [{score:.3f}] {pattern.title}")


def main():
    """Run hybrid retrieval demo."""
    print("=" * 80)
    print("HYBRID RETRIEVAL SYSTEM DEMO")
    print("=" * 80)

    # Create demo patterns
    patterns = create_demo_patterns()
    print(f"\nCreated {len(patterns)} demo patterns")

    # Initialize embeddings client
    try:
        print("Initializing embeddings client...")
        embeddings_client = EmbeddingsClient()
        print(f"Embeddings dimension: {embeddings_client.get_embedding_dimension()}")
        print(f"API available: {embeddings_client.is_api_available()}")
    except Exception as e:
        print(f"Warning: Could not initialize embeddings client: {e}")
        print("Using fallback hash-based embeddings")
        embeddings_client = EmbeddingsClient()

    # Create hybrid retriever
    print("\nInitializing hybrid retriever...")
    retriever = HybridRetriever(patterns, embeddings_client)

    # Show stats
    stats = retriever.get_stats()
    print("\nRetriever stats:")
    print(f"  Patterns: {stats['pattern_count']}")
    print(f"  Embeddings available: {stats['embeddings_available']}")
    print(f"  Embeddings cached: {stats['embeddings_cached']}")
    print(f"  Embedding dimension: {stats['embedding_dimension']}")

    # Demo different search modes
    query = "async database connection"

    demo_bm25_search(retriever, query)
    demo_embedding_search(retriever, query)
    demo_hybrid_search(retriever, query)

    # Demo synonym detection
    demo_synonym_detection(retriever)

    # Performance comparison
    print(f"\n{'='*80}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*80}")

    import time

    # BM25 timing
    start = time.time()
    for _ in range(100):
        retriever.search("database", limit=5, alpha=0.0)
    bm25_time = (time.time() - start) / 100 * 1000

    # Embedding timing
    start = time.time()
    for _ in range(100):
        retriever.search("database", limit=5, alpha=1.0)
    embedding_time = (time.time() - start) / 100 * 1000

    # Hybrid timing
    start = time.time()
    for _ in range(100):
        retriever.search("database", limit=5, alpha=0.5)
    hybrid_time = (time.time() - start) / 100 * 1000

    print("\nAverage search latency (100 iterations):")
    print(f"  BM25 only:     {bm25_time:.2f}ms")
    print(f"  Embedding only: {embedding_time:.2f}ms")
    print(f"  Hybrid:        {hybrid_time:.2f}ms")

    print(f"\n{'='*80}")
    print("Demo complete!")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
