#!/usr/bin/env python3
"""
Cortex MCP Server — Official MCP SDK over stdio.

Exposes Cortex Bridge intelligence as MCP tools for Claude Code.
Connects to bridge at :8765 via HTTP (no heavy imports).

Tools:
  - cortex_service_health: Ecosystem health (all services, tests, EMOS)
  - cortex_intelligence: Natural language query → insights
  - cortex_recommendations: Next actions and risk alerts
  - cortex_anomalies: Detected anomalies across projects
  - cortex_projects: Project status overview
  - cortex_sessions: Active/recent Claude sessions
  - cortex_taskboard: Task board items (list/create/update)
  - cortex_emos_status: EMOS pair counts and readiness

Resources:
  - cortex://goals: Current GOALS.md content
  - cortex://metrics/tests: Test results by project
  - cortex://metrics/emos: EMOS pair counts
"""

import json
import urllib.request
import urllib.error
from pathlib import Path

from mcp.server.fastmcp import FastMCP

BRIDGE_URL = "http://127.0.0.1:8765"
METRICS_DIR = Path.home() / ".cortex" / "metrics"
GOALS_FILE = Path.home() / "Dev" / "GOALS.md"

mcp = FastMCP("cortex")


def _bridge_get(path: str, timeout: float = 3.0) -> dict:
    """GET from bridge API. Returns parsed JSON or error dict."""
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}{path}",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": f"Bridge unavailable: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _bridge_post(path: str, payload: dict, timeout: float = 5.0) -> dict:
    """POST to bridge API. Returns parsed JSON or error dict."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{BRIDGE_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": f"Bridge unavailable: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


# ── Tools ──


@mcp.tool()
def cortex_service_health() -> str:
    """Get ecosystem health: bridge, Vortex, Winfield, Mission Control, test results, and EMOS pair counts."""
    result = _bridge_get("/service-health")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_intelligence(query: str, query_type: str = "research") -> str:
    """Query Cortex intelligence engine with natural language.

    Args:
        query: Natural language question about the codebase or projects.
        query_type: One of 'spec', 'architecture', 'implementation', 'research'.
    """
    valid_types = {"spec", "architecture", "implementation", "research"}
    if query_type not in valid_types:
        query_type = "research"
    result = _bridge_post(
        "/intelligence/query",
        {"request": query, "project": "cortex", "query_type": query_type},
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_recommendations() -> str:
    """Get strategic recommendations: next action, risk alerts, and priority projects."""
    result = _bridge_get("/intelligence/recommendations")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_anomalies() -> str:
    """Get detected anomalies across all projects with severity and recommendations."""
    result = _bridge_get("/anomalies")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_projects() -> str:
    """Get status overview of all active projects (health, test counts, recent activity)."""
    result = _bridge_get("/projects")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_sessions(active_only: bool = False) -> str:
    """Get Claude Code sessions (active or recent). Shows session IDs, duration, and projects touched."""
    param = "?active_only=true" if active_only else ""
    result = _bridge_get(f"/sessions{param}")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_taskboard(status: str = "", project: str = "") -> str:
    """Get task board items, optionally filtered by status (pending/in_progress/done) or project name."""
    params = []
    if status:
        params.append(f"status={status}")
    if project:
        params.append(f"project={project}")
    qs = "?" + "&".join(params) if params else ""
    result = _bridge_get(f"/taskboard{qs}")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_create_task(
    title: str, description: str = "", priority: str = "medium", project: str = ""
) -> str:
    """Create a new task on the Cortex task board."""
    payload = {"title": title}
    if description:
        payload["description"] = description
    if priority:
        payload["priority"] = priority
    if project:
        payload["project"] = project
    result = _bridge_post("/taskboard", payload)
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_emos_status() -> str:
    """Get EMOS calibration pair counts per model and readiness status (threshold: 2000 pairs)."""
    try:
        emos_file = METRICS_DIR / "emos.json"
        if not emos_file.exists():
            return json.dumps({"error": "No EMOS metrics file found"})

        data = json.loads(emos_file.read_text())
        pairs = data.get("pairs", {})
        threshold = 2000
        ready = {k: v for k, v in pairs.items() if v >= threshold}
        not_ready = {k: v for k, v in pairs.items() if v < threshold}

        return json.dumps(
            {
                "pairs": pairs,
                "threshold": threshold,
                "ready_models": list(ready.keys()),
                "not_ready": {
                    k: f"{v}/{threshold} ({v / threshold * 100:.0f}%)" for k, v in not_ready.items()
                },
                "timestamp": data.get("timestamp", "unknown"),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Resources ──


@mcp.resource("cortex://goals")
def goals_resource() -> str:
    """Current strategic goals from GOALS.md."""
    if GOALS_FILE.exists():
        return GOALS_FILE.read_text()
    return "GOALS.md not found"


@mcp.resource("cortex://metrics/tests")
def test_metrics_resource() -> str:
    """Test results by project (passed/failed counts)."""
    tests_file = METRICS_DIR / "tests.json"
    if tests_file.exists():
        return tests_file.read_text()
    return json.dumps({"error": "No test metrics found"})


@mcp.resource("cortex://metrics/emos")
def emos_metrics_resource() -> str:
    """EMOS calibration pair counts per model."""
    emos_file = METRICS_DIR / "emos.json"
    if emos_file.exists():
        return emos_file.read_text()
    return json.dumps({"error": "No EMOS metrics found"})


if __name__ == "__main__":
    mcp.run()
