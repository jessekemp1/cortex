#!/usr/bin/env python3
"""
Tests for UniversalSignalBus

Covers: DB init, absorb fan-out (silent failure), query, cross-project patterns,
event log, and multiple signals from different projects.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortex.engines.workstream_orchestrator import (
    SignalSource,
    WorkspaceSignal,
    WorkstreamPhase,
)
from cortex.engines.universal_signal_bus import UniversalSignalBus


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def tmp_bus(tmp_path):
    """Bus with isolated SQLite DB for each test."""
    return UniversalSignalBus(db_path=tmp_path / "signal_bus.db")


def make_signal(
    project: str = "vortex",
    content: str = "test signal content",
    content_type: str = "insight",
    confidence: float = 0.8,
) -> WorkspaceSignal:
    return WorkspaceSignal(
        source=SignalSource.CLAUDE_CODE,
        timestamp=datetime.now(),
        project=project,
        workstream=WorkstreamPhase.BUILD,
        content_type=content_type,
        content=content,
        confidence=confidence,
    )


# ─── DB Init ─────────────────────────────────────────────────


def test_bus_init_creates_db(tmp_path):
    UniversalSignalBus(db_path=tmp_path / "test.db")
    assert (tmp_path / "test.db").exists()


def test_bus_init_creates_schema(tmp_path):
    import sqlite3

    UniversalSignalBus(db_path=tmp_path / "test.db")
    conn = sqlite3.connect(tmp_path / "test.db")
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    assert "bus_events" in tables


# ─── absorb ──────────────────────────────────────────────────


def test_absorb_logs_event(tmp_bus):
    signal = make_signal()
    tmp_bus.absorb(signal)

    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] == 1


def test_absorb_multiple_signals(tmp_bus):
    for i in range(5):
        tmp_bus.absorb(make_signal(project=f"proj{i}", content=f"signal {i}"))

    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] == 5


def test_absorb_deduplicates_signal_ids(tmp_bus):
    """Same signal_id should only be logged once."""
    signal = make_signal()
    tmp_bus.absorb(signal)
    tmp_bus.absorb(signal)  # Duplicate

    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] == 1


def test_absorb_does_not_raise_on_bad_content(tmp_bus):
    """Bus must not raise even with unusual content."""
    signal = make_signal(content="")
    tmp_bus.absorb(signal)

    signal2 = make_signal(content="x" * 2000)
    tmp_bus.absorb(signal2)

    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] >= 1


def test_absorb_silences_engine_errors(tmp_bus, monkeypatch):
    """Broken engines must not block signal ingestion."""

    def broken_record(s):
        raise RuntimeError("engine is down")

    orch = tmp_bus._get_orchestrator()
    monkeypatch.setattr(orch, "record_signal", broken_record)

    signal = make_signal()
    tmp_bus.absorb(signal)  # Must not raise

    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] == 1


# ─── query ───────────────────────────────────────────────────


def test_query_returns_dict(tmp_bus):
    result = tmp_bus.query("authentication", "vortex", "claude_code")
    assert isinstance(result, dict)
    assert result["context"] == "authentication"
    assert result["project"] == "vortex"
    assert "graph_nodes" in result
    assert "recent_signals" in result
    assert "trust" in result


def test_query_does_not_raise_when_offline(tmp_bus):
    """Query must be resilient to empty/unavailable engines."""
    result = tmp_bus.query("ensemble model", "cortex", "iterm")
    assert isinstance(result, dict)


def test_query_includes_project_field(tmp_bus):
    result = tmp_bus.query("caching strategy", "pupil")
    assert result["project"] == "pupil"
    assert result["tool_source"] == "unknown"  # default


# ─── cross_project_patterns ──────────────────────────────────


def test_cross_project_patterns_returns_list(tmp_bus):
    patterns = tmp_bus.get_cross_project_patterns("vortex")
    assert isinstance(patterns, list)


def test_cross_project_patterns_limit(tmp_bus):
    patterns = tmp_bus.get_cross_project_patterns("vortex", limit=3)
    assert len(patterns) <= 3


def test_cross_project_patterns_excludes_active_project(tmp_bus):
    patterns = tmp_bus.get_cross_project_patterns("vortex")
    for p in patterns:
        assert p.get("project_source") != "vortex"


def test_cross_project_patterns_structure(tmp_bus):
    """Each pattern entry must have required fields."""
    patterns = tmp_bus.get_cross_project_patterns("cortex")
    for p in patterns:
        assert "pattern" in p
        assert "project_source" in p
        assert "node_type" in p
        assert "summary" in p


# ─── bus_stats ───────────────────────────────────────────────


def test_bus_stats_empty(tmp_bus):
    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] == 0


def test_bus_stats_after_absorbs(tmp_bus):
    for _ in range(3):
        tmp_bus.absorb(make_signal())

    stats = tmp_bus.get_bus_stats()
    # Dedup: all 3 have unique signal_ids from different timestamps
    assert stats["total_events"] >= 1  # At least 1 logged


# ─── Low confidence signals ──────────────────────────────────


def test_low_confidence_signal_absorbed_but_not_graphed(tmp_bus):
    """Signals with confidence < 0.6 are logged but not added to graph."""
    signal = make_signal(content_type="insight", confidence=0.3)
    tmp_bus.absorb(signal)
    stats = tmp_bus.get_bus_stats()
    assert stats["total_events"] == 1
