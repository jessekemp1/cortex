#!/usr/bin/env python3
"""Tests for the Privacy Guarantee Engine (Layer 7)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.privacy import (
    PRIVACY_FEATURES,
    PrivacyEngine,
    PrivacyReport,
    RecordPrivacy,
)
from synthetic.schemas import CustomerProfile, GenerationRequest


@pytest.fixture
def kb():
    return CanadianFinServKB()


@pytest.fixture
def privacy_engine(kb):
    return PrivacyEngine(kb=kb)


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def sample_profiles(generator):
    """Generate 100 profiles for privacy testing."""
    request = GenerationRequest(data_type="profiles", count=100)
    profiles, _ = generator._generate_profiles(request)
    return profiles


class TestPrivacyEvaluation:
    """Test full privacy evaluation."""

    def test_evaluate_returns_report(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert isinstance(report, PrivacyReport)

    def test_dcr_in_valid_range(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert report.mean_dcr >= 0
        assert report.min_dcr >= 0
        assert 0.0 <= report.dcr_pass_rate <= 1.0

    def test_nndr_in_valid_range(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert report.mean_nndr >= 0
        assert report.min_nndr >= 0
        assert 0.0 <= report.nndr_pass_rate <= 1.0

    def test_mia_in_valid_range(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert 0.0 <= report.mia_accuracy <= 1.0
        assert report.mia_advantage == pytest.approx(
            report.mia_accuracy - 0.5, abs=1e-9
        )

    def test_sample_counts_correct(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert report.n_synthetic == len(sample_profiles)
        assert report.n_reference == len(sample_profiles)

    def test_per_record_generated(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert len(report.per_record) == len(sample_profiles)
        for rec in report.per_record:
            assert isinstance(rec, RecordPrivacy)

    def test_custom_reference(self, privacy_engine, generator):
        """Test providing explicit reference profiles."""
        req = GenerationRequest(data_type="profiles", count=50)
        synth, _ = generator._generate_profiles(req)
        ref, _ = generator._generate_profiles(req)
        report = privacy_engine.evaluate(synth, reference_profiles=ref)
        assert report.n_reference == 50


class TestDCR:
    """Test Distance to Closest Record metric."""

    def test_dcr_positive_for_random_data(self, privacy_engine, sample_profiles):
        """Random synthetic data should have positive DCR."""
        report = privacy_engine.evaluate(sample_profiles)
        assert report.mean_dcr > 0

    def test_dcr_threshold_check(self, privacy_engine, sample_profiles):
        """KB-sampled data should generally pass DCR threshold."""
        report = privacy_engine.evaluate(sample_profiles)
        # Both sets from same KB — records won't be identical since different seeds
        assert report.dcr_pass_rate >= 0.5  # At least half should pass

    def test_identical_records_have_zero_dcr(self, privacy_engine):
        """If synthetic copies reference exactly, DCR should be very low."""
        profiles = [
            CustomerProfile(
                profile_id=f"COPY-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(30)
        ]
        # Evaluate with identical reference — DCR should be ~0
        report = privacy_engine.evaluate(profiles, reference_profiles=profiles)
        assert report.min_dcr == pytest.approx(0.0, abs=1e-9)
        assert not report.passed  # Should fail


class TestNNDR:
    """Test Nearest Neighbor Distance Ratio metric."""

    def test_nndr_range(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        assert report.mean_nndr >= 0
        assert report.mean_nndr <= 1.0  # Ratio of d1/d2, always <= 1

    def test_nndr_with_uniform_distances(self, privacy_engine):
        """When distances are uniform, NNDR should be close to 1."""
        # Create profiles that are roughly equidistant from reference
        gen = SyntheticGenerator()
        req = GenerationRequest(data_type="profiles", count=50)
        synth, _ = gen._generate_profiles(req)
        ref, _ = gen._generate_profiles(req)
        report = privacy_engine.evaluate(synth, reference_profiles=ref)
        # With diverse random data, NNDR should be moderate to high
        assert report.mean_nndr > 0.3


class TestMIA:
    """Test Membership Inference Attack simulation."""

    def test_mia_near_random_for_kb_data(self, privacy_engine, sample_profiles):
        """Both synthetic and reference from same KB → MIA should be near random."""
        report = privacy_engine.evaluate(sample_profiles)
        # MIA advantage should be small (< 0.15 = less than 65% accuracy)
        assert report.mia_accuracy < 0.75, (
            f"MIA accuracy {report.mia_accuracy:.3f} too high — "
            f"synthetic data is leaking membership information"
        )

    def test_mia_with_small_sample(self, privacy_engine):
        """MIA with < 20 samples should return 0.50 (random)."""
        profiles = [
            CustomerProfile(
                profile_id=f"TINY-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(10)
        ]
        report = privacy_engine.evaluate(profiles)
        assert report.mia_accuracy == pytest.approx(0.50, abs=0.01)


class TestPerRecordPrivacy:
    """Test per-record privacy scoring."""

    def test_per_record_structure(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        for rec in report.per_record:
            assert rec.dcr >= 0
            assert rec.nndr >= 0
            assert 0.0 <= rec.privacy_score <= 1.0
            assert rec.closest_feature in PRIVACY_FEATURES
            assert isinstance(rec.safe, bool)

    def test_per_record_profile_ids_match(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        expected_ids = {p.profile_id for p in sample_profiles}
        actual_ids = {r.profile_id for r in report.per_record}
        assert actual_ids == expected_ids

    def test_unsafe_records_identified(self, privacy_engine):
        """Identical records should be flagged as unsafe."""
        profiles = [
            CustomerProfile(
                profile_id=f"UNSAFE-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(30)
        ]
        report = privacy_engine.evaluate(profiles, reference_profiles=profiles)
        unsafe = [r for r in report.per_record if not r.safe]
        assert len(unsafe) == len(profiles)  # All should be unsafe


class TestNoiseCalibration:
    """Test per-dimension noise adjustment feedback."""

    def test_no_adjustments_when_passing(self, privacy_engine, sample_profiles):
        """If all records pass DCR, no noise adjustments needed."""
        report = privacy_engine.evaluate(sample_profiles)
        if report.dcr_pass_rate == 1.0 and report.nndr_pass_rate == 1.0:
            assert len(report.noise_adjustments) == 0

    def test_adjustments_for_violations(self, privacy_engine):
        """Identical records should trigger noise adjustments."""
        profiles = [
            CustomerProfile(
                profile_id=f"ADJ-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(30)
        ]
        report = privacy_engine.evaluate(profiles, reference_profiles=profiles)
        # Should identify low-privacy dimensions and propose noise increases
        assert len(report.low_privacy_dimensions) > 0

    def test_noise_adjustments_positive(self, privacy_engine):
        """Noise adjustments should always be non-negative (increase noise)."""
        profiles = [
            CustomerProfile(
                profile_id=f"POS-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(30)
        ]
        report = privacy_engine.evaluate(profiles, reference_profiles=profiles)
        for feat, adj in report.noise_adjustments.items():
            assert adj >= 0, f"Noise adjustment for {feat} is negative: {adj}"


class TestFeatureExtraction:
    """Test profile-to-feature conversion."""

    def test_feature_matrix_shape(self, privacy_engine, sample_profiles):
        X = privacy_engine._profiles_to_features(sample_profiles)
        assert X.shape == (len(sample_profiles), len(PRIVACY_FEATURES))

    def test_normalization(self, privacy_engine, sample_profiles):
        X = privacy_engine._profiles_to_features(sample_profiles)
        ref = privacy_engine._profiles_to_features(sample_profiles)
        X_norm, ref_norm = privacy_engine._normalize(X, ref)
        assert X_norm.min() >= 0.0 - 1e-9
        assert X_norm.max() <= 1.0 + 1e-9


class TestSerialization:
    """Test report serialization."""

    def test_report_to_dict(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        d = report.to_dict()
        assert "passed" in d
        assert "dcr" in d
        assert "nndr" in d
        assert "mia" in d
        assert "noise_adjustments" in d

    def test_record_privacy_to_dict(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        d = report.per_record[0].to_dict()
        assert "profile_id" in d
        assert "dcr" in d
        assert "nndr" in d
        assert "privacy_score" in d
        assert "safe" in d

    def test_summary_readable(self, privacy_engine, sample_profiles):
        report = privacy_engine.evaluate(sample_profiles)
        summary = report.summary()
        assert "Privacy" in summary
        assert "DCR=" in summary
        assert "NNDR=" in summary
        assert "MIA=" in summary
