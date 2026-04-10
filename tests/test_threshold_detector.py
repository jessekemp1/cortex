"""
Tests for cortex/notifications/threshold_detector.py
"""

import json
from unittest.mock import MagicMock, patch

from notifications.threshold_detector import (
    ThresholdEvent,
    _load_state,
    _save_state,
    check_batch_queue_health,
    check_bridge_status,
    check_test_regression,
    run_all_checks,
)


# ── state helpers ─────────────────────────────────────────────────────────────


def test_load_state_empty(tmp_path):
    """Fresh state file path that doesn't exist returns empty dict."""
    state_file = tmp_path / "threshold_state.json"
    result = _load_state(state_file)
    assert result == {}


def test_save_and_load_state(tmp_path):
    """Roundtrip: save then load returns same data."""
    state_file = tmp_path / "threshold_state.json"
    data = {"bridge_status": "healthy", "batch_failed_count": 42}
    _save_state(data, state_file)
    result = _load_state(state_file)
    assert result == data


# ── bridge status ─────────────────────────────────────────────────────────────


def test_bridge_status_change_fires_event(tmp_path):
    """Transition healthy → down fires a CRITICAL event."""
    state_file = tmp_path / "state.json"
    _save_state({"bridge_status": "healthy"}, state_file)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch("notifications.threshold_detector.subprocess.run", return_value=mock_result):
        event = check_bridge_status(state_file)

    assert event is not None
    assert event.metric == "bridge_status"
    assert event.previous_value == "healthy"
    assert event.current_value == "down"
    assert event.severity == "CRITICAL"
    assert event.direction == "state_change"


def test_bridge_status_no_change(tmp_path):
    """Same state does not fire an event."""
    state_file = tmp_path / "state.json"
    _save_state({"bridge_status": "healthy"}, state_file)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"status": "healthy"}'

    with patch("notifications.threshold_detector.subprocess.run", return_value=mock_result):
        event = check_bridge_status(state_file)

    assert event is None


def test_bridge_status_first_check_no_event(tmp_path):
    """First check (unknown → healthy) does not fire an event."""
    state_file = tmp_path / "state.json"
    # No prior state

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"status": "healthy"}'

    with patch("notifications.threshold_detector.subprocess.run", return_value=mock_result):
        event = check_bridge_status(state_file)

    assert event is None
    # But state is now written
    state = _load_state(state_file)
    assert state["bridge_status"] == "healthy"


# ── batch queue health ────────────────────────────────────────────────────────


def test_batch_threshold_fires_on_jump(tmp_path):
    """Jump of >100 failures fires a WARNING event."""
    state_file = tmp_path / "state.json"
    _save_state({"batch_failed_count": 0}, state_file)

    # Create 200 fake failed files under .cortex/batch (matches Path.home() / ".cortex" / "batch")
    batch_dir = tmp_path / ".cortex" / "batch"
    batch_dir.mkdir(parents=True)
    for i in range(200):
        (batch_dir / f"task_{i}_failed.json").touch()

    with patch("notifications.threshold_detector.Path.home", return_value=tmp_path):
        event = check_batch_queue_health(state_file)

    assert event is not None
    assert event.metric == "batch_failed_count"
    assert event.severity == "WARNING"
    assert event.direction == "crossed_above"
    assert int(event.current_value) == 200


def test_batch_threshold_small_change_no_event(tmp_path):
    """Small increase in failures does not fire an event."""
    state_file = tmp_path / "state.json"
    _save_state({"batch_failed_count": 0}, state_file)

    batch_dir = tmp_path / ".cortex" / "batch"
    batch_dir.mkdir(parents=True)
    for i in range(5):
        (batch_dir / f"task_{i}_failed.json").touch()

    with patch("notifications.threshold_detector.Path.home", return_value=tmp_path):
        event = check_batch_queue_health(state_file)

    assert event is None


# ── test regression ───────────────────────────────────────────────────────────


def test_test_regression_fires(tmp_path):
    """Drop of >10 tests fires a WARNING event."""
    state_file = tmp_path / "state.json"
    _save_state({"test_total": 1000}, state_file)

    metrics_dir = tmp_path / ".cortex" / "metrics"
    metrics_dir.mkdir(parents=True)
    metrics_file = metrics_dir / "tests.json"
    metrics_file.write_text(json.dumps({"cortex": 500, "vortex": 480}))

    with patch("notifications.threshold_detector.Path.home", return_value=tmp_path):
        event = check_test_regression(state_file)

    assert event is not None
    assert event.metric == "test_total"
    assert event.severity == "WARNING"
    assert event.direction == "crossed_below"
    assert event.previous_value == "1000"
    assert event.current_value == "980"


def test_test_regression_increase_no_event(tmp_path):
    """Test count going up does not fire an event."""
    state_file = tmp_path / "state.json"
    _save_state({"test_total": 900}, state_file)

    metrics_dir = tmp_path / ".cortex" / "metrics"
    metrics_dir.mkdir(parents=True)
    metrics_file = metrics_dir / "tests.json"
    metrics_file.write_text(json.dumps({"cortex": 600, "vortex": 500}))

    with patch("notifications.threshold_detector.Path.home", return_value=tmp_path):
        event = check_test_regression(state_file)

    assert event is None


# ── run_all_checks ────────────────────────────────────────────────────────────


def test_run_all_checks_returns_list(tmp_path):
    """run_all_checks always returns a list (may be empty)."""
    state_file = tmp_path / "state.json"
    result = run_all_checks(state_file)
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, ThresholdEvent)
