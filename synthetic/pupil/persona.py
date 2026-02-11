#!/usr/bin/env python3
"""
Persona Agent — Behavioral financial consumer agent for Pupil simulations.

Each PersonaAgent wraps a SynthFinServ CustomerProfile with:
- Segment-calibrated behavioral model (from segment_models.py)
- Lifecycle state machine (onboarding → active → at_risk → churned)
- Decision memory (past actions influence future decisions)
- Monthly step function (observe environment → decide → act)

Agents are stateful: credit score, deposits, products, and satisfaction
evolve over time based on market conditions and their own decisions.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .schemas import CustomerProfile
from .segment_models import SegmentBehavior, get_behavior
from .market_env import MarketEnvironment


class LifecycleState(str, Enum):
    """Agent lifecycle stages."""

    ONBOARDING = "onboarding"
    ACTIVE = "active"
    AT_RISK = "at_risk"
    CHURNED = "churned"
    DORMANT = "dormant"


class ActionType(str, Enum):
    """Types of actions an agent can take."""

    HOLD = "hold"
    ADOPT_PRODUCT = "adopt_product"
    DROP_PRODUCT = "drop_product"
    SWITCH_TO_COMPETITOR = "switch"
    INCREASE_DEPOSITS = "increase_deposits"
    DECREASE_DEPOSITS = "decrease_deposits"
    MISS_PAYMENT = "miss_payment"
    DEFAULT = "default"
    CHURN = "churn"


@dataclass
class Action:
    """A discrete action taken by an agent at a time step."""

    action_type: ActionType
    agent_id: str
    step: int
    product: Optional[str] = None
    amount: Optional[float] = None
    target: Optional[str] = None
    reason: str = ""
    context: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "agent_id": self.agent_id,
            "step": self.step,
            "product": self.product,
            "amount": self.amount,
            "target": self.target,
            "reason": self.reason,
            "context": self.context,
        }


class PersonaAgent:
    """
    A synthetic financial consumer with behavioral intelligence.

    Wraps a SynthFinServ CustomerProfile with segment-calibrated
    behavioral rules, lifecycle state, and decision memory.
    """

    def __init__(
        self,
        profile: CustomerProfile,
        behavior: Optional[SegmentBehavior] = None,
        seed: Optional[int] = None,
    ):
        self.profile = profile
        self.agent_id = profile.profile_id
        self.behavior = behavior or get_behavior(profile.segment)
        self._rng = random.Random(seed)

        # Mutable state
        self.state = LifecycleState.ACTIVE
        self.satisfaction = 0.75 + self._rng.random() * 0.20  # 0.75-0.95
        self.products = list(profile.products_held)
        self.credit_score = profile.credit_score
        self.deposits = profile.total_deposits
        self.income = profile.annual_income
        self.tenure_months = int(profile.tenure_years * 12)

        # Memory
        self.memory: List[Action] = []
        self.months_at_risk = 0
        self.months_since_last_adoption = 0
        self._baseline_boc_rate: Optional[float] = None

    @property
    def tenure_years(self) -> float:
        return self.tenure_months / 12.0

    def step(self, env: MarketEnvironment) -> List[Action]:
        """
        Process one time step (month). Agent observes environment,
        evaluates satisfaction, and makes decisions.
        """
        if self.state == LifecycleState.CHURNED:
            return []

        if self._baseline_boc_rate is None:
            self._baseline_boc_rate = env.boc_overnight_rate

        actions = []
        self.tenure_months += 1
        self.months_since_last_adoption += 1

        # 1. Update satisfaction based on environment
        self._update_satisfaction(env)

        # 2. Check for stress events
        stress_actions = self._check_stress(env)
        actions.extend(stress_actions)

        # 3. Check for churn
        churn_action = self._check_churn(env)
        if churn_action:
            actions.append(churn_action)
            self.memory.extend(actions)
            return actions

        # 4. Check for competitive switching
        switch_actions = self._check_competitive_switch(env)
        actions.extend(switch_actions)

        # 5. Check for product adoption
        adopt_actions = self._check_product_adoption(env)
        actions.extend(adopt_actions)

        # 6. Check deposit behavior
        deposit_actions = self._check_deposit_behavior(env)
        actions.extend(deposit_actions)

        # If nothing happened, record HOLD
        if not actions:
            actions.append(
                Action(
                    action_type=ActionType.HOLD,
                    agent_id=self.agent_id,
                    step=env.step,
                    reason="No action triggers met",
                )
            )

        # Update state machine
        self._update_lifecycle_state()

        # Record to memory
        self.memory.extend(actions)

        return actions

    def _update_satisfaction(self, env: MarketEnvironment):
        """Adjust satisfaction based on market conditions."""
        delta = 0.0

        # Rate changes
        rate_change = env.boc_overnight_rate - self._baseline_boc_rate
        if rate_change > 0.25 and "mortgage" in self.products:
            delta -= rate_change * 0.05 * self.behavior.rate_sensitivity
        elif rate_change < -0.25 and self.deposits > 50000:
            delta -= abs(rate_change) * 0.03 * self.behavior.rate_sensitivity

        # Unemployment pressure
        if env.unemployment_rate > 7.0:
            delta -= (env.unemployment_rate - 7.0) * 0.02 * self.behavior.unemployment_sensitivity

        # Competition events
        for event in env.events:
            if event.affects_segment(self.profile.segment):
                if event.rate_offered and event.rate_offered > env.avg_savings_rate + 0.5:
                    delta -= event.impact_magnitude * 0.05 * self.behavior.competitor_susceptibility

        # Tenure loyalty bonus
        delta += self.behavior.loyalty_bonus_per_year / 12.0

        self.satisfaction = max(0.0, min(1.0, self.satisfaction + delta))

    def _check_stress(self, env: MarketEnvironment) -> List[Action]:
        """Check for financial stress events."""
        actions = []

        # Unemployment shock
        if env.unemployment_rate > 7.0:
            shock_prob = (
                (env.unemployment_rate - 7.0) * 0.01 * self.behavior.unemployment_sensitivity
            )
            if self._rng.random() < shock_prob:
                self.income *= 0.90
                self.credit_score = max(300, self.credit_score - 15)
                self.satisfaction -= 0.10

        # Payment miss
        if self.credit_score < self.behavior.payment_miss_threshold:
            miss_prob = (self.behavior.payment_miss_threshold - self.credit_score) / 300.0
            if self._rng.random() < miss_prob:
                self.credit_score = max(300, self.credit_score - 25)
                actions.append(
                    Action(
                        action_type=ActionType.MISS_PAYMENT,
                        agent_id=self.agent_id,
                        step=env.step,
                        reason=(
                            f"Credit {self.credit_score} below miss threshold "
                            f"{self.behavior.payment_miss_threshold}"
                        ),
                        context={
                            "credit_score": float(self.credit_score),
                            "miss_threshold": float(self.behavior.payment_miss_threshold),
                            "unemployment_rate": env.unemployment_rate,
                        },
                    )
                )

        # Default
        if self.credit_score < self.behavior.default_threshold:
            default_prob = (self.behavior.default_threshold - self.credit_score) / 200.0
            if self._rng.random() < default_prob:
                actions.append(
                    Action(
                        action_type=ActionType.DEFAULT,
                        agent_id=self.agent_id,
                        step=env.step,
                        reason=(
                            f"Credit {self.credit_score} below default threshold "
                            f"{self.behavior.default_threshold}"
                        ),
                        context={
                            "credit_score": float(self.credit_score),
                            "default_threshold": float(self.behavior.default_threshold),
                        },
                    )
                )
                self.credit_score = max(300, self.credit_score - 50)

        # Credit recovery in good conditions
        if env.unemployment_rate < 6.5 and self.credit_score < 750:
            self.credit_score = min(
                900, self.credit_score + int(self.behavior.credit_recovery_rate)
            )

        return actions

    def _check_churn(self, env: MarketEnvironment) -> Optional[Action]:
        """Check if agent churns this month."""
        monthly_churn = 1.0 - (1.0 - self.behavior.base_annual_churn_rate) ** (1.0 / 12.0)

        # Satisfaction modifiers
        if self.satisfaction < 0.4:
            monthly_churn *= 2.5
        elif self.satisfaction < 0.6:
            monthly_churn *= 1.5
        elif self.satisfaction > 0.85:
            monthly_churn *= 0.5

        # Tenure loyalty
        tenure_mod = max(0.3, 1.0 - self.tenure_years * self.behavior.loyalty_bonus_per_year * 12)
        monthly_churn *= tenure_mod

        # More products = stickier
        product_mod = max(0.4, 1.0 - len(self.products) * 0.08)
        monthly_churn *= product_mod

        if self._rng.random() < monthly_churn:
            self.state = LifecycleState.CHURNED
            return Action(
                action_type=ActionType.CHURN,
                agent_id=self.agent_id,
                step=env.step,
                reason=(
                    f"Churn (satisfaction={self.satisfaction:.2f}, "
                    f"tenure={self.tenure_years:.1f}yr, "
                    f"products={len(self.products)})"
                ),
                context={
                    "satisfaction": self.satisfaction,
                    "monthly_churn_prob": monthly_churn,
                    "tenure_years": self.tenure_years,
                    "num_products": float(len(self.products)),
                    "tenure_modifier": tenure_mod,
                    "product_modifier": product_mod,
                },
            )
        return None

    def _check_competitive_switch(self, env: MarketEnvironment) -> List[Action]:
        """Check if agent switches products to competitors."""
        actions = []

        for event in env.events:
            if not event.affects_segment(self.profile.segment):
                continue
            if event.event_type.value not in ("product_launch", "rate_change"):
                continue
            if not event.product or event.product not in self.products:
                continue

            switch_prob = (
                self.behavior.competitor_susceptibility
                * event.impact_magnitude
                * (1.0 - self.satisfaction)
            )

            if event.rate_offered and event.rate_offered > env.avg_savings_rate + 0.3:
                rate_bonus = (
                    (event.rate_offered - env.avg_savings_rate)
                    * self.behavior.rate_sensitivity
                    * 0.3
                )
                switch_prob += rate_bonus

            if self._rng.random() < switch_prob / 12.0:
                actions.append(
                    Action(
                        action_type=ActionType.SWITCH_TO_COMPETITOR,
                        agent_id=self.agent_id,
                        step=env.step,
                        product=event.product,
                        target=event.institution,
                        reason=(
                            f"Switch to {event.institution} "
                            f"(rate={event.rate_offered}, "
                            f"satisfaction={self.satisfaction:.2f})"
                        ),
                        context={
                            "switch_probability": switch_prob / 12.0,
                            "competitor_susceptibility": self.behavior.competitor_susceptibility,
                            "satisfaction": self.satisfaction,
                            "offered_rate": float(event.rate_offered or 0.0),
                            "market_rate": env.avg_savings_rate,
                            "impact_magnitude": event.impact_magnitude,
                        },
                    )
                )

        return actions

    def _check_product_adoption(self, env: MarketEnvironment) -> List[Action]:
        """Check if agent adopts new products."""
        actions = []
        monthly_adoption = self.behavior.product_adoption_propensity / 12.0

        if len(self.products) >= self.behavior.target_products:
            monthly_adoption *= 0.3
        if self.months_since_last_adoption < 3:
            monthly_adoption *= 0.2

        if self._rng.random() < monthly_adoption:
            candidates = [p for p in self.behavior.preferred_products if p not in self.products]
            if candidates:
                product = self._rng.choice(candidates)

                # Conditional checks for expensive products
                if product == "mortgage" and self._rng.random() > self.behavior.mortgage_likelihood:
                    return actions
                if (
                    product in ("investment_account", "gic")
                    and self._rng.random() > self.behavior.investment_propensity
                ):
                    return actions

                self.products.append(product)
                self.months_since_last_adoption = 0
                actions.append(
                    Action(
                        action_type=ActionType.ADOPT_PRODUCT,
                        agent_id=self.agent_id,
                        step=env.step,
                        product=product,
                        reason=(
                            f"Adoption (propensity={self.behavior.product_adoption_propensity:.2f}, "
                            f"products={len(self.products)})"
                        ),
                        context={
                            "adoption_propensity": self.behavior.product_adoption_propensity,
                            "monthly_rate": monthly_adoption,
                            "num_products": float(len(self.products)),
                            "target_products": float(self.behavior.target_products),
                        },
                    )
                )

        return actions

    def _check_deposit_behavior(self, env: MarketEnvironment) -> List[Action]:
        """Check deposit growth/withdrawal behavior."""
        actions = []

        if env.avg_savings_rate > self.behavior.savings_rate_threshold:
            growth = self.income * 0.005 * (env.avg_savings_rate / 4.0)
            self.deposits += growth
            if growth > 500:
                actions.append(
                    Action(
                        action_type=ActionType.INCREASE_DEPOSITS,
                        agent_id=self.agent_id,
                        step=env.step,
                        amount=round(growth, 2),
                        reason=(
                            f"Rate {env.avg_savings_rate:.2f}% > threshold "
                            f"{self.behavior.savings_rate_threshold:.2f}%"
                        ),
                        context={
                            "growth_amount": growth,
                            "savings_rate": env.avg_savings_rate,
                            "rate_threshold": self.behavior.savings_rate_threshold,
                            "income": self.income,
                        },
                    )
                )
        elif self.satisfaction < 0.5:
            withdrawal = self.deposits * 0.03
            self.deposits = max(0, self.deposits - withdrawal)
            if withdrawal > 500:
                actions.append(
                    Action(
                        action_type=ActionType.DECREASE_DEPOSITS,
                        agent_id=self.agent_id,
                        step=env.step,
                        amount=round(withdrawal, 2),
                        reason=f"Low satisfaction ({self.satisfaction:.2f})",
                        context={
                            "withdrawal_amount": withdrawal,
                            "satisfaction": self.satisfaction,
                            "deposits_before": self.deposits + withdrawal,
                        },
                    )
                )

        return actions

    def _update_lifecycle_state(self):
        """Update lifecycle state based on satisfaction."""
        if self.state == LifecycleState.CHURNED:
            return

        if self.satisfaction < 0.4:
            self.state = LifecycleState.AT_RISK
            self.months_at_risk += 1
        elif self.satisfaction < 0.6 and self.state == LifecycleState.AT_RISK:
            self.months_at_risk += 1
        else:
            self.state = LifecycleState.ACTIVE
            self.months_at_risk = 0

        if self.state == LifecycleState.ONBOARDING and self.tenure_months >= 6:
            self.state = LifecycleState.ACTIVE

    def snapshot(self) -> Dict[str, Any]:
        """Current agent state as a dictionary."""
        return {
            "agent_id": self.agent_id,
            "segment": self.profile.segment,
            "province": self.profile.province,
            "age": self.profile.age,
            "state": self.state.value,
            "satisfaction": round(self.satisfaction, 3),
            "credit_score": self.credit_score,
            "deposits": round(self.deposits, 2),
            "income": round(self.income, 2),
            "products": list(self.products),
            "product_count": len(self.products),
            "tenure_months": self.tenure_months,
            "months_at_risk": self.months_at_risk,
            "total_actions": len(self.memory),
        }
