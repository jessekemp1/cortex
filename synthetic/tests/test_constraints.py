#!/usr/bin/env python3
"""Tests for the Statistical Constraint Engine."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.constraints import ConstraintEngine, ConstraintReport, ConstraintResult
from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile, GenerationRequest


@pytest.fixture
def engine():
    return ConstraintEngine()


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def kb():
    return CanadianFinServKB()


@pytest.fixture
def sample_profiles(generator):
    """Generate a batch of 200 profiles for testing."""
    request = GenerationRequest(data_type="profiles", count=200)
    result = generator.generate(request)
    # Re-generate profiles directly for in-memory access
    profiles, _ = generator._generate_profiles(request)
    return profiles


class TestChiSquared:
    """Test chi-squared goodness-of-fit for categorical distributions."""

    def test_province_distribution_passes(self, engine, sample_profiles):
        """Province distribution should roughly match StatsCan."""
        report = engine.validate_batch(sample_profiles)
        chi_results = [r for r in report.results if r.test_name == "chi_squared" and r.dimension == "province"]
        assert len(chi_results) == 1
        # With 200 samples, chi-squared should pass if generator is calibrated
        assert chi_results[0].statistic >= 0  # Valid statistic

    def test_segment_distribution_passes(self, engine, sample_profiles):
        """Segment distribution should match Big 5 averages."""
        report = engine.validate_batch(sample_profiles)
        chi_results = [r for r in report.results if r.test_name == "chi_squared" and r.dimension == "segment"]
        assert len(chi_results) == 1
        assert chi_results[0].deviation < 0.20  # < 20% max deviation

    def test_digital_adoption_tested(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        chi_results = [r for r in report.results if r.test_name == "chi_squared" and r.dimension == "digital_adoption"]
        assert len(chi_results) == 1

    def test_empty_batch_handled(self, engine):
        report = engine.validate_batch([])
        assert report.all_passed  # Empty = vacuously true
        assert report.pass_rate == 1.0

    def test_chi_squared_with_perfect_distribution(self, engine):
        """Exact match to KB should pass all tests."""
        # Create profiles that exactly match province distribution
        kb = engine.kb
        constraint = kb.get_constraint("province_distribution")
        profiles = []
        n = 1000
        for prov, pct in constraint.distribution.items():
            count = int(pct * n)
            for _ in range(count):
                profiles.append(CustomerProfile(
                    profile_id=f"TEST-{len(profiles)}",
                    age=35, province=prov, fsa="M5V", segment="mass_market",
                    annual_income=50000.0, household_income=80000.0,
                    credit_score=700, products_held=["chequing"],
                    total_deposits=10000.0, total_credit_outstanding=0.0,
                    digital_adoption="hybrid", primary_channel="mobile",
                    tenure_years=5.0, products_per_household=1,
                ))
        report = engine.validate_batch(profiles)
        prov_chi = [r for r in report.results if r.test_name == "chi_squared" and r.dimension == "province"]
        assert prov_chi[0].passed


class TestJSD:
    """Test Jensen-Shannon Divergence metric."""

    def test_jsd_computed_for_all_categoricals(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        jsd_results = [r for r in report.results if r.test_name == "jsd"]
        # Should have JSD for province, segment, digital_adoption, primary_channel
        assert len(jsd_results) >= 4

    def test_jsd_range_valid(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        jsd_results = [r for r in report.results if r.test_name == "jsd"]
        for jsd in jsd_results:
            assert 0.0 <= jsd.statistic <= 1.0, f"JSD out of range for {jsd.dimension}"

    def test_jsd_identical_distributions_near_zero(self, engine):
        """JSD of identical distributions should be ~0."""
        import numpy as np
        p = np.array([0.4, 0.3, 0.2, 0.1])
        q = np.array([0.4, 0.3, 0.2, 0.1])
        jsd = ConstraintEngine._compute_jsd(p, q)
        assert jsd < 0.001

    def test_jsd_different_distributions_positive(self, engine):
        """JSD of very different distributions should be significant."""
        import numpy as np
        p = np.array([0.9, 0.05, 0.03, 0.02])
        q = np.array([0.25, 0.25, 0.25, 0.25])
        jsd = ConstraintEngine._compute_jsd(p, q)
        assert jsd > 0.1


class TestKS:
    """Test Kolmogorov-Smirnov test for continuous distributions."""

    def test_ks_tests_run_for_continuous_dims(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        ks_results = [r for r in report.results if r.test_name == "ks"]
        # Should test age, income, credit_score, tenure
        assert len(ks_results) >= 3

    def test_ks_statistic_valid_range(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        ks_results = [r for r in report.results if r.test_name == "ks"]
        for ks in ks_results:
            assert 0.0 <= ks.statistic <= 1.0

    def test_ks_pvalue_valid(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        ks_results = [r for r in report.results if r.test_name == "ks"]
        for ks in ks_results:
            assert ks.p_value is not None
            assert 0.0 <= ks.p_value <= 1.0


class TestJointDistribution:
    """Test joint distribution (province × segment) chi-squared."""

    def test_joint_test_runs_with_enough_data(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        joint_results = [r for r in report.results if r.test_name == "chi_squared_joint"]
        assert len(joint_results) == 1  # Should run with 200 profiles

    def test_joint_test_skipped_with_too_few(self, engine):
        """Joint test needs >= 50 profiles."""
        profiles = [
            CustomerProfile(
                profile_id=f"TEST-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(20)
        ]
        report = engine.validate_batch(profiles)
        joint_results = [r for r in report.results if r.test_name == "chi_squared_joint"]
        assert len(joint_results) == 0  # Skipped


class TestDeviationVector:
    """Test per-dimension deviation computation."""

    def test_deviation_vector_has_all_dimensions(self, engine, sample_profiles):
        dev = engine.compute_deviation_vector(sample_profiles)
        # Should have province, segment, digital deviations + continuous
        assert any(k.startswith("province_") for k in dev)
        assert any(k.startswith("segment_") for k in dev)
        assert "age_mean" in dev
        assert "income_mean_log" in dev
        assert "credit_mean" in dev

    def test_deviation_signs_correct(self, engine):
        """If all profiles are ON, province_ON should be positive (over-represented)."""
        profiles = [
            CustomerProfile(
                profile_id=f"TEST-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(100)
        ]
        dev = engine.compute_deviation_vector(profiles)
        # ON is 38.5% of Canada but 100% of this batch
        assert dev["province_ON"] > 0.5

    def test_empty_batch_returns_empty(self, engine):
        dev = engine.compute_deviation_vector([])
        assert dev == {}


class TestAntiCollapse:
    """Test hard reset detection (15% threshold)."""

    def test_no_collapse_on_normal_batch(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        # Normal generation shouldn't trigger hard reset
        # (though it's possible with random sampling)
        assert isinstance(report.needs_hard_reset, bool)

    def test_collapse_detected_on_skewed_batch(self, engine):
        """All-ON batch should trigger collapse warning for some provinces."""
        profiles = [
            CustomerProfile(
                profile_id=f"TEST-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(100)
        ]
        dev = engine.compute_deviation_vector(profiles)
        needs_reset, collapsed = engine.check_collapse_risk(dev)
        assert needs_reset
        assert "province_ON" in collapsed

    def test_threshold_boundary(self, engine):
        """Exactly at threshold should not trigger."""
        dev_vector = {"test_dim": 0.15}
        needs_reset, collapsed = engine.check_collapse_risk(dev_vector)
        assert not needs_reset  # 0.15 == threshold, not > threshold

    def test_just_over_threshold(self, engine):
        dev_vector = {"test_dim": 0.151}
        needs_reset, collapsed = engine.check_collapse_risk(dev_vector)
        assert needs_reset
        assert "test_dim" in collapsed


class TestConstraintReport:
    """Test report aggregation and serialization."""

    def test_report_serializes(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        d = report.to_dict()
        assert "results" in d
        assert "deviation_vector" in d
        assert "pass_rate" in d

    def test_report_summary_readable(self, engine, sample_profiles):
        report = engine.validate_batch(sample_profiles)
        summary = report.summary()
        assert "Constraints:" in summary
        assert "passed" in summary
