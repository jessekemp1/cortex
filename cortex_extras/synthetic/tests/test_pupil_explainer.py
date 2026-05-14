"""Cortex-side tests for Pupil DecisionExplainer."""

import sys
from pathlib import Path

# Ensure pupil package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pupil"))

from synthetic.pupil.explainer import DecisionExplainer, Explanation
from synthetic.pupil.market_env import build_timeline
from synthetic.pupil.persona import Action, ActionType, PersonaAgent
from synthetic.pupil.schemas import CustomerProfile


def _make_profile(**overrides):
    defaults = dict(
        profile_id="expl-test-001",
        age=35,
        province="ON",
        fsa="M5V",
        segment="mass_market",
        annual_income=65000,
        household_income=97500,
        credit_score=720,
        products_held=["chequing"],
        total_deposits=25000,
        total_credit_outstanding=5000,
        digital_adoption="hybrid",
        primary_channel="mobile",
        tenure_years=5.0,
        products_per_household=1,
    )
    defaults.update(overrides)
    return CustomerProfile(**defaults)


class TestExplainerFromImport:
    """Verify DecisionExplainer is importable via the pupil package."""

    def test_import_from_package(self):
        from synthetic.pupil import DecisionExplainer, Explanation, Factor

        assert DecisionExplainer is not None
        assert Explanation is not None
        assert Factor is not None


class TestExplainerWithContext:
    def test_churn_explanation_structure(self):
        action = Action(
            action_type=ActionType.CHURN,
            agent_id="ctx-001",
            step=5,
            context={
                "satisfaction": 0.35,
                "monthly_churn_prob": 0.045,
                "tenure_years": 2.1,
                "num_products": 1.0,
                "tenure_modifier": 0.85,
                "product_modifier": 0.92,
            },
        )
        explanation = DecisionExplainer().explain(action)
        assert isinstance(explanation, Explanation)
        assert explanation.action_type == "churn"
        assert explanation.primary_driver == "satisfaction"
        assert len(explanation.factors) == 6

        # Verify factor sorting (weight descending)
        for i in range(len(explanation.factors) - 1):
            assert explanation.factors[i].weight >= explanation.factors[i + 1].weight

    def test_empty_context_explanation(self):
        action = Action(action_type=ActionType.HOLD, agent_id="h-001", step=0)
        explanation = DecisionExplainer().explain(action)
        assert explanation.factors == []
        assert explanation.primary_driver is None

    def test_batch_explain(self):
        actions = [
            Action(action_type=ActionType.HOLD, agent_id="b-1", step=0),
            Action(
                action_type=ActionType.DEFAULT,
                agent_id="b-2",
                step=3,
                context={"credit_score": 430.0, "default_threshold": 500.0},
            ),
        ]
        results = DecisionExplainer().explain_batch(actions)
        assert len(results) == 2
        assert results[0].primary_driver is None
        assert results[1].primary_driver == "credit_score"


class TestExplainerIntegration:
    def test_real_simulation_all_actions_explainable(self):
        """Every action from a real sim should be explainable without errors."""
        profiles = [_make_profile(profile_id=f"integ-{i}") for i in range(30)]
        agents = [PersonaAgent(p, seed=i) for i, p in enumerate(profiles)]
        timeline = build_timeline(months=6)
        explainer = DecisionExplainer()

        for env in timeline:
            for agent in agents:
                for action in agent.step(env):
                    explanation = explainer.explain(action)
                    assert isinstance(explanation, Explanation)
                    assert isinstance(explanation.narrative, str)
                    assert len(explanation.narrative) > 0
