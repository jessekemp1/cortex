# PRD: Cortex MCP Server V2

**Author:** Jesse Kemp | **Date:** 2026-03-27 | **Status:** READY TO SHIP
**Effort:** ~4h implementation, ~1h testing | **Deploy:** Same day

---

## Problem

Cortex exposes 45+ REST endpoints via `bridge_endpoint.py` at `:8765`. The MCP server (`mcp_server.py`) only wraps 15 of them. Any MCP-connected agent (Claude Code, Claude Desktop, Cowork, third-party) can only access ~33% of Cortex's capability. The rest requires either direct HTTP calls or CLI usage.

The industry has converged on MCP as the universal agent integration standard (97M monthly SDK downloads, adopted by OpenAI/Google/Microsoft). Cortex's partial MCP coverage means external agents hit a wall and fall back to unstructured workarounds.

## Current State

**Exposed via MCP (15 tools, 4 resources):**

| Tool | Bridge Endpoint | Group |
|------|----------------|-------|
| `cortex_service_health` | `GET /service-health` | core |
| `cortex_intelligence` | `POST /intelligence/query` | core |
| `cortex_recommendations` | `GET /intelligence/recommendations` | core |
| `cortex_anomalies` | `GET /anomalies` | core |
| `cortex_projects` | `GET /projects` | core |
| `cortex_sessions` | `GET /sessions` | core |
| `cortex_taskboard` | `GET /taskboard` | core |
| `cortex_create_task` | `POST /taskboard` | core |
| `cortex_emos_status` | file read | core |
| `cortex_prompt_refine` | file read | core |
| `cortex_orchestrate` | direct import | core |
| `cortex_enable_tools` | meta | core |
| `cortex_conductor_compose` | `POST /conductor/compose` | deferred:conductor |
| `cortex_conductor_startup` | `GET /conductor/startup` | deferred:conductor |
| `cortex_research_status` | direct import | deferred:research |
| `cortex_research_digest` | direct import | deferred:research |
| `cortex_research_proposals` | direct import | deferred:research |

**NOT exposed via MCP (30+ endpoints):**

| Category | Endpoints | Why It Matters |
|----------|-----------|---------------|
| V2 Prime Graph | `GET /graph/query`, `GET /v2/graph/search`, `GET /v2/graph/stats` | Context graph is Cortex's differentiator — invisible to MCP agents |
| Memory & Context | `POST /intelligence/reason`, `POST /signal/absorb`, `GET /signal/bus-stats` | Agents can't feed signals back or use deep reasoning |
| Planning | No endpoint yet (bridge methods only) | `create_plan`, `start_plan`, `complete_step` — core workflow, zero MCP access |
| Batch Ops | `GET /batches`, `GET /batches/{id}`, `POST /batches/{id}/cancel` | Can't monitor or cancel batch jobs |
| Queue | `GET /queue`, `POST /queue`, `DELETE /queue/{id}` | Can't manage work queue |
| Guardian | `POST /guardian/claim`, `/release`, `/snapshot`, `/recover` | Deploy safety net invisible to agents |
| Portfolio | `GET /v2/outcomes`, `/v2/outcomes/stats`, `/v2/compound-health` | Cross-project intelligence locked behind HTTP |
| Docs | `GET /docs/tree`, `GET /docs/content` | Can't browse project documentation |
| Decisions | `POST /decisions/record` | Can't log decisions for learning loop |
| Predictions | `GET /predictions/current` | Can't read active predictions |
| Activity | `GET /activity/heatmap` | Can't see where work is happening |
| Meta | `GET /meta/compounding`, `/meta/compounding/portfolio`, `/meta/compounding/file` | Examined Engineer triggers invisible |

## Design

### Architecture Decision: Thin HTTP Proxy (Keep Current Pattern)

The existing MCP server uses `_bridge_get`/`_bridge_post` to proxy to `:8765`. This is the right call:

- **No heavy imports** — MCP process stays lightweight (~10MB RSS)
- **Bridge API is the single source of truth** — no divergent codebases
- **Bridge already running** — required for Conductor UI, Streamlit, etc.
- **Crash isolation** — MCP server can't take down the bridge

Exception: direct imports for CRA (research agent) and orchestration are fine where bridge endpoints don't exist yet.

### Tool Group Architecture (Deferred Loading)

Current deferred loading already works. V2 extends this to 6 groups:

| Group | Load | Tools | Token Budget |
|-------|------|-------|-------------|
| `core` | always | 8 tools | ~2,000 tokens |
| `orchestration` | always | 2 tools | ~500 tokens |
| `graph` | deferred | 4 tools | ~800 tokens |
| `planning` | deferred | 5 tools | ~1,000 tokens |
| `research` | deferred | 3 tools (existing) | ~600 tokens |
| `conductor` | deferred | 2 tools (existing) | ~400 tokens |
| `ops` | deferred | 6 tools | ~1,200 tokens |
| `portfolio` | deferred | 5 tools | ~1,000 tokens |

**Default session cost:** ~2,500 tokens (core + orchestration).
**Full load:** ~7,500 tokens. Current V1 is ~3,100 tokens.
**With `defer_loading: true` in MCP config:** Claude Code's Tool Search handles discovery, so even "always" tools could be deferred. Net effect: **85% token reduction** per session (per CRA research brief).

### New Tools Spec

#### Group: `graph` (deferred)

```python
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

@mcp.tool()
def cortex_graph_stats() -> str:
    """Get context graph statistics: node counts by type, edge counts, density."""

@mcp.tool()
def cortex_graph_add_node(node_type: str, name: str, data: str = "{}") -> str:
    """Add a node to the context graph.

    Args:
        node_type: One of: goal, project, pattern, lesson, decision, warning.
        name: Human-readable node name.
        data: JSON string of additional metadata.
    """

@mcp.tool()
def cortex_graph_search(query: str, node_types: str = "", limit: int = 5) -> str:
    """Semantic search across the V2 context graph.

    Args:
        query: Natural language search query.
        node_types: Comma-separated filter (e.g., "pattern,lesson").
        limit: Max results.
    """
```

#### Group: `planning` (deferred)

```python
@mcp.tool()
def cortex_plan_create(project: str, title: str = "") -> str:
    """Create an execution plan for a project. Parses GOALS.md for active items.

    Args:
        project: Target project (vortex, cortex, alpha-arena, pupil, etc.).
        title: Optional plan title. Auto-generated from goals if omitted.
    """

@mcp.tool()
def cortex_plan_list(status: str = "") -> str:
    """List all execution plans, optionally filtered by status.

    Args:
        status: Filter by status: draft, active, completed, abandoned.
    """

@mcp.tool()
def cortex_plan_get(plan_id: str) -> str:
    """Get plan details including steps, progress, and dependencies.

    Args:
        plan_id: The plan identifier.
    """

@mcp.tool()
def cortex_plan_step(plan_id: str, step_id: str, action: str = "complete", notes: str = "") -> str:
    """Update a plan step: complete it, skip it, or add notes.

    Args:
        plan_id: The plan identifier.
        step_id: The step identifier.
        action: One of: complete, skip, block.
        notes: Optional notes about the step outcome.
    """

@mcp.tool()
def cortex_plan_progress() -> str:
    """Get progress summary of all active plans."""
```

#### Group: `ops` (deferred)

```python
@mcp.tool()
def cortex_batch_list() -> str:
    """List all batch jobs with status and progress."""

@mcp.tool()
def cortex_batch_status(batch_id: str) -> str:
    """Get detailed status of a specific batch job.

    Args:
        batch_id: The batch job identifier.
    """

@mcp.tool()
def cortex_queue_list(status: str = "") -> str:
    """List work queue items, optionally filtered by status.

    Args:
        status: Filter: pending, running, completed, failed.
    """

@mcp.tool()
def cortex_queue_add(task: str, project: str = "", priority: str = "medium") -> str:
    """Add a work item to the queue.

    Args:
        task: Task description.
        project: Target project.
        priority: critical, high, medium, low.
    """

@mcp.tool()
def cortex_signal_absorb(signals: str) -> str:
    """Feed signals into the Cortex signal bus for processing.

    Args:
        signals: JSON array of signal objects with type, source, and data fields.
    """

@mcp.tool()
def cortex_record_decision(decision: str, context: str = "", alternatives: str = "", rationale: str = "") -> str:
    """Record a decision for the learning loop.

    Args:
        decision: What was decided.
        context: Why this decision was needed.
        alternatives: What other options existed.
        rationale: Why this option was chosen.
    """
```

#### Group: `portfolio` (deferred)

```python
@mcp.tool()
def cortex_outcomes(project: str = "", limit: int = 20) -> str:
    """Get outcome tracking data — what shipped, what validated, what failed.

    Args:
        project: Filter by project.
        limit: Max results.
    """

@mcp.tool()
def cortex_compound_health() -> str:
    """Get compound health score across all projects — trends, risk areas, momentum."""

@mcp.tool()
def cortex_docs_tree(project: str = "") -> str:
    """Browse project documentation tree structure.

    Args:
        project: Filter by project. Shows all if omitted.
    """

@mcp.tool()
def cortex_docs_content(path: str) -> str:
    """Read documentation content by path.

    Args:
        path: Document path from docs_tree output.
    """

@mcp.tool()
def cortex_activity_heatmap(days: int = 7) -> str:
    """Get activity heatmap showing where work is concentrated.

    Args:
        days: Lookback window (default 7).
    """
```

### New Resources

```python
@mcp.resource("cortex://graph/stats")    # V2 graph summary
@mcp.resource("cortex://queue/pending")  # Current work queue
@mcp.resource("cortex://plans/active")   # Active execution plans
@mcp.resource("cortex://health/compound") # Compound health score
```

### Elicitation Hooks (Phase 2)

Per the CRA research brief, MCP now supports mid-task elicitation — structured input dialogs during tool execution. Wire this for:

1. **`cortex_signal_absorb`** — confirm before writing signals that modify graph state
2. **`cortex_record_decision`** — prompt for missing `rationale` if omitted
3. **`cortex_queue_add` with priority=critical** — confirm before creating critical-priority work

Implementation: Use `ctx.session.create_elicitation_request()` when available in the MCP SDK. Fallback: return a confirmation prompt in the tool response and require a second call.

### MCP Config for Claude Code

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["-m", "cortex.mcp_server"],
      "env": {
        "CORTEX_ROOT_DIR": "~/Dev",
        "CORTEX_DOMAIN": "aidev"
      }
    }
  }
}
```

For **85% token savings**, add to `.claude/settings.json`:
```json
{
  "mcpServers": {
    "cortex": {
      "defer_loading": true
    }
  }
}
```

This makes Claude Code discover tools via Tool Search instead of loading all definitions upfront. Already validated by Anthropic at 88.1% accuracy on MCP evals.

## Implementation Plan

### Phase 1: Core Gap Fill (~2h) — SHIP THIS

1. **Add bridge endpoints** for planning (`/plans/*`) and decisions (`/decisions/record`) — these exist as bridge methods but have no REST route
2. **Add 20 new MCP tools** across 4 deferred groups (graph, planning, ops, portfolio)
3. **Update deferred loading** — extend `_DEFERRED_TOOL_GROUPS` with new groups
4. **Add 4 new resources**
5. **Test:** Verify each tool returns valid JSON via `mcp dev cortex.mcp_server`

### Phase 2: Optimization (~1h)

1. **Enable `defer_loading: true`** in MCP config
2. **Measure token savings** — compare session init cost before/after
3. **Add tool descriptions** optimized for Tool Search discovery (keyword-rich, action-oriented)

### Phase 3: Elicitation (defer until MCP SDK ships it)

1. Wire elicitation hooks for write operations
2. Add confirmation flow for critical-priority queue items

## Success Criteria

1. All 45 bridge endpoints reachable via MCP tools
2. Default session token cost ≤3,000 tokens (with deferred loading)
3. Full load ≤8,000 tokens
4. `mcp dev` smoke test passes for all tools
5. Claude Code can execute full workflow via MCP only: query → plan → execute → record decision → check outcomes

## Non-Goals

- **No new bridge endpoints for V2 Prime** — use existing REST surface. If an endpoint doesn't exist, the tool imports directly (same pattern as CRA tools)
- **No auth on MCP** — localhost only, same trust model as current
- **No streaming** — tools return complete JSON. Streaming is a V3 concern when context windows grow beyond 1M
- **No A-MEM integration** — flagged by CRA brief but out of scope. Separate PRD for memory architecture overhaul

## Risk

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Bridge not running when MCP tools called | Medium | Tool returns error | Already handled: `_bridge_get` returns `{"error": "Bridge unavailable"}` — agent sees clean failure |
| Tool count bloat slows Tool Search | Low | Slower discovery | Deferred loading + group architecture limits default to 10 tools |
| Direct imports (CRA pattern) cause import errors | Low | Tool fails silently | Existing try/except pattern handles this — tool returns error dict |

## Dependencies

- `mcp` Python SDK (already installed, FastMCP)
- Bridge API running at `:8765` (existing `launchd` service)
- Planning methods on CortexBridge (exist in `bridge_system.py`, may need REST routes)

## Relationship to CRA Research Brief

This PRD directly addresses three signals from the March 26 research brief:

1. **"MCP Tool Search reduces token usage by 85%"** → Phase 2 enables `defer_loading: true`
2. **"MCP elicitation support enables interactive agent dialogs"** → Phase 3 wires confirmation hooks
3. **"Memory as the differentiator"** → Full MCP coverage of graph/planning/signals makes Cortex's memory architecture accessible to any agent, not just HTTP clients

[Conf: 90% | Assumption: Bridge API stays stable | Flips if: MCP SDK breaks deferred loading | 6mo: Cortex becomes composable with any MCP agent — third-party tools can query context graph]
