#!/usr/bin/env python3
"""
Discriminator Feedback Engine — Can a classifier tell synthetic from reference?

Trains an XGBoost binary classifier:
  - Class 0: Reference data (independently sampled from KB distributions)
  - Class 1: Generated synthetic data

If AUC-ROC < 0.65, the generator faithfully reproduces KB distributions
and the synthetic data is near-indistinguishable from reference samples.

SHAP values identify which features make synthetic data distinguishable
and in which direction, providing targeted feedback for the flywheel.

Architecture:
    Discriminator(kb) → train_and_evaluate(profiles) → DiscriminatorReport
    → shap_feedback → flywheel correction signals (Layer 5)
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile

# Lazy imports for heavy deps
_xgboost = None
_shap = None


def _get_xgboost():
    global _xgboost
    if _xgboost is None:
        import xgboost

        _xgboost = xgboost
    return _xgboost


def _get_shap():
    global _shap
    if _shap is None:
        import shap

        _shap = shap
    return _shap


# Feature columns used for discrimination
FEATURE_COLUMNS = [
    "age",
    "annual_income",
    "household_income",
    "credit_score",
    "total_deposits",
    "total_credit_outstanding",
    "tenure_years",
    "products_per_household",
]

# Categorical features encoded as numeric
CATEGORICAL_FEATURES = {
    "province": ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"],
    "segment": [
        "mass_market",
        "mass_affluent",
        "affluent",
        "high_net_worth",
        "ultra_hnw",
        "small_business",
        "commercial",
        "new_to_canada",
    ],
    "digital_adoption": ["digital_first", "hybrid", "branch_preferred"],
    "primary_channel": ["mobile", "online", "branch", "telephone"],
}


@dataclass
class FeatureImportance:
    """SHAP-based feature importance with direction."""

    feature: str
    importance: float  # Mean absolute SHAP value
    direction: str  # "too_high", "too_low", or "wrong_shape"
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "importance": round(self.importance, 6),
            "direction": self.direction,
            "detail": self.detail,
        }


@dataclass
class DiscriminatorReport:
    """Report from discriminator training and evaluation."""

    auc_roc: float
    accuracy: float
    precision: float
    recall: float
    n_synthetic: int
    n_reference: int
    n_folds: int
    feature_importances: List[FeatureImportance] = field(default_factory=list)
    top_distinguishing_features: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Synthetic is near-indistinguishable if AUC < 0.65."""
        return self.auc_roc < 0.65

    def summary(self) -> str:
        status = "PASS (indistinguishable)" if self.passed else "FAIL (distinguishable)"
        return (
            f"Discriminator: AUC={self.auc_roc:.3f} {status} | "
            f"Acc={self.accuracy:.3f} | "
            f"Top features: {', '.join(self.top_distinguishing_features[:3])}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auc_roc": round(self.auc_roc, 4),
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "passed": self.passed,
            "n_synthetic": self.n_synthetic,
            "n_reference": self.n_reference,
            "n_folds": self.n_folds,
            "feature_importances": [fi.to_dict() for fi in self.feature_importances],
            "top_distinguishing_features": self.top_distinguishing_features,
        }


class Discriminator:
    """
    XGBoost-based discriminator for synthetic data quality assessment.

    Trains a classifier to distinguish synthetic profiles from
    KB-sampled reference profiles. Low AUC = good synthetic data.
    SHAP values provide per-feature directional feedback.
    """

    TARGET_AUC = 0.65  # Below this = synthetic is near-indistinguishable
    N_FOLDS = 5

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()
        self._feature_names: List[str] = []

    def train_and_evaluate(
        self,
        synthetic_profiles: List[CustomerProfile],
        n_folds: int = 5,
        reference_profiles: Optional[List[CustomerProfile]] = None,
    ) -> DiscriminatorReport:
        """
        Train discriminator and evaluate synthetic data quality.

        Args:
            synthetic_profiles: Generated profiles to evaluate
            n_folds: Number of cross-validation folds
            reference_profiles: Optional reference profiles. If None,
                generates from KB distributions.

        Returns:
            DiscriminatorReport with AUC, accuracy, and SHAP feedback
        """
        xgb = _get_xgboost()
        from sklearn.metrics import (
            accuracy_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from sklearn.model_selection import StratifiedKFold

        # Generate reference data if not provided
        if reference_profiles is None:
            reference_profiles = self._generate_reference(len(synthetic_profiles))

        # Convert to feature matrices
        X_synth = self._profiles_to_features(synthetic_profiles)
        X_ref = self._profiles_to_features(reference_profiles)

        # Labels: 0 = reference, 1 = synthetic
        X = np.vstack([X_ref, X_synth])
        y = np.concatenate([np.zeros(len(X_ref)), np.ones(len(X_synth))])

        # Stratified k-fold cross-validation
        skf = StratifiedKFold(n_splits=min(n_folds, len(y) // 4), shuffle=True, random_state=42)

        auc_scores = []
        acc_scores = []
        prec_scores = []
        rec_scores = []
        all_shap_values = []

        for train_idx, test_idx in skf.split(X, y):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric="logloss",
                verbosity=0,
            )
            model.fit(X_train, y_train)

            y_pred_proba = model.predict_proba(X_test)[:, 1]
            y_pred = model.predict(X_test)

            auc_scores.append(roc_auc_score(y_test, y_pred_proba))
            acc_scores.append(accuracy_score(y_test, y_pred))
            prec_scores.append(precision_score(y_test, y_pred, zero_division=0))
            rec_scores.append(recall_score(y_test, y_pred, zero_division=0))

            # SHAP on last fold
            shap_values = self._compute_shap(model, X_test)
            if shap_values is not None:
                all_shap_values.append(shap_values)

        # Aggregate metrics
        mean_auc = float(np.mean(auc_scores))
        mean_acc = float(np.mean(acc_scores))
        mean_prec = float(np.mean(prec_scores))
        mean_rec = float(np.mean(rec_scores))

        # Extract feature importances from SHAP
        feature_importances = []
        top_features = []
        if all_shap_values:
            feature_importances, top_features = self._extract_shap_feedback(
                all_shap_values[-1], X_synth, X_ref
            )

        return DiscriminatorReport(
            auc_roc=mean_auc,
            accuracy=mean_acc,
            precision=mean_prec,
            recall=mean_rec,
            n_synthetic=len(synthetic_profiles),
            n_reference=len(reference_profiles),
            n_folds=min(n_folds, len(y) // 4),
            feature_importances=feature_importances,
            top_distinguishing_features=top_features,
        )

    def get_shap_feedback(
        self, synthetic_profiles: List[CustomerProfile]
    ) -> List[FeatureImportance]:
        """Get SHAP-based feedback without full report."""
        report = self.train_and_evaluate(synthetic_profiles)
        return report.feature_importances

    # --- Feature Engineering ---

    def _profiles_to_features(self, profiles: List[CustomerProfile]) -> np.ndarray:
        """Convert profiles to numeric feature matrix."""
        rows = []
        for p in profiles:
            row = [
                float(p.age),
                p.annual_income,
                p.household_income,
                float(p.credit_score),
                p.total_deposits,
                p.total_credit_outstanding,
                p.tenure_years,
                float(p.products_per_household),
            ]

            # One-hot encode categoricals
            for cat_name, categories in CATEGORICAL_FEATURES.items():
                value = getattr(p, cat_name, "")
                for cat_val in categories:
                    row.append(1.0 if value == cat_val else 0.0)

            rows.append(row)

        # Build feature names on first call
        if not self._feature_names:
            self._feature_names = list(FEATURE_COLUMNS)
            for cat_name, categories in CATEGORICAL_FEATURES.items():
                for cat_val in categories:
                    self._feature_names.append(f"{cat_name}_{cat_val}")

        return np.array(rows, dtype=float)

    def _generate_reference(self, n: int) -> List[CustomerProfile]:
        """Generate reference profiles from KB distributions."""
        from synthetic.generator import SyntheticGenerator
        from synthetic.schemas import GenerationRequest

        gen = SyntheticGenerator(kb=self.kb)
        request = GenerationRequest(data_type="profiles", count=n)
        profiles, _ = gen._generate_profiles(request)
        return profiles

    # --- SHAP Analysis ---

    def _compute_shap(self, model, X: np.ndarray) -> Optional[np.ndarray]:
        """Compute SHAP values for the test set."""
        try:
            shap = _get_shap()
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)
            return shap_values
        except Exception:
            return None

    def _extract_shap_feedback(
        self,
        shap_values: np.ndarray,
        X_synth: np.ndarray,
        X_ref: np.ndarray,
    ) -> Tuple[List[FeatureImportance], List[str]]:
        """
        Extract per-feature directional feedback from SHAP values.

        Identifies which features make synthetic data most distinguishable
        and whether synthetic values are too high, too low, or wrong shape.
        """
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

        # Map to feature names
        importances = []
        for i, feature_name in enumerate(self._feature_names):
            if i >= len(mean_abs_shap):
                break

            imp = float(mean_abs_shap[i])
            if imp < 0.001:
                continue  # Skip negligible features

            # Determine direction: compare synthetic vs reference means
            if i < X_synth.shape[1] and i < X_ref.shape[1]:
                synth_mean = float(np.mean(X_synth[:, i]))
                ref_mean = float(np.mean(X_ref[:, i]))

                if synth_mean > ref_mean * 1.05:
                    direction = "too_high"
                    detail = f"Synthetic mean ({synth_mean:.2f}) > reference ({ref_mean:.2f})"
                elif synth_mean < ref_mean * 0.95:
                    direction = "too_low"
                    detail = f"Synthetic mean ({synth_mean:.2f}) < reference ({ref_mean:.2f})"
                else:
                    direction = "wrong_shape"
                    detail = f"Means similar ({synth_mean:.2f} vs {ref_mean:.2f}), distribution shape differs"
            else:
                direction = "unknown"
                detail = "Feature index out of range"

            importances.append(
                FeatureImportance(
                    feature=feature_name,
                    importance=imp,
                    direction=direction,
                    detail=detail,
                )
            )

        # Sort by importance descending
        importances.sort(key=lambda x: x.importance, reverse=True)
        top_features = [fi.feature for fi in importances[:5]]

        return importances, top_features
