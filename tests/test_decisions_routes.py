"""Route-level tests for the two /decisions endpoints.

These exercise the FastAPI routes directly via TestClient (no running bridge),
asserting the decision is actually persisted — not merely that a call returns
*something*. This catches the class of regression where the learning-loop
recorder (`cortex_record_decision` MCP tool -> POST /decisions/learning) got
silently shadowed by the Co-Navigator scenario recorder on /decisions/record.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes.decisions as decisions_mod
from api.routes.decisions import router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """App with the decisions router and the whole store pointed at a temp dir.

    /decisions/record writes via the module-level DECISIONS_FILE constant;
    /decisions/learning delegates to mcp_handlers, which resolves paths through
    CORTEX_STATE_DIR at call time — redirect both so neither touches ~/.cortex.
    """
    tmp_file = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(decisions_mod, "DECISIONS_FILE", tmp_file)
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), tmp_file


def test_learning_decision_is_recorded(client):
    """POST /decisions/learning with the MCP-tool schema persists a learning-loop entry."""
    c, tmp_file = client
    resp = c.post(
        "/decisions/learning",
        json={
            "decision": "Put cortex-dbx on hold",
            "context": "focus on shipping cortex",
            "alternatives": "hard stop; freeze dev only",
            "rationale": "soft pause keeps resume cheap",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recorded"] is True
    assert body["decision_id"].startswith("dec_")

    lines = [l for l in tmp_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["decision"] == "Put cortex-dbx on hold"
    assert entry["context"] == "focus on shipping cortex"
    assert entry["source"] == "mcp"
    # Canonical learning-loop schema — what cortex_intelligence reads.
    assert set(entry) >= {
        "decision_id", "decision", "context", "alternatives", "rationale", "timestamp", "source",
    }


def test_learning_decision_requires_only_decision(client):
    """`decision` is the sole required field; the rest default to empty."""
    c, tmp_file = client
    resp = c.post("/decisions/learning", json={"decision": "minimal"})
    assert resp.status_code == 200, resp.text
    entry = json.loads(tmp_file.read_text().splitlines()[0])
    assert entry["decision"] == "minimal"
    assert entry["context"] == ""


def test_learning_decision_rejects_empty_body(client):
    """Missing `decision` -> 422 (Pydantic validation)."""
    c, _ = client
    assert c.post("/decisions/learning", json={}).status_code == 422


def test_two_decision_schemas_stay_separate(client):
    """The learning schema must NOT be accepted by the Co-Navigator /decisions/record,
    and vice-versa — proving the two recorders are wired to distinct paths."""
    c, _ = client
    # Learning payload hitting the scenario route -> 422 (missing prediction_id, ...).
    assert c.post("/decisions/record", json={"decision": "x"}).status_code == 422
    # Scenario payload hitting the learning route -> 422 (missing decision).
    scenario = {
        "prediction_id": "p1",
        "scenario_chosen": "A",
        "scenario_name": "ship now",
        "domain": "release",
    }
    assert c.post("/decisions/learning", json=scenario).status_code == 422
    # ...but the scenario payload on its own route still works (no regression there).
    assert c.post("/decisions/record", json=scenario).status_code == 200
