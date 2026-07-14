#!/usr/bin/env python3
"""
Cortex MCP Server — Official MCP SDK over stdio.

Exposes Cortex Bridge intelligence as MCP tools for Claude Code.
Connects to bridge at :8765 via HTTP (no heavy imports).

Tools (18 always-loaded):
  Core:
  - cortex_service_health: Ecosystem health (all services, tests)
  - cortex_intelligence: Natural language query → insights
  - cortex_recommendations: Next actions and risk alerts
  - cortex_anomalies: Detected anomalies across projects
  - cortex_projects: Project status overview
  - cortex_sessions: Active/recent Claude sessions
  - cortex_taskboard: Task board items (list/filter)
  - cortex_orchestrate: Discover and dispatch work items via Conductor
  - cortex_prompt_refine: Get refinement suggestions for any prompt
  - cortex_conductor_compose: Receive composed prompt from Conductor UI

  Operations (always available — no enable step required):
  - cortex_graph_query: Search context graph by type or text
  - cortex_plan_create: Create execution plan from project goals
  - cortex_plan_progress: Get progress summary of all active plans
  - cortex_batch_status: Get detailed status of a specific batch job
  - cortex_outcomes: Outcome tracking (shipped, validated, failed)
  - cortex_record_decision: Record a decision for the learning loop

  Intelligence:
  - cortex_research_digest: CRA weekly research digest
  - cortex_doctor: System health check (Python, deps, API keys, bridge)

Resources:
  - cortex://goals: Current GOALS.md content
  - cortex://metrics/tests: Test results by project
  - cortex://metrics/emos: EMOS pair counts
  - cortex://prompts/patterns: Learned prompt patterns and category hints
"""

from __future__ import annotations

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
DOMAIN = os.environ.get("CORTEX_DOMAIN", "aidev")

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
    """Get ecosystem health: bridge, Vortex, Mission Control, test results, and EMOS pair counts."""
    result = _bridge_get("/service-health")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_intelligence(
    query: str, query_type: str = "research", project: str | None = None
) -> str:
    """Query Cortex intelligence engine with natural language.

    Args:
        query: Natural language question about the codebase or projects.
        query_type: One of 'spec', 'architecture', 'implementation', 'research'.
        project: Project to scope the query to (e.g. 'interac', 'manulife-genie').
            Pass it whenever you know which project the question is about — explicit
            scoping yields the most relevant recall. When omitted, the bridge falls back
            to auto-detecting from its working directory, which is unreliable; leave empty
            only for genuinely project-agnostic queries.
    """
    valid_types = {"spec", "architecture", "implementation", "research"}
    if query_type not in valid_types:
        query_type = "research"
    payload = {"request": query, "domain": DOMAIN, "query_type": query_type}
    if project:
        payload["project"] = project
    # Intelligence queries run hybrid retrieval and portfolio scans on the
    # bridge; measured latency is ~10s+ so the 5s default guarantees timeouts.
    result = _bridge_post("/intelligence/query", payload, timeout=60.0)
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_recommendations() -> str:
    """Get strategic recommendations: next action, risk alerts, and priority projects."""
    result = _bridge_get("/intelligence/recommendations", timeout=30.0)
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_anomalies() -> str:
    """Get detected anomalies across all projects with severity and recommendations."""
    result = _bridge_get("/anomalies", timeout=15.0)
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


# ── Graph Tools ──


@mcp.tool()
def cortex_graph_query(node_type: str = "", query: str = "", limit: int = 10) -> str:
    """Search the Cortex context graph by node type or text query.

    Node types: goal, project, file, pattern, lesson, error, dependency, work_item.
    Returns nodes with relationships and metadata.

    Args:
        node_type: Filter by node type (optional).
        query: Text search across node names and data (optional).
        limit: Max results (default 10).
    """
    params = []
    if node_type:
        params.append(f"node_type={node_type}")
    if query:
        params.append(f"q={query}")
    if limit != 10:
        params.append(f"limit={limit}")
    qs = "?" + "&".join(params) if params else ""
    result = _bridge_get(f"/graph/query{qs}", timeout=15.0)
    return json.dumps(result, indent=2)


# ── Planning Tools ──


@mcp.tool()
def cortex_plan_create(project: str, title: str = "") -> str:
    """Create an execution plan for a project. Parses GOALS.md for active items.

    Args:
        project: Target project (vortex, cortex, alpha-arena, pupil, etc.).
        title: Optional plan title. Auto-generated from goals if omitted.
    """
    payload = {"project": project}
    if title:
        payload["title"] = title
    result = _bridge_post("/plans/create", payload)
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_plan_progress() -> str:
    """Get progress summary of all active plans."""
    result = _bridge_get("/plans/progress")
    return json.dumps(result, indent=2)


# ── Ops Tools ──


@mcp.tool()
def cortex_batch_status(batch_id: str) -> str:
    """Get detailed status of a specific batch job.

    Args:
        batch_id: The batch job identifier.
    """
    result = _bridge_get(f"/batches/{batch_id}")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_record_decision(
    decision: str, context: str = "", alternatives: str = "", rationale: str = ""
) -> str:
    """Record a decision for the Cortex learning loop.

    Args:
        decision: What was decided.
        context: Why this decision was needed.
        alternatives: What other options existed (comma-separated or prose).
        rationale: Why this option was chosen over alternatives.
    """
    payload = {"decision": decision}
    if context:
        payload["context"] = context
    if alternatives:
        payload["alternatives"] = alternatives
    if rationale:
        payload["rationale"] = rationale
    result = _bridge_post("/decisions/learning", payload)
    return json.dumps(result, indent=2)


# ── Portfolio Tools ──


@mcp.tool()
def cortex_outcomes(project: str = "", limit: int = 20) -> str:
    """Get outcome tracking data — what shipped, what validated, what failed.

    Args:
        project: Filter by project name.
        limit: Max results (default 20).
    """
    params = []
    if project:
        params.append(f"project={project}")
    if limit != 20:
        params.append(f"limit={limit}")
    qs = "?" + "&".join(params) if params else ""
    result = _bridge_get(f"/v2/outcomes{qs}")
    return json.dumps(result, indent=2)


# ── CRA Research Tools ──


@mcp.tool()
def cortex_research_digest() -> str:
    """Get the CRA weekly research digest — discoveries, assessments, urgent threats, and pending proposals."""
    try:
        from cortex.engines.research_agent import CortexResearchAgent

        agent = CortexResearchAgent()
        return agent.weekly_digest()
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── System Tools ──


@mcp.tool()
def cortex_doctor() -> str:
    """Run Cortex system health check: Python version, dependencies, API keys, bridge, and data dir."""
    import socket
    import sys

    checks = []

    # Python version
    major, minor = sys.version_info[:2]
    checks.append(
        {
            "check": "Python >= 3.11",
            "pass": (major, minor) >= (3, 11),
            "detail": f"{major}.{minor}.{sys.version_info.micro}",
        }
    )

    # Key dependencies
    for dep in ("anthropic", "sklearn", "fastapi"):
        try:
            mod = __import__(dep)
            ver = getattr(mod, "__version__", "?")
            checks.append({"check": f"{dep} importable", "pass": True, "detail": ver})
        except ImportError:
            checks.append({"check": f"{dep} importable", "pass": False, "detail": "missing"})

    # API key
    checks.append(
        {
            "check": "ANTHROPIC_API_KEY set",
            "pass": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "detail": "present" if os.environ.get("ANTHROPIC_API_KEY") else "missing",
        }
    )

    # Data dir
    data_dir = Path.home() / ".cortex"
    checks.append(
        {
            "check": "~/.cortex/ exists",
            "pass": data_dir.exists(),
            "detail": str(data_dir) if data_dir.exists() else "missing",
        }
    )

    # Bridge
    bridge_up = False
    try:
        s = socket.create_connection(("127.0.0.1", 8765), timeout=1)
        s.close()
        bridge_up = True
    except OSError:
        pass
    checks.append(
        {
            "check": "bridge :8765 reachable",
            "pass": bridge_up,
            "detail": "up" if bridge_up else "down",
        }
    )

    all_pass = all(c["pass"] for c in checks)
    return json.dumps({"checks": checks, "all_pass": all_pass}, indent=2)


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


def main():
    """Entry point for cortex-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
