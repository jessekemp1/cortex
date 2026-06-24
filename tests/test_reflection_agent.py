"""Tests for cortex/batch/reflection_agent.py (Phase 3)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta


from cortex.batch.reflection_agent import (
    ReflectionAgent,
    find_repeated_patterns,
    load_recent_outcomes,
    write_lessons_to_graph,
)


# ---------------------------------------------------------------------------
# test_load_recent_outcomes
# ---------------------------------------------------------------------------


def test_load_recent_outcomes_with_tmp_jsonl(tmp_path):
    """load_recent_outcomes returns records within the date window."""
    now = datetime.now()
    old = now - timedelta(days=10)

    records = [
        {
            "timestamp": now.isoformat(),
            "domain": "vortex",
            "outcome": "success",
            "recommendation_id": "r1",
            "recommendation_title": "T1",
            "followed": True,
            "confidence": 0.8,
        },
        {
            "timestamp": old.isoformat(),
            "domain": "cortex",
            "outcome": "failure",
            "recommendation_id": "r2",
            "recommendation_title": "T2",
            "followed": False,
            "confidence": 0.5,
        },
    ]
    jsonl = tmp_path / "outcomes.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in records))

    results = load_recent_outcomes(days=7, path=jsonl)
    assert len(results) == 1
    assert results[0]["domain"] == "vortex"


def test_load_recent_outcomes_missing_file(tmp_path):
    """Returns empty list when file does not exist."""
    results = load_recent_outcomes(path=tmp_path / "missing.jsonl")
    assert results == []


# ---------------------------------------------------------------------------
# test_find_repeated_patterns
# ---------------------------------------------------------------------------


def test_find_repeated_patterns_threshold():
    """Patterns with >= 3 occurrences are returned; below threshold are excluded."""
    outcomes = [{"domain": "vortex", "outcome": "success"} for _ in range(3)] + [
        {"domain": "cortex", "outcome": "failure"}
        for _ in range(2)  # below threshold
    ]

    patterns = find_repeated_patterns(outcomes, signals=[], threshold=3)

    keys = [p["key"] for p in patterns]
    assert "vortex:success" in keys
    assert "cortex:failure" not in keys


def test_find_repeated_patterns_count():
    """Pattern count reflects actual occurrences."""
    outcomes = [{"domain": "alpha", "outcome": "win"} for _ in range(5)]
    patterns = find_repeated_patterns(outcomes, signals=[], threshold=3)
    assert len(patterns) == 1
    assert patterns[0]["count"] == 5


def test_find_repeated_patterns_empty():
    """Empty outcomes returns empty list."""
    assert find_repeated_patterns([], [], threshold=3) == []


# ---------------------------------------------------------------------------
# test_run_dry_run
# ---------------------------------------------------------------------------


def test_run_dry_run_completes_without_api_call(tmp_path, monkeypatch):
    """dry_run=True completes and returns correct structure without API calls."""
    # Point file paths at tmp empty files
    import cortex.batch.reflection_agent as ra

    monkeypatch.setattr(ra, "OUTCOMES_FILE", tmp_path / "outcomes.jsonl")
    monkeypatch.setattr(ra, "SIGNAL_BUS_DB", tmp_path / "signal_bus.db")

    agent = ReflectionAgent()
    result = agent.run(dry_run=True)

    assert result["dry_run"] is True
    assert "date" in result
    assert "outcomes_read" in result
    assert "signals_read" in result
    assert "patterns_found" in result
    assert "lessons_added" in result
    assert result["model"] == "claude-haiku-4-5"
    # dry_run must not write to graph (lessons_added == 0)
    assert result["lessons_added"] == 0


# ---------------------------------------------------------------------------
# test_write_lessons_to_graph
# ---------------------------------------------------------------------------


def test_write_lessons_to_graph_creates_lesson_nodes(tmp_path):
    """write_lessons_to_graph creates LESSON nodes in ContextGraph."""
    lessons = [
        {
            "pattern_key": "vortex:success",
            "domain": "vortex",
            "outcome": "success",
            "lesson": "Deployments succeed when tests pass first.",
            "confidence": 0.9,
            "dry_run": False,
        }
    ]

    added = write_lessons_to_graph(lessons, storage_path=tmp_path / "graph")

    assert added == 1

    # Verify node persisted
    nodes_file = tmp_path / "graph" / "nodes.json"
    assert nodes_file.exists()
    nodes = json.loads(nodes_file.read_text())
    assert len(nodes) == 1
    assert nodes[0]["type"] == "lesson"
    assert "vortex:success" in nodes[0]["data"]["pattern_key"]


def test_write_lessons_to_graph_empty(tmp_path):
    """Empty lessons list returns 0 without error."""
    assert write_lessons_to_graph([], storage_path=tmp_path / "graph") == 0
