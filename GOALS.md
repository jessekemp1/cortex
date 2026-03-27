# Cortex Beta Readiness Goals

## Phase 1: Security Hardening (COMPLETE)
- [x] Replace eval() in workflows/runner.py with safe AST-based condition parser
- [x] Sandbox exec() in runtime/agents/loader.py with AST validation + import whitelist
- [x] Replace all shell=True subprocess calls (6 locations) with shell=False
- [x] Remove cortexDBX (SQL injection via f-strings in Spark queries)
- [x] Add bearer token auth to all API endpoints via FastAPI Depends
- [x] Replace pickle.load/dump with numpy.save/load + json metadata
- [x] Fix snapshot ID collision bug (uuid suffix)

## Phase 2: Robustness Hardening (COMPLETE)

### Error Handling
- [x] Replace all 13 bare `except:` with specific exception types
- [x] Fix cli.py functions returning None on error → return (0, 0) tuples
- [x] Add exc_info=True to all error-level log calls in supervisor/core.py

### Concurrency Safety
- [x] Add threading.Lock (_state_lock) around supervisor shared state
- [x] Make _quality_evaluator singleton thread-safe (double-checked locking)

### Config Validation
- [x] Add __post_init__ validation to SupervisorConfig (bounds on all numerics)
- [x] Wrap env var parsing with try/except fallback to defaults

### API Hardening
- [x] Add slowapi rate limiting middleware (60 req/min)
- [x] Add ge/le bounds to all Query(limit=) params (7 endpoints)
- [ ] Add Pydantic field constraints (max_length, regex) to request models
- [ ] Validate graph query filters against schema before passing to bridge

### Logging (deferred to Phase 3+)
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
