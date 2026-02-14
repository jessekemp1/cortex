#!/usr/bin/env python3
"""
Decision Twin Engine

Simulates alternative weekly execution plans and ranks them by a
compound utility score that balances shipped impact, focus cost, and risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class PlanTask:
    """Single task used in a plan simulation."""

    title: str
    impact_points: float
    effort_hours: float
    focus_cost: float
    risk: float = 0.0


@dataclass(frozen=True)
class PlanScenario:
    """Alternative weekly plan candidate."""

    scenario_id: str
    name: str
    tasks: tuple[PlanTask, ...]
    notes: str = ""


@dataclass(frozen=True)
class ScenarioScore:
    """Scored scenario payload returned by DecisionTwinEngine."""

    scenario_id: str
    name: str
    shipped_impact: float
    total_effort_hours: float
    total_focus_cost: float
    total_risk: float
    utility_score: float
    rationale: str = ""


@dataclass(frozen=True)
class TwinWeights:
    """Weights for multi-objective scoring."""

    impact_weight: float = 1.0
    focus_penalty: float = 0.6
    risk_penalty: float = 0.8
    effort_penalty: float = 0.15


@dataclass
class DecisionTwinEngine:
    """Simulate and rank weekly plan scenarios."""

    weights: TwinWeights = field(default_factory=TwinWeights)

    def score_scenario(self, scenario: PlanScenario) -> ScenarioScore:
        shipped_impact = sum(task.impact_points for task in scenario.tasks)
        total_effort = sum(max(task.effort_hours, 0.0) for task in scenario.tasks)
        total_focus = sum(max(task.focus_cost, 0.0) for task in scenario.tasks)
        total_risk = sum(max(task.risk, 0.0) for task in scenario.tasks)

        utility = (
            self.weights.impact_weight * shipped_impact
            - self.weights.focus_penalty * total_focus
            - self.weights.risk_penalty * total_risk
            - self.weights.effort_penalty * total_effort
        )

        rationale = (
            f"impact={shipped_impact:.2f}, focus={total_focus:.2f}, "
            f"risk={total_risk:.2f}, effort={total_effort:.2f}"
        )

        return ScenarioScore(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            shipped_impact=round(shipped_impact, 3),
            total_effort_hours=round(total_effort, 3),
            total_focus_cost=round(total_focus, 3),
            total_risk=round(total_risk, 3),
            utility_score=round(utility, 3),
            rationale=rationale,
        )

    def rank_scenarios(self, scenarios: Iterable[PlanScenario]) -> list[ScenarioScore]:
        scored = [self.score_scenario(scenario) for scenario in scenarios]
        return sorted(scored, key=lambda item: item.utility_score, reverse=True)

    def choose_best(self, scenarios: Iterable[PlanScenario]) -> ScenarioScore:
        ranked = self.rank_scenarios(scenarios)
        if not ranked:
            raise ValueError("At least one scenario is required")
        return ranked[0]

