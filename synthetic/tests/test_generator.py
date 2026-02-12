#!/usr/bin/env python3
"""Tests for the Synthetic Data Generator."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.quality import SyntheticQualityTracker
from synthetic.schemas import (
    CustomerProfile,
    GenerationRequest,
    GenerationResult,
    Transaction,
)


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def kb():
    return CanadianFinServKB()


@pytest.fixture
def quality_tracker():
    return SyntheticQualityTracker()


class TestSchemas:
    """Test data model schemas."""

    def test_customer_profile_to_dict(self):
        profile = CustomerProfile(
            profile_id="TEST-001",
            age=35,
            province="ON",
            fsa="M5V",
            segment="mass_affluent",
            annual_income=95000.0,
            household_income=150000.0,
            credit_score=750,
            products_held=["chequing", "savings", "tfsa"],
            total_deposits=50000.0,
            total_credit_outstanding=250000.0,
            digital_adoption="digital_first",
            primary_channel="mobile",
            tenure_years=8.5,
            products_per_household=3,
        )
        d = profile.to_dict()
        assert d["profile_id"] == "TEST-001"
        assert d["province"] == "ON"
        assert d["credit_score"] == 750
        assert len(d["products_held"]) == 3

    def test_transaction_to_dict(self):
        txn = Transaction(
            transaction_id="TXN-001",
            profile_id="TEST-001",
            timestamp="2026-02-05T12:00:00",
            transaction_type="pos_purchase",
            amount=42.50,
            currency="CAD",
        )
        d = txn.to_dict()
        assert d["amount"] == 42.50
        assert d["currency"] == "CAD"
        assert d["risk_flag"] == "none"

    def test_generation_result_summary(self):
        request = GenerationRequest(data_type="profiles", count=100)
        result = GenerationResult(
            request=request,
            records_generated=100,
            records_passed_quality=95,
            records_rejected=5,
            average_quality_score=0.87,
            quality_distribution={
                "excellent_0.9+": 40,
                "good_0.8-0.9": 45,
                "fair_0.7-0.8": 10,
                "low_<0.7": 5,
            },
            generation_time_seconds=1.5,
        )
        summary = result.summary()
        assert "100" in summary
        assert "95" in summary
        assert "0.870" in summary


class TestKnowledgeBase:
    """Test Canadian FinServ Knowledge Base."""

    def test_province_distribution_sums_to_1(self, kb):
        constraint = kb.get_constraint("province_distribution")
        total = sum(constraint.distribution.values())
        assert abs(total - 1.0) < 0.01

    def test_segment_distribution_sums_to_1(self, kb):
        constraint = kb.get_constraint("segment_distribution")
        total = sum(constraint.distribution.values())
        assert abs(total - 1.0) < 0.01

    def test_income_ranges_for_segments(self, kb):
        mass = kb.get_income_range_for_segment("mass_market")
        affluent = kb.get_income_range_for_segment("affluent")
        assert mass[1] < affluent[0]  # Mass market max < affluent min

    def test_credit_score_ranges_realistic(self, kb):
        for segment in ["mass_market", "affluent", "high_net_worth"]:
            lo, hi = kb.get_credit_score_range_for_segment(segment)
            assert 300 <= lo <= 900
            assert 300 <= hi <= 900
            assert lo <= hi

    def test_regulatory_params_loaded(self, kb):
        reg = kb.get_regulatory_params()
        assert reg["large_cash_threshold_cad"] == 10_000
        assert reg["max_gds_ratio"] == 0.39
        assert reg["stress_test_rate"] > 0

    def test_fsa_for_province(self, kb):
        fsas = kb.get_fsa_for_province("ON")
        assert len(fsas) > 0
        # Ontario FSAs start with K, L, M, N, or P
        assert all(fsa[0] in "KLMNP" for fsa in fsas)

    def test_product_likelihood_adjusted_by_segment(self, kb):
        mass = kb.get_product_likelihood("mass_market")
        hnw = kb.get_product_likelihood("high_net_worth")
        # HNW should have higher investment account likelihood
        assert hnw["investment_account"] > mass["investment_account"]

    def test_get_all_constraints(self, kb):
        constraints = kb.get_all_constraints()
        assert len(constraints) >= 7  # Province, age, income, segment, credit, product, digital


class TestGenerator:
    """Test synthetic data generation."""

    def test_generate_profiles_basic(self, generator):
        request = GenerationRequest(data_type="profiles", count=10)
        result = generator.generate(request)
        assert result.records_generated == 10
        assert result.records_passed_quality > 0
        assert result.average_quality_score > 0

    def test_generate_profiles_with_segment(self, generator):
        request = GenerationRequest(data_type="profiles", count=20, segment="affluent")
        result = generator.generate(request)
        assert result.records_generated == 20

    def test_generate_profiles_with_province(self, generator):
        request = GenerationRequest(data_type="profiles", count=10, province="QC")
        result = generator.generate(request)
        assert result.records_generated == 10

    def test_generate_transactions_normal(self, generator):
        request = GenerationRequest(data_type="transactions", count=50)
        result = generator.generate(request)
        assert result.records_generated == 50

    def test_generate_transactions_with_risk(self, generator):
        request = GenerationRequest(
            data_type="transactions",
            count=100,
            include_risk_flags=True,
            risk_profile="high",
        )
        result = generator.generate(request)
        assert result.records_generated == 100

    def test_quality_filtering(self, generator):
        request = GenerationRequest(
            data_type="profiles",
            count=50,
            min_quality_score=0.9,  # High threshold
        )
        result = generator.generate(request)
        # Some records may be rejected
        assert result.records_passed_quality <= result.records_generated
        assert result.records_rejected >= 0

    def test_output_written(self, generator):
        request = GenerationRequest(data_type="profiles", count=5)
        result = generator.generate(request)
        assert result.output_path is not None
        assert Path(result.output_path).exists()

    def test_flywheel_id_generated(self, generator):
        request = GenerationRequest(data_type="profiles", count=5)
        result = generator.generate(request)
        assert result.flywheel_id is not None


class TestQualityTracker:
    """Test synthetic data quality validation."""

    def test_profile_quality_score_range(self, quality_tracker):
        profile = CustomerProfile(
            profile_id="QA-001",
            age=40,
            province="ON",
            fsa="M5V",
            segment="mass_affluent",
            annual_income=100000.0,
            household_income=150000.0,
            credit_score=750,
            products_held=["chequing", "savings", "tfsa"],
            total_deposits=80000.0,
            total_credit_outstanding=300000.0,
            digital_adoption="digital_first",
            primary_channel="mobile",
            tenure_years=10.0,
            products_per_household=3,
        )
        quality = quality_tracker.assess_profile(profile)
        score = quality.overall_score()
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be decent quality

    def test_inconsistent_profile_lower_score(self, quality_tracker):
        # Income doesn't match segment (mass_market with $500K income)
        profile = CustomerProfile(
            profile_id="QA-002",
            age=30,
            province="ON",
            fsa="M5V",
            segment="mass_market",
            annual_income=500000.0,  # Way too high for mass_market
            household_income=200000.0,  # Less than individual — inconsistent
            credit_score=400,
            products_held=["chequing"],
            total_deposits=1000.0,
            total_credit_outstanding=0.0,
            digital_adoption="digital_first",
            primary_channel="mobile",
            tenure_years=5.0,
            products_per_household=1,
        )
        quality = quality_tracker.assess_profile(profile)
        # Consistency should be lower due to income/segment mismatch
        assert quality.consistency < 1.0

    def test_transaction_quality(self, quality_tracker):
        txn = Transaction(
            transaction_id="TXN-QA-001",
            profile_id="QA-001",
            timestamp="2026-02-05T14:30:00",
            transaction_type="pos_purchase",
            amount=45.99,
            currency="CAD",
        )
        quality = quality_tracker.assess_transaction(txn)
        assert quality.overall_score() > 0.7

    def test_uniqueness_detection(self, quality_tracker):
        profile1 = CustomerProfile(
            profile_id="DUP-001",
            age=30,
            province="ON",
            fsa="M5V",
            segment="mass_market",
            annual_income=50000.0,
            household_income=80000.0,
            credit_score=700,
            products_held=["chequing"],
            total_deposits=10000.0,
            total_credit_outstanding=0.0,
            digital_adoption="hybrid",
            primary_channel="mobile",
            tenure_years=5.0,
            products_per_household=1,
        )
        # First assessment — unique
        q1 = quality_tracker.assess_profile(profile1)
        assert q1.uniqueness == 1.0

        # Second with same ID — duplicate
        q2 = quality_tracker.assess_profile(profile1)
        assert q2.uniqueness == 0.0
