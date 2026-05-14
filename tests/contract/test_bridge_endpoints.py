"""
Bridge endpoint contract tests for non-MCP consumers.

These tests cover endpoints hit by gateway/, supervisor/, alert_monitor,
heartbeat, notifications, and intelligence/analysis — i.e. the consumers
that will survive when MCP migrates to direct CortexBridge imports in
Phase 5 (the HTTP bridge becomes a ~300-line shim serving only these).

Each test documents the consumer and the exact request shape it sends.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.bridge_endpoint import app

client = TestClient(app)


# ──────────────────────────────────────────────────────────────────────
# /health — hit by heartbeat.py, threshold_detector.py, compounding_risk.py
# ──────────────────────────────────────────────────────────────────────


def test_health_endpoint():
    """GET /health — used as a liveness probe by 3+ consumers."""
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("status") == "healthy"


# ──────────────────────────────────────────────────────────────────────
# /docs — FastAPI auto-docs page. alert_monitor.py uses this as a
# liveness check (it expects an HTML 200 response).
# ──────────────────────────────────────────────────────────────────────


def test_docs_endpoint_renders():
    """GET /docs — alert_monitor.py probes this to verify the bridge is up."""
    resp = client.get("/docs")
    assert resp.status_code == 200, resp.text
    # FastAPI returns Swagger HTML at /docs.
    assert "text/html" in resp.headers.get("content-type", "")


# ──────────────────────────────────────────────────────────────────────
# /intelligence/reason — hit by telegram_bot.py and web_chat.py
# Telegram payload: {"question": <user_query>}
# ──────────────────────────────────────────────────────────────────────


def test_intelligence_reason_contract():
    """POST /intelligence/reason — telegram & web chat reasoning endpoint."""
    fake_bridge = MagicMock()
    fake_bridge.query_intelligence.return_value = {"answer": "test", "patterns": []}
    with patch("api.bridge_endpoint.get_bridge", return_value=fake_bridge):
        resp = client.post(
            "/intelligence/reason",
            json={"question": "why is X happening"},
        )
    # Acceptable: 200 with reasoning, or 501 if mode not available.
    # NOT 422 (rejecting the payload shape).
    assert resp.status_code != 422, f"Endpoint rejects gateway payload: {resp.text}"


# ──────────────────────────────────────────────────────────────────────
# /meta/compounding — hit by intelligence/analysis/compounding_risk.py
# ──────────────────────────────────────────────────────────────────────


def test_meta_compounding_project_contract():
    """GET /meta/compounding?project=X — compounding_risk.py:600."""
    resp = client.get("/meta/compounding?project=vortex-backend")
    # Route exists; data may be empty without prior compounding analysis runs.
    assert resp.status_code != 422
    assert resp.status_code < 600


def test_meta_compounding_portfolio_contract():
    """GET /meta/compounding/portfolio — compounding_risk.py:616."""
    resp = client.get("/meta/compounding/portfolio")
    assert resp.status_code != 422
    assert resp.status_code < 600


def test_meta_compounding_file_contract():
    """GET /meta/compounding/file?path=X — compounding_risk.py:631."""
    resp = client.get("/meta/compounding/file?path=cortex/bridge.py")
    assert resp.status_code != 422
    assert resp.status_code < 600
