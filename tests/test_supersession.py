#!/usr/bin/env python3
"""Tests for explicit decision supersession (P1 curation).

When a decision supersedes a prior one, the writer appends the new entry AND a
tombstone marking the old id superseded — append-only, never mutating the
original line. The retriever drops superseded ids from recall (tested in
test_hybrid_retriever.py).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_handlers


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    return tmp_path


def _lines(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_supersede_appends_tombstone(state_dir):
    old = mcp_handlers.record_learning_decision(decision="original decision about X")
    old_id = old["decision_id"]

    new = mcp_handlers.record_learning_decision(
        decision="revised decision about X, superseding the earlier call",
        supersedes=old_id,
    )
    new_id = new["decision_id"]

    entries = _lines(state_dir / "decisions.jsonl")
    # original + new + tombstone = 3 lines
    assert len(entries) == 3

    # new entry links forward
    new_entry = next(e for e in entries if e.get("decision_id") == new_id and "superseded_by" not in e)
    assert new_entry["supersedes"] == old_id

    # tombstone marks the old id superseded
    tombstone = next(e for e in entries if e.get("superseded_by") == new_id)
    assert tombstone["decision_id"] == old_id
    assert tombstone["source"] == "supersede"


def test_original_line_never_mutated(state_dir):
    old = mcp_handlers.record_learning_decision(decision="pristine original")
    old_id = old["decision_id"]
    original_line = (state_dir / "decisions.jsonl").read_text().splitlines()[0]

    mcp_handlers.record_learning_decision(decision="replacement", supersedes=old_id)

    # The first physical line is byte-identical (append-only, no rewrite).
    after_first_line = (state_dir / "decisions.jsonl").read_text().splitlines()[0]
    assert after_first_line == original_line


def test_no_supersedes_no_tombstone(state_dir):
    mcp_handlers.record_learning_decision(decision="standalone decision, supersedes nothing")
    entries = _lines(state_dir / "decisions.jsonl")
    assert len(entries) == 1
    assert "supersedes" not in entries[0]
    assert all("superseded_by" not in e for e in entries)
