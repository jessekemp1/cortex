"""Shared fixtures for synthetic tests."""

from pathlib import Path

import pytest

# Calibration file path that the flywheel may create during L8/L9 testing.
# We clean it up so it doesn't contaminate other tests that check CBA baselines
# via get_behavior().
_CALIBRATED_FILE = Path.home() / ".cortex" / "synthetic" / "pupil" / "calibrated_segments.json"


@pytest.fixture(autouse=True)
def _clean_calibration_file():
    """Remove any calibration file before and after each test."""
    _CALIBRATED_FILE.unlink(missing_ok=True)
    yield
    _CALIBRATED_FILE.unlink(missing_ok=True)
