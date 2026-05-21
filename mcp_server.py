#!/usr/bin/env python3
"""
Cortex MCP Server — Official MCP SDK over stdio.

Exposes Cortex intelligence as MCP tools for Claude Code.

Since Phase 5, every tool runs IN-PROCESS — no HTTP, no bridge daemon.
Tools call either a lazy CortexBridge singleton (see _get_bridge) or the
stdlib-only helpers in mcp_handlers.py / health_probe.py. The HTTP bridge
at :8765 is optional infrastructure used only by local agents (Hermes).

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
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

METRICS_DIR = Path.home() / ".cortex" / "metrics"
GOALS_FILE = Path(os.environ.get("CORTEX_ROOT_DIR", Path.home() / "Dev")) / "GOALS.md"
PROMPTS_DIR = Path.home() / ".cortex" / "prompts"
DOMAIN = os.environ.get("CORTEX_DOMAIN", "aidev")

mcp = FastMCP("cortex")


# Phase 5: Lazy singleton for direct CortexBridge access.
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
    classes — a real-world hazard before Phase 5 standardized on the bare
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


# ── Tools ──


@mcp.tool()
def cortex_service_health() -> str:
    """Get ecosystem health: bridge, Vortex, Mission Control, test results, and EMOS pair counts."""
    # Phase 5: direct call to standalone health_probe — no HTTP, no CortexBridge.
    # Single canonical import path to avoid the double-import hazard
    # (`bridge` vs `cortex.bridge` produced two distinct module objects).
    import health_probe

    services = health_probe.compute_service_health()
    statuses = [
        s.get("status") for s in services.values() if isinstance(s, dict) and "status" in s
    ]
    overall = "healthy" if all(s == "healthy" for s in statuses) else "degraded"
    return json.dumps({"overall": overall, "services": services}, indent=2)


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
    # Phase 5 Step 3: direct CortexBridge.query_intelligence call.
    try:
        bridge = _get_bridge()
        result = bridge.query_intelligence(
            request=query,
            project=DOMAIN,
            query_type=query_type,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_recommendations() -> str:
    """Get strategic recommendations: next action, risk alerts, and priority projects."""
    # Phase 5 Step 2: direct call to CortexBridge.get_recommendations (no HTTP).
    try:
        bridge = _get_bridge()
        recommendations = bridge.get_recommendations()
        # Apply the same default-limit normalization the HTTP route does.
        if isinstance(recommendations, dict) and "recommendations" in recommendations:
            recommendations["recommendations"] = recommendations["recommendations"][:5]
        return json.dumps(recommendations, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_anomalies() -> str:
    """Get detected anomalies across all projects with severity and recommendations."""
    # Phase 5 Step 2: direct call to OrchestrationAnomalyManager.
    try:
        from orchestration.anomaly_detector import OrchestrationAnomalyManager
        from orchestration.database import OrchestrationDatabase

        manager = OrchestrationAnomalyManager(OrchestrationDatabase())
        context = {
            "active_projects": ["cortex", "vortex", "alpha_arena"],
            "total_projects": 4,
            "goals_in_progress": 2,
            "goals_pending": 1,
        }
        anomalies = manager.detect_all(context=context)
        # Manager returns Anomaly objects; convert to dicts for JSON.
        result = []
        for a in anomalies:
            sev = getattr(a.severity, "value", a.severity) if hasattr(a, "severity") else None
            result.append(
                {
                    "id": getattr(a, "id", None),
                    "type": getattr(a, "type", None),
                    "severity": sev,
                    "message": getattr(a, "message", None),
                    "recommendation": getattr(a, "recommendation", None),
                }
            )
        return json.dumps({"anomalies": result, "total": len(result)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_projects() -> str:
    """Get status overview of all active projects (health, test counts, recent activity)."""
    # Phase 5 Step 2: direct filesystem scan via mcp_handlers.
    import mcp_handlers

    return json.dumps(mcp_handlers.compute_projects(), indent=2)


@mcp.tool()
def cortex_sessions(active_only: bool = False) -> str:
    """Get Claude Code sessions (active or recent). Shows session IDs, duration, and projects touched."""
    # Phase 5 Step 2: direct filesystem scan via mcp_handlers.
    import mcp_handlers

    return json.dumps(mcp_handlers.scan_sessions(active_only=active_only), indent=2)


@mcp.tool()
def cortex_taskboard(status: str = "", project: str = "") -> str:
    """Get task board items, optionally filtered by status (pending/in_progress/done) or project name."""
    # Phase 5 Step 2: direct filesystem read via mcp_handlers.
    import mcp_handlers

    return json.dumps(
        mcp_handlers.query_taskboard(
            status=status or None,
            project=project or None,
        ),
        indent=2,
    )


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

    # Phase 5 Step 3: direct call to mcp_handlers.compose_conductor_prompt.
    import mcp_handlers

    try:
        result = mcp_handlers.compose_conductor_prompt(
            intent=intent,
            project_id=project,
            intent_level=intent_level,
            include_context=include_context,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


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

    Node types: goal, project, pattern, lesson, decision, warning.
    Returns nodes with relationships and metadata.

    Args:
        node_type: Filter by node type (optional).
        query: Text search across node names and data (optional).
        limit: Max results (default 10).
    """
    # Phase 5 Step 2: direct CortexBridge.query_graph call (no HTTP).
    try:
        bridge = _get_bridge()
        if node_type:
            types_to_query = [node_type]
        else:
            try:
                from engines.synthesis import NodeType

                types_to_query = [nt.value for nt in NodeType]
            except ImportError:
                types_to_query = [
                    "goal",
                    "project",
                    "pattern",
                    "lesson",
                    "decision",
                    "warning",
                ]

        all_nodes: list[dict] = []
        for nt in types_to_query:
            try:
                nodes = bridge.query_graph(node_type=nt)
            except Exception:
                continue
            if isinstance(nodes, list):
                for n in nodes:
                    if isinstance(n, dict) and "error" not in n:
                        all_nodes.append(n)

        if query:
            needle = query.lower()
            all_nodes = [n for n in all_nodes if needle in json.dumps(n, default=str).lower()]

        truncated = all_nodes[:limit]
        result = {
            "node_type": node_type or None,
            "q": query or None,
            "count": len(truncated),
            "total_matched": len(all_nodes),
            "nodes": truncated,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Planning Tools ──


@mcp.tool()
def cortex_plan_create(project: str, title: str = "") -> str:
    """Create an execution plan for a project. Parses GOALS.md for active items.

    Args:
        project: Target project (vortex, cortex, alpha-arena, pupil, etc.).
        title: Optional plan title. Auto-generated from goals if omitted.
    """
    # Phase 5 Step 3: direct call to mcp_handlers.create_plan.
    import mcp_handlers

    try:
        result = mcp_handlers.create_plan(project=project, title=title or None)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_plan_progress() -> str:
    """Get progress summary of all active plans."""
    # Phase 5 Step 2: direct filesystem scan via mcp_handlers.
    import mcp_handlers

    try:
        return json.dumps(mcp_handlers.plans_progress(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Ops Tools ──


@mcp.tool()
def cortex_batch_status(batch_id: str) -> str:
    """Get detailed status of a specific batch job.

    Args:
        batch_id: The batch job identifier.
    """
    # Phase 5 Step 2: direct BatchAPIClient call.
    try:
        from batch.batch_api_client import BatchAPIClient

        client = BatchAPIClient()
        return json.dumps(client.get_batch_status(batch_id), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cortex_record_decision(
    decision: str,
    context: str = "",
    alternatives: str = "",
    rationale: str = "",
    project: str = "",
    confidence: float = 0.0,
    tags: str = "",
) -> str:
    """Record a decision for the Cortex learning loop.

    Args:
        decision: What was decided.
        context: Why this decision was needed.
        alternatives: What other options existed (comma-separated or prose).
        rationale: Why this option was chosen over alternatives.
        project: Optional project the decision applies to (vortex, cortex, …).
        confidence: Optional confidence 0.0-1.0.
        tags: Optional comma-separated tags.
    """
    # Phase 5 Step 3: direct call to mcp_handlers.record_freeform_decision.
    import mcp_handlers

    try:
        result = mcp_handlers.record_freeform_decision(
            decision=decision,
            context=context,
            alternatives=alternatives,
            rationale=rationale,
            project=project,
            confidence=confidence,
            tags=tags,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Portfolio Tools ──


@mcp.tool()
def cortex_outcomes(project: str = "", limit: int = 20) -> str:
    """Get outcome tracking data — what shipped, what validated, what failed.

    Args:
        project: Filter by project name.
        limit: Max results (default 20).
    """
    # Phase 5 Step 2: direct OutcomeDetector call.
    try:
        from v2.learning.outcomes import OutcomeDetector

        detector = OutcomeDetector()
        outcomes = detector.get_recent_outcomes(project=project or None, days=7)
        return json.dumps(
            {
                "outcomes": [o.to_dict() for o in outcomes[:limit]],
                "total": len(outcomes),
            },
            indent=2,
        )
    except ImportError as e:
        return json.dumps({"error": f"v2 module not available: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


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

    # Bridge — INFORMATIONAL ONLY. Since Phase 5 the MCP server runs fully
    # in-process; the HTTP bridge is optional infrastructure used only by
    # local agents (Hermes). "down" is not a failure for MCP users.
    bridge_up = False
    try:
        s = socket.create_connection(("127.0.0.1", 8765), timeout=1)
        s.close()
        bridge_up = True
    except OSError:
        pass
    checks.append(
        {
            "check": "bridge :8765 reachable (optional)",
            "pass": True,  # informational — never fails the overall check
            "detail": "up" if bridge_up else "down (optional — only needed by Hermes)",
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
