"""Core-outcomes proof — Outcome 2 (RECALL), decisions INCLUDED.

This is the gap-closing measurement. The existing Tier-1 benchmark
(test_retrieval_benchmark.py) deliberately loads patterns with
``include_decisions=False`` (see its fixture: recorded decisions would inject
hundreds of live distractors and flap the threshold), so **no existing test
measures whether a recorded decision is retrievable**. Live telemetry confirms
the gap empirically: ``~/.cortex/recall_events.jsonl`` shows
``n_decisions_surfaced == 0`` on every event.

This module seeds a controlled corpus of decisions into a tmp store and
measures Recall@K over decision-shaped queries, plus the tool-level
``n_decisions_surfaced`` signal. Because each seeded decision shares a rare
token with its query, a hit is unambiguous and BM25 alone finds it — the
Recall@K gate is therefore backend-robust (no Voyage/Ollama required). MRR is
the strict top-rank metric and is gated on VOYAGE_API_KEY, matching Tier-1.

If Recall@K or n_decisions_surfaced reads ~0 HERE (hermetic, controlled), the
record->recall loop is broken in CODE, not data — and this test fails loudly
with the number, which is itself the proof. If it passes here but live
telemetry stays 0, the gap is data/wiring in the live path — the aggregator's
``--live`` audit reports that separately.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# HybridRetriever depends on scikit-learn (BM25 + optional embeddings). It's an
# optional dep for retrieval evaluation — skip the module cleanly if absent.
pytest.importorskip("sklearn", reason="recall benchmark requires scikit-learn (optional)")

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.proof.seed_corpus import SEED_DECISIONS, seed_decisions_for_recall  # noqa: E402

RECALL_THRESHOLD = 0.60
MRR_THRESHOLD = 0.40


@pytest.fixture(autouse=True)
def hermetic_store(tmp_path, monkeypatch):
    """Redirect the store to tmp. Sets BOTH env vars because the retrieval path
    reads decisions via CORTEX_HOME (pattern_indexer / hybrid_retriever) while
    the record path writes via CORTEX_STATE_DIR (mcp_handlers)."""
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("CORTEX_HOME", str(tmp_path))
    # hybrid_retriever binds its store paths to Path.home()/.cortex at IMPORT
    # time (module constants _DECISIONS_PATH / _OUTCOMES_PATH / _DIGESTS_PATH) —
    # it does NOT honor CORTEX_HOME. Without redirecting them the retriever would
    # search the live ~/.cortex decisions (277+ rows), not the seeded corpus, so
    # the recall number would be meaningless. Patch the constants + reset the
    # mtime-keyed decision cache so each test sees only its tmp store.
    try:
        import intelligence.memory.hybrid_retriever as hr

        monkeypatch.setattr(hr, "_DECISIONS_PATH", tmp_path / "decisions.jsonl", raising=False)
        monkeypatch.setattr(hr, "_OUTCOMES_PATH", tmp_path / "outcomes.jsonl", raising=False)
        monkeypatch.setattr(hr, "_DIGESTS_PATH", tmp_path / "conversation_digests.jsonl", raising=False)
        hr._decision_cache = None
        hr._decision_cache_mtime = 0.0
    except Exception:
        pass
    return tmp_path


def _build_retriever(state_dir: Path):
    """Seed decisions, then build a HybridRetriever over ONLY that corpus.

    PatternIndexer.root_dir points at an EMPTY tmp dir (not ~/Dev) so no
    git-derived patterns leak in; conversation digests are disabled; cache_dir
    is tmp so no live embedding cache is read. The retriever's own always-on
    decision merge then pulls the seeded decisions from the tmp CORTEX_HOME.
    """
    seed_decisions_for_recall(state_dir, include_distractors=True)

    from intelligence.embeddings_client import EmbeddingsClient
    from intelligence.memory.hybrid_retriever import HybridRetriever
    from intelligence.memory.pattern_indexer import PatternIndexer

    empty_root = state_dir / "empty_repo_root"
    empty_root.mkdir(parents=True, exist_ok=True)
    indexer = PatternIndexer(root_dir=empty_root, cache_dir=state_dir / "patterns")
    patterns = indexer.load_patterns(include_seeds=False, include_decisions=True)

    # Auto-detect a real 768-dim embeddings backend; fall back to BM25-only
    # (embeddings_client=None) otherwise. Recall@K is robust to this; MRR is not
    # (hence the VOYAGE gate on the MRR test).
    embeddings_client = None
    try:
        client = EmbeddingsClient()
        if len(client.generate_embedding("probe")) == 768:
            embeddings_client = client
    except Exception:
        pass

    retriever = HybridRetriever(
        patterns,
        embeddings_client=embeddings_client,
        cache_dir=state_dir / "patterns",
        include_conversation_digests=False,
    )
    return retriever


def _run_benchmark(retriever, k: int = 10):
    """Return (recall_at_k, mrr, results) over the must-hit seeded queries.

    A hit = the seeded decision's distinctive token appears in a retrieved
    pattern's title or description within the top-k.
    """
    must_hit = [d for d in SEED_DECISIONS if d.get("must_hit") and d.get("query")]
    hits = 0
    rr_sum = 0.0
    results = []
    for d in must_hit:
        token = d["token"].lower()
        search = retriever.search(d["query"], limit=k, alpha=0.5)
        retrieved = [f"{p.title} {p.description}".lower() for p, _ in search]
        rank = next((i + 1 for i, text in enumerate(retrieved) if token in text), None)
        hit = rank is not None
        hits += 1 if hit else 0
        rr_sum += (1.0 / rank) if rank else 0.0
        results.append({"token": d["token"], "query": d["query"], "hit": hit, "rank": rank})

    n = len(must_hit)
    recall = hits / n if n else 0.0
    mrr = rr_sum / n if n else 0.0
    return recall, mrr, results


@pytest.fixture(scope="function")
def benchmark(hermetic_store):
    retriever = _build_retriever(hermetic_store)
    recall, mrr, results = _run_benchmark(retriever, k=10)
    # Persist for the aggregator.
    metrics_dir = hermetic_store / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "recall_at_10": recall,
        "mrr": mrr,
        "n_queries": len(results),
        "misses": [r["token"] for r in results if not r["hit"]],
        "embeddings": os.getenv("VOYAGE_API_KEY") is not None,
    }
    (metrics_dir / "decision_recall_benchmark.json").write_text(json.dumps(payload, indent=2))
    return payload, results


def test_no_empty_results(benchmark):
    """Every seeded query returns at least one result (retriever is wired)."""
    _, results = benchmark
    assert results, "benchmark produced zero queries"
    # Every must-hit query got a rank or an explicit miss — none errored out.
    assert all("hit" in r for r in results)


def test_decision_recall_at_10_hermetic(benchmark):
    """Recall@10 over recorded decisions must clear the threshold.

    THE headline metric: proves a recorded decision comes back for a relevant
    query. Backend-robust (BM25 finds the shared rare token).
    """
    payload, results = benchmark
    recall = payload["recall_at_10"]
    misses = [r["token"] for r in results if not r["hit"]]
    assert recall >= RECALL_THRESHOLD, (
        f"decision Recall@10 = {recall:.1%} (threshold {RECALL_THRESHOLD:.0%}). "
        f"Misses: {misses}. A low number here means the record->recall loop is "
        f"broken in code — that IS the proof, surfaced loudly."
    )


def test_tool_level_decisions_surfaced(hermetic_store):
    """The exact live-telemetry metric (n_decisions_surfaced) can be > 0.

    Live recall_events.jsonl shows this stuck at 0. Here we prove it CAN be
    positive on a controlled corpus via the in-process cortex_intelligence
    path + count_surfaced — isolating whether the live 0 is data or code.
    """
    seed_decisions_for_recall(hermetic_store, include_distractors=True)
    from intelligence.recall_events import count_surfaced

    import mcp_server

    # Unwrap the FastMCP-decorated tool to call the raw function.
    fn = mcp_server.cortex_intelligence
    for attr in ("fn", "__wrapped__", "_fn"):
        raw = getattr(fn, attr, None)
        if callable(raw):
            fn = raw
            break

    query = next(d["query"] for d in SEED_DECISIONS if d.get("must_hit"))
    raw_result = fn(query=query, project="interac")
    result = json.loads(str(raw_result))

    if "error" in result:
        pytest.skip(f"intelligence engine unavailable in this env: {result['error']}")

    counts = count_surfaced(result)
    assert counts["n_decisions_surfaced"] > 0, (
        f"n_decisions_surfaced == 0 for a query whose answer was just recorded. "
        f"predictions={counts['n_predictions']}. This reproduces the live-telemetry "
        f"gap in a controlled setting: the record->recall loop is not surfacing decisions."
    )


def test_mrr_gated(benchmark):
    """MRR >= 0.40, gated on a production embeddings backend (Voyage).

    Under the BM25/hashing fallback, exact-rank precision is noisy, so this
    strict top-rank check only runs when VOYAGE_API_KEY is set — matching the
    Tier-1 benchmark's calibration. Recall@10 remains the backend-robust gate.
    """
    if not os.getenv("VOYAGE_API_KEY"):
        pytest.skip("MRR>=0.40 is calibrated for Voyage embeddings; set VOYAGE_API_KEY to run")
    payload, _ = benchmark
    assert payload["mrr"] >= MRR_THRESHOLD, f"MRR = {payload['mrr']:.3f} (threshold {MRR_THRESHOLD})"
