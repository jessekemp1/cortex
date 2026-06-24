# Changelog

All notable changes to Cortex are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-06-24

Beta-readiness release: make Cortex work for a second user, fix the decision
write path, and parse on Python 3.11.

### Fixed
- `cortex_record_decision` now records. It POSTed the learning-loop schema to
  `/decisions/record`, a path owned by the Co-Navigator scenario recorder, so
  every call returned 422. Added a dedicated `POST /decisions/learning` route and
  repointed the MCP tool. (#4)
- Parse on Python 3.11. A nested f-string containing a backslash in
  `intelligence/contracts.py` was a `SyntaxError` before 3.12, breaking
  `pytest --collect-only` (the CI smoke gate) on the advertised minimum Python. (#4)
- `discover_projects()` no longer raises (HTTP 500 via `/projects`) when
  `CORTEX_ROOT_DIR` points at a file — guard with `is_dir()`. (#5)

### Changed
- De-authored for a second user: project discovery resolves from `CORTEX_ROOT_DIR`
  via `config.discover_projects()`; removed the hardcoded `~/Dev`, the author's
  project list, and the literal default project `"cortex"`. `cortex_intelligence`
  accepts an explicit `project`. (#5)

### Removed
- Dead/superseded code: `mvp/`, `lean/`, `integrations/`, `examples/`, `reports/`,
  `semantic_recommender.py`, `project_metadata.py`, scratch docs; `ruff` F401/F811
  sweep. (#5)

### Known issues (beta)
- Intelligence git-context is empty for a "folder of independent repos" layout
  (currently uses the monorepo model). Tracked.
- Residual author-specific paths remain in `NEXT_SESSION_FILES` and `/health`
  checks. Tracked.

## [1.0.0] — 2026-06-02

First public release surviving an adversarial brilliant-tester audit.

### Added
- `cortex demo` — falsifiable 30-second proof of the prompt→outcome FK loop.
  Runs against a synthesized in-memory queue using the real
  `intelligence.outcome_linker`. No API key, no network call. (`fe7e0d1`)
- `intelligence/outcome_linker.py` — the FK contract module that closes the
  prompt → commit/test_result loop. Accepts `queue_path` / `outcomes_path`
  kwargs so demos and tests can use isolated tempdirs without mutating
  module-level state. Idempotent on re-run. (`d5ed3f3`)
- `cortex/__init__.py` — namespace shim. Extends the package `__path__` so
  `from cortex.X import Y` resolves to top-level modules at the repo root.
  Lets 82 internal `cortex.*` import sites work on a fresh `pip install -e .`
  without per-site refactoring. (`4724c03`)
- API-key pre-flight in `cli.commands._helpers.require_api_key()`. Inserted
  at the top of `cmd_briefing` and `cmd_intelligence` so they exit `2` with
  an actionable message instead of hanging when `ANTHROPIC_API_KEY` is
  unset. (`fe7e0d1`)
- `tests/test_outcome_linker.py` — 5 integration tests against the real
  linker, covering happy-path attribution, idempotency, isolation, and
  no-op semantics on empty queues. (`d5ed3f3`)
- `tests/test_research_batcher.py` — 7 tests for the previously-uncovered
  `batch/research_batcher.py` surface (empty-batch fast path, payload
  assembly, success/error/unknown result envelopes). (`fc383c9`)
- `tests/test_mcp_tools_contract.py` — 37 contract tests parametrized over
  all 18 MCP tools (smoke + return-type-is-str + non-empty-output +
  JSON-or-word-content). (`fc383c9`)
- `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml` — structured
  issue templates. (`d5ed3f3`)
- `CONTRIBUTING.md` — 60-second onboarding map pointing at `cortex demo`
  as the canonical first action. (`d5ed3f3`)
- `docs/AUDIT_FINDINGS.md` — public audit log with severity-ranked
  findings, evidence, and resolution notes.
- `.github/workflows/ci.yml` — collection + demo smoke on every PR.

### Changed
- `cli/commands/demo.py` — switched from monkey-patching
  `intelligence.outcome_linker.QUEUE`/`OUTCOMES` to passing kwargs. (`d5ed3f3`)
- `conductor/caller.py`, `runtime/config.py` — `.env` loading moved out of
  module init time. Pre-flight checks now see the real shell environment
  instead of one mutated by a transitive import. (`d5ed3f3`)
- ROADMAP.md §1 Phase-1 milestones re-anchored to the actual v1.0.0 ship
  state. (`d5ed3f3`)
- README Quick Start: `cortex demo` is now the first action, before any
  API-key setup, so testers can verify the headline claim before
  committing credentials. (this release)
- Tests badge in README: `2361+` → `1855` (real number on a fresh-clone
  pytest run; the larger number had been inflated by a contaminated
  editable install during measurement).
- `conductor/tests/test_router.py` — updated to reflect the shipped
  routing table (qwen primary for `long_context`, deepseek primary for
  `research`, 7 providers in the registry). (`3a5241f`)
- `feedback.py:load_outcomes` — now filters JSON kwargs against
  OutcomeEntry's dataclass fields. Tolerates schema drift across versions.
  (`3a5241f`)

### Fixed
- `batch/briefing_batcher.py` `InsightBatcher.__init__`: missing
  `self.model_policy = BatchModels()` assignment was causing an
  AttributeError mid-batch. (`3a5241f`)
- `batch/reflection_agent.py:72`: `datetime` comparison was mixing
  offset-naive and offset-aware values when input records varied in TZ
  handling. Now normalizes both sides before comparing. (`3a5241f`)
- Multiple test files updated to skip cleanly when optional dependencies
  (`sklearn`, `scipy`) or environmental preconditions (Cortex Bridge
  running, repo under `~/Dev`, internal toolchain scripts) aren't
  present. Brilliant testers cloning into `/tmp` and running `pytest`
  cold no longer see false failures. (`3a5241f`)

### Removed
- Top-level `cortex` executable script. `pyproject.toml`'s
  `[project.scripts] cortex = "cli:main"` already provides the wrapper;
  the explicit script was redundant and conflicted with making `cortex/`
  a real Python package. (`4724c03`)
- `_contrib/` directory (4.2 MB shadow of `synthetic/`, `cortexdbx/`,
  `site/`). Was the primary source of pytest collection errors on a
  fresh clone. (`ef2f5c5`)
- `launcher/launcher_data.json` — leaked the maintainer's full
  `/Users/jesse.kemp/Dev/*` dev environment + running PIDs. (`ef2f5c5`)
- Top-level `cortex` (script form). (`4724c03`)

### Known Issues
- `synthetic/tests/` and `tests/test_hybrid_retriever.py` require
  `scipy` / `sklearn` (not core deps). Install them or pass
  `--ignore=synthetic/tests --ignore=tests/test_hybrid_retriever.py`
  to pytest.
- God-file refactors (`briefing.py` 122 KB, `api/bridge_endpoint.py`
  3158 LOC / 58 routes) remain. Tracked in `docs/AUDIT_FINDINGS.md`
  as deliberate post-v1.0.0 work — each needs a focused PR with
  golden-file route regression.

## Pre-v1.0.0

Pre-v1.0.0 history is in the git log. The project's "real" public-ready
state begins at the v1.0.0 tag — prior commits assumed a contaminated
editable-install environment for verification.
