#!/usr/bin/env python3
"""
Hybrid Retriever - BM25 + Embedding hybrid retrieval with reciprocal rank fusion.

Combines keyword-based (BM25) and semantic (embedding) search for improved
pattern retrieval. Uses Reciprocal Rank Fusion (RRF) to merge results.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from intelligence.embeddings_client import EmbeddingsClient
from intelligence.memory.pattern_indexer import Pattern, PatternSearcher

logger = logging.getLogger(__name__)


class HybridRetriever:
    """BM25 + Embedding hybrid retrieval with reciprocal rank fusion."""

    def __init__(
        self,
        patterns: List[Pattern],
        embeddings_client: Optional[EmbeddingsClient] = None,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize hybrid retriever.

        Args:
            patterns: List of patterns to index
            embeddings_client: Client for generating embeddings
            cache_dir: Directory for embedding cache (default: ~/.cortex/patterns)
        """
        self.patterns = patterns
        self.bm25_searcher = PatternSearcher(patterns)

        if cache_dir is None:
            cache_dir = Path.home() / ".cortex" / "patterns"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize embeddings client
        self.embeddings_client = embeddings_client
        self.embeddings_available = embeddings_client is not None

        # Pattern embeddings cache
        self.pattern_embeddings: Optional[np.ndarray] = None
        self.embedding_dimension = 768  # Default

        if self.embeddings_available:
            self.embedding_dimension = self.embeddings_client.get_embedding_dimension()
            self._load_or_generate_embeddings()

    def _load_or_generate_embeddings(self):
        """Load embeddings from cache or generate new ones."""
        cache_file = self.cache_dir / "embeddings.pkl"
        cache_meta_file = self.cache_dir / "embeddings_meta.pkl"

        # Check if cache exists and is valid
        if cache_file.exists() and cache_meta_file.exists():
            try:
                # Note: pickle is used here for numpy array serialization
                # Cache files are stored locally in ~/.cortex/patterns
                with open(cache_meta_file, "rb") as f:
                    meta = pickle.load(f)

                # Verify cache matches current patterns
                if meta.get("pattern_count") == len(self.patterns):
                    # Check if pattern IDs match
                    cached_ids = set(meta.get("pattern_ids", []))
                    current_ids = {p.id for p in self.patterns}

                    if cached_ids == current_ids:
                        with open(cache_file, "rb") as f:
                            self.pattern_embeddings = pickle.load(f)
                        logger.info(f"Loaded {len(self.patterns)} pattern embeddings from cache")
                        return
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")

        # Generate new embeddings
        logger.info(f"Generating embeddings for {len(self.patterns)} patterns...")
        self._generate_embeddings()
        self._save_embeddings()

    def _generate_embeddings(self):
        """Generate embeddings for all patterns."""
        if not self.embeddings_available:
            logger.warning("Embeddings client not available")
            return

        # Create text representations of patterns
        pattern_texts = []
        for pattern in self.patterns:
            # Combine title, description, and keywords for richer embedding
            text = f"{pattern.title} {pattern.description} {' '.join(pattern.keywords)}"
            pattern_texts.append(text)

        # Generate embeddings in batch
        try:
            embeddings = self.embeddings_client.generate_embeddings_batch(
                pattern_texts, batch_size=100
            )
            self.pattern_embeddings = np.array(embeddings)
            logger.info(
                f"Generated embeddings with shape {self.pattern_embeddings.shape}"
            )
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            self.pattern_embeddings = None

    def _save_embeddings(self):
        """Save embeddings to cache."""
        if self.pattern_embeddings is None:
            return

        cache_file = self.cache_dir / "embeddings.pkl"
        cache_meta_file = self.cache_dir / "embeddings_meta.pkl"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(self.pattern_embeddings, f)

            meta = {
                "pattern_count": len(self.patterns),
                "pattern_ids": [p.id for p in self.patterns],
                "embedding_dimension": self.embedding_dimension,
            }
            with open(cache_meta_file, "wb") as f:
                pickle.dump(meta, f)

            logger.info(f"Saved embeddings to cache: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to save embedding cache: {e}")

    def search(
        self, query: str, limit: int = 10, alpha: float = 0.5
    ) -> List[Tuple[Pattern, float]]:
        """
        Hybrid search with configurable BM25/embedding weight.

        Args:
            query: Search query
            limit: Maximum results to return
            alpha: Weight for method combination
                   0.0 = Pure BM25 (existing behavior)
                   0.5 = Equal weight to both methods
                   1.0 = Pure semantic search

        Returns:
            List of (Pattern, score) tuples sorted by score
        """
        # Validate alpha
        alpha = max(0.0, min(1.0, alpha))

        # Get BM25 results
        bm25_results = self.bm25_searcher.search(query, limit=limit * 2)

        # If alpha is 0, return BM25 only (backward compatible)
        if alpha == 0.0:
            return bm25_results[:limit]

        # Get embedding results if available
        embedding_results = []
        if self.embeddings_available and self.pattern_embeddings is not None:
            embedding_results = self._semantic_search(query, limit=limit * 2)

            # If alpha is 1.0, return embeddings only
            if alpha == 1.0:
                return embedding_results[:limit]

        # If no embedding results, fall back to BM25
        if not embedding_results:
            logger.warning("Embeddings not available, falling back to BM25 only")
            return bm25_results[:limit]

        # Merge results using Reciprocal Rank Fusion
        merged = self._rrf_merge(bm25_results, embedding_results, limit, alpha)

        return merged

    def _semantic_search(
        self, query: str, limit: int = 10
    ) -> List[Tuple[Pattern, float]]:
        """
        Semantic search using embeddings.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of (Pattern, score) tuples sorted by similarity
        """
        if not self.embeddings_available or self.pattern_embeddings is None:
            return []

        try:
            # Generate query embedding
            query_embedding = self.embeddings_client.generate_embedding(query)
            query_vector = np.array(query_embedding)

            # Compute cosine similarity
            # Normalize vectors
            query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-10)
            pattern_norms = self.pattern_embeddings / (
                np.linalg.norm(self.pattern_embeddings, axis=1, keepdims=True) + 1e-10
            )

            # Compute similarities
            similarities = np.dot(pattern_norms, query_norm)

            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:limit]

            # Build results
            results = []
            for idx in top_indices:
                if idx < len(self.patterns):
                    pattern = self.patterns[idx]
                    # Convert cosine similarity [-1, 1] to [0, 1]
                    score = (similarities[idx] + 1.0) / 2.0
                    results.append((pattern, float(score)))

            return results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def _rrf_merge(
        self,
        bm25_results: List[Tuple[Pattern, float]],
        embedding_results: List[Tuple[Pattern, float]],
        limit: int,
        alpha: float,
    ) -> List[Tuple[Pattern, float]]:
        """
        Merge BM25 and embedding results using Reciprocal Rank Fusion (RRF).

        RRF formula: score = sum(1 / (k + rank)) where k=60
        Weight by alpha parameter.

        Args:
            bm25_results: BM25 search results
            embedding_results: Embedding search results
            limit: Maximum results to return
            alpha: Weight for method combination (0=BM25 only, 1=embedding only)

        Returns:
            Merged and ranked results
        """
        k = 60  # RRF constant

        # Build rank maps
        bm25_ranks = {pattern.id: rank for rank, (pattern, _) in enumerate(bm25_results)}
        embedding_ranks = {
            pattern.id: rank for rank, (pattern, _) in enumerate(embedding_results)
        }

        # Get all unique pattern IDs
        all_pattern_ids = set(bm25_ranks.keys()) | set(embedding_ranks.keys())

        # Calculate RRF scores
        rrf_scores = {}
        for pattern_id in all_pattern_ids:
            bm25_score = 0.0
            embedding_score = 0.0

            if pattern_id in bm25_ranks:
                bm25_score = 1.0 / (k + bm25_ranks[pattern_id])

            if pattern_id in embedding_ranks:
                embedding_score = 1.0 / (k + embedding_ranks[pattern_id])

            # Weight by alpha
            # alpha = 0: BM25 only
            # alpha = 1: embedding only
            # alpha = 0.5: equal weight
            rrf_scores[pattern_id] = (1.0 - alpha) * bm25_score + alpha * embedding_score

        # Build pattern map
        pattern_map = {}
        for pattern, _ in bm25_results:
            pattern_map[pattern.id] = pattern
        for pattern, _ in embedding_results:
            pattern_map[pattern.id] = pattern

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Build final results
        results = []
        for pattern_id in sorted_ids[:limit]:
            if pattern_id in pattern_map:
                pattern = pattern_map[pattern_id]
                score = rrf_scores[pattern_id]
                results.append((pattern, score))

        return results

    def invalidate_cache(self):
        """Invalidate embedding cache, forcing regeneration on next use."""
        cache_file = self.cache_dir / "embeddings.pkl"
        cache_meta_file = self.cache_dir / "embeddings_meta.pkl"

        try:
            if cache_file.exists():
                cache_file.unlink()
            if cache_meta_file.exists():
                cache_meta_file.unlink()
            logger.info("Embedding cache invalidated")
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")

    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "pattern_count": len(self.patterns),
            "embeddings_available": self.embeddings_available,
            "embeddings_cached": self.pattern_embeddings is not None,
            "embedding_dimension": self.embedding_dimension,
            "cache_dir": str(self.cache_dir),
        }
