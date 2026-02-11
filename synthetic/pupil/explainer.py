#!/usr/bin/env python3
"""
DecisionExplainer — Reconstructs human-readable narratives from Action context dicts.

Each Pupil Action carries a `context: Dict[str, float]` with the numeric factors
that drove the decision. This module interprets those factors into structured
explanations with factor ranking, risk classification, and natural language.

Usage:
    from pupil.explainer import DecisionExplainer
    explainer = DecisionExplainer()
    explanation = explainer.explain(action)
    print(explanation.narrative)     # "Agent churned primarily due to low satisfaction (0.35)..."
    print(explanation.factors)       # [Factor(name="satisfaction", value=0.35, direction="risk", ...)]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .persona import Action, ActionType


@dataclass
class Factor:
    """A single decision factor with its contribution assessment."""

    name: str
    value: float
    direction: str  # "risk" or "protective"
    weight: float  # 0-1 relative importance within this decision
    label: str  # Human-readable description


@dataclass
class Explanation:
    """Structured explanation for a single agent decision."""

    action_type: str
    agent_id: str
    step: int
    factors: List[Factor]
    narrative: str
    primary_driver: Optional[str] = None


# Factor metadata: defines how to interpret each context key per action type.
# direction_fn: given the value, returns "risk" or "protective"
# weight: relative importance (sums to ~1.0 within each action type)
# label_fn: produces human-readable description from value

_FACTOR_SPECS: Dict[str, Dict[str, dict]] = {
    ActionType.CHURN.value: {
        "satisfaction": {
            "direction_fn": lambda v: "risk" if v < 0.5 else "protective",
            "weight": 0.30,
            "label_fn": lambda v: f"satisfaction at {v:.2f}" + (" (below risk threshold 0.50)" if v < 0.5 else ""),
        },
        "monthly_churn_prob": {
            "direction_fn": lambda v: "risk" if v > 0.02 else "protective",
            "weight": 0.25,
            "label_fn": lambda v: f"monthly churn probability {v:.4f} ({v*12:.1%} annualized)",
        },
        "tenure_years": {
            "direction_fn": lambda v: "protective" if v > 3.0 else "risk",
            "weight": 0.15,
            "label_fn": lambda v: f"tenure {v:.1f} years" + (" (short tenure increases risk)" if v < 3.0 else ""),
        },
        "num_products": {
            "direction_fn": lambda v: "protective" if v >= 2 else "risk",
            "weight": 0.10,
            "label_fn": lambda v: f"{int(v)} products held" + (" (single product = less sticky)" if v < 2 else ""),
        },
        "tenure_modifier": {
            "direction_fn": lambda v: "protective" if v < 0.7 else "risk",
            "weight": 0.10,
            "label_fn": lambda v: f"tenure modifier {v:.2f}" + (" (loyalty reducing churn)" if v < 0.7 else ""),
        },
        "product_modifier": {
            "direction_fn": lambda v: "protective" if v < 0.7 else "risk",
            "weight": 0.10,
            "label_fn": lambda v: f"product modifier {v:.2f}",
        },
    },
    ActionType.MISS_PAYMENT.value: {
        "credit_score": {
            "direction_fn": lambda v: "risk" if v < 650 else "protective",
            "weight": 0.50,
            "label_fn": lambda v: f"credit score {int(v)}" + (" (below prime threshold)" if v < 650 else ""),
        },
        "miss_threshold": {
            "direction_fn": lambda _v: "risk",
            "weight": 0.30,
            "label_fn": lambda v: f"segment miss threshold {int(v)}",
        },
        "unemployment_rate": {
            "direction_fn": lambda v: "risk" if v > 7.0 else "protective",
            "weight": 0.20,
            "label_fn": lambda v: f"unemployment {v:.1f}%" + (" (elevated)" if v > 7.0 else ""),
        },
    },
    ActionType.DEFAULT.value: {
        "credit_score": {
            "direction_fn": lambda v: "risk" if v < 550 else "protective",
            "weight": 0.60,
            "label_fn": lambda v: f"credit score {int(v)} (severe distress)" if v < 450 else f"credit score {int(v)}",
        },
        "default_threshold": {
            "direction_fn": lambda _v: "risk",
            "weight": 0.40,
            "label_fn": lambda v: f"segment default threshold {int(v)}",
        },
    },
    ActionType.SWITCH_TO_COMPETITOR.value: {
        "switch_probability": {
            "direction_fn": lambda v: "risk" if v > 0.05 else "protective",
            "weight": 0.25,
            "label_fn": lambda v: f"switch probability {v:.4f}",
        },
        "competitor_susceptibility": {
            "direction_fn": lambda v: "risk" if v > 0.3 else "protective",
            "weight": 0.20,
            "label_fn": lambda v: f"competitor susceptibility {v:.2f}",
        },
        "satisfaction": {
            "direction_fn": lambda v: "risk" if v < 0.5 else "protective",
            "weight": 0.20,
            "label_fn": lambda v: f"satisfaction {v:.2f}",
        },
        "offered_rate": {
            "direction_fn": lambda v: "risk" if v > 0 else "protective",
            "weight": 0.15,
            "label_fn": lambda v: f"competitor offered rate {v:.2f}%",
        },
        "market_rate": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.10,
            "label_fn": lambda v: f"market average rate {v:.2f}%",
        },
        "impact_magnitude": {
            "direction_fn": lambda v: "risk" if v > 0.5 else "protective",
            "weight": 0.10,
            "label_fn": lambda v: f"event impact magnitude {v:.2f}",
        },
    },
    ActionType.ADOPT_PRODUCT.value: {
        "adoption_propensity": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.35,
            "label_fn": lambda v: f"adoption propensity {v:.2f}",
        },
        "monthly_rate": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.25,
            "label_fn": lambda v: f"effective monthly adoption rate {v:.4f}",
        },
        "num_products": {
            "direction_fn": lambda v: "protective" if v <= 3 else "risk",
            "weight": 0.20,
            "label_fn": lambda v: f"{int(v)} products held after adoption",
        },
        "target_products": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.20,
            "label_fn": lambda v: f"segment target {int(v)} products",
        },
    },
    ActionType.INCREASE_DEPOSITS.value: {
        "growth_amount": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.30,
            "label_fn": lambda v: f"deposit growth ${v:,.2f}",
        },
        "savings_rate": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.30,
            "label_fn": lambda v: f"savings rate {v:.2f}%",
        },
        "rate_threshold": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.20,
            "label_fn": lambda v: f"segment rate threshold {v:.2f}%",
        },
        "income": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.20,
            "label_fn": lambda v: f"annual income ${v:,.0f}",
        },
    },
    ActionType.DECREASE_DEPOSITS.value: {
        "withdrawal_amount": {
            "direction_fn": lambda _v: "risk",
            "weight": 0.35,
            "label_fn": lambda v: f"withdrawal ${v:,.2f}",
        },
        "satisfaction": {
            "direction_fn": lambda v: "risk" if v < 0.5 else "protective",
            "weight": 0.40,
            "label_fn": lambda v: f"satisfaction {v:.2f} (driving withdrawal)",
        },
        "deposits_before": {
            "direction_fn": lambda _v: "protective",
            "weight": 0.25,
            "label_fn": lambda v: f"deposits before withdrawal ${v:,.2f}",
        },
    },
}


class DecisionExplainer:
    """Reconstructs narrative explanations from Action context dicts."""

    def explain(self, action: Action) -> Explanation:
        """Produce a structured explanation for a single action.

        Args:
            action: An Action with a populated context dict.

        Returns:
            Explanation with ranked factors and narrative string.
        """
        if not action.context:
            return Explanation(
                action_type=action.action_type.value,
                agent_id=action.agent_id,
                step=action.step,
                factors=[],
                narrative=f"Agent {action.agent_id} took action {action.action_type.value} at step {action.step} (no decision factors recorded).",
            )

        specs = _FACTOR_SPECS.get(action.action_type.value, {})
        factors: List[Factor] = []

        for key, value in action.context.items():
            spec = specs.get(key)
            if spec:
                factors.append(
                    Factor(
                        name=key,
                        value=value,
                        direction=spec["direction_fn"](value),
                        weight=spec["weight"],
                        label=spec["label_fn"](value),
                    )
                )
            else:
                # Unknown factor — include with neutral weight
                factors.append(
                    Factor(
                        name=key,
                        value=value,
                        direction="risk",
                        weight=0.0,
                        label=f"{key}={value:.4f}",
                    )
                )

        # Sort by weight descending — primary driver first
        factors.sort(key=lambda f: f.weight, reverse=True)

        primary = factors[0] if factors else None
        narrative = self._build_narrative(action, factors, primary)

        return Explanation(
            action_type=action.action_type.value,
            agent_id=action.agent_id,
            step=action.step,
            factors=factors,
            narrative=narrative,
            primary_driver=primary.name if primary else None,
        )

    def explain_batch(self, actions: List[Action]) -> List[Explanation]:
        """Explain a list of actions."""
        return [self.explain(a) for a in actions]

    def _build_narrative(
        self,
        action: Action,
        factors: List[Factor],
        primary: Optional[Factor],
    ) -> str:
        """Build a human-readable narrative from ranked factors."""
        action_name = action.action_type.value.replace("_", " ")

        if not primary:
            return f"Agent {action.agent_id} performed {action_name} at step {action.step}."

        risk_factors = [f for f in factors if f.direction == "risk" and f.weight > 0]
        protective_factors = [f for f in factors if f.direction == "protective" and f.weight > 0]

        parts = [f"Agent {action.agent_id} performed {action_name} at step {action.step}"]
        parts.append(f"primarily due to {primary.label}")

        if len(risk_factors) > 1:
            secondary_risks = [f.label for f in risk_factors[: 2] if f.name != primary.name]
            if secondary_risks:
                parts.append(f"compounded by {secondary_risks[0]}")

        if protective_factors:
            top_protective = protective_factors[0]
            parts.append(f"despite {top_protective.label}")

        return ", ".join(parts) + "."
