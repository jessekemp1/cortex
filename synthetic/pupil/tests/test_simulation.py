"""Standalone tests for Pupil SimulationEngine."""

import pytest

from pupil.market_env import build_timeline
from pupil.simulation import SimulationEngine, SimulationResult

from helpers import make_profiles


@pytest.fixture
def engine():
    return SimulationEngine(seed=42)


@pytest.fixture
def profiles_50():
    return make_profiles(50)


@pytest.fixture
def baseline_timeline():
    return build_timeline(months=12)


class TestSimulationRun:
    def test_run_basic(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert isinstance(result, SimulationResult)
        assert result.n_agents == 50
        assert result.n_steps == 12

    def test_run_no_agents_raises(self, engine, baseline_timeline):
        with pytest.raises(ValueError, match="No agents"):
            engine.run(baseline_timeline)

    def test_cumulative_churn(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        churned_over_time = [s.n_churned for s in result.steps]
        for i in range(1, len(churned_over_time)):
            assert churned_over_time[i] >= churned_over_time[i - 1]

    def test_final_snapshots_match_last_step(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert result.final_snapshots == result.steps[-1].snapshots

    def test_same_seed_same_result(self, profiles_50, baseline_timeline):
        e1 = SimulationEngine(seed=42)
        e1.generate_agents(profiles_50)
        r1 = e1.run(baseline_timeline)

        e2 = SimulationEngine(seed=42)
        e2.generate_agents(profiles_50)
        r2 = e2.run(baseline_timeline)

        assert r1.total_churned == r2.total_churned
        assert r1.churn_rate == pytest.approx(r2.churn_rate, abs=1e-6)

    def test_churn_rate_and_summary(self, engine, profiles_50, baseline_timeline):
        engine.generate_agents(profiles_50)
        result = engine.run(baseline_timeline)
        assert 0.0 <= result.churn_rate <= 1.0
        summary = result.summary()
        assert "50 agents" in summary
        assert "12 months" in summary
