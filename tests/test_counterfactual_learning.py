#!/usr/bin/env python3
"""Tests for Counterfactual Learning ledger."""

from pathlib import Path

from intelligence.counterfactual_learning import CounterfactualLedger


def test_logs_and_summarizes_follow_rate(tmp_path: Path):
    ledger = CounterfactualLedger(path=tmp_path / "counterfactuals.jsonl")
    ledger.record(
        recommendation_id="r1",
        project="cortex",
        recommended_action="queue_now",
        chosen_action="queue_now",
        expected_value=5.0,
        actual_value=4.8,
        confidence=0.7,
    )
    ledger.record(
        recommendation_id="r2",
        project="vortex",
        recommended_action="queue_now",
        chosen_action="skip",
        expected_value=3.0,
        actual_value=0.5,
        confidence=0.6,
    )

    summary = ledger.summarize()
    assert summary["count"] == 2
    assert summary["follow_rate"] == 0.5
    assert summary["missed_value_estimate"] >= 2.0


def test_missed_value_uses_expected_when_actual_missing(tmp_path: Path):
    ledger = CounterfactualLedger(path=tmp_path / "counterfactuals.jsonl")
    ledger.record(
        recommendation_id="r3",
        project="alpha_arena",
        recommended_action="investigate_first",
        chosen_action="queue_now",
        expected_value=2.5,
        actual_value=None,
    )

    summary = ledger.summarize()
    assert summary["missed_value_estimate"] == 2.5

