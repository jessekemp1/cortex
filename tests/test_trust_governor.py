#!/usr/bin/env python3
"""Tests for Trust Governor policy transitions."""

from intelligence.trust_governor import TrustGovernor


def test_promotes_on_strong_calibration_signals(monkeypatch):
    governor = TrustGovernor()

    monkeypatch.setattr(
        governor,
        "_load_calibration_stats",
        lambda: {
            "total_predictions": 30,
            "accuracy": 0.82,
            "calibration_error": 0.11,
            "overconfidence_index": 0.04,
        },
    )
    decision = governor.evaluate(current_level=1)
    assert decision["action"] == "promote"
    assert decision["next_level"] == 2


def test_degrades_on_trust_gate_breach(monkeypatch):
    governor = TrustGovernor()

    monkeypatch.setattr(
        governor,
        "_load_calibration_stats",
        lambda: {
            "total_predictions": 30,
            "accuracy": 0.35,
            "calibration_error": 0.5,
            "overconfidence_index": 0.4,
        },
    )
    decision = governor.evaluate(current_level=2)
    assert decision["action"] == "degrade"
    assert decision["next_level"] == 1

