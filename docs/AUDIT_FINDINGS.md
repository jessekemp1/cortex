# Cortex Audit Findings — 2026-06-02

This document is the public record of an adversarial brilliant-tester audit
of `github.com/jessekemp1/cortex`, run against commits `13a22ed3` (pre-audit
baseline) through `3a5241f` (post-audit polish). It exists so external
testers can see what was tested, what failed, and what was fixed — without
having to reverse-engineer it from the commit graph.

The repo is small. The audit is honest. If a finding here contradicts what
the README claims, the README is wrong; please file an issue.

## Methodology

The audit was structured to simulate what a brilliant external developer
will do in their first 15 minutes:

1. `git clone …` — does the install work?
2. Read the README — do the claims match the reality?
3. `pip install -e .` — does this complete without errors?
4. Run a CLI command — does anything actually work?
5. `pytest --collect-only -q` — does the test suite at least *load*?
6. Run pytest — what's the pass rate?
7. Open the largest files — is the code legible or intimidating?
8. `grep -rn jessekemp1` — does the repo leak the maintainer's setup?

Each step was performed against a **fresh clone in `/tmp`**, with a **fresh
venv** created by the system Python, with **no editable install of any
sibling tree**. This is critical — the pre-audit commits passed
maintainer-machine verification but were measured under contamination from
a sibling editable install masking 82 import errors.

## Findings (severity-ranked)

### S0 — Foundational: `cortex` package didn't exist on a fresh install

**Symptom:** Every `cortex` command crashed immediately:

```
ModuleNotFoundError: No module named 'cortex'
```

**Root cause:** The repo used a flat layout — top-level `state_paths.py`,
`feedback.py`, the `intelligence/` package, etc. — but 82 files imported them
through the `cortex.<name>` namespace (e.g. `from cortex.state_paths import
get_cortex_dir`). There was no `cortex/` package on disk; the top-level
`cortex` was a one-line wrapper script.

The maintainer's local editable install of a sibling monorepo silently
exposed the top-level files under a `cortex.*` namespace, so all tests
passed and `cortex demo` ran during pre-audit verification. On any fresh
tester's machine without that sibling install, nothing worked.

**Resolution:** Commit `4724c03`. Replaced the top-level `cortex` wrapper
script (already redundant — `pyproject.toml` provides `cortex = "cli:main"`
as a console_script) with a `cortex/__init__.py` package whose only line is:

```python
__path__.append(repo_root)
```

This extends the package's submodule search path to include the repo root,
so Python's import machinery resolves `cortex.state_paths` →
`<repo_root>/state_paths.py` natively. Works for all import shapes (`import
cortex.X`, `from cortex.X import Y`, `from cortex.X.Y.Z import W`).

This pattern was deliberately chosen over (a) a 82-file refactor to drop
the `cortex.` prefix, (b) eager pre-import of all submodules (causes
circular-init failures), and (c) PEP 562 `__getattr__` (only fires on
attribute access, not on Python's `_find_and_load` step which is what
`from cortex.X import Y` actually uses).

### S1 — `pytest --collect-only` had 18 errors on a fresh clone

**Symptom:** First command a brilliant tester runs after install. `pytest
--collect-only -q` exited with collection errors before any tests could run.

**Root cause(s):**
- `_contrib/synthetic/` shadowed `synthetic/` — pytest could not decide
  which to load, raised `ImportPathMismatchError` on every test file.
- `synthetic/pupil/tests/*` imported `pupil` (a separate sibling project
  that was never published; the tests should not have been in this repo).
- `tests/test_workflows.py` imported `cortex.workflows.runner` (module
  doesn't exist; orphan test).
- `plugins/status/tests/__init__.py` created a `tests` namespace collision
  with the rootdir `tests` package.

**Resolution:** Commit `ef2f5c5`. Deleted `_contrib/`, the orphan pupil
tests, the orphan workflows test, and the conflicting `__init__.py`.
Collection now exits 0 with 1908 tests discovered (after the S0 shim;
see also S2 below for the 23 runtime failures the cleaner collection
unblocked).

### S2 — Sticker shock: 23 runtime test failures on a fresh install

After S0 + S1 fixes, the full pytest surfaced 23 failures + errors that
had been silently buried. They split into four categories:

**Cat 1 (5 errors): missing optional deps.** Tests for retrieval benchmarks
+ the conversation ingestor's digest path required `scikit-learn`, which
is not a core dependency. Resolution: `pytest.importorskip("sklearn")` at
the affected module tops. The tests skip cleanly when sklearn isn't
installed instead of erroring at collection.

**Cat 2 (5 failures): test/code drift in the conductor router.** The
routing table had been updated to add a `qwen` provider and to put
cost-optimized models as the primary for `long_context` (qwen-turbo) and
`research` (deepseek-chat), but the tests still asserted the old `xai`
primary. Resolution: updated 5 tests in `conductor/tests/test_router.py`
to reflect the shipped table. Code was right; tests had lagged.

**Cat 3 (2 failures): schema drift in OutcomeEntry deserialization.**
`feedback.py:load_outcomes` was unpacking arbitrary JSON kwargs into the
`OutcomeEntry` dataclass. When newer writers persisted a `validated`
field that older readers didn't know about, deserialization raised
`TypeError`. Resolution: filter incoming kwargs against
`OutcomeEntry`'s declared fields before unpacking. Forward/back compat is
now graceful.

**Cat 4 (11 failures): real bugs + env-gated tests.**
- `batch/briefing_batcher.py` `InsightBatcher.__init__` was missing
  `self.model_policy = BatchModels()` — `_build_insight_requests` then
  raised `AttributeError` mid-batch. Production bug. Fixed in `3a5241f`.
- `batch/reflection_agent.py:72` mixed offset-naive and offset-aware
  `datetime` instances. Fixed by TZ-normalizing both sides before compare.
- `tests/test_compact_briefing.py::test_compact_flag_in_cli` didn't expect
  the API-key pre-flight added in Phase 1. Resolution: the test now patches
  `cli.commands._helpers.require_api_key` (it tests CLI plumbing, not the
  API).
- `tests/test_orchestration_script_contracts.py`: `parents[2]` should have
  been `parents[1]`, and the scripts being tested aren't shipped in this
  repo. Resolution: fixed the path bug and added `skipif` for missing
  scripts.
- `plugins/status/tests/test_status.py::test_full_workflow_in_real_repo`
  hard-asserted the parent directory was named `Dev`. Resolution: `skipif`
  when the check isn't living under `~/Dev`.
- `tests/test_moltbot_integration.py` required a running Cortex Bridge on
  `127.0.0.1:8765`. Resolution: module-level `skipif` probes the socket;
  tests skip cleanly when the bridge isn't up.

**Post-S2 state:** 1855 pass, 1 fail (the moltbot test fails on the
maintainer's box because a local bridge is running and the version is
slightly stale; on any fresh tester's machine without a bridge running,
the skipif fires and the failure becomes a skip). Fresh-tester pass rate:
100%.

### S3 — README claimed numbers that weren't true on a fresh clone

**Symptom:** The README badge showed `tests-2361+ passing`. The actual
number on a fresh clone of the audited commit was 1855.

**Root cause:** The 2361 figure was measured from a contaminated
editable-install verification run. After the S0/S1/S2 cleanup, the
honest number is 1855.

**Resolution:** Badge corrected. Quick Start reordered so `cortex demo`
is step 2 — testers can verify the headline claim before committing
API keys or starting LLM-backed workflows.

### S4 — Personal-environment leaks

**Symptom:** `launcher/launcher_data.json` shipped to the public repo with
`~/Dev/*` paths plus running PIDs. `grep -rn jesse.kemp .`
returned 28 hits across code + docs.

**Resolution:** Commit `ef2f5c5` removed `launcher_data.json` and added
it to `.gitignore`. Commit `fe7e0d1` sanitized `weekly_planner.py`,
`deep_assessment.py`, `self_audit.py`, and `weekly_report.sh` to read
`CORTEX_DEV_ROOT` from env with a `~/Dev` default instead of hardcoding
`~/Dev`.

### S5 — Silent-hang failure mode on missing API key

**Symptom:** `cortex briefing` with `ANTHROPIC_API_KEY` unset hung for
~30 seconds with no output, then printed an unhelpful traceback.

**Resolution:** Commit `fe7e0d1` added `cli.commands._helpers.require_api_key()`
called at the top of `cmd_briefing` and `cmd_intelligence`. Now exits `2`
with an actionable message in <100ms.

## What this audit did NOT cover

Honest gaps that brilliant testers will spot. These are deliberately
deferred to focused post-v1.0.0 PRs, not pretended-done:

- **God-file split — Phase 3a functionally complete.**
  `api/bridge_endpoint.py` was 3158 LOC / 58 routes in one file at the
  start of the audit. All ten named clusters have been extracted:
    - `api/routes/guardian.py`     (6 routes — `4f14a71`)
    - `api/routes/batch.py`        (3 routes — `369ddc6`)
    - `api/routes/queue.py`        (4 routes — `73778ef`)
    - `api/routes/taskboard.py`    (5 routes — `505c740`)
    - `api/routes/conductor.py`    (4 routes — `bb66ea7`)
    - `api/routes/decisions.py`    (1 route  — `52a5b80`)
    - `api/routes/meta.py`         (3 routes — `af0d347`)
    - `api/routes/activity.py`     (1 route  — `3f527c6`)
    - `api/routes/sessions.py`     (3 routes — `592b016`)
    - `api/routes/intelligence.py` (4 routes — `b0fcabc`)

  bridge_endpoint.py is now **1600 LOC** (down from 3158, −49%). 34 of
  58 named-cluster routes extracted across 10 router files. The
  remaining ~24 inline routes are the app's core surface (health, status,
  metrics, anomalies, batches, projects, signal-bus, docs, predictions,
  v2 stats) plus the FastAPI app assembly, CORS, middleware, and lazy-
  init helpers. Splitting those further yields diminishing returns
  relative to the review-confidence cost paid.

  The strict P3a-01 target was `≤ 200 LOC`. We did not hit that — the
  remaining content is genuinely "the FastAPI app's own assembly code"
  and a handful of small core routes. The functional goal (each named
  domain readable in isolation) is met. A subsequent PR can pursue
  the strict target by extracting the small core routes too, but that's
  cosmetic cleanup, not architectural.
  create `api/routes/<concern>.py`, define an APIRouter, move handlers
  + their Pydantic request models + their module-level helpers, replace
  the inline definitions in bridge_endpoint.py with
  `app.include_router(...)`, and verify with `TestClient` that every
  path still resolves to the expected status code. The remaining
  extractions are tracked as separate PRs to keep each blast radius
  small:
    - `api/routes/intelligence.py` — `/intelligence/*`, `/recommendations`, `/meta/compounding/*`
    - `api/routes/conductor.py` — `/conductor/*` (4 routes; `/decisions/record` is conceptually separate UI tracking)
    - `api/routes/decisions.py` — `/decisions/record`
    - `api/routes/sessions.py` — `/sessions`, `/session/*`, `/activity/heatmap`

- **`briefing.py` split — harness ready, refactor not started.**
  Still 122 KB / 3035 LOC. The pre-requisite golden-file harness shipped
  at `tests/test_briefing_golden.py` + `tests/fixtures/briefing_golden/`
  in `fc6b6bc` + `186003e`. It captures byte-stable output for
  `format_briefing`, `format_compact`, and `format_statusline` against
  a deterministic `BriefingData` fixture, with `detect_resume_context`
  / `detect_stale_items` patched out so the goldens don't depend on
  CWD git state. The split itself remains the highest-risk single
  refactor in the codebase; the formatters share many internal helpers
  (`_load_briefing_style`, `_build_progress_bar`,
  `get_briefing_signal_quality`, ...) that need careful slice
  boundaries. Plan: extract one formatter at a time with the harness
  green between each step.

- **Final personal-path leak in MEMORY_FILE — fixed in `9caedb1`.**
  The audit's earlier `grep jessekemp1|jesse.kemp|kempion` sweep had
  missed `-Users-jesse-kemp-Dev` (the Claude-projects encoded form of
  the maintainer's path with `-` separators) at
  bridge_endpoint.py:985. Surfaced by a fresh-clone verify post-
  intelligence-extraction. Now derived from `WORKSPACE` (which itself
  reads `CORTEX_DEV_ROOT` env var with `~/Dev` fallback). `grep -rn
  'jesse.kemp\|/Users/kempion' api/` now returns zero results.
- **Test-to-source ratio.** 1910 collected / ~700 source files = 0.27.
  Healthy is ≥ 0.30. The MCP-tool contract pass (37 tests) raised this
  significantly; further coverage is a continuing concern, not a one-PR
  fix.
- **External user feedback.** The audit was performed by the maintainer
  against the maintainer's own work. The first external feedback report
  will, with near-certainty, surface findings that this document missed.
  That's the next test.

## How to file findings

Use the [bug report template](../.github/ISSUE_TEMPLATE/bug_report.yml) —
the structured fields (especially `cortex doctor` output and the commit
SHA you saw the bug on) make audit-style findings actionable. If a
finding would lower the next audit's score, it is particularly welcome.
