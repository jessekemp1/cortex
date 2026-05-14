"""
Phase 5 direct-call contract tests.

For MCP tools migrated off HTTP (Phase 5), this file verifies:
  1. The tool produces a valid response.
  2. The tool does NOT touch `urllib.request.urlopen` — i.e., it really
     bypasses the HTTP bridge.
  3. Where applicable, the right `CortexBridge` method is invoked with the
     right kwargs.

As tools migrate in Steps 1-3, add a `test_<tool>_no_http` test here.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# cortex_service_health (Step 1 — migrated)
# ──────────────────────────────────────────────────────────────────────


def test_service_health_no_http():
    """cortex_service_health must NOT call urllib.request.urlopen from the
    MCP module path. It now uses health_probe.compute_service_health directly."""
    from mcp_server import cortex_service_health

    # The MCP server function should bypass urlopen entirely. health_probe
    # itself calls urlopen to reach external services — that's expected, the
    # contract is that mcp_server.cortex_service_health does NOT use the
    # HTTP bridge (port 8765) anymore.
    with patch("mcp_server._bridge_get") as bridge_get:
        result_str = cortex_service_health()
        bridge_get.assert_not_called()

    data = json.loads(result_str)
    assert "overall" in data
    assert "services" in data
    assert isinstance(data["services"], dict)
    assert "bridge" in data["services"]


def test_service_health_uses_health_probe_helper():
    """The tool delegates to compute_service_health, not the FastAPI route."""
    from mcp_server import cortex_service_health

    fake_services = {"bridge": {"status": "healthy", "port": 8765}}
    with patch("health_probe.compute_service_health", return_value=fake_services):
        result_str = cortex_service_health()

    data = json.loads(result_str)
    assert data == {"overall": "healthy", "services": fake_services}


# ──────────────────────────────────────────────────────────────────────
# Singleton lifecycle
# ──────────────────────────────────────────────────────────────────────


def test_get_bridge_singleton_caches():
    """_get_bridge() must return the SAME instance across calls.

    Note: we can't reliably patch CortexBridge here because mcp_server's
    `from bridge import CortexBridge` happens lazily inside _get_bridge,
    and the imported binding is captured before any patch site can intercept
    it. Instead, prove the caching property: two calls return identical
    objects, and the cached singleton survives a third call.
    """
    import mcp_server

    # Reset state so this test is independent of any earlier MCP tool calls.
    mcp_server._bridge_singleton = None

    first = mcp_server._get_bridge()
    second = mcp_server._get_bridge()
    third = mcp_server._get_bridge()

    assert first is second is third, "Singleton must be cached — three calls produced different objects"


def test_get_bridge_not_called_at_import():
    """Importing mcp_server must not eagerly instantiate CortexBridge.

    Bridge instantiation triggers ~16s of optional ML imports. Lazy startup
    is essential for MCP responsiveness — the first tool call pays the cost,
    not module load.
    """
    # Force a fresh import to observe module-load behavior.
    import importlib
    import sys

    if "mcp_server" in sys.modules:
        del sys.modules["mcp_server"]
    mcp_server = importlib.import_module("mcp_server")
    assert mcp_server._bridge_singleton is None, (
        "_bridge_singleton must remain None after import — lazy initialization is required"
    )
