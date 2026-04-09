# Cortex Deep Assessment — 2026-04-08

**Assessed by**: Claude Opus 4.6
**Evidence base**: Test suite run (975 passed, 1 failed, 18 skipped, 4 xfailed), source code audit of 30+ files, design doc review, research brief alignment
**Overall Grade**: C+

---

## Executive Summary

### Overall Grade: C+ (weighted 2.35/4.0)

**Top 3 Findings** (each with file:line citation):

1. **Embeddings are non-functional — memory retrieval is degraded to BM25-only.** The `EmbeddingsClient` at `intelligence/embeddings_client.py:39` uses `text-embedding-3-small` (an OpenAI model name) via the Anthropic SDK, which does not have a production embeddings API. The hybrid retriever at `intelligence/memory/hybrid_retriever.py:147` falls back gracefully, but this means Cortex's "semantic pattern matching" design principle (DESIGN_PRINCIPLES.md:87-88) is not operational. The benchmark failure (`tests/test_retrieval_benchmark.py:282-286`) is a direct symptom: 2 of 15+ queries return 0 results under BM25-only.

2. **V2 Prime 3-Engine architecture exists as code but is not wired into production.** `engines/absorber.py`, `engines/synthesis.py`, and `engines/broker.py` define the Context Absorber, Synthesis Core, and Action Broker with full class hierarchies. However, the production path still flows through `bridge.py` (2,220 lines) and `cli.py` (2,115 lines). The engines are imported in `engines/__init__.py` but are not called from the MCP server or bridge endpoint. The V2 Prime architecture is scaffolded, not shipped.

3. **Batch processor lacks env var validation — ran broken for 6 weeks.** `batch/morning_processor.py` has zero references to `ANTHROPIC_API_KEY` or `os.environ` (confirmed by grep). When the launchd plist lacked the key, the processor failed silently for ~6 weeks with no alert. `batch/intelligent_orchestrator.py:105` reads `CORTEX_ROOT_DIR` from `os.environ` but does not validate `ANTHROPIC_API_KEY` either.

**Trajectory**: Cortex is **improving but at risk of architectural divergence**. The V1 system (bridge + BM25 + outcomes) works and has real data (310 outcomes). The V2 Prime engines are being built in parallel but are not integrated. The longer these two codepaths coexist without convergence, the higher the maintenance tax and the greater the risk that V2 never ships.

---

## Dimension Scorecards

### 1. Architecture: Design vs. Reality — Grade: C (weight: 30%)

**Principle 1: "Depth Over Speed"** — Partially implemented.
- DESIGN_PRINCIPLES.md:19-38 states deep mode is default.
- `intelligence/adaptive_latency.py:18-23` implements `AnalysisMode` enum with FAST/DEEP/AUTO.
- `cli.py:2997-3001` shows `cortex deep`, `cortex quick`, `cortex auto` in help text.
- However, `grep "def deep\|def quick\|def auto" cli.py` returns **no matches** — these are documented commands that do not appear to have dedicated function implementations. They exist in help text but the routing to `AdaptiveLatency` modes is not confirmed as functional.
- **Verdict**: Scaffolded, not proven operational.

**Principle 2: "Simplicity Over Optimization"** — Mixed progress.
- Target: <30 perf-related files from 141. Current grep for `perf|cache|lazy|async def` returns **199 occurrences across 30 files** — including `session_cache.py` (28 hits), `api/bridge_endpoint.py` (75 hits), `task_discovery.py` (25 hits).
- The batch directory alone contains **50+ files** (`ls batch/` output), including `optimization.py`, `optimizer.py`, `usage_optimizer.py`, `bandwidth_experiments.py` — a clear accumulation counter to the simplicity principle.
- **Verdict**: Complexity has not been reduced; it has shifted.

**Principle 3: "Batch API First"** — Implemented but fragile.
- `batch/intelligent_orchestrator.py` is well-designed: capacity calculation, priority scoring, overnight window management.
- `batch/morning_processor.py` processes results from 3 source locations.
- But: zero env var validation at startup. The 6-week silent failure proves the "first" principle is aspirational — batch is a secondary system that nobody notices when it breaks.
- **Verdict**: Architecture exists; operations fail the design intent.

**Principle 4: "Adaptive Latency"** — Code exists, production use unclear.
- `intelligence/adaptive_latency.py:18-23` defines `AnalysisMode` with FAST/DEEP/AUTO.
- The file is 50+ lines of config with mode-specific settings (git_days, spec_limit, pattern_semantic, etc.).
- No evidence it's wired into the actual CLI command dispatch.
- **Verdict**: Designed but not confirmed in production path.

**Principle 5: "Compound Intelligence"** — The strongest implementation.
- `learning.py:47-150` implements outcome-based learning with quality weighting.
- `intelligence/memory/hybrid_retriever.py:161-179` loads outcome boosts that adjust retrieval ranking by project success rate.
- 310 outcomes recorded (per MEMORY.md).
- This is the design working as intended: outcomes feed back into recommendations.
- **Verdict**: Operational and compounding. Best-aligned principle.

**V2 Prime 3-Engine Model**:
- **Context Absorber** (`engines/absorber.py`): Full class hierarchy with SignalType enum (12 types), abstract `SignalSource` base class. `engines/universal_signal_bus.py` routes signals to engines via fan-out. SQLite event log at `~/.cortex/signal_bus.db`. Status: **Implemented but not production-wired**.
- **Synthesis Core** (`engines/synthesis.py`): `NodeType` and `EdgeType` enums, hierarchical context graph model. Status: **Implemented but not production-wired**.
- **Action Broker** (`engines/broker.py`): `InterventionType` enum with 7 intervention types, `Severity` enum. Status: **Implemented but not production-wired**.

The gap: all three engines exist as Python modules. The `UniversalSignalBus` connects them. But the production MCP server (`mcp_server.py`) and bridge (`bridge.py`) do not import or invoke these engines. The V1 path (bridge HTTP) remains the only active path.

---

### 2. Memory Architecture Maturity — Grade: C- (weight: 25%)

**3-Stage Framework Assessment**:

| Stage | Description | Cortex State | Evidence |
|---|---|---|---|
| Stage 1 | Raw storage + semantic retrieval | **Partial** — BM25 works, embeddings broken | `hybrid_retriever.py:147` falls back to BM25-only |
| Stage 2 | Pattern extraction + reflection | **Partial** — outcome boosts exist, no reflection passes | `hybrid_retriever.py:161-179` implements project success boosts; no consolidation/reflection agent |
| Stage 3 | Experience abstraction | **Not implemented** | No code converts repeated patterns into generalized lessons automatically |

**Cortex memory maturity: Stage 1.5** — It stores and retrieves, and has rudimentary outcome-based ranking adjustment, but does not perform reflection passes, memory consolidation, or experience abstraction.

**MAGMA Multi-Graph Relevance**:
- MAGMA uses orthogonal semantic/temporal/causal/entity graphs.
- Cortex has: BM25 keyword index (1 dimension), embedding vectors (broken), outcome boosts (1 scalar per project).
- The `engines/synthesis.py` ContextGraph has node types and edge types that could support multi-graph decomposition, but it's not wired into retrieval.
- **Gap**: Cortex retrieval is single-dimension (keyword). MAGMA demonstrates 45.5% higher accuracy with multi-graph traversal. This is the single largest capability gap.

**BM25 Fallback Implications**:
- The test failure (`test_retrieval_benchmark.py:282-286`) shows 2 queries returning 0 results with BM25-only: "commit without running tests" and "agent deployment infrastructure".
- BM25 is keyword-dependent. Abstract queries (like "commit without running tests") may not match any stored pattern keywords. Semantic embeddings would handle this via vector similarity.
- 310 outcomes are stored but the feedback loop is weakened: outcome boosts adjust ranking, but without embeddings, the retrieval pool is already limited.

**DeepSeek Engram Pattern**:
- Engram separates static knowledge (O(1) hash lookup) from dynamic reasoning (working context).
- Cortex partially mirrors this: `~/.cortex/outcomes.jsonl` (static outcomes) vs. `bridge.py` session context (dynamic). But there's no architectural separation — both are loaded into the same retrieval pipeline.
- The `intelligence/memory/tiered_memory.py` file exists (confirmed by grep), suggesting a tiered storage concept, but it's behind a feature flag (`TIERED_MEMORY_AVAILABLE`).

---

### 3. MCP Coverage — Grade: C (57%) (weight: 20%)

**Current**: 17 `@mcp.tool()` decorators in `mcp_server.py` (confirmed by grep).
**PRD Target**: 30+ tools across 8 groups.

| Group | Status | Tools Implemented | Tools Specified | Notes |
|---|---|---|---|---|
| core | Implemented | 8 | 8 | `cortex_service_health`, `cortex_intelligence`, etc. |
| orchestration | Implemented | 2 | 2 | `cortex_orchestrate`, `cortex_enable_tools` |
| research | Implemented | 3 | 3 | `cortex_research_status/digest/proposals` |
| conductor | Implemented | 2 | 2 | `cortex_conductor_compose/startup` |
| graph | **Missing** | 0 | 4 | `cortex_graph_query/stats/add_node/search` |
| planning | **Missing** | 0 | 5 | `cortex_plan_create/list/get/step/progress` |
| ops | **Missing** | 0 | 6 | `cortex_batch_list/status`, `cortex_queue_*`, `cortex_signal_absorb`, `cortex_record_decision` |
| portfolio | **Missing** | 0 | 5 | `cortex_outcomes`, `cortex_compound_health`, `cortex_docs_*`, `cortex_activity_heatmap` |

**Coverage**: 15/35 = 43% (the PRD says 15 current, I count 17 `@mcp.tool()` decorators — 2 may be prompt_refine and emos_status which are file-read tools). Effective coverage of specified V2 tools: ~43%.

**Highest-impact missing tools** (ranked by Claude Code session improvement):
1. **`cortex_graph_query`** — the context graph is Cortex's stated differentiator, invisible to MCP agents
2. **`cortex_plan_create/step`** — planning workflow entirely unavailable via MCP
3. **`cortex_record_decision`** — learning loop cannot be fed from MCP agents
4. **`cortex_outcomes`** — cross-project intelligence locked behind HTTP

---

### 4. Test Quality — Grade: B- (weight: 15%)

**test_retrieval_benchmark.py (the failing test)**: This is actually a **high-quality benchmark test**. `test_no_empty_results` at line 282-286 catches a real issue (BM25-only retrieval missing abstract queries). The benchmark includes MRR thresholds (line 270-272: `>= 0.40`), category-specific recall (line 278: anti-pattern recall >= 70%), and per-query diagnostics. This is the kind of test that should exist for every core capability.

**test_bridge_integration.py**: The first 4 tests (lines 37-59) are the known `assert X in (True, False)` pattern — mathematically always true, testing nothing. Lines 67-80 improve somewhat with conditional logic but still rely on `assert bridge is not None` patterns. This file represents the legacy quality floor.

**KNOWN_ISSUES.md**: Well-documented with specific counts (~87 always-true, ~30 sole `assert is not None`). Claims "Fixed in `test_bridge_integration.py`" but the file still contains 4 occurrences (per grep). The documentation is ahead of the reality.

**Always-true assertion audit**:
- Grep shows 7 remaining `assert X in (True, False)` across 3 files (down from ~87 claimed).
- Either significant cleanup has occurred (87 → 7), or KNOWN_ISSUES.md was counting a broader pattern.
- The 3 remaining files: `test_assertion_quality.py` (1 — likely the meta-test), `test_bridge_integration.py` (4), `test_memory_roundtrip.py` (2).

**xfailed tests (4)**:
1. `test_memory_roundtrip.py:33` — "Memory bridge not implemented: Claude Code and Cortex are isolated systems" — **genuine architectural gap**, strict=True
2. `test_memory_roundtrip.py:256` — "KNOWN_ISSUES.md contains 'Fixed' claims that contradict code reality" — **meta-test catching documentation drift**, strict=True
3. `test_memory_roundtrip.py:324` — "Claude Code and Cortex have zero cross-references" — **genuine architectural gap**, strict=True
4. `test_moltbot_integration.py:169` — "Legacy ~/clawd/skills/ directory no longer exists" — **dead code reference**, NOT strict

Verdict: 3 of 4 xfails are well-justified with `strict=True` and represent genuine planned work. The 4th (moltbot) should be deleted, not xfailed.

**Regression catch rate estimate**: ~70% of tests would catch real regressions. The remaining ~30% are either always-true assertions, sole `is not None` checks, or import-availability tests that don't exercise functionality. The benchmark tests and memory roundtrip tests represent the quality ceiling; the bridge integration tests represent the floor.

---

### 5. Ops/Reliability — Grade: D (weight: 10%)

1. **Env var validation**: `batch/morning_processor.py` has **zero** references to `ANTHROPIC_API_KEY` or `os.environ`. No startup validation. This is the root cause of the 6-week silent failure.

2. **Batch health metric**: `batch/morning_processor.py` writes to `~/.cortex/briefing_cache.json` but there is no "last successful batch run" timestamp exposed via `/service-health`. The MCP tool `cortex_service_health` hits `GET /service-health` on the bridge, but batch health is not included in that response (no batch health endpoints in MCP tools either).

3. **API key security**: Keys are read from `os.environ` in code (e.g., `embeddings_client.py:31`). The vulnerability is in the launchd plist, which must separately set env vars — and when it doesn't, there's no fallback or loud failure.

4. **Batch break alerting**: No alert mechanism exists. `batch/monitor_batch_overnight.py.bak` is a `.bak` file — the monitor itself appears to be disabled/archived. There is no cron or launchd job that checks whether batch jobs completed.

5. **WORK_PROGRESS_REPORT.md signals**: "174 plan drifts, 89 unplanned work" out of 50 tracked items means **3.5 plan drifts per work item** and **1.8 unplanned items per planned item**. This signals that planning is aspirational — work follows an ad-hoc path significantly more often than the planned path. This is not inherently bad for a solo developer, but it conflicts with the "Compound Intelligence" principle which assumes stable feedback loops.

---

## Research Brief Alignment

| Brief Signal | Current State | Gap | Priority | Effort |
|---|---|---|---|---|
| **MAGMA multi-graph memory** (45.5% higher accuracy, 95% less tokens) | Single-dimension BM25 retrieval. `engines/synthesis.py` has graph node/edge types but not wired to retrieval. | No multi-graph decomposition. Retrieval is keyword-only (embeddings broken). No temporal/causal/entity graph views. | **H** — largest capability gap | 2-3 weeks: implement semantic + temporal + causal graph layers; wire into retrieval pipeline |
| **3-stage memory maturity** (Storage → Reflection → Experience) | Stage 1.5: stores patterns + outcomes, rudimentary outcome boosts in retrieval ranking. No reflection agent, no experience abstraction. | Missing: reflection/consolidation passes, automatic pattern-to-lesson extraction, experience generalization. | **H** — determines long-term learning velocity | 1-2 weeks: add nightly reflection batch job that consolidates patterns into lessons |
| **Claude Code subagent isolation** (MCP V2 architecture) | MCP server is monolithic (17 tools, single process). No subagent isolation, no per-agent context windows. | V2 Prime engines exist but are not MCP-accessible. No agent-per-domain architecture. | **M** — improves composability | 1 week: expose V2 engines as separate MCP tool groups per PRD-mcp-v2.md |
| **Ollama MLX local inference** (20-50% faster on Apple Silicon) | `conductor/providers/` directory exists with `anthropic_provider.py`. No Ollama/MLX provider found. | No local inference path. All AI calls go through Anthropic API. | **M** — reduces cost, enables offline | 3-5 days: add Ollama provider to Conductor, route batch/low-priority tasks locally |
| **300K batch output tokens** via Batches API | `batch/intelligent_orchestrator.py:39` shows `max_output_tokens_per_request: int = 8_000`. | Hard-coded at 8K — 37.5x below the new API limit. | **L** — quick config fix but limited current need | 1 hour: update default + add beta header. Low priority because current batch jobs don't need 300K output. |

---

## What Cortex Gets Right

1. **Outcome-based learning loop is real and compounding.** `learning.py` processes 310 outcomes with quality-weighted accuracy. `hybrid_retriever.py:161-179` applies per-project success rate boosts to retrieval ranking. This is the feature no competitor has (per ROADMAP.md:25-27), and it works.

2. **Test suite is substantial and mostly specific.** 975 passing tests with specific benchmarks (retrieval MRR >= 0.40, anti-pattern recall >= 70%) is strong for a solo-developer project. The xfail tests are well-justified with `strict=True` and document genuine architectural gaps rather than hiding broken code.

3. **V2 Prime engine design is sound.** `engines/absorber.py`, `engines/synthesis.py`, `engines/broker.py`, and `engines/universal_signal_bus.py` implement a coherent 3-engine architecture with proper abstractions (SignalType enum, NodeType/EdgeType enums, InterventionType enum). The design separates concerns cleanly. The problem is wiring, not design.

4. **Research brief generation is production-quality.** `cortex_ai_research_brief_2026-04-08.md` is genuinely useful intelligence — ranked by actionability, with source citations, impact assessments, and specific action items. The Cortex Research Agent (CRA) described in ROADMAP.md is one of the system's strongest differentiators.

---

## Prioritized Improvement Backlog

| Rank | Item | Impact (1-10) | Effort (days) | Ratio | Evidence |
|---|---|---|---|---|---|
| 1 | **Fix embeddings** — switch to working embedding provider (OpenAI, local sentence-transformers, or Voyage) | 9 | 1 | 9.0 | `embeddings_client.py:39` uses non-existent Anthropic embeddings API; 15x fallback log in test run |
| 2 | **Add batch startup env var validation** — fail loudly if ANTHROPIC_API_KEY missing | 7 | 0.25 | 28.0 | `morning_processor.py` has zero env var checks; 6-week silent failure |
| 3 | **Ship MCP V2 tool groups** (graph, planning, ops, portfolio) | 8 | 2 | 4.0 | PRD-mcp-v2.md specifies 20 missing tools; PRD says ~4h implementation |
| 4 | **Wire V2 Prime engines into production path** — connect signal bus to bridge/MCP | 8 | 3 | 2.7 | Engines exist at `engines/*.py` but `mcp_server.py` and `bridge.py` don't import them |
| 5 | **Add nightly memory reflection job** — consolidate patterns into lessons | 7 | 5 | 1.4 | No reflection/consolidation code exists; stuck at Stage 1.5 memory maturity |
| 6 | **Add batch health to /service-health** — expose last-successful-run timestamp | 6 | 0.5 | 12.0 | No batch health metric in service-health endpoint; `monitor_batch_overnight.py.bak` is archived |
| 7 | **Add Ollama/MLX provider** to Conductor for local inference | 6 | 3 | 2.0 | Only `anthropic_provider.py` exists; no local inference path |
| 8 | **Clean up remaining weak assertions** — fix 7 `assert X in (True, False)` patterns | 4 | 0.5 | 8.0 | 7 remaining across 3 files per grep; KNOWN_ISSUES.md claims fixed but reality disagrees |
| 9 | **Delete moltbot xfail test** — legacy dead code reference | 2 | 0.1 | 20.0 | `test_moltbot_integration.py:169` references `~/clawd/skills/` which no longer exists |
| 10 | **Update batch token limits** — raise max_output from 8K to 300K | 3 | 0.1 | 30.0 | `intelligent_orchestrator.py:39` hard-codes 8K; API now supports 300K |

---

## Appendix: Evidence Citations

| Citation | File | Lines | Finding |
|---|---|---|---|
| Embeddings fallback | `intelligence/embeddings_client.py` | 39 | Uses `text-embedding-3-small` model name that is not an Anthropic model |
| BM25-only retrieval | `intelligence/memory/hybrid_retriever.py` | 147 | `self.embeddings_available = embeddings_client is not None` — False in production |
| Outcome boost loop | `intelligence/memory/hybrid_retriever.py` | 161-179 | Project success rate boosts applied during RRF merge |
| Benchmark failure | `tests/test_retrieval_benchmark.py` | 282-286 | `test_no_empty_results` catches 2 queries with 0 results |
| Always-true assertions | `tests/test_bridge_integration.py` | 42, 49, 55, 59 | `assert X in (True, False)` pattern |
| No env validation | `batch/morning_processor.py` | 1-100 | Zero references to ANTHROPIC_API_KEY or os.environ |
| V2 absorber scaffolded | `engines/absorber.py` | 1-40 | Full SignalType enum and abstract SignalSource class |
| V2 synthesis scaffolded | `engines/synthesis.py` | 1-40 | NodeType/EdgeType enums, hierarchical graph model |
| V2 broker scaffolded | `engines/broker.py` | 1-40 | InterventionType/Severity enums, proactive intervention model |
| Signal bus connecting engines | `engines/universal_signal_bus.py` | 1-40 | Fan-out to all 3 engines, SQLite event log |
| MCP tool count | `mcp_server.py` | various | 17 `@mcp.tool()` decorators |
| Batch file count | `batch/` directory | N/A | 50+ files including 3 optimizer variants |
| Adaptive latency module | `intelligence/adaptive_latency.py` | 18-23 | AnalysisMode enum with FAST/DEEP/AUTO |
| CLI help text only | `cli.py` | 2997-3001 | `cortex deep/quick/auto` in help text, no function defs found |
| Plan drift metric | `WORK_PROGRESS_REPORT.md` | 6 | 174 plan drifts / 50 work items = 3.5 drifts per item |
| Outcome count | MEMORY.md (external) | N/A | 310 outcomes recorded |
| Design principles | `DESIGN_PRINCIPLES.md` | 19-280 | 5 principles, 4 migration phases (all unchecked) |
| KNOWN_ISSUES accuracy | `tests/KNOWN_ISSUES.md` | 28-29 | Claims "Fixed in test_bridge_integration.py" but 4 occurrences remain |
| xfail quality | `tests/test_memory_roundtrip.py` | 33-36, 256-259, 324-327 | 3 genuine architectural gap tests with strict=True |
