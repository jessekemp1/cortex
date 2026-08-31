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
    except urllib.error.HTTPError as e:
        # Bridge is up but returned a non-2xx (e.g. 404 for an unknown id).
        # HTTPError subclasses URLError, so catch it FIRST — otherwise a live
        # 404 gets mislabeled "Bridge unavailable" as if the daemon were down.
        detail = e.reason
        try:
            detail = json.loads(e.read()).get("detail", detail)
        except Exception:
            pass
        return {"error": f"Bridge HTTP {e.code}: {detail}", "status": e.code}
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
    except urllib.error.HTTPError as e:
        # Bridge is up but returned a non-2xx (e.g. 404 for an unknown id).
        # HTTPError subclasses URLError, so catch it FIRST — otherwise a live
        # 404 gets mislabeled "Bridge unavailable" as if the daemon were down.
        detail = e.reason
        try:
            detail = json.loads(e.read()).get("detail", detail)
        except Exception:
            pass
        return {"error": f"Bridge HTTP {e.code}: {detail}", "status": e.code}
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
    # Two distinct graph surfaces, and the args pick which one:
    #   /v2/graph/search  takes query= + limit=  (text search over the V2 graph)
    #   /graph/query      REQUIRES node_type=    (type lookup, no text, no limit)
    # This used to send q=/limit= to /graph/query, which accepts neither and
    # requires node_type — so any text query returned a bare 422.
    from urllib.parse import urlencode

    if query:
        qs = urlencode({"query": query, "limit": limit})
        result = _bridge_get(f"/v2/graph/search?{qs}", timeout=15.0)
    elif node_type:
        result = _bridge_get(
            f"/graph/query?{urlencode({'node_type': node_type})}", timeout=15.0
        )
        # /graph/query has no limit param, so bound it here rather than
        # handing the caller an unbounded node list.
        if isinstance(result, dict) and isinstance(result.get("nodes"), list):
            total = len(result["nodes"])
            if total > limit:
                result["nodes"] = result["nodes"][:limit]
                result["truncated"] = {"returned": limit, "total": total}
    else:
        result = {
            "error": "supply either query= (text search) or node_type= (type lookup)",
            "node_types": [
                "goal", "project", "file", "pattern",
                "lesson", "error", "dependency", "work_item",
            ],
        }
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
def cortex_plan_progress(project: str = "", limit: int = 25) -> str:
    """Get progress summary of active plans, newest first.

    Args:
        project: Optional project filter.
        limit: Max plans to return (default 25). Bounded deliberately — the
            unbounded form returned ~157KB across hundreds of plans, which
            would swamp the caller's context. `total` still reports the real
            count, so the cap is always visible.
    """
    try:
        import mcp_handlers

        result = mcp_handlers.plans_progress(project=project, limit=limit)
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
    supersedes: str = "",
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
        supersedes: Optional decision_id of a prior decision this one replaces.
            The old decision is tombstoned so it drops out of recall — use it
            when a decision reverses or updates an earlier one, instead of
            leaving both to compete in retrieval.
    """
    try:
        import mcp_handlers

        result = mcp_handlers.record_learning_decision(
            decision=decision,
            context=context,
            alternatives=alternatives,
            rationale=rationale,
            project=project,
            supersedes=supersedes,
        )
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2, default=str)


# ── Portfolio Tools ──


@mcp.tool()
def cortex_outcomes(project: str = "", limit: int = 20, exclude_types: str = "") -> str:
    """Get outcome tracking data — what shipped, what validated, what failed.

    Args:
        project: Filter by project name.
        limit: Max results (default 20).
        exclude_types: Comma-separated recommendation_type prefixes to drop.
            Pass "failure:" to hide machine-emitted operational telemetry
            (pytest / anomaly signals) and see only decision-linked outcomes.
            Nothing is excluded by default. The response always carries a
            `by_type` breakdown plus `total` / `returned` / `excluded` counts,
            so a burst of same-timestamp auto rows can't silently monopolize
            the newest-first window.
    """
    try:
        import mcp_handlers

        result = mcp_handlers.read_outcomes(
            project=project, limit=limit, exclude_types=exclude_types
        )
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

    # ── Retrieval correctness ───────────────────────────────────────────────
    # The checks above assert infrastructure (deps present, bridge listening).
    # They all passed while semantic recall was silently dead for every MCP
    # query, because nothing asserted that retrieval actually *works*. These
    # three close that gap. They compare state for CONSISTENCY rather than
    # probing the network, so they stay fast and don't fail merely because
    # Ollama is briefly down.
    checks.extend(_doctor_retrieval_checks())

    all_pass = all(c["pass"] for c in checks)
    return json.dumps({"checks": checks, "all_pass": all_pass}, indent=2)


def _doctor_retrieval_checks() -> list:
    """Assert semantic retrieval is wired and its cache is usable.

    Reads only the small pickle *metadata* file — never ``embeddings.pkl``
    (multi-MB) — so ``cortex_doctor`` stays fast.

    Returns a list of check dicts in the same shape as ``cortex_doctor``'s.
    """
    import pickle

    results = []
    meta_path = Path.home() / ".cortex" / "patterns" / "embeddings_meta.pkl"
    decisions_path = Path.home() / ".cortex" / "decisions.jsonl"

    cached_backend = None
    indexed_ids = []
    indexed_count = None
    if meta_path.exists():
        try:
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            cached_backend = meta.get("backend")
            indexed_ids = meta.get("pattern_ids", []) or []
            indexed_count = meta.get("pattern_count")
        except Exception as e:  # corrupt/unreadable cache is itself a finding
            results.append(
                {
                    "check": "embedding cache readable",
                    "pass": False,
                    "detail": f"{meta_path.name}: {e}",
                }
            )

    # 1. Live embedding backend must match the one the cache was built with.
    #    A mismatch means vectors on disk are incomparable to freshly generated
    #    ones — the condition that would otherwise trigger a full regeneration
    #    over a good cache.
    live_backend = None
    try:
        from intelligence.embeddings_client import EmbeddingsClient

        live_backend = EmbeddingsClient().get_embedding_info().get("backend")
    except Exception as e:
        live_backend = f"unavailable: {e}"

    if cached_backend is None:
        results.append(
            {
                "check": "embeddings backend matches cache",
                "pass": True,
                "detail": f"no cache yet; live backend {live_backend}",
            }
        )
    else:
        matches = cached_backend == live_backend
        results.append(
            {
                "check": "embeddings backend matches cache",
                "pass": matches,
                "detail": (
                    f"live={live_backend} cached={cached_backend}"
                    + ("" if matches else " — MISMATCH: recall degrades to keyword-only")
                ),
            }
        )

    # 2. The index must actually cover the decision store. This is the check
    #    that would have caught mis-reading the metadata dict's key count as
    #    the item count.
    n_decisions = 0
    if decisions_path.exists():
        try:
            with open(decisions_path, encoding="utf-8") as f:
                n_decisions = sum(1 for line in f if line.strip())
        except Exception:
            n_decisions = 0
    # Count only ids the loader actually produces for decisions. The index also
    # holds conversation- and git-derived patterns, so comparing the whole index
    # against the decision store would compare mismatched populations — and could
    # report more "indexed" than exist, which would make this check unable to fail.
    n_indexed_decisions = sum(
        1 for i in indexed_ids if str(i).startswith("decision:dec_")
    )
    if n_decisions == 0:
        coverage_pass = True
        coverage_detail = "no decisions recorded yet"
    else:
        # Tombstoned/superseded and low-signal decisions are intentionally
        # dropped from the index, so exact parity is not expected — but a zero
        # or tiny index against a populated store means indexing is broken.
        # Deliberately a floor, not parity. The index accumulates across
        # reindexes and id formats, so it can legitimately hold MORE
        # decision-prefixed patterns than the store currently has lines. What
        # this must catch is the opposite: an index that has collapsed to zero
        # or a fraction of the store while queries keep silently succeeding.
        coverage_pass = n_indexed_decisions > 0 and n_indexed_decisions >= n_decisions * 0.5
        coverage_detail = (
            f"{n_indexed_decisions} decision patterns indexed vs {n_decisions} "
            f"store lines ({indexed_count} patterns total, all sources)"
        )
        if not coverage_pass:
            coverage_detail += " — index does not cover the store; run a reindex"
    results.append(
        {
            "check": "embedding index covers decisions",
            "pass": coverage_pass,
            "detail": coverage_detail,
        }
    )

    # 3. The bridge must wire an embeddings client into its retriever. This is
    #    the exact wiring that was broken: bridge.py constructed
    #    HybridRetriever(patterns=...) with no client, so embeddings_available
    #    was False and every MCP query silently ran keyword-only.
    #
    #    Asserted by static inspection of the call sites rather than by building
    #    a retriever: constructing one loads the full pattern set and embedding
    #    cache (tens of seconds), which is far too slow for a health check.
    try:
        import inspect

        import bridge as _bridge_mod

        src = inspect.getsource(_bridge_mod)
        bad_calls = src.count("HybridRetriever(patterns=")
        wired = bad_calls == 0 and "EmbeddingsClient" in src
        results.append(
            {
                "check": "bridge wires embeddings into retrieval",
                "pass": wired,
                "detail": (
                    "embeddings client passed at all call sites"
                    if wired
                    else f"{bad_calls} HybridRetriever call site(s) missing "
                    "embeddings_client — MCP recall degrades to keyword-only"
                ),
            }
        )
    except Exception as e:
        results.append(
            {
                "check": "bridge wires embeddings into retrieval",
                "pass": False,
                "detail": f"could not inspect bridge call sites: {e}",
            }
        )

    return results


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
    # Load ~/.cortex/.env then repo .env so a key saved by install.sh reaches
    # the MCP server process without a shell export (real env vars still win).
    try:
        from env_loader import load_env

        load_env()
    except Exception:
        pass  # env loading must never block the server
    mcp.run()


if __name__ == "__main__":
    main()
