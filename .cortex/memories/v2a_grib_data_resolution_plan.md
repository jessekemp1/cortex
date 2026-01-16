# V2a GRIB Data Resolution Plan

**Created**: 2026-01-16
**Status**: Phase 1 recommended for 9am deadline
**Priority**: HIGH (blocks V2a endpoint testing)

---

## Problem Statement

**Symptom**: V2a endpoint returns 200 but 0 forecast points
- Tests fail: `test_v2a_basic_request` expects forecast data
- Root cause: Current GRIB forecasts unavailable in test environment
- Cloud GRIB sources (Azure/AWS/Google) have 2-3 day delays for free tier

**What's Working**:
- ✅ V2a endpoint infrastructure (returns 200, correct structure)
- ✅ Field selection logic (ECMWF for wind_speed, GFS for wind_direction)
- ✅ Integration tests pass for metadata/structure (6/8 tests)
- ✅ Batch validation running (historical data download)
- ✅ Mock GRIB fixture infrastructure exists in `tests/fixtures/grib_data.py`

**What's Missing**:
1. **Current forecast GRIB data** - Endpoint needs today's 00Z/12Z model runs
2. **Test data pipeline** - Tests should use fixtures or cached GRIB
3. **Production GRIB cache** - Enable offline development/testing

---

## Solution: Hybrid 3-Phase Approach

### Phase 1: Mock Injection (1-2 hours) ← **RECOMMENDED FOR 9AM DEADLINE**

**Goal**: Get tests passing with mock data

**Implementation**:
1. Create `/tests/fixtures/v2a_grib_mocks.py` with realistic forecast data
2. Patch `HerbieECMWFLoader.fetch_forecast_at_location` and `GFSLoader.fetch_complete`
3. Apply mocks via `@pytest.fixture(autouse=True)` in V2a tests
4. Validate field selection logic with known inputs

**Critical Files**:
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/tests/fixtures/v2a_grib_mocks.py` (NEW)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/tests/integration/test_v2a_endpoint.py` (MODIFY)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/tests/conftest.py` (MODIFY)

**Success Criteria**:
- ✅ All 8 V2a tests pass (currently 6/8)
- ✅ test_v2a_basic_request returns forecast points
- ✅ Field selection validated (ECMWF for wind_speed, GFS for wind_direction)
- ✅ No production code changes

**Tradeoffs**:
- ✅ Fast (1-2 hours)
- ✅ No production impact
- ⚠️ Tests validate logic only, not actual GRIB integration
- ✅ Enables 9am deadline

---

### Phase 2: GRIB Cache Layer (4-6 hours) ← **THIS WEEK**

**Goal**: Enable development/testing with real GRIB data offline

**Implementation**:
1. Create `GRIBCacheManager` class
   - Check cache: `/data/gribs/current/{model}_{run_time}_{fxx}.grib2`
   - TTL: 6 hours (model run cycle)
   - Cleanup: Remove files >24h old
2. Modify loaders to check cache before Herbie download
   - `HerbieECMWFLoader.fetch_forecast_at_location` → cache layer
   - `GFSLoader.fetch_complete` → cache layer
3. Create manual download script: `scripts/download_current_gribs.py`
   - Downloads today's 00Z and 12Z runs
   - Populates cache for development
4. Add config flags:
   - `GRIB_CACHE_ENABLED=true`
   - `GRIB_CACHE_DIR=/data/gribs/current/`
   - `GRIB_CACHE_TTL=6h`

**Critical Files**:
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/weather/grib_cache_manager.py` (NEW)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/weather/herbie_ecmwf.py:281` (MODIFY - add cache check)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/weather/gfs_loader.py:356` (MODIFY - add cache check)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/scripts/download_current_gribs.py` (NEW)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/utils/config.py` (MODIFY - add GRIB cache config)

**Success Criteria**:
- ✅ Manual download script works
- ✅ Cache hit reduces latency 15s → <1s
- ✅ Tests use real GRIB data structure
- ✅ Works offline after initial download

**Tradeoffs**:
- ✅ Full GRIB integration testing
- ✅ Useful for development
- ⚠️ Requires manual cache population initially
- ⚠️ Cache invalidation complexity

---

### Phase 3: Auto-refresh Pipeline (2-3 days) ← **NEXT SPRINT**

**Goal**: Production-ready GRIB fetching with auto-refresh

**Implementation**:
1. GRIB Scheduler Service
   - Cron job: download ECMWF/GFS every 6 hours
   - Target: 00Z and 12Z runs, forecast hours 0-72
   - Retry logic with exponential backoff
2. Cache Management
   - Auto-cleanup old files (>24h)
   - Health checks for data freshness
3. Monitoring & Alerts
   - Track download success rate
   - Alert if data >12 hours old
   - Metrics: cache hit rate, download latency

**Critical Files**:
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/scheduler.py` (MODIFY - add GRIB task)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/core/weather/grib_automation.py` (NEW)
- `/Users/jesse.kemp/Dev/Vortex/VortexV2/app/monitoring/grib_health.py` (NEW)

**Success Criteria**:
- ✅ Auto-refresh every 6 hours
- ✅ 99% data freshness (no stale data >12h)
- ✅ Production-ready for live forecasts
- ✅ Monitoring dashboard

**Tradeoffs**:
- ✅ Production-grade solution
- ✅ Enables live V2a forecasts
- ⚠️ Complex (scheduler, error handling, monitoring)
- ⚠️ Requires significant testing

---

## Comparison Matrix

| Criteria | Phase 1 (Mock) | Phase 2 (Cache) | Phase 3 (Pipeline) |
|----------|----------------|------------------|---------------------|
| **Time to implement** | 1-2 hours ✅ | 4-6 hours | 2-3 days |
| **9am deadline** | YES ✅ | Maybe | NO |
| **Test validity** | Logic only | Full integration ✅ | Production-grade ✅ |
| **Production ready** | NO | Partial | YES ✅ |
| **Maintenance** | Low ✅ | Medium | High |
| **Offline testing** | YES ✅ | YES ✅ | Partial |

---

## Mock Data Structure (Phase 1)

```python
# ECMWF mock response format
{
    "run_time": datetime(2026, 1, 16, 12, 0),  # Today's 12Z run
    "valid_time": datetime(2026, 1, 16, 18, 0),  # 6 hours ahead
    "forecast_hour": 6,
    "latitude": 41.49,
    "longitude": -70.67,
    "wind_speed_kts": 15.2,
    "wind_speed_ms": 7.8,
    "wind_direction_deg": 225.0,
    "wind_gust_kts": 22.5,
    "pressure_hpa": 1013.2,
    "wave_height_m": 1.8,
    "wave_period_s": 7.2,
    "wave_direction_deg": 200.0,
    "swell_height_m": 1.2,
    "swell_period_s": 10.5,
    "swell_direction_deg": 190.0,
}

# GFS mock response format (similar structure, different values)
{
    "run_time": datetime(2026, 1, 16, 12, 0),
    "valid_time": datetime(2026, 1, 16, 18, 0),
    "forecast_hour": 6,
    "latitude": 41.49,
    "longitude": -70.67,
    "wind_speed_kts": 17.8,  # Different from ECMWF
    "wind_direction_deg": 230.0,  # Different
    # ... all fields with GFS values
}
```

**Expected Field Selection** (from FIELD_WINNERS):
- wind_speed: 15.2 kt (from ECMWF)
- wind_direction: 230.0° (from GFS)
- wave_height: 1.8 m (from ECMWF)
- pressure: 1013.2 hPa (from ECMWF)

---

## Risk Mitigation

**Phase 1 Risks**:
- Mock data diverges from production format
  - **Mitigation**: Copy exact field names from loader output
- Tests pass but production fails with real data
  - **Mitigation**: Accept for now, Phase 2 addresses with real GRIB

**Phase 2 Risks**:
- Download fails in CI/test environment
  - **Mitigation**: Graceful fallback to Phase 1 mocks
- Cache corruption
  - **Mitigation**: Validation on read, delete corrupt files

**Phase 3 Risks**:
- Scheduler fails silently
  - **Mitigation**: Health checks + monitoring alerts
- Disk space exhaustion
  - **Mitigation**: Aggressive cleanup + alerts at 80% capacity

---

## Batch Validation Status

**Current State** (as of 2026-01-16 15:20):
- Wave 1: 50% complete (1/2 tasks)
  - ✅ Sprint 1: 7-day validation running (45 min ETA)
  - 🔄 Sprint 2: API smoke tests (5 min)
- Wave 2: 0% (blocked on Wave 1)
- Wave 3: 0% (blocked on Wave 2)
- Wave 4: 0% (blocked on Wave 3)

**Note**: Batch validation downloads HISTORICAL data (7 days ago) not current forecasts. This won't solve the test data issue but will provide empirical field winners for production refinement.

---

## Next Steps

**Immediate (for 9am deadline)**:
1. Implement Phase 1 mock injection (1-2 hours)
2. Verify all 8 V2a tests pass
3. Document mock data source in tests

**This Week**:
1. Implement Phase 2 GRIB cache layer
2. Create manual download script
3. Update development documentation

**Next Sprint**:
1. Design Phase 3 auto-refresh pipeline
2. Implement scheduler + monitoring
3. Deploy to production

---

## References

- Plan Agent ID: `ac19d27` (resume for continuation)
- V2a Implementation Plan: `.claude/plans/tingly-toasting-cray.md`
- Batch Orchestration Memory: `cortex/.cortex/memories/batch_orchestration_system.md`
- Existing Mock Fixtures: `Vortex/VortexV2/tests/fixtures/grib_data.py`
- V2a Endpoint: `Vortex/VortexV2/app/api/v2/weather.py:959-1129`
