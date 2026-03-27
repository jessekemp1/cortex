# Cortex Beta Readiness Goals

## Phase 1: Security Hardening (COMPLETE)
- [x] Replace eval() in workflows/runner.py with safe AST-based condition parser
- [x] Sandbox exec() in runtime/agents/loader.py with AST validation + import whitelist
- [x] Replace all shell=True subprocess calls (6 locations) with shell=False
- [x] Remove cortexDBX (SQL injection via f-strings in Spark queries)
- [x] Add bearer token auth to all API endpoints via FastAPI Depends
- [x] Replace pickle.load/dump with numpy.save/load + json metadata
- [x] Fix snapshot ID collision bug (uuid suffix)

## Phase 2: Robustness Hardening

### Error Handling
- [ ] Replace all bare `except:` with specific exception types + logging
  - `integration/git_tracker.py:189`
  - `integration/metrics.py:32`
  - `cli.py:2054`
  - `scripts/internal/auto_calibration.py:44,55,100,244`
  - `portfolio_analyzer.py:181`
  - `batch/intelligent_orchestrator_anthropic.py:181`
  - `intelligence/status/git_hygiene.py:166,194,210`
  - `reports/validation_2026-02/collect_metrics.py:99`
- [ ] Fix functions returning None on error (indistinguishable from "no data")
  - `cli.py:176` (_portfolio_counts_from_scanner)
  - `cli.py:195` (_goal_counts_from_parser)
- [ ] Add exc_info=True to all error-level log calls in supervisor/core.py

### Concurrency Safety
- [ ] Add threading.Lock around supervisor shared state
  - `supervisor/core.py:88-90` (_dispatched_ids, _dispatched_descriptions)
  - `supervisor/core.py:103-105` (_pending_ai_tasks, _pending_batch_ids)
- [ ] Make _quality_evaluator singleton thread-safe (supervisor/core.py:31)

### Config Validation
- [ ] Add Pydantic or __post_init__ validation to SupervisorConfig
  - Validate tick_interval_seconds > 0 and <= 3600
  - Validate max_concurrent_shell_tasks > 0 and <= 100
  - Validate stale_task_hours > 0
- [ ] Wrap env var parsing with try/except (supervisor/config.py:94-101)

### API Hardening
- [ ] Add rate limiting middleware (slowapi or custom)
- [ ] Add input bounds to all query params (limit: ge=1, le=100)
- [ ] Add Pydantic field constraints (max_length, regex) to request models
- [ ] Validate graph query filters against schema before passing to bridge

### Logging
- [ ] Add structured JSON logging (structlog or python-json-logger)
- [ ] Implement log rotation (RotatingFileHandler)
- [ ] Audit all error paths for sensitive data leakage

## Phase 3: Test Quality & Enterprise Credibility

### Critical Coverage Gaps
- [ ] Write tests for api/bridge_endpoint.py (30+ endpoint tests)
  - Auth verification (valid token, invalid token, no token, localhost)
  - Input validation (bounds, types, malformed JSON)
  - Error responses (404, 500, rate limit)
- [ ] Expand intelligence/ test coverage (113 files, only 24 tests)
  - Priority: context_injector, executor, storage modules
- [ ] Add supervisor/ unit tests for dispatch, routing, approval integration

### Assertion Quality
- [ ] Replace 356 isinstance() assertions with value-checking assertions
- [ ] Replace 356 `is not None` assertions with specific value checks
- [ ] Add assertion helpers that show actual vs expected on failure

### Edge Case & Error Path Coverage
- [ ] Add error path tests (database unavailable, file missing, API timeout)
- [ ] Add boundary condition tests (empty inputs, max-size inputs)
- [ ] Target: 20% of tests should cover edge cases (currently 7%)

### Flaky Test Elimination
- [ ] Replace all time.sleep() in tests with mocked time or event-based waits
- [ ] Add @pytest.mark.slow markers to timing-dependent tests
- [ ] Isolate env var dependencies with monkeypatch in all tests

### Missing Test Categories
- [ ] Add property-based tests (Hypothesis) for core invariants
  - Priority scores always valid, learning metrics bounded 0-1
- [ ] Add API contract tests for bridge_endpoint.py
- [ ] Configure pytest-cov with 75% minimum threshold
- [ ] Add coverage reporting to CI

### Integration Test Improvement
- [ ] Reduce over-mocking in integration tests (146 Mock instances)
- [ ] Add at least 3 unmocked end-to-end tests exercising real components
  - supervisor tick → task execution → outcome recording
  - intelligence query → context injection → response
  - guardian claim → snapshot → recovery
