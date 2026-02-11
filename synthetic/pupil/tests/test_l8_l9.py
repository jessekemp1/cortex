"""Standalone tests for Pupil L8 (Behavioral Fidelity) and L9 (Temporal Coherence)."""

import pytest

from pupil.market_env import build_timeline
from pupil.simulation import SimulationEngine, SimulationResult
from pupil.behavioral_fidelity import BehavioralFidelityValidator, FidelityReport
from pupil.temporal_coherence import TemporalCoherenceValidator, CoherenceReport

from helpers import make_mixed_profiles


@pytest.fixture
def baseline_result():
    profiles = make_mixed_profiles(75)
    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(months=12)
    return engine.run(timeline)


@pytest.fixture
def empty_result():
    return SimulationResult(
        n_agents=0, n_steps=0, steps=[], final_snapshots=[], all_actions=[],
    )


@pytest.fixture
def l8_validator():
    return BehavioralFidelityValidator()


@pytest.fixture
def l9_validator():
    return TemporalCoherenceValidator()


class TestBehavioralFidelity:
    def test_baseline_passes(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        assert isinstance(report, FidelityReport)
        assert report.passed is True
        assert report.overall_score > 0.6

    def test_has_all_checks(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        check_names = {c.check_name for c in report.checks}
        assert "churn_rate_fidelity" in check_names
        assert "credit_score_range" in check_names
        assert "lifecycle_transitions" in check_names

    def test_empty_result(self, l8_validator, empty_result):
        report = l8_validator.validate(empty_result)
        assert report.overall_score == 0.0
        assert report.passed is False


class TestTemporalCoherence:
    def test_baseline_passes(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        assert isinstance(report, CoherenceReport)
        assert report.passed is True
        assert report.overall_score > 0.6

    def test_churn_monotonic(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        churn_check = next(
            c for c in report.checks if c.check_name == "churn_monotonicity"
        )
        assert churn_check.passed is True

    def test_empty_result(self, l9_validator, empty_result):
        report = l9_validator.validate(empty_result)
        assert report.overall_score == 0.0
        assert report.passed is False


class TestCrossLayer:
    def test_both_pass_baseline(self, l8_validator, l9_validator, baseline_result):
        l8_report = l8_validator.validate(baseline_result)
        l9_report = l9_validator.validate(baseline_result)
        assert l8_report.passed is True
        assert l9_report.passed is True
