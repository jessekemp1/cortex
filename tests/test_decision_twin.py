#!/usr/bin/env python3
"""Tests for Decision Twin Engine."""

from intelligence.decision_twin import DecisionTwinEngine, PlanScenario, PlanTask


def test_ranks_higher_impact_scenario_with_lower_focus_penalty():
    engine = DecisionTwinEngine()

    scenario_a = PlanScenario(
        scenario_id="A",
        name="Balanced",
        tasks=(
            PlanTask("Ship forecasting endpoint", impact_points=10, effort_hours=8, focus_cost=3, risk=1),
            PlanTask("Stabilize tests", impact_points=6, effort_hours=5, focus_cost=2, risk=1),
        ),
    )
    scenario_b = PlanScenario(
        scenario_id="B",
        name="Noisy Sprint",
        tasks=(
            PlanTask("Many small tasks", impact_points=11, effort_hours=10, focus_cost=8, risk=2),
        ),
    )

    ranked = engine.rank_scenarios([scenario_b, scenario_a])
    assert ranked[0].scenario_id == "A"
    assert ranked[0].utility_score > ranked[1].utility_score


def test_choose_best_requires_non_empty_input():
    engine = DecisionTwinEngine()
    try:
        engine.choose_best([])
        assert False, "expected ValueError"
    except ValueError:
        assert True

