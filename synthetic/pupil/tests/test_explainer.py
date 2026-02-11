"""Standalone tests for DecisionExplainer."""

from pupil.persona import Action, ActionType, PersonaAgent
from pupil.explainer import DecisionExplainer, Explanation, Factor
from pupil.market_env import build_timeline

from helpers import make_profile


class TestDecisionExplainerBasic:
    def test_explain_empty_context(self):
        """Actions without context should produce a narrative but no factors."""
        action = Action(
            action_type=ActionType.HOLD,
            agent_id="test-001",
            step=0,
            reason="No action triggers met",
        )
        explainer = DecisionExplainer()
        explanation = explainer.explain(action)
        assert isinstance(explanation, Explanation)
        assert explanation.factors == []
        assert explanation.primary_driver is None
        assert "test-001" in explanation.narrative
        assert "no decision factors" in explanation.narrative.lower()

    def test_explain_churn_action(self):
        """Churn explanation should rank factors and identify primary driver."""
        action = Action(
            action_type=ActionType.CHURN,
            agent_id="churn-001",
            step=5,
            reason="Churn (satisfaction=0.35, tenure=2.1yr, products=1)",
            context={
                "satisfaction": 0.35,
                "monthly_churn_prob": 0.045,
                "tenure_years": 2.1,
                "num_products": 1.0,
                "tenure_modifier": 0.85,
                "product_modifier": 0.92,
            },
        )
        explainer = DecisionExplainer()
        explanation = explainer.explain(action)

        assert explanation.action_type == "churn"
        assert explanation.agent_id == "churn-001"
        assert explanation.step == 5
        assert len(explanation.factors) == 6

        # Primary driver should be satisfaction (highest weight at 0.30)
        assert explanation.primary_driver == "satisfaction"
        assert explanation.factors[0].name == "satisfaction"
        assert explanation.factors[0].direction == "risk"

        # Factors should be sorted by weight descending
        weights = [f.weight for f in explanation.factors]
        assert weights == sorted(weights, reverse=True)

        # Narrative should mention agent and primary factor
        assert "churn-001" in explanation.narrative
        assert "satisfaction" in explanation.narrative

    def test_explain_miss_payment(self):
        action = Action(
            action_type=ActionType.MISS_PAYMENT,
            agent_id="miss-001",
            step=3,
            context={
                "credit_score": 580.0,
                "miss_threshold": 600.0,
                "unemployment_rate": 8.2,
            },
        )
        explanation = DecisionExplainer().explain(action)
        assert explanation.primary_driver == "credit_score"
        assert len(explanation.factors) == 3
        # Credit score below 650 should be "risk"
        credit_factor = next(f for f in explanation.factors if f.name == "credit_score")
        assert credit_factor.direction == "risk"

    def test_explain_default(self):
        action = Action(
            action_type=ActionType.DEFAULT,
            agent_id="def-001",
            step=7,
            context={"credit_score": 420.0, "default_threshold": 500.0},
        )
        explanation = DecisionExplainer().explain(action)
        assert explanation.primary_driver == "credit_score"
        credit_factor = next(f for f in explanation.factors if f.name == "credit_score")
        assert "severe distress" in credit_factor.label

    def test_explain_adopt_product(self):
        action = Action(
            action_type=ActionType.ADOPT_PRODUCT,
            agent_id="adopt-001",
            step=4,
            product="tfsa",
            context={
                "adoption_propensity": 0.25,
                "monthly_rate": 0.0208,
                "num_products": 3.0,
                "target_products": 4.0,
            },
        )
        explanation = DecisionExplainer().explain(action)
        assert explanation.primary_driver == "adoption_propensity"
        assert len(explanation.factors) == 4

    def test_explain_increase_deposits(self):
        action = Action(
            action_type=ActionType.INCREASE_DEPOSITS,
            agent_id="dep-001",
            step=6,
            amount=1250.00,
            context={
                "growth_amount": 1250.0,
                "savings_rate": 4.5,
                "rate_threshold": 2.0,
                "income": 85000.0,
            },
        )
        explanation = DecisionExplainer().explain(action)
        assert len(explanation.factors) == 4
        # All factors should be "protective" for deposit increases
        assert all(f.direction == "protective" for f in explanation.factors)

    def test_explain_decrease_deposits(self):
        action = Action(
            action_type=ActionType.DECREASE_DEPOSITS,
            agent_id="wd-001",
            step=8,
            amount=750.0,
            context={
                "withdrawal_amount": 750.0,
                "satisfaction": 0.38,
                "deposits_before": 25750.0,
            },
        )
        explanation = DecisionExplainer().explain(action)
        assert explanation.primary_driver == "satisfaction"
        sat_factor = next(f for f in explanation.factors if f.name == "satisfaction")
        assert sat_factor.direction == "risk"

    def test_explain_switch_to_competitor(self):
        action = Action(
            action_type=ActionType.SWITCH_TO_COMPETITOR,
            agent_id="sw-001",
            step=9,
            product="savings",
            target="EQ Bank",
            context={
                "switch_probability": 0.08,
                "competitor_susceptibility": 0.45,
                "satisfaction": 0.42,
                "offered_rate": 5.25,
                "market_rate": 3.80,
                "impact_magnitude": 0.7,
            },
        )
        explanation = DecisionExplainer().explain(action)
        assert len(explanation.factors) == 6
        assert explanation.primary_driver == "switch_probability"


class TestExplainBatch:
    def test_explain_batch_returns_list(self):
        actions = [
            Action(action_type=ActionType.HOLD, agent_id="b-1", step=0),
            Action(
                action_type=ActionType.CHURN,
                agent_id="b-2",
                step=3,
                context={"satisfaction": 0.3, "monthly_churn_prob": 0.05,
                         "tenure_years": 1.0, "num_products": 1.0,
                         "tenure_modifier": 0.9, "product_modifier": 0.92},
            ),
        ]
        explanations = DecisionExplainer().explain_batch(actions)
        assert len(explanations) == 2
        assert explanations[0].factors == []
        assert len(explanations[1].factors) == 6


class TestExplainerIntegration:
    def test_explain_real_simulation_actions(self):
        """Run a real sim and explain every action that has context."""
        profiles = [make_profile(profile_id=f"expl-{i}") for i in range(50)]
        agents = [PersonaAgent(p, seed=i) for i, p in enumerate(profiles)]
        timeline = build_timeline(months=6)

        explainer = DecisionExplainer()
        explained_count = 0

        for env in timeline:
            for agent in agents:
                for action in agent.step(env):
                    explanation = explainer.explain(action)
                    assert isinstance(explanation, Explanation)
                    assert explanation.action_type == action.action_type.value
                    assert explanation.agent_id == action.agent_id
                    if action.context:
                        assert len(explanation.factors) > 0
                        assert explanation.primary_driver is not None
                        explained_count += 1

        # Should have explained at least some non-trivial actions
        assert explained_count > 0


class TestFactorDataclass:
    def test_factor_fields(self):
        f = Factor(name="satisfaction", value=0.35, direction="risk", weight=0.30, label="test")
        assert f.name == "satisfaction"
        assert f.value == 0.35
        assert f.direction == "risk"
        assert f.weight == 0.30
        assert f.label == "test"
