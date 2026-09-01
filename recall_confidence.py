"""Report recall results with rank and a confidence band, not a fake similarity.

The score attached to recall results is a Reciprocal Rank Fusion value:
`sum(1 / (k + rank))` with k=60 (intelligence/memory/hybrid_retriever.py). So a
rank-1 hit scores 1/60 = 0.0167 — the CEILING — and rank 53 scores 0.0089. It was
emitted to MCP callers as `similarity_score`, which reads as a 0-1 cosine
similarity and is not one. It is bounded near 0.016, has no visible scale, and
0.0167-vs-0.0089 looks like "both near zero" when it actually means rank 1 vs
rank 53. That mislabelling led a reader (me) to call working retrieval "noise".

This module reports what the number actually is:

  * fusion_score — the raw RRF value, named for what it is.
  * rank         — 0-based position, the thing the score really encodes.
  * confidence   — high/medium/low from the SEPARATION between the top result
                   and the rest, not from raw magnitude (magnitude only encodes
                   rank and is near-constant). A clear top result is high
                   confidence; a flat field where everything scored alike is low,
                   because nothing distinguished the winner.

`similarity_score` is kept as a deprecated alias equal to fusion_score so no
existing caller breaks. Remove it once no consumer reads the old key
(grep `similarity_score` across callers returns only this module's tests).
"""

from __future__ import annotations

from statistics import median
from typing import Any, Dict, List

SCORE_KEYS = ("score", "similarity_score", "fusion_score")

# Separation thresholds: top score's relative lift over the median of the field.
# Derived from the RRF geometry — rank-1 vs rank-2 differ ~2% (0.01667 vs
# 0.01639), so a top result that stands clearly above the median field is a
# real signal, while a field bunched within a few percent distinguishes nothing.
_HIGH_SEPARATION = 0.25   # top >=25% above median field
_LOW_SEPARATION = 0.05    # top <5% above median field -> nothing stood out


def _raw_score(item: Dict[str, Any]) -> float:
    for k in SCORE_KEYS:
        v = item.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _confidence_band(scores: List[float]) -> str:
    """One band for the whole result set, from top-vs-median separation.

    Single result: 'high' — there is nothing it could be confused with.
    All-equal field: 'low' — the ranking distinguished nothing.
    """
    if not scores:
        return "low"
    if len(scores) == 1:
        return "high"
    top = max(scores)
    med = median(scores)
    if med <= 0:
        # Degenerate field (all zero or negative): magnitude tells us nothing.
        return "low" if top <= 0 else "medium"
    separation = (top - med) / med
    if separation >= _HIGH_SEPARATION:
        return "high"
    if separation < _LOW_SEPARATION:
        return "low"
    return "medium"


def mark_unranked(items: List[Dict[str, Any]], basis: str) -> List[Dict[str, Any]]:
    """Label results that were retrieved WITHOUT a similarity score.

    Graph-adjacency results (a project's lessons/patterns promoted into
    similar_work) have no retrieval score — they are neighbours, not ranked
    matches. Emitting a fabricated `similarity_score: 0.5` for them claimed a
    measurement that never happened, which is the exact thing this initiative
    exists to stop. This states the truth instead: a rank by position, an
    explicit `retrieval_basis`, and confidence "unranked". No fusion_score or
    similarity_score is attached, because none was measured.
    """
    for rank, it in enumerate(items):
        it["rank"] = rank
        it["confidence"] = "unranked"
        it["retrieval_basis"] = basis
        it.pop("fusion_score", None)
        it.pop("similarity_score", None)
    return items


def annotate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach fusion_score, rank, and a shared confidence band to recall items.

    Mutates and returns the same list (callers build these dicts locally and
    expect the annotated list back). Idempotent: re-annotating recomputes rather
    than stacking. Assumes items are already in descending score order, which is
    how the retriever returns them; rank is assigned by position.
    """
    if not items:
        return items
    scores = [_raw_score(it) for it in items]
    band = _confidence_band(scores)
    for rank, (it, sc) in enumerate(zip(items, scores)):
        it["fusion_score"] = sc
        it["rank"] = rank
        it["confidence"] = band
        # Deprecated alias, kept equal to fusion_score for one release so a
        # caller still reading similarity_score does not break.
        it["similarity_score"] = sc
    return items
