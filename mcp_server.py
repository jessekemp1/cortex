#!/usr/bin/env python3
"""
Cortex MCP Server — Official MCP SDK over stdio.

Exposes Cortex intelligence as MCP tools for Claude Code.

The core memory-loop tools run IN-PROCESS (no HTTP round-trip, no running
bridge daemon required): record_decision, intelligence, recommendations,
outcomes, plan_create, plan_progress, projects, doctor. Decision writes are
crash-proof via mcp_handlers (direct append + spool fallback). The remaining
tools still pass through to the bridge daemon at :8765.

Tools:
  Golden five (always registered — the smallest credible beta surface):
  - cortex_intelligence: Natural language query → insights (in-process)
  - cortex_record_decision: Record a decision for the learning loop (in-process)
  - cortex_outcomes: Outcome tracking — shipped, validated, failed (in-process)
  - cortex_service_health: Ecosystem health (bridge passthrough; degrades to an
    honest "bridge unavailable" envelope when the :8765 daemon is down)
  - cortex_doctor: System health check (Python, deps, API keys, bridge, spool)

  The session-briefing/debrief hooks reach cortex over the bridge's HTTP API
  and via mcp_handlers in-process — they do NOT depend on any non-golden MCP
  tool — so nothing beyond the golden five needs to stay visible for them.

  Experimental 13 (registered only when CORTEX_EXPERIMENTAL=1):
  - in-process memory-loop extras: cortex_recommendations, cortex_projects,
    cortex_plan_create, cortex_plan_progress
  - bridge passthroughs (need the :8765 daemon): cortex_anomalies,
    cortex_sessions, cortex_taskboard, cortex_conductor_compose,
    cortex_graph_query, cortex_batch_status
  - other: cortex_orchestrate, cortex_prompt_refine, cortex_research_digest

Resources:
  - cortex://goals: Current GOALS.md content
  - cortex://metrics/tests: Test results by project
  - cortex://metrics/emos: EMOS pair counts
  - cortex://prompts/patterns: Learned prompt patterns and category hints
"""

from __future__ import annotations

import json
import os
import threading
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


# Lazy singleton for direct CortexBridge access.
# Importing CortexBridge triggers ~16s of optional ML imports — DO NOT eagerly
# instantiate at module load. First MCP tool call pays the cost; subsequent
# calls reuse the cached instance.
_bridge_singleton = None
_bridge_lock = threading.Lock()


def _get_bridge():
    """Lazy CortexBridge instance — instantiated on first call, then cached.

    Uses a single canonical import path (`bridge`) to guarantee one shared
    CortexBridge instance across all callers. Importing via both `bridge`
    and `cortex.bridge` produces two distinct module objects with distinct
    classes — a real-world hazard before this standardized on the bare
    name (bridge.py adds CORTEX_ROOT to sys.path on import).

    Thread-safe: FastMCP can dispatch tool calls concurrently. Without the
    lock, two tools racing on a cold process could both see `None` and each
    construct a CortexBridge — a 16s double-init plus two divergent instances.
    Double-checked locking keeps the hot path lock-free after warm-up.
    """
    global _bridge_singleton
    if _bridge_singleton is None:
        with _bridge_lock:
            if _bridge_singleton is None:
                from bridge import CortexBridge  # noqa: WPS433  type: ignore

                _bridge_singleton = CortexBridge()
    return _bridge_singleton


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


_EXPERIMENTAL = bool(os.environ.get("CORTEX_EXPERIMENTAL"))


def _experimental_tool(fn):
    """Register as an MCP tool only when CORTEX_EXPERIMENTAL=1.

    MVP surface trim: the core-8 memory-loop tools are always registered;
    the passthrough/ops tools join only in experimental mode. The function
    itself stays importable and callable either way (contract tests and
    direct callers are unaffected) — only MCP registration is gated.
    """
    return mcp.tool()(fn) if _EXPERIMENTAL else fn


# ── Tools ──


@mcp.tool()
def cortex_service_health() -> str:
    """Get ecosystem health: bridge, Vortex, Mission Control, test results, and EMOS pair counts.

    Golden-five tool: always registered. This is the one bridge passthrough in
    the golden set, so it must never hang or crash when the :8765 daemon is
    down. _bridge_get caps the connect at a short timeout and maps URLError to
    an error dict; here we normalize that into an explicit, honest
    "bridge unavailable" envelope (bridge_up=false) rather than surfacing a raw
    urllib reason — the caller learns the truth without a stack trace or a hang.
    """
    result = _bridge_get("/service-health", timeout=2.0)
    if isinstance(result, dict) and "error" in result:
        return json.dumps(
            {
                "bridge_up": False,
                "status": "bridge unavailable",
                "detail": result["error"],
                "hint": "Start the bridge daemon (:8765) to get live ecosystem health.",
            },
            indent=2,
        )
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
    try:
        bridge = _get_bridge()
        # Resolve project when omitted: prefer the bridge's git-aware detector
        # (derived from CORTEX_ROOT_DIR), then keyword auto-detect over the
        # user's discovered projects. Never default to a literal "cortex".
        # (Same resolution order as POST /intelligence/query.)
        if not project:
            try:
                project = bridge._detect_current_project()
            except Exception:
                project = None
            if not project:
                import mcp_handlers

                project = mcp_handlers.auto_detect_project(query)
        result = bridge.query_intelligence(
            request=query, project=project, query_type=query_type
        )
        # Recall instrumentation (Workstream B) — append a best-effort event on
        # the in-process path too, so the "memory is being used" signal keeps
        # accruing even when the bridge daemon (:8765) is down. Never breaks the
        # query: record_recall_event swallows its own exceptions and skips
        # error results.
        try:
            from intelligence.recall_events import record_recall_event

            record_recall_event(result)
        except Exception:
            pass
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


@_experimental_tool
def cortex_recommendations(project: str = "", limit: int = 5) -> str:
    """Get strategic recommendations: next action, risk alerts, and priority projects.

    Args:
        project: Optional project filter.
        limit: Max recommendations (default 5).
    """
    try:
        import mcp_handlers

        bridge = _get_bridge()
        raw = bridge.get_recommendations()
        result = mcp_handlers.normalize_recommendations(
            raw, project=project or None, limit=limit
        )
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


@_experimental_tool
def cortex_anomalies() -> str:
    """Get detected anomalies across all projects with severity and recommendations."""
    result = _bridge_get("/anomalies", timeout=15.0)
    return json.dumps(result, indent=2)


@_experimental_tool
def cortex_projects() -> str:
    """Get status overview of all active projects (health, test counts, recent activity)."""
    try:
        import mcp_handlers

        result = mcp_handlers.compute_projects()
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


@_experimental_tool
def cortex_sessions(active_only: bool = False) -> str:
    """Get Claude Code sessions (active or recent). Shows session IDs, duration, and projects touched."""
    param = "?active_only=true" if active_only else ""
    result = _bridge_get(f"/sessions{param}")
    return json.dumps(result, indent=2)


@_experimental_tool
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


@_experimental_tool
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


@_experimental_tool
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
        # Route schema (PromptComposeRequest) names this project_id; sending
        # "project" made every call 422 with "Unprocessable Content".
        "project_id": project,
        "intent_level": intent_level,
        "include_context": include_context,
    }
    result = _bridge_post("/conductor/compose", payload, timeout=10.0)
    return json.dumps(result, indent=2)


@_experimental_tool
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


@_experimental_tool
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


@_experimental_tool
def cortex_plan_create(project: str, title: str = "") -> str:
    """Create an execution plan for a project. Parses GOALS.md for active items.

    Args:
        project: Target project (vortex, cortex, alpha-arena, pupil, etc.).
        title: Optional plan title. Auto-generated from goals if omitted.
    """
    try:
        import mcp_handlers

        result = mcp_handlers.create_plan(project, title or None)
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


@_experimental_tool
def cortex_plan_progress() -> str:
    """Get progress summary of all active plans."""
    try:
        import mcp_handlers

        result = mcp_handlers.plans_progress()
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


# ── Ops Tools ──


@_experimental_tool
def cortex_batch_status(batch_id: str) -> str:
    """Get detailed status of a specific batch job.

    Args:
        batch_id: The batch job identifier.
    """
    result = _bridge_get(f"/batches/{batch_id}")
    return json.dumps(result, indent=2)


@mcp.tool()
def cortex_record_decision(
    decision: str,
    context: str = "",
    alternatives: str = "",
    rationale: str = "",
    project: str = "",
) -> str:
    """Record a decision for the Cortex learning loop.

    Writes in-process (crash-proof: direct append with spool fallback) — a
    decision is never lost to a dead bridge daemon.

    Args:
        decision: What was decided.
        context: Why this decision was needed.
        alternatives: What other options existed (comma-separated or prose).
        rationale: Why this option was chosen over alternatives.
        project: Project this decision belongs to. Pass it whenever known —
            untagged decisions are much harder to recall per-project later.
    """
    try:
        import mcp_handlers

        result = mcp_handlers.record_learning_decision(
            decision=decision,
            context=context,
            alternatives=alternatives,
            rationale=rationale,
            project=project,
        )
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


# ── Portfolio Tools ──


@mcp.tool()
def cortex_outcomes(project: str = "", limit: int = 20) -> str:
    """Get outcome tracking data — what shipped, what validated, what failed.

    Args:
        project: Filter by project name.
        limit: Max results (default 20).
    """
    try:
        import mcp_handlers

        result = mcp_handlers.read_outcomes(project=project, limit=limit)
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


# ── CRA Research Tools ──


@_experimental_tool
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

    # Decision spool (entries stranded by a failed primary append)
    try:
        import mcp_handlers

        depth = mcp_handlers.spool_depth()
        checks.append(
            {
                "check": "decision spool empty",
                "pass": depth == 0,
                "detail": "empty" if depth == 0 else f"{depth} pending — run: cortex doctor --fix",
            }
        )
    except Exception as e:
        checks.append({"check": "decision spool empty", "pass": False, "detail": str(e)})

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
