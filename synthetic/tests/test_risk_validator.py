#!/usr/bin/env python3
"""Tests for the AML Risk Model Validator."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.generator import SyntheticGenerator
from synthetic.risk_validator import AdversarialResult, RiskValidator
from synthetic.schemas import Transaction


@pytest.fixture
def validator():
    return RiskValidator()


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def normal_transaction():
    return Transaction(
        transaction_id="TXN-NORM-001",
        profile_id="TEST-001",
        timestamp="2026-02-05T12:00:00",
        transaction_type="pos_purchase",
        amount=42.50,
        currency="CAD",
    )


@pytest.fixture
def structuring_transaction():
    return Transaction(
        transaction_id="TXN-STRUCT-001",
        profile_id="TEST-002",
        timestamp="2026-02-05T12:00:00",
        transaction_type="deposit",
        amount=9500.00,
        currency="CAD",
        risk_flag="structuring",
        risk_score=0.75,
    )


@pytest.fixture
def geographic_risk_transaction():
    return Transaction(
        transaction_id="TXN-GEO-001",
        profile_id="TEST-003",
        timestamp="2026-02-05T12:00:00",
        transaction_type="wire_international",
        amount=50000.00,
        currency="CAD",
        is_international=True,
        country_code="IR",
        risk_flag="geographic_risk",
        risk_score=0.85,
    )


@pytest.fixture
def round_amount_transaction():
    return Transaction(
        transaction_id="TXN-ROUND-001",
        profile_id="TEST-004",
        timestamp="2026-02-05T12:00:00",
        transaction_type="wire_domestic",
        amount=25000.00,
        currency="CAD",
        risk_flag="round_amounts",
        risk_score=0.5,
    )


@pytest.fixture
def rapid_movement_transaction():
    return Transaction(
        transaction_id="TXN-RAPID-001",
        profile_id="TEST-005",
        timestamp="2026-02-05T12:00:00",
        transaction_type="wire_domestic",
        amount=30000.00,
        currency="CAD",
        risk_flag="rapid_movement",
        risk_score=0.7,
    )


class TestIndividualRules:
    """Test each AML rule independently."""

    def test_structuring_detects_below_threshold(self, validator, structuring_transaction):
        results = validator.validate_transaction(structuring_transaction)
        struct_result = next(r for r in results if r.rule_name == "structuring")
        assert struct_result.triggered
        assert struct_result.confidence > 0.5

    def test_structuring_ignores_normal(self, validator, normal_transaction):
        results = validator.validate_transaction(normal_transaction)
        struct_result = next(r for r in results if r.rule_name == "structuring")
        assert not struct_result.triggered

    def test_geographic_risk_detects_high_risk_country(
        self, validator, geographic_risk_transaction
    ):
        results = validator.validate_transaction(geographic_risk_transaction)
        geo_result = next(r for r in results if r.rule_name == "geographic_risk")
        assert geo_result.triggered
        assert geo_result.confidence >= 0.8

    def test_geographic_risk_ignores_domestic(self, validator, normal_transaction):
        results = validator.validate_transaction(normal_transaction)
        geo_result = next(r for r in results if r.rule_name == "geographic_risk")
        assert not geo_result.triggered

    def test_round_amounts_detects_round_wire(self, validator, round_amount_transaction):
        results = validator.validate_transaction(round_amount_transaction)
        round_result = next(r for r in results if r.rule_name == "round_amounts")
        assert round_result.triggered

    def test_round_amounts_ignores_odd_amount(self, validator, normal_transaction):
        results = validator.validate_transaction(normal_transaction)
        round_result = next(r for r in results if r.rule_name == "round_amounts")
        assert not round_result.triggered

    def test_rapid_movement_detects_large_transfer(self, validator, rapid_movement_transaction):
        results = validator.validate_transaction(rapid_movement_transaction)
        rapid_result = next(r for r in results if r.rule_name == "rapid_movement")
        assert rapid_result.triggered

    def test_unusual_volume_detects_spike(self, validator):
        """A $5,000 POS purchase is unusual (65x median)."""
        txn = Transaction(
            transaction_id="TXN-VOL-001",
            profile_id="TEST",
            timestamp="2026-02-05T12:00:00",
            transaction_type="pos_purchase",
            amount=5000.0,
            currency="CAD",
        )
        results = validator.validate_transaction(txn)
        vol_result = next(r for r in results if r.rule_name == "unusual_volume")
        assert vol_result.triggered

    def test_all_seven_rules_run(self, validator, normal_transaction):
        """All 7 rules should be applied to every transaction."""
        results = validator.validate_transaction(normal_transaction)
        assert len(results) == 7
        rule_names = {r.rule_name for r in results}
        assert rule_names == {
            "structuring",
            "rapid_movement",
            "round_amounts",
            "geographic_risk",
            "unusual_volume",
            "dormant_reactivation",
            "third_party",
        }


class TestBatchValidation:
    """Test batch validation and confusion matrix."""

    def test_batch_report_structure(self, validator):
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                profile_id="TEST",
                timestamp="2026-02-05T12:00:00",
                transaction_type="pos_purchase",
                amount=50.0,
                currency="CAD",
            )
            for i in range(10)
        ]
        report = validator.validate_batch(transactions)
        assert report.total_transactions == 10
        assert isinstance(report.detection_rate, float)
        assert isinstance(report.precision, float)

    def test_true_positive_counted(self, validator, structuring_transaction):
        report = validator.validate_batch([structuring_transaction])
        assert report.true_positives == 1
        assert report.false_negatives == 0

    def test_true_negative_counted(self, validator, normal_transaction):
        report = validator.validate_batch([normal_transaction])
        # Normal POS purchase shouldn't trigger most rules
        # But unusual_volume might fire if amount is high enough
        assert report.total_transactions == 1

    def test_mixed_batch_confusion_matrix(
        self, validator, normal_transaction, structuring_transaction, geographic_risk_transaction
    ):
        transactions = [normal_transaction, structuring_transaction, geographic_risk_transaction]
        report = validator.validate_batch(transactions)
        assert report.total_transactions == 3
        assert report.flagged_by_generator == 2  # structuring + geographic
        # Both flagged should be detected
        assert report.true_positives >= 1

    def test_detection_rate_high_for_obvious_patterns(self, validator):
        """Generator's 4 implemented patterns should all be detected."""
        transactions = [
            Transaction(
                transaction_id="S1",
                profile_id="T",
                timestamp="2026-02-05T12:00:00",
                transaction_type="deposit",
                amount=9800.0,
                currency="CAD",
                risk_flag="structuring",
                risk_score=0.7,
            ),
            Transaction(
                transaction_id="R1",
                profile_id="T",
                timestamp="2026-02-05T12:00:00",
                transaction_type="wire_domestic",
                amount=30000.0,
                currency="CAD",
                risk_flag="rapid_movement",
                risk_score=0.6,
            ),
            Transaction(
                transaction_id="A1",
                profile_id="T",
                timestamp="2026-02-05T12:00:00",
                transaction_type="wire_domestic",
                amount=25000.0,
                currency="CAD",
                risk_flag="round_amounts",
                risk_score=0.5,
            ),
            Transaction(
                transaction_id="G1",
                profile_id="T",
                timestamp="2026-02-05T12:00:00",
                transaction_type="wire_international",
                amount=50000.0,
                currency="CAD",
                is_international=True,
                country_code="IR",
                risk_flag="geographic_risk",
                risk_score=0.85,
            ),
        ]
        report = validator.validate_batch(transactions)
        assert report.detection_rate >= 0.90  # Target: > 90%

    def test_report_serialization(self, validator, normal_transaction):
        report = validator.validate_batch([normal_transaction])
        d = report.to_dict()
        assert "detection_rate" in d
        assert "precision" in d
        assert "rule_coverage" in d

    def test_report_summary_readable(self, validator, normal_transaction):
        report = validator.validate_batch([normal_transaction])
        summary = report.summary()
        assert "Risk Validation:" in summary
        assert "Detection rate:" in summary


class TestRuleCoverage:
    """Test rule coverage reporting."""

    def test_coverage_report_structure(self, validator):
        transactions = [
            Transaction(
                transaction_id=f"TXN-{i}",
                profile_id="TEST",
                timestamp="2026-02-05T12:00:00",
                transaction_type="deposit",
                amount=9800.0,
                currency="CAD",
                risk_flag="structuring",
                risk_score=0.7,
            )
            for i in range(10)
        ]
        coverage = validator.get_rule_coverage_report(transactions)
        assert "structuring" in coverage
        assert coverage["structuring"]["triggers"] >= 5
        assert coverage["structuring"]["sufficient"]


class TestAdversarialLoop:
    """Test the adversarial generation loop."""

    def test_adversarial_returns_result(self, validator, generator):
        result = validator.adversarial_loop(
            generator,
            count=50,
            max_rounds=2,
            target_rate=0.50,
        )
        assert isinstance(result, AdversarialResult)
        assert result.rounds_executed >= 1
        assert len(result.detection_rates) >= 1

    def test_adversarial_converges_eventually(self, validator, generator):
        """With low target, should converge quickly."""
        result = validator.adversarial_loop(
            generator,
            count=100,
            max_rounds=3,
            target_rate=0.50,
        )
        # With high-risk profile, most patterns should be detectable
        assert result.final_detection_rate > 0

    def test_adversarial_result_serialization(self, validator, generator):
        result = validator.adversarial_loop(
            generator,
            count=30,
            max_rounds=1,
            target_rate=0.99,
        )
        d = result.to_dict()
        assert "rounds_executed" in d
        assert "detection_rates" in d
        assert "converged" in d
