"""Tests for mcp_handlers — the stdlib-only, bridge-free endpoint logic.

The crash-proof contract under test:
  - record_learning_decision appends the canonical /decisions/learning schema
  - primary-append failure spools instead of losing the entry
  - flush_spool is deduped by decision_id and idempotent
  - concurrent writers never corrupt decisions.jsonl

All tests redirect the store via CORTEX_STATE_DIR (state_paths honors it at
call time), so nothing touches the real ~/.cortex.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import mcp_handlers


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    """Point the whole cortex store at a tmp dir."""
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    return tmp_path


def _lines(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ─── Schema ────────────────────────────────────────────────────────────


def test_record_matches_learning_route_schema(state_dir):
    """Entries carry the exact /decisions/learning schema keys."""
    result = mcp_handlers.record_learning_decision(
        decision="use WAL mode",
        context="shared sqlite stores",
        alternatives="file locks",
        rationale="cheapest safe option",
    )
    assert result["recorded"] is True
    assert "spooled" not in result
    assert result["decision_id"].startswith("dec_")

    entries = _lines(state_dir / "decisions.jsonl")
    assert len(entries) == 1
    entry = entries[0]
    assert entry["decision"] == "use WAL mode"
    assert entry["context"] == "shared sqlite stores"
    assert entry["alternatives"] == "file locks"
    assert entry["rationale"] == "cheapest safe option"
    assert entry["source"] == "mcp"
    assert entry["decision_id"] == result["decision_id"]
    assert "timestamp" in entry
    # No project passed -> no project key (back-compat with old entries).
    assert "project" not in entry


def test_record_includes_project_when_given(state_dir):
    mcp_handlers.record_learning_decision(decision="d", project="cortex")
    (entry,) = _lines(state_dir / "decisions.jsonl")
    assert entry["project"] == "cortex"


def test_decision_ids_unique_at_second_resolution(state_dir):
    """uuid ids fix the old dec_{int(time.time())} collision."""
    ids = {
        mcp_handlers.record_learning_decision(decision=f"d{i}")["decision_id"]
        for i in range(20)
    }
    assert len(ids) == 20


# ─── Spool fallback ────────────────────────────────────────────────────


def test_spool_on_primary_append_failure(state_dir, monkeypatch):
    def boom(path, entry):
        raise OSError("disk says no")

    monkeypatch.setattr(mcp_handlers, "_append_line", boom)
    result = mcp_handlers.record_learning_decision(decision="survive me")

    assert result["recorded"] is True
    assert result["spooled"] is True
    spool_files = list((state_dir / "spool").glob("decision-*.json"))
    assert len(spool_files) == 1
    entry = json.loads(spool_files[0].read_text())
    assert entry["decision"] == "survive me"
    assert mcp_handlers.spool_depth() == 1


def test_flush_spool_replays_and_dedups(state_dir, monkeypatch):
    # Spool two entries via forced failure. NB: flush_spool writes directly
    # (not via _append_line), so the opportunistic flush inside the second
    # record call would replay entry 1 — pre-create the spool files instead.
    def boom(path, entry):
        raise OSError("nope")

    with monkeypatch.context() as m:
        m.setattr(mcp_handlers, "_append_line", boom)
        m.setattr(mcp_handlers, "flush_spool", lambda: None)  # isolate spooling
        r1 = mcp_handlers.record_learning_decision(decision="first")
        r2 = mcp_handlers.record_learning_decision(decision="second")
    assert mcp_handlers.spool_depth() == 2

    result = mcp_handlers.flush_spool()
    assert result == {"flushed": 2, "skipped": 0, "remaining": 0}
    ids = {e["decision_id"] for e in _lines(state_dir / "decisions.jsonl")}
    assert ids == {r1["decision_id"], r2["decision_id"]}

    # Idempotent: a second flush is a no-op.
    assert mcp_handlers.flush_spool() == {"flushed": 0, "skipped": 0, "remaining": 0}

    # A stale spool file whose id already landed is skipped and removed.
    spool = state_dir / "spool"
    stale = spool / f"decision-{r1['decision_id']}.json"
    stale.write_text(json.dumps({"decision_id": r1["decision_id"], "decision": "dupe"}))
    result = mcp_handlers.flush_spool()
    assert result == {"flushed": 0, "skipped": 1, "remaining": 0}
    assert len(_lines(state_dir / "decisions.jsonl")) == 2  # no dupe appended


def test_record_opportunistically_flushes(state_dir, monkeypatch):
    def boom(path, entry):
        raise OSError("nope")

    with monkeypatch.context() as m:
        m.setattr(mcp_handlers, "_append_line", boom)
        spooled = mcp_handlers.record_learning_decision(decision="stuck")
    assert mcp_handlers.spool_depth() == 1

    ok = mcp_handlers.record_learning_decision(decision="healthy again")
    assert mcp_handlers.spool_depth() == 0
    ids = {e["decision_id"] for e in _lines(state_dir / "decisions.jsonl")}
    assert ids == {spooled["decision_id"], ok["decision_id"]}


# ─── Concurrency ───────────────────────────────────────────────────────


def test_concurrent_writers_produce_clean_jsonl(state_dir):
    """4 processes x 50 appends -> 200 parseable single-line entries."""
    script = (
        "import mcp_handlers\n"
        "for i in range(50):\n"
        "    mcp_handlers.record_learning_decision(decision=f'c{i}')\n"
    )
    repo_root = str(Path(__file__).resolve().parent.parent)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=repo_root,
            env={
                "PATH": "/usr/bin:/bin",
                "CORTEX_STATE_DIR": str(state_dir),
                "PYTHONPATH": repo_root,
            },
        )
        for _ in range(4)
    ]
    for p in procs:
        assert p.wait(timeout=60) == 0

    entries = _lines(state_dir / "decisions.jsonl")
    assert len(entries) == 200
    assert len({e["decision_id"] for e in entries}) == 200


# ─── Read handlers ─────────────────────────────────────────────────────


def test_read_outcomes_filters_and_orders(state_dir):
    outcomes = state_dir / "outcomes.jsonl"
    rows = [
        {"timestamp": "2026-01-01T00:00:00", "outcome": "success", "context": {"project": "a"}},
        {"timestamp": "2026-01-03T00:00:00", "outcome": "failed", "context": {"project": "b"}},
        {"timestamp": "2026-01-02T00:00:00", "outcome": "success", "context": {"project": "a"}},
    ]
    outcomes.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    all_result = mcp_handlers.read_outcomes()
    assert all_result["total"] == 3
    assert [e["timestamp"][:10] for e in all_result["outcomes"]] == [
        "2026-01-03",
        "2026-01-02",
        "2026-01-01",
    ]

    a_result = mcp_handlers.read_outcomes(project="A", limit=1)
    assert a_result["total"] == 2
    assert len(a_result["outcomes"]) == 1
    assert a_result["outcomes"][0]["timestamp"].startswith("2026-01-02")


def test_plans_progress_summarizes(state_dir):
    plans = state_dir / "plans"
    plans.mkdir()
    (plans / "p1.json").write_text(
        json.dumps(
            {
                "plan_id": "plan_x_1",
                "project": "x",
                "title": "T",
                "created_at": "2026-01-01",
                "items": [{"status": "done"}, {"status": "open"}, {"status": "done"}],
            }
        )
    )
    result = mcp_handlers.plans_progress()
    assert result["total"] == 1
    (summary,) = result["plans"]
    assert summary["item_count"] == 3
    assert summary["by_status"] == {"done": 2, "open": 1}
