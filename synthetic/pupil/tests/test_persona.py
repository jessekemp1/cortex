"""Standalone tests for Pupil persona agents, market env, and segment models."""

import pytest
from helpers import make_profile
from pupil.market_env import (
    MarketEnvironment,
    build_timeline,
)
from pupil.persona import Action, ActionType, LifecycleState, PersonaAgent
from pupil.segment_models import SEGMENT_MODELS, get_behavior


@pytest.fixture
def mass_market_profile():
    return make_profile(segment="mass_market")


@pytest.fixture
def baseline_env():
    return MarketEnvironment(month=1, year=2026, step=0)


class TestSegmentModels:
    def test_all_eight_segments_exist(self):
        expected = {
            "mass_market",
            "mass_affluent",
            "affluent",
            "high_net_worth",
            "ultra_hnw",
            "small_business",
            "commercial",
            "new_to_canada",
        }
        assert set(SEGMENT_MODELS.keys()) == expected

    def test_get_behavior_known_segment(self):
        behavior = get_behavior("affluent")
        assert behavior.segment_name == "affluent"

    def test_get_behavior_fallback(self):
        behavior = get_behavior("nonexistent_segment")
        assert behavior.segment_name == "mass_market"

    def test_churn_rates_ordered(self):
        mm = get_behavior("mass_market")
        hnw = get_behavior("high_net_worth")
        uhnw = get_behavior("ultra_hnw")
        assert mm.base_annual_churn_rate > hnw.base_annual_churn_rate
        assert hnw.base_annual_churn_rate > uhnw.base_annual_churn_rate

    def test_parameters_within_valid_ranges(self):
        for name, model in SEGMENT_MODELS.items():
            assert 0.0 < model.base_annual_churn_rate < 0.5, f"{name} churn out of range"
            assert 0.0 <= model.rate_sensitivity <= 1.0, f"{name} rate_sensitivity"
            assert 300 <= model.payment_miss_threshold <= 900, f"{name} payment_miss_threshold"


class TestMarketEnvironment:
    def test_date_label(self):
        env = MarketEnvironment(month=3, year=2026, step=2)
        assert env.date_label == "Mar 2026"

    def test_default_values(self, baseline_env):
        assert baseline_env.boc_overnight_rate == 4.50
        assert baseline_env.unemployment_rate == 6.1


class TestBuildTimeline:
    def test_basic_timeline(self):
        timeline = build_timeline(months=12)
        assert len(timeline) == 12
        assert timeline[0].month == 1
        assert timeline[11].month == 12

    def test_rate_schedule(self):
        schedule = {0: 4.50, 3: 4.25, 6: 4.00}
        timeline = build_timeline(months=12, rate_schedule=schedule)
        assert timeline[3].boc_overnight_rate == 4.25
        assert timeline[6].boc_overnight_rate == 4.00


class TestPersonaAgent:
    def test_initial_state(self, mass_market_profile):
        agent = PersonaAgent(mass_market_profile, seed=42)
        assert agent.state == LifecycleState.ACTIVE
        assert 0.75 <= agent.satisfaction <= 0.95
        assert agent.credit_score == 720

    def test_step_returns_actions(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        actions = agent.step(baseline_env)
        assert isinstance(actions, list)
        assert all(isinstance(a, Action) for a in actions)
        assert len(actions) >= 1

    def test_deterministic_with_seed(self, mass_market_profile, baseline_env):
        agent1 = PersonaAgent(mass_market_profile, seed=42)
        agent2 = PersonaAgent(mass_market_profile, seed=42)
        actions1 = agent1.step(baseline_env)
        actions2 = agent2.step(baseline_env)
        assert len(actions1) == len(actions2)
        for a, b in zip(actions1, actions2):
            assert a.action_type == b.action_type

    def test_churned_agent_does_nothing(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.state = LifecycleState.CHURNED
        actions = agent.step(baseline_env)
        assert actions == []

    def test_churn_over_12_months(self):
        profiles = [make_profile(profile_id=f"churn-{i}") for i in range(200)]
        agents = [PersonaAgent(p, seed=i) for i, p in enumerate(profiles)]
        timeline = build_timeline(months=12)
        for env in timeline:
            for agent in agents:
                agent.step(env)
        churned = sum(1 for a in agents if a.state == LifecycleState.CHURNED)
        churn_rate = churned / len(agents)
        assert 0.03 < churn_rate < 0.40

    def test_snapshot_fields(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.step(baseline_env)
        snap = agent.snapshot()
        assert snap["agent_id"] == "test-001"
        assert snap["segment"] == "mass_market"
        assert 0.0 <= snap["satisfaction"] <= 1.0


class TestActionContext:
    def test_churn_action_has_context(self):
        """Run enough agents to get a churn; verify context keys."""
        profiles = [make_profile(profile_id=f"ctx-{i}") for i in range(200)]
        agents = [PersonaAgent(p, seed=i) for i, p in enumerate(profiles)]
        timeline = build_timeline(months=12)

        churn_actions = []
        for env in timeline:
            for agent in agents:
                for action in agent.step(env):
                    if action.action_type == ActionType.CHURN:
                        churn_actions.append(action)

        assert len(churn_actions) > 0, "Expected at least one churn in 200 agents over 12 months"
        churn = churn_actions[0]
        assert isinstance(churn.context, dict)
        expected_keys = {
            "satisfaction",
            "monthly_churn_prob",
            "tenure_years",
            "num_products",
            "tenure_modifier",
            "product_modifier",
        }
        assert expected_keys == set(churn.context.keys())
        assert 0.0 <= churn.context["satisfaction"] <= 1.0

    def test_hold_action_has_empty_context(self, mass_market_profile, baseline_env):
        """HOLD actions should have empty context (no triggers fired)."""
        agent = PersonaAgent(mass_market_profile, seed=42)
        actions = agent.step(baseline_env)
        holds = [a for a in actions if a.action_type == ActionType.HOLD]
        if holds:
            assert holds[0].context == {}

    def test_action_default_context_is_empty_dict(self):
        """Action created without context= should have empty dict, not None."""
        action = Action(
            action_type=ActionType.HOLD,
            agent_id="test",
            step=0,
        )
        assert action.context == {}
        assert isinstance(action.context, dict)
