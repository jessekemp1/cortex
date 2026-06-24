# Cortex Ship-Readiness — Hygiene / Dead-Code Removal Plan

**Companion to:** `docs/P0_DEAUTHORING_PLAN.md` (that one = correctness/de-authoring; this one = cruft/dead-code cut).
**Source:** Opus 4.8 advisor audit, read-only, evidence-backed (`grep`/`ruff`/`vulture`).
**Hygiene grade:** **C+ — shippable after a focused cut, not before.**

## Top-line
- Core package (`intelligence/`, `engines/`, `supervisor/`, `conductor/`, `bridge*.py`, `mcp_server.py`) is densely interconnected and **live**.
- Cut size: **~6–8 scratch artifacts** + **`site/` (3.1 MB)** + **~5 orphaned dirs** (`mvp/`, `lean/`, `cortex_mvp`, `integrations/`, `examples/`) + **2 dead modules** + **1 critical duplicate-class consolidation** + **215 ruff F401/F811** auto-fixable nits.
- **The single most important fix is NOT a deletion** — it's resolving the two-`RecommendationEngine`-classes hazard (below) before shipping to Omnigent.
- **Packaging caveat:** `pyproject.toml` excludes (`:86-111`) + `MANIFEST.in` already prune `mvp*/cortex_mvp*/site*/automation*/batch*/reports*` from the wheel — so most scratch **doesn't ship**, but it's still repo clutter that confuses new users. The `cortex_intelligence.egg-info/top_level.txt` listing everything is a **stale** old-build leftover, not authoritative.
- **Methodology note (important):** the `cortex/` namespace shim (`cortex/__init__.py` extends `__path__`) means every dead-code check must grep BOTH `from cortex.X import` **and** bare `from X import`. A naive bare-name grep falsely flags `recommendations.py` as dead.

---

## Removal table
| Path | Type | Evidence | Verdict | Risk |
|---|---|---|---|---|
| `semantic_recommender.py` | dead module | only self-ref; no import (either form); no `__main__` | **SAFE-DELETE** | Low |
| `project_metadata.py` | dead module | `ProjectMetadataReader` only self-ref; no inbound import | **VERIFY-THEN-DELETE** (scan `importlib`/getattr) | Low |
| `cortex_mvp` (272 B bash wrapper) | scratch | runs `python mvp/cli.py` (dead) | **SAFE-DELETE** | Low |
| `mvp/` (cli, dashboard) | superseded | 0 inbound; superseded by `cli/` (26 refs) + `mcp_server.py`; wheel-excluded | **VERIFY-THEN-DELETE** (no `install*.sh` ref) | Low |
| `lean/` (7 files) | superseded | 0 inbound; parallel "guardians" vs live `guardian/` (14 refs) | **VERIFY-THEN-DELETE** (no `install_git_hooks.sh` ref) | Low |
| `integrations/` (`vortex_monitor.py`) | dead module | 0 inbound imports (≠ live `integration/`, 18 refs); standalone `__main__` | **VERIFY-THEN-DELETE** (no plist/cron) | Low |
| `examples/` (7 demo_*.py) | scratch | 0 inbound; wheel-excluded | **VERIFY-THEN-DELETE** (keep only if intended as docs) | Low |
| `site/` (3.1 MB) | scratch | landing-page assets; wheel-excluded | **VERIFY-THEN-DELETE** (move to gh-pages/separate repo) | Low |
| `reports/` | scratch | author run outputs; wheel-excluded | **SAFE-DELETE** | Low |
| `research_briefs/` (88 K) | scratch | author notes; not imported | **VERIFY-THEN-DELETE** (grep `research_briefs/SKILL.md` for skill wiring) | Low |
| `WORK_PROGRESS_REPORT.md` | scratch | author log | **SAFE-DELETE** | None |
| `ICLR_2026_MEMAGNETS_PITCH.md` | scratch | conference pitch | **SAFE-DELETE** | None |
| `cortex_ai_research_brief_2026-03-26.md`, `…_2026-04-08.md` | scratch | dated briefs at root | **SAFE-DELETE** | None |
| `research_directives.md` | scratch | author directives | **VERIFY-THEN-DELETE** (grep loader) | Low |
| `_contrib/.DS_Store` + empty `_contrib/` | scratch | only a `.DS_Store` (egg-info SOURCES stale) | **SAFE-DELETE** | None |
| `batch/bandwidth_experiments.py` | dead block | vulture: unreachable after `return` (lines 314/375/452/517/587, 100%) | **CONSOLIDATE** (trim) or delete if experiment-only | Low |
| 215 × F401/F811 | import noise | `ruff check --select F401,F811` (129 auto-fixable) | **CONSOLIDATE** (`ruff --fix`, then re-test) | Low |

---

## Consolidations (real refactors — do last, full test run each)

### 1. `RecommendationEngine` — TWO live classes, same name, incompatible APIs (HIGH — do before Omnigent ship)
- `recommendations.py::RecommendationEngine` — report API (`get_full_report`, `get_recommended_next_action`, …); imported by **`bridge_intelligence.py:1045,1065,1086,1110`** (the **live MCP path Omnigent hits**) + `intelligence/unified_intelligence.py:1071`.
- `recommendation_engine.py::RecommendationEngine` — `generate_recommendations(...)`; 17 refs (`bridge_system.py`, `orchestrator.py`, `bridge_intelligence.py:1222…`, `briefing/__init__.py`, …).
- **Fix:** rename `recommendations.py::RecommendationEngine` → e.g. `PortfolioRecommender` to kill the collision; repoint the 5 report-API call sites; later decide whether to fold its surface into `recommendation_engine.py`. **Run the `:8765` MCP smoke test after** — `bridge_intelligence.py` is the Omnigent-facing path.
- (A third, *unrelated* `intelligence/recommendations/` package is live and fine — don't touch.)

### 2. `spec_knowledge_base.py` (top-level) → fold into `intelligence/spec_knowledge_base.py`
- `intelligence/` version is on the live bridge/MCP path (`bridge.py:47`, +4); top-level reached only by `portfolio_analyzer.py:23`, `data_migration.py:330`, `scripts/internal/e2e_validation.py:27`.
- **VERIFY-THEN-CONSOLIDATE:** diff class signatures for API-compat, pick `intelligence/` as canonical, repoint the 3 top-level importers, delete top-level.

### NOT duplicates — keep all (flagged to prevent mistaken deletion)
- `bridge.py` / `bridge_system.py` / `bridge_intelligence.py` — intentional mixin split (`bridge.py:201-202`; "Split for maintainability, Feb 2026"). 92 refs to `bridge.py`. **No action.**
- top-level `synthetic/` — live (`bridge.py:146-147`, 112 refs). `_contrib/synthetic/` is gone (only stale egg-info). **No action.**

---

## Stub / TODO & test-debt
- 70 TODO/FIXME/XXX/HACK markers. Hotspot: **`batch/optimizer.py` (25)** — review if finished; then `intelligence/deep_analysis.py` (9), `agents/data_agent/analyzers/lesson_extractor.py` (5), `ai_intelligence.py` (4).
- 17 `NotImplementedError` — audit as intentional ABC contracts vs genuine stubs.
- **`tests/KNOWN_ISSUES.md` is STALE:** claims "~87 weak `assert X in (True, False)`" but the tree has **10**. Reconcile/fix the 10 (`is True` / `pytest.mark.skipif`) before a user reads the doc and panics.

## Dependencies
- **`openai` declared but unused** — 0 imports (only `sk-` regex/comments; `conductor/caller.py` uses a local `openai_compat`, not the pkg). Remove from `pyproject.toml:54` + `requirements.txt:30` (or justify).
- Used-but-undeclared, all guarded (low risk): `watchdog`, `tiktoken`; `pandas` only in `mvp/dashboard.py` (moot once `mvp/` deleted).
- `requirements.txt` vs `pyproject.toml` drift — for a shipped pkg the pyproject-extras layout is right; regen/mark `requirements.txt` as dev-pin to avoid drift.

## Entry points (flag only — install robustness is P1 elsewhere)
Overlapping installers: root `install.sh` (main), `install_automation.sh`, `install_git_hooks.sh`, `uninstall_automation.sh`; `scripts/install_launchagents.sh` + others; `com.cortex.heartbeat.plist` + `automation/*.plist`. These reference the standalone `__main__` entry scripts (`heartbeat.py`, `scheduler.py`, `self_audit.py`, `deep_assessment.py`, `portfolio_analyzer.py`, `goal_velocity.py`, `data_migration.py`) — reachable via plist/cron/docs, **not dead**.

---

## Execution order
1. **Reconcile stale doc** (no code risk): fix `tests/KNOWN_ISSUES.md` count + the 10 weak asserts.
2. **`ruff check --select F401,F811 --fix`** → run tests; manually re-check `__init__.py` re-exports (`cli/__init__.py`, `briefing/__init__.py`).
3. **SAFE-DELETE scratch:** `WORK_PROGRESS_REPORT.md`, `ICLR_2026_MEMAGNETS_PITCH.md`, the two `cortex_ai_research_brief_*.md`, `reports/`, `cortex_mvp`, `_contrib/`.
4. **VERIFY-THEN-DELETE modules:** `semantic_recommender.py`, `project_metadata.py`, `integrations/`.
5. **VERIFY-THEN-DELETE dirs:** `mvp/`, `lean/`, `examples/`, `site/`, `research_briefs/`.
6. **Dep cut:** remove `openai`; reconcile `requirements.txt`.
7. **CONSOLIDATIONS (full test run each):** `spec_knowledge_base` fold; `RecommendationEngine` rename (+ MCP smoke test); trim `batch/bandwidth_experiments.py`.

**Verification gate before EVERY delete:** (a) `ruff`/`pytest` green; (b) `grep -rn "<name>"` across `*.py *.sh *.plist *.toml *.md` returns only self + intended; (c) scan neighborhood for `importlib`/`__import__`/`import_module`/entry-point strings; (d) test BOTH `from cortex.X import` and bare `from X import`.
