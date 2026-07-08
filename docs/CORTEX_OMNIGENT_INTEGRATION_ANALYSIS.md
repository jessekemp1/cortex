# Cortex × Omnigent — Assessment & Integration Analysis

**Author:** polly (multi-agent orchestrator)
**Date:** 2026-06-26
**Method:** Read-only investigation via parallel coding sub-agents (`claude_code`), four lenses:
Cortex outcomes/docs, Cortex code/architecture, Omnigent architecture, Omnigent injection-points.
All `file:line` citations are from the sub-agents' verified inspection of the local checkouts.

**Repos assessed**
- **Cortex** — `/Users/jesse.kemp/dbx-dev/cortex` (origin `jessekemp1/cortex`), branch `chore/ship-cleanup-deauthoring`, pkg `cortex-intelligence` v1.0.1, ~197K LOC Python / 621 files.
- **Omnigent** — `/Users/jesse.kemp/dbx-dev/omnigent`, branch `fix/mcp-tools-whitelist-propagation`, pkg `omnigent` v0.1.0, ~226K LOC source / 645 test files.

**The thesis in one line:** Cortex is a *persistent-intelligence/memory layer* ("solves session amnesia"); Omnigent is a *meta-harness orchestration runtime* (normalizes Claude Code, Codex, Pi, OpenAI Agents SDK, Databricks Supervisor behind one executor + policy engine). They are complementary, not overlapping — Cortex is the natural **memory/intelligence layer for Omnigent agents**, and the most likely integration is **Cortex's MCP server attached to an Omnigent agent** — the exact attachment mechanism is **[unverified]** (no example agent config wires an MCP server via `config.yaml` today) and is Phase 0's first job to pin down.

> ⚠️ **Confidence note.** This run hit a hard environmental wall: `codex` and `pi` were unavailable (Codex native terminal would not boot; Pi not installed), so all four lenses ran on `claude_code` only — **no cross-vendor verification of the investigation**. Three lenses completed fully; the fourth (Omnigent injection-points) was cancelled mid-run after the harness approval gate stalled it, but had already traced the load-bearing MCP/tool-registration seams. Treat code citations as single-vendor-verified. Items I could not fully confirm are marked **[unverified]**.

---

## Part 1 — Cortex Assessment (code · outcome · doc)

### 1A. Code & Architecture

**Shape.** ~196.8K LOC Python across 621 files. Flat layout (`bridge.py`, `intelligence/`, etc. at repo root) with a **namespace shim** in `cortex/__init__.py:1` that appends the repo root to `cortex.__path__` so both `import intelligence.foo` and `from cortex.intelligence.foo` resolve across ~586 import sites. Clever, but a structural smell.

**LOC by area (Python, excl. venv):**

| Area | LOC | Role |
|---|---|---|
| `intelligence/` | 36,058 | The engine: memory, retrieval, model selection, monitoring, recommendations, planning |
| `tests/` | 30,109 | Test suite |
| `batch/` | 18,028 | Anthropic Message-Batches orchestration, overnight work |
| `synthetic/` | 15,242 | Synthetic FinServ data + "pupil" calibration (self-contained) |
| `supervisor/` | 8,061 | `cortex_orchestrate`: intake → route → dispatch |
| `engines/` | 7,736 | Session absorption, **context graph** (`synthesis.py`), research agent, signal bus |
| `agents/` | 6,261 | data_agent analyzers (dependency/git/project) |
| `cli/` | 5,774 | `cortex`/`cx` CLI |
| `conductor/` | 5,253 | Multi-provider prompt composition + cost tracking |
| `orchestration/` | 4,435 | Anomaly + anti-pattern detectors |
| `api/` | 3,729 | **Bridge FastAPI server** (`bridge_endpoint.py` + routes) |
| `runtime/` | 3,437 | **Second FastAPI server** (agent exec/scheduling, :8000) |
| `cortexdbx/` | 1,940 | Separate Databricks-flavored layer (not imported by core) |

**Load-bearing modules:** `config.py` / `state_paths.py` (paths + feature flags), `bridge.py` (the `CortexBridge` aggregator = `IntelligenceMixin` + `SystemMixin`, `bridge.py:204`), `api/bridge_endpoint.py` (the long-running service), `mcp_server.py` (the integration surface), `intelligence/unified_intelligence.py` (query aggregator), `engines/synthesis.py` (context graph).

**Two intelligence paths, both behind the bridge:**
1. **Pattern retrieval (no LLM)** — `POST /intelligence/query` → `UnifiedIntelligence.query()` (`unified_intelligence.py:57`). Lazily-initialized sub-systems queried in parallel via `ThreadPoolExecutor`, 5-min cache keyed `request:project:query_type`. Returns an `IntelligenceResult` with patterns / lessons / warnings / recommendations / similar_work + ranking & confidence scoring. Query types: `spec | architecture | implementation | research`.
2. **LLM reasoning** — `POST /intelligence/reason` (`api/routes/intelligence.py:157`). Gathers a context bundle (portfolio status, service health, git log/diff, top-3 pattern predictions, `GOALS.md` "Immediate Actions") then calls **`claude-haiku-4-5-20251001`** (`:330`), with a raw-context fallback on failure.

**Memory & retrieval (the crown jewels):**
- **Three-tier memory** (`intelligence/memory/tiered_memory.py`): short-term (in-memory, LRU, ~50 items) → working (7-day, **SQLite**) → long-term (`PatternMemory`, indexed). `MemoryItem` carries `outcome` (success/partial/failed) + `quality_score`; items promote across tiers by access + outcome quality.
- **Hybrid retrieval** (`hybrid_retriever.py`): **BM25 + embedding + Reciprocal Rank Fusion**. Outcome-weighted boosts from `~/.cortex/outcomes.jsonl` (`_load_outcome_boosts :161`) — project success >70% → up to +0.15, <30% → −0.10, <5 samples → none. **Note: boost is project-level, not pattern-level — coarse.**
- **Context graph** (`engines/synthesis.py`): `ContextGraph` (`:115`) persisted as JSON at `~/.cortex/graph/{nodes,edges}.json`. Node types: `goal, project, file, pattern, lesson, error, dependency, work_item`. Edge types: `relates_to, implements, blocks, causes, contains, used_in, occurs_in, depends_on`.
- **Anti-pattern detector** (`orchestration/anti_pattern_detector.py`): scans for `validated_undeployed`, `fixed_not_integrated`, `recommendation_not_acted`, `orphaned_validation` — i.e. "validated-but-not-shipped" failure modes.

**Bridge service.** `api/bridge_endpoint.py:99` FastAPI app on `127.0.0.1:8765`; every heavy dependency imported under `try/except ImportError` so failures degrade gracefully rather than cascade. Rich endpoint surface (`/intelligence/*`, `/graph/query`, `/v2/outcomes`, `/decisions/record`, `/conductor/*`, `/guardian/*`, taskboard, sessions, etc.). A **second** FastAPI server lives in `runtime/` (:8000) for agent execution/scheduling.

**MCP surface** (`mcp_server.py`): the documented integration point — ~18 contract-tested tools (intelligence query, graph query, record decision, recommendations, orchestrate, etc.).

**Code-quality read:** thoughtful architecture, real separation of concerns, graceful degradation, contract tests on the MCP surface. Main structural risks: a cluster of multi-thousand-line god-modules (`bridge_intelligence.py` 1,683; `bridge_system.py` 1,645; `briefing/formatters.py` 1,681; `deep_assessment.py` 1,645; `api/bridge_endpoint.py` 1,604) and the namespace-shim layout.

### 1B. Outcome — what actually works

- **Genuinely operational:** three-tier memory + hybrid retrieval, anti-pattern store, outcome-weighted learning loop, ~18 MCP tools, a falsifiable `cortex demo` artifact.
- **Live usage signal:** the outcome ledger `~/.cortex/outcomes.jsonl` (~1,611 rows) is **still being written today** — real single-developer dogfooding, not a dead demo.
- **Honest scope (README.md:297):** "Cortex is optimized for one use case: a developer or small team using LLM agents." It does **not** claim to make the model smarter — it claims to deliver the right context at the right time. That honesty is a strength.

### 1C. Doc & Positioning

- **One-liner (README.md:1-3):** "🧠 Cortex — Persistent Intelligence for LLM Agents… Cortex solves session amnesia."
- **Framing (README.md:23,38):** "This is not an intelligence problem. It is an infrastructure problem." / "Cortex does not make the LLM smarter. It gives the LLM the right context at the right time."
- **Ambition (DESIGN_PRINCIPLES.md:11-15):** take a developer "from managing 3-5 projects to strategically coordinating 30+ projects."
- **Claimed moat (README.md:289-297, ROADMAP.md:35-38):** developer-workflow primitives memory-only competitors (Mem0, claude-mem, Supermemory) lack — anti-pattern DB, goal→task parsing, outcome-based model routing, orchestration.
- Two of the most useful audit docs (`docs/P0_DEAUTHORING_PLAN.md`, `docs/SHIP_CLEANUP_PLAN.md`) are **untracked** — fresh Opus-advisor audits not yet committed.

**Positioning verdict:** sharp, honest, and — critically — it maps almost 1:1 onto "be the memory layer for an agent runtime." That is exactly the Omnigent fit.

---

## Part 2 — Omnigent Assessment (deep)

**One-line thesis:** Omnigent is a *meta-harness* — a single agent/session model + YAML spec that normalizes Claude Code, Codex, Pi, the OpenAI Agents SDK, and a Databricks Supervisor behind one async-event executor contract, governed by a CEL/Python policy engine and OS-level sandboxes. Large (~226K LOC, 645 test files), unusually well-commented, security-conscious; main structural risk is a few multi-thousand-line god-modules.

**Top-level layout:** `omnigent/` (package), `sdks/` (`python-client` headless HTTP/SSE client + `ui` Rich/prompt_toolkit components), `ap-web/` (Vite + React 18 + Tailwind v4 + shadcn + TipTap, Electron wrapper, talks to FastAPI OpenAI-compatible API), `deploy/`, `examples/` (`debby/`, `polly/` agent images), `tests/`.

**Core runtime contract:** `Executor.run_turn` (`executor.py:502`) — the single async-event turn contract every harness implements. Harnesses are registered in a registry (`harnesses/__init__.py:34`).

**Harness model (the key to integration):** `harness_aliases.py` distinguishes:
- **SDK harnesses** — `claude-sdk` (alias `claude`), `openai-agents` — driven through the Omnigent transcript; tools/MCP injected by Omnigent directly.
- **Native CLI harnesses** — `claude-native`/`codex-native` — boot from their **own** on-disk runtime transcript (Claude Code's project JSONL / Codex's rollout) and **own their own permission gate**. (This is precisely why this run's approval prompts could not be cleared from the orchestrator policy side — the native harness's tmux/permission gate sits outside Omnigent's policy engine.)

**Tool registration seams** (`omnigent/tools/manager.py`):
- `_register_skill_tools` (`:265`) — always registers `load_skill`; discovers host-scope skills (`~/.claude/skills/`).
- `_register_builtin_tools` (`:287`) — `web_search`, `web_fetch`, `upload_file`, etc.
- `_register_local_tools` (`:573`) — `@tool`-decorated functions from `tools/python/*.py`; supports server, **client-runtime**, and **UC-function** tools; name collisions fail loud (per "G27").
- MCP tools dispatch via **`ProxyMcpManager`** / **`RunnerMcpManager`** (`runner/app.py`) — the live stdio-subprocess MCP pool that bridges declared `mcp_servers` to each harness type.

**Config-driven extensibility (the likely seam):** an agent is a directory with `config.yaml` declaring `local_tools`, `skills`, `sub_agents`, and `guardrails.policies`. Omnigent defines a real `MCPServerConfig` type (`omnigent/tools/mcp.py`) plus a live stdio MCP pool (`ProxyMcpManager`/`RunnerMcpManager`), so attaching an external MCP server is clearly *supported*. **[unverified]** However, **no example agent config (including polly's own) declares `mcp_servers` in `config.yaml`** — attached MCP servers (Cortex included) appear to be wired through a runtime/deployment path, not the config file. So "addable by config alone" is plausible but **unproven**; confirming the real attachment point is Phase 0's first deliverable.

**Policy engine:** three actions only — `ALLOW` / `ASK` / `DENY` (`spec/types.py:1098-1100`) — evaluated via **CEL** expressions (`cel.py:92`) + Python policies (e.g. `blast_radius`, which classifies each native Bash command as risky → ASK, per-command). OS-level sandboxing via macOS **Seatbelt** (`sandbox-exec -f <profile>`) and Linux bubblewrap.

**Persistence & feedback:** `Conversation` rows (SQLAlchemy + Alembic) carry the **spawn tree** (`parent` / `root_conversation_id`); sub-agents dispatch via `tool_dispatch.py:879`. **Session outcomes are classified at turn-end** — a natural, already-existing hook for an external learning loop to consume.

**Code-quality read:** strong. Verified citations, heavy commenting, security-first design (CEL + sandbox), broad test coverage. Same structural risk as Cortex: a few god-modules (notably `runner/app.py` is enormous).

---

## Part 3 — Integration Design

### Why they fit (no real overlap)

| Concern | Cortex | Omnigent |
|---|---|---|
| Cross-session memory / "what did we learn" | ✅ core competency | ❌ stores transcripts, not distilled intelligence |
| Hybrid retrieval (BM25+embedding+RRF) | ✅ | ❌ |
| Outcome-weighted learning loop | ✅ | ⚠️ classifies outcomes at turn-end, but doesn't *learn* from them |
| Multi-harness orchestration | ⚠️ has a `supervisor/`, single-provider-ish | ✅ core competency |
| Policy / sandbox / governance | ❌ | ✅ |
| Spawn tree / sub-agent fan-out | ⚠️ basic | ✅ |
| MCP server surface | ✅ ~18 tools, exposes intelligence | ✅ consumes MCP servers by config |

The overlap (each has a "supervisor"/"orchestrate") is shallow; the **complement is deep**. Omnigent has no distilled memory; Cortex *is* distilled memory and already speaks MCP. Omnigent already classifies outcomes at turn-end but does nothing durable with them; Cortex has the outcome ledger + learning loop that wants exactly that signal.

### Path A — Cortex AS Omnigent's memory layer ✅ **(Recommended)**

**The mechanism is configuration/runtime wiring, not a Cortex code change — but the exact wiring point is [unverified].** The `config.yaml` snippet below is the *hypothesized* form; since no example agent currently declares `mcp_servers` this way, Phase 0 must first confirm where an stdio MCP server actually attaches (config file vs. runtime/deployment injection):

```yaml
# examples/<agent>/config.yaml
mcp_servers:
  - name: cortex
    command: ["python", "-m", "cortex.mcp_server"]   # or the cortex CLI MCP entrypoint
    # env: { CORTEX_STATE_DIR: ... }   # see Gap G2
```

Omnigent's `ProxyMcpManager`/`RunnerMcpManager` then surfaces Cortex's ~18 tools (intelligence query, graph query, record decision, recommendations, orchestrate) to the agent, namespaced (`mcp__cortex__*`). The agent — e.g. an orchestrator like polly — gains:
- **Pre-task context injection:** call `cortex_intelligence` / `cortex_graph_query` before planning to retrieve patterns, lessons, warnings, prior similar work.
- **Decision capture:** call `cortex_record_decision` at decision points → feeds the learning loop.
- **Anti-pattern guardrails:** surface "validated-but-not-shipped" warnings into the plan gate.

**Phased plan (each phase = its own implementer PR + cross-vendor review):**
1. **Phase 0 (config-only prototype):** add the Cortex MCP server to one Omnigent example agent; verify the ~18 tools enumerate and a `cortex_intelligence` round-trips. *No Cortex code change.* **This is the falsifiable first step.**
2. **Phase 1 (read path):** wire a pre-turn context-injection step (skill or local tool) that queries Cortex and prepends distilled context. Measure: does it improve plan quality / reduce rediscovery?
3. **Phase 2 (write/feedback path):** bridge Omnigent's **turn-end outcome classification** → Cortex `outcomes.jsonl` so the learning loop is fed by real Omnigent runs (closes the compounding loop). Requires the Cortex multi-user/state-dir gaps (G1/G2) fixed first.
4. **Phase 3 (graph + spawn tree):** mirror Omnigent's `Conversation` spawn tree into Cortex's context graph (`work_item`/`project` nodes) for cross-session, cross-agent recall.

### Path B — Omnigent orchestrates Cortex ⚖️ (evaluated; selective value)

Using Omnigent's fan-out to *operate* Cortex workflows (e.g. run `cortex_orchestrate`, batch jobs, overnight flywheel as Omnigent sub-agent tasks).

**Verdict:** lower marginal value than A, but **two genuinely useful slices**:
- **B1 — orchestrate Cortex's batch/overnight work** via Omnigent sub-agents (Cortex's `batch/` + `supervisor/` become dispatch targets). Useful because Omnigent's spawn-tree + policy/sandbox is more robust than Cortex's own supervisor.
- **B2 — let Cortex's `cortex_orchestrate` route *to* Omnigent** (Cortex picks the model/worker, Omnigent executes under governance). This is the inverse and arguably the most powerful combination long-term, but it's the highest-coupling option — defer until A Phases 0-2 prove the seam.

**Recommendation:** commit to **Path A, Phases 0→2**. Treat B1 as an opportunistic add-on once A's MCP seam is proven; treat B2 as a future "north star," not now.

---

## Part 4 — Cortex Gap List (you asked me to define these)

Ranked by how much they block the Omnigent integration.

| # | Gap | Evidence | Impact on integration | Fix sketch |
|---|---|---|---|---|
| **G1** | **Workspace coupling** — bridge assumes the author's `~/Dev` workspace / fixed project list / default project `"cortex"`. A second user "starts fine then silently gets empty or the author's results." | outcomes/docs lens; `api/routes/intelligence.py` deauthoring partly done but coupling persists elsewhere | **Blocks Phase 2** (Omnigent agents run in arbitrary workdirs). High. | Finish the deauthoring (`docs/P0_DEAUTHORING_PLAN.md`); derive workspace/projects from the calling agent's context, not a static map. |
| **G2** | **State-dir override only partial** — `state_paths.get_cortex_dir()` honors `CORTEX_STATE_DIR`→`CORTEX_HOME`→`~/.cortex`, but many modules hard-code `Path.home()/".cortex"` directly (`hybrid_retriever.py:27`, `synthesis.py:124`, `supervisor/router.py:25`). | code lens | Blocks multi-tenant / per-agent isolation. High. | Replace direct `Path.home()/".cortex"` with the helper everywhere; add a lint/test guard. |
| **G3** | **Embeddings are not neural** — `embeddings_client.py:1-27` uses sklearn `HashingVectorizer` (768-dim hashed n-grams) unless `VOYAGE_API_KEY` is set (`:47-56`). "Semantic" recall is really lexical n-gram overlap. | code lens (corroborated by a failing MRR benchmark) | Caps retrieval quality — the very thing Cortex sells. Medium-High. | Make Voyage (or a local embedding model) the default path; document the degraded mode loudly. |
| **G4** | **MCP contract/impl mismatch** — `cortex_graph_query` advertises node types `decision`/`warning` (`mcp_server.py:314`) that **don't exist** in the actual `NodeType` enum (which has `file/error/dependency/work_item` instead). | code lens | An Omnigent agent calling the documented contract gets wrong/empty results. Medium (and embarrassing). | Reconcile the tool docstring with the enum; add a contract test asserting advertised == actual node types. |
| **G5** | **Hardcoded interpreter & model** — `/intelligence/reason` shells to `/opt/homebrew/bin/python3` (`api/routes/intelligence.py:188`) and pins `claude-haiku-4-5-20251001` (`:330`). | code lens | Breaks on any non-Homebrew host (incl. CI / Databricks). Medium. | Use `sys.executable`; make the model configurable. |
| **G6** | **Coarse learning loop** — outcome boosts are **project-level**, not pattern-level (`hybrid_retriever.py:161`). | code lens | Limits how much Omnigent's fine-grained turn outcomes can sharpen retrieval. Medium. | Add pattern-level outcome attribution. |
| **G7** | **Doc/metric drift** — inconsistent test counts across docs (1855 / 2361 / 1291); a stale prompt-tokens telemetry stream (0 processor activations, last write ~2026-05-06); README "production metrics" the project's own paper walks back. | both lenses | Erodes trust in claims; not a hard blocker. Low-Medium. | Single source of truth for test count (CI-generated); prune or revive the telemetry stream; soften unbacked metrics. |
| **G8** | **God-modules + namespace shim** — five files >1.6K LOC; `cortex/__init__.py` path shim. | code lens | Maintainability risk; not integration-blocking. Low. | Incremental decomposition; treat as tech-debt backlog. |

**The two that gate the Omnigent feedback loop (Phase 2): G1 and G2.** Everything else is parallelizable.

---

## Part 5 — Risks, and Recommended Next Actions

**Risks**
- **No cross-vendor verification this run** (Codex/Pi unavailable). Before any code lands, restore a second vendor so cross-review is real. *(Hard rule: review is always a different vendor than the implementer.)*
- **Native-harness permission gate** is outside Omnigent's policy engine — automation that drives `claude-native`/`codex-native` will keep hitting per-tool approval unless the harness's own settings (`.claude/settings.local.json` allow-rules) are pre-configured. (This run is the cautionary tale.)
- **Multi-tenant assumptions (G1/G2)** mean Phase 2 must wait on Cortex fixes; don't wire the write path against a single-user-coupled bridge.

**Recommended next actions (this project)**
1. **[cortex×omnigent] Ship the Phase 0 prototype** — add Cortex's MCP server to one Omnigent example agent's `config.yaml`, confirm tool enumeration + one live `cortex_intelligence` round-trip. Falsifiable, config-only, no Cortex code change. *(Implementer PR + cross-vendor review once a 2nd vendor is restored.)*
2. **[cortex] Fix G1 + G2 (deauthoring + state-dir)** — the two gaps that gate the feedback loop; small, well-scoped, test-guardable.
3. **[cortex] Fix G4 (MCP contract mismatch)** — one-file reconciliation + a contract test; cheap trust win before Omnigent agents call the surface.
4. **[infra] Restore a second coding vendor** (Codex native terminal or install Pi) so cross-vendor review is possible before code lands.

---

*Generated from four read-only sub-agent investigations. Code citations single-vendor (`claude_code`) verified. Phase plan assumes each implementation lands as its own PR with opposite-vendor review; nothing here has been merged.*
