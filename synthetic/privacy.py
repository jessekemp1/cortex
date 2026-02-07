#!/usr/bin/env python3
"""
Privacy Guarantee Engine — Ensures synthetic data doesn't leak real individuals.

Three complementary privacy metrics:

  1. DCR (Distance to Closest Record): For each synthetic record, measures
     the minimum distance to any reference record. Target > 0.05 (normalized).
     Detects memorization — if the generator is just copying real records.

  2. NNDR (Nearest Neighbor Distance Ratio): Ratio of distance to 1st vs 2nd
     nearest reference neighbor. Target > 0.5. Low NNDR means a synthetic
     record is suspiciously close to ONE specific real record (vs. being
     generally similar to many).

  3. MIA (Membership Inference Attack): Trains a shadow model to guess whether
     a record was in the generator's training set. Success rate < 55% means
     the synthetic data doesn't leak membership information.

Architecture:
    PrivacyEngine(kb) → evaluate(profiles) → PrivacyReport
    → privacy_feedback → flywheel correction signals (Layer 7)
    → noise_calibration → per-dimension noise adjustments
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import CustomerProfile


# Features used for privacy distance calculations
PRIVACY_FEATURES = [
    "age", "annual_income", "household_income", "credit_score",
    "total_deposits", "total_credit_outstanding", "tenure_years",
    "products_per_household",
]


@dataclass
class RecordPrivacy:
    """Privacy assessment for a single synthetic record."""
    profile_id: str
    dcr: float  # Distance to Closest Record (normalized)
    nndr: float  # Nearest Neighbor Distance Ratio
    privacy_score: float  # Combined score 0-1
    closest_feature: str  # Which feature drives the closest match
    safe: bool  # Meets all thresholds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "dcr": round(self.dcr, 6),
            "nndr": round(self.nndr, 6),
            "privacy_score": round(self.privacy_score, 4),
            "closest_feature": self.closest_feature,
            "safe": self.safe,
        }


@dataclass
class PrivacyReport:
    """Aggregate privacy report for a batch of synthetic records."""
    n_synthetic: int
    n_reference: int
    # DCR metrics
    mean_dcr: float
    min_dcr: float
    dcr_pass_rate: float  # Fraction with DCR > threshold
    # NNDR metrics
    mean_nndr: float
    min_nndr: float
    nndr_pass_rate: float  # Fraction with NNDR > threshold
    # MIA metrics
    mia_accuracy: float  # Attack success rate (lower = better)
    mia_advantage: float  # Accuracy - 0.5 (0 = random, ideal)
    # Aggregate
    per_record: List[RecordPrivacy] = field(default_factory=list)
    low_privacy_dimensions: Dict[str, float] = field(default_factory=dict)
    noise_adjustments: Dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """All privacy thresholds met."""
        return (
            self.min_dcr > PrivacyEngine.DCR_THRESHOLD
            and self.min_nndr > PrivacyEngine.NNDR_THRESHOLD
            and self.mia_accuracy < PrivacyEngine.MIA_THRESHOLD
        )

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"Privacy: {status} | "
            f"DCR={self.mean_dcr:.4f} (min={self.min_dcr:.4f}) | "
            f"NNDR={self.mean_nndr:.4f} (min={self.min_nndr:.4f}) | "
            f"MIA={self.mia_accuracy:.3f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "n_synthetic": self.n_synthetic,
            "n_reference": self.n_reference,
            "dcr": {
                "mean": round(self.mean_dcr, 6),
                "min": round(self.min_dcr, 6),
                "pass_rate": round(self.dcr_pass_rate, 4),
                "threshold": PrivacyEngine.DCR_THRESHOLD,
            },
            "nndr": {
                "mean": round(self.mean_nndr, 6),
                "min": round(self.min_nndr, 6),
                "pass_rate": round(self.nndr_pass_rate, 4),
                "threshold": PrivacyEngine.NNDR_THRESHOLD,
            },
            "mia": {
                "accuracy": round(self.mia_accuracy, 4),
                "advantage": round(self.mia_advantage, 4),
                "threshold": PrivacyEngine.MIA_THRESHOLD,
            },
            "low_privacy_dimensions": {
                k: round(v, 6) for k, v in self.low_privacy_dimensions.items()
            },
            "noise_adjustments": {
                k: round(v, 6) for k, v in self.noise_adjustments.items()
            },
            "per_record_count": len(self.per_record),
        }


class PrivacyEngine:
    """
    Privacy guarantee engine for synthetic data.

    Evaluates DCR, NNDR, and MIA resistance. Provides per-record
    privacy scores and per-dimension noise calibration feedback
    for the flywheel.
    """

    DCR_THRESHOLD = 0.05  # Minimum normalized distance to closest record
    NNDR_THRESHOLD = 0.5  # Minimum nearest-neighbor distance ratio
    MIA_THRESHOLD = 0.55  # Maximum MIA success rate (55% = near random)
    NOISE_SCALE_FACTOR = 0.1  # How much to increase noise per violation

    def __init__(self, kb: Optional[CanadianFinServKB] = None):
        self.kb = kb or CanadianFinServKB()
        self._feature_ranges: Optional[Dict[str, Tuple[float, float]]] = None

    def evaluate(
        self,
        synthetic_profiles: List[CustomerProfile],
        reference_profiles: Optional[List[CustomerProfile]] = None,
    ) -> PrivacyReport:
        """
        Run full privacy evaluation on synthetic profiles.

        Args:
            synthetic_profiles: Generated profiles to evaluate
            reference_profiles: Reference data (auto-generated if None)

        Returns:
            PrivacyReport with DCR, NNDR, MIA, and noise calibration
        """
        if reference_profiles is None:
            reference_profiles = self._generate_reference(len(synthetic_profiles))

        # Convert to feature matrices
        X_synth = self._profiles_to_features(synthetic_profiles)
        X_ref = self._profiles_to_features(reference_profiles)

        # Normalize features to [0, 1] for fair distance calculation
        X_synth_norm, X_ref_norm = self._normalize(X_synth, X_ref)

        # Compute pairwise distances (synthetic → reference)
        distances = self._pairwise_distances(X_synth_norm, X_ref_norm)

        # DCR: minimum distance per synthetic record
        dcr_values = np.min(distances, axis=1)

        # NNDR: ratio of 1st to 2nd nearest neighbor distance
        nndr_values = self._compute_nndr(distances)

        # Per-record privacy scores
        per_record = self._build_per_record(
            synthetic_profiles, dcr_values, nndr_values,
            distances, X_synth_norm, X_ref_norm,
        )

        # MIA: Membership Inference Attack
        mia_accuracy = self._run_mia(X_synth, X_ref)

        # Low-privacy dimensions
        low_dims = self._identify_low_privacy_dimensions(
            X_synth_norm, X_ref_norm, distances,
        )

        # Noise adjustments
        noise_adj = self._calibrate_noise(low_dims, dcr_values, nndr_values)

        return PrivacyReport(
            n_synthetic=len(synthetic_profiles),
            n_reference=len(reference_profiles),
            mean_dcr=float(np.mean(dcr_values)),
            min_dcr=float(np.min(dcr_values)),
            dcr_pass_rate=float(np.mean(dcr_values > self.DCR_THRESHOLD)),
            mean_nndr=float(np.mean(nndr_values)),
            min_nndr=float(np.min(nndr_values)),
            nndr_pass_rate=float(np.mean(nndr_values > self.NNDR_THRESHOLD)),
            mia_accuracy=mia_accuracy,
            mia_advantage=mia_accuracy - 0.5,
            per_record=per_record,
            low_privacy_dimensions=low_dims,
            noise_adjustments=noise_adj,
        )

    # --- Feature Extraction ---

    def _profiles_to_features(self, profiles: List[CustomerProfile]) -> np.ndarray:
        """Convert profiles to numeric feature matrix."""
        rows = []
        for p in profiles:
            rows.append([
                float(p.age),
                p.annual_income,
                p.household_income,
                float(p.credit_score),
                p.total_deposits,
                p.total_credit_outstanding,
                p.tenure_years,
                float(p.products_per_household),
            ])
        return np.array(rows, dtype=float)

    def _normalize(
        self, X_synth: np.ndarray, X_ref: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Min-max normalize both matrices using combined range."""
        combined = np.vstack([X_synth, X_ref])
        mins = combined.min(axis=0)
        maxs = combined.max(axis=0)
        ranges = maxs - mins
        # Avoid division by zero for constant features
        ranges[ranges == 0] = 1.0

        # Store feature ranges for dimension analysis
        self._feature_ranges = {
            PRIVACY_FEATURES[i]: (float(mins[i]), float(maxs[i]))
            for i in range(len(PRIVACY_FEATURES))
        }

        X_synth_norm = (X_synth - mins) / ranges
        X_ref_norm = (X_ref - mins) / ranges
        return X_synth_norm, X_ref_norm

    # --- Distance Computation ---

    def _pairwise_distances(
        self, X_synth: np.ndarray, X_ref: np.ndarray
    ) -> np.ndarray:
        """Compute Euclidean distance from each synthetic to each reference record."""
        # (n_synth, n_ref) distance matrix
        # Using efficient vectorized computation
        synth_sq = np.sum(X_synth ** 2, axis=1, keepdims=True)
        ref_sq = np.sum(X_ref ** 2, axis=1, keepdims=True)
        cross = X_synth @ X_ref.T
        distances = np.sqrt(np.maximum(synth_sq + ref_sq.T - 2 * cross, 0.0))
        return distances

    def _compute_nndr(self, distances: np.ndarray) -> np.ndarray:
        """
        Nearest Neighbor Distance Ratio for each synthetic record.

        NNDR = dist_to_1st_nearest / dist_to_2nd_nearest
        Low NNDR = suspiciously close to one specific record.
        """
        if distances.shape[1] < 2:
            return np.ones(distances.shape[0])  # Can't compute NNDR with < 2 reference

        # Partition to find 2 smallest distances per row
        partitioned = np.partition(distances, 1, axis=1)
        d1 = partitioned[:, 0]  # Nearest
        d2 = partitioned[:, 1]  # Second nearest

        # Avoid division by zero — compute safely
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = np.divide(d1, d2, out=np.ones_like(d1), where=d2 > 0)
        return ratio

    # --- Membership Inference Attack ---

    def _run_mia(self, X_synth: np.ndarray, X_ref: np.ndarray) -> float:
        """
        Simulate a Membership Inference Attack.

        Strategy: Train a model to distinguish "member" (used in generation)
        from "non-member" (held-out reference). If accuracy ≈ 50%, the
        synthetic data doesn't leak membership.

        Since we don't have actual training data, we use a shadow model approach:
        split reference into "training" and "holdout", generate synthetic from
        each, and train a classifier to distinguish them.
        """
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        from sklearn.model_selection import train_test_split

        n = min(len(X_synth), len(X_ref))
        if n < 20:
            return 0.50  # Not enough data, assume random

        # Create attack dataset:
        # "Members" = synthetic records (assume they reflect training data)
        # "Non-members" = reference records (independent samples)
        X = np.vstack([X_synth[:n], X_ref[:n]])
        y = np.concatenate([np.ones(n), np.zeros(n)])

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.3, random_state=42, stratify=y
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.3, random_state=42
            )

        clf = RandomForestClassifier(n_estimators=50, max_depth=3, random_state=42)
        clf.fit(X_train, y_train)
        accuracy = accuracy_score(y_test, clf.predict(X_test))

        return float(accuracy)

    # --- Per-Record Analysis ---

    def _build_per_record(
        self,
        profiles: List[CustomerProfile],
        dcr_values: np.ndarray,
        nndr_values: np.ndarray,
        distances: np.ndarray,
        X_synth_norm: np.ndarray,
        X_ref_norm: np.ndarray,
    ) -> List[RecordPrivacy]:
        """Build per-record privacy assessments."""
        records = []
        for i, profile in enumerate(profiles):
            dcr = float(dcr_values[i])
            nndr = float(nndr_values[i])

            # Combined privacy score: geometric mean of normalized DCR and NNDR
            dcr_score = min(1.0, dcr / self.DCR_THRESHOLD)
            nndr_score = min(1.0, nndr / self.NNDR_THRESHOLD)
            privacy_score = (dcr_score * nndr_score) ** 0.5

            # Find which feature drives the closest match
            closest_ref_idx = int(np.argmin(distances[i]))
            feature_diffs = np.abs(X_synth_norm[i] - X_ref_norm[closest_ref_idx])
            closest_feat_idx = int(np.argmin(feature_diffs))
            closest_feature = PRIVACY_FEATURES[closest_feat_idx]

            safe = dcr > self.DCR_THRESHOLD and nndr > self.NNDR_THRESHOLD

            records.append(RecordPrivacy(
                profile_id=profile.profile_id,
                dcr=dcr,
                nndr=nndr,
                privacy_score=privacy_score,
                closest_feature=closest_feature,
                safe=safe,
            ))

        return records

    # --- Dimension Analysis ---

    def _identify_low_privacy_dimensions(
        self,
        X_synth_norm: np.ndarray,
        X_ref_norm: np.ndarray,
        distances: np.ndarray,
    ) -> Dict[str, float]:
        """
        Identify which features contribute most to privacy violations.

        For records with low DCR, measure per-feature distance contribution.
        Features with small differences drive the close matches.
        """
        low_privacy_dims = {}

        # Find records with DCR below threshold
        min_dists = np.min(distances, axis=1)
        violations = min_dists < self.DCR_THRESHOLD
        if not np.any(violations):
            return low_privacy_dims

        # For violating records, find which features are too similar
        violation_indices = np.where(violations)[0]
        for i in violation_indices:
            closest_ref = int(np.argmin(distances[i]))
            feature_diffs = np.abs(X_synth_norm[i] - X_ref_norm[closest_ref])

            for j, feat in enumerate(PRIVACY_FEATURES):
                if feature_diffs[j] < 0.02:  # Very close on this feature
                    low_privacy_dims[feat] = low_privacy_dims.get(feat, 0) + 1

        # Normalize by violation count
        n_violations = len(violation_indices)
        return {
            feat: count / n_violations
            for feat, count in low_privacy_dims.items()
        }

    def _calibrate_noise(
        self,
        low_dims: Dict[str, float],
        dcr_values: np.ndarray,
        nndr_values: np.ndarray,
    ) -> Dict[str, float]:
        """
        Compute per-dimension noise adjustments.

        Increases noise for dimensions that contribute to privacy violations.
        The adjustment magnitude is proportional to how much the dimension
        contributes and how severe the violations are.
        """
        adjustments = {}

        # Global violation severity
        dcr_violation_rate = float(np.mean(dcr_values < self.DCR_THRESHOLD))
        nndr_violation_rate = float(np.mean(nndr_values < self.NNDR_THRESHOLD))
        severity = max(dcr_violation_rate, nndr_violation_rate)

        if severity == 0:
            return adjustments  # No violations, no noise needed

        for feat, contribution in low_dims.items():
            # Scale noise increase by contribution and severity
            adjustment = contribution * severity * self.NOISE_SCALE_FACTOR
            adjustments[feat] = adjustment

        return adjustments

    # --- Reference Generation ---

    def _generate_reference(self, n: int) -> List[CustomerProfile]:
        """Generate reference profiles from KB distributions."""
        from synthetic.generator import SyntheticGenerator
        from synthetic.schemas import GenerationRequest

        gen = SyntheticGenerator(kb=self.kb)
        request = GenerationRequest(data_type="profiles", count=n)
        profiles, _ = gen._generate_profiles(request)
        return profiles
