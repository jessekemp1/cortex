"""Standalone tests for Pupil MarketAnalyzer."""

import pytest
from helpers import make_mixed_profiles

from pupil.analysis import AnalysisReport, MarketAnalyzer
from pupil.market_env import build_timeline
from pupil.simulation import SimulationEngine


@pytest.fixture
def mixed_simulation_result():
    profiles = make_mixed_profiles(75)
    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(months=12)
    return engine.run(timeline)


@pytest.fixture
def analyzer():
    return MarketAnalyzer()


class TestAnalyze:
    def test_returns_analysis_report(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert isinstance(report, AnalysisReport)
        assert report.n_agents == mixed_simulation_result.n_agents

    def test_has_segment_analyses(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        segments = {sa.segment for sa in report.segment_analyses}
        assert "mass_market" in segments

    def test_churn_curve_monotonic(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for i in range(1, len(report.churn_curve)):
            assert (
                report.churn_curve[i]["cumulative_churn"]
                >= report.churn_curve[i - 1]["cumulative_churn"]
            )

    def test_to_dict_complete(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        d = report.to_dict()
        assert "segments" in d
        assert "migration_flows" in d
        assert "churn_curve" in d
        assert "action_summary" in d
