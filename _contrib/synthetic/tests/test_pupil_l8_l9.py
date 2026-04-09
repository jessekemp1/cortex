#!/usr/bin/env python3
"""Tests for Pupil Layer 8 (Behavioral Fidelity) and Layer 9 (Temporal Coherence)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.pupil.behavioral_fidelity import (
    BehavioralFidelityValidator,
    FidelityReport,
)
from synthetic.pupil.market_env import build_timeline
from synthetic.pupil.simulation import SimulationEngine, SimulationResult
from synthetic.pupil.temporal_coherence import (
    CoherenceReport,
    TemporalCoherenceValidator,
)
from synthetic.schemas import CustomerProfile

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


def make_mixed_profiles(n: int = 75) -> list[CustomerProfile]:
    """Create a mixed-segment population for realistic testing."""
    profiles = []
    # Distribution: ~40% mass_market, ~20% mass_affluent, ~13% new_to_canada,
    # ~10% affluent, ~7% small_business, ~5% high_net_worth, ~5% commercial
    segments = [
        ("mass_market", int(n * 0.40)),
        ("mass_affluent", int(n * 0.20)),
        ("new_to_canada", int(n * 0.13)),
        ("affluent", int(n * 0.10)),
        ("small_business", int(n * 0.07)),
        ("high_net_worth", int(n * 0.05)),
    ]
    # Fill remainder with mass_market
    allocated = sum(count for _, count in segments)
    if allocated < n:
        segments[0] = ("mass_market", segments[0][1] + (n - allocated))

    idx = 0
    segment_configs = {
        "mass_market": {"credit_score": 700, "income": 60000, "deposits": 20000},
        "mass_affluent": {"credit_score": 740, "income": 110000, "deposits": 75000},
        "new_to_canada": {"credit_score": 640, "income": 50000, "deposits": 10000},
        "affluent": {"credit_score": 770, "income": 250000, "deposits": 200000},
        "small_business": {"credit_score": 710, "income": 85000, "deposits": 45000},
        "high_net_worth": {"credit_score": 800, "income": 400000, "deposits": 500000},
    }

    for seg, count in segments:
        cfg = segment_configs[seg]
        for _ in range(count):
            profiles.append(
                make_profile(
                    profile_id=f"mix-{idx:03d}",
                    segment=seg,
                    credit_score=cfg["credit_score"],
                    annual_income=cfg["income"],
                    total_deposits=cfg["deposits"],
                )
            )
            idx += 1

    return profiles


@pytest.fixture
def baseline_result():
    """Standard baseline simulation: 75 mixed agents, 12 months, seed=42."""
    profiles = make_mixed_profiles(75)
    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(months=12)
    return engine.run(timeline)


@pytest.fixture
def short_result():
    """Short simulation: 20 agents, 3 months."""
    profiles = [make_profile(profile_id=f"short-{i}") for i in range(20)]
    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(months=3)
    return engine.run(timeline)


@pytest.fixture
def single_step_result():
    """Single-step simulation: 10 agents, 1 month."""
    profiles = [make_profile(profile_id=f"single-{i}") for i in range(10)]
    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(months=1)
    return engine.run(timeline)


@pytest.fixture
def stress_result():
    """Stress scenario: rate hikes + unemployment spike."""
    profiles = make_mixed_profiles(75)
    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(
        months=12,
        rate_schedule={0: 4.50, 3: 5.25, 6: 6.00},
        unemployment_schedule={0: 6.1, 4: 8.0, 8: 9.5},
    )
    return engine.run(timeline)


@pytest.fixture
def empty_result():
    """Empty simulation result."""
    return SimulationResult(
        n_agents=0,
        n_steps=0,
        steps=[],
        final_snapshots=[],
        all_actions=[],
    )


@pytest.fixture
def l8_validator():
    return BehavioralFidelityValidator()


@pytest.fixture
def l9_validator():
    return TemporalCoherenceValidator()


# ============================================================================
# Layer 8: Behavioral Fidelity Tests
# ============================================================================


class TestBehavioralFidelityBaseline:
    """Test L8 validator on standard baseline scenario."""

    def test_baseline_passes(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        assert isinstance(report, FidelityReport)
        assert report.overall_score > 0.6, (
            f"Baseline should pass L8 (score={report.overall_score:.3f})"
        )
        assert report.passed is True

    def test_baseline_has_all_checks(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        check_names = {c.check_name for c in report.checks}
        assert "churn_rate_fidelity" in check_names
        assert "product_adoption_fidelity" in check_names
        assert "deposit_sensitivity" in check_names
        assert "credit_score_range" in check_names
        assert "lifecycle_transitions" in check_names

    def test_baseline_agent_count(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        assert report.n_agents == 75
        assert report.n_steps == 12

    def test_baseline_segment_scores(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        assert len(report.segment_scores) > 0
        for seg, score in report.segment_scores.items():
            assert 0.0 <= score <= 1.0, f"Segment {seg} score out of range"


class TestBehavioralFidelityChurnCheck:
    """Test the churn rate fidelity check specifically."""

    def test_churn_check_has_segment_detail(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        churn_check = next(c for c in report.checks if c.check_name == "churn_rate_fidelity")
        assert isinstance(churn_check.actual, dict)
        # Should have at least mass_market segment detail
        assert "mass_market" in churn_check.actual

    def test_churn_check_segments_have_expected(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        churn_check = next(c for c in report.checks if c.check_name == "churn_rate_fidelity")
        for seg, detail in churn_check.actual.items():
            assert "expected" in detail
            assert "observed" in detail
            assert "tolerance" in detail
            assert "in_range" in detail
            assert detail["expected"] > 0, f"Segment {seg} should have non-zero expected churn"

    def test_churn_score_between_0_and_1(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        churn_check = next(c for c in report.checks if c.check_name == "churn_rate_fidelity")
        assert 0.0 <= churn_check.score <= 1.0


class TestBehavioralFidelityCreditCheck:
    """Test the credit score range check."""

    def test_credit_scores_stay_valid(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        credit_check = next(c for c in report.checks if c.check_name == "credit_score_range")
        # Baseline scenario should have no violations
        assert credit_check.passed is True
        assert credit_check.score == 1.0, "No credit range violations expected in baseline"

    def test_credit_check_reports_observation_count(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        credit_check = next(c for c in report.checks if c.check_name == "credit_score_range")
        assert credit_check.actual["total_observations"] > 0


class TestBehavioralFidelityLifecycleCheck:
    """Test the lifecycle transition check."""

    def test_no_invalid_transitions_baseline(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        lc_check = next(c for c in report.checks if c.check_name == "lifecycle_transitions")
        # The simulation engine should produce only valid transitions
        assert lc_check.passed is True, f"Found invalid transitions: {lc_check.actual}"
        assert lc_check.score == 1.0


class TestBehavioralFidelityEdgeCases:
    """Test L8 edge cases."""

    def test_empty_result(self, l8_validator, empty_result):
        report = l8_validator.validate(empty_result)
        assert report.overall_score == 0.0
        assert report.passed is False
        assert len(report.checks) == 1
        assert report.checks[0].check_name == "empty_result"

    def test_single_step_result(self, l8_validator, single_step_result):
        report = l8_validator.validate(single_step_result)
        assert isinstance(report, FidelityReport)
        # Single step should still produce some meaningful checks
        assert report.overall_score >= 0.0
        # Lifecycle check should pass (1 step = no transitions)
        lc_check = next(c for c in report.checks if c.check_name == "lifecycle_transitions")
        assert lc_check.passed is True

    def test_short_result(self, l8_validator, short_result):
        report = l8_validator.validate(short_result)
        assert isinstance(report, FidelityReport)
        assert 0.0 <= report.overall_score <= 1.0

    def test_stress_scenario_still_scored(self, l8_validator, stress_result):
        report = l8_validator.validate(stress_result)
        assert isinstance(report, FidelityReport)
        # Stress scenario may have lower score but should still produce valid report
        assert 0.0 <= report.overall_score <= 1.0
        assert len(report.checks) == 5


class TestBehavioralFidelitySerialization:
    """Test report serialization."""

    def test_report_to_dict(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        d = report.to_dict()
        assert "overall_score" in d
        assert "passed" in d
        assert "checks" in d
        assert "segment_scores" in d
        assert "n_agents" in d
        assert "n_steps" in d
        assert isinstance(d["checks"], list)
        assert len(d["checks"]) == 5

    def test_check_to_dict(self, l8_validator, baseline_result):
        report = l8_validator.validate(baseline_result)
        for check in report.checks:
            d = check.to_dict()
            assert "check_name" in d
            assert "passed" in d
            assert "score" in d
            assert "detail" in d
            assert isinstance(d["score"], float)


# ============================================================================
# Layer 9: Temporal Coherence Tests
# ============================================================================


class TestTemporalCoherenceBaseline:
    """Test L9 validator on standard baseline scenario."""

    def test_baseline_passes(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        assert isinstance(report, CoherenceReport)
        assert report.overall_score > 0.6, (
            f"Baseline should pass L9 (score={report.overall_score:.3f})"
        )
        assert report.passed is True

    def test_baseline_has_all_checks(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        check_names = {c.check_name for c in report.checks}
        assert "satisfaction_autocorrelation" in check_names
        assert "churn_monotonicity" in check_names
        assert "deposit_smoothness" in check_names
        assert "unemployment_responsiveness" in check_names
        assert "state_transition_validity" in check_names

    def test_baseline_agent_count(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        assert report.n_agents == 75
        assert report.n_steps == 12


class TestTemporalCoherenceAutocorrelation:
    """Test satisfaction autocorrelation check."""

    def test_autocorrelation_positive(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        ac_check = next(c for c in report.checks if c.check_name == "satisfaction_autocorrelation")
        # Satisfaction should be positively autocorrelated in baseline
        assert ac_check.actual is not None
        assert ac_check.actual > 0.0, "Satisfaction should show positive autocorrelation"
        assert 0.0 <= ac_check.score <= 1.0


class TestTemporalCoherenceChurnMonotonicity:
    """Test churn curve monotonicity check."""

    def test_churn_monotonic_baseline(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        churn_check = next(c for c in report.checks if c.check_name == "churn_monotonicity")
        # Simulation engine produces non-decreasing churn
        assert churn_check.passed is True
        assert churn_check.score == 1.0

    def test_churn_check_reports_curve(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        churn_check = next(c for c in report.checks if c.check_name == "churn_monotonicity")
        assert "churn_curve" in churn_check.actual
        assert len(churn_check.actual["churn_curve"]) == 12


class TestTemporalCoherenceDepositSmoothness:
    """Test deposit trajectory smoothness check."""

    def test_deposits_smooth_baseline(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        dep_check = next(c for c in report.checks if c.check_name == "deposit_smoothness")
        # Baseline should have smooth deposits (low violation rate)
        assert dep_check.score > 0.5, f"Deposit smoothness too low: {dep_check.detail}"

    def test_deposit_check_has_violation_detail(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        dep_check = next(c for c in report.checks if c.check_name == "deposit_smoothness")
        assert "violations" in dep_check.actual
        assert "total_transitions" in dep_check.actual
        assert "violation_rate" in dep_check.actual


class TestTemporalCoherenceStateTransitions:
    """Test state transition validity in time series."""

    def test_no_invalid_transitions_baseline(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        trans_check = next(c for c in report.checks if c.check_name == "state_transition_validity")
        assert trans_check.passed is True, f"Found invalid transitions: {trans_check.actual}"
        assert trans_check.score == 1.0


class TestTemporalCoherenceEdgeCases:
    """Test L9 edge cases."""

    def test_empty_result(self, l9_validator, empty_result):
        report = l9_validator.validate(empty_result)
        assert report.overall_score == 0.0
        assert report.passed is False
        assert len(report.checks) == 1
        assert report.checks[0].check_name == "empty_result"

    def test_single_step_result(self, l9_validator, single_step_result):
        report = l9_validator.validate(single_step_result)
        assert isinstance(report, CoherenceReport)
        # Most checks should gracefully handle 1 step
        assert report.overall_score >= 0.0

    def test_short_result(self, l9_validator, short_result):
        report = l9_validator.validate(short_result)
        assert isinstance(report, CoherenceReport)
        assert 0.0 <= report.overall_score <= 1.0

    def test_stress_scenario_coherent(self, l9_validator, stress_result):
        report = l9_validator.validate(stress_result)
        assert isinstance(report, CoherenceReport)
        # Even stress scenario should maintain temporal coherence
        assert 0.0 <= report.overall_score <= 1.0
        # Churn monotonicity should still hold
        churn_check = next(c for c in report.checks if c.check_name == "churn_monotonicity")
        assert churn_check.passed is True


class TestTemporalCoherenceSerialization:
    """Test report serialization."""

    def test_report_to_dict(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        d = report.to_dict()
        assert "overall_score" in d
        assert "passed" in d
        assert "checks" in d
        assert "n_agents" in d
        assert "n_steps" in d
        assert isinstance(d["checks"], list)
        assert len(d["checks"]) == 5

    def test_check_to_dict(self, l9_validator, baseline_result):
        report = l9_validator.validate(baseline_result)
        for check in report.checks:
            d = check.to_dict()
            assert "check_name" in d
            assert "passed" in d
            assert "score" in d
            assert "detail" in d
            assert isinstance(d["score"], float)


# ============================================================================
# Cross-Layer Tests (L8 + L9 together)
# ============================================================================


class TestCrossLayerConsistency:
    """Test that L8 and L9 agree on the same simulation."""

    def test_both_pass_baseline(self, l8_validator, l9_validator, baseline_result):
        l8_report = l8_validator.validate(baseline_result)
        l9_report = l9_validator.validate(baseline_result)
        assert l8_report.passed is True, f"L8 failed: {l8_report.overall_score:.3f}"
        assert l9_report.passed is True, f"L9 failed: {l9_report.overall_score:.3f}"

    def test_lifecycle_checks_agree(self, l8_validator, l9_validator, baseline_result):
        """Both L8 and L9 check lifecycle transitions — they should agree."""
        l8_report = l8_validator.validate(baseline_result)
        l9_report = l9_validator.validate(baseline_result)

        l8_lc = next(c for c in l8_report.checks if c.check_name == "lifecycle_transitions")
        l9_lc = next(c for c in l9_report.checks if c.check_name == "state_transition_validity")
        # Both should pass or both should fail (they check the same transitions)
        assert l8_lc.passed == l9_lc.passed

    def test_deterministic_results(self, l8_validator, l9_validator):
        """Same seed produces same validation scores."""
        profiles = make_mixed_profiles(75)

        engine1 = SimulationEngine(seed=42)
        engine1.generate_agents(profiles)
        result1 = engine1.run(build_timeline(months=12))

        engine2 = SimulationEngine(seed=42)
        engine2.generate_agents(profiles)
        result2 = engine2.run(build_timeline(months=12))

        l8_r1 = l8_validator.validate(result1)
        l8_r2 = l8_validator.validate(result2)
        assert l8_r1.overall_score == pytest.approx(l8_r2.overall_score, abs=1e-6)

        l9_r1 = l9_validator.validate(result1)
        l9_r2 = l9_validator.validate(result2)
        assert l9_r1.overall_score == pytest.approx(l9_r2.overall_score, abs=1e-6)
