"""Tests for cortex/batch/nightly_reflection.py — no live API calls."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
CORTEX_ROOT = Path(__file__).parent.parent


def _make_queue(tmp_path: Path, entries: list[dict]) -> Path:
    q = tmp_path / "interaction_queue.jsonl"
    with q.open("w") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    return q


# ---------------------------------------------------------------------------
# load_todays_interactions
# ---------------------------------------------------------------------------


def test_gather_today_empty(tmp_path):
    """Empty queue returns empty list."""
    from batch.nightly_reflection import load_todays_interactions

    q = tmp_path / "queue.jsonl"
    # File doesn't exist
    assert load_todays_interactions(q) == []


def test_gather_today_filters_by_date(tmp_path):
    """Only today's prompt-type entries are returned."""
    from batch.nightly_reflection import load_todays_interactions

    today = date.today().isoformat()
    entries = [
        {"type": "prompt", "timestamp": f"{today}T10:00:00", "content": "hello"},
        {"type": "prompt", "timestamp": "2020-01-01T10:00:00", "content": "old"},
        {"type": "response", "timestamp": f"{today}T10:01:00", "content": "ignored"},
        {"type": "", "timestamp": f"{today}T09:00:00", "content": "legacy"},
    ]
    q = _make_queue(tmp_path, entries)
    result = load_todays_interactions(q)
    contents = [r["content"] for r in result]
    assert "hello" in contents
    assert "old" not in contents
    assert "ignored" not in contents
    assert "legacy" in contents


def test_gather_today_skips_bad_json(tmp_path):
    """Malformed lines are silently skipped."""
    from batch.nightly_reflection import load_todays_interactions

    today = date.today().isoformat()
    q = tmp_path / "queue.jsonl"
    q.write_text(
        f'{{"type":"prompt","timestamp":"{today}T10:00:00","content":"ok"}}\n'
        "NOT_JSON\n"
        f'{{"type":"prompt","timestamp":"{today}T11:00:00","content":"also ok"}}\n'
    )
    result = load_todays_interactions(q)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# synthesise_reflection
# ---------------------------------------------------------------------------


def test_synthesise_dry_run():
    """dry_run=True returns stub without calling API."""
    from batch.nightly_reflection import synthesise_reflection

    result = synthesise_reflection([], dry_run=True)
    assert result["dry_run"] is True
    assert "dry-run mode" in result["themes"][0]
    assert "error" not in result


def test_synthesise_no_interactions():
    """Empty interaction list with dry_run=False returns stub with no-data theme."""
    from batch.nightly_reflection import synthesise_reflection

    result = synthesise_reflection([], dry_run=False)
    assert result["interaction_count"] == 0
    assert any("no interactions" in t for t in result["themes"])


def test_synthesise_with_mock_client():
    """Mocked Anthropic client returns parsed reflection."""
    from batch.nightly_reflection import synthesise_reflection

    today = date.today().isoformat()
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "date": today,
                    "themes": ["testing"],
                    "decisions_made": ["use mocks"],
                    "blockers_surfaced": [],
                    "patterns_noticed": [],
                    "tomorrow_priorities": ["ship it"],
                    "confidence": 0.8,
                }
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    interactions = [{"type": "prompt", "timestamp": f"{today}T10:00:00", "content": "test"}]
    result = synthesise_reflection(interactions, anthropic_client=mock_client)

    mock_client.messages.create.assert_called_once()
    assert result["themes"] == ["testing"]
    assert result["confidence"] == 0.8
    assert "error" not in result


def test_synthesise_handles_api_error():
    """API error is captured in 'error' key, not raised."""
    from batch.nightly_reflection import synthesise_reflection

    today = date.today().isoformat()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("network timeout")

    interactions = [{"type": "prompt", "timestamp": f"{today}T10:00:00", "content": "test"}]
    result = synthesise_reflection(interactions, anthropic_client=mock_client)
    assert "error" in result
    assert "network timeout" in result["error"]


def test_synthesise_handles_bad_json_response():
    """Malformed JSON from API captured in 'error', not raised."""
    from batch.nightly_reflection import synthesise_reflection

    today = date.today().isoformat()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not json at all")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    interactions = [{"type": "prompt", "timestamp": f"{today}T10:00:00", "content": "test"}]
    result = synthesise_reflection(interactions, anthropic_client=mock_client)
    assert "error" in result


# ---------------------------------------------------------------------------
# save_reflection
# ---------------------------------------------------------------------------


def test_save_reflection(tmp_path, monkeypatch):
    """Reflection is saved to correct path."""
    from batch import nightly_reflection as nr_mod

    monkeypatch.setattr(nr_mod, "REFLECTIONS_DIR", tmp_path / "reflections")

    reflection = {
        "date": date.today().isoformat(),
        "themes": ["test"],
        "decisions_made": [],
        "blockers_surfaced": [],
        "patterns_noticed": [],
        "tomorrow_priorities": [],
        "confidence": 0.5,
    }
    out = nr_mod.save_reflection(reflection)
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert loaded["themes"] == ["test"]


# ---------------------------------------------------------------------------
# NightlyReflection class
# ---------------------------------------------------------------------------


def test_run_dry_run(tmp_path, monkeypatch):
    """NightlyReflection.run(dry_run=True) succeeds and returns dict."""
    from batch import nightly_reflection as nr_mod

    monkeypatch.setattr(nr_mod, "REFLECTIONS_DIR", tmp_path / "reflections")

    q = tmp_path / "queue.jsonl"
    nr = nr_mod.NightlyReflection(interaction_queue=q)
    result = nr.run(dry_run=True)

    assert isinstance(result, dict)
    assert result.get("dry_run") is True
    # Should NOT have raised even though no real API


def test_run_with_mock_client(tmp_path, monkeypatch):
    """NightlyReflection.run() with injected client calls API and saves."""
    from batch import nightly_reflection as nr_mod

    monkeypatch.setattr(nr_mod, "REFLECTIONS_DIR", tmp_path / "reflections")

    today = date.today().isoformat()
    q = _make_queue(
        tmp_path,
        [{"type": "prompt", "timestamp": f"{today}T10:00:00", "content": "test prompt"}],
    )

    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "date": today,
                    "themes": ["mocked"],
                    "decisions_made": [],
                    "blockers_surfaced": [],
                    "patterns_noticed": [],
                    "tomorrow_priorities": [],
                    "confidence": 0.9,
                }
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    # Patch seed so we don't need ChromaDB
    monkeypatch.setattr(nr_mod, "seed_reflection_to_memory", lambda r: False)

    nr = nr_mod.NightlyReflection(anthropic_client=mock_client, interaction_queue=q)
    result = nr.run(dry_run=False)

    assert result["themes"] == ["mocked"]
    saved = tmp_path / "reflections" / f"{today}.json"
    assert saved.exists()


def test_reflect_status_no_data(tmp_path, monkeypatch):
    """status() returns a string when no reflections exist."""
    from batch import nightly_reflection as nr_mod

    monkeypatch.setattr(nr_mod, "REFLECTIONS_DIR", tmp_path / "reflections")

    nr = nr_mod.NightlyReflection()
    status = nr.status()
    assert isinstance(status, str)
    assert "no reflections" in status


def test_reflect_status_with_data(tmp_path, monkeypatch):
    """status() returns summary of last reflection."""
    from batch import nightly_reflection as nr_mod

    monkeypatch.setattr(nr_mod, "REFLECTIONS_DIR", tmp_path / "reflections")

    today = date.today().isoformat()
    reflection = {
        "date": today,
        "themes": ["ship it", "tests green"],
        "interaction_count": 5,
        "decisions_made": [],
        "blockers_surfaced": [],
        "patterns_noticed": [],
        "tomorrow_priorities": [],
        "confidence": 0.7,
    }
    nr = nr_mod.NightlyReflection()
    nr_mod.save_reflection(reflection)

    status = nr.status()
    assert today in status
    assert "ship it" in status
