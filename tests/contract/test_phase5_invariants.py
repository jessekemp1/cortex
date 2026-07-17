"""Architecture invariants for the in-process MCP core.

Three invariants:

  1. MCP module import is fast — the lazy CortexBridge singleton means
     `cortex-mcp` must start without paying the ~16s ML-import tax, and the
     singleton must not be instantiated at import time.

  2. The bridge HTTP shim contains exactly the documented endpoint set.
     Adding or removing an endpoint requires updating this test, making
     accidental surface drift visible in review.

  3. Selected core shim routes actually respond (TestClient, hermetic).
"""

from __future__ import annotations

import importlib
import sys
import time

import pytest


# ──────────────────────────────────────────────────────────────────────
# Invariant 1: MCP startup is fast and lazy
# ──────────────────────────────────────────────────────────────────────


def _fresh_import_mcp_server():
    for mod in list(sys.modules):
        if mod == "mcp_server" or mod.endswith(".mcp_server"):
            del sys.modules[mod]
    return importlib.import_module("mcp_server")


def test_mcp_module_import_under_2s():
    """Importing mcp_server must be quick — the lazy CortexBridge singleton
    is what makes this possible. Eager bridge import costs ~16s.

    Allowance: 2.0s is generous; on a warm disk this should land under 0.5s.
    The threshold protects against accidentally moving `from bridge import
    CortexBridge` to module scope.
    """
    start = time.perf_counter()
    _fresh_import_mcp_server()
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, (
        f"mcp_server import took {elapsed:.2f}s (threshold 2.0s). "
        "Did someone eagerly import CortexBridge or another heavy module? "
        "Imports should be lazy — inside functions, not at module top."
    )


def test_bridge_singleton_remains_uninitialized_after_import():
    """The lazy singleton must not be eagerly instantiated."""
    mcp_server = _fresh_import_mcp_server()
    assert mcp_server._bridge_singleton is None, (
        "_bridge_singleton was instantiated at import — lazy initialization broken"
    )


# ──────────────────────────────────────────────────────────────────────
# Invariant 2: Endpoint inventory is bounded
# ──────────────────────────────────────────────────────────────────────


# Paths served by the bridge shim (api/bridge_endpoint.py + routers).
# Regenerated 2026-07-08 from the live `app.routes` (61 paths). Adding or
# removing endpoints requires updating this set — drift is a conscious
# decision made in review, never an accident.
EXPECTED_ENDPOINTS = {
    "/",
    "/activity/heatmap",
    "/anomalies",
    "/batches",
    "/batches/{batch_id}",
    "/batches/{batch_id}/cancel",
    "/briefing/executions",
    "/chat",
    "/chat/manifest.json",
    "/conductor/compose",
    "/conductor/history",
    "/conductor/startup",
    "/conductor/templates",
    "/decisions/learning",
    "/decisions/record",
    "/docs",
    "/docs/content",
    "/docs/oauth2-redirect",
    "/docs/tree",
    "/goals/stale-items",
    "/graph/query",
    "/guardian/claim",
    "/guardian/recover",
    "/guardian/release",
    "/guardian/snapshot",
    "/guardian/snapshots",
    "/guardian/status",
    "/health",
    "/intelligence/query",
    "/intelligence/reason",
    "/intelligence/recommendations",
    "/memory/temporal",
    "/meta/compounding",
    "/meta/compounding/file",
    "/meta/compounding/portfolio",
    "/metrics",
    "/openapi.json",
    "/predictions/current",
    "/projects",
    "/providers/status",
    "/queue",
    "/queue/{task_id}",
    "/recommendations",
    "/redoc",
    "/service-health",
    "/services/status",
    "/session/delta",
    "/session/resume-context",
    "/sessions",
    "/signal/absorb",
    "/signal/bus-stats",
    "/status",
    "/taskboard",
    "/taskboard/decompose",
    "/taskboard/{task_id}",
    "/v2/compound-health",
    "/v2/graph/search",
    "/v2/graph/stats",
    "/v2/outcomes",
    "/v2/outcomes/stats",
    "/ws/chat",
}


def test_bridge_endpoint_inventory_is_pinned():
    from api.bridge_endpoint import app

    actual = {getattr(r, "path", None) for r in app.routes}
    actual.discard(None)

    added = actual - EXPECTED_ENDPOINTS
    removed = EXPECTED_ENDPOINTS - actual
    assert not added and not removed, (
        f"Bridge endpoint surface drifted. Added: {sorted(added)}; "
        f"Removed: {sorted(removed)}. Update EXPECTED_ENDPOINTS deliberately."
    )


# ──────────────────────────────────────────────────────────────────────
# Invariant 3: core shim routes respond (hermetic)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.bridge_endpoint import app

    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    return TestClient(app)


def test_health_responds(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_decisions_learning_roundtrip(client, tmp_path):
    resp = client.post("/decisions/learning", json={"decision": "invariant check"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["recorded"] is True
    assert (tmp_path / "decisions.jsonl").exists()
