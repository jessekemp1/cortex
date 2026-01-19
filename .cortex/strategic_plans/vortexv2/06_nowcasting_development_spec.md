# VortexV2 Nowcasting System - Development Specification

**Created**: 2026-01-18
**Status**: Complete technical specification
**Purpose**: Detailed implementation requirements for Phase 1 MVP

---

## 1. API Specification

### 1.1 REST Endpoints

#### POST /api/v2/nowcast/precipitation

**Purpose**: Get precipitation nowcast for a specific location

**Request Schema**:
```python
from pydantic import BaseModel, Field
from typing import Optional

class PrecipNowcastRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    lead_minutes: int = Field(60, ge=5, le=120, description="Forecast lead time in minutes")
    ensemble_size: int = Field(10, ge=1, le=20, description="Number of ensemble members")
    include_uncertainty: bool = Field(True, description="Include uncertainty quantiles")

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 43.615,
                "longitude": -83.895,
                "lead_minutes": 60,
                "ensemble_size": 10,
                "include_uncertainty": True
            }
        }
```

**Response Schema**:
```python
from datetime import datetime
from typing import List, Optional

class PrecipNowcastTimestep(BaseModel):
    """Single timestep forecast"""
    valid_time: datetime
    lead_minutes: int
    precip_rate_mm_h: float = Field(..., description="Mean precipitation rate (mm/h)")
    precip_rate_p10: Optional[float] = Field(None, description="10th percentile (mm/h)")
    precip_rate_p50: Optional[float] = Field(None, description="50th percentile (mm/h)")
    precip_rate_p90: Optional[float] = Field(None, description="90th percentile (mm/h)")
    probability_gt_1mm: Optional[float] = Field(None, description="Probability > 1mm/h")
    probability_gt_5mm: Optional[float] = Field(None, description="Probability > 5mm/h")

class PrecipNowcastResponse(BaseModel):
    """Complete nowcast response"""
    location: dict = Field(..., description="Requested location")
    forecast_time: datetime = Field(..., description="Analysis time (nowcast initialized)")
    radar_age_minutes: float = Field(..., description="Age of radar data in minutes")
    quality_score: float = Field(..., ge=0, le=1, description="Data quality score (0-1)")
    timesteps: List[PrecipNowcastTimestep]
    metadata: dict = Field(..., description="Processing metadata")
```

#### GET /api/v2/nowcast/precipitation/stream

**Purpose**: Server-Sent Events stream for real-time forecast updates

**Implementation**:
```python
from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter
import asyncio

@router.get("/precipitation/stream")
async def stream_precipitation_nowcast(
    latitude: float,
    longitude: float,
    lead_minutes: int = 60,
    update_interval: int = 300
):
    async def event_generator():
        while True:
            try:
                nowcast = await get_cached_nowcast(latitude, longitude, lead_minutes)
                if nowcast:
                    yield {"event": "nowcast", "data": nowcast.json()}
                await asyncio.sleep(30)
                yield {"event": "heartbeat", "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})}
                await asyncio.sleep(update_interval - 30)
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"error": str(e)})}
                await asyncio.sleep(update_interval)

    return EventSourceResponse(event_generator())
```

---

## 2. Database Schema

### 2.1 TimescaleDB Tables

```sql
-- Core verification data (hypertable)
CREATE TABLE nowcast_verification (
    time TIMESTAMPTZ NOT NULL,
    forecast_time TIMESTAMPTZ NOT NULL,
    lead_minutes INTEGER NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    forecast_precip_rate REAL,
    observed_precip_rate REAL,
    threshold_mm_h REAL,
    hit BOOLEAN,
    false_alarm BOOLEAN,
    miss BOOLEAN,
    correct_negative BOOLEAN,
    ensemble_spread REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT create_hypertable('nowcast_verification', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_verification_forecast_time ON nowcast_verification (forecast_time);
CREATE INDEX idx_verification_lead_minutes ON nowcast_verification (lead_minutes);
SELECT add_retention_policy('nowcast_verification', INTERVAL '90 days');
```

### 2.2 Continuous Aggregates

```sql
-- Hourly skill scores
CREATE MATERIALIZED VIEW nowcast_skill_scores_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    lead_minutes,
    threshold_mm_h,
    SUM(CASE WHEN hit THEN 1 ELSE 0 END)::REAL /
        NULLIF(SUM(CASE WHEN hit OR false_alarm OR miss THEN 1 ELSE 0 END), 0) AS csi,
    AVG(ABS(forecast_precip_rate - observed_precip_rate)) AS mae,
    COUNT(*) AS sample_count
FROM nowcast_verification
GROUP BY hour, lead_minutes, threshold_mm_h;
```

---

## 3. Core Algorithms

### 3.1 PySTEPS Pipeline

```python
class PySTEPSNowcastEngine:
    """Core PySTEPS nowcasting pipeline"""

    async def generate_nowcast(
        self,
        radar_grids: List[np.ndarray],
        timestamps: List[datetime],
        lead_minutes: int = 120
    ) -> xr.Dataset:
        """Generate probabilistic precipitation nowcast"""

        # STEP 1: Convert to reflectivity (dBR)
        dbr_grids, metadata = self._to_reflectivity(radar_grids)

        # STEP 2: Compute motion field (Lucas-Kanade)
        motion_field = self._compute_motion(dbr_grids, timestamps)

        # STEP 3: Cascade decomposition
        cascade_decomp = self._decompose_cascade(dbr_grids[-1])

        # STEP 4: Generate ensemble
        ensemble_nowcasts = self._generate_ensemble(
            dbr_grids[-1],
            motion_field,
            cascade_decomp,
            lead_minutes
        )

        # STEP 5: Convert back to mm/h
        precip_ensemble = self._to_precipitation(ensemble_nowcasts, metadata)

        # STEP 6: Package into xarray Dataset
        dataset = self._create_dataset(precip_ensemble, timestamps[-1], lead_minutes)

        return dataset
```

---

## 4. Caching Strategy

### 4.1 Multi-Tier Architecture

```
Tier 1: In-Memory (LRU) → 2min TTL, point forecasts
Tier 2: SQLite (Disk)   → 5min TTL, gridded nowcasts
Tier 3: Generate Fresh  → PySTEPS pipeline
```

### 4.2 Implementation

```python
class NowcastCacheService:
    """Multi-tier caching for nowcast data

    Security Note: Uses pickle for xarray serialization (internal cache only).
    Never deserialize untrusted pickle data.
    """

    def __init__(self, db_path: str = "data/nowcast_cache.db"):
        self.db_path = db_path
        self._init_cache_db()

    @lru_cache(maxsize=100)
    def get_point_forecast(
        self,
        latitude: float,
        longitude: float,
        lead_minutes: int,
        cache_key: str
    ) -> Optional[dict]:
        """Tier 1: In-memory LRU cache"""
        return None

    def get_gridded_nowcast(self, init_time: datetime) -> Optional[xr.Dataset]:
        """Tier 2: SQLite disk cache"""
        # Query and deserialize from SQLite
        # WARNING: Only deserializes internally-generated pickle data
        pass

    def set_gridded_nowcast(self, init_time: datetime, dataset: xr.Dataset, ttl_minutes: int = 5):
        """Store gridded nowcast in SQLite"""
        # Serialize xarray Dataset using pickle (internal use only)
        grid_data = pickle.dumps(dataset)
        # Store in SQLite with expiration
        pass
```

---

## 5. Monitoring

### 5.1 Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
nowcast_requests_total = Counter(
    'vortex_nowcast_requests_total',
    'Total nowcast API requests',
    ['endpoint', 'status']
)

nowcast_request_duration_seconds = Histogram(
    'vortex_nowcast_request_duration_seconds',
    'Nowcast request duration',
    ['endpoint'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# Data freshness
nowcast_radar_age_minutes = Gauge(
    'vortex_nowcast_radar_age_minutes',
    'Age of most recent radar data',
    ['station']
)

# Skill scores
nowcast_csi_score = Gauge(
    'vortex_nowcast_csi_score',
    'Critical Success Index',
    ['lead_minutes', 'threshold_mm_h']
)

# Cache metrics
nowcast_cache_hits_total = Counter('vortex_nowcast_cache_hits_total', 'Cache hits', ['tier'])
nowcast_cache_misses_total = Counter('vortex_nowcast_cache_misses_total', 'Cache misses', ['tier'])
```

### 5.2 Alerting Rules

```yaml
groups:
  - name: nowcasting_alerts
    rules:
      - alert: NowcastRadarStale
        expr: vortex_nowcast_radar_age_minutes > 15
        for: 5m
        severity: critical

      - alert: NowcastAPISlowP95
        expr: histogram_quantile(0.95, vortex_nowcast_request_duration_seconds) > 5.0
        for: 5m
        severity: critical

      - alert: NowcastCSIDegraded
        expr: vortex_nowcast_csi_score{lead_minutes="60"} < 0.30
        for: 1h
        severity: warning
```

---

## 6. Testing Requirements

### 6.1 Unit Tests (>90% Coverage)

```python
# tests/unit/nowcast/test_pysteps_engine.py
class TestPySTEPSNowcastEngine:
    def test_to_reflectivity_conversion(self, engine, sample_radar_grids):
        """Test precipitation to dBR conversion"""
        dbr_grids, metadata = engine._to_reflectivity(sample_radar_grids)
        assert len(dbr_grids) == 2
        assert metadata['transform'] == 'dB'

    @pytest.mark.asyncio
    async def test_generate_nowcast_integration(self, engine, sample_radar_grids):
        """Integration test for full pipeline"""
        dataset = await engine.generate_nowcast(sample_radar_grids, timestamps, lead_minutes=60)
        assert dataset.dims['member'] == 10
        assert dataset.dims['time'] == 12
```

### 6.2 Performance Tests

```python
# tests/performance/test_nowcast_latency.py
@pytest.mark.asyncio
async def test_generation_latency_target(self, engine):
    """Verify generation <30s for 120-minute forecast"""
    start = time.time()
    dataset = await engine.generate_nowcast(radar_data, timestamps, lead_minutes=120)
    duration = time.time() - start
    assert duration < 30.0, f"Generation took {duration:.1f}s (target: <30s)"
```

---

## 7. Dependencies

```txt
# requirements.txt additions

# Nowcasting - Phase 1
pysteps>=1.8.0              # Radar nowcasting
pyart>=1.15.0               # Radar processing
s3fs>=2023.6.0              # S3 interface
boto3>=1.28.0               # AWS SDK
nexradaws>=2.0.0            # NEXRAD utilities
cartopy>=0.21.0             # Projections
xarray>=2023.1.0            # Arrays
sse-starlette>=1.6.0        # Server-Sent Events
```

---

## 8. File Structure

```
app/
├── core/
│   ├── nowcast/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── data/
│   │   │   ├── nexrad_downloader.py
│   │   │   ├── mrms_downloader.py
│   │   │   └── radar_preprocessor.py
│   │   ├── engines/
│   │   │   ├── pysteps_engine.py
│   │   │   └── grid_manager.py
│   │   ├── services/
│   │   │   ├── cache_service.py
│   │   │   └── verification_service.py
│   │   └── utils/
│   │       └── geo_utils.py
│   └── scheduler.py (MODIFY)
├── api/
│   └── v2/
│       └── nowcast.py (NEW)
└── main.py (MODIFY)
```

---

**Next**: Document 3 - Full Implementation Plan (Golden Spec)

**Document Version**: 1.0
**Last Updated**: 2026-01-18
**Status**: ✅ Complete
