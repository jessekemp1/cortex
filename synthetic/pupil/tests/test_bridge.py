"""Standalone tests for PupilBridge."""

import pytest

from pupil.bridge import PupilBridge
from pupil.simulation import SimulationResult
from pupil.analysis import AnalysisReport

from helpers import make_profiles


@pytest.fixture
def bridge():
    return PupilBridge()


@pytest.fixture
def profiles_50():
    return make_profiles(50)


class TestFromProfiles:
    def test_returns_simulation_result(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50)
        assert isinstance(result, SimulationResult)
        assert result.n_agents == 50
        assert result.n_steps == 12

    def test_custom_months(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50, months=6)
        assert result.n_steps == 6


class TestFullAnalysis:
    def test_returns_tuple(self, bridge, profiles_50):
        sim_result, report = bridge.full_analysis(profiles_50)
        assert isinstance(sim_result, SimulationResult)
        assert isinstance(report, AnalysisReport)
        assert report.n_agents == sim_result.n_agents

    def test_report_has_churn_curve(self, bridge, profiles_50):
        _, report = bridge.full_analysis(profiles_50)
        assert len(report.churn_curve) == 12


class TestScenarioComparison:
    def test_returns_dict_of_results(self, bridge, profiles_50):
        scenarios = {
            "baseline": {},
            "stress": {"rate_schedule": {3: 5.50}},
        }
        results = bridge.scenario_comparison(profiles_50, scenarios)
        assert set(results.keys()) == {"baseline", "stress"}
        for name, (sim, report) in results.items():
            assert isinstance(sim, SimulationResult)
            assert isinstance(report, AnalysisReport)

    def test_deterministic(self, bridge, profiles_50):
        r1 = bridge.from_profiles(profiles_50, seed=42)
        r2 = bridge.from_profiles(profiles_50, seed=42)
        assert r1.total_churned == r2.total_churned
