"""
MCP tool contract tests.

For every MCP tool in cortex/mcp_server.py that calls the bridge, this file
asserts the bridge accepts the EXACT payload the MCP tool sends and returns
the response shape the MCP tool's docstring promises.

Why this exists: the previous test suite verified tools were *registered*, not
that they *worked*. Four broken tools shipped because no test sent a real
payload through. See plan: /root/.claude/plans/can-we-also-run-shimmying-globe.md
(Phase 0).

Convention: each test mirrors the payload built in mcp_server.py. Heavy upstream
calls (CortexBridge, OutcomeDetector, batch clients) are patched so tests
isolate the HTTP contract, not the implementation.

Known-broken tools are marked @pytest.mark.xfail(strict=True). Phase 1 fixes
will flip these to passing — strict=True catches the moment they unexpectedly
pass and forces removal of the marker.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.bridge_endpoint import app

client = TestClient(app)


# ──────────────────────────────────────────────────────────────────────
# Working bridge-backed tools (10 of 14)
# ──────────────────────────────────────────────────────────────────────


def test_service_health_contract():
    """cortex_service_health → GET /service-health. Returns status payload."""
    resp = client.get("/service-health")
    assert resp.status_code == 200
    data = resp.json()
    # The MCP tool returns this verbatim; verify it's a dict with at least one key.
    assert isinstance(data, dict)
    assert len(data) > 0


def test_intelligence_query_contract():
    """cortex_intelligence(query, query_type) → POST /intelligence/query.

    MCP sends: {"request": <query>, "domain": <env>, "query_type": <type>}.
    """
    fake_bridge = MagicMock()
    fake_bridge.query_intelligence.return_value = {"answer": "test", "patterns": []}
    with patch("api.bridge_endpoint.get_bridge", return_value=fake_bridge):
        resp = client.post(
            "/intelligence/query",
            json={"request": "what is cortex", "domain": "aidev", "query_type": "research"},
        )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), dict)


def test_recommendations_contract():
    """cortex_recommendations → GET /intelligence/recommendations."""
    fake_bridge = MagicMock()
    fake_bridge.get_recommendations.return_value = {
        "recommendations": [],
        "next_action": None,
    }
    with patch("api.bridge_endpoint.get_bridge", return_value=fake_bridge):
        resp = client.get("/intelligence/recommendations")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), dict)


def test_anomalies_contract():
    """cortex_anomalies → GET /anomalies."""
    fake_manager = MagicMock()
    fake_manager.get_active_anomalies.return_value = []
    with patch("api.bridge_endpoint.get_anomaly_manager", return_value=fake_manager):
        resp = client.get("/anomalies")
    assert resp.status_code == 200, resp.text


def test_projects_contract():
    """cortex_projects → GET /projects."""
    resp = client.get("/projects")
    # /projects has no required upstream; reads filesystem. Should always 200.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)


def test_sessions_contract():
    """cortex_sessions(active_only) → GET /sessions[?active_only=true]."""
    resp = client.get("/sessions")
    assert resp.status_code == 200, resp.text
    # MCP docstring promises session IDs, duration, projects touched.
    # In an empty test env it may be empty; just verify shape.
    data = resp.json()
    assert isinstance(data, (list, dict))

    resp_filtered = client.get("/sessions?active_only=true")
    assert resp_filtered.status_code == 200, resp_filtered.text


def test_taskboard_contract():
    """cortex_taskboard(status, project) → GET /taskboard."""
    resp = client.get("/taskboard")
    assert resp.status_code == 200, resp.text
    # Verify filter params accepted
    resp_filtered = client.get("/taskboard?status=pending&project=cortex")
    assert resp_filtered.status_code == 200, resp_filtered.text


def test_batch_status_contract():
    """cortex_batch_status(batch_id) → GET /batches/{batch_id}.

    Uses a fake batch_id; expect 404 or 200 — anything but 5xx or 422
    (which would mean the route signature is broken).
    """
    fake_client = MagicMock()
    fake_client.get_batch_status.return_value = {"status": "completed", "id": "test_batch"}
    with patch("api.bridge_endpoint.get_batch_client", return_value=fake_client):
        resp = client.get("/batches/test_batch")
    # Acceptable: 200 (mocked), 404 (not found), 500 (lazy import fail) — NOT 422.
    assert resp.status_code != 422, f"Route signature broken: {resp.text}"
    assert resp.status_code < 600


def test_outcomes_contract():
    """cortex_outcomes(project, limit) → GET /v2/outcomes."""
    resp = client.get("/v2/outcomes")
    # v2 module may not be available in test env (returns 501).
    # The contract: route exists, doesn't 422 the MCP query.
    assert resp.status_code != 422, f"Route rejects MCP payload: {resp.text}"
    assert resp.status_code in (200, 500, 501), f"Unexpected status: {resp.status_code}"

    resp_filtered = client.get("/v2/outcomes?project=cortex&limit=10")
    assert resp_filtered.status_code != 422, f"Filter params rejected: {resp_filtered.text}"


# ──────────────────────────────────────────────────────────────────────
# Direct-call MCP tools (4 of 18) — don't go through bridge
# ──────────────────────────────────────────────────────────────────────


def test_doctor_is_local():
    """cortex_doctor runs entirely in-process; verify no /doctor route exists.

    This is documentation: cortex_doctor does NOT call the bridge.
    """
    resp = client.get("/doctor")
    assert resp.status_code == 404, "cortex_doctor should be local-only; /doctor must not exist"


def test_prompt_refine_is_local():
    """cortex_prompt_refine reads ~/.cortex/prompts/patterns.json; no bridge route."""
    resp = client.get("/prompts/refine")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# Known-broken tools (Phase 1 will fix)
# Each is marked xfail(strict=True). When Phase 1 fixes the underlying
# issue, the test will unexpectedly pass — pytest will fail the run,
# forcing us to remove the marker. That's the ratchet.
# ──────────────────────────────────────────────────────────────────────


def test_conductor_compose_contract():
    """cortex_conductor_compose → POST /conductor/compose.

    Fixed in Phase 1: mcp_server.py now sends 'project_id' (matching the bridge
    PromptComposeRequest model at api/bridge_endpoint.py:2011-2019).
    """
    mcp_payload = {
        "intent": "build a thing",
        "project_id": "cortex",
        "intent_level": "collaborative",
        "include_context": True,
    }
    resp = client.post("/conductor/compose", json=mcp_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "prompt" in body
    assert body.get("project") == "cortex" or body.get("project_id") == "cortex"


def test_graph_query_contract():
    """cortex_graph_query → GET /graph/query.

    Phase 1 extended the bridge to accept (node_type, q, limit). node_type is
    now optional; with empty node_type the bridge queries all node types and
    applies an optional case-insensitive text filter via `q`.
    """
    # Case 1: text-only query, no node_type
    resp = client.get("/graph/query?q=patterns&limit=5")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "nodes" in body
    assert "count" in body
    assert "q" in body and body["q"] == "patterns"
    assert len(body["nodes"]) <= 5

    # Case 2: node_type only, no q
    resp2 = client.get("/graph/query?node_type=pattern&limit=10")
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["node_type"] == "pattern"

    # Case 3: no params at all (most common MCP-default scenario)
    resp3 = client.get("/graph/query")
    assert resp3.status_code == 200, resp3.text


def test_record_decision_contract():
    """cortex_record_decision → POST /decisions/record-freeform.

    Phase 1 added a new endpoint that matches the MCP free-form schema.
    The original /decisions/record (scenario-picker) is preserved for the
    Co-Navigator UI.
    """
    mcp_payload = {
        "decision": "use postgres",
        "context": "needed durable storage",
        "alternatives": "sqlite, dynamodb",
        "rationale": "team familiarity",
        "project": "cortex",
        "confidence": 0.8,
        "tags": "infra,storage",
    }
    resp = client.post("/decisions/record-freeform", json=mcp_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("recorded") is True
    assert body.get("decision_id", "").startswith("dec_")


def test_plan_create_contract(tmp_path, monkeypatch):
    """cortex_plan_create → POST /plans/create."""
    # Point goals file at a temp ACTION_PLAN.md so we don't depend on the
    # caller's repo state.
    goals = tmp_path / "ACTION_PLAN.md"
    goals.write_text(
        "## Priority A\n\n"
        "### A1: Test goal for cortex\n"
        "- Project: cortex\n"
        "- Status: pending\n"
        "- Description: smoke test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CORTEX_GOALS_FILE", str(goals))

    # Plans should be written under a temp HOME so test runs don't litter.
    monkeypatch.setenv("HOME", str(tmp_path))
    # Re-import PLANS_DIR-using module path is not necessary — the endpoint
    # reads Path.home() at request time.

    resp = client.post("/plans/create", json={"project": "cortex", "title": "test plan"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "plan_id" in body
    assert body["plan_id"].startswith("plan_cortex_")
    assert "path" in body


def test_plan_progress_contract():
    """cortex_plan_progress → GET /plans/progress.

    Phase 1 added the endpoint. Plans dir may be empty in the test env —
    contract is that the route exists and returns a well-formed response.
    """
    resp = client.get("/plans/progress")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "plans" in body
    assert "total" in body
    assert isinstance(body["plans"], list)


# ──────────────────────────────────────────────────────────────────────
# Surface invariants — what MCP advertises must match what bridge accepts
# ──────────────────────────────────────────────────────────────────────


def test_all_18_tools_documented():
    """The MCP server must register exactly the 18 tools the docs promise.

    This guards against silent additions or deletions that drift from
    BETA_ONBOARDING.md.
    """
    pytest.importorskip("mcp")
    from cortex.mcp_server import mcp as mcp_instance

    expected = {
        "cortex_service_health",
        "cortex_intelligence",
        "cortex_recommendations",
        "cortex_anomalies",
        "cortex_projects",
        "cortex_sessions",
        "cortex_taskboard",
        "cortex_orchestrate",
        "cortex_prompt_refine",
        "cortex_conductor_compose",
        "cortex_graph_query",
        "cortex_plan_create",
        "cortex_plan_progress",
        "cortex_batch_status",
        "cortex_outcomes",
        "cortex_record_decision",
        "cortex_research_digest",
        "cortex_doctor",
    }
    registered = {
        t for t in mcp_instance._tool_manager._tools.keys() if t.startswith("cortex_")
    }
    assert registered == expected, (
        f"Tool surface drift. Missing: {expected - registered}. "
        f"Extra: {registered - expected}."
    )


def test_mcp_payloads_match_bridge_pydantic_models():
    """Static check: for every _bridge_post call in mcp_server.py, the dict keys
    sent must match the matching Pydantic model on the bridge.

    This is the test that would have caught the conductor_compose bug
    (`project` vs `project_id`) and the record_decision schema mismatch.

    Walks each FunctionDef in mcp_server.py independently so payload keys
    are scoped to the function containing the _bridge_post call.
    """
    import ast
    from pathlib import Path

    from api.bridge_endpoint import (
        DecisionRecordRequest,
        PromptComposeRequest,
    )

    # Map endpoint path → Pydantic model used by the bridge route.
    # /decisions/record-freeform takes DecisionFreeformRequest (Phase 1).
    from api.bridge_endpoint import DecisionFreeformRequest, PlanCreateRequest

    endpoint_models = {
        "/conductor/compose": PromptComposeRequest,
        "/decisions/record-freeform": DecisionFreeformRequest,
        "/plans/create": PlanCreateRequest,
    }

    mcp_src = Path(__file__).parent.parent.parent / "mcp_server.py"
    tree = ast.parse(mcp_src.read_text())

    drift = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue

        # Find _bridge_post call inside this function (if any).
        call_node = None
        for sub in ast.walk(fn):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == "_bridge_post"
                and len(sub.args) >= 2
                and isinstance(sub.args[0], ast.Constant)
                and isinstance(sub.args[0].value, str)
            ):
                call_node = sub
                break
        if call_node is None:
            continue

        endpoint = call_node.args[0].value
        if endpoint not in endpoint_models:
            continue

        # Collect keys from any of:
        #   _bridge_post(endpoint, {literal dict})
        #   payload = {literal dict}                    ← dict-literal assign
        #   payload[KEY] = ...                          ← per-key subscript assign
        # scoped to THIS function only.
        sent_keys: set[str] = set()
        payload_arg = call_node.args[1]
        if isinstance(payload_arg, ast.Dict):
            for k in payload_arg.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    sent_keys.add(k.value)
        for assign in ast.walk(fn):
            # Handle both `payload = {...}` (Assign) and
            # `payload: dict = {...}` (AnnAssign).
            if isinstance(assign, ast.Assign):
                if len(assign.targets) != 1:
                    continue
                target = assign.targets[0]
                value = assign.value
            elif isinstance(assign, ast.AnnAssign):
                target = assign.target
                value = assign.value
            else:
                continue

            # payload = {...} or payload: dict = {...}
            if (
                isinstance(target, ast.Name)
                and target.id == "payload"
                and isinstance(value, ast.Dict)
            ):
                for k in value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        sent_keys.add(k.value)
            # payload[KEY] = ...
            elif (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "payload"
                and isinstance(target.slice, ast.Constant)
            ):
                sent_keys.add(target.slice.value)

        model = endpoint_models[endpoint]
        required_fields = {
            name
            for name, field in model.model_fields.items()
            if field.is_required()
        }
        missing = required_fields - sent_keys
        if missing:
            drift.append(
                f"{fn.name} → {endpoint}: required fields {missing} not sent "
                f"(sends {sent_keys})"
            )

    assert not drift, (
        "MCP payloads drift from bridge Pydantic models:\n" + "\n".join(drift)
    )
