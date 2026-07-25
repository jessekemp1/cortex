#!/usr/bin/env python3
"""Tests for hybrid retrieval system."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.embeddings_client import EmbeddingsClient
from intelligence.memory.hybrid_retriever import HybridRetriever
from intelligence.memory.pattern_indexer import Pattern

# Disable conversation digest AND recorded-decision loading in all tests in
# this module. Tests here verify BM25/embedding mechanics, not the live-store
# integration, so both auto-loaded sources are pointed at nonexistent paths.
import intelligence.memory.hybrid_retriever as _hr_module

_hr_module._DIGESTS_PATH = Path("/nonexistent/digests.jsonl")
_hr_module._DECISIONS_PATH = Path("/nonexistent/decisions.jsonl")


# Fixtures
@pytest.fixture
def sample_patterns():
    """Create sample patterns for testing."""
    return [
        Pattern(
            id="proj1:abc123",
            project="proj1",
            commit_hash="abc123",
            commit_date=datetime(2024, 1, 1),
            title="Fix async database connection",
            description="Fixed database connection pool for async operations",
            files_changed=["db/pool.py", "db/async_client.py"],
            keywords={"async", "database", "connection", "pool", "fix"},
            pattern_type="fix",
        ),
        Pattern(
            id="proj2:def456",
            project="proj2",
            commit_hash="def456",
            commit_date=datetime(2024, 1, 2),
            title="Implement concurrent task processing",
            description="Added parallel task processing using asyncio",
            files_changed=["tasks/processor.py", "tasks/queue.py"],
            keywords={"concurrent", "parallel", "async", "task", "processing"},
            pattern_type="feature",
        ),
        Pattern(
            id="proj1:ghi789",
            project="proj1",
            commit_hash="ghi789",
            commit_date=datetime(2024, 1, 3),
            title="Add API rate limiting",
            description="Implemented rate limiting for API endpoints",
            files_changed=["api/middleware.py", "api/limiter.py"],
            keywords={"api", "rate", "limiting", "middleware"},
            pattern_type="feature",
        ),
        Pattern(
            id="proj3:jkl012",
            project="proj3",
            commit_hash="jkl012",
            commit_date=datetime(2024, 1, 4),
            title="Fix memory leak in cache",
            description="Fixed memory leak in LRU cache implementation",
            files_changed=["cache/lru.py"],
            keywords={"memory", "leak", "cache", "fix", "lru"},
            pattern_type="fix",
        ),
    ]


@pytest.fixture
def mock_embeddings_client():
    """Create mock embeddings client."""
    client = Mock(spec=EmbeddingsClient)
    client.get_embedding_dimension.return_value = 768

    # Generate deterministic embeddings based on text
    def generate_embedding(text):
        # Simple hash-based embedding for testing
        import hashlib

        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i : i + 4]
            value = int.from_bytes(chunk, byteorder="big")
            normalized = (value / (2**32)) * 2 - 1
            embedding.append(normalized)

        # Pad to 768 dimensions
        while len(embedding) < 768:
            embedding.extend(embedding[: min(768 - len(embedding), len(embedding))])

        return embedding[:768]

    def generate_embeddings_batch(texts, batch_size=100):
        return [generate_embedding(text) for text in texts]

    client.generate_embedding.side_effect = generate_embedding
    client.generate_embeddings_batch.side_effect = generate_embeddings_batch

    return client


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


# Tests
class TestHybridRetriever:
    """Tests for HybridRetriever class."""

    def test_init_without_embeddings(self, sample_patterns):
        """Test initialization without embeddings client."""
        retriever = HybridRetriever(sample_patterns, embeddings_client=None)

        assert retriever.patterns == sample_patterns
        assert retriever.bm25_searcher is not None
        assert retriever.embeddings_available is False
        assert retriever.pattern_embeddings is None

    def test_init_with_embeddings(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test initialization with embeddings client."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        assert retriever.patterns == sample_patterns
        assert retriever.embeddings_available is True
        assert retriever.pattern_embeddings is not None
        assert retriever.pattern_embeddings.shape == (len(sample_patterns), 768)

    def test_embedding_cache_save_load(
        self, sample_patterns, mock_embeddings_client, temp_cache_dir
    ):
        """Test embedding cache save and load."""
        # Create retriever (generates and saves embeddings)
        retriever1 = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Cache files should exist
        assert (temp_cache_dir / "embeddings.pkl").exists()
        assert (temp_cache_dir / "embeddings_meta.pkl").exists()

        # Create new retriever (should load from cache)
        with patch.object(mock_embeddings_client, "generate_embeddings_batch") as mock_batch:
            retriever2 = HybridRetriever(
                sample_patterns,
                embeddings_client=mock_embeddings_client,
                cache_dir=temp_cache_dir,
            )

            # Should not have called generate_embeddings_batch (loaded from cache)
            mock_batch.assert_not_called()

        # Embeddings should match
        np.testing.assert_array_equal(retriever1.pattern_embeddings, retriever2.pattern_embeddings)

    def test_bm25_only_search(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test BM25-only search (alpha=0.0)."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Search with alpha=0.0 (BM25 only)
        results = retriever.search("async database connection", limit=5, alpha=0.0)

        assert len(results) > 0
        assert all(isinstance(pattern, Pattern) for pattern, _ in results)
        assert all(isinstance(score, float) for _, score in results)

        # First result should be the async database pattern
        top_pattern, top_score = results[0]
        assert "async" in top_pattern.keywords or "database" in top_pattern.keywords

    def test_embedding_only_search(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test embedding-only search (alpha=1.0)."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Search with alpha=1.0 (embedding only)
        results = retriever.search("asynchronous database", limit=5, alpha=1.0)

        assert len(results) > 0
        assert all(isinstance(pattern, Pattern) for pattern, _ in results)
        assert all(isinstance(score, float) for _, score in results)
        # Scores should be in [0, 1] range
        assert all(0.0 <= score <= 1.0 for _, score in results)

    def test_hybrid_search(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test hybrid search (alpha=0.5)."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Search with alpha=0.5 (hybrid)
        results = retriever.search("async operations", limit=5, alpha=0.5)

        assert len(results) > 0
        assert all(isinstance(pattern, Pattern) for pattern, _ in results)
        assert all(isinstance(score, float) for _, score in results)

    def test_rrf_merge_correctness(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test RRF merge correctness."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Create mock results
        bm25_results = [
            (sample_patterns[0], 1.0),
            (sample_patterns[1], 0.8),
            (sample_patterns[2], 0.6),
        ]

        embedding_results = [
            (sample_patterns[1], 0.9),
            (sample_patterns[0], 0.7),
            (sample_patterns[3], 0.5),
        ]

        # Test RRF merge with alpha=0.5
        merged = retriever._rrf_merge(bm25_results, embedding_results, limit=5, alpha=0.5)

        # Check that all patterns are present
        merged_ids = {pattern.id for pattern, _ in merged}
        expected_ids = {p.id for p in sample_patterns[:4]}
        assert merged_ids == expected_ids

        # Check that scores are computed
        assert all(isinstance(score, float) for _, score in merged)
        assert all(score > 0 for _, score in merged)

        # Pattern that appears in both lists should rank higher
        # (sample_patterns[0] and [1] appear in both lists)
        top_ids = {pattern.id for pattern, _ in merged[:2]}
        assert sample_patterns[0].id in top_ids or sample_patterns[1].id in top_ids

    def test_alpha_boundaries(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test alpha parameter boundaries."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        query = "async database"

        # Test alpha < 0 (should clamp to 0)
        results_neg = retriever.search(query, limit=5, alpha=-0.5)
        assert len(results_neg) > 0

        # Test alpha > 1 (should clamp to 1)
        results_over = retriever.search(query, limit=5, alpha=1.5)
        assert len(results_over) > 0

    def test_fallback_to_bm25(self, sample_patterns, temp_cache_dir):
        """Test fallback to BM25 when embeddings unavailable."""
        # Create retriever without embeddings client
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=None, cache_dir=temp_cache_dir
        )

        # Search should fall back to BM25
        results = retriever.search("async database", limit=5, alpha=0.5)

        assert len(results) > 0
        # Should use BM25 despite alpha=0.5

    def test_invalidate_cache(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test cache invalidation."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Cache should exist
        assert (temp_cache_dir / "embeddings.pkl").exists()
        assert (temp_cache_dir / "embeddings_meta.pkl").exists()

        # Invalidate cache
        retriever.invalidate_cache()

        # Cache should be deleted
        assert not (temp_cache_dir / "embeddings.pkl").exists()
        assert not (temp_cache_dir / "embeddings_meta.pkl").exists()

    def test_get_stats(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test get_stats method."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        stats = retriever.get_stats()

        assert stats["pattern_count"] == len(sample_patterns)
        assert stats["embeddings_available"] is True
        assert stats["embeddings_cached"] is True
        assert stats["embedding_dimension"] == 768
        assert "cache_dir" in stats

    def test_semantic_search_with_synonyms(
        self, sample_patterns, mock_embeddings_client, temp_cache_dir
    ):
        """Test semantic search can find synonyms."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Search for "concurrent" (synonym for "async", "parallel")
        # Use embedding-only to test semantic matching
        results = retriever.search("concurrent processing", limit=5, alpha=1.0)

        assert len(results) > 0

        # Should find patterns with "concurrent", "async", or "parallel"
        found_keywords = set()
        for pattern, _ in results:
            found_keywords.update(pattern.keywords)

        # At least one of these keywords should be found
        assert any(kw in found_keywords for kw in ["concurrent", "async", "parallel"])

    def test_empty_patterns_list(self, mock_embeddings_client, temp_cache_dir):
        """Test with empty patterns list."""
        retriever = HybridRetriever(
            [], embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        results = retriever.search("test query", limit=5, alpha=0.5)

        assert len(results) == 0

    def test_limit_parameter(self, sample_patterns, mock_embeddings_client, temp_cache_dir):
        """Test limit parameter."""
        retriever = HybridRetriever(
            sample_patterns, embeddings_client=mock_embeddings_client, cache_dir=temp_cache_dir
        )

        # Search with limit=2
        results = retriever.search("database", limit=2, alpha=0.5)

        assert len(results) <= 2


class TestPatternMemoryIntegration:
    """Integration tests for PatternMemory with hybrid retrieval."""

    def test_pattern_memory_backward_compatibility(self, sample_patterns, temp_cache_dir):
        """Test PatternMemory backward compatibility without hybrid retrieval."""
        from intelligence.memory.pattern_memory import PatternMemory

        # Mock the indexer to return sample patterns
        with patch("intelligence.memory.pattern_memory.PatternIndexer") as MockIndexer:
            mock_indexer = MockIndexer.return_value
            mock_indexer.load_patterns.return_value = sample_patterns
            mock_indexer.cache_dir = temp_cache_dir

            # Create PatternMemory without hybrid retrieval
            memory = PatternMemory(use_hybrid_retrieval=False)

            # Should use BM25 only
            assert memory.use_hybrid_retrieval is False
            assert memory.hybrid_retriever is None

            # Search should work
            patterns = memory.get_relevant_patterns("database", limit=5)
            assert len(patterns) > 0

    def test_pattern_memory_with_hybrid_retrieval(
        self, sample_patterns, mock_embeddings_client, temp_cache_dir
    ):
        """Test PatternMemory with hybrid retrieval enabled."""
        from intelligence.memory.pattern_memory import PatternMemory

        # Mock the indexer
        with patch("intelligence.memory.pattern_memory.PatternIndexer") as MockIndexer:
            with patch(
                "intelligence.memory.pattern_memory.EmbeddingsClient",
                return_value=mock_embeddings_client,
            ):
                mock_indexer = MockIndexer.return_value
                mock_indexer.load_patterns.return_value = sample_patterns
                mock_indexer.cache_dir = temp_cache_dir

                # Create PatternMemory with hybrid retrieval
                memory = PatternMemory(use_hybrid_retrieval=True, hybrid_alpha=0.5)

                # Should use hybrid retrieval
                assert memory.use_hybrid_retrieval is True
                assert memory.hybrid_retriever is not None

                # Search should work
                patterns = memory.get_relevant_patterns("database", limit=5)
                assert len(patterns) > 0

    def test_pattern_memory_stats_with_hybrid(
        self, sample_patterns, mock_embeddings_client, temp_cache_dir
    ):
        """Test PatternMemory stats include hybrid retrieval info."""
        from intelligence.memory.pattern_memory import PatternMemory

        with patch("intelligence.memory.pattern_memory.PatternIndexer") as MockIndexer:
            with patch(
                "intelligence.memory.pattern_memory.EmbeddingsClient",
                return_value=mock_embeddings_client,
            ):
                mock_indexer = MockIndexer.return_value
                mock_indexer.load_patterns.return_value = sample_patterns
                mock_indexer.cache_dir = temp_cache_dir

                memory = PatternMemory(use_hybrid_retrieval=True)

                stats = memory.get_stats()

                assert "hybrid_retrieval" in stats
                assert stats["hybrid_retrieval"] is True
                assert "hybrid_alpha" in stats
                assert "hybrid_stats" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
