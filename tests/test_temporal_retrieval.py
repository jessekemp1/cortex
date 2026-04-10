"""Tests for cortex/memory/temporal.py — temporal retrieval."""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory.temporal import TemporalQuery, parse_window, _parse_ts


# ---------------------------------------------------------------------------
# parse_window
# ---------------------------------------------------------------------------


def test_parse_window_relative_days():
    start, end = parse_window(since="3d")
    assert start is not None
    assert end is not None
    assert (end - start).days == 3 or (end - start).total_seconds() / 3600 > 70
    assert end > start


def test_parse_window_relative_hours():
    start, end = parse_window(since="6h")
    assert start is not None
    diff_hours = (end - start).total_seconds() / 3600
    assert 5.9 <= diff_hours <= 6.1


def test_parse_window_absolute_date():
    start, end = parse_window(since="2026-01-01", until="2026-01-07")
    assert start.year == 2026
    assert start.month == 1
    assert start.day == 1
    assert end.day == 7


def test_parse_window_yesterday():
    start, end = parse_window(since="yesterday")
    assert start is not None
    # yesterday's start should be 1+ day in the past
    assert (datetime.now(tz=timezone.utc) - start).days >= 1


def test_parse_window_today():
    from datetime import date

    start, end = parse_window(since="today")
    assert start is not None
    # parse_window uses date.today() (local time) — compare against local date
    assert start.date() == date.today()


def test_parse_window_none_returns_none_start():
    start, end = parse_window()
    assert start is None
    assert end is not None  # defaults to now


def test_parse_window_invalid_raises():
    with pytest.raises(ValueError, match="Cannot parse"):
        parse_window(since="not-a-date-or-offset")


def test_parse_window_last_weekday():
    # "last monday" etc. should parse without error
    start, end = parse_window(since="last monday")
    assert start is not None
    # Must be a monday and in the past
    assert start.weekday() == 0


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------


def test_parse_ts_iso_with_offset():
    dt = _parse_ts("2026-04-09T10:00:00+00:00")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_ts_iso_z_suffix():
    dt = _parse_ts("2026-04-09T10:00:00Z")
    assert dt is not None


def test_parse_ts_naive_gets_utc():
    dt = _parse_ts("2026-04-09T10:00:00")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_ts_empty():
    assert _parse_ts("") is None
    assert _parse_ts(None) is None


# ---------------------------------------------------------------------------
# TemporalQuery — file-based tests using tmp_path
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, entries: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _make_cortex_home(tmp_path: Path) -> Path:
    """Set up a fake ~/.cortex structure."""
    home = tmp_path / "cortex_home"
    home.mkdir()
    return home


def test_query_interactions_within_window(tmp_path):
    home = _make_cortex_home(tmp_path)
    now = datetime.now(tz=timezone.utc)
    entries = [
        {
            "type": "prompt_received",
            "queued_at": (now - timedelta(hours=2)).isoformat(),
            "prompt": "recent",
        },
        {
            "type": "prompt_received",
            "queued_at": (now - timedelta(days=5)).isoformat(),
            "prompt": "old",
        },
    ]
    _write_jsonl(home / "interaction_queue.jsonl", entries)

    tq = TemporalQuery(cortex_home=home)
    results = tq.query(since="1d", sources=["interaction"])
    assert len(results) == 1
    assert results[0]["prompt"] == "recent"


def test_query_returns_sorted_by_recency(tmp_path):
    home = _make_cortex_home(tmp_path)
    now = datetime.now(tz=timezone.utc)
    entries = [
        {
            "type": "prompt_received",
            "queued_at": (now - timedelta(hours=3)).isoformat(),
            "prompt": "older",
        },
        {
            "type": "prompt_received",
            "queued_at": (now - timedelta(hours=1)).isoformat(),
            "prompt": "newer",
        },
    ]
    _write_jsonl(home / "interaction_queue.jsonl", entries)

    tq = TemporalQuery(cortex_home=home)
    results = tq.query(since="1d", sources=["interaction"])
    assert results[0]["prompt"] == "newer"
    assert results[1]["prompt"] == "older"


def test_query_text_filter(tmp_path):
    home = _make_cortex_home(tmp_path)
    now = datetime.now(tz=timezone.utc)
    entries = [
        {"type": "prompt_received", "queued_at": now.isoformat(), "prompt": "about chromadb"},
        {"type": "prompt_received", "queued_at": now.isoformat(), "prompt": "unrelated topic"},
    ]
    _write_jsonl(home / "interaction_queue.jsonl", entries)

    tq = TemporalQuery(cortex_home=home)
    results = tq.query(text="chromadb", sources=["interaction"])
    assert len(results) == 1
    assert "chromadb" in results[0]["prompt"]


def test_query_reflections(tmp_path):
    home = _make_cortex_home(tmp_path)
    reflections_dir = home / "reflections"
    reflections_dir.mkdir()
    today = datetime.now(tz=timezone.utc).date().isoformat()
    (reflections_dir / f"{today}.json").write_text(
        json.dumps({"date": today, "themes": ["testing"], "confidence": 0.9})
    )

    tq = TemporalQuery(cortex_home=home)
    results = tq.query(since="1d", sources=["reflection"])
    assert len(results) == 1
    assert results[0]["themes"] == ["testing"]


def test_query_empty_directory(tmp_path):
    home = _make_cortex_home(tmp_path)
    tq = TemporalQuery(cortex_home=home)
    results = tq.query(since="7d")
    assert results == []


def test_query_limit(tmp_path):
    home = _make_cortex_home(tmp_path)
    now = datetime.now(tz=timezone.utc)
    entries = [
        {
            "type": "prompt_received",
            "queued_at": (now - timedelta(minutes=i)).isoformat(),
            "prompt": f"p{i}",
        }
        for i in range(10)
    ]
    _write_jsonl(home / "interaction_queue.jsonl", entries)

    tq = TemporalQuery(cortex_home=home)
    results = tq.query(since="1d", sources=["interaction"], limit=3)
    assert len(results) == 3


def test_summarise_returns_by_source(tmp_path):
    home = _make_cortex_home(tmp_path)
    now = datetime.now(tz=timezone.utc)
    entries = [
        {"type": "prompt_received", "queued_at": now.isoformat(), "prompt": "x"},
    ]
    _write_jsonl(home / "interaction_queue.jsonl", entries)
    (home / "reflections").mkdir()
    today = now.date().isoformat()
    (home / "reflections" / f"{today}.json").write_text(
        json.dumps({"date": today, "themes": ["y"]})
    )

    tq = TemporalQuery(cortex_home=home)
    summary = tq.summarise(since="1d")
    assert summary["by_source"].get("interaction", 0) >= 1
    assert summary["by_source"].get("reflection", 0) >= 1
    assert summary["total"] >= 2
