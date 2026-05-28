# Cortex Gap Analysis & Fix Spec
_Assessed 2026-05-13 against cortex-dbx (E2E tested baseline)_

## Executive Summary

cortex (jessekemp1/cortex) has 18 MCP tools. Of those, **4 are broken**, **3 are missing critical cortex-dbx capabilities**, and **3 are degraded** (work but with gaps). The root cause is architectural: every tool proxies through a 115K-line FastAPI bridge at localhost:8765, adding fragility and indirection that cortex-dbx avoids with direct function calls.

| Status | Count | Tools |
|--------|-------|-------|
| Working | 5 | sessions, batch_status, taskboard, doctor/service_health, record_decision (degraded) |
| Degraded | 3 | record_decision, projects, recommendations |
| Broken | 4 | plan_create, plan_progress, conductor_compose, graph_query |
| Missing | 3 | log_outcome, recall_similar, flag_anti_pattern |

---

## Part 1: Missing Tools (cortex-dbx has, cortex doesn't)

### M1. `log_outcome` — Decision Feedback Loop

**What cortex-dbx does:** `log_outcome(decision_id, followed, outcome, metrics, notes)` writes to Postgres `outcomes` table with FK to `decisions`. Enables closed-loop learning — 90% outcome close rate in cortex-dbx.

**What cortex has:** Nothing. `cortex_outcomes` MCP tool reads `model_outcomes.jsonl` (3 entries, model routing outcomes — wrong schema entirely). `outcomes.jsonl` (1610 lines) contains recommendation execution logs, not decision outcomes.

**Fix spec:**
- Add `cortex_log_outcome` MCP tool to `mcp_server.py`
- Params: `decision_id: str, followed: bool, outcome: Literal["success","partial","failed","pending"], metrics: dict = None, notes: str = None`
- Storage: Append to `~/.cortex/decision_outcomes.jsonl` (new file, avoids collision with existing `outcomes.jsonl`)
- Schema: `{"outcome_id": "out_{timestamp}", "decision_id": "dec_xxx", "followed": bool, "outcome": str, "metrics": {}, "notes": str, "created_at": iso8601}`
- Implement directly in `mcp_server.py` (no bridge dependency — same pattern as `cortex_prompt_refine`)
- Return: `{"outcome_id": str}`

**Effort:** Small (30-50 lines). No bridge changes needed.

---

### M2. `recall_similar` — Decision Retrieval

**What cortex-dbx does:** Hybrid keyword ILIKE + Vector Search over decisions. Deduplicates, returns top-k with project filter. The core value proposition — query "guardrails for sensitive data" and get back the manulife-genie defense-in-depth pattern.

**What cortex has:** Nothing. `cortex_intelligence` does NLP queries over project metadata, not structured recall over decisions.

**Fix spec:**
- Add `cortex_recall_similar` MCP tool to `mcp_server.py`
- Params: `context: str, k: int = 5, project: str = None`
- Implement directly in `mcp_server.py` (no bridge):
  1. Read `~/.cortex/decisions.jsonl` into memory
  2. Tokenize `context` into keywords (lowercase, len > 2)
  3. Score each decision by keyword overlap across `decision + rationale + context` fields
  4. Optional: filter by `project` field
  5. Sort by score descending, return top-k
  6. Enrich with latest outcome from `~/.cortex/decision_outcomes.jsonl` if exists
- Return: `{"results": [{"decision_id", "project", "decision", "rationale", "outcome"}]}`
- No Vector Search (local has no VS). BM25-style keyword scoring is sufficient at <100 decisions.

**Effort:** Medium (80-120 lines). Pure Python, no deps beyond stdlib.

---

### M3. `flag_anti_pattern` — Pattern Registry

**What cortex-dbx does:** `flag_anti_pattern(name, description, detection_rule, is_anti_pattern)` writes to Postgres `patterns` table. 2 patterns stored, surfaced in intelligence_query results.

**What cortex has:** `~/.cortex/anti_patterns/` directory exists but is empty. No MCP tool, no bridge endpoint.

**Fix spec:**
- Add `cortex_flag_anti_pattern` MCP tool to `mcp_server.py`
- Params: `name: str, description: str, detection_rule: str = None, is_anti_pattern: bool = True`
- Storage: Append to `~/.cortex/patterns.jsonl` (new file)
- Schema: `{"pattern_id": "pat_{timestamp}", "name": str, "description": str, "detection_rule": str|null, "is_anti_pattern": bool, "created_at": iso8601}`
- Enforce unique `name` constraint (scan file before appending)
- Include patterns in `cortex_recall_similar` results (keyword match against name + description)
- Return: `{"pattern_id": str}`

**Effort:** Small (40-60 lines).

---

## Part 2: Broken Tools

### B1. `cortex_plan_create` / `cortex_plan_progress` — 404 Not Found

**Root cause:** MCP tools call `POST /plans/create` and `GET /plans/progress` but these endpoints do not exist in `bridge_endpoint.py`. Zero grep hits. The plan data exists (`~/.cortex/plans/` has 4 old JSON files from Dec 2025) but there's no route to access it.

**Fix spec (Option A — wire endpoints):**
- Add `POST /plans/create` to `bridge_endpoint.py`:
  - Read `GOALS.md` for the specified project
  - Parse into plan items (existing `goal_parser.py` logic)
  - Write plan JSON to `~/.cortex/plans/{project}_{timestamp}.json`
  - Return plan summary
- Add `GET /plans/progress` to `bridge_endpoint.py`:
  - Scan `~/.cortex/plans/` for active plans
  - Cross-reference with git log for completed items
  - Return progress summary

**Fix spec (Option B — bypass bridge):**
- Rewrite both MCP tools to work directly (like `cortex_prompt_refine`)
- Read GOALS.md directly, parse goals, write plan JSON
- Eliminates bridge dependency for these tools

**Recommendation:** Option B. These are read-heavy tools that don't need the bridge.

**Effort:** Medium (100-150 lines for both).

---

### B2. `cortex_conductor_compose` — 422 Field Name Mismatch

**Root cause:** MCP tool sends `{"project": "cortex"}` but bridge endpoint expects `{"project_id": "cortex"}` in the Pydantic model.

**Fix spec:**
- In `mcp_server.py`, change the payload key from `project` to `project_id`:
```python
# Line ~480 in mcp_server.py (approximate)
payload = {"intent": intent, "project_id": project, ...}  # was "project"
```

**Effort:** One-line fix.

---

### B3. `cortex_graph_query` — Param Mismatch + Empty Data

**Root cause (1):** Bridge endpoint requires `node_type` as mandatory `Query(...)` param, but MCP tool sends it as optional (empty string default). When empty, bridge returns 422.

**Root cause (2):** MCP tool sends `query` param but bridge expects `q` param name.

**Root cause (3):** Even with correct params, graph returns empty. The graph data in `~/.cortex/graph/` may use a different storage format than what the endpoint queries.

**Fix spec:**
- Fix param names in MCP tool to match bridge: `q` instead of `query`
- Make `node_type` non-empty by defaulting to `"pattern"` when caller omits it, OR fix bridge to accept empty node_type (return all types)
- Verify graph storage format matches bridge reader — may need to reseed the graph

**Effort:** Small for param fixes (5 lines). Medium if graph data needs reseeding.

---

## Part 3: Degraded Tools

### D1. `cortex_record_decision` — Missing Fields

**Current schema:** `{decision, context, alternatives, rationale}` (4 fields)
**cortex-dbx schema:** `{project, context, decision, rationale, confidence, alternatives, tags}` (7 fields)

**Missing:** `project`, `confidence`, `tags`

**Fix spec:**
- Add params to MCP tool: `project: str = "", confidence: float = 0.0, tags: str = ""`
- Update JSONL schema to include new fields
- `project` is critical for cross-project recall — without it, all decisions are unscoped

**Effort:** Small (10-15 lines changed in MCP tool + bridge endpoint).

---

### D2. `cortex_projects` — Hardcoded Paths

**Current:** Scans hardcoded paths under `~/Dev/` (`Vortex/backend`, `Vortex/frontend`, `cortex`, `alpha_arena`, `pupil`).

**Problem:** Misses all `/dbx-dev/` projects (manulife-genie, genie-iq-score-lite, cortex-dbx). For beta testers, will miss their repos entirely.

**Fix spec:**
- Add configurable `PROJECT_ROOTS` list (default: `["~/Dev", "~/dbx-dev"]`)
- Read from `~/.cortex/config.yaml` or env var `CORTEX_PROJECT_ROOTS`
- Auto-discover repos: scan each root for directories containing `.git/`
- Enrich with decision/outcome counts from `decisions.jsonl` grouped by project field

**Effort:** Medium (50-80 lines). Touches bridge endpoint.

---

### D3. `cortex_recommendations` — Not Decision-Aware

**Current:** Returns high-level strategic view: `{next_action, risk_alerts, goals_summary, session_activity_24h}`. Recommendations are generic ("all goals on track", "no commits in analysis period").

**cortex-dbx:** Returns scored, project-scoped recommendations based on: open decisions without outcomes, recent anomaly alerts, anti-pattern matches.

**Fix spec:**
- After existing recommendation logic, append decision-aware recommendations:
  1. Scan `decisions.jsonl` for entries without matching `decision_outcomes.jsonl` entry (open decisions > 7 days old → "log_outcome" recommendation)
  2. Scan `patterns.jsonl` and check recent decisions against pattern names (anti-pattern match → "review_anti_pattern" recommendation)
  3. Score and merge with existing recommendations
- This depends on M1 (log_outcome) and M3 (flag_anti_pattern) being implemented first

**Effort:** Medium (60-80 lines). Depends on M1 + M3.

---

## Part 4: Working Tools (No Changes Needed)

| Tool | Status | Notes |
|------|--------|-------|
| `cortex_sessions` | Working | 20 sessions tracked, auto-capture from Claude Code JSONL |
| `cortex_batch_status` | Working | Proxies to Anthropic Batch API, 101MB queue DB |
| `cortex_taskboard` | Working | 3 tasks, full CRUD via bridge |
| `cortex_doctor` | Working | Health checks Python, deps, API keys, bridge |
| `cortex_service_health` | Working | Ecosystem health across all services |
| `cortex_orchestrate` | Likely working | Direct import (no bridge), full supervisor module |
| `cortex_research_digest` | Likely working | Direct import, needs Anthropic API key |
| `cortex_prompt_refine` | Conditional | Works if patterns.json populated, heuristic only |

---

## Part 5: Implementation Priority

### Phase A — Beta Blockers (must fix before beta testers)
| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| A1 | Add `project` field to `record_decision` (D1) | Small | Without this, decisions are unscoped — breaks recall |
| A2 | Add `log_outcome` tool (M1) | Small | Closes the feedback loop — core value prop |
| A3 | Add `recall_similar` tool (M2) | Medium | The reason cortex exists — retrieving past decisions |
| A4 | Fix `conductor_compose` field name (B2) | Trivial | One-line fix, unblocks a shipped feature |

### Phase B — Quality Fixes (should fix for beta)
| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| B1 | Fix `graph_query` params (B3) | Small | Unblocks context graph exploration |
| B2 | Add `flag_anti_pattern` tool (M3) | Small | Enables pattern learning |
| B3 | Fix `projects` to scan configurable roots (D2) | Medium | Beta testers will have different repo layouts |
| B4 | Fix or remove `plan_create`/`plan_progress` (B1) | Medium | Currently 404 — either wire up or remove to avoid confusion |

### Phase C — Value Amplifiers (after beta launch)
| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| C1 | Make `recommendations` decision-aware (D3) | Medium | Requires M1 + M3 first |
| C2 | Fix `cortex_outcomes` to use correct schema (Part 1 audit) | Small | Currently reads wrong file |
| C3 | Consider replacing bridge with direct calls (architectural) | Large | Eliminates localhost:8765 dependency for beta |

---

## Part 6: Architectural Recommendation

The 115K-line `bridge_endpoint.py` is the single biggest risk for beta. Every MCP tool (except 4 that use direct imports) requires the bridge process running at localhost:8765. If the bridge crashes, 14 of 18 tools return "Bridge unavailable."

cortex-dbx proves the direct-call pattern works: MCP tool → Python function → storage. No bridge process. For the Phase A fixes (M1, M2, M3), implement them as **direct functions in mcp_server.py** — same pattern cortex already uses for `prompt_refine`, `orchestrate`, and `research_digest`. This avoids touching the bridge and reduces the failure surface for beta testers.

Long-term, consider migrating all bridge-dependent tools to direct calls, retiring the bridge entirely. The bridge was necessary when cortex ran as a separate FastAPI service; as an MCP server in Claude Code's process, the indirection adds latency and failure modes with no benefit.
