#!/usr/bin/env python3
"""Tests for the Feedback Flywheel Orchestrator."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.flywheel import Flywheel, FlywheelReport
from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile, GenerationRequest


@pytest.fixture
def kb():
    return CanadianFinServKB()


@pytest.fixture
def flywheel(kb):
    return Flywheel(kb=kb)


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def sample_profiles(generator):
    """Generate 100 profiles for flywheel testing."""
    request = GenerationRequest(data_type="profiles", count=100)
    profiles, _ = generator._generate_profiles(request)
    return profiles


@pytest.fixture
def sample_transactions(generator):
    """Generate 100 transactions with risk flags."""
    request = GenerationRequest(
        data_type="transactions", count=100,
        include_risk_flags=True, risk_profile="high",
    )
    txns, _ = generator._generate_transactions(request)
    return txns


class TestFlywheelCycle:
    """Test full flywheel cycle execution."""

    def test_cycle_with_profiles(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="test-001")
        assert isinstance(report, FlywheelReport)
        assert report.layers_executed >= 3  # L1, L2, L3 always; L5, L6 if deps available
        assert report.overall_score > 0

    def test_cycle_with_transactions(self, flywheel, sample_transactions):
        report = flywheel.run_cycle(
            transactions=sample_transactions, flywheel_id="test-002"
        )
        assert report.layers_executed >= 1  # L4 should run

    def test_cycle_with_both(self, flywheel, sample_profiles, sample_transactions):
        report = flywheel.run_cycle(
            profiles=sample_profiles,
            transactions=sample_transactions,
            flywheel_id="test-003",
        )
        assert report.layers_executed == 6  # All 6 layers (L1-L6)

    def test_cycle_skip_heavy_layers(self, flywheel, sample_profiles, sample_transactions):
        report = flywheel.run_cycle(
            profiles=sample_profiles,
            transactions=sample_transactions,
            flywheel_id="test-skip",
            skip_heavy_layers=True,
        )
        assert report.layers_executed == 4  # Only L1-L4

    def test_cycle_increments(self, flywheel, sample_profiles):
        r1 = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="t1")
        r2 = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="t2")
        assert r1.cycle_id != r2.cycle_id
        # Second cycle should have quality_improvement calculated
        assert r2.quality_improvement is not None

    def test_empty_inputs_handled(self, flywheel):
        report = flywheel.run_cycle(flywheel_id="empty")
        assert report.layers_executed == 0
        assert report.overall_score == 0.0


class TestLayer1Quality:
    """Test Layer 1: Quality Gate."""

    def test_layer1_runs_and_scores(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l1-test")
        l1 = next(lr for lr in report.layer_results if lr.layer_num == 1)
        assert l1.layer_name == "quality_gate"
        assert 0.0 <= l1.score <= 1.0

    def test_layer1_identifies_weak_dimensions(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l1-weak")
        l1 = next(lr for lr in report.layer_results if lr.layer_num == 1)
        assert "weak_dimensions" in l1.feedback
        assert "avg_quality" in l1.feedback

    def test_layer1_reports_pass_rate(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l1-rate")
        l1 = next(lr for lr in report.layer_results if lr.layer_num == 1)
        assert "pass_rate" in l1.feedback
        assert 0.0 <= l1.feedback["pass_rate"] <= 1.0


class TestLayer2Statistical:
    """Test Layer 2: Statistical Fidelity."""

    def test_layer2_runs_with_enough_profiles(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l2-test")
        l2 = next(lr for lr in report.layer_results if lr.layer_num == 2)
        assert l2.layer_name == "statistical_fidelity"

    def test_layer2_produces_deviation_vector(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l2-dev")
        l2 = next(lr for lr in report.layer_results if lr.layer_num == 2)
        assert "deviation_vector" in l2.feedback
        assert len(l2.feedback["deviation_vector"]) > 0

    def test_layer2_skipped_for_small_batch(self, flywheel):
        """Layer 2 needs >= 10 profiles."""
        profiles = [
            CustomerProfile(
                profile_id=f"SMALL-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(5)
        ]
        report = flywheel.run_cycle(profiles=profiles, flywheel_id="l2-small")
        l2_results = [lr for lr in report.layer_results if lr.layer_num == 2]
        assert len(l2_results) == 0  # Skipped


class TestLayer3Consistency:
    """Test Layer 3: Cross-Field Consistency."""

    def test_layer3_checks_all_consistency_rules(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l3-test")
        l3 = next(lr for lr in report.layer_results if lr.layer_num == 3)
        rates = l3.feedback["inconsistency_rates"]
        assert "income_segment_mismatch" in rates
        assert "credit_segment_mismatch" in rates
        assert "household_lt_individual" in rates
        assert "age_tenure_impossible" in rates

    def test_layer3_high_score_for_calibrated_data(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l3-score")
        l3 = next(lr for lr in report.layer_results if lr.layer_num == 3)
        assert l3.score >= 0.80  # Generator should produce consistent data


class TestLayer4Risk:
    """Test Layer 4: Risk Model Validation."""

    def test_layer4_runs_on_transactions(self, flywheel, sample_transactions):
        report = flywheel.run_cycle(
            transactions=sample_transactions, flywheel_id="l4-test"
        )
        l4 = next(lr for lr in report.layer_results if lr.layer_num == 4)
        assert l4.layer_name == "risk_model_validation"

    def test_layer4_reports_confusion_matrix(self, flywheel, sample_transactions):
        report = flywheel.run_cycle(
            transactions=sample_transactions, flywheel_id="l4-cm"
        )
        l4 = next(lr for lr in report.layer_results if lr.layer_num == 4)
        cm = l4.feedback["confusion_matrix"]
        assert "TP" in cm
        assert "FP" in cm
        assert "FN" in cm
        assert "TN" in cm

    def test_layer4_detection_rate_reported(self, flywheel, sample_transactions):
        report = flywheel.run_cycle(
            transactions=sample_transactions, flywheel_id="l4-dr"
        )
        l4 = next(lr for lr in report.layer_results if lr.layer_num == 4)
        assert "detection_rate" in l4.feedback
        assert 0.0 <= l4.feedback["detection_rate"] <= 1.0


class TestLayer5Discriminator:
    """Test Layer 5: Discriminator Feedback via flywheel."""

    def test_layer5_runs_with_enough_profiles(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l5-test")
        l5_results = [lr for lr in report.layer_results if lr.layer_num == 5]
        assert len(l5_results) == 1
        assert l5_results[0].layer_name == "discriminator_feedback"

    def test_layer5_reports_auc(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l5-auc")
        l5 = next(lr for lr in report.layer_results if lr.layer_num == 5)
        assert "auc_roc" in l5.feedback
        assert 0.0 <= l5.feedback["auc_roc"] <= 1.0

    def test_layer5_reports_shap_corrections(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l5-shap")
        l5 = next(lr for lr in report.layer_results if lr.layer_num == 5)
        assert "shap_corrections" in l5.feedback
        assert "top_distinguishing_features" in l5.feedback

    def test_layer5_skipped_for_small_batch(self, flywheel):
        """Layer 5 needs >= 30 profiles."""
        profiles = [
            CustomerProfile(
                profile_id=f"SMALL-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(20)
        ]
        report = flywheel.run_cycle(profiles=profiles, flywheel_id="l5-small")
        l5_results = [lr for lr in report.layer_results if lr.layer_num == 5]
        assert len(l5_results) == 0  # Skipped


class TestLayer6TSTR:
    """Test Layer 6: TSTR via flywheel."""

    def test_layer6_runs_with_enough_profiles(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l6-test")
        l6_results = [lr for lr in report.layer_results if lr.layer_num == 6]
        assert len(l6_results) == 1
        assert l6_results[0].layer_name == "tstr_utility"

    def test_layer6_reports_task_results(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l6-tasks")
        l6 = next(lr for lr in report.layer_results if lr.layer_num == 6)
        assert "task_results" in l6.feedback
        assert len(l6.feedback["task_results"]) >= 3  # At least 3 profile tasks

    def test_layer6_reports_delta(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="l6-delta")
        l6 = next(lr for lr in report.layer_results if lr.layer_num == 6)
        assert "avg_delta" in l6.feedback
        assert "worst_delta" in l6.feedback

    def test_layer6_skipped_for_small_batch(self, flywheel):
        """Layer 6 needs >= 50 profiles."""
        profiles = [
            CustomerProfile(
                profile_id=f"SMALL-{i}", age=35, province="ON", fsa="M5V",
                segment="mass_market", annual_income=50000.0,
                household_income=80000.0, credit_score=700,
                products_held=["chequing"], total_deposits=10000.0,
                total_credit_outstanding=0.0, digital_adoption="hybrid",
                primary_channel="mobile", tenure_years=5.0,
                products_per_household=1,
            )
            for i in range(40)
        ]
        report = flywheel.run_cycle(profiles=profiles, flywheel_id="l6-small")
        l6_results = [lr for lr in report.layer_results if lr.layer_num == 6]
        assert len(l6_results) == 0  # Skipped


class TestCorrections:
    """Test feedback aggregation and correction application."""

    def test_corrections_computed(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="corr-test")
        assert "adjustments" in report.corrections
        assert "weighted_score" in report.corrections

    def test_corrections_bounded(self, flywheel, sample_profiles):
        """No single correction should exceed MAX_CORRECTION."""
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="corr-bound")
        for dim, val in report.corrections.get("adjustments", {}).items():
            assert abs(val) <= flywheel.MAX_CORRECTION + 1e-9

    def test_apply_corrections_modifies_params(self, flywheel):
        corrections = {"adjustments": {"province_ON": 0.02, "segment_mass_market": -0.01}}
        params = {"province_ON": 0.385, "segment_mass_market": 0.55}
        adjusted = flywheel.apply_corrections(corrections, params)
        assert adjusted["province_ON"] == pytest.approx(0.405, abs=0.001)
        assert adjusted["segment_mass_market"] == pytest.approx(0.54, abs=0.001)


class TestHardReset:
    """Test hard reset detection."""

    def test_no_reset_on_normal_deviation(self, flywheel):
        assert not flywheel.should_hard_reset({"province": 0.03, "segment": 0.05})

    def test_reset_on_extreme_deviation(self, flywheel):
        assert flywheel.should_hard_reset({"province": 0.20})

    def test_reset_threshold_exact(self, flywheel):
        # 0.15 exactly should NOT trigger (> not >=)
        assert not flywheel.should_hard_reset({"dim": 0.15})
        assert flywheel.should_hard_reset({"dim": 0.151})


class TestTrend:
    """Test quality trend tracking."""

    def test_trend_after_multiple_cycles(self, flywheel, sample_profiles):
        for i in range(3):
            flywheel.run_cycle(profiles=sample_profiles, flywheel_id=f"trend-{i}")
        trend = flywheel.get_trend()
        assert trend["cycles"] == 3
        assert "current_score" in trend
        assert trend["trend"] in ("improving", "declining", "stable")

    def test_trend_with_no_cycles(self, flywheel):
        trend = flywheel.get_trend()
        assert trend["trend"] == "no_data"


class TestSerialization:
    """Test report serialization."""

    def test_report_to_dict(self, flywheel, sample_profiles, sample_transactions):
        report = flywheel.run_cycle(
            profiles=sample_profiles,
            transactions=sample_transactions,
            flywheel_id="serial-test",
        )
        d = report.to_dict()
        assert "cycle_id" in d
        assert "layer_results" in d
        assert "corrections" in d
        assert "overall_score" in d

    def test_report_summary_readable(self, flywheel, sample_profiles):
        report = flywheel.run_cycle(profiles=sample_profiles, flywheel_id="summary-test")
        summary = report.summary()
        assert "Flywheel Cycle" in summary
        assert "layers passed" in summary
