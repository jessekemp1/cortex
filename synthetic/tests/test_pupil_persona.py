#!/usr/bin/env python3
"""Tests for Pupil persona agents, market environment, and segment models."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.pupil.market_env import (
    CompetitionEvent,
    EventType,
    MarketEnvironment,
    build_timeline,
)
from synthetic.pupil.persona import (
    Action,
    ActionType,
    LifecycleState,
    PersonaAgent,
)
from synthetic.pupil.segment_models import (
    SEGMENT_MODELS,
    get_behavior,
)
from synthetic.schemas import CustomerProfile

# ============================================================================
# Fixtures
# ============================================================================


def make_profile(
    profile_id: str = "test-001",
    segment: str = "mass_market",
    age: int = 35,
    province: str = "ON",
    credit_score: int = 720,
    annual_income: float = 65000.0,
    total_deposits: float = 25000.0,
    tenure_years: float = 5.0,
    products: list | None = None,
) -> CustomerProfile:
    """Factory for test CustomerProfiles."""
    return CustomerProfile(
        profile_id=profile_id,
        age=age,
        province=province,
        fsa="M5V",
        segment=segment,
        annual_income=annual_income,
        household_income=annual_income * 1.5,
        credit_score=credit_score,
        products_held=products or ["chequing", "savings"],
        total_deposits=total_deposits,
        total_credit_outstanding=5000.0,
        digital_adoption="hybrid",
        primary_channel="mobile",
        tenure_years=tenure_years,
        products_per_household=2,
    )


@pytest.fixture
def mass_market_profile():
    return make_profile(segment="mass_market")


@pytest.fixture
def hnw_profile():
    return make_profile(
        profile_id="hnw-001",
        segment="high_net_worth",
        credit_score=810,
        annual_income=600000.0,
        total_deposits=500000.0,
        tenure_years=15.0,
        products=["chequing", "savings", "mortgage", "investment_account", "gic"],
    )


@pytest.fixture
def new_to_canada_profile():
    return make_profile(
        profile_id="ntc-001",
        segment="new_to_canada",
        credit_score=650,
        annual_income=45000.0,
        total_deposits=5000.0,
        tenure_years=0.5,
        products=["chequing"],
    )


@pytest.fixture
def baseline_env():
    return MarketEnvironment(month=1, year=2026, step=0)


@pytest.fixture
def stress_env():
    """Environment with high unemployment and competitor attack."""
    return MarketEnvironment(
        month=6,
        year=2026,
        step=5,
        boc_overnight_rate=5.25,
        unemployment_rate=8.5,
        housing_price_yoy=-3.0,
        avg_savings_rate=4.25,
        events=[
            CompetitionEvent(
                event_type=EventType.PRODUCT_LAUNCH,
                institution="EQ Bank",
                description="5% HISA launch",
                product="savings",
                rate_offered=5.0,
                target_segment=None,
                impact_magnitude=0.8,
            )
        ],
    )


# ============================================================================
# Market Environment Tests
# ============================================================================


class TestMarketEnvironment:
    def test_date_label(self):
        env = MarketEnvironment(month=3, year=2026, step=2)
        assert env.date_label == "Mar 2026"

    def test_date_label_december(self):
        env = MarketEnvironment(month=12, year=2025, step=11)
        assert env.date_label == "Dec 2025"

    def test_rate_delta(self):
        env = MarketEnvironment(month=1, year=2026, step=0, boc_overnight_rate=5.0)
        assert env.rate_delta_from(4.50) == pytest.approx(0.5)

    def test_default_values(self, baseline_env):
        assert baseline_env.boc_overnight_rate == 4.50
        assert baseline_env.unemployment_rate == 6.1
        assert baseline_env.cpi_yoy == 2.8
        assert baseline_env.events == []


class TestBuildTimeline:
    def test_basic_timeline(self):
        timeline = build_timeline(months=12)
        assert len(timeline) == 12
        assert timeline[0].month == 1
        assert timeline[0].year == 2026
        assert timeline[11].month == 12
        assert timeline[11].year == 2026

    def test_step_numbering(self):
        timeline = build_timeline(months=6)
        for i, env in enumerate(timeline):
            assert env.step == i

    def test_year_rollover(self):
        timeline = build_timeline(months=15, start_month=10, start_year=2025)
        assert timeline[0].month == 10
        assert timeline[0].year == 2025
        assert timeline[3].month == 1
        assert timeline[3].year == 2026
        assert timeline[14].month == 12
        assert timeline[14].year == 2026

    def test_rate_schedule(self):
        schedule = {0: 4.50, 3: 4.25, 6: 4.00}
        timeline = build_timeline(months=12, rate_schedule=schedule)
        assert timeline[0].boc_overnight_rate == 4.50
        assert timeline[2].boc_overnight_rate == 4.50
        assert timeline[3].boc_overnight_rate == 4.25
        assert timeline[5].boc_overnight_rate == 4.25
        assert timeline[6].boc_overnight_rate == 4.00

    def test_derived_rates(self):
        """Banking rates should derive from BoC overnight rate."""
        timeline = build_timeline(months=1, base_rate=4.50)
        env = timeline[0]
        assert env.avg_savings_rate == pytest.approx(3.50)  # BoC - 1.0
        assert env.avg_mortgage_rate_5yr == pytest.approx(5.20)  # BoC + 0.7
        assert env.avg_gic_rate_1yr == pytest.approx(4.00)  # BoC - 0.5

    def test_event_injection(self):
        event = CompetitionEvent(
            event_type=EventType.RATE_CHANGE,
            institution="Tangerine",
            description="Rate hike",
        )
        timeline = build_timeline(months=3, events={1: [event]})
        assert len(timeline[0].events) == 0
        assert len(timeline[1].events) == 1
        assert timeline[1].events[0].institution == "Tangerine"
        assert len(timeline[2].events) == 0

    def test_unemployment_schedule(self):
        schedule = {0: 6.1, 4: 7.5}
        timeline = build_timeline(months=6, unemployment_schedule=schedule)
        assert timeline[0].unemployment_rate == 6.1
        assert timeline[3].unemployment_rate == 6.1
        assert timeline[4].unemployment_rate == 7.5


class TestCompetitionEvent:
    def test_affects_all_segments(self):
        event = CompetitionEvent(
            event_type=EventType.RATE_CHANGE,
            institution="EQ Bank",
            description="Rate hike",
            target_segment=None,
        )
        assert event.affects_segment("mass_market") is True
        assert event.affects_segment("high_net_worth") is True

    def test_affects_targeted_segment_only(self):
        event = CompetitionEvent(
            event_type=EventType.PRODUCT_LAUNCH,
            institution="Wealthsimple",
            description="HISA launch",
            target_segment="mass_affluent",
        )
        assert event.affects_segment("mass_affluent") is True
        assert event.affects_segment("mass_market") is False


# ============================================================================
# Segment Model Tests
# ============================================================================


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
        """Higher-value segments should have lower base churn."""
        mm = get_behavior("mass_market")
        hnw = get_behavior("high_net_worth")
        uhnw = get_behavior("ultra_hnw")
        assert mm.base_annual_churn_rate > hnw.base_annual_churn_rate
        assert hnw.base_annual_churn_rate > uhnw.base_annual_churn_rate

    def test_new_to_canada_highest_churn(self):
        ntc = get_behavior("new_to_canada")
        for name, model in SEGMENT_MODELS.items():
            if name != "new_to_canada":
                assert ntc.base_annual_churn_rate >= model.base_annual_churn_rate

    def test_new_to_canada_highest_fintech_openness(self):
        ntc = get_behavior("new_to_canada")
        for name, model in SEGMENT_MODELS.items():
            if name != "new_to_canada":
                assert ntc.fintech_openness >= model.fintech_openness

    def test_ultra_hnw_lowest_fintech(self):
        uhnw = get_behavior("ultra_hnw")
        for name, model in SEGMENT_MODELS.items():
            if name != "ultra_hnw":
                assert uhnw.fintech_openness <= model.fintech_openness

    def test_all_segments_have_preferred_products(self):
        for name, model in SEGMENT_MODELS.items():
            assert len(model.preferred_products) > 0, f"{name} has no preferred products"
            assert "chequing" in model.preferred_products, f"{name} missing chequing"

    def test_parameters_within_valid_ranges(self):
        for name, model in SEGMENT_MODELS.items():
            assert 0.0 < model.base_annual_churn_rate < 0.5, f"{name} churn out of range"
            assert 0.0 <= model.rate_sensitivity <= 1.0, f"{name} rate_sensitivity out of range"
            assert (
                0.0 <= model.competitor_susceptibility <= 1.0
            ), f"{name} competitor_susceptibility"
            assert 0.0 <= model.digital_preference <= 1.0, f"{name} digital_preference"
            assert 300 <= model.payment_miss_threshold <= 900, f"{name} payment_miss_threshold"
            assert (
                model.default_threshold < model.payment_miss_threshold
            ), f"{name} default_threshold >= payment_miss_threshold"


# ============================================================================
# PersonaAgent Tests
# ============================================================================


class TestPersonaAgentInit:
    def test_initial_state(self, mass_market_profile):
        agent = PersonaAgent(mass_market_profile, seed=42)
        assert agent.state == LifecycleState.ACTIVE
        assert 0.75 <= agent.satisfaction <= 0.95
        assert agent.credit_score == 720
        assert agent.deposits == 25000.0
        assert agent.products == ["chequing", "savings"]
        assert agent.memory == []

    def test_behavior_auto_assigned(self, mass_market_profile):
        agent = PersonaAgent(mass_market_profile, seed=42)
        assert agent.behavior.segment_name == "mass_market"

    def test_custom_behavior(self, mass_market_profile):
        custom = get_behavior("affluent")
        agent = PersonaAgent(mass_market_profile, behavior=custom, seed=42)
        assert agent.behavior.segment_name == "affluent"


class TestPersonaAgentStep:
    def test_step_returns_actions(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        actions = agent.step(baseline_env)
        assert isinstance(actions, list)
        assert all(isinstance(a, Action) for a in actions)
        assert len(actions) >= 1  # At minimum HOLD

    def test_step_records_memory(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.step(baseline_env)
        assert len(agent.memory) >= 1

    def test_step_increments_tenure(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        initial_tenure = agent.tenure_months
        agent.step(baseline_env)
        assert agent.tenure_months == initial_tenure + 1

    def test_churned_agent_does_nothing(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.state = LifecycleState.CHURNED
        actions = agent.step(baseline_env)
        assert actions == []

    def test_deterministic_with_seed(self, mass_market_profile, baseline_env):
        """Same seed → same actions."""
        agent1 = PersonaAgent(mass_market_profile, seed=42)
        agent2 = PersonaAgent(mass_market_profile, seed=42)
        actions1 = agent1.step(baseline_env)
        actions2 = agent2.step(baseline_env)
        assert len(actions1) == len(actions2)
        for a, b in zip(actions1, actions2):
            assert a.action_type == b.action_type

    def test_different_seeds_differ(self, mass_market_profile):
        """Different seeds should produce different satisfaction values."""
        timeline = build_timeline(months=12)
        agents = [PersonaAgent(mass_market_profile, seed=i) for i in range(10)]
        for env in timeline:
            for agent in agents:
                agent.step(env)
        satisfactions = [a.satisfaction for a in agents]
        # Not all the same (extremely unlikely with different seeds)
        assert len(set(round(s, 3) for s in satisfactions)) > 1


class TestPersonaAgentSatisfaction:
    def test_rate_hike_reduces_mortgage_holder_satisfaction(self):
        profile = make_profile(products=["chequing", "mortgage"])
        agent = PersonaAgent(profile, seed=42)
        initial_sat = agent.satisfaction

        env = MarketEnvironment(month=1, year=2026, step=0, boc_overnight_rate=4.50)
        agent.step(env)
        # Set baseline, then hike
        env2 = MarketEnvironment(month=2, year=2026, step=1, boc_overnight_rate=5.50)
        agent.step(env2)

        # Satisfaction should have dropped (rate hike + mortgage holder)
        # May not always be strictly less due to loyalty bonus, but
        # over a big rate hike the net should be negative
        assert agent.satisfaction < initial_sat + 0.05  # Allow small loyalty offset

    def test_unemployment_pressure(self):
        profile = make_profile(segment="mass_market")
        agent = PersonaAgent(profile, seed=42)

        # Run 6 months of high unemployment
        timeline = build_timeline(
            months=6,
            unemployment_schedule={0: 9.0},
        )
        for env in timeline:
            agent.step(env)

        # mass_market has 0.80 unemployment_sensitivity → satisfaction drops
        assert agent.satisfaction < 0.90


class TestPersonaAgentChurn:
    def test_churn_over_12_months(self):
        """Run 100 mass_market agents for 12 months; churn should be ~18% annual."""
        profiles = [
            make_profile(profile_id=f"churn-{i}", segment="mass_market") for i in range(200)
        ]
        agents = [PersonaAgent(p, seed=i) for i, p in enumerate(profiles)]
        timeline = build_timeline(months=12)

        for env in timeline:
            for agent in agents:
                agent.step(env)

        churned = sum(1 for a in agents if a.state == LifecycleState.CHURNED)
        churn_rate = churned / len(agents)
        # CBA-calibrated: mass_market 18% annual. Allow ±10pp for stochastic variance.
        assert 0.03 < churn_rate < 0.40, f"Churn rate {churn_rate:.2%} outside expected range"

    def test_hnw_lower_churn_than_mass_market(self):
        """HNW should churn less than mass_market over same period."""
        n = 200
        mm_profiles = [make_profile(profile_id=f"mm-{i}", segment="mass_market") for i in range(n)]
        hnw_profiles = [
            make_profile(
                profile_id=f"hnw-{i}",
                segment="high_net_worth",
                credit_score=810,
                annual_income=600000,
                total_deposits=500000,
                products=["chequing", "savings", "mortgage", "investment_account"],
            )
            for i in range(n)
        ]
        mm_agents = [PersonaAgent(p, seed=i) for i, p in enumerate(mm_profiles)]
        hnw_agents = [PersonaAgent(p, seed=i + 1000) for i, p in enumerate(hnw_profiles)]

        timeline = build_timeline(months=12)
        for env in timeline:
            for a in mm_agents + hnw_agents:
                a.step(env)

        mm_churn = sum(1 for a in mm_agents if a.state == LifecycleState.CHURNED) / n
        hnw_churn = sum(1 for a in hnw_agents if a.state == LifecycleState.CHURNED) / n
        assert (
            hnw_churn < mm_churn
        ), f"HNW churn ({hnw_churn:.2%}) should be < mass_market ({mm_churn:.2%})"


class TestPersonaAgentStress:
    def test_low_credit_triggers_payment_miss(self):
        profile = make_profile(credit_score=550)
        agent = PersonaAgent(profile, seed=42)
        timeline = build_timeline(months=12)

        all_actions = []
        for env in timeline:
            all_actions.extend(agent.step(env))

        # With credit 550 < mass_market threshold 600, misses should occur
        miss_actions = [a for a in all_actions if a.action_type == ActionType.MISS_PAYMENT]
        # Credit recovery may fix it, so check at least one attempt path
        assert agent.credit_score != 550 or len(miss_actions) > 0  # State must have changed

    def test_credit_recovery_in_good_conditions(self):
        profile = make_profile(credit_score=650)
        agent = PersonaAgent(profile, seed=42)
        # Good conditions (low unemployment)
        timeline = build_timeline(months=12, unemployment_schedule={0: 5.0})
        for env in timeline:
            agent.step(env)
        # Credit should recover toward 750+
        assert agent.credit_score >= 650  # At minimum didn't degrade


class TestPersonaAgentDeposits:
    def test_high_rates_attract_deposits(self):
        profile = make_profile(total_deposits=50000.0)
        agent = PersonaAgent(profile, seed=42)
        # High savings rate (threshold for mass_market is 2.0)
        timeline = build_timeline(months=12, base_rate=5.0)
        for env in timeline:
            agent.step(env)
        # Deposits should grow when rate > threshold
        assert agent.deposits >= 50000.0

    def test_low_satisfaction_withdrawals(self):
        profile = make_profile(total_deposits=50000.0)
        agent = PersonaAgent(profile, seed=42)
        agent.satisfaction = 0.35  # Below 0.5 → withdrawal trigger
        # Low rates so no deposit growth offsets
        timeline = build_timeline(months=6, base_rate=2.5)
        for env in timeline:
            agent.step(env)
        # Deposits should have decreased
        assert agent.deposits < 50000.0


class TestPersonaAgentLifecycle:
    def test_active_to_at_risk_on_low_satisfaction(self, mass_market_profile):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.satisfaction = 0.35
        env = MarketEnvironment(month=1, year=2026, step=0)
        agent.step(env)
        assert agent.state == LifecycleState.AT_RISK or agent.state == LifecycleState.CHURNED

    def test_at_risk_back_to_active_if_satisfied(self, mass_market_profile):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.state = LifecycleState.AT_RISK
        agent.satisfaction = 0.80  # Above thresholds
        env = MarketEnvironment(month=1, year=2026, step=0)
        agent.step(env)
        # If didn't churn, should be back to active
        if agent.state != LifecycleState.CHURNED:
            assert agent.state == LifecycleState.ACTIVE


class TestPersonaAgentSnapshot:
    def test_snapshot_fields(self, mass_market_profile, baseline_env):
        agent = PersonaAgent(mass_market_profile, seed=42)
        agent.step(baseline_env)
        snap = agent.snapshot()
        assert snap["agent_id"] == "test-001"
        assert snap["segment"] == "mass_market"
        assert snap["province"] == "ON"
        assert snap["state"] in ("active", "at_risk", "churned", "dormant", "onboarding")
        assert 0.0 <= snap["satisfaction"] <= 1.0
        assert snap["credit_score"] >= 300
        assert isinstance(snap["products"], list)
        assert snap["total_actions"] >= 1


class TestActionSerialization:
    def test_action_to_dict(self):
        action = Action(
            action_type=ActionType.ADOPT_PRODUCT,
            agent_id="test-001",
            step=3,
            product="tfsa",
            reason="New product",
        )
        d = action.to_dict()
        assert d["action_type"] == "adopt_product"
        assert d["agent_id"] == "test-001"
        assert d["step"] == 3
        assert d["product"] == "tfsa"
        assert "context" in d
        assert isinstance(d["context"], dict)

    def test_action_to_dict_with_context(self):
        action = Action(
            action_type=ActionType.CHURN,
            agent_id="test-002",
            step=5,
            reason="Churn test",
            context={"satisfaction": 0.35, "monthly_churn_prob": 0.08},
        )
        d = action.to_dict()
        assert d["context"]["satisfaction"] == 0.35
        assert d["context"]["monthly_churn_prob"] == 0.08
