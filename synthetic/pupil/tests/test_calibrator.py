"""Standalone tests for SegmentCalibrator."""

import pytest
from pupil.calibrator import MAX_CORRECTION, SegmentCalibrator
from pupil.segment_models import SEGMENT_MODELS


@pytest.fixture
def tmp_calibration_dir(tmp_path):
    cal_dir = tmp_path / "pupil"
    cal_dir.mkdir()
    return cal_dir


@pytest.fixture
def calibrator(tmp_calibration_dir):
    return SegmentCalibrator(calibration_dir=tmp_calibration_dir)


def _make_l8_feedback(checks):
    return {"checks": checks}


def _churn_check(segment_data, passed=False):
    return {
        "check_name": "churn_rate_fidelity",
        "passed": passed,
        "score": 0.3 if not passed else 1.0,
        "detail": "test",
        "actual": segment_data,
    }


class TestChurnCorrections:
    def test_overshoot_decreases_rate(self, calibrator):
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
                )
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0001")
        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        assert result["mass_market"]["base_annual_churn_rate"] < baseline

    def test_undershoot_increases_rate(self, calibrator):
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.20,
                            "observed": 0.05,
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                )
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0002")
        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        assert result["mass_market"]["base_annual_churn_rate"] > baseline


class TestBounding:
    def test_large_error_bounded(self, calibrator):
        l8 = _make_l8_feedback(
            [
                _churn_check(
                    {
                        "mass_market": {
                            "expected": 0.05,
                            "observed": 0.95,
                            "in_range": False,
                            "n_agents": 100,
                        },
                    }
                )
            ]
        )
        result = calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0004")
        baseline = SEGMENT_MODELS["mass_market"].base_annual_churn_rate
        actual_delta = abs(result["mass_market"]["base_annual_churn_rate"] - baseline)
        assert actual_delta <= MAX_CORRECTION + 1e-9


class TestPersistence:
    def test_file_created(self, calibrator, tmp_calibration_dir):
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
                )
            ]
        )
        calibrator.calibrate_from_feedback(l8_feedback=l8, cycle_id="C0010")
        cal_file = tmp_calibration_dir / "calibrated_segments.json"
        assert cal_file.exists()

    def test_no_feedback_no_changes(self, calibrator):
        result = calibrator.calibrate_from_feedback(cycle_id="C0101")
        assert result == {}
