#!/usr/bin/env python3
"""Tests for pre-mortem forecasting and mitigation routing."""

from intelligence.pre_mortem import Initiative, PreMortemEngine


def test_generates_sorted_failure_narratives():
    engine = PreMortemEngine()
    initiatives = [
        Initiative("low-risk", complexity=0.2, dependency_risk=0.2, deadline_pressure=0.2),
        Initiative("high-risk", complexity=0.9, dependency_risk=0.8, deadline_pressure=0.7),
    ]
    narratives = engine.generate(initiatives)
    assert narratives[0].initiative == "high-risk"
    assert narratives[0].risk_score > narratives[1].risk_score


def test_routes_mitigations_to_queue_actions():
    engine = PreMortemEngine()
    narratives = engine.generate(
        [Initiative("feature-rollout", complexity=0.8, dependency_risk=0.7, deadline_pressure=0.6)]
    )
    actions = engine.route_mitigations(narratives)
    assert actions
    assert all(a["task_type"] == "research" for a in actions)
    assert all("pre-mortem:risk=" in a["context"] for a in actions)

