#!/usr/bin/env python3
"""
Pupil Segment Calibrator — Closes the feedback loop between L8/L9 validation
and Pupil's hardcoded CBA/StatsCan segment parameters.

Data flow:
    L8 (BehavioralFidelityValidator) produces FidelityCheck results with
    expected-vs-observed data per segment. L9 (TemporalCoherenceValidator)
    produces CoherenceCheck scores for time-series properties.

    SegmentCalibrator reads these results, computes bounded deltas, and writes
    calibrated overrides to ~/.cortex/synthetic/pupil/calibrated_segments.json.
    Next cycle, get_behavior() returns calibrated params → simulation improves.

Safety:
    - MAX_CORRECTION = 0.05 per cycle per parameter
    - All parameters bounded by PARAMETER_BOUNDS (physical limits)
    - Accumulates on existing calibration (doesn't reset to baseline)
    - Audit trail in calibration_log.jsonl
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .segment_models import DEFAULT_DATA_DIR, SEGMENT_MODELS


# ============================================================================
# Constants
# ============================================================================

MAX_CORRECTION = 0.05  # Max absolute adjustment per parameter per cycle

# Hard physical bounds per parameter — corrections cannot exceed these
PARAMETER_BOUNDS: Dict[str, tuple] = {
    "base_annual_churn_rate": (0.01, 0.40),
    "rate_sensitivity": (0.0, 1.0),
    "fee_sensitivity": (0.0, 1.0),
    "competitor_susceptibility": (0.0, 1.0),
    "product_adoption_propensity": (0.0, 1.0),
    "savings_rate_threshold": (0.5, 8.0),
    "mortgage_likelihood": (0.0, 1.0),
    "investment_propensity": (0.0, 1.0),
    "unemployment_sensitivity": (0.0, 1.0),
    "payment_miss_threshold": (300, 850),
    "default_threshold": (300, 850),
    "credit_recovery_rate": (1.0, 10.0),
    "digital_preference": (0.0, 1.0),
    "fintech_openness": (0.0, 1.0),
    "loyalty_bonus_per_year": (0.001, 0.025),
    "avg_tenure_years": (1.0, 30.0),
}

# Fields that must never be overridden (non-numeric or structural)
IMMUTABLE_FIELDS = {"segment_name", "preferred_products", "target_products"}

# Default paths
CALIBRATION_DIR = DEFAULT_DATA_DIR
CALIBRATED_FILE = CALIBRATION_DIR / "calibrated_segments.json"
CALIBRATION_LOG = CALIBRATION_DIR / "calibration_log.jsonl"


# ============================================================================
# Calibrator
# ============================================================================


class SegmentCalibrator:
    """
    Reads L8/L9 feedback, computes bounded corrections to segment parameters,
    and persists calibrated overrides for the next flywheel cycle.
    """

    def __init__(
        self,
        calibration_dir: Optional[Path] = None,
        max_correction: float = MAX_CORRECTION,
    ):
        self.calibration_dir = calibration_dir or CALIBRATION_DIR
        self.max_correction = max_correction
        self.calibrated_file = self.calibration_dir / "calibrated_segments.json"
        self.calibration_log = self.calibration_dir / "calibration_log.jsonl"

    def calibrate_from_feedback(
        self,
        l8_feedback: Optional[Dict[str, Any]] = None,
        l9_feedback: Optional[Dict[str, Any]] = None,
        cycle_id: str = "",
    ) -> Dict[str, Dict[str, float]]:
        """
        Main entry point. Reads L8/L9 feedback, computes bounded deltas,
        writes calibrated_segments.json, and appends audit log.

        Args:
            l8_feedback: LayerResult.feedback from L8 (behavioral fidelity)
            l9_feedback: LayerResult.feedback from L9 (temporal coherence)
            cycle_id: Flywheel cycle identifier for audit trail

        Returns:
            Dict mapping segment_name -> {param: calibrated_value}
        """
        if not l8_feedback and not l9_feedback:
            return {}

        # Load existing calibration (accumulates across cycles)
        current = self._load_calibration()

        # Compute deltas from L8 feedback (per-segment)
        l8_deltas = self._deltas_from_l8(l8_feedback) if l8_feedback else {}

        # Compute deltas from L9 feedback (global, applied to all segments)
        l9_deltas = self._deltas_from_l9(l9_feedback) if l9_feedback else {}

        # Merge deltas into current calibration
        updated = self._apply_deltas(current, l8_deltas, l9_deltas)

        if not updated:
            return current

        # Write calibrated file
        self._save_calibration(updated)

        # Audit log
        self._log_calibration(cycle_id, l8_deltas, l9_deltas, updated)

        return updated

    # ------------------------------------------------------------------
    # L8 → Deltas (per-segment)
    # ------------------------------------------------------------------

    def _deltas_from_l8(
        self, feedback: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:
        """
        Map L8 check failures to per-segment parameter deltas.

        L8 checks:
          - churn_rate_fidelity → adjust base_annual_churn_rate
          - product_adoption_fidelity → adjust product_adoption_propensity
          - deposit_sensitivity → adjust savings_rate_threshold
          - credit_score_range → adjust credit_recovery_rate, payment_miss_threshold
        """
        deltas: Dict[str, Dict[str, float]] = {}
        checks = feedback.get("checks", [])

        for check in checks:
            name = check.get("check_name", "")
            if check.get("passed", True):
                continue  # No correction needed for passing checks

            if name == "churn_rate_fidelity":
                self._extract_churn_deltas(check, deltas)
            elif name == "product_adoption_fidelity":
                self._extract_adoption_deltas(check, deltas)
            elif name == "deposit_sensitivity":
                self._extract_deposit_deltas(check, deltas)
            elif name == "credit_score_range":
                self._extract_credit_deltas(check, deltas)

        return deltas

    def _extract_churn_deltas(
        self, check: Dict[str, Any], deltas: Dict[str, Dict[str, float]]
    ):
        """
        Churn overshoot → decrease base_annual_churn_rate.
        Churn undershoot → increase base_annual_churn_rate.
        """
        actual = check.get("actual", {})
        if not isinstance(actual, dict):
            return

        for segment, data in actual.items():
            if not isinstance(data, dict):
                continue
            expected = data.get("expected")
            observed = data.get("observed")
            if expected is None or observed is None:
                continue
            if data.get("in_range", True):
                continue  # This segment is fine

            # Delta proportional to error, but in terms of annual rate.
            # observed > expected means too much churn → decrease rate (negative delta)
            # observed < expected means too little churn → increase rate (positive delta)
            error = observed - expected
            # Negate: correction is opposite direction of the error.
            # Scale conservatively (0.5x) since simulation-period rates
            # don't map 1:1 to annual rate adjustments.
            delta = -error * 0.5
            deltas.setdefault(segment, {})["base_annual_churn_rate"] = delta

    def _extract_adoption_deltas(
        self, check: Dict[str, Any], deltas: Dict[str, Dict[str, float]]
    ):
        """
        If adoption rank ordering is wrong, nudge propensity.
        Since L8 gives us per-segment adoption rates, we can compare
        to the expected propensity and adjust.
        """
        actual = check.get("actual", {})
        if not isinstance(actual, dict):
            return

        for segment, rate in actual.items():
            if segment not in SEGMENT_MODELS or not isinstance(rate, (int, float)):
                continue
            behavior = SEGMENT_MODELS[segment]
            # If observed adoption rate is much lower than propensity, increase it
            # If much higher, decrease it
            # Propensity is 0-1, rate is per-agent actions (different scales)
            # Use direction only: if rate is 0 but propensity > 0.2, increase
            if rate == 0 and behavior.product_adoption_propensity > 0.15:
                deltas.setdefault(segment, {})["product_adoption_propensity"] = 0.02
            elif rate > 0 and behavior.product_adoption_propensity < 0.05:
                deltas.setdefault(segment, {})["product_adoption_propensity"] = -0.02

    def _extract_deposit_deltas(
        self, check: Dict[str, Any], deltas: Dict[str, Dict[str, float]]
    ):
        """
        Deposit sensitivity failing (deposits crashed) → adjust
        savings_rate_threshold to make agents less sensitive to rate changes.
        """
        actual = check.get("actual", {})
        if not isinstance(actual, dict):
            return
        first = actual.get("first_half_avg", 0)
        second = actual.get("second_half_avg", 0)
        if first > 0:
            change_pct = (second - first) / first
            if change_pct < -0.30:
                # Deposits crashed — lower savings_rate_threshold so agents
                # are less likely to switch away (stabilizes deposits)
                # Apply to all segments since this is an aggregate check
                for segment in SEGMENT_MODELS:
                    deltas.setdefault(segment, {})["savings_rate_threshold"] = -0.1

    def _extract_credit_deltas(
        self, check: Dict[str, Any], deltas: Dict[str, Dict[str, float]]
    ):
        """
        Credit score range violations → increase credit_recovery_rate
        and raise payment_miss_threshold so fewer agents hit floor.
        """
        actual = check.get("actual", {})
        if not isinstance(actual, dict):
            return
        violations = actual.get("violations", 0)
        if violations > 0:
            # Apply small corrections globally
            for segment in SEGMENT_MODELS:
                deltas.setdefault(segment, {}).update({
                    "credit_recovery_rate": 0.3,
                    "payment_miss_threshold": 10,
                })

    # ------------------------------------------------------------------
    # L9 → Deltas (global)
    # ------------------------------------------------------------------

    def _deltas_from_l9(
        self, feedback: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Map L9 check failures to global parameter deltas.

        L9 checks:
          - satisfaction_autocorrelation low → increase loyalty_bonus_per_year
          - deposit_smoothness violations → dampen fee_sensitivity
        """
        deltas: Dict[str, float] = {}
        checks = feedback.get("checks", [])

        for check in checks:
            name = check.get("check_name", "")
            if check.get("passed", True):
                continue

            if name == "satisfaction_autocorrelation":
                # Low autocorrelation means satisfaction jumps randomly.
                # Increasing loyalty_bonus_per_year smooths satisfaction
                # by making tenure matter more.
                deltas["loyalty_bonus_per_year"] = 0.001

            elif name == "deposit_smoothness":
                # Too many deposit swings → dampen fee_sensitivity
                # so agents don't overreact to fee changes.
                deltas["fee_sensitivity"] = -0.03

        return deltas

    # ------------------------------------------------------------------
    # Apply & Bound
    # ------------------------------------------------------------------

    def _apply_deltas(
        self,
        current: Dict[str, Dict[str, float]],
        l8_deltas: Dict[str, Dict[str, float]],
        l9_deltas: Dict[str, float],
    ) -> Dict[str, Dict[str, float]]:
        """
        Merge L8 (per-segment) and L9 (global) deltas into the current
        calibration, applying MAX_CORRECTION and PARAMETER_BOUNDS.
        """
        result = {seg: dict(overrides) for seg, overrides in current.items()}
        any_change = False

        all_segments = set(list(l8_deltas.keys()) + list(SEGMENT_MODELS.keys()))

        for segment in all_segments:
            if segment not in SEGMENT_MODELS:
                continue

            baseline = SEGMENT_MODELS[segment]
            segment_overrides = result.get(segment, {})

            # Merge L8 segment-specific deltas
            seg_deltas = l8_deltas.get(segment, {})

            # Merge L9 global deltas
            merged_deltas: Dict[str, float] = {}
            for param, delta in seg_deltas.items():
                merged_deltas[param] = delta
            for param, delta in l9_deltas.items():
                # L9 deltas add to any L8 delta for the same param
                merged_deltas[param] = merged_deltas.get(param, 0.0) + delta

            if not merged_deltas:
                continue

            for param, delta in merged_deltas.items():
                if param in IMMUTABLE_FIELDS:
                    continue
                if param not in PARAMETER_BOUNDS:
                    continue

                # Clamp delta to MAX_CORRECTION
                clamped_delta = max(-self.max_correction, min(self.max_correction, delta))

                # Current value: calibrated override or baseline
                current_val = segment_overrides.get(param)
                if current_val is None:
                    current_val = getattr(baseline, param, None)
                if current_val is None or not isinstance(current_val, (int, float)):
                    continue

                # Apply delta
                new_val = current_val + clamped_delta

                # Clamp to physical bounds
                low, high = PARAMETER_BOUNDS[param]
                new_val = max(low, min(high, new_val))

                # Only record if changed
                if new_val != current_val:
                    segment_overrides[param] = new_val
                    any_change = True

            if segment_overrides:
                result[segment] = segment_overrides

        return result if any_change else current

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_calibration(self) -> Dict[str, Dict[str, float]]:
        """Load existing calibrated overrides, or empty dict if none."""
        if not self.calibrated_file.exists():
            return {}
        try:
            with open(self.calibrated_file) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save_calibration(self, calibration: Dict[str, Dict[str, float]]):
        """Write calibrated overrides to disk."""
        self.calibration_dir.mkdir(parents=True, exist_ok=True)
        # Round all values for clean JSON
        rounded = {}
        for segment, overrides in calibration.items():
            rounded[segment] = {
                param: round(val, 6) if isinstance(val, float) else val
                for param, val in overrides.items()
            }
        with open(self.calibrated_file, "w") as f:
            json.dump(rounded, f, indent=2)

    def _log_calibration(
        self,
        cycle_id: str,
        l8_deltas: Dict[str, Dict[str, float]],
        l9_deltas: Dict[str, float],
        result: Dict[str, Dict[str, float]],
    ):
        """Append audit entry to calibration log."""
        self.calibration_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle_id": cycle_id,
            "l8_deltas": l8_deltas,
            "l9_deltas": l9_deltas,
            "segments_updated": list(result.keys()),
            "n_params_calibrated": sum(len(v) for v in result.values()),
        }
        with open(self.calibration_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
