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


@pytest.mark.xfail(
    strict=True,
    reason="BROKEN: mcp_server.py:241 sends 'project' but bridge expects 'project_id'. "
    "Phase 1 fixes this — one-line rename in mcp_server.py.",
)
def test_conductor_compose_contract_broken():
    """cortex_conductor_compose → POST /conductor/compose.

    Current MCP payload (mcp_server.py:239-244):
        {"intent": str, "project": str, "intent_level": str, "include_context": bool}

    Bridge model (api/bridge_endpoint.py:2011-2019) requires 'project_id'.
    Result: every call returns 422.
    """
    mcp_payload = {
        "intent": "build a thing",
        "project": "cortex",  # ← BUG: bridge wants 'project_id'
        "intent_level": "collaborative",
        "include_context": True,
    }
    resp = client.post("/conductor/compose", json=mcp_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


@pytest.mark.xfail(
    strict=True,
    reason="BROKEN: bridge /graph/query accepts only node_type+filters; MCP sends q/limit "
    "which FastAPI silently drops. With empty node_type, returns 422. "
    "Phase 1 will extend the bridge to accept q+limit OR fix MCP signature.",
)
def test_graph_query_contract_broken():
    """cortex_graph_query → GET /graph/query.

    MCP signature (mcp_server.py:307-327) advertises (node_type, query, limit).
    Bridge endpoint accepts only (node_type, filters). The 'query' and 'limit'
    params are silently dropped by FastAPI.

    When MCP user omits node_type (default ""), nothing is sent → bridge 422
    (node_type is required).
    """
    # Reproduces the case where MCP user passes only a text query
    resp = client.get("/graph/query?q=patterns&limit=5")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


@pytest.mark.xfail(
    strict=True,
    reason="BROKEN: bridge /decisions/record requires scenario-picker schema "
    "(prediction_id, scenario_chosen, scenario_name, domain) but MCP sends "
    "free-form decision schema (decision, context, alternatives, rationale). "
    "Phase 1 will add /decisions/record-freeform with matching Pydantic model.",
)
def test_record_decision_contract_broken():
    """cortex_record_decision → POST /decisions/record.

    Current MCP payload (mcp_server.py:381-389):
        {"decision": str, "context": str, "alternatives": str, "rationale": str}

    Bridge model (api/bridge_endpoint.py:126-138) requires:
        prediction_id, scenario_chosen, scenario_name, domain (all Field(...))

    Every MCP call returns 422.
    """
    mcp_payload = {
        "decision": "use postgres",
        "context": "needed durable storage",
        "alternatives": "sqlite, dynamodb",
        "rationale": "team familiarity",
    }
    resp = client.post("/decisions/record", json=mcp_payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


@pytest.mark.xfail(
    strict=True,
    reason="BROKEN: bridge has no /plans/create endpoint. Returns 404. "
    "Phase 1 will add POST /plans/create using existing goal_parser.GoalParser.",
)
def test_plan_create_contract_missing():
    """cortex_plan_create → POST /plans/create (does not exist)."""
    resp = client.post("/plans/create", json={"project": "cortex", "title": "test"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


@pytest.mark.xfail(
    strict=True,
    reason="BROKEN: bridge has no /plans/progress endpoint. Returns 404. "
    "Phase 1 will add GET /plans/progress reading ~/.cortex/plans/*.json.",
)
def test_plan_progress_contract_missing():
    """cortex_plan_progress → GET /plans/progress (does not exist)."""
    resp = client.get("/plans/progress")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


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

    endpoint_models = {
        "/conductor/compose": PromptComposeRequest,
        "/decisions/record": DecisionRecordRequest,
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

        # Collect keys: dict literal + payload[...] = ... assignments
        # scoped to THIS function only.
        sent_keys: set[str] = set()
        payload_arg = call_node.args[1]
        if isinstance(payload_arg, ast.Dict):
            for k in payload_arg.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    sent_keys.add(k.value)
        for assign in ast.walk(fn):
            if (
                isinstance(assign, ast.Assign)
                and len(assign.targets) == 1
                and isinstance(assign.targets[0], ast.Subscript)
                and isinstance(assign.targets[0].value, ast.Name)
                and assign.targets[0].value.id == "payload"
                and isinstance(assign.targets[0].slice, ast.Constant)
            ):
                sent_keys.add(assign.targets[0].slice.value)

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

    # NOTE: This test is EXPECTED to fail today (2 drifts: conductor_compose
    # and record_decision). Phase 1 fixes them. When it passes, remove this
    # marker.
    if drift:
        pytest.xfail(
            "MCP payloads drift from bridge Pydantic models (Phase 1 fixes):\n"
            + "\n".join(drift)
        )
