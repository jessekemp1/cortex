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

## Phase 3: Test Quality & Enterprise Credibility (COMPLETE)

### Critical Coverage Gaps
- [x] Write tests for api/bridge_endpoint.py (18 tests: auth, validation, errors)
- [x] Add SupervisorConfig validation tests (12 tests: bounds, env safety)
- [x] Add edge case tests (23 tests: supervisor, guardian, store, quality evaluator, workflows)
- [ ] Expand intelligence/ test coverage further (deferred)

### Assertion Quality
- [x] Replace isinstance() assertions with value checks in integration_learning, briefing, orchestrator, supervisor
- [x] Replace `is not None` with specific value assertions (briefing, supervisor, orchestrator)
- [ ] Add assertion helpers (deferred — current assertions are specific enough)

### Edge Case & Error Path Coverage
- [x] Add error path tests (corrupt state, missing files, empty inputs, bad snapshots)
- [x] Add boundary condition tests (zero duration, empty lists, injection attempts)
- [x] Condition evaluator edge cases (empty, unknown step, malicious input)

### Flaky Test Elimination
- [x] Replace all time.sleep(1.1) in guardian tests with mocked time
- [x] Remove unnecessary time.sleep(0.01) from snapshot tests (UUID suffixes)
- [x] Fix hardcoded date strings in test_prompt_history (relative timestamps)

### Coverage Reporting
- [x] Configure pytest-cov with 50% minimum threshold
- [x] Coverage at 69.43% across supervisor/, guardian/, intelligence/storage/, workflows/
- [x] Key modules: quality_evaluator 100%, config 97%, approval 96%, snapshots 91%

### Remaining (future sprints)
- [ ] Add property-based tests (Hypothesis) for core invariants
- [ ] Expand intelligence/ tests from 24 to 120+
- [ ] Reduce over-mocking in integration tests
- [ ] Add 3 unmocked e2e tests (supervisor→execution→outcome, guardian claim→snap→recover)
