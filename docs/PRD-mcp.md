# PRD: Cortex MCP Server — Beta

**Author:** Jesse Kemp | **Date:** 2026-05-21 | **Status:** SHIPPED — beta-ready

Supersedes `PRD-mcp-v2` (2026-03-27). The v2 PRD planned 30 more tools wrapped
around an always-on HTTP bridge; what actually shipped is smaller and stronger
— 18 in-process tools with no bridge dependency, a contract-test safety net,
and ~50 K LOC removed from the beta tree.

---

## What this is

A Model Context Protocol server that gives any MCP-compatible client (Claude
Code, Claude Desktop, Cursor) **18 tools** for cross-session, cross-project
intelligence over a developer's portfolio. All tools run **in-process** — no
background server, no HTTP daemon, no "is the bridge up?" failure mode.

## Why this PRD exists

The v2 PRD's central assumption — that the right path was a thin HTTP proxy
exposing more endpoints — didn't survive contact. Bridge HTTP turned out to
be a serialization tax with no isolation benefit (MCP and the bridge ran in
the same trust zone, same machine, same Python). When 4 of 18 tools shipped
silently broken because their HTTP payloads drifted from the bridge's Pydantic
models, the right fix wasn't more tools, it was killing the indirection.

This PRD describes the system that resulted: smaller, faster, tested, honest.

---

## Current State (shipped)

**18 MCP tools, all in-process, all contract-tested.** Verified end-to-end
on a clean Linux install: 17/18 green; the 1 holdout (`cortex_batch_status`)
needs an Anthropic API key and now returns a clear actionable message
without one.

| Tool | What it does | Backed by |
|---|---|---|
| `cortex_service_health` | Ecosystem health probes (Vortex, Mission Control, EMOS) | `health_probe.compute_service_health` (stdlib-only) |
| `cortex_intelligence` | Natural-language query over portfolio | `CortexBridge.query_intelligence` (lazy) |
| `cortex_recommendations` | Strategic next-actions | `CortexBridge.get_recommendations` (lazy) |
| `cortex_anomalies` | Cross-project anomalies | `OrchestrationAnomalyManager` (lazy import) |
| `cortex_projects` | Project status overview | `mcp_handlers.compute_projects` (stdlib) |
| `cortex_sessions` | Active/recent Claude Code sessions | `mcp_handlers.scan_sessions` (stdlib) |
| `cortex_taskboard` | Task board read | `mcp_handlers.query_taskboard` (stdlib) |
| `cortex_orchestrate` | Discover & dispatch work via Conductor | Direct supervisor import |
| `cortex_prompt_refine` | Prompt refinement using learned patterns | `intelligence.prompt_db` (auto-seeds) |
| `cortex_conductor_compose` | Compose prompt with intent + context | `mcp_handlers.compose_conductor_prompt` |
| `cortex_graph_query` | Context-graph search (type + text) | `CortexBridge.query_graph` (lazy) |
| `cortex_plan_create` | Create execution plan from GOALS.md | `mcp_handlers.create_plan` |
| `cortex_plan_progress` | Active-plan progress | `mcp_handlers.plans_progress` |
| `cortex_batch_status` | Batch job status | `batch.batch_api_client` |
| `cortex_outcomes` | Outcome tracking (real `~/.cortex/outcomes.jsonl`) | `mcp_handlers.read_outcomes` |
| `cortex_record_decision` | Record a free-form decision | `mcp_handlers.record_freeform_decision` |
| `cortex_research_digest` | CRA weekly digest | Direct engine import |
| `cortex_doctor` | System health check | Local (Python/deps/API key/optional bridge) |

**Resources:** `cortex://goals`, `cortex://metrics/tests`, `cortex://metrics/emos`, `cortex://prompts/patterns`.

---

## Architecture

```
┌────────────────────┐
│   MCP client       │  Claude Code, Claude Desktop, Cursor, …
│  (stdio JSON-RPC)  │
└──────────┬─────────┘
           │
┌──────────▼─────────┐
│   mcp_server.py    │  18 tools, all in-process
│                    │  Lazy singleton _get_bridge() (thread-safe)
│                    │  No urllib, no BRIDGE_URL, no HTTP from MCP
└──────────┬─────────┘
           │  direct Python calls
   ┌───────┼───────┬───────────────┐
   ▼       ▼       ▼               ▼
┌──────┐ ┌──────┐ ┌────────────┐ ┌──────────────────┐
│mcp_  │ │health│ │CortexBridge│ │ intelligence/    │
│handl │ │probe │ │+ mixins    │ │ engines/         │
│ers.py│ │ .py  │ │            │ │ supervisor/      │
└──────┘ └──────┘ └────────────┘ └──────────────────┘

(optional, for local agents only)
┌──────────────────────────────────┐
│ api/bridge_endpoint.py — shim    │  53 endpoints; ~2.6K LOC.
│ uvicorn at :8765                 │  Used by Hermes + monitoring probes.
│                                  │  MCP and CLI never require it.
└──────────────────────────────────┘
```

**Three principles enforced by tests:**

1. **`mcp_server.py` is HTTP-free.** AST scan in `tests/contract/test_mcp_direct.py`
   asserts no `urllib`, no `BRIDGE_URL`, no `_bridge_get/_bridge_post`. Any
   regression fails CI.
2. **MCP startup is fast.** `test_mcp_module_import_under_2s` asserts the
   import-to-ready time. The lazy singleton means the ~16 s bridge construction
   (transformer + ML imports) only pays once on the first tool call that needs
   it, not at handshake.
3. **Bridge endpoint inventory is bounded.** `test_bridge_endpoint_inventory_unchanged`
   pins the surviving 53 routes; `test_no_phase5_deleted_endpoints_resurrect`
   lists the 12 removed paths by name and fails if any reappears.

---

## What's NOT in the beta (and why)

| Removed | Why |
|---|---|
| `cortex_extras/` (~25 K LOC: synthetic, cortexdbx, mvp, plugins, tui, lean) | Staged for sibling-repo extraction. Git history is the staging area now. |
| `archive/` (~5 K LOC: vite dashboard + telegram/web_chat gateway) | Frozen UI surfaces — bridge is scoped to local agents (Hermes). |
| 12 bridge endpoints (intelligence/query, projects, sessions, taskboard write, graph/query, batches/*, v2/outcomes*, conductor/compose, plans/*, decisions/record-freeform) | Migrated to in-process direct calls; MCP no longer needs HTTP for them. |
| The HTTP-bridge code paths in `mcp_server.py` (BRIDGE_URL, _bridge_get/post, urllib) | Phase 5 collapse. AST test enforces they don't return. |
| 4 batch modules (deprecated/, intelligent_orchestrator_anthropic, strategic_orchestrator, weather_batcher) | Verified zero importers; first-pass batch gut. |

---

## Install + run

```bash
# Fresh install — Linux or macOS
git clone https://github.com/jessekemp1/cortex && cd cortex
python -m venv .venv && source .venv/bin/activate
pip install -e .                       # core install — pulls mcp + scikit-learn
export ANTHROPIC_API_KEY=sk-ant-...
cortex doctor                          # all pass except missing key (correct)
```

```json
// Claude Code: ~/.claude/mcp_settings.json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["-m", "cortex.mcp_server"],
      "env": {
        "CORTEX_ROOT_DIR": "/path/to/your/projects",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

No bridge process to start. No services to register. The 18 tools are immediately available.

---

## Success criteria (status)

| Criterion | Status |
|---|---|
| All 18 advertised MCP tools return successful end-to-end responses on a clean install | ✅ 17/18 green; 1 needs API key with clear message |
| MCP server runs without the HTTP bridge process | ✅ `smoke_mcp.py --no-bridge` is the default verification |
| Fresh `pip install -e .` works on Linux out of the box | ✅ verified |
| Install script is portable (no macOS-only `sed -i ''`) | ✅ `sed_inplace` helper |
| Contract suite gates regressions in payload/response shape | ✅ 37 contract tests |
| MCP import is fast (<2 s — lazy singleton defers bridge cost) | ✅ asserted by `test_mcp_module_import_under_2s` |
| AST guard prevents HTTP-bridge plumbing returning to `mcp_server.py` | ✅ `test_mcp_server_has_no_http_plumbing` |
| Single canonical install + onboarding doc (no contradicting copies) | ✅ root `INSTALL.md` is canonical; `docs/INSTALLATION.md` is a pointer |

---

## Non-goals

- **No HTTP-only mode for MCP.** MCP runs in-process; the HTTP bridge is for
  out-of-process non-Python consumers (Hermes) only.
- **No deferred-tool-loading.** The v2 PRD's `defer_loading: true` /
  `_DEFERRED_TOOL_GROUPS` machinery was removed (an existing test enforces this).
  All 18 tools always load — they're cheap; the tool-search micro-optimization
  wasn't worth the conceptual complexity.
- **No web UI in the beta.** The vite dashboard moved to archive then out of
  the tree. If a web UI returns, it consumes MCP, not the bridge directly.
- **No telegram / web-chat in the beta.** Same fate; the gateway was the
  bridge's main HTTP consumer and is gone.
- **No streaming.** Tools return complete JSON. Reconsider when context
  windows demand it.
- **No multi-tenant / auth.** Localhost stdio, same trust model as the
  invoking MCP client.

---

## What's planned but not shipped

Tracked in `ROADMAP.md`:

- **Phase 6 — Batch redesign (local-first tiered routing).** `batch/` is
  ~14.7 K LOC after the first gut; target ~3-4 K. A 4-tier router
  (local-compute / local-LLM / Claude Batch / Claude real-time) replacing the
  always-full cloud queue. Steps 1-5 with caller migration gated by the
  contract suite.
- **Hermes verification.** Phase 5 Step 6 removed 12 bridge endpoints based on
  a Python-repo grep. If Hermes calls any of them, restoration is one git
  revert per block. Still owed.
- **Surgical bridge-mixin cleanup.** 86 `CortexBridge` methods; only ~5
  called in-repo. After Hermes is known, dead-method detection is tractable
  and likely cuts 500-1,500 LOC.

---

## Risk

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Hermes uses a Phase-5-deleted endpoint | Unknown — Hermes source not audited | Hermes breaks | Git revert per block; `test_no_phase5_deleted_endpoints_resurrect` lists them by name |
| First MCP tool call in a session is slow (lazy bridge cost) | Certain (~2-16 s) | One-time UX hit, then warm | Documented; contract test pins import-time fast, not first-call |
| sklearn 1.3+ ABI break vs. installed numpy | Low | embeddings_client fails | Pinned floor; numpy is also a core dep |
| Contract-test machinery itself stales | Low | Drift goes undetected | Tests assert source files via AST + payload shapes; broken assertions surface fast |

---

## Beta-readiness verdict

**Ship-ready on macOS and Linux.** The core product — MCP server + 18 tools +
CLI + in-process bridge — installs cleanly, runs fully without a daemon, and
is gated by a real test suite.

**One caveat for Linux beta users:** the launchd-based background automation
(heartbeat, nightly batch jobs) is macOS-only. The MCP product works equally
on both, but Linux users get no autonomous background loop until those are
ported to systemd timers. The Phase 6 batch redesign is the right time to
build those timers — one daily timer for the batch cycle replaces 7
launchd plists.

---

## Relationship to v2 PRD

The v2 PRD assumed: more tools + tool-search deferred loading + 85% token
savings + HTTP bridge as foundation. What actually delivered better value:
**fewer, honest tools** + **the HTTP indirection deleted** + **a test
ratchet** + **install-process correctness on Linux**. The v2 PRD is preserved
in git history as a planning record; this PRD describes what beta users
actually receive.
