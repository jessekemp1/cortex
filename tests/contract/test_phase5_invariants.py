"""
Phase 5 invariants — enforce the post-collapse architecture.

Three invariants:

  1. mcp_server.py has no HTTP plumbing
     (already enforced by test_mcp_direct.test_mcp_server_has_no_http_plumbing)

  2. MCP module import is fast — the lazy CortexBridge singleton means
     `python -m cortex.mcp_server` should start without paying the 16s
     transformer-import tax.

  3. The bridge HTTP shim contains only the documented surviving endpoint set.
     Adding a new endpoint requires updating this test, making accidental
     re-introductions visible.
"""

from __future__ import annotations

import importlib
import sys
import time

import pytest


# ──────────────────────────────────────────────────────────────────────
# Invariant 2: MCP startup is fast
# ──────────────────────────────────────────────────────────────────────


def test_mcp_module_import_under_2s():
    """Importing cortex.mcp_server must be quick — the lazy CortexBridge
    singleton is what makes this possible. Eager bridge import costs ~16s.

    Allowance: 2.0s is generous; on a cold disk this should land under 0.5s.
    The threshold protects against accidentally moving `from bridge import
    CortexBridge` to module scope.
    """
    # Ensure a fresh import path is taken.
    for mod in list(sys.modules):
        if mod == "mcp_server" or mod.endswith(".mcp_server"):
            del sys.modules[mod]

    start = time.perf_counter()
    importlib.import_module("mcp_server")
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, (
        f"mcp_server import took {elapsed:.2f}s (threshold 2.0s). "
        "Did someone eagerly import CortexBridge or another heavy module? "
        "Imports should be lazy — inside functions, not at module top."
    )


def test_bridge_singleton_remains_uninitialized_after_import():
    """The lazy singleton must not be eagerly instantiated."""
    for mod in list(sys.modules):
        if mod == "mcp_server" or mod.endswith(".mcp_server"):
            del sys.modules[mod]
    mcp_server = importlib.import_module("mcp_server")
    assert mcp_server._bridge_singleton is None, (
        "_bridge_singleton was instantiated at import — lazy initialization broken"
    )


# ──────────────────────────────────────────────────────────────────────
# Invariant 3: Endpoint inventory is bounded
# ──────────────────────────────────────────────────────────────────────


# Endpoints retained on the bridge after Phase 5 Step 6.
# Adding or removing endpoints requires updating this set. The test
# treats any drift as a failure to force conscious decisions.
EXPECTED_ENDPOINTS = {
    # FastAPI defaults — auto-generated, can't be removed without disabling docs
    ("GET", "/openapi.json"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
    # NOTE: the web-chat router (/chat, /ws/chat) was removed when the UI
    # surfaces (vite dashboard + gateway) were removed from the beta tree.
    # The bridge now serves only local agents (Hermes) + monitoring probes.
    # Root + liveness
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/service-health"),
    ("GET", "/status"),
    # Gateway-consumed
    ("POST", "/intelligence/reason"),
    ("GET", "/intelligence/recommendations"),
    ("GET", "/anomalies"),
    # Recommendations alias
    ("GET", "/recommendations"),
    # TaskBoard (vite UI surface)
    ("GET", "/taskboard"),
    ("POST", "/taskboard"),
    ("PATCH", "/taskboard/{task_id}"),
    ("DELETE", "/taskboard/{task_id}"),
    ("POST", "/taskboard/decompose"),
    # Batch + queue (vite UI / monitoring)
    ("GET", "/batches"),
    ("GET", "/queue"),
    ("POST", "/queue"),
    ("PATCH", "/queue/{task_id}"),
    ("DELETE", "/queue/{task_id}"),
    ("GET", "/metrics"),
    # v2 graph + compounding (vite UI + compounding_risk.py)
    ("GET", "/v2/graph/search"),
    ("GET", "/v2/graph/stats"),
    ("GET", "/v2/compound-health"),
    ("GET", "/meta/compounding"),
    ("GET", "/meta/compounding/portfolio"),
    ("GET", "/meta/compounding/file"),
    # Briefing (existing test + gateway)
    ("POST", "/briefing/executions"),
    ("GET", "/briefing/executions"),
    # Guardian (vite UI)
    ("POST", "/guardian/claim"),
    ("POST", "/guardian/release"),
    ("GET", "/guardian/status"),
    ("POST", "/guardian/snapshot"),
    ("GET", "/guardian/snapshots"),
    ("POST", "/guardian/recover"),
    # Signal bus
    ("POST", "/signal/absorb"),
    ("GET", "/signal/bus-stats"),
    # Conductor (vite UI Conductor panel)
    ("GET", "/conductor/startup"),
    ("GET", "/conductor/templates"),
    ("GET", "/conductor/history"),
    # Doc/services/predictions/memory/providers (vite UI)
    ("GET", "/docs/tree"),
    ("GET", "/docs/content"),
    ("GET", "/services/status"),
    ("GET", "/predictions/current"),
    ("POST", "/decisions/record"),  # scenario-picker (Co-Navigator UI)
    ("GET", "/activity/heatmap"),
    ("GET", "/memory/temporal"),
    ("GET", "/providers/status"),
    # Briefing helper endpoints
    ("GET", "/session/resume-context"),
    ("GET", "/goals/stale-items"),
    ("GET", "/session/delta"),
}


def _normalize_route(route) -> tuple:
    """Extract (method, path) from a FastAPI route, or path for non-method routes."""
    methods = getattr(route, "methods", None)
    path = getattr(route, "path", None) or getattr(route, "path_format", None)
    if path is None:
        return None
    if methods:
        return (sorted(methods)[0], path)
    return path  # static/openapi routes


def test_bridge_endpoint_inventory_unchanged():
    """The set of endpoints registered on the bridge must match the
    documented EXPECTED_ENDPOINTS exactly.

    If this test fails, EITHER:
      - An endpoint was added → add it to EXPECTED_ENDPOINTS with a note
        about which consumer needs it.
      - An endpoint was removed → drop it from EXPECTED_ENDPOINTS.
      - An endpoint URL changed → update both sides.
    Don't silently widen the set.
    """
    from api.bridge_endpoint import app

    registered = set()
    for route in app.routes:
        norm = _normalize_route(route)
        if norm is not None:
            # Filter to method+path tuples and well-known path strings only.
            if isinstance(norm, tuple):
                # Skip HEAD methods FastAPI auto-adds; we care about user-facing verbs.
                method, path = norm
                if method == "HEAD":
                    continue
                # Some routes have multiple methods listed; normalize to the
                # first non-HEAD one we see.
                registered.add((method, path))
            else:
                registered.add(norm)

    missing = EXPECTED_ENDPOINTS - registered
    extra = registered - EXPECTED_ENDPOINTS
    # Sort by string repr so mixed (tuple, str) entries are comparable.
    sorted_missing = sorted(missing, key=str)
    sorted_extra = sorted(extra, key=str)
    assert not missing and not extra, (
        f"Bridge endpoint inventory drift:\n"
        f"  Missing (expected but not registered): {sorted_missing}\n"
        f"  Extra (registered but not expected):   {sorted_extra}\n"
        "Update EXPECTED_ENDPOINTS in tests/contract/test_phase5_invariants.py "
        "with a comment explaining which consumer requires the change."
    )


def test_no_phase5_deleted_endpoints_resurrect():
    """Endpoints deleted in Phase 5 Step 6 must not reappear.

    These paths exist as concrete tombstones — if any of them comes back,
    its functionality should go through mcp_handlers / direct CortexBridge
    methods instead.
    """
    from api.bridge_endpoint import app

    deleted_paths = {
        "/intelligence/query",
        "/graph/query",
        "/batches/{batch_id}",
        "/batches/{batch_id}/cancel",
        "/v2/outcomes",
        "/v2/outcomes/stats",
        "/projects",
        "/sessions",
        "/conductor/compose",
        "/decisions/record-freeform",
        "/plans/create",
        "/plans/progress",
    }

    registered_paths = {getattr(r, "path", None) for r in app.routes}
    resurrected = deleted_paths & registered_paths
    assert not resurrected, (
        f"Phase 5 Step 6 deleted these endpoints; they MUST NOT reappear: "
        f"{sorted(resurrected)}. Use mcp_handlers/_get_bridge instead."
    )
