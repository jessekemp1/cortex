#!/usr/bin/env python3
"""
Tests for SegmentCalibrator — Pupil calibration feedback loop.

Covers:
- Churn overshoot/undershoot → base_annual_churn_rate corrections
- MAX_CORRECTION bounding
- PARAMETER_BOUNDS physical limits
- Calibration file persistence and loading
- get_behavior() integration with calibrated overrides
- Accumulation across multiple cycles
- No-op when all checks pass
- Immutable fields never overridden
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.pupil.calibrator import (
    MAX_CORRECTION,
    PARAMETER_BOUNDS,
    SegmentCalibrator,
)
from synthetic.pupil.segment_models import (
    SEGMENT_MODELS,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tmp_calibration_dir(tmp_path):
    """Provide a temporary directory for calibration files."""
    cal_dir = tmp_path / "pupil"
    cal_dir.mkdir()
    return cal_dir


@pytest.fixture
def calibrator(tmp_calibration_dir):
    """Create a SegmentCalibrator using temporary directory."""
    return SegmentCalibrator(calibration_dir=tmp_calibration_dir)


def _make_l8_feedback(checks):
    """Build L8 feedback dict from a list of check dicts."""
    return {"checks": checks}


def _make_l9_feedback(checks):
    """Build L9 feedback dict from a list of check dicts."""
    return {"checks": checks}


def _churn_check(segment_data, passed=False):
    """Build a churn_rate_fidelity check with per-segment actual data."""
    return {
        "check_name": "churn_rate_fidelity",
        "passed": passed,
        "score": 0.3 if not passed else 1.0,
        "detail": "test",
        "expected": "Per-segment churn within +/-50% of calibration",
        "actual": segment_data,
    }


# ============================================================================
# Test: Churn Corrections
# ============================================================================


class TestChurnCorrections:
    """Churn overshoot decreases rate, undershoot increases rate."""

    def test_churn_overshoot_decreases_rate(self, calibrator):
        """If observed > expected, base_annual_churn_rate should decrease."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.20,  # Overshooting by 0.10
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                ),
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0001")

        assert "mass_market" in result
        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        calibrated = result["mass_market"]["base_annual_churn_rate"]
        # Overshoot → rate should decrease (calibrated < baseline)
        assert calibrated < baseline

    def test_churn_undershoot_increases_rate(self, calibrator):
        """If observed < expected, base_annual_churn_rate should increase."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.20,
                            "observed": 0.05,  # Undershooting by 0.15
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                ),
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0002")

        assert "mass_market" in result
        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        calibrated = result["mass_market"]["base_annual_churn_rate"]
        # Undershoot → rate should increase (calibrated > baseline)
        assert calibrated > baseline

    def test_churn_in_range_no_correction(self, calibrator):
        """Segments already in range get no correction."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.11,
                            "in_range": True,
                            "n_agents": 100,
                        },
                    },
                    passed=True,
                ),
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0003")
        # No changes since check passed
        assert result == {} or "mass_market" not in result


# ============================================================================
# Test: MAX_CORRECTION Bounding
# ============================================================================


class TestMaxCorrectionBound:
    """Corrections are clamped to MAX_CORRECTION per cycle."""

    def test_large_churn_error_bounded(self, calibrator):
        """Even a huge error only produces MAX_CORRECTION delta."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.05,
                            "observed": 0.95,  # Massive overshoot
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                ),
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0004")

        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        calibrated = result["mass_market"]["base_annual_churn_rate"]
        actual_delta = abs(calibrated - baseline)
        assert actual_delta <= MAX_CORRECTION + 1e-9

    def test_custom_max_correction(self, tmp_calibration_dir):
        """Custom max_correction is honored."""
        cal = SegmentCalibrator(calibration_dir=tmp_calibration_dir, max_correction=0.01)
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.05,
                            "observed": 0.50,
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                ),
            ]
        )
        result = cal.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0005")

        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        calibrated = result["mass_market"]["base_annual_churn_rate"]
        actual_delta = abs(calibrated - baseline)
        assert actual_delta <= 0.01 + 1e-9


# ============================================================================
# Test: PARAMETER_BOUNDS Physical Limits
# ============================================================================


class TestParameterBounds:
    """Corrections cannot push values outside physical bounds."""

    def test_churn_rate_cannot_exceed_upper_bound(self, tmp_calibration_dir):
        """Even with many cycles of undershoot, churn stays <= 0.40."""
        cal = SegmentCalibrator(calibration_dir=tmp_calibration_dir, max_correction=0.10)
        for i in range(20):
            l8 = _make_l8_feedback(
                [
                    _churn_check(
                        {
                            "new_to_canada": {
                                "expected": 0.99,
                                "observed": 0.01,  # Extreme undershoot → increase
                                "in_range": False,
                                "n_agents": 100,
                            },
                        }
                    ),
                ]
            )
            cal.calibrate_from_feedback(l8_feedback=l8, cycle_id=f"C{i:04d}")

        result = cal._load_calibration()
        upper = PARAMETER_BOUNDS["base_annual_churn_rate"][1]
        assert result["new_to_canada"]["base_annual_churn_rate"] <= upper

    def test_churn_rate_cannot_go_below_lower_bound(self, tmp_calibration_dir):
        """Even with many cycles of overshoot, churn stays >= 0.01."""
        cal = SegmentCalibrator(calibration_dir=tmp_calibration_dir, max_correction=0.10)
        for i in range(20):
            l8 = _make_l8_feedback(
                [
                    _churn_check(
                        {
                            "ultra_hnw": {
                                "expected": 0.01,
                                "observed": 0.99,  # Extreme overshoot → decrease
                                "in_range": False,
                                "n_agents": 100,
                            },
                        }
                    ),
                ]
            )
            cal.calibrate_from_feedback(l8_feedback=l8, cycle_id=f"C{i:04d}")

        result = cal._load_calibration()
        lower = PARAMETER_BOUNDS["base_annual_churn_rate"][0]
        assert result["ultra_hnw"]["base_annual_churn_rate"] >= lower


# ============================================================================
# Test: Persistence
# ============================================================================


class TestPersistence:
    """Calibration file persists and loads correctly."""

    def test_calibrated_file_created(self, calibrator, tmp_calibration_dir):
        """calibrated_segments.json is written after calibration."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.20,
                            "in_range": False,
                            "n_agents": 50,
                        },
                    }
                ),
            ]
        )
        calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0010")

        cal_file = tmp_calibration_dir / "calibrated_segments.json"
        assert cal_file.exists()
        data = json.loads(cal_file.read_text())
        assert "mass_market" in data
        assert "base_annual_churn_rate" in data["mass_market"]

    def test_audit_log_appended(self, calibrator, tmp_calibration_dir):
        """calibration_log.jsonl gets an entry per calibration."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.20,
                            "in_range": False,
                            "n_agents": 50,
                        },
                    }
                ),
            ]
        )
        calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0011")
        calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0012")

        log_file = tmp_calibration_dir / "calibration_log.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert entry["cycle_id"] == "C0011"

    def test_load_from_disk(self, calibrator, tmp_calibration_dir):
        """Second calibration accumulates on persisted first calibration."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.20,
                            "in_range": False,
                            "n_agents": 50,
                        },
                    }
                ),
            ]
        )
        result1 = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0020")
        val1 = result1["mass_market"]["base_annual_churn_rate"]

        # Second calibration should accumulate
        result2 = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0021")
        val2 = result2["mass_market"]["base_annual_churn_rate"]

        # val2 should be further decreased (overshoot correction applied twice)
        assert val2 < val1


# ============================================================================
# Test: get_behavior() Integration
# ============================================================================


class TestGetBehaviorIntegration:
    """get_behavior() returns calibrated values when file exists."""

    def test_get_behavior_returns_calibrated(self, calibrator, tmp_calibration_dir):
        """get_behavior() picks up calibrated overrides."""
        # Write calibration
        calibration = {
            "mass_market": {"base_annual_churn_rate": 0.25},
        }
        cal_file = tmp_calibration_dir / "calibrated_segments.json"
        cal_file.write_text(json.dumps(calibration))

        # Import and call with patched path
        from synthetic.pupil import segment_models

        with patch.object(
            segment_models,
            "_load_calibrated_overrides",
            side_effect=lambda seg: calibration.get(seg, {}),
        ):
            behavior = segment_models.get_behavior("mass_market", use_calibrated=True)
            assert behavior.base_annual_churn_rate == 0.25

    def test_get_behavior_uncalibrated_returns_baseline(self):
        """get_behavior(use_calibrated=False) returns pure CBA baseline."""
        from synthetic.pupil import segment_models

        behavior = segment_models.get_behavior("mass_market", use_calibrated=False)
        assert (
            behavior.base_annual_churn_rate == SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        )

    def test_get_behavior_missing_file_returns_baseline(self):
        """get_behavior() returns baseline when no calibration file exists."""
        from synthetic.pupil import segment_models

        with patch.object(
            segment_models,
            "_load_calibrated_overrides",
            return_value={},
        ):
            behavior = segment_models.get_behavior("mass_market", use_calibrated=True)
            assert (
                behavior.base_annual_churn_rate
                == SEGMENT_MODELS["mass_market"].base_annual_churn_rate
            )


# ============================================================================
# Test: Accumulation Across Cycles
# ============================================================================


class TestAccumulation:
    """Corrections accumulate across multiple cycles."""

    def test_three_cycles_accumulate(self, calibrator):
        """Three cycles of the same error produce increasing correction."""
        # Use new_to_canada (baseline 0.22) with a small overshoot so
        # 3 cycles of -0.02 delta don't hit the 0.01 lower bound.
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "new_to_canada": {
                            "expected": 0.15,
                            "observed": 0.19,  # Small overshoot → decrease
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                ),
            ]
        )

        baseline = SEGMENT_MODELS["new_to_canada"].base_annual_churn_rate
        values = []
        for i in range(3):
            result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id=f"C{i:04d}")
            values.append(result["new_to_canada"]["base_annual_churn_rate"])

        # Each cycle should decrease the rate further
        assert values[0] < baseline
        assert values[1] < values[0]
        assert values[2] < values[1]


# ============================================================================
# Test: No-Op When All Checks Pass
# ============================================================================


class TestNoOp:
    """No corrections when all checks pass."""

    def test_all_passing_no_changes(self, calibrator):
        """Passing checks produce no corrections."""
        l8 = _make_l8_feedback(
            [
                {
                    "check_name": "churn_rate_fidelity",
                    "passed": True,
                    "score": 0.9,
                    "detail": "all good",
                    "actual": {},
                },
                {
                    "check_name": "product_adoption_fidelity",
                    "passed": True,
                    "score": 0.8,
                    "detail": "all good",
                    "actual": {},
                },
            ]
        )
        l9 = _make_l9_feedback(
            [
                {
                    "check_name": "satisfaction_autocorrelation",
                    "passed": True,
                    "score": 0.9,
                    "detail": "all good",
                },
                {
                    "check_name": "deposit_smoothness",
                    "passed": True,
                    "score": 0.95,
                    "detail": "all good",
                },
            ]
        )
        result = calibrator.calibrate_from_feedback(
            l8_feedback=l8, l9_feedback=l9, cycle_id="C0100"
        )
        assert result == {}

    def test_no_feedback_no_changes(self, calibrator):
        """No feedback at all → no changes."""
        result = calibrator.calibrate_from_feedback(cycle_id="C0101")
        assert result == {}


# ============================================================================
# Test: Immutable Fields Never Overridden
# ============================================================================


class TestImmutableFields:
    """Non-numeric/structural fields are never modified."""

    def test_segment_name_immutable(self, calibrator, tmp_calibration_dir):
        """segment_name is never written to calibration."""
        # Manually write a bad calibration to verify it doesn't propagate
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.25,
                            "in_range": False,
                            "n_agents": 50,
                        },
                    }
                ),
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0200")

        if "mass_market" in result:
            assert "segment_name" not in result["mass_market"]
            assert "preferred_products" not in result["mass_market"]
            assert "target_products" not in result["mass_market"]


# ============================================================================
# Test: L9 Temporal Coherence Corrections
# ============================================================================


class TestL9Corrections:
    """L9 feedback produces global corrections."""

    def test_low_autocorrelation_increases_loyalty(self, calibrator):
        """Low satisfaction autocorrelation → loyalty_bonus_per_year increases."""
        l9 = _make_l9_feedback(
            [
                {
                    "check_name": "satisfaction_autocorrelation",
                    "passed": False,
                    "score": 0.3,
                    "detail": "Avg autocorrelation: 0.2",
                },
            ]
        )
        result = calibrator.calibrate_from_feedback(l9_feedback=l9, cycle_id="C0300")

        # Check that at least one segment got loyalty_bonus_per_year increase
        segments_with_loyalty = [
            seg for seg, overrides in result.items() if "loyalty_bonus_per_year" in overrides
        ]
        assert len(segments_with_loyalty) > 0

        for seg in segments_with_loyalty:
            baseline = SEGMENT_MODELS[seg].loyalty_bonus_per_year
            calibrated = result[seg]["loyalty_bonus_per_year"]
            assert calibrated > baseline

    def test_deposit_smoothness_failure_dampens_fee_sensitivity(self, calibrator):
        """Deposit smoothness violations → fee_sensitivity decreases."""
        l9 = _make_l9_feedback(
            [
                {
                    "check_name": "deposit_smoothness",
                    "passed": False,
                    "score": 0.2,
                    "detail": "Too many swings",
                },
            ]
        )
        result = calibrator.calibrate_from_feedback(l9_feedback=l9, cycle_id="C0301")

        segments_with_fee = [
            seg for seg, overrides in result.items() if "fee_sensitivity" in overrides
        ]
        assert len(segments_with_fee) > 0

        for seg in segments_with_fee:
            baseline = SEGMENT_MODELS[seg].fee_sensitivity
            calibrated = result[seg]["fee_sensitivity"]
            assert calibrated < baseline


# ============================================================================
# Test: Credit Score Range Corrections
# ============================================================================


class TestCreditCorrections:
    """Credit score violations produce recovery corrections."""

    def test_credit_violations_increase_recovery(self, calibrator):
        """Credit score range violations → credit_recovery_rate increases."""
        l8 = _make_l8_feedback(
            [
                {
                    "check_name": "credit_score_range",
                    "passed": False,
                    "score": 0.5,
                    "detail": "10 violations",
                    "actual": {"violations": 10, "total_observations": 1000},
                },
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0400")

        # At least some segments should have credit_recovery_rate adjustment
        segments_with_credit = [
            seg for seg, overrides in result.items() if "credit_recovery_rate" in overrides
        ]
        assert len(segments_with_credit) > 0

        for seg in segments_with_credit:
            baseline = SEGMENT_MODELS[seg].credit_recovery_rate
            calibrated = result[seg]["credit_recovery_rate"]
            assert calibrated >= baseline


# ============================================================================
# Test: Combined L8 + L9
# ============================================================================


class TestCombinedFeedback:
    """L8 and L9 corrections combine correctly."""

    def test_l8_and_l9_both_apply(self, calibrator):
        """Both L8 (per-segment) and L9 (global) corrections are applied."""
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.20,
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                ),
            ]
        )
        l9 = _make_l9_feedback(
            [
                {
                    "check_name": "satisfaction_autocorrelation",
                    "passed": False,
                    "score": 0.3,
                    "detail": "Low autocorrelation",
                },
            ]
        )
        result = calibrator.calibrate_from_feedback(
            l8_feedback=l8, l9_feedback=l9, cycle_id="C0500"
        )

        assert "mass_market" in result
        # Should have both churn correction AND loyalty correction
        mm = result["mass_market"]
        assert "base_annual_churn_rate" in mm
        assert "loyalty_bonus_per_year" in mm


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge cases and malformed input handling."""

    def test_empty_checks_list(self, calibrator):
        """Empty checks list → no corrections."""
        result = calibrator.calibrate_from_feedback(l8_feedback={"checks": []}, cycle_id="C0600")
        assert result == {}

    def test_unknown_check_name_ignored(self, calibrator):
        """Unknown check names are silently ignored."""
        l8 = _make_l8_feedback(
            [
                {
                    "check_name": "future_check_v99",
                    "passed": False,
                    "score": 0.1,
                    "detail": "Unknown",
                },
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0601")
        assert result == {}

    def test_malformed_actual_data_no_crash(self, calibrator):
        """Malformed actual data doesn't crash the calibrator."""
        l8 = _make_l8_feedback(
            [
                {
                    "check_name": "churn_rate_fidelity",
                    "passed": False,
                    "score": 0.3,
                    "detail": "test",
                    "actual": "not a dict",
                },
            ]
        )
        # Should not raise
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0602")
        assert isinstance(result, dict)

    def test_corrupt_calibration_file_recovers(self, calibrator, tmp_calibration_dir):
        """Corrupt calibration file → starts fresh."""
        cal_file = tmp_calibration_dir / "calibrated_segments.json"
        cal_file.write_text("{invalid json")

        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.10,
                            "observed": 0.20,
                            "in_range": False,
                            "n_agents": 50,
                        },
                    }
                ),
            ]
        )
        # Should recover and produce results
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0603")
        assert "mass_market" in result
