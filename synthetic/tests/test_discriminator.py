#!/usr/bin/env python3
"""Tests for the Discriminator Feedback Engine (Layer 5)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.discriminator import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    Discriminator,
    DiscriminatorReport,
    FeatureImportance,
)
from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import GenerationRequest


@pytest.fixture
def kb():
    return CanadianFinServKB()


@pytest.fixture
def discriminator(kb):
    return Discriminator(kb=kb)


@pytest.fixture
def generator():
    return SyntheticGenerator()


@pytest.fixture
def sample_profiles(generator):
    """Generate 100 profiles for discriminator testing."""
    request = GenerationRequest(data_type="profiles", count=100)
    profiles, _ = generator._generate_profiles(request)
    return profiles


class TestDiscriminatorTraining:
    """Test discriminator training and evaluation."""

    def test_train_and_evaluate_returns_report(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert isinstance(report, DiscriminatorReport)

    def test_auc_in_valid_range(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert 0.0 <= report.auc_roc <= 1.0

    def test_accuracy_in_valid_range(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert 0.0 <= report.accuracy <= 1.0

    def test_precision_recall_valid(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert 0.0 <= report.precision <= 1.0
        assert 0.0 <= report.recall <= 1.0

    def test_uses_correct_sample_counts(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert report.n_synthetic == len(sample_profiles)
        assert report.n_reference == len(sample_profiles)

    def test_custom_folds(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles, n_folds=3)
        assert report.n_folds >= 2  # May be adjusted if too few samples

    def test_with_custom_reference(self, discriminator, generator):
        """Test providing explicit reference profiles."""
        req = GenerationRequest(data_type="profiles", count=50)
        synth, _ = generator._generate_profiles(req)
        ref, _ = generator._generate_profiles(req)
        report = discriminator.train_and_evaluate(synth, reference_profiles=ref)
        assert isinstance(report, DiscriminatorReport)
        assert report.n_reference == 50


class TestAUCInterpretation:
    """Test AUC-based pass/fail logic."""

    def test_low_auc_passes(self):
        """AUC < 0.65 means synthetic is near-indistinguishable."""
        report = DiscriminatorReport(
            auc_roc=0.55,
            accuracy=0.52,
            precision=0.50,
            recall=0.50,
            n_synthetic=100,
            n_reference=100,
            n_folds=5,
        )
        assert report.passed is True

    def test_high_auc_fails(self):
        """AUC >= 0.65 means synthetic is distinguishable."""
        report = DiscriminatorReport(
            auc_roc=0.80,
            accuracy=0.75,
            precision=0.70,
            recall=0.70,
            n_synthetic=100,
            n_reference=100,
            n_folds=5,
        )
        assert report.passed is False

    def test_boundary_auc(self):
        """AUC = 0.65 exactly should fail (not < 0.65)."""
        report = DiscriminatorReport(
            auc_roc=0.65,
            accuracy=0.60,
            precision=0.55,
            recall=0.55,
            n_synthetic=100,
            n_reference=100,
            n_folds=5,
        )
        assert report.passed is False

    def test_generated_data_should_be_low_auc(self, discriminator, sample_profiles):
        """Synthetic from same KB should be hard to distinguish from reference."""
        report = discriminator.train_and_evaluate(sample_profiles)
        # Both are sampled from same KB distributions, so AUC should be low
        # Allow up to 0.75 since random forests can find minor distributional artifacts
        assert report.auc_roc < 0.75, (
            f"AUC {report.auc_roc:.3f} too high — synthetic "
            f"is easily distinguishable from reference"
        )


class TestFeatureEngineering:
    """Test profile-to-feature conversion."""

    def test_feature_matrix_shape(self, discriminator, sample_profiles):
        X = discriminator._profiles_to_features(sample_profiles)
        n_numeric = len(FEATURE_COLUMNS)
        n_categorical = sum(len(cats) for cats in CATEGORICAL_FEATURES.values())
        expected_cols = n_numeric + n_categorical
        assert X.shape == (len(sample_profiles), expected_cols)

    def test_feature_names_populated(self, discriminator, sample_profiles):
        discriminator._profiles_to_features(sample_profiles)
        assert len(discriminator._feature_names) > 0
        assert "age" in discriminator._feature_names
        assert "province_ON" in discriminator._feature_names
        assert "segment_mass_market" in discriminator._feature_names

    def test_one_hot_encoding(self, discriminator, sample_profiles):
        X = discriminator._profiles_to_features(sample_profiles)
        # Province columns should be binary (0 or 1)
        n_numeric = len(FEATURE_COLUMNS)
        province_cols = X[:, n_numeric : n_numeric + len(CATEGORICAL_FEATURES["province"])]
        assert np.all((province_cols == 0.0) | (province_cols == 1.0))
        # Each profile should have exactly 1 province
        assert np.all(province_cols.sum(axis=1) == 1.0)

    def test_numeric_features_reasonable(self, discriminator, sample_profiles):
        X = discriminator._profiles_to_features(sample_profiles)
        ages = X[:, 0]  # age column
        assert np.all(ages >= 18)
        assert np.all(ages <= 100)


class TestSHAPFeedback:
    """Test SHAP-based feature importance extraction."""

    def test_feature_importances_populated(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert len(report.feature_importances) > 0

    def test_feature_importance_structure(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        for fi in report.feature_importances:
            assert isinstance(fi, FeatureImportance)
            assert fi.importance >= 0
            assert fi.direction in ("too_high", "too_low", "wrong_shape", "unknown")
            assert len(fi.detail) > 0

    def test_top_features_extracted(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        assert len(report.top_distinguishing_features) > 0
        assert len(report.top_distinguishing_features) <= 5

    def test_get_shap_feedback_shortcut(self, discriminator, sample_profiles):
        importances = discriminator.get_shap_feedback(sample_profiles)
        assert isinstance(importances, list)
        assert all(isinstance(fi, FeatureImportance) for fi in importances)


class TestSerialization:
    """Test report serialization."""

    def test_report_to_dict(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        d = report.to_dict()
        assert "auc_roc" in d
        assert "accuracy" in d
        assert "passed" in d
        assert "feature_importances" in d
        assert "top_distinguishing_features" in d

    def test_feature_importance_to_dict(self):
        fi = FeatureImportance(
            feature="age",
            importance=0.05,
            direction="too_high",
            detail="Synthetic mean (42.5) > reference (38.2)",
        )
        d = fi.to_dict()
        assert d["feature"] == "age"
        assert d["direction"] == "too_high"
        assert d["importance"] == 0.05

    def test_summary_readable(self, discriminator, sample_profiles):
        report = discriminator.train_and_evaluate(sample_profiles)
        summary = report.summary()
        assert "Discriminator" in summary
        assert "AUC=" in summary
