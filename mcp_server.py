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
  - cortex_prompt_refine: Get refinement suggestions for any prompt (cross-model)
  - cortex_conductor_compose: Receive composed prompts from Conductor UI
  - cortex_conductor_startup: Get startup intelligence summary from Conductor

Resources:
  - cortex://goals: Current GOALS.md content
  - cortex://metrics/tests: Test results by project
  - cortex://metrics/emos: EMOS pair counts
  - cortex://prompts/patterns: Learned prompt patterns and category hints
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path

from mcp.server.fastmcp import FastMCP

BRIDGE_URL = "http://127.0.0.1:8765"
METRICS_DIR = Path.home() / ".cortex" / "metrics"
GOALS_FILE = Path(os.environ.get("CORTEX_ROOT_DIR", Path.home() / "Dev")) / "GOALS.md"
PROMPTS_DIR = Path.home() / ".cortex" / "prompts"

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


@mcp.tool()
def cortex_prompt_refine(prompt: str, category: str = "") -> str:
    """Get refinement suggestions for a prompt using learned patterns.

    Analyzes the prompt, classifies it, and returns category-specific refinement
    hints plus similar high-value prompts from the database. Works for any model.

    Args:
        prompt: The raw user prompt to refine.
        category: Optional override for category (direction/investigation/meta/idea/decision/request).
    """
    patterns_file = PROMPTS_DIR / "patterns.json"
    if not patterns_file.exists():
        return json.dumps(
            {"error": "No patterns cache. Run: python cortex/intelligence/prompt_db.py patterns"}
        )

    try:
        patterns = json.loads(patterns_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return json.dumps({"error": str(e)})

    # Auto-classify if no category provided
    if not category:
        prompt_lower = prompt.lower()
        category_keywords = {
            "direction": ["should", "path", "strategy", "approach", "plan", "vision", "10/10"],
            "investigation": ["why", "broken", "failing", "debug", "diagnose", "root cause"],
            "meta": ["learn", "improve", "optimize", "refine", "prompt", "workflow"],
            "idea": ["what if", "imagine", "consider", "concept", "brainstorm"],
            "decision": ["decide", "choose", "trade-off", "versus", "option"],
            "request": ["add", "create", "build", "implement", "fix", "update"],
        }
        scores = {}
        for cat, keywords in category_keywords.items():
            scores[cat] = sum(1 for kw in keywords if kw in prompt_lower)
        category = max(scores, key=scores.get) if any(scores.values()) else "request"

    # Get category hint
    hints = patterns.get("category_hints", {})
    hint = hints.get(category, "Add: acceptance criteria, scope, test requirements")

    # Find similar high-value prompts
    top = patterns.get("top_patterns", [])
    similar = [p for p in top if p.get("category") == category and p.get("value_score", 0) >= 0.7][
        :3
    ]

    result = {
        "classified_category": category,
        "refinement_hint": hint,
        "similar_high_value_prompts": similar,
        "word_count": len(prompt.split()),
        "suggestion": f"Consider adding: {hint.split(': ', 1)[-1] if ': ' in hint else hint}",
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_conductor_compose(
    intent: str, project: str, intent_level: str = "collaborative", include_context: bool = True
) -> str:
    """Receive a composed prompt from the Conductor UI instead of clipboard copy.

    The Conductor composes a full prompt with context, intent classification,
    and relevant Cortex intelligence, then delivers it here for execution.

    Args:
        intent: The user's intent or task description from Conductor.
        project: Target project (vortex, cortex, alpha-arena, etc.).
        intent_level: Intent level — one of 'advisory', 'collaborative', 'autonomous', 'supervisory'. Default: collaborative.
        include_context: Whether to include Cortex context (goals, recent sessions, anomalies). Default: True.
    """
    valid_levels = {"advisory", "collaborative", "autonomous", "supervisory"}
    if intent_level not in valid_levels:
        intent_level = "collaborative"

    payload = {
        "intent": intent,
        "project": project,
        "intent_level": intent_level,
        "include_context": include_context,
    }
    result = _bridge_post("/conductor/compose", payload, timeout=10.0)
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_conductor_startup(project_id: str = "") -> str:
    """Get startup intelligence summary from Conductor.

    Returns project health, active goals, recent anomalies, and recommended
    first actions — everything needed to orient at the start of a session.

    Args:
        project_id: Optional project to focus the startup summary on.
    """
    params = f"?project_id={project_id}" if project_id else ""
    result = _bridge_get(f"/conductor/startup{params}", timeout=10.0)
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_orchestrate(
    task: str = "",
    project: str = "",
    priority: str = "medium",
    dry_run: bool = False,
    max_items: int = 0,
) -> str:
    """Orchestrate work: discover tasks from GOALS.md/taskboard, route to optimal models, and dispatch.

    With no arguments, discovers all pending work and dispatches it.
    With a task description, creates a single work item and dispatches it.

    Args:
        task: Optional task description. If empty, discovers work from all sources.
        project: Optional project filter (vortex, cortex, etc.).
        priority: Priority level (critical/high/medium/low). Default: medium.
        dry_run: If true, discover and route but don't dispatch. Shows what would happen.
        max_items: Limit number of items to process (0 = unlimited).
    """
    import sys
    from pathlib import Path

    # Add cortex to path for imports
    cortex_dir = Path(__file__).parent
    if str(cortex_dir) not in sys.path:
        sys.path.insert(0, str(cortex_dir))

    try:
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor
        from supervisor.intake import WorkIntake

        config = SupervisorConfig(dry_run=dry_run)
        supervisor = CortexSupervisor(config=config)
        intake = WorkIntake()

        if task:
            work_items = [intake.from_cli(task, project=project, priority=priority)]
        else:
            work_items = intake.discover_all()
            if project:
                work_items = [wi for wi in work_items if wi.project == project]

        if max_items:
            work_items = work_items[:max_items]

        result = supervisor.orchestrate(work_items if work_items else None)
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ── CRA Research Tools ──


@mcp.tool()
def cortex_research_status() -> str:
    """Get CRA (Cortex Research Agent) pipeline status: discovery, assessment, proposal counts, and baseline score."""
    try:
        from cortex.engines.research_agent import CortexResearchAgent

        agent = CortexResearchAgent()
        discoveries = agent.load_discoveries()
        assessments = agent.load_assessments()
        adopt = agent.get_adopt_recommendations()
        threats = agent.get_urgent_threats()
        proposals = agent.get_pending_proposals()
        statuses = agent.status_tracker.get_all()

        status_counts = {}
        for _file, data in statuses.items():
            s = data.get("status", "draft")
            status_counts[s] = status_counts.get(s, 0) + 1

        result = {
            "discoveries": len(discoveries),
            "assessments": len(assessments),
            "adopt_recommendations": len(adopt),
            "urgent_threats": len(threats),
            "pending_proposals": len(proposals),
            "baseline_score": round(agent.get_baseline_score(), 4),
            "scan_due": agent.should_scan(),
            "proposal_statuses": status_counts,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_research_digest() -> str:
    """Get the CRA weekly research digest — discoveries, assessments, urgent threats, and pending proposals."""
    try:
        from cortex.engines.research_agent import CortexResearchAgent

        agent = CortexResearchAgent()
        return agent.weekly_digest()
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_research_proposals(action: str = "list") -> str:
    """Manage CRA research proposals. List pending proposals or approve one for live execution.

    Args:
        action: "list" to show all proposals with status, or "approve:<filename>" to approve a proposal.
    """
    try:
        from cortex.engines.research_agent import CortexResearchAgent

        agent = CortexResearchAgent()

        if action.startswith("approve:"):
            proposal_file = action.split(":", 1)[1].strip()
            agent.approve_proposal(proposal_file)
            return json.dumps(
                {
                    "approved": proposal_file,
                    "new_status": agent.status_tracker.get_status(proposal_file),
                },
                indent=2,
            )

        # Default: list proposals with status
        proposals = agent.get_pending_proposals()
        result = []
        for p in proposals:
            status = agent.status_tracker.get_status(p["file"])
            result.append(
                {
                    "file": p["file"],
                    "title": p["title"],
                    "created": p["created"],
                    "status": status,
                }
            )
        return json.dumps({"proposals": result, "count": len(result)}, indent=2)
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


@mcp.resource("cortex://prompts/patterns")
def prompt_patterns_resource() -> str:
    """Learned prompt patterns: category hints, top prompts, recurring structures."""
    patterns_file = PROMPTS_DIR / "patterns.json"
    if patterns_file.exists():
        return patterns_file.read_text()
    return json.dumps(
        {"error": "No patterns cache. Run: python cortex/intelligence/prompt_db.py patterns"}
    )


# ── Deferred Tool Loading ──
#
# Low-frequency tools (research, conductor) are removed at import time
# and re-registered on demand via cortex_enable_tools(). This reduces
# the initial tools/list payload sent to clients — fewer tokens per session.

_DEFERRED_TOOL_GROUPS = {
    "research": {
        "cortex_research_status": cortex_research_status,
        "cortex_research_digest": cortex_research_digest,
        "cortex_research_proposals": cortex_research_proposals,
    },
    "conductor": {
        "cortex_conductor_compose": cortex_conductor_compose,
        "cortex_conductor_startup": cortex_conductor_startup,
    },
}

_DEFERRED_TOOL_NAMES = set()
for _group_tools in _DEFERRED_TOOL_GROUPS.values():
    _DEFERRED_TOOL_NAMES.update(_group_tools.keys())

# Remove deferred tools from initial registration
for _name in _DEFERRED_TOOL_NAMES:
    try:
        mcp.remove_tool(_name)
    except Exception:
        pass  # Tool may not exist if registration order changes


@mcp.tool()
def cortex_enable_tools(group: str = "all") -> str:
    """Enable deferred tool groups that were not loaded at startup.

    Available groups: 'research' (CRA status/digest/proposals),
    'conductor' (compose/startup), or 'all'.

    Args:
        group: Tool group to enable — 'research', 'conductor', or 'all'.
    """
    if group == "all":
        groups_to_enable = list(_DEFERRED_TOOL_GROUPS.keys())
    elif group in _DEFERRED_TOOL_GROUPS:
        groups_to_enable = [group]
    else:
        return json.dumps({"error": f"Unknown group '{group}'. Valid: research, conductor, all"})

    enabled = []
    for g in groups_to_enable:
        for tool_name, tool_fn in _DEFERRED_TOOL_GROUPS[g].items():
            # Skip if already registered
            if tool_name in {t for t in mcp._tool_manager._tools}:
                continue
            mcp.add_tool(tool_fn, name=tool_name)
            enabled.append(tool_name)

    return json.dumps({"enabled": enabled, "group": group})


def main():
    """Entry point for cortex-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
