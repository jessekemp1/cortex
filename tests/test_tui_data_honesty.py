"""Honesty tests for the TUI shared data layer (Workstream C, C1).

`tui.data._collect_learning()` used to return a hardcoded accuracy of 91.0%
and total_tracked=84 regardless of any real data. These tests lock the fix:
the learning number is DERIVED from the real ~/.cortex/outcomes.jsonl log, and
falls back to an honest empty state (accuracy_pct=None, collecting=True) when
there is nothing to score — never a fabricated percentage.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

import tui.data as data


@pytest.fixture()
def outcomes_dir(tmp_path, monkeypatch):
    """Redirect tui.data's CORTEX_DIR at a tmp dir."""
    monkeypatch.setattr(data, "CORTEX_DIR", tmp_path)
    return tmp_path


def _write_outcomes(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_no_outcomes_file_is_honest_empty(outcomes_dir):
    """No log at all → None accuracy, collecting=True. NOT 91.0%."""
    lh = data._collect_learning()
    assert lh.accuracy_pct is None
    assert lh.total_tracked == 0
    assert lh.collecting is True


def test_accuracy_is_derived_not_hardcoded(outcomes_dir):
    """Two followed outcomes (success + partial) → 75.0%, computed from data."""
    now = datetime.now().isoformat()
    _write_outcomes(
        outcomes_dir / "outcomes.jsonl",
        [
            {"timestamp": now, "followed": True, "outcome": "success"},
            {"timestamp": now, "followed": True, "outcome": "partial"},
        ],
    )
    lh = data._collect_learning()
    assert lh.accuracy_pct == 75.0  # (1.0 + 0.5) / 2 * 100 — never the old 91.0
    assert lh.total_tracked == 2
    assert lh.collecting is False


def test_outcomes_but_none_followed_is_honest(outcomes_dir):
    """Outcomes exist but none were followed → nothing to score honestly."""
    now = datetime.now().isoformat()
    _write_outcomes(
        outcomes_dir / "outcomes.jsonl",
        [{"timestamp": now, "followed": False, "outcome": "success"}],
    )
    lh = data._collect_learning()
    assert lh.accuracy_pct is None
    assert lh.total_tracked == 1
    assert lh.collecting is True


def test_all_failed_reports_zero_not_fake(outcomes_dir):
    """All followed outcomes failed → honest 0.0%, proving zeros aren't masked."""
    now = datetime.now().isoformat()
    _write_outcomes(
        outcomes_dir / "outcomes.jsonl",
        [
            {"timestamp": now, "followed": True, "outcome": "failed"},
            {"timestamp": now, "followed": True, "outcome": "failed"},
        ],
    )
    lh = data._collect_learning()
    assert lh.accuracy_pct == 0.0
    assert lh.collecting is False
