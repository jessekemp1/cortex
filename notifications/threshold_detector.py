"""
Threshold-crossing event detector for Cortex notifications.

Monitors key metrics and fires alerts when thresholds are crossed.
Designed to be called periodically (e.g., from launchd or cron).
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

THRESHOLD_STATE_FILE = Path.home() / ".cortex" / "threshold_state.json"


@dataclass
class ThresholdEvent:
    metric: str  # e.g., "bridge_status", "batch_failed_count"
    previous_value: str  # previous state
    current_value: str  # current state
    direction: str  # "crossed_above", "crossed_below", "state_change"
    severity: str  # "CRITICAL", "WARNING", "INFO"
    message: str  # human-readable description


def _load_state(state_file: Optional[Path] = None) -> dict:
    """Load previous threshold state from disk."""
    path = state_file or THRESHOLD_STATE_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: dict, state_file: Optional[Path] = None) -> None:
    """Save threshold state to disk."""
    path = state_file or THRESHOLD_STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def check_bridge_status(state_file: Optional[Path] = None) -> Optional[ThresholdEvent]:
    """Check if bridge status has transitioned."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "3", "http://localhost:8765/health"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        current = "healthy" if result.returncode == 0 and "healthy" in result.stdout else "down"
    except Exception:
        current = "down"

    state = _load_state(state_file)
    previous = state.get("bridge_status", "unknown")

    if previous != current and previous != "unknown":
        event = ThresholdEvent(
            metric="bridge_status",
            previous_value=previous,
            current_value=current,
            direction="state_change",
            severity="CRITICAL" if current == "down" else "INFO",
            message=f"Bridge status: {previous} → {current}",
        )
        state["bridge_status"] = current
        _save_state(state, state_file)
        return event

    state["bridge_status"] = current
    _save_state(state, state_file)
    return None


def check_batch_queue_health(state_file: Optional[Path] = None) -> Optional[ThresholdEvent]:
    """Check if batch failure count has crossed thresholds."""
    batch_dir = Path.home() / ".cortex" / "batch"
    try:
        failed_count = 0
        if batch_dir.exists():
            failed_count = len(list(batch_dir.glob("*failed*"))) + len(
                list(batch_dir.glob("*error*"))
            )
    except Exception:
        return None

    state = _load_state(state_file)
    previous_count = state.get("batch_failed_count", 0)

    # Alert if failures jumped by more than 100
    if failed_count > previous_count + 100:
        event = ThresholdEvent(
            metric="batch_failed_count",
            previous_value=str(previous_count),
            current_value=str(failed_count),
            direction="crossed_above",
            severity="WARNING",
            message=f"Batch failures increased: {previous_count} → {failed_count} (+{failed_count - previous_count})",
        )
        state["batch_failed_count"] = failed_count
        _save_state(state, state_file)
        return event

    state["batch_failed_count"] = failed_count
    _save_state(state, state_file)
    return None


def check_test_regression(state_file: Optional[Path] = None) -> Optional[ThresholdEvent]:
    """Check if test count dropped (regression indicator)."""
    metrics_file = Path.home() / ".cortex" / "metrics" / "tests.json"
    try:
        if not metrics_file.exists():
            return None
        data = json.loads(metrics_file.read_text())
        current_total = sum(v for v in data.values() if isinstance(v, int))
    except Exception:
        return None

    state = _load_state(state_file)
    previous_total = state.get("test_total", 0)

    if previous_total > 0 and current_total < previous_total - 10:
        event = ThresholdEvent(
            metric="test_total",
            previous_value=str(previous_total),
            current_value=str(current_total),
            direction="crossed_below",
            severity="WARNING",
            message=f"Test count dropped: {previous_total} → {current_total} (-{previous_total - current_total})",
        )
        state["test_total"] = current_total
        _save_state(state, state_file)
        return event

    state["test_total"] = current_total
    _save_state(state, state_file)
    return None


def run_all_checks(state_file: Optional[Path] = None) -> list:
    """Run all threshold checks and return events that fired."""
    checks = [
        lambda: check_bridge_status(state_file),
        lambda: check_batch_queue_health(state_file),
        lambda: check_test_regression(state_file),
    ]
    events = []
    for check in checks:
        try:
            event = check()
            if event is not None:
                events.append(event)
        except Exception:
            continue
    return events
