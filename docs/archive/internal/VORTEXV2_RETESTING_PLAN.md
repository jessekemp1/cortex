# VortexV2 Retesting Plan

**Created**: 2026-01-31
**Reason**: Testing audit revealed critical gaps (see VORTEXV2_TESTING_AUDIT.md)
**Goal**: Verify VortexV2 actually works at user level, not just code level

---

## The Problem

**VortexV2 has 1,180 tests but only 20% code coverage.**

Critical systems have **0% coverage**:
- Authentication/rate limiting (291 lines)
- Monitoring/alerts (750 lines)
- GRIB cache (81 lines)
- Ensemble static models (473 lines)

**Same pattern as /prompt-learn failure**: Tests exist, tests may pass, but user-facing features unverified.

---

## Retesting Strategy

### Top-Down (User First)

**NOT** this (bottom-up):
```
❌ Test Python functions → Test classes → Test modules → Assume API works
```

**THIS** (top-down):
```
✅ Test API endpoints → Test integration → Test components → Test units
   (User level first)      (Working backwards)
```

---

## Phase 1: Critical Path Verification (This Week)

### Test 1: API Endpoints (User Acceptance)

**Test manually, then generate evidence**:

```bash
# Start API
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
python app/main.py

# Test health endpoint
curl http://localhost:8000/
curl http://localhost:8000/api/v2/health

# Test forecast endpoint (CRITICAL)
curl -X POST http://localhost:8000/api/v2/weather/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 44.5,
    "longitude": -82.0,
    "forecast_hours": 24
  }'

# Expected: 200 OK with valid forecast data
# If 500/422: FAILS retesting
```

**Edge cases**:
```bash
# Invalid coordinates
curl -X POST http://localhost:8000/api/v2/weather/forecast \
  -H "Content-Type: application/json" \
  -d '{"latitude": 91.0, "longitude": -82.0, "forecast_hours": 24}'

# Expected: 422 Validation Error

# No GRIB data available
# Expected: 500 with clear error message (not silent failure)
```

**Success criteria**:
- [ ] Health endpoint returns 200
- [ ] Forecast endpoint returns 200 with valid data
- [ ] Invalid coords return 422 (not 500)
- [ ] Missing GRIB returns 500 with **clear error** (not cryptic stack trace)
- [ ] Response includes required fields: forecast, wind_speed, wind_direction, confidence

**Generate evidence**:
```bash
python cortex/enforcement/evidence_generator.py vortex-forecast-api
```

---

### Test 2: Authentication (0% Coverage → Must Verify)

```bash
# Test without API key
curl http://localhost:8000/api/v2/weather/forecast

# Expected: 401 or 403 (if auth is required)
# If 200: AUTH NOT WORKING

# Test rate limiting
for i in {1..100}; do
  curl http://localhost:8000/api/v2/health
done

# Expected: Eventually get 429 Too Many Requests
# If always 200: RATE LIMITING NOT WORKING
```

**Success criteria**:
- [ ] Unauthorized requests blocked (if auth enabled)
- [ ] Rate limiting triggers after N requests
- [ ] Clear error messages for auth failures

**Generate evidence**:
```bash
python cortex/enforcement/evidence_generator.py vortex-auth
```

---

### Test 3: Streamlit UI (User Interface)

```bash
# Start UI
streamlit run ui/app.py
```

**Manual verification**:
- [ ] App loads without errors
- [ ] Can enter coordinates
- [ ] Can request forecast
- [ ] Forecast displays correctly
- [ ] Map renders (if applicable)
- [ ] Navigation between pages works

**Success criteria**: All UI flows work without errors

**Generate evidence**:
```bash
python cortex/enforcement/evidence_generator.py vortex-ui
```

---

### Test 4: GRIB System (0% Coverage → Must Verify)

```bash
# Check GRIB status
curl http://localhost:8000/api/v2/weather/grib/status

# Expected: 200 with status information
# Or 500 with clear error if GRIB unavailable
```

**Success criteria**:
- [ ] GRIB status endpoint works
- [ ] GRIB download works (if enabled)
- [ ] GRIB cache works (if enabled)
- [ ] Clear errors if GRIB unavailable (not cryptic failures)

---

### Test 5: Monitoring (0% Coverage → Must Verify)

**Check monitoring endpoints**:
```bash
# Health check
curl http://localhost:8000/api/v2/health

# Metrics (if exposed)
curl http://localhost:8000/metrics

# Expected: All return valid data
```

**Success criteria**:
- [ ] Health checks actually work
- [ ] Metrics collection works
- [ ] Alerts trigger correctly (test by causing error)

---

## Phase 2: Fix Automated Tests (Next Week)

### Fix 1: Permissive E2E Assertions

**Current** (test_api_flow.py:62):
```python
# ❌ BAD - accepts success OR failure
assert response.status_code in [200, 422, 500]
```

**Fixed**:
```python
# ✅ GOOD - verifies actual success
assert response.status_code == 200, f"Forecast failed: {response.json()}"
data = response.json()
assert "forecast" in data
assert len(data["forecast"]) > 0
assert data["forecast"][0]["wind_speed"] is not None
```

### Fix 2: Create GRIB Fixtures

**Problem**: Tests skip due to missing GRIB data

**Fix**: Create sample GRIB files in `tests/fixtures/grib/`
```bash
# Option 1: Download sample GRIB
wget https://example.com/sample.grib2 -O tests/fixtures/grib/sample.grib2

# Option 2: Create minimal test GRIB
python scripts/create_test_grib.py tests/fixtures/grib/
```

### Fix 3: Reduce Auto-Skip

**Current**: Tests skip if `MODELS_AVAILABLE=false`

**Fix**: Provide test models/data so tests can run
```bash
# Set environment for testing
export MODELS_AVAILABLE=true
export SENSOR_TESTS_ENABLED=false  # Keep this off (future feature)

# Run tests
pytest tests/ -v --cov=app --cov-report=html
```

---

## Phase 3: Increase Coverage (Next 2 Weeks)

### Target: 80% Coverage (Currently 20%)

**Priority areas** (0% → 80%):

1. **Authentication** (`app/middleware/auth.py`):
   - Test API key validation
   - Test rate limiting
   - Test unauthorized access blocking
   - Target: >80% coverage

2. **Monitoring** (`app/monitoring/`):
   - Test health checks
   - Test metrics collection
   - Test alert triggering
   - Target: >70% coverage

3. **GRIB Systems** (`app/models/grib_cache.py`):
   - Test GRIB download
   - Test GRIB caching
   - Test GRIB parsing
   - Target: >80% coverage

4. **Ensemble Models** (`app/models/ensemble_static.py`):
   - Test model predictions
   - Test weight calculations
   - Test confidence scoring
   - Target: >70% coverage

---

## Phase 4: Enforce Standards (Ongoing)

### Apply Enforcement System

**Create pre-commit hook for VortexV2**:
```bash
# Edit .git/hooks/pre-commit to check for VortexV2 evidence
# If commit message contains "vortex.*ready", require evidence
```

**Evidence template** (`~/.cortex/test_evidence/vortex-*.json`):
```json
{
  "feature_name": "vortex-forecast-api",
  "user_command_tested": true,
  "user_command_output": "curl POST /api/v2/weather/forecast → 200 OK",
  "edge_cases_tested": true,
  "edge_case_results": [
    "Invalid coords: 422 Validation Error",
    "No GRIB data: 500 with clear error",
    "Rate limit: 429 Too Many Requests"
  ],
  "regression_passed": true,
  "regression_results": "Tested: health, nowcast, grib/status - all pass"
}
```

### Coverage Gates

**Block commits if coverage decreases**:
```bash
# In CI/CD or pre-commit
pytest tests/ --cov=app --cov-fail-under=80

# If coverage < 80%: BLOCK
```

---

## Test Evidence Required

Before claiming any VortexV2 feature is "ready" or "production", must have:

1. **API Evidence** (`vortex-forecast-api.json`):
   - Forecast endpoint tested
   - Edge cases tested
   - Regression tests passed

2. **Auth Evidence** (`vortex-auth.json`):
   - API key validation tested
   - Rate limiting tested
   - Unauthorized access blocked

3. **UI Evidence** (`vortex-ui.json`):
   - UI loads without errors
   - User workflows tested
   - Navigation tested

4. **GRIB Evidence** (`vortex-grib.json`):
   - GRIB download tested
   - GRIB caching tested
   - Error handling tested

5. **Monitoring Evidence** (`vortex-monitoring.json`):
   - Health checks tested
   - Metrics collection tested
   - Alerts tested

---

## Success Metrics

### Week 1 (Critical Path)

- [ ] API endpoints verified manually (evidence generated)
- [ ] Auth/rate limiting verified (evidence generated)
- [ ] UI workflows verified (evidence generated)
- [ ] GRIB system verified (evidence generated)
- [ ] Monitoring verified (evidence generated)

**Deliverable**: 5 test evidence files in `~/.cortex/test_evidence/`

### Week 2 (Automated Tests)

- [ ] E2E tests fixed (no more permissive assertions)
- [ ] GRIB fixtures created (tests can run)
- [ ] Auto-skip reduced (<5% of tests)
- [ ] Coverage report generated

**Deliverable**: Test suite runs without skips, clear pass/fail

### Week 4 (Coverage Target)

- [ ] Overall coverage: >80% (currently 20%)
- [ ] Auth coverage: >80% (currently 0%)
- [ ] Monitoring coverage: >70% (currently 0%)
- [ ] GRIB coverage: >80% (currently 0%)

**Deliverable**: Coverage report showing >80% overall

### Ongoing (Enforcement)

- [ ] Pre-commit hook blocks untested claims
- [ ] CI/CD blocks PRs with low coverage
- [ ] Quarterly retesting of all production features

**Deliverable**: Enforcement system prevents future failures

---

## How to Execute

### Step 1: Manual Testing (Today)

```bash
# 1. Start VortexV2 API
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
python app/main.py

# 2. Run critical path tests (see Phase 1 above)
# 3. Document results in evidence generator
python cortex/enforcement/evidence_generator.py vortex-forecast-api

# Answer questions:
# - Did you test the actual API endpoint? yes
# - What was the command and output? curl POST /api/v2/weather/forecast → 200 OK with forecast data
# - Did you test edge cases? yes
# - What edge cases? Invalid coords (422), no GRIB (500), rate limit (429)
# - Did regression tests pass? yes
# - What did you test? health, nowcast, grib/status
```

### Step 2: Fix Automated Tests (This Week)

```bash
# 1. Create GRIB fixtures
mkdir -p tests/fixtures/grib
# Download or create sample GRIB files

# 2. Fix permissive assertions
# Edit tests/e2e/test_api_flow.py
# Change: assert response.status_code in [200, 422, 500]
# To: assert response.status_code == 200

# 3. Run tests
export MODELS_AVAILABLE=true
pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# 4. Check results
open htmlcov/index.html
```

### Step 3: Increase Coverage (Next 2 Weeks)

```bash
# 1. Identify 0% coverage files
pytest tests/ --cov=app --cov-report=term-missing | grep "0%"

# 2. Write tests for critical 0% files
# - app/middleware/auth.py
# - app/monitoring/*.py
# - app/models/grib_cache.py

# 3. Verify coverage increases
pytest tests/ --cov=app --cov-fail-under=80
```

---

## Checklist

### Immediate (Today)

- [x] Audit completed (VORTEXV2_TESTING_AUDIT.md)
- [ ] Manual API test (forecast endpoint)
- [ ] Manual auth test (rate limiting)
- [ ] Manual UI test (streamlit)
- [ ] Generate evidence files (5 total)

### This Week

- [ ] Create GRIB fixtures
- [ ] Fix permissive E2E assertions
- [ ] Reduce auto-skip behavior
- [ ] Run full test suite with coverage
- [ ] Document skip count

### Next 2 Weeks

- [ ] Write tests for auth (0% → >80%)
- [ ] Write tests for monitoring (0% → >70%)
- [ ] Write tests for GRIB (0% → >80%)
- [ ] Increase overall coverage (20% → >80%)

### Ongoing

- [ ] Apply enforcement to VortexV2
- [ ] Set up coverage gates
- [ ] Quarterly retesting schedule

---

## Contact

Questions? Check:
- `VORTEXV2_TESTING_AUDIT.md` - Detailed audit findings
- `TESTING_CHECKLIST.md` - Universal testing standards
- `ENFORCEMENT_VERIFIED.md` - Proof enforcement works

**Enforcement prevents this**: Cannot claim "ready" without evidence.

---

**Plan Status**: ⏭️ READY TO EXECUTE
**Next Action**: Manual testing of critical paths (Phase 1)
**Timeline**: 4 weeks to 80% coverage with enforcement
