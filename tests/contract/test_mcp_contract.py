"""
Bridge endpoint contract tests for endpoints that SURVIVED Phase 5.

After Phase 5, MCP tools no longer go through HTTP — see
tests/contract/test_mcp_direct.py for the in-process contracts. This file
now narrowly verifies that the endpoints non-MCP HTTP consumers
(telegram bot, vite UI, monitoring) hit are still wired correctly.

Endpoints retained on the bridge after Phase 5 Step 6:
  - /service-health (gateway + MCP fallback documentation)
  - /intelligence/recommendations (telegram, web chat)
  - /anomalies (telegram, web chat)
  - /taskboard GET (gateway + future web UI)
  - plus /health, /docs, /intelligence/reason, /meta/compounding*
    covered in tests/contract/test_bridge_endpoints.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.bridge_endpoint import app

client = TestClient(app)


def test_service_health_contract():
    """GET /service-health — gateway uses this for status panels."""
    resp = client.get("/service-health")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert len(data) > 0


def test_recommendations_contract():
    """GET /intelligence/recommendations — telegram + web chat."""
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
    """GET /anomalies — telegram + web chat."""
    fake_manager = MagicMock()
    fake_manager.get_active_anomalies.return_value = []
    with patch("api.bridge_endpoint.get_anomaly_manager", return_value=fake_manager):
        resp = client.get("/anomalies")
    assert resp.status_code == 200, resp.text


def test_taskboard_contract():
    """GET /taskboard — kept for vite UI / gateway."""
    resp = client.get("/taskboard")
    assert resp.status_code == 200, resp.text
    resp_filtered = client.get("/taskboard?status=pending&project=cortex")
    assert resp_filtered.status_code == 200, resp_filtered.text


# ──────────────────────────────────────────────────────────────────────
# Tool-surface invariants
# ──────────────────────────────────────────────────────────────────────


def test_doctor_is_local():
    """cortex_doctor runs entirely in-process; verify no /doctor route exists."""
    resp = client.get("/doctor")
    assert resp.status_code == 404


def test_prompt_refine_is_local():
    """cortex_prompt_refine reads patterns.json; no bridge route."""
    resp = client.get("/prompts/refine")
    assert resp.status_code == 404


def test_all_18_tools_documented():
    """The MCP server must register exactly the 18 tools BETA_ONBOARDING.md promises."""
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
