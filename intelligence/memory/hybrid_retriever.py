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
import math
import os
import pickle
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

# Recorded-decisions path (written by mcp_handlers.record_learning_decision /
# POST /decisions/learning). These are the "your past decisions come back to
# you" memories; without loading them here they were write-only.
_DECISIONS_PATH = Path.home() / ".cortex" / "decisions.jsonl"


# Module-level cache for decision patterns, keyed by decisions.jsonl mtime, so
# repeated HybridRetriever constructions don't re-parse the whole file each
# time. Invalidated automatically when the file changes.
_decision_cache: Optional[List[Pattern]] = None
_decision_cache_mtime: Optional[float] = None
# P1 curation: per-decision recall multiplier (importance × recency decay),
# keyed by Pattern id ("decision:<id>"). Populated alongside _decision_cache and
# applied in _rrf_merge next to the outcome boosts.
_decision_weights: Dict[str, float] = {}
_DECAY_HALF_LIFE_DAYS = int(os.environ.get("CORTEX_DECAY_HALF_LIFE_DAYS", "120"))


def _load_decision_patterns() -> List[Pattern]:
    """Load recorded decisions and convert them to Pattern objects.

    Decisions flow into the same BM25+embedding pipeline as git/conversation
    patterns. Their IDs carry a ``decision:`` prefix so that
    ``recall_events.count_surfaced`` recognises them as decisions
    (n_decisions_surfaced) and so ``search`` can surface them by relevance.

    Result is cached at module level and reused until decisions.jsonl changes.
    """
    global _decision_cache, _decision_cache_mtime, _decision_weights

    if not _DECISIONS_PATH.exists():
        return []

    try:
        mtime = _DECISIONS_PATH.stat().st_mtime
    except OSError:
        mtime = None
    if _decision_cache is not None and _decision_cache_mtime == mtime:
        return _decision_cache

    patterns: List[Pattern] = []
    weights: Dict[str, float] = {}
    try:
        raw_lines = _DECISIONS_PATH.read_text().splitlines()

        # First pass: collect ids marked superseded by a tombstone (P1 curation).
        # A superseded decision is dropped from recall so stale/reversed calls
        # can't resurface and crowd the top-k.
        superseded: set = set()
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("superseded_by"):
                superseded.add(d.get("decision_id"))

        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Skip tombstones and superseded originals — they never enter recall.
            if d.get("superseded_by"):
                continue
            decision = d.get("decision", "")
            if not decision:
                continue
            decision_id = d.get("decision_id", "unknown")
            if decision_id in superseded:
                continue
            project = d.get("project", "unknown")

            desc_parts = [decision]
            if d.get("rationale"):
                desc_parts.append(f"rationale: {d['rationale']}")
            if d.get("context"):
                desc_parts.append(f"context: {d['context']}")
            if d.get("alternatives"):
                desc_parts.append(f"alternatives: {d['alternatives']}")

            try:
                commit_date = datetime.fromisoformat(
                    d.get("timestamp", "").replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                commit_date = datetime.now()

            # Keywords from the decision text (cheap tokenisation) + project.
            words = {w.strip(".,:;()[]").lower() for w in decision.split() if len(w) > 3}
            words.add(project)

            pattern_id = f"decision:{decision_id}"
            patterns.append(
                Pattern(
                    id=pattern_id,
                    project=project,
                    commit_hash=str(decision_id)[:8],
                    commit_date=commit_date,
                    title=f"Decision: {decision[:80]}",
                    description=" | ".join(desc_parts),
                    files_changed=[],
                    keywords=words,
                    pattern_type="decision",
                )
            )

            # P1 curation: recall multiplier = importance × recency decay.
            # importance defaults to a neutral 5 for pre-P1 entries (no key),
            # so un-backfilled history is unaffected until scored.
            importance = d.get("importance", 5)
            try:
                age_days = max(0.0, (datetime.now() - commit_date.replace(tzinfo=None)).days)
            except Exception:
                age_days = 0.0
            decay = math.exp(-age_days / _DECAY_HALF_LIFE_DAYS) if _DECAY_HALF_LIFE_DAYS > 0 else 1.0
            # Map importance 1..10 to ~0.5..1.1 so low-signal is penalised but
            # never zeroed (still findable), high-signal mildly boosted.
            imp_factor = 0.5 + (importance / 10.0) * 0.6
            weights[pattern_id] = imp_factor * decay
    except Exception as e:
        logger.warning(f"Failed to load decision patterns: {e}")

    _decision_cache = patterns
    _decision_cache_mtime = mtime
    _decision_weights = weights
    return patterns


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

        # Merge recorded decisions so past decisions can be recalled. Always
        # loaded (not gated on include_conversation_digests): a decision store
        # is the core "memory comes back" signal, independent of chat history.
        decision_patterns = _load_decision_patterns()
        if decision_patterns:
            logger.info(f"Loaded {len(decision_patterns)} recorded-decision patterns")
            patterns = list(patterns) + decision_patterns

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

    def _current_backend(self):
        """Active embedding backend name as a str, or None if undeterminable.

        Returns None for clients that don't report a real string backend (e.g.
        a test Mock), so callers can skip backend-based cache invalidation
        rather than regenerate spuriously.
        """
        try:
            backend = self.embeddings_client.get_embedding_info().get("backend")
        except Exception:
            return None
        return backend if isinstance(backend, str) else None

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

                # Verify cache matches current patterns AND embedding backend.
                # A backend switch (e.g. hashing -> ollama) yields different
                # vectors, so a stale cache must NOT be reused with a new backend.
                # Only force a regen on a DEFINITE string mismatch — if the
                # backend is unknown (e.g. a mocked client), fall back to the
                # count+id check rather than regenerating spuriously.
                current_backend = self._current_backend()
                backend_ok = (
                    not isinstance(current_backend, str)
                    or meta.get("backend") == current_backend
                )
                if meta.get("pattern_count") == len(self.patterns) and backend_ok:
                    # Check if pattern IDs match
                    cached_ids = set(meta.get("pattern_ids", []))
                    current_ids = {p.id for p in self.patterns}

                    if cached_ids == current_ids:
                        import warnings

                        with open(cache_file, "rb") as f:
                            # Suppress numpy internal namespace deprecation from
                            # cached arrays serialized with older numpy versions.
                            # Cache files are local-only (~/.cortex/patterns).
                            with warnings.catch_warnings():
                                warnings.filterwarnings(
                                    "ignore", category=DeprecationWarning, module="numpy"
                                )
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
            logger.info(f"Generated embeddings with shape {self.pattern_embeddings.shape}")
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
                "backend": self._current_backend(),
            }
            with open(cache_meta_file, "wb") as f:
                pickle.dump(meta, f)

            logger.info(f"Saved embeddings to cache: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to save embedding cache: {e}")

    def _scoped_index(
        self, project: Optional[str]
    ) -> Tuple[List[Pattern], Optional[np.ndarray], PatternSearcher]:
        """Return patterns, embeddings, and BM25 searcher for an optional project scope."""
        if not project:
            return self.patterns, self.pattern_embeddings, self.bm25_searcher

        indices = [i for i, p in enumerate(self.patterns) if p.project == project]
        if not indices:
            return [], None, PatternSearcher([])

        scoped_patterns = [self.patterns[i] for i in indices]
        scoped_embeddings = (
            self.pattern_embeddings[indices]
            if self.pattern_embeddings is not None
            else None
        )
        return scoped_patterns, scoped_embeddings, PatternSearcher(scoped_patterns)

    def search(
        self,
        query: str,
        limit: int = 10,
        alpha: float = 0.5,
        project: Optional[str] = None,
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
            project: When set, restrict results to patterns tagged with this
                project (decisions, digests, and git-derived patterns).

        Returns:
            List of (Pattern, score) tuples sorted by score
        """
        # Validate alpha
        alpha = max(0.0, min(1.0, alpha))

        patterns, pattern_embeddings, bm25_searcher = self._scoped_index(project)
        if not patterns:
            return []

        # Get BM25 results
        bm25_results = bm25_searcher.search(query, limit=limit * 2)

        # If alpha is 0, return BM25 only (backward compatible)
        if alpha == 0.0:
            return bm25_results[:limit]

        # Get embedding results if available
        embedding_results = []
        if self.embeddings_available and pattern_embeddings is not None:
            embedding_results = self._semantic_search(
                query,
                limit=limit * 2,
                patterns=patterns,
                pattern_embeddings=pattern_embeddings,
            )

            # If alpha is 1.0, return embeddings only
            if alpha == 1.0:
                return embedding_results[:limit]

        # If no embedding results, fall back to BM25
        if not embedding_results:
            if alpha > 0.0:
                logger.warning("Embeddings not available, falling back to BM25 only")
            return bm25_results[:limit]

        # Merge results using Reciprocal Rank Fusion
        merged = self._rrf_merge(bm25_results, embedding_results, limit, alpha)

        return merged

    def _semantic_search(
        self,
        query: str,
        limit: int = 10,
        patterns: Optional[List[Pattern]] = None,
        pattern_embeddings: Optional[np.ndarray] = None,
    ) -> List[Tuple[Pattern, float]]:
        """
        Semantic search using embeddings.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of (Pattern, score) tuples sorted by similarity
        """
        patterns = patterns if patterns is not None else self.patterns
        pattern_embeddings = (
            pattern_embeddings
            if pattern_embeddings is not None
            else self.pattern_embeddings
        )

        if not self.embeddings_available or pattern_embeddings is None:
            return []

        try:
            # Generate query embedding
            query_embedding = self.embeddings_client.generate_embedding(query)
            query_vector = np.array(query_embedding)

            # Compute cosine similarity
            # Normalize vectors
            query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-10)
            pattern_norms = pattern_embeddings / (
                np.linalg.norm(pattern_embeddings, axis=1, keepdims=True) + 1e-10
            )

            # Compute similarities
            similarities = np.dot(pattern_norms, query_norm)

            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:limit]

            # Build results
            results = []
            for idx in top_indices:
                if idx < len(patterns):
                    pattern = patterns[idx]
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

            # P1 curation: multiply by the decision's importance × recency-decay
            # weight so low-signal / stale decisions rank below fresh, developed
            # ones. Non-decision patterns (no entry in the map) are unaffected.
            base_score *= _decision_weights.get(pattern_id, 1.0)

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
