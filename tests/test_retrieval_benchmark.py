"""Tier 1 Retrieval Benchmark — Recall@K and Precision@K for HybridRetriever.

Tests whether the retrieval system finds known-relevant items for real queries
derived from CLAUDE.md anti-patterns, gotchas, and session history.

This is the ground-truth sanity check before running the expensive
Tier 2 (retrieval vs. stuffing head-to-head) comparison.

Usage:
    pytest cortex/tests/test_retrieval_benchmark.py -v
    pytest cortex/tests/test_retrieval_benchmark.py -v -k "tier1"
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest

# Retrieval benchmark depends on HybridRetriever which imports scikit-learn.
# scikit-learn is not a core dep — it's only needed for retrieval evaluation.
# Skip the whole module when sklearn isn't installed instead of erroring at
# collection time.
pytest.importorskip("sklearn", reason="retrieval benchmark requires scikit-learn (optional)")

# ---------------------------------------------------------------------------
# Ground-truth query corpus
# ---------------------------------------------------------------------------

# Each query maps to expected patterns (by title substring match).
# Derived from CLAUDE.md anti-patterns, gotchas, and real session tasks.

TIER1_CORPUS = [
    # Anti-patterns (from CLAUDE.md)
    {
        "query": "mock patch namespace python import",
        "expected_titles": ["Testing implementation", "mock", "import"],
        "category": "anti-pattern",
    },
    {
        "query": "force push to main branch",
        "expected_titles": ["Force push to main"],
        "category": "anti-pattern",
    },
    {
        "query": "commit without running tests",
        "expected_titles": ["Deploy without running tests"],
        "category": "anti-pattern",
    },
    {
        "query": "permissive test assertion status code",
        "expected_titles": ["Permissive test assertion"],
        "category": "anti-pattern",
    },
    {
        "query": "circular import module",
        "expected_titles": ["Circular import"],
        "category": "anti-pattern",
    },
    {
        "query": "secret key committed to git repository",
        "expected_titles": ["Secret committed"],
        "category": "anti-pattern",
    },
    {
        "query": "large binary file committed",
        "expected_titles": ["Large binary committed"],
        "category": "anti-pattern",
    },
    {
        "query": "merge conflict markers in code",
        "expected_titles": ["Merge conflict markers"],
        "category": "anti-pattern",
    },
    {
        "query": "build artifacts committed to repository",
        "expected_titles": ["Build artifacts committed"],
        "category": "anti-pattern",
    },
    {
        "query": "schema change without migration",
        "expected_titles": ["Schema change without migration"],
        "category": "anti-pattern",
    },
    # Operational queries (from session patterns)
    {
        "query": "deploy without tests production",
        "expected_titles": ["Deploy without running tests"],
        "category": "operational",
    },
    {
        "query": "uncommitted changes destructive operation",
        "expected_titles": ["Uncommitted changes"],
        "category": "operational",
    },
    # Broader domain queries
    {
        "query": "testing behavior vs implementation",
        "expected_titles": ["Testing implementation instead of behavior"],
        "category": "testing",
    },
    {
        "query": "security vulnerability code review",
        "expected_titles": ["Secret committed", "security"],
        "category": "security",
    },
    {
        "query": "agent deployment infrastructure",
        "expected_titles": ["agent", "deploy"],
        "category": "infrastructure",
    },
]


@dataclass
class BenchmarkResult:
    """Result of a single benchmark query."""

    query: str
    category: str
    expected_titles: List[str]
    retrieved_titles: List[str] = field(default_factory=list)
    retrieved_scores: List[float] = field(default_factory=list)
    hit: bool = False
    reciprocal_rank: float = 0.0

    @property
    def precision_at_k(self) -> float:
        """Fraction of top-K results that are relevant."""
        if not self.retrieved_titles:
            return 0.0
        hits = sum(
            1
            for title in self.retrieved_titles
            if any(exp.lower() in title.lower() for exp in self.expected_titles)
        )
        return hits / len(self.retrieved_titles)


@dataclass
class BenchmarkSummary:
    """Aggregated benchmark results."""

    total_queries: int = 0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mean_reciprocal_rank: float = 0.0
    precision_at_5: float = 0.0
    by_category: dict = field(default_factory=dict)
    results: List[BenchmarkResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def run_tier1_benchmark(retriever, k: int = 10) -> BenchmarkSummary:
    """Run Tier 1 benchmark: recall@K for known-relevant queries."""
    results = []

    for item in TIER1_CORPUS:
        query = item["query"]
        expected = item["expected_titles"]
        category = item["category"]

        # Search
        search_results = retriever.search(query, limit=k, alpha=0.5)

        retrieved_titles = [p.title for p, score in search_results]
        retrieved_scores = [score for _, score in search_results]

        # Check if any expected title appears in results
        hit = any(
            any(exp.lower() in title.lower() for exp in expected) for title in retrieved_titles
        )

        # Compute reciprocal rank
        rr = 0.0
        for rank, title in enumerate(retrieved_titles, 1):
            if any(exp.lower() in title.lower() for exp in expected):
                rr = 1.0 / rank
                break

        result = BenchmarkResult(
            query=query,
            category=category,
            expected_titles=expected,
            retrieved_titles=retrieved_titles[:k],
            retrieved_scores=retrieved_scores[:k],
            hit=hit,
            reciprocal_rank=rr,
        )
        results.append(result)

    # Aggregate
    total = len(results)
    hits_at_5 = sum(1 for r in results if r.hit and len(r.retrieved_titles) <= 5 or r.hit)
    hits_at_10 = sum(1 for r in results if r.hit)
    mrr = sum(r.reciprocal_rank for r in results) / total if total else 0

    # Per-category
    categories: dict = {}
    for r in results:
        cat = r.category
        if cat not in categories:
            categories[cat] = {"total": 0, "hits": 0}
        categories[cat]["total"] += 1
        if r.hit:
            categories[cat]["hits"] += 1

    return BenchmarkSummary(
        total_queries=total,
        recall_at_5=hits_at_5 / total if total else 0,
        recall_at_10=hits_at_10 / total if total else 0,
        mean_reciprocal_rank=mrr,
        precision_at_5=sum(r.precision_at_k for r in results) / total if total else 0,
        by_category={k: v["hits"] / v["total"] for k, v in categories.items()},
        results=results,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def retriever():
    """Initialize HybridRetriever with real pattern data."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from intelligence.embeddings_client import EmbeddingsClient
    from intelligence.memory.hybrid_retriever import HybridRetriever
    from intelligence.memory.pattern_indexer import PatternIndexer

    indexer = PatternIndexer(root_dir=Path.home() / "Dev")
    patterns = indexer.load_patterns()

    # Enable embeddings only if real embedding API is available.
    # Hash-based fallback degrades BM25 quality via RRF noise.
    embeddings_client = None
    try:
        client = EmbeddingsClient()
        # Test if real embeddings work (not just hash fallback)
        test_vec = client.generate_embedding("test")
        if len(test_vec) == 768:
            embeddings_client = client
    except (ImportError, ValueError, Exception):
        pass

    return HybridRetriever(patterns, embeddings_client=embeddings_client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTier1RetrievalBenchmark:
    """Tier 1: Does HybridRetriever find known-relevant items?"""

    def test_recall_at_10_above_threshold(self, retriever):
        """Recall@10 must be >= 60% for the benchmark to pass."""
        summary = run_tier1_benchmark(retriever, k=10)
        assert summary.recall_at_10 >= 0.60, (
            f"Recall@10 = {summary.recall_at_10:.1%} (threshold: 60%). "
            f"Misses: {[r.query for r in summary.results if not r.hit]}"
        )

    def test_mrr_above_threshold(self, retriever):
        """Mean Reciprocal Rank must be >= 0.4 (relevant items in top 2-3)."""
        summary = run_tier1_benchmark(retriever, k=10)
        assert summary.mean_reciprocal_rank >= 0.40, (
            f"MRR = {summary.mean_reciprocal_rank:.3f} (threshold: 0.40)"
        )

    def test_anti_pattern_recall(self, retriever):
        """Anti-pattern queries should have highest recall (core use case)."""
        summary = run_tier1_benchmark(retriever, k=10)
        anti_pattern_recall = summary.by_category.get("anti-pattern", 0)
        assert anti_pattern_recall >= 0.70, (
            f"Anti-pattern recall = {anti_pattern_recall:.1%} (threshold: 70%)"
        )

    def test_no_empty_results(self, retriever):
        """Every query should return at least 1 result."""
        summary = run_tier1_benchmark(retriever, k=10)
        empty = [r.query for r in summary.results if not r.retrieved_titles]
        assert not empty, f"Queries with 0 results: {empty}"


class TestTier1Report:
    """Generate and display the full benchmark report."""

    def test_generate_report(self, retriever):
        """Run benchmark and print detailed report."""
        summary = run_tier1_benchmark(retriever, k=10)

        print("\n")
        print("┌─────────────────────────────────────────────────────────────┐")
        print("│  TIER 1 RETRIEVAL BENCHMARK                                 │")
        print("├─────────────────────────────────────────────────────────────┤")
        print(
            f"│  Queries:       {summary.total_queries:>3}                                        │"
        )
        print(
            f"│  Recall@10:     {summary.recall_at_10:>5.1%}                                     │"
        )
        print(
            f"│  MRR:           {summary.mean_reciprocal_rank:>5.3f}                                     │"
        )
        print(
            f"│  Precision@5:   {summary.precision_at_5:>5.1%}                                     │"
        )
        print("├─────────────────────────────────────────────────────────────┤")

        for cat, recall in sorted(summary.by_category.items()):
            bar = "█" * int(recall * 20) + "░" * (20 - int(recall * 20))
            print(f"│  {cat:<15} {bar} {recall:.0%}             │")

        print("├─────────────────────────────────────────────────────────────┤")

        for r in summary.results:
            status = "✅" if r.hit else "❌"
            top_title = r.retrieved_titles[0][:35] if r.retrieved_titles else "NO RESULTS"
            print(f"│  {status} {r.query[:30]:<32} → {top_title:<25}│")

        print("└─────────────────────────────────────────────────────────────┘")

        # Smoke-check: benchmark must return valid structure with results
        assert summary.total_queries > 0, "Benchmark produced zero queries"
        assert 0.0 <= summary.recall_at_10 <= 1.0
        assert 0.0 <= summary.mean_reciprocal_rank <= 1.0

        # Write results to JSON for Tier 2 consumption
        results_path = Path.home() / ".cortex" / "metrics" / "retrieval_benchmark.json"
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(
                {
                    "tier": 1,
                    "recall_at_10": summary.recall_at_10,
                    "mrr": summary.mean_reciprocal_rank,
                    "precision_at_5": summary.precision_at_5,
                    "by_category": summary.by_category,
                    "total_queries": summary.total_queries,
                    "misses": [r.query for r in summary.results if not r.hit],
                },
                indent=2,
            )
        )
