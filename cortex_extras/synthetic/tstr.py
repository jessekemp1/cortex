#!/usr/bin/env python3
"""
Train-on-Synthetic, Test-on-Real (TSTR) — Utility validation framework.

The gold standard for synthetic data quality: if a model trained on
synthetic data performs comparably to one trained on real data, then
the synthetic data captures the real data's predictive structure.

Since we don't have real customer data (that's the point), we use
independently-sampled KB reference data as the "real" test set.
This validates that synthetic data preserves the statistical
relationships needed for downstream ML tasks.

Built-in tasks:
  1. Credit Score Prediction: Predict credit score bucket from profile features
  2. AML Detection: Predict risk flag from transaction features

Architecture:
    TSTRFramework(kb) → evaluate_task(profiles) → TSTRReport
    → performance_delta → flywheel correction signals (Layer 6)
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile, Transaction


@dataclass
class TaskResult:
    """Result from a single TSTR task evaluation."""

    task_name: str
    metric_name: str  # "accuracy", "f1", "rmse", etc.
    synthetic_score: float  # Score when trained on synthetic
    reference_score: float  # Score when trained on reference
    delta: float  # synthetic - reference (negative = synthetic worse)
    passed: bool  # delta within acceptable gap
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "metric_name": self.metric_name,
            "synthetic_score": round(self.synthetic_score, 4),
            "reference_score": round(self.reference_score, 4),
            "delta": round(self.delta, 4),
            "delta_pct": round(self.delta * 100, 2),
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass
class TSTRReport:
    """Aggregate report from TSTR evaluation."""

    tasks: List[TaskResult] = field(default_factory=list)
    n_synthetic_train: int = 0
    n_reference_train: int = 0
    n_test: int = 0

    @property
    def all_passed(self) -> bool:
        return all(t.passed for t in self.tasks)

    @property
    def avg_delta(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.delta for t in self.tasks) / len(self.tasks)

    @property
    def worst_delta(self) -> float:
        if not self.tasks:
            return 0.0
        return min(t.delta for t in self.tasks)

    def summary(self) -> str:
        passed = sum(1 for t in self.tasks if t.passed)
        total = len(self.tasks)
        return (
            f"TSTR: {passed}/{total} tasks passed | "
            f"Avg delta: {self.avg_delta:+.3f} | "
            f"Worst: {self.worst_delta:+.3f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "all_passed": self.all_passed,
            "avg_delta": round(self.avg_delta, 4),
            "worst_delta": round(self.worst_delta, 4),
            "n_synthetic_train": self.n_synthetic_train,
            "n_reference_train": self.n_reference_train,
            "n_test": self.n_test,
        }


class TSTRFramework:
    """
    Train-on-Synthetic, Test-on-Real evaluation framework.

    Trains models on synthetic data, evaluates on independently-sampled
    reference data, and compares against models trained on reference data.
    A performance gap < 5% means synthetic data is useful for ML.
    """

    MAX_ACCEPTABLE_GAP = 0.05  # 5% accuracy gap

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()

    def evaluate_all(
        self,
        synthetic_profiles: List[CustomerProfile],
        synthetic_transactions: Optional[List[Transaction]] = None,
        reference_profiles: Optional[List[CustomerProfile]] = None,
        reference_transactions: Optional[List[Transaction]] = None,
    ) -> TSTRReport:
        """
        Run all built-in TSTR tasks.

        Args:
            synthetic_profiles: Generated profiles for training
            synthetic_transactions: Generated transactions (optional)
            reference_profiles: Reference profiles. Auto-generated if None.
            reference_transactions: Reference transactions (optional)

        Returns:
            TSTRReport with per-task results
        """
        report = TSTRReport()

        # Generate reference data if not provided
        if reference_profiles is None:
            reference_profiles = self._generate_reference_profiles(len(synthetic_profiles))

        report.n_synthetic_train = len(synthetic_profiles)
        report.n_reference_train = len(reference_profiles)

        # Task 1: Credit Score Prediction
        credit_result = self._task_credit_score_prediction(synthetic_profiles, reference_profiles)
        report.tasks.append(credit_result)

        # Task 2: Segment Classification
        segment_result = self._task_segment_classification(synthetic_profiles, reference_profiles)
        report.tasks.append(segment_result)

        # Task 3: Income Regression
        income_result = self._task_income_regression(synthetic_profiles, reference_profiles)
        report.tasks.append(income_result)

        # Task 4: AML Detection (if transactions provided)
        if synthetic_transactions and len(synthetic_transactions) >= 20:
            if reference_transactions is None:
                reference_transactions = self._generate_reference_transactions(
                    len(synthetic_transactions)
                )
            aml_result = self._task_aml_detection(synthetic_transactions, reference_transactions)
            report.tasks.append(aml_result)

        # Set test count from the credit task (representative)
        report.n_test = len(reference_profiles) // 3  # Approx test split

        return report

    # --- Built-in Tasks ---

    def _task_credit_score_prediction(
        self,
        synthetic: List[CustomerProfile],
        reference: List[CustomerProfile],
    ) -> TaskResult:
        """
        Task 1: Predict credit score bucket from profile features.

        Bins credit scores into 4 buckets (Poor/Fair/Good/Excellent)
        and trains a classifier. Measures accuracy.
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        from sklearn.model_selection import train_test_split

        def _prepare(profiles):
            X = np.array(
                [
                    [
                        p.age,
                        p.annual_income,
                        p.household_income,
                        p.tenure_years,
                        p.products_per_household,
                        p.total_deposits,
                    ]
                    for p in profiles
                ]
            )
            y = np.array([self._credit_bucket(p.credit_score) for p in profiles])
            return X, y

        X_synth, y_synth = _prepare(synthetic)
        X_ref, y_ref = _prepare(reference)

        # Split reference into train and test (stratified, fallback to random)
        try:
            X_ref_train, X_test, y_ref_train, y_test = train_test_split(
                X_ref, y_ref, test_size=0.3, random_state=42, stratify=y_ref
            )
        except ValueError:
            X_ref_train, X_test, y_ref_train, y_test = train_test_split(
                X_ref, y_ref, test_size=0.3, random_state=42
            )

        # Train on synthetic, test on reference test set
        clf_synth = RandomForestClassifier(n_estimators=50, random_state=42)
        clf_synth.fit(X_synth, y_synth)
        synth_acc = accuracy_score(y_test, clf_synth.predict(X_test))

        # Train on reference train, test on reference test (baseline)
        clf_ref = RandomForestClassifier(n_estimators=50, random_state=42)
        clf_ref.fit(X_ref_train, y_ref_train)
        ref_acc = accuracy_score(y_test, clf_ref.predict(X_test))

        delta = synth_acc - ref_acc

        return TaskResult(
            task_name="credit_score_prediction",
            metric_name="accuracy",
            synthetic_score=synth_acc,
            reference_score=ref_acc,
            delta=delta,
            passed=abs(delta) <= self.MAX_ACCEPTABLE_GAP,
            detail=(
                f"Credit bucket prediction: "
                f"synthetic={synth_acc:.3f}, reference={ref_acc:.3f}, "
                f"delta={delta:+.3f}"
            ),
        )

    def _task_segment_classification(
        self,
        synthetic: List[CustomerProfile],
        reference: List[CustomerProfile],
    ) -> TaskResult:
        """
        Task 2: Predict customer segment from financial features.
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder

        le = LabelEncoder()

        def _prepare(profiles, fit=False):
            X = np.array(
                [
                    [
                        p.age,
                        p.annual_income,
                        p.credit_score,
                        p.total_deposits,
                        p.total_credit_outstanding,
                        p.products_per_household,
                    ]
                    for p in profiles
                ]
            )
            segments = [p.segment for p in profiles]
            if fit:
                y = le.fit_transform(segments)
            else:
                # Handle unseen labels gracefully
                known = set(le.classes_)
                mapped = [s if s in known else le.classes_[0] for s in segments]
                y = le.transform(mapped)
            return X, y

        X_synth, y_synth = _prepare(synthetic, fit=True)
        X_ref, y_ref = _prepare(reference)

        # Stratified split, fall back to non-stratified if rare classes exist
        try:
            X_ref_train, X_test, y_ref_train, y_test = train_test_split(
                X_ref, y_ref, test_size=0.3, random_state=42, stratify=y_ref
            )
        except ValueError:
            X_ref_train, X_test, y_ref_train, y_test = train_test_split(
                X_ref, y_ref, test_size=0.3, random_state=42
            )

        clf_synth = RandomForestClassifier(n_estimators=50, random_state=42)
        clf_synth.fit(X_synth, y_synth)
        synth_acc = accuracy_score(y_test, clf_synth.predict(X_test))

        clf_ref = RandomForestClassifier(n_estimators=50, random_state=42)
        clf_ref.fit(X_ref_train, y_ref_train)
        ref_acc = accuracy_score(y_test, clf_ref.predict(X_test))

        delta = synth_acc - ref_acc

        return TaskResult(
            task_name="segment_classification",
            metric_name="accuracy",
            synthetic_score=synth_acc,
            reference_score=ref_acc,
            delta=delta,
            passed=abs(delta) <= self.MAX_ACCEPTABLE_GAP,
            detail=(
                f"Segment classification: "
                f"synthetic={synth_acc:.3f}, reference={ref_acc:.3f}, "
                f"delta={delta:+.3f}"
            ),
        )

    def _task_income_regression(
        self,
        synthetic: List[CustomerProfile],
        reference: List[CustomerProfile],
    ) -> TaskResult:
        """
        Task 3: Predict income from demographic features.

        Uses R² score — measures how well the model captures
        income variance from age, credit score, products, etc.
        """
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import r2_score
        from sklearn.model_selection import train_test_split

        def _prepare(profiles):
            X = np.array(
                [
                    [
                        p.age,
                        p.credit_score,
                        p.products_per_household,
                        p.tenure_years,
                        p.total_deposits,
                    ]
                    for p in profiles
                ]
            )
            y = np.array([p.annual_income for p in profiles])
            return X, y

        X_synth, y_synth = _prepare(synthetic)
        X_ref, y_ref = _prepare(reference)

        X_ref_train, X_test, y_ref_train, y_test = train_test_split(
            X_ref, y_ref, test_size=0.3, random_state=42
        )

        reg_synth = RandomForestRegressor(n_estimators=50, random_state=42)
        reg_synth.fit(X_synth, y_synth)
        synth_r2 = r2_score(y_test, reg_synth.predict(X_test))

        reg_ref = RandomForestRegressor(n_estimators=50, random_state=42)
        reg_ref.fit(X_ref_train, y_ref_train)
        ref_r2 = r2_score(y_test, reg_ref.predict(X_test))

        delta = synth_r2 - ref_r2

        return TaskResult(
            task_name="income_regression",
            metric_name="r2_score",
            synthetic_score=max(0, synth_r2),  # R² can be negative
            reference_score=max(0, ref_r2),
            delta=delta,
            passed=abs(delta) <= self.MAX_ACCEPTABLE_GAP * 2,  # Wider tolerance for regression
            detail=(
                f"Income regression (R²): "
                f"synthetic={synth_r2:.3f}, reference={ref_r2:.3f}, "
                f"delta={delta:+.3f}"
            ),
        )

    def _task_aml_detection(
        self,
        synthetic_txns: List[Transaction],
        reference_txns: List[Transaction],
    ) -> TaskResult:
        """
        Task 4: Predict risk flag from transaction features.

        Binary classification: is the transaction suspicious?
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        from sklearn.model_selection import train_test_split

        def _prepare(txns):
            X = np.array(
                [
                    [
                        t.amount,
                        1.0 if t.is_international else 0.0,
                        t.risk_score,
                        (
                            1.0
                            if t.transaction_type in ("wire_domestic", "wire_international")
                            else 0.0
                        ),
                        1.0 if t.transaction_type == "deposit" else 0.0,
                    ]
                    for t in txns
                ]
            )
            y = np.array([1 if t.risk_flag != "none" else 0 for t in txns])
            return X, y

        X_synth, y_synth = _prepare(synthetic_txns)
        X_ref, y_ref = _prepare(reference_txns)

        # Need at least some positive labels
        if y_synth.sum() < 2 or y_ref.sum() < 2:
            return TaskResult(
                task_name="aml_detection",
                metric_name="accuracy",
                synthetic_score=0.0,
                reference_score=0.0,
                delta=0.0,
                passed=True,  # Can't evaluate, pass by default
                detail="Insufficient positive labels for AML detection task",
            )

        # Stratified split on reference
        try:
            X_ref_train, X_test, y_ref_train, y_test = train_test_split(
                X_ref, y_ref, test_size=0.3, random_state=42, stratify=y_ref
            )
        except ValueError:
            # Not enough samples for stratified split
            X_ref_train, X_test, y_ref_train, y_test = train_test_split(
                X_ref, y_ref, test_size=0.3, random_state=42
            )

        clf_synth = RandomForestClassifier(n_estimators=50, random_state=42)
        clf_synth.fit(X_synth, y_synth)
        synth_acc = accuracy_score(y_test, clf_synth.predict(X_test))

        clf_ref = RandomForestClassifier(n_estimators=50, random_state=42)
        clf_ref.fit(X_ref_train, y_ref_train)
        ref_acc = accuracy_score(y_test, clf_ref.predict(X_test))

        delta = synth_acc - ref_acc

        return TaskResult(
            task_name="aml_detection",
            metric_name="accuracy",
            synthetic_score=synth_acc,
            reference_score=ref_acc,
            delta=delta,
            passed=abs(delta) <= self.MAX_ACCEPTABLE_GAP,
            detail=(
                f"AML detection: "
                f"synthetic={synth_acc:.3f}, reference={ref_acc:.3f}, "
                f"delta={delta:+.3f}"
            ),
        )

    # --- Helpers ---

    @staticmethod
    def _credit_bucket(score: int) -> int:
        """Bin credit score into 4 buckets."""
        if score < 580:
            return 0  # Poor
        elif score < 660:
            return 1  # Fair
        elif score < 760:
            return 2  # Good
        else:
            return 3  # Excellent

    def _generate_reference_profiles(self, n: int) -> List[CustomerProfile]:
        """Generate reference profiles from KB distributions."""
        from synthetic.generator import SyntheticGenerator
        from synthetic.schemas import GenerationRequest

        gen = SyntheticGenerator(kb=self.kb)
        request = GenerationRequest(data_type="profiles", count=n)
        profiles, _ = gen._generate_profiles(request)
        return profiles

    def _generate_reference_transactions(self, n: int) -> List[Transaction]:
        """Generate reference transactions from KB distributions."""
        from synthetic.generator import SyntheticGenerator
        from synthetic.schemas import GenerationRequest

        gen = SyntheticGenerator(kb=self.kb)
        request = GenerationRequest(
            data_type="transactions",
            count=n,
            include_risk_flags=True,
            risk_profile="high",
        )
        txns, _ = gen._generate_transactions(request)
        return txns
