#!/usr/bin/env python3
"""Tests for Pupil SimulationEngine — time-stepping orchestrator."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.schemas import CustomerProfile
from synthetic.pupil.market_env import (
    CompetitionEvent,
    EventType,
    build_timeline,
)
from synthetic.pupil.persona import PersonaAgent
from synthetic.pupil.simulation import (
    SimulationEngine,
    SimulationResult,
    StepResult,
)


# ============================================================================
# Fixtures
# ============================================================================


def make_profile(
    profile_id: str = "test-001",
    segment: str = "mass_market",
    credit_score: int = 720,
    annual_income: float = 65000.0,
    total_deposits: float = 25000.0,
    tenure_years: float = 5.0,
    products: list | None = None,
) -> CustomerProfile:
    return CustomerProfile(
        profile_id=profile_id,
        age=35,
        province="ON",
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


def make_profiles(n: int = 50, segment: str = "mass_market") -> list[CustomerProfile]:
    return [make_profile(profile_id=f"{segment}-{i}", segment=segment) for i in range(n)]


@pytest.fixture
def engine():
    return SimulationEngine(seed=42)


@pytest.fixture
def profiles_50():
    return make_profiles(50)


@pytest.fixture
def profiles_mixed():
    """Mix of segments for realistic simulation."""
    profiles = []
    segments = [
        ("mass_market", 20),
        ("mass_affluent", 10),
        ("affluent", 5),
        ("high_net_worth", 3),
        ("new_to_canada", 8),
        ("small_business", 4),
    ]
    idx = 0
    for seg, count in segments:
        for _ in range(count):
            profiles.append(make_profile(
                profile_id=f"mix-{idx}",
                segment=seg,
                credit_score=720 if seg != "new_to_canada" else 650,
                annual_income=65000 if seg not in ("high_net_worth", "affluent") else 300000,
                total_deposits=25000 if seg not in ("high_net_worth",) else 500000,
            ))
            idx += 1
    return profiles


@pytest.fixture
def baseline_timeline():
    return build_timeline(months=12)


@pytest.fixture
def stress_timeline():
    """Rate hike + unemployment spike scenario."""
    return build_timeline(
        months=12,
        rate_schedule={0: 4.50, 3: 5.00, 6: 5.50},
        unemployment_schedule={0: 6.1, 4: 7.5, 8: 8.5},
        events={
            2: [CompetitionEvent(
                event_type=EventType.PRODUCT_LAUNCH,
                institution="EQ Bank",
                description="5% HISA",
                product="savings",
                rate_offered=5.0,
                impact_magnitude=0.8,
            )],
            7: [CompetitionEvent(
                event_type=EventType.RATE_CHANGE,
                institution="Tangerine",
                description="Rate match",
                product="savings",
                rate_offered=5.25,
                impact_magnitude=0.7,
            )],
        },
    )


# ============================================================================
# SimulationEngine Tests
# ============================================================================


class TestGenerateAgents:
    def test_generates_correct_count(self, engine, profiles_50):
        agents = engine.generate_agents(profiles_50)
        assert len(agents) == 50
        assert len(engine.agents) == 50

    def test_agents_have_correct_segments(self, engine, profiles_mixed):
        agents = engine.generate_agents(profiles_mixed)
        segments = {a.behavior.segment_name for a in agents}
        assert "mass_market" in segments
        assert "high_net_worth" in segments
        assert "new_to_canada" in segments

    def test_agents_have_unique_seeds(self, engine, profiles_50):
        agents = engine.generate_agents(profiles_50, seed=100)
        # Each agent's RNG should be different
        randoms = [a._rng.random() for a in agents]
        assert len(set(round(r, 6) for r in randoms)) == len(randoms)


class TestSimulationRun:
    def test_run_basic(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert isinstance(result, SimulationResult)
        assert result.n_agents == 50
        assert result.n_steps == 12
        assert len(result.steps) == 12

    def test_run_no_agents_raises(self, engine, baseline_timeline):
        with pytest.raises(ValueError, match="No agents"):
            engine.run(baseline_timeline)

    def test_step_results_have_aggregates(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        step0 = result.steps[0]
        assert isinstance(step0, StepResult)
        assert step0.n_active + step0.n_at_risk + step0.n_churned == 50
        assert step0.total_actions >= 50  # At least one action per agent

    def test_cumulative_churn(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        # Churn should be non-decreasing across steps
        churned_over_time = [s.n_churned for s in result.steps]
        for i in range(1, len(churned_over_time)):
            assert churned_over_time[i] >= churned_over_time[i - 1]

    def test_all_actions_collected(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        step_action_count = sum(len(s.actions) for s in result.steps)
        assert len(result.all_actions) == step_action_count

    def test_final_snapshots_match_last_step(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert result.final_snapshots == result.steps[-1].snapshots

    def test_pass_agents_directly(self, profiles_50, baseline_timeline):
        """Can pass agents to run() without generate_agents()."""
        agents = [PersonaAgent(p, seed=i) for i, p in enumerate(profiles_50)]
        engine = SimulationEngine()
        result = engine.run(baseline_timeline, agents=agents)
        assert result.n_agents == 50


class TestSimulationDeterminism:
    def test_same_seed_same_result(self, profiles_50, baseline_timeline):
        e1 = SimulationEngine(seed=42)
        e1.generate_agents(profiles_50)
        r1 = e1.run(baseline_timeline)

        e2 = SimulationEngine(seed=42)
        e2.generate_agents(profiles_50)
        r2 = e2.run(baseline_timeline)

        assert r1.total_churned == r2.total_churned
        assert r1.avg_final_satisfaction == pytest.approx(r2.avg_final_satisfaction, abs=1e-6)
        assert r1.churn_rate == pytest.approx(r2.churn_rate, abs=1e-6)

    def test_different_seed_different_result(self, profiles_50, baseline_timeline):
        e1 = SimulationEngine(seed=42)
        e1.generate_agents(profiles_50)
        r1 = e1.run(baseline_timeline)

        e2 = SimulationEngine(seed=999)
        e2.generate_agents(profiles_50)
        r2 = e2.run(baseline_timeline)

        # Very unlikely to be identical with different seeds
        assert (
            r1.total_churned != r2.total_churned
            or r1.avg_final_satisfaction != pytest.approx(r2.avg_final_satisfaction, abs=1e-6)
        )


class TestSimulationStressScenario:
    def test_stress_increases_churn(self, baseline_timeline, stress_timeline):
        # Use 200 agents to reduce stochastic variance in comparison
        profiles_200 = make_profiles(200)

        e_base = SimulationEngine(seed=42)
        e_base.generate_agents(profiles_200)
        r_base = e_base.run(baseline_timeline)

        e_stress = SimulationEngine(seed=42)
        e_stress.generate_agents(profiles_200)
        r_stress = e_stress.run(stress_timeline)

        # Stress scenario should produce more churn (or lower satisfaction)
        assert (
            r_stress.total_churned >= r_base.total_churned
            or r_stress.avg_final_satisfaction < r_base.avg_final_satisfaction
        )

    def test_mixed_segments_respond_differently(self, profiles_mixed, stress_timeline):
        engine = SimulationEngine(seed=42)
        engine.generate_agents(profiles_mixed)
        result = engine.run(stress_timeline)

        # Group snapshots by segment
        by_seg = {}
        for snap in result.final_snapshots:
            by_seg.setdefault(snap["segment"], []).append(snap)

        # new_to_canada should have more churn than high_net_worth
        if "new_to_canada" in by_seg and "high_net_worth" in by_seg:
            ntc_churn = sum(1 for s in by_seg["new_to_canada"] if s["state"] == "churned")
            hnw_churn = sum(1 for s in by_seg["high_net_worth"] if s["state"] == "churned")
            ntc_rate = ntc_churn / len(by_seg["new_to_canada"])
            hnw_rate = hnw_churn / len(by_seg["high_net_worth"]) if by_seg["high_net_worth"] else 0
            # Allow for small samples — just check direction when both have churns
            if ntc_churn + hnw_churn > 0:
                assert ntc_rate >= hnw_rate or ntc_churn >= hnw_churn


class TestSimulationResultProperties:
    def test_churn_rate(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert 0.0 <= result.churn_rate <= 1.0
        assert result.churn_rate == result.total_churned / result.n_agents

    def test_avg_final_satisfaction(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert 0.0 <= result.avg_final_satisfaction <= 1.0

    def test_summary_string(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        summary = result.summary()
        assert "50 agents" in summary
        assert "12 months" in summary
        assert "Churn:" in summary

    def test_to_dict(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        d = result.to_dict()
        assert d["n_agents"] == 50
        assert d["n_steps"] == 12
        assert len(d["steps"]) == 12
        assert "churn_rate" in d


class TestStepResultSerialization:
    def test_step_to_dict(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        step_dict = result.steps[0].to_dict()
        assert "step" in step_dict
        assert "date_label" in step_dict
        assert "n_active" in step_dict
        assert "churn_count" in step_dict
