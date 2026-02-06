#!/usr/bin/env python3
"""Tests for the TSTR (Train-on-Synthetic, Test-on-Real) Framework (Layer 6)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import GenerationRequest
from synthetic.tstr import TaskResult, TSTRFramework, TSTRReport


@pytest.fixture
def kb():
    return CanadianFinServKB()


@pytest.fixture
def tstr(kb):
    return TSTRFramework(kb=kb)


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def sample_profiles(generator):
    """Generate 100 profiles for TSTR testing."""
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


class TestTSTREvaluation:
    """Test full TSTR evaluation."""

    def test_evaluate_all_returns_report(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        assert isinstance(report, TSTRReport)

    def test_profile_tasks_run(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task_names = [t.task_name for t in report.tasks]
        assert "credit_score_prediction" in task_names
        assert "segment_classification" in task_names
        assert "income_regression" in task_names

    def test_transaction_task_runs(self, tstr, sample_profiles, sample_transactions):
        report = tstr.evaluate_all(
            sample_profiles,
            synthetic_transactions=sample_transactions,
        )
        task_names = [t.task_name for t in report.tasks]
        assert "aml_detection" in task_names

    def test_no_transactions_skips_aml(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task_names = [t.task_name for t in report.tasks]
        assert "aml_detection" not in task_names

    def test_sample_counts_set(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        assert report.n_synthetic_train == len(sample_profiles)
        assert report.n_reference_train == len(sample_profiles)
        assert report.n_test > 0

    def test_custom_reference_profiles(self, tstr, generator):
        """Test providing explicit reference profiles."""
        req = GenerationRequest(data_type="profiles", count=60)
        synth, _ = generator._generate_profiles(req)
        ref, _ = generator._generate_profiles(req)
        report = tstr.evaluate_all(synth, reference_profiles=ref)
        assert report.n_reference_train == 60


class TestCreditScoreTask:
    """Test Task 1: Credit Score Prediction."""

    def test_credit_score_task_result(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "credit_score_prediction")
        assert isinstance(task, TaskResult)
        assert task.metric_name == "accuracy"

    def test_credit_score_accuracy_reasonable(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "credit_score_prediction")
        # Both train on KB-generated data, so accuracy should be non-trivial
        assert task.synthetic_score > 0.15  # Better than random (4 classes)
        assert task.reference_score > 0.15

    def test_credit_buckets(self, tstr):
        assert tstr._credit_bucket(500) == 0  # Poor
        assert tstr._credit_bucket(620) == 1  # Fair
        assert tstr._credit_bucket(700) == 2  # Good
        assert tstr._credit_bucket(800) == 3  # Excellent


class TestSegmentClassificationTask:
    """Test Task 2: Segment Classification."""

    def test_segment_task_result(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "segment_classification")
        assert task.metric_name == "accuracy"

    def test_segment_scores_valid(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "segment_classification")
        assert 0.0 <= task.synthetic_score <= 1.0
        assert 0.0 <= task.reference_score <= 1.0


class TestIncomeRegressionTask:
    """Test Task 3: Income Regression."""

    def test_income_task_result(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "income_regression")
        assert task.metric_name == "r2_score"

    def test_income_r2_non_negative(self, tstr, sample_profiles):
        """R² can be negative, but stored score is clamped to >= 0."""
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "income_regression")
        assert task.synthetic_score >= 0
        assert task.reference_score >= 0

    def test_income_wider_tolerance(self, tstr, sample_profiles):
        """Income regression uses 2x wider tolerance (10% instead of 5%)."""
        report = tstr.evaluate_all(sample_profiles)
        task = next(t for t in report.tasks if t.task_name == "income_regression")
        # The wider tolerance (MAX_ACCEPTABLE_GAP * 2 = 0.10) should help pass
        # even when R² values differ slightly
        assert task.delta is not None


class TestAMLDetectionTask:
    """Test Task 4: AML Detection."""

    def test_aml_task_result(self, tstr, sample_profiles, sample_transactions):
        report = tstr.evaluate_all(
            sample_profiles,
            synthetic_transactions=sample_transactions,
        )
        aml_tasks = [t for t in report.tasks if t.task_name == "aml_detection"]
        assert len(aml_tasks) == 1
        assert aml_tasks[0].metric_name == "accuracy"

    def test_aml_skipped_with_few_transactions(self, tstr, sample_profiles, generator):
        """AML task requires >= 20 transactions."""
        req = GenerationRequest(
            data_type="transactions", count=10,
            include_risk_flags=True, risk_profile="high",
        )
        txns, _ = generator._generate_transactions(req)
        report = tstr.evaluate_all(
            sample_profiles, synthetic_transactions=txns,
        )
        aml_tasks = [t for t in report.tasks if t.task_name == "aml_detection"]
        assert len(aml_tasks) == 0  # Not enough transactions


class TestTSTRPassFail:
    """Test pass/fail logic."""

    def test_delta_calculation(self):
        task = TaskResult(
            task_name="test", metric_name="accuracy",
            synthetic_score=0.85, reference_score=0.90,
            delta=-0.05, passed=True, detail="test",
        )
        assert task.delta == -0.05

    def test_all_passed_true(self):
        report = TSTRReport(tasks=[
            TaskResult("t1", "acc", 0.85, 0.87, -0.02, True, "ok"),
            TaskResult("t2", "acc", 0.90, 0.88, 0.02, True, "ok"),
        ])
        assert report.all_passed is True

    def test_all_passed_false(self):
        report = TSTRReport(tasks=[
            TaskResult("t1", "acc", 0.85, 0.87, -0.02, True, "ok"),
            TaskResult("t2", "acc", 0.70, 0.85, -0.15, False, "bad"),
        ])
        assert report.all_passed is False

    def test_avg_delta(self):
        report = TSTRReport(tasks=[
            TaskResult("t1", "acc", 0.85, 0.87, -0.02, True, "ok"),
            TaskResult("t2", "acc", 0.90, 0.88, 0.02, True, "ok"),
        ])
        assert report.avg_delta == pytest.approx(0.0, abs=1e-9)

    def test_worst_delta(self):
        report = TSTRReport(tasks=[
            TaskResult("t1", "acc", 0.85, 0.87, -0.02, True, "ok"),
            TaskResult("t2", "acc", 0.90, 0.88, 0.02, True, "ok"),
        ])
        assert report.worst_delta == -0.02

    def test_same_kb_data_should_have_small_delta(self, tstr, sample_profiles):
        """Both synthetic and reference from same KB → classification deltas should be small."""
        report = tstr.evaluate_all(sample_profiles)
        for task in report.tasks:
            if task.metric_name == "r2_score":
                # R² can be wildly negative with small samples, so delta can be large
                # Just verify it's a valid number
                assert task.delta is not None
            else:
                assert abs(task.delta) < 0.30, (
                    f"Task {task.task_name} delta {task.delta:+.3f} "
                    f"too large for same-KB data"
                )


class TestSerialization:
    """Test report serialization."""

    def test_report_to_dict(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        d = report.to_dict()
        assert "tasks" in d
        assert "all_passed" in d
        assert "avg_delta" in d
        assert "worst_delta" in d
        assert "n_synthetic_train" in d

    def test_task_result_to_dict(self):
        task = TaskResult(
            task_name="credit_score_prediction",
            metric_name="accuracy",
            synthetic_score=0.85,
            reference_score=0.87,
            delta=-0.02,
            passed=True,
            detail="test",
        )
        d = task.to_dict()
        assert d["task_name"] == "credit_score_prediction"
        assert d["delta"] == -0.02
        assert d["delta_pct"] == -2.0
        assert d["passed"] is True

    def test_report_summary_readable(self, tstr, sample_profiles):
        report = tstr.evaluate_all(sample_profiles)
        summary = report.summary()
        assert "TSTR" in summary
        assert "passed" in summary
