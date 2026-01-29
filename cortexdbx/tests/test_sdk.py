"""Tests for CortexDBx SDK client (local backend)."""

import pytest
from cortexdbx.sdk.client import CortexDBxClient, CortexDBxConfig


def test_client_default_uses_local_backend():
    client = CortexDBxClient()
    assert client._local is not None


def test_client_log_outcome_returns_id():
    client = CortexDBxClient()
    outcome_id = client.log_outcome(
        context={"alert_type": "fraud", "amount": "high"},
        strategy="escalate_to_analyst",
        result="SUCCESS",
        evidence={"alert_id": "ALT-123"},
    )
    assert outcome_id is not None
    assert len(outcome_id) == 36  # UUID length with hyphens


def test_client_recommend_after_logging():
    client = CortexDBxClient()
    ctx = {"table": "orders", "operation": "aggregate"}
    client.log_outcome(ctx, "incremental_refresh", "SUCCESS")
    client.log_outcome(ctx, "incremental_refresh", "SUCCESS")
    client.log_outcome(ctx, "full_scan", "FAILURE")

    recs = client.recommend(ctx, min_confidence=0.3, limit=5)
    assert len(recs) >= 1
    assert recs[0]["strategy_name"] == "incremental_refresh"
    assert recs[0]["confidence"] > 0.5
    assert "explanation" in recs[0]


def test_client_recommend_empty_without_data():
    client = CortexDBxClient()
    recs = client.recommend({"unknown": "context"}, min_confidence=0.5)
    assert recs == []


def test_client_get_confidence():
    client = CortexDBxClient()
    ctx = {"domain": "test", "key": "value"}
    client.log_outcome(ctx, "strategy_a", "SUCCESS")
    client.log_outcome(ctx, "strategy_a", "SUCCESS")
    client.log_outcome(ctx, "strategy_a", "FAILURE")

    conf, explanation = client.get_confidence(ctx, "strategy_a")
    assert conf > 0.5
    assert "confidence" in explanation.lower()
    assert "successes" in explanation.lower()


def test_client_get_confidence_no_data():
    client = CortexDBxClient()
    conf, explanation = client.get_confidence({"x": "y"}, "nonexistent")
    assert conf == 0.5
    assert "No historical data" in explanation


def test_client_same_context_same_hash():
    client = CortexDBxClient()
    ctx1 = {"a": 1, "b": 2}
    ctx2 = {"b": 2, "a": 1}
    h1 = client._fingerprint_context(ctx1)
    h2 = client._fingerprint_context(ctx2)
    assert h1 == h2


def test_client_multiple_strategies_ranked_by_confidence():
    client = CortexDBxClient()
    ctx = {"domain": "test"}
    for _ in range(5):
        client.log_outcome(ctx, "good_strategy", "SUCCESS")
    for _ in range(5):
        client.log_outcome(ctx, "bad_strategy", "FAILURE")

    recs = client.recommend(ctx, min_confidence=0.0, limit=10)
    assert len(recs) == 2
    assert recs[0]["strategy_name"] == "good_strategy"
    assert recs[0]["confidence"] > recs[1]["confidence"]
