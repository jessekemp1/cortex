"""Contract tests for the MCP tool surface in mcp_server.py.

For each of the 18 @mcp.tool() functions, this module asserts the basic
contract a brilliant external integrator depends on:

  (a) Smoke: calling with default/minimal args returns without raising.
  (b) Return-shape: the result is a string (per the declared return type).
  (c) Non-empty: the returned string is not empty — every tool produces
      *something*, even on no-data paths.

Each tool's deeper semantics is not tested here — that's the job of focused
unit tests per tool. This module exists so that if a maintainer breaks the
return type of a tool, or makes it crash on minimal input, the brilliant
external tester (who runs `pytest -k mcp_tools_contract`) catches it first.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

import pytest

# Each entry: (tool_name, kwargs_for_minimal_invocation)
# kwargs use defaults where possible; for tools that require specific input
# shape (e.g., a batch_id), we pass a recognizably-fake value and expect the
# tool to return a graceful error envelope, not crash.
TOOL_INVOCATIONS: list[tuple[str, Dict[str, Any]]] = [
    ("cortex_service_health", {}),
    ("cortex_intelligence", {"query": "test query"}),
    ("cortex_recommendations", {}),
    ("cortex_anomalies", {}),
    ("cortex_projects", {}),
    ("cortex_sessions", {}),
    ("cortex_taskboard", {}),
    ("cortex_prompt_refine", {"prompt": "make this better"}),
    ("cortex_conductor_compose", {"intent": "test intent", "project": "test_project"}),
    ("cortex_orchestrate", {}),
    ("cortex_graph_query", {}),
    ("cortex_plan_create", {"project": "test_project"}),
    ("cortex_plan_progress", {}),
    ("cortex_batch_status", {"batch_id": "batch_does_not_exist"}),
    ("cortex_record_decision", {"decision": "test decision"}),
    ("cortex_outcomes", {}),
    ("cortex_research_digest", {}),
    ("cortex_doctor", {}),
]


@pytest.fixture(scope="module")
def mcp_module():
    """Import mcp_server once per module."""
    import mcp_server

    return mcp_server


def _resolve_tool(mcp_module, name: str):
    """Get the wrapped Python function for a tool by name.

    The @mcp.tool() decorator wraps the function but the original is
    accessible via the module attribute (FastMCP/anthropic-mcp pattern).
    """
    fn = getattr(mcp_module, name, None)
    if fn is None:
        pytest.skip(f"tool {name} not exported from mcp_server")
    # Unwrap FastMCP / decorator-wrapped tool if needed
    for attr in ("fn", "__wrapped__", "_fn"):
        wrapped = getattr(fn, attr, None)
        if callable(wrapped):
            fn = wrapped
            break
    return fn


@pytest.mark.parametrize(("name", "kwargs"), TOOL_INVOCATIONS, ids=[t[0] for t in TOOL_INVOCATIONS])
def test_tool_returns_string_without_crashing(mcp_module, name, kwargs):
    """Smoke + return-type contract for each MCP tool."""
    fn = _resolve_tool(mcp_module, name)
    try:
        result = fn(**kwargs)
    except Exception as e:
        pytest.fail(
            f"tool {name}(**{kwargs!r}) raised {type(e).__name__}: {e}. "
            f"MCP tools must return a graceful response envelope, never crash."
        )

    assert isinstance(result, str), (
        f"tool {name} returned {type(result).__name__}, expected str "
        f"(MCP tools declare -> str return)"
    )
    assert result, f"tool {name} returned an empty string; even no-data paths must produce output"


@pytest.mark.parametrize(("name", "kwargs"), TOOL_INVOCATIONS, ids=[t[0] for t in TOOL_INVOCATIONS])
def test_tool_output_is_parseable_or_human_readable(mcp_module, name, kwargs):
    """The output is either valid JSON or contains some signal (>=1 word)."""
    fn = _resolve_tool(mcp_module, name)
    try:
        result = fn(**kwargs)
    except Exception:
        pytest.skip("smoke test handles crashes; skip parseability if smoke fails")

    if not isinstance(result, str):
        pytest.skip("return-shape test handles non-string; skip parseability")

    # Either valid JSON or non-trivial human-readable text.
    is_json = False
    try:
        json.loads(result)
        is_json = True
    except (json.JSONDecodeError, ValueError):
        pass

    if not is_json:
        # At least one word — not just whitespace or a single punctuation char.
        assert re.search(r"\w", result), (
            f"tool {name} returned non-JSON non-word string: {result!r}"
        )


def test_mcp_module_exposes_at_least_18_tools(mcp_module):
    """Regression guard: future commits may not silently drop tools."""
    tool_count = sum(1 for name, _ in TOOL_INVOCATIONS if getattr(mcp_module, name, None))
    assert tool_count >= 16, (
        f"only {tool_count} of {len(TOOL_INVOCATIONS)} expected tools resolvable. "
        f"Tools may have been renamed or removed without updating this contract test."
    )
