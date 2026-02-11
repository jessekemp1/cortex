"""Shared fixtures for standalone Pupil tests."""

from pathlib import Path

import pytest


_CALIBRATED_FILE = Path.home() / ".cortex" / "synthetic" / "pupil" / "calibrated_segments.json"


@pytest.fixture(autouse=True)
def _clean_calibration_file():
    """Remove any calibration file before and after each test."""
    _CALIBRATED_FILE.unlink(missing_ok=True)
    yield
    _CALIBRATED_FILE.unlink(missing_ok=True)
