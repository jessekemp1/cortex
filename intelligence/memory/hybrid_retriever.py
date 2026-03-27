#!/usr/bin/env python3
"""
Hybrid Retriever - BM25 + Embedding hybrid retrieval with reciprocal rank fusion.

Combines keyword-based (BM25) and semantic (embedding) search for improved
pattern retrieval. Uses Reciprocal Rank Fusion (RRF) to merge results.

Outcome-aware: loads historical outcome data to boost patterns associated
with successful outcomes and demote those associated with failures.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from intelligence.embeddings_client import EmbeddingsClient
from intelligence.memory.pattern_indexer import Pattern, PatternSearcher

logger = logging.getLogger(__name__)

# Outcome data path
_OUTCOMES_PATH = Path.home() / ".cortex" / "outcomes.jsonl"

# Conversation digests path
_DIGESTS_PATH = Path.home() / ".cortex" / "conversation_digests.jsonl"


def _load_digest_patterns() -> List[Pattern]:
    """
    Load conversation digests and convert them to Pattern objects.

    This allows conversation history to participate in the same BM25+embedding
    search pipeline as git-derived patterns. Digest patterns use a "conversation:"
    prefix in their ID to distinguish them from commit-based patterns.
    """
    if not _DIGESTS_PATH.exists():
        return []

    patterns = []
    try:
        for line in _DIGESTS_PATH.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                session_id = d.get("session_id", "unknown")
                project = d.get("project", "unknown")
                topics = d.get("topics", [])
                files_written = d.get("files_written", [])
                slash_cmds = d.get("slash_commands", [])

                # Build description from digest fields
                desc_parts = []
                if d.get("outcome"):
                    desc_parts.append(f"outcome:{d['outcome']}")
                if slash_cmds:
                    desc_parts.append(f"commands: {' '.join(slash_cmds)}")
                if d.get("correction_count", 0) > 0:
                    desc_parts.append(
                        f"{d['correction_count']} corrections in "
                        f"{d.get('user_prompt_count', 0)} prompts"
                    )
                desc_parts.append(
                    f"{d.get('tool_use_count', 0)} tool uses, {d.get('duration_minutes', 0):.0f}min"
                )

                # Build keywords from topics + file basenames
                keywords = set(topics)
                for f in files_written[:10]:
                    # Extract filename without extension
                    basename = f.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    if basename:
                        keywords.add(basename)
                keywords.update(slash_cmds)

                # Parse date
                started = d.get("started_at", "")
                try:
                    commit_date = datetime.fromisoformat(started.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    commit_date = datetime.now()

                patterns.append(
                    Pattern(
                        id=f"conversation:{session_id}",
                        project=project,
                        commit_hash=session_id[:8],
                        commit_date=commit_date,
                        title=f"Session: {' '.join(topics[:5])}",
                        description=" | ".join(desc_parts),
                        files_changed=files_written[:20],
                        keywords=keywords,
                        pattern_type="conversation",
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    except Exception as e:
        logger.warning(f"Failed to load digest patterns: {e}")

    return patterns


class HybridRetriever:
    """BM25 + Embedding hybrid retrieval with reciprocal rank fusion."""

    def __init__(
        self,
        patterns: List[Pattern],
        embeddings_client: Optional[EmbeddingsClient] = None,
        cache_dir: Optional[Path] = None,
        include_conversation_digests: bool = True,
    ):
        """
        Initialize hybrid retriever.

        Args:
            patterns: List of patterns to index
            embeddings_client: Client for generating embeddings
            cache_dir: Directory for embedding cache (default: ~/.cortex/patterns)
            include_conversation_digests: Whether to include conversation history
                patterns from ~/.cortex/conversation_digests.jsonl (default: True)
        """
        # Merge git patterns with conversation digest patterns
        if include_conversation_digests:
            digest_patterns = _load_digest_patterns()
            if digest_patterns:
                logger.info(f"Loaded {len(digest_patterns)} conversation digest patterns")
                patterns = list(patterns) + digest_patterns

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

        # Outcome-based boosting
        self._outcome_boosts: Dict[str, float] = {}
        self._load_outcome_boosts()

        if self.embeddings_available:
            self.embedding_dimension = self.embeddings_client.get_embedding_dimension()
            self._load_or_generate_embeddings()

    def _load_outcome_boosts(self) -> None:
        """Load outcome data and compute per-project success rate boosts.

        Reads outcomes.jsonl and computes a boost factor for each project:
        - Projects with >70% success rate get a positive boost (up to +0.15)
        - Projects with <30% success rate get a negative boost (down to -0.10)
        - Projects with insufficient data (< 5 outcomes) get no boost

        These boosts are applied during RRF merge to close the feedback loop:
        patterns from projects where outcomes were successful rank higher.
        """
        if not _OUTCOMES_PATH.exists():
            return

        project_outcomes: Dict[str, list] = defaultdict(list)
        try:
            with open(_OUTCOMES_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        project = (
                            entry.get("context", {}).get("project", "")
                            if entry.get("context")
                            else ""
                        )
                        if not project or project == "unknown":
                            continue
                        outcome = entry.get("outcome", "")
                        project_outcomes[project].append(outcome == "success")
                    except (json.JSONDecodeError, TypeError):
                        continue

            for project, results in project_outcomes.items():
                if len(results) < 5:
                    continue
                success_rate = sum(results) / len(results)
                if success_rate > 0.7:
                    self._outcome_boosts[project] = 0.15 * (success_rate - 0.5)
                elif success_rate < 0.3:
                    self._outcome_boosts[project] = -0.10 * (0.5 - success_rate)

            if self._outcome_boosts:
                logger.info(f"Loaded outcome boosts for {len(self._outcome_boosts)} projects")
        except Exception as e:
            logger.warning(f"Failed to load outcome boosts: {e}")

    def _load_or_generate_embeddings(self):
        """Load embeddings from cache or generate new ones."""
        cache_file = self.cache_dir / "embeddings.npy"
        cache_meta_file = self.cache_dir / "embeddings_meta.json"

        # Check if cache exists and is valid
        if cache_file.exists() and cache_meta_file.exists():
            try:
                with open(cache_meta_file, "r") as f:
                    meta = json.load(f)

                # Verify cache matches current patterns
                if meta.get("pattern_count") == len(self.patterns):
                    cached_ids = set(meta.get("pattern_ids", []))
                    current_ids = {p.id for p in self.patterns}

                    if cached_ids == current_ids:
                        # numpy.load with allow_pickle=False is safe
                        self.pattern_embeddings = np.load(
                            str(cache_file), allow_pickle=False
                        )
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
            logger.info(f"Generated embeddings with shape {self.pattern_embeddings.shape}")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            self.pattern_embeddings = None

    def _save_embeddings(self):
        """Save embeddings to cache using numpy (no pickle)."""
        if self.pattern_embeddings is None:
            return

        cache_file = self.cache_dir / "embeddings.npy"
        cache_meta_file = self.cache_dir / "embeddings_meta.json"

        try:
            np.save(str(cache_file), self.pattern_embeddings, allow_pickle=False)

            meta = {
                "pattern_count": len(self.patterns),
                "pattern_ids": [p.id for p in self.patterns],
                "embedding_dimension": self.embedding_dimension,
            }
            with open(cache_meta_file, "w") as f:
                json.dump(meta, f)

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

    def _semantic_search(self, query: str, limit: int = 10) -> List[Tuple[Pattern, float]]:
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
        embedding_ranks = {pattern.id: rank for rank, (pattern, _) in enumerate(embedding_results)}

        # Get all unique pattern IDs
        all_pattern_ids = set(bm25_ranks.keys()) | set(embedding_ranks.keys())

        # Build project lookup for outcome boosting
        project_by_id: Dict[str, str] = {}
        for pattern, _ in bm25_results:
            project_by_id[pattern.id] = pattern.project
        for pattern, _ in embedding_results:
            project_by_id[pattern.id] = pattern.project

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
            base_score = (1.0 - alpha) * bm25_score + alpha * embedding_score

            # Apply outcome-based boost (feedback loop closes here)
            if self._outcome_boosts:
                project = project_by_id.get(pattern_id, "")
                base_score += self._outcome_boosts.get(project, 0.0)

            rrf_scores[pattern_id] = base_score

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
        conversation_count = sum(1 for p in self.patterns if p.id.startswith("conversation:"))
        return {
            "pattern_count": len(self.patterns),
            "conversation_pattern_count": conversation_count,
            "git_pattern_count": len(self.patterns) - conversation_count,
            "embeddings_available": self.embeddings_available,
            "embeddings_cached": self.pattern_embeddings is not None,
            "embedding_dimension": self.embedding_dimension,
            "cache_dir": str(self.cache_dir),
            "outcome_boosts": len(self._outcome_boosts),
            "outcome_boost_projects": list(self._outcome_boosts.keys()),
        }
