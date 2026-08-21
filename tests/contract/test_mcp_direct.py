"""Contract: the core-8 MCP tools run in-process, never over HTTP.

The crash-proof guarantee ("a decision is never lost to a dead bridge")
holds only while the core tools stay off the HTTP path. This module pins
that with an AST scan of the eight core tool bodies (no _bridge_get /
_bridge_post / urllib) plus mocked-delegation tests proving each tool
routes through mcp_handlers or the in-process CortexBridge singleton.

The 10 passthrough tools legitimately keep using urllib — the ban is
per-function, not per-module.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

CORE_TOOLS = {
    "cortex_record_decision",
    "cortex_intelligence",
    "cortex_recommendations",
    "cortex_outcomes",
    "cortex_plan_create",
    "cortex_plan_progress",
    "cortex_projects",
    "cortex_doctor",
}

BANNED_NAMES = {"_bridge_get", "_bridge_post", "urllib"}

MCP_SERVER = Path(__file__).resolve().parent.parent.parent / "mcp_server.py"


def _core_function_defs():
    tree = ast.parse(MCP_SERVER.read_text(encoding="utf-8"))
    defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = CORE_TOOLS - set(defs)
    assert not missing, f"core tools missing from mcp_server.py: {missing}"
    return {name: defs[name] for name in CORE_TOOLS}


@pytest.mark.parametrize("tool_name", sorted(CORE_TOOLS))
def test_core_tool_body_has_no_http_bridge_calls(tool_name):
    """AST scan: no _bridge_get/_bridge_post/urllib inside a core tool body."""
    fn = _core_function_defs()[tool_name]
    offenders = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            offenders.append(f"{node.id} at line {node.lineno}")
        elif isinstance(node, ast.Attribute):
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in BANNED_NAMES:
                offenders.append(f"{ast.dump(node)[:60]} at line {node.lineno}")
    assert not offenders, (
        f"{tool_name} must run in-process (crash-proof contract) but references "
        f"the HTTP bridge: {offenders}"
    )


# ─── Mocked delegation: each core tool routes through mcp_handlers /
#     the in-process singleton ─────────────────────────────────────────


@pytest.fixture()
def mcp_module(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    import mcp_server

    return mcp_server


def _unwrap(fn) -> Any:
    for attr in ("fn", "__wrapped__", "_fn"):
        wrapped = getattr(fn, attr, None)
        if callable(wrapped):
            return wrapped
    return fn


def test_record_decision_delegates_to_handler(mcp_module, monkeypatch):
    import mcp_handlers

    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return {"recorded": True, "decision_id": "dec_test"}

    monkeypatch.setattr(mcp_handlers, "record_learning_decision", fake)
    out = json.loads(
        _unwrap(mcp_module.cortex_record_decision)(decision="d", project="p")
    )
    assert out["recorded"] is True
    assert seen["decision"] == "d"
    assert seen["project"] == "p"


def test_outcomes_plan_projects_delegate_to_handlers(mcp_module, monkeypatch):
    import mcp_handlers

    monkeypatch.setattr(mcp_handlers, "read_outcomes", lambda **kw: {"outcomes": [], "total": 0})
    monkeypatch.setattr(
        mcp_handlers, "plans_progress", lambda **kw: {"plans": [], "total": 0}
    )
    monkeypatch.setattr(
        mcp_handlers, "create_plan", lambda project, title=None: {"plan_id": f"plan_{project}"}
    )
    monkeypatch.setattr(mcp_handlers, "compute_projects", lambda: [{"name": "x"}])

    assert json.loads(_unwrap(mcp_module.cortex_outcomes)())["total"] == 0
    assert json.loads(_unwrap(mcp_module.cortex_plan_progress)())["total"] == 0
    assert json.loads(_unwrap(mcp_module.cortex_plan_create)(project="x"))["plan_id"] == "plan_x"
    assert json.loads(_unwrap(mcp_module.cortex_projects)())[0]["name"] == "x"


def test_intelligence_uses_in_process_singleton(mcp_module, monkeypatch):
    class FakeBridge:
        def _detect_current_project(self):
            return "projx"

        def query_intelligence(self, **kwargs):
            return {"answer": "42", "project": kwargs.get("project")}

    monkeypatch.setattr(mcp_module, "_get_bridge", lambda: FakeBridge())
    out = json.loads(_unwrap(mcp_module.cortex_intelligence)(query="q"))
    assert out["answer"] == "42"
    assert out["project"] == "projx"  # bridge detector wins when project omitted

    out = json.loads(_unwrap(mcp_module.cortex_intelligence)(query="q", project="explicit"))
    assert out["project"] == "explicit"  # explicit param is never overridden


def test_recommendations_uses_in_process_singleton(mcp_module, monkeypatch):
    class FakeBridge:
        def get_recommendations(self):
            return {"next_action": {"action": "ship it", "priority": "HIGH"}}

    monkeypatch.setattr(mcp_module, "_get_bridge", lambda: FakeBridge())
    out = json.loads(_unwrap(mcp_module.cortex_recommendations)())
    recs = out["recommendations"]
    assert recs and recs[0]["title"] == "ship it"


def test_core_tools_error_envelope_not_exception(mcp_module, monkeypatch):
    """A broken dependency yields {"error": ...}, never a raised exception."""

    def boom():
        raise RuntimeError("cold start failed")

    monkeypatch.setattr(mcp_module, "_get_bridge", boom)
    out = json.loads(_unwrap(mcp_module.cortex_intelligence)(query="q"))
    assert "error" in out
    out = json.loads(_unwrap(mcp_module.cortex_recommendations)())
    assert "error" in out


def test_doctor_reports_spool_depth(mcp_module, tmp_path):
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "decision-dec_x.json").write_text('{"decision_id": "dec_x"}')

    out = json.loads(_unwrap(mcp_module.cortex_doctor)())
    spool_checks = [c for c in out["checks"] if c["check"] == "decision spool empty"]
    assert spool_checks, "doctor must include the decision-spool check"
    assert spool_checks[0]["pass"] is False
    assert "1 pending" in spool_checks[0]["detail"]
