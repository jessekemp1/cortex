#!/usr/bin/env python3
"""
Simulation Engine — Time-stepping orchestrator for Pupil agent simulations.

Runs N PersonaAgents through a MarketEnvironment timeline, collecting
actions and snapshots at each step. Supports:
- Configurable agent pool sizes and segment mixes
- Event injection via build_timeline schedules
- Deterministic replay via seed control
- Per-step and aggregate result collection

Architecture:
    SyntheticGenerator → profiles → PersonaAgent pool
    → SimulationEngine.run(timeline) → StepResult[] → SimulationResult
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .market_env import MarketEnvironment
from .persona import Action, PersonaAgent
from .schemas import CustomerProfile
from .segment_models import get_behavior


@dataclass
class StepResult:
    """Results from a single simulation step (month)."""

    step: int
    date_label: str
    actions: List[Action]
    snapshots: List[Dict[str, Any]]

    # Aggregates (computed after collection)
    n_active: int = 0
    n_at_risk: int = 0
    n_churned: int = 0
    total_actions: int = 0
    churn_count: int = 0
    adoption_count: int = 0
    switch_count: int = 0
    miss_count: int = 0
    default_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "date_label": self.date_label,
            "n_active": self.n_active,
            "n_at_risk": self.n_at_risk,
            "n_churned": self.n_churned,
            "total_actions": self.total_actions,
            "churn_count": self.churn_count,
            "adoption_count": self.adoption_count,
            "switch_count": self.switch_count,
            "miss_count": self.miss_count,
            "default_count": self.default_count,
        }


@dataclass
class SimulationResult:
    """Complete simulation results."""

    n_agents: int
    n_steps: int
    steps: List[StepResult]
    final_snapshots: List[Dict[str, Any]]
    all_actions: List[Action] = field(default_factory=list)

    @property
    def total_churned(self) -> int:
        return sum(1 for s in self.final_snapshots if s["state"] == "churned")

    @property
    def churn_rate(self) -> float:
        if self.n_agents == 0:
            return 0.0
        return self.total_churned / self.n_agents

    @property
    def avg_final_satisfaction(self) -> float:
        active = [s["satisfaction"] for s in self.final_snapshots if s["state"] != "churned"]
        if not active:
            return 0.0
        return sum(active) / len(active)

    def summary(self) -> str:
        return (
            f"Simulation: {self.n_agents} agents × {self.n_steps} months | "
            f"Churn: {self.total_churned}/{self.n_agents} ({self.churn_rate:.1%}) | "
            f"Avg satisfaction: {self.avg_final_satisfaction:.3f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_agents": self.n_agents,
            "n_steps": self.n_steps,
            "churn_rate": round(self.churn_rate, 4),
            "total_churned": self.total_churned,
            "avg_final_satisfaction": round(self.avg_final_satisfaction, 4),
            "steps": [s.to_dict() for s in self.steps],
        }


class SimulationEngine:
    """
    Time-stepping simulation engine for PersonaAgent populations.

    Generates agents from SynthFinServ profiles, steps them through
    a MarketEnvironment timeline, and collects behavioral data.
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.agents: List[PersonaAgent] = []

    def generate_agents(
        self,
        profiles: List[CustomerProfile],
        seed: Optional[int] = None,
    ) -> List[PersonaAgent]:
        """
        Create PersonaAgents from SynthFinServ profiles.

        Each agent gets a unique seed derived from the engine seed
        for deterministic but varied behavior.
        """
        base_seed = seed or self.seed or 42
        self.agents = []

        for i, profile in enumerate(profiles):
            behavior = get_behavior(profile.segment)
            agent = PersonaAgent(
                profile=profile,
                behavior=behavior,
                seed=base_seed + i,
            )
            self.agents.append(agent)

        return self.agents

    def run(
        self,
        timeline: List[MarketEnvironment],
        agents: Optional[List[PersonaAgent]] = None,
    ) -> SimulationResult:
        """
        Run simulation through the full timeline.

        Args:
            timeline: List of MarketEnvironment, one per month
            agents: Optional agent list. If None, uses self.agents.

        Returns:
            SimulationResult with per-step and aggregate data
        """
        agents = agents or self.agents
        if not agents:
            raise ValueError("No agents. Call generate_agents() first or pass agents.")

        step_results = []
        all_actions = []

        for env in timeline:
            step_actions = []
            step_snapshots = []

            for agent in agents:
                actions = agent.step(env)
                step_actions.extend(actions)

                # Snapshot after stepping (captures updated state)
                step_snapshots.append(agent.snapshot())

            # Build step result with aggregates
            result = StepResult(
                step=env.step,
                date_label=env.date_label,
                actions=step_actions,
                snapshots=step_snapshots,
            )
            self._compute_step_aggregates(result)
            step_results.append(result)
            all_actions.extend(step_actions)

        # Final snapshots from last step
        final_snapshots = step_results[-1].snapshots if step_results else []

        return SimulationResult(
            n_agents=len(agents),
            n_steps=len(timeline),
            steps=step_results,
            final_snapshots=final_snapshots,
            all_actions=all_actions,
        )

    def _compute_step_aggregates(self, result: StepResult):
        """Compute aggregate counts for a step result."""
        result.n_active = sum(1 for s in result.snapshots if s["state"] == "active")
        result.n_at_risk = sum(1 for s in result.snapshots if s["state"] == "at_risk")
        result.n_churned = sum(1 for s in result.snapshots if s["state"] == "churned")
        result.total_actions = len(result.actions)
        result.churn_count = sum(1 for a in result.actions if a.action_type.value == "churn")
        result.adoption_count = sum(
            1 for a in result.actions if a.action_type.value == "adopt_product"
        )
        result.switch_count = sum(1 for a in result.actions if a.action_type.value == "switch")
        result.miss_count = sum(1 for a in result.actions if a.action_type.value == "miss_payment")
        result.default_count = sum(1 for a in result.actions if a.action_type.value == "default")
