"""
Phase 5 direct-call contract tests.

For MCP tools migrated off HTTP (Phase 5), this file verifies:
  1. mcp_server.py does NOT contain HTTP-bridge plumbing
     (_bridge_get/_bridge_post/BRIDGE_URL/urllib). One module-level AST
     scan catches any reintroduction.
  2. Each migrated tool calls the right handler/method with the right kwargs.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────────────────────────────
# Invariant: mcp_server.py is HTTP-free
# ──────────────────────────────────────────────────────────────────────


def test_mcp_server_has_no_http_plumbing():
    """After Phase 5, mcp_server.py must not import urllib or reference
    _bridge_get/_bridge_post/BRIDGE_URL. The lazy CortexBridge singleton
    is the only allowed cross-module call.

    This is the canonical no-HTTP enforcement. Per-tool patch-based
    bridge_get.assert_not_called() checks are redundant once this passes.
    """
    src = (Path(__file__).parent.parent.parent / "mcp_server.py").read_text()
    tree = ast.parse(src)

    banned_names = {"_bridge_get", "_bridge_post", "BRIDGE_URL"}
    banned_imports = {"urllib", "urllib.request", "urllib.error"}

    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in banned_imports or alias.name.startswith("urllib."):
                    offenders.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module in banned_imports or (
                node.module and node.module.startswith("urllib")
            ):
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Name) and node.id in banned_names:
            offenders.append(f"line {node.lineno}: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in banned_names:
            offenders.append(f"line {node.lineno}: .{node.attr}")
    assert not offenders, (
        "mcp_server.py contains banned HTTP-bridge plumbing:\n  "
        + "\n  ".join(offenders)
    )


# ──────────────────────────────────────────────────────────────────────
# cortex_service_health (Step 1)
# ──────────────────────────────────────────────────────────────────────


def test_service_health_delegates_to_health_probe():
    """The tool calls compute_service_health and wraps with overall status."""
    from mcp_server import cortex_service_health

    fake_services = {"bridge": {"status": "healthy", "port": 8765}}
    with patch("health_probe.compute_service_health", return_value=fake_services):
        result = json.loads(cortex_service_health())
    assert result == {"overall": "healthy", "services": fake_services}


def test_service_health_overall_degraded_when_any_service_offline():
    """If any service has non-healthy status, overall is 'degraded'."""
    from mcp_server import cortex_service_health

    fake_services = {
        "bridge": {"status": "healthy", "port": 8765},
        "vortex_backend": {"status": "offline", "port": 8000},
    }
    with patch("health_probe.compute_service_health", return_value=fake_services):
        result = json.loads(cortex_service_health())
    assert result["overall"] == "degraded"


# ──────────────────────────────────────────────────────────────────────
# Singleton lifecycle
# ──────────────────────────────────────────────────────────────────────


def test_get_bridge_singleton_caches():
    """_get_bridge() must return the SAME instance across calls."""
    import mcp_server

    mcp_server._bridge_singleton = None

    first = mcp_server._get_bridge()
    second = mcp_server._get_bridge()
    third = mcp_server._get_bridge()

    assert first is second is third, "Singleton must be cached — three calls produced different objects"


def test_get_bridge_is_thread_safe():
    """Concurrent first-callers must all receive the SAME CortexBridge.

    FastMCP can dispatch tool calls on multiple threads. Without the lock in
    _get_bridge, a cold-start race could construct two CortexBridge instances.
    This test resets the singleton and hammers _get_bridge from many threads.
    """
    import threading

    import mcp_server

    mcp_server._bridge_singleton = None

    results: list = []
    barrier = threading.Barrier(12)

    def worker():
        barrier.wait()  # maximize the race — all threads hit _get_bridge together
        results.append(mcp_server._get_bridge())

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 12
    assert all(r is results[0] for r in results), (
        "Concurrent _get_bridge calls produced more than one instance — "
        "the double-checked lock is not working"
    )


def test_get_bridge_not_called_at_import():
    """Importing mcp_server must not eagerly instantiate CortexBridge."""
    import importlib
    import sys

    if "mcp_server" in sys.modules:
        del sys.modules["mcp_server"]
    mcp_server = importlib.import_module("mcp_server")
    assert mcp_server._bridge_singleton is None


# ──────────────────────────────────────────────────────────────────────
# Step 2: read-only tools delegate to the right handler
# ──────────────────────────────────────────────────────────────────────


def test_projects_delegates_to_mcp_handlers():
    from mcp_server import cortex_projects

    fake = [{"name": "Cortex", "path": "cortex", "status": "healthy", "last_activity": ""}]
    with patch("mcp_handlers.compute_projects", return_value=fake) as h:
        result = json.loads(cortex_projects())
    h.assert_called_once()
    assert result == fake


def test_sessions_delegates_to_mcp_handlers():
    from mcp_server import cortex_sessions

    fake = {"sessions": [], "total": 0, "active_count": 0}
    with patch("mcp_handlers.scan_sessions", return_value=fake) as h:
        result = json.loads(cortex_sessions(active_only=True))
    h.assert_called_once_with(active_only=True)
    assert result == fake


def test_taskboard_delegates_to_mcp_handlers():
    from mcp_server import cortex_taskboard

    fake = {"tasks": [], "total": 0}
    with patch("mcp_handlers.query_taskboard", return_value=fake) as h:
        result = json.loads(cortex_taskboard(status="pending", project="cortex"))
    h.assert_called_once_with(status="pending", project="cortex")
    assert result == fake


def test_plan_progress_delegates_to_mcp_handlers():
    from mcp_server import cortex_plan_progress

    fake = {"plans": [], "total": 0}
    with patch("mcp_handlers.plans_progress", return_value=fake) as h:
        result = json.loads(cortex_plan_progress())
    h.assert_called_once()
    assert result == fake


def test_recommendations_delegates_to_bridge_method():
    import mcp_server

    fake_bridge = MagicMock()
    fake_bridge.get_recommendations.return_value = {"recommendations": [], "next_action": None}
    with patch.object(mcp_server, "_get_bridge", return_value=fake_bridge):
        result = json.loads(mcp_server.cortex_recommendations())
    fake_bridge.get_recommendations.assert_called_once()
    assert isinstance(result, dict)


def test_graph_query_delegates_to_bridge_method():
    import mcp_server

    fake_bridge = MagicMock()
    fake_bridge.query_graph.return_value = []
    with patch.object(mcp_server, "_get_bridge", return_value=fake_bridge):
        result = json.loads(mcp_server.cortex_graph_query(node_type="pattern", limit=5))
    fake_bridge.query_graph.assert_called_with(node_type="pattern")
    assert result["node_type"] == "pattern"


# ──────────────────────────────────────────────────────────────────────
# Step 3: POST tools delegate to the right handler
# ──────────────────────────────────────────────────────────────────────


def test_intelligence_delegates_to_bridge_method():
    import mcp_server

    fake_bridge = MagicMock()
    fake_bridge.query_intelligence.return_value = {"answer": "ok", "patterns": []}
    with patch.object(mcp_server, "_get_bridge", return_value=fake_bridge):
        result = json.loads(mcp_server.cortex_intelligence(query="test", query_type="research"))
    fake_bridge.query_intelligence.assert_called_once()
    assert result == {"answer": "ok", "patterns": []}


def test_conductor_compose_delegates_to_mcp_handlers():
    from mcp_server import cortex_conductor_compose

    fake = {"prompt": "x", "project": "cortex", "intent_level": "advisory", "token_estimate": 5}
    with patch("mcp_handlers.compose_conductor_prompt", return_value=fake) as h:
        result = json.loads(
            cortex_conductor_compose(
                intent="test", project="cortex", intent_level="advisory", include_context=False
            )
        )
    h.assert_called_once_with(
        intent="test", project_id="cortex", intent_level="advisory", include_context=False
    )
    assert result == fake


def test_plan_create_delegates_to_mcp_handlers():
    from mcp_server import cortex_plan_create

    fake = {"plan_id": "plan_cortex_1", "path": "/tmp/x.json", "item_count": 0}
    with patch("mcp_handlers.create_plan", return_value=fake) as h:
        result = json.loads(cortex_plan_create(project="cortex"))
    h.assert_called_once_with(project="cortex", title=None)
    assert result == fake


def test_record_decision_delegates_to_mcp_handlers():
    from mcp_server import cortex_record_decision

    fake = {"recorded": True, "decision_id": "dec_1", "timestamp": "2026-05-14T00:00:00"}
    with patch("mcp_handlers.record_freeform_decision", return_value=fake) as h:
        result = json.loads(
            cortex_record_decision(
                decision="use X", context="why", project="cortex", confidence=0.7
            )
        )
    h.assert_called_once_with(
        decision="use X",
        context="why",
        alternatives="",
        rationale="",
        project="cortex",
        confidence=0.7,
        tags="",
    )
    assert result == fake
