"""Recall results report rank + confidence, not a fake 0-1 similarity."""

from __future__ import annotations

from recall_confidence import annotate, mark_unranked


def test_mark_unranked_does_not_fabricate_a_similarity():
    """Graph-adjacency items had a hardcoded similarity_score: 0.5 — a claimed
    measurement that never happened. mark_unranked states the truth instead."""
    items = [{"id": "a", "score": 0.5}, {"id": "b", "similarity_score": 0.5}]
    out = mark_unranked(items, basis="graph-adjacency")
    for it in out:
        assert "similarity_score" not in it
        assert "fusion_score" not in it
        assert it["confidence"] == "unranked"
        assert it["retrieval_basis"] == "graph-adjacency"
    assert [it["rank"] for it in out] == [0, 1]


def test_annotate_assigns_rank_by_position():
    items = [{"score": 0.0167}, {"score": 0.0120}, {"score": 0.0089}]
    out = annotate(items)
    assert [it["rank"] for it in out] == [0, 1, 2]


def test_fusion_score_equals_raw_and_replaces_the_similarity_label():
    items = [{"score": 0.0167}]
    out = annotate(items)
    assert out[0]["fusion_score"] == 0.0167
    # Deprecated alias kept equal, so old callers do not break.
    assert out[0]["similarity_score"] == 0.0167


def test_single_result_is_high_confidence():
    out = annotate([{"score": 0.0167}])
    assert out[0]["confidence"] == "high"


def test_clear_top_result_is_high_confidence():
    # Top well above the median field.
    items = [{"score": 0.0167}, {"score": 0.004}, {"score": 0.004}, {"score": 0.003}]
    out = annotate(items)
    assert out[0]["confidence"] == "high"


def test_flat_field_is_low_confidence():
    """Everything scored alike -> the ranking distinguished nothing."""
    items = [{"score": 0.0167}, {"score": 0.0166}, {"score": 0.0165}, {"score": 0.0164}]
    out = annotate(items)
    assert out[0]["confidence"] == "low"


def test_confidence_is_shared_across_the_set():
    items = [{"score": 0.02}, {"score": 0.004}, {"score": 0.004}]
    out = annotate(items)
    assert len({it["confidence"] for it in out}) == 1


def test_confidence_ignores_raw_magnitude():
    """Two fields with identical SHAPE but scaled magnitude get the same band —
    proving confidence tracks separation, not the near-constant RRF magnitude."""
    small = annotate([{"score": 0.0167}, {"score": 0.0080}, {"score": 0.0080}])
    big = annotate([{"score": 0.90}, {"score": 0.43}, {"score": 0.43}])
    assert small[0]["confidence"] == big[0]["confidence"]


def test_annotate_is_idempotent():
    items = [{"score": 0.0167}, {"score": 0.0089}]
    once = annotate(items)
    ranks_once = [it["rank"] for it in once]
    twice = annotate(once)
    assert [it["rank"] for it in twice] == ranks_once
    assert twice[0]["fusion_score"] == 0.0167


def test_reads_score_from_legacy_similarity_key():
    """Items already carrying only similarity_score still annotate."""
    out = annotate([{"similarity_score": 0.0167}, {"similarity_score": 0.0089}])
    assert out[0]["fusion_score"] == 0.0167
    assert out[0]["rank"] == 0


def test_empty_list_is_safe():
    assert annotate([]) == []


def test_rank1_ceiling_no_longer_reads_as_near_zero():
    """The whole point: 0.0167 (rank-1 ceiling) surfaces as rank 0 / high, not
    as a number a reader dismisses as 'basically zero'."""
    out = annotate([{"score": 0.0167}, {"score": 0.001}, {"score": 0.001}])
    top = out[0]
    assert top["rank"] == 0 and top["confidence"] == "high"
