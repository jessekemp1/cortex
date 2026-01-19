# VortexV2 Nowcasting System - Full Implementation Plan

**Created**: 2026-01-18
**Status**: Ready for execution
**Timeline**: 6 weeks (Phase 1 MVP)
**Methodology**: Golden Spec (dependency-ordered tasks)

---

## Overview

This document provides a **complete, dependency-ordered task breakdown** for implementing the VortexV2 nowcasting system Phase 1 MVP. Each task is designed to be:

- **Atomic**: Can be completed in a single focused session
- **Testable**: Has clear acceptance criteria
- **Ordered**: Dependencies make the build order obvious
- **Estimable**: Relative effort (Small/Medium/Large)

**Total Tasks**: 38 (NOW-001 through NOW-038)
**Timeline**: 6 weeks @ 40 hours/week = 240 hours
**Critical Path**: NOW-001 → NOW-005 → NOW-006 → NOW-009 → NOW-011

---

## Task List (Dependency Order)

### Sprint 1: Foundation (Week 1)

#### NOW-001: Create nowcast module structure
**Dependencies**: None
**Effort**: Small (2h)
**Priority**: P0 (Critical Path)

**Description**: Create directory structure and base files for nowcast module

**Files to Create**:
- `app/core/nowcast/__init__.py`
- `app/core/nowcast/config.py`
- `app/core/nowcast/data/__init__.py`
- `app/core/nowcast/engines/__init__.py`
- `app/core/nowcast/services/__init__.py`
- `app/core/nowcast/utils/__init__.py`

**Acceptance Criteria**:
- [ ] All directories created
- [ ] `__init__.py` files import correctly
- [ ] `config.py` has `NowcastConfig` class with defaults
- [ ] Module imports without errors: `from app.core.nowcast import config`

**Code Structure**:
```python
# app/core/nowcast/config.py
from pydantic import BaseSettings

class NowcastConfig(BaseSettings):
    # NEXRAD Configuration
    NEXRAD_STATIONS: list = ["KDTX", "KAPX", "KGRB", "KMQT"]
    NEXRAD_S3_BUCKET: str = "noaa-nexrad-level2"

    # PySTEPS Configuration
    PYSTEPS_MOTION: str = "lucaskanade"
    PYSTEPS_CASCADE_LEVELS: int = 8
    PYSTEPS_EXTRAP_METHOD: str = "semilagrangian"
    PYSTEPS_NOISE_METHOD: str = "nonparametric"
    PYSTEPS_ENSEMBLE_SIZE: int = 10

    # Forecast Configuration
    MAX_LEAD_MINUTES: int = 120
    TIMESTEP_MINUTES: int = 5
    MAX_RADAR_AGE_MINUTES: int = 10

    # Cache Configuration
    CACHE_DIR: str = "data/nowcast/cache"
    RADAR_CACHE_DIR: str = "data/nowcast/radar"
    CACHE_TTL_MINUTES: int = 5

    class Config:
        env_file = ".env"
        env_prefix = "NOWCAST_"
```

---

#### NOW-002: Install nowcasting dependencies
**Dependencies**: NOW-001
**Effort**: Small (1h)
**Priority**: P0

**Description**: Add PySTEPS and related dependencies to requirements.txt

**Files to Modify**:
- `requirements.txt`

**Acceptance Criteria**:
- [ ] All dependencies added to requirements.txt
- [ ] Virtual environment created: `python -m venv venv`
- [ ] Dependencies install without errors: `pip install -r requirements.txt`
- [ ] PySTEPS imports successfully: `python -c "import pysteps"`

**Dependencies to Add**:
```txt
# Nowcasting - Phase 1
pysteps>=1.8.0
pyart>=1.15.0
wradlib>=2.0.0
s3fs>=2023.6.0
boto3>=1.28.0
nexradaws>=2.0.0
cartopy>=0.21.0
pyproj>=3.5.0
rasterio>=1.3.0
xarray>=2023.1.0
dask[complete]>=2023.1.0
zarr>=2.14.0
sse-starlette>=1.6.0
```

---

#### NOW-003: Implement NEXRAD downloader
**Dependencies**: NOW-002
**Effort**: Large (8h)
**Priority**: P0 (Critical Path)

**Description**: Build S3 downloader for NEXRAD Level-II radar data with caching

**Files to Create**:
- `app/core/nowcast/data/nexrad_downloader.py`
- `tests/unit/nowcast/data/test_nexrad_downloader.py`

**Acceptance Criteria**:
- [ ] Can list available NEXRAD files from S3
- [ ] Can download latest scan for a station (KDTX)
- [ ] Downloaded files cached locally (7-day retention)
- [ ] Exponential backoff on S3 rate limits (2s, 4s, 8s, 16s)
- [ ] Unit tests pass with mocked S3 responses
- [ ] Integration test downloads real file from S3

**Code Structure**:
```python
# app/core/nowcast/data/nexrad_downloader.py
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import time

class NEXRADDownloader:
    def __init__(self, cache_dir: str = "data/nowcast/radar"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = "noaa-nexrad-level2"
        self.s3_client = boto3.client('s3', region_name='us-east-1')

    async def get_latest_scan(
        self,
        station: str,
        max_age_minutes: int = 10
    ) -> Optional[Path]:
        """Get most recent volume scan for a station"""

        # Check cache first
        cached_file = self._get_cached_scan(station, max_age_minutes)
        if cached_file:
            return cached_file

        # Download from S3
        return await self._download_latest(station)

    def _get_cached_scan(self, station: str, max_age_minutes: int) -> Optional[Path]:
        """Check local cache for recent scan"""
        station_dir = self.cache_dir / station
        if not station_dir.exists():
            return None

        # Find most recent file
        files = sorted(station_dir.glob("*.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            latest = files[0]
            age_minutes = (datetime.now().timestamp() - latest.stat().st_mtime) / 60
            if age_minutes <= max_age_minutes:
                return latest

        return None

    async def _download_latest(self, station: str) -> Optional[Path]:
        """Download latest scan from S3 with exponential backoff"""

        # List recent files (last 30 minutes)
        prefix = self._build_prefix(station, datetime.utcnow())

        retries = 0
        max_retries = 4
        backoff_seconds = 2

        while retries < max_retries:
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.s3_bucket,
                    Prefix=prefix,
                    MaxKeys=10
                )

                if 'Contents' not in response:
                    return None

                # Get most recent file
                latest_key = sorted(response['Contents'], key=lambda x: x['LastModified'])[-1]['Key']

                # Download file
                local_path = self.cache_dir / station / Path(latest_key).name
                local_path.parent.mkdir(parents=True, exist_ok=True)

                self.s3_client.download_file(
                    self.s3_bucket,
                    latest_key,
                    str(local_path)
                )

                return local_path

            except ClientError as e:
                if e.response['Error']['Code'] == 'SlowDown':
                    # S3 rate limiting
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    retries += 1
                else:
                    raise

        return None

    def _build_prefix(self, station: str, dt: datetime) -> str:
        """Build S3 prefix for a station and date"""
        return f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}/{station}/"

    def cleanup_old_files(self, retention_days: int = 7):
        """Remove cached files older than retention period"""
        cutoff = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff.timestamp()

        for file in self.cache_dir.rglob("*.gz"):
            if file.stat().st_mtime < cutoff_timestamp:
                file.unlink()
```

---

#### NOW-004: Implement radar preprocessor
**Dependencies**: NOW-003
**Effort**: Medium (6h)
**Priority**: P0

**Description**: Quality control and preprocessing for NEXRAD Level-II data

**Files to Create**:
- `app/core/nowcast/data/radar_preprocessor.py`
- `tests/unit/nowcast/data/test_radar_preprocessor.py`

**Acceptance Criteria**:
- [ ] Can read NEXRAD Level-II file using Py-ART
- [ ] Extracts base reflectivity field (dBZ)
- [ ] Converts to precipitation rate (mm/h) using Z-R relationship
- [ ] Applies quality control (clutter filter, dealiasing)
- [ ] Generates 2D grid on Cartesian projection
- [ ] Unit tests with sample NEXRAD file

**Code Structure**:
```python
# app/core/nowcast/data/radar_preprocessor.py
import pyart
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

class RadarPreprocessor:
    def __init__(self, grid_shape: tuple = (256, 256), grid_extent_km: float = 128.0):
        self.grid_shape = grid_shape
        self.grid_extent_km = grid_extent_km

    def process_nexrad_file(self, file_path: Path) -> Optional[Tuple[np.ndarray, dict]]:
        """Process NEXRAD Level-II file to precipitation grid"""

        # Read radar file
        radar = pyart.io.read(str(file_path))

        # Extract base reflectivity
        ref_field = radar.fields.get('reflectivity')
        if ref_field is None:
            return None

        # Quality control
        ref_data = self._apply_quality_control(ref_field['data'])

        # Convert to precipitation rate (Z-R relationship)
        precip_rate = self._dbz_to_precip_rate(ref_data)

        # Grid to Cartesian
        grid, metadata = self._grid_to_cartesian(radar, precip_rate)

        return grid, metadata

    def _apply_quality_control(self, ref_data: np.ma.MaskedArray) -> np.ma.MaskedArray:
        """Apply quality control filters"""

        # Mask values below threshold (clutter)
        ref_data = np.ma.masked_less(ref_data, 5.0)  # < 5 dBZ is noise

        # Mask very high values (artifacts)
        ref_data = np.ma.masked_greater(ref_data, 70.0)  # > 70 dBZ is unlikely

        return ref_data

    def _dbz_to_precip_rate(self, dbz: np.ma.MaskedArray) -> np.ma.MaskedArray:
        """Convert reflectivity (dBZ) to precipitation rate (mm/h)

        Uses Marshall-Palmer Z-R relationship: Z = 200 * R^1.6
        Inverted: R = (Z / 200)^(1/1.6)
        """

        # Convert dBZ to Z (linear)
        z_linear = 10.0 ** (dbz / 10.0)

        # Apply Z-R relationship
        precip_rate = (z_linear / 200.0) ** (1.0 / 1.6)

        return precip_rate

    def _grid_to_cartesian(
        self,
        radar: pyart.core.Radar,
        data: np.ma.MaskedArray
    ) -> Tuple[np.ndarray, dict]:
        """Grid radar data to Cartesian coordinates"""

        # Create grid
        grid = pyart.map.grid_from_radars(
            (radar,),
            grid_shape=self.grid_shape,
            grid_limits=(
                (-self.grid_extent_km * 1000, self.grid_extent_km * 1000),
                (-self.grid_extent_km * 1000, self.grid_extent_km * 1000),
                (0, 10000)  # Vertical extent (0-10km)
            ),
            fields=['reflectivity']
        )

        # Extract lowest elevation slice
        grid_2d = grid.fields['reflectivity']['data'][0, :, :].filled(0.0)

        metadata = {
            'projection': grid.projection,
            'x_coords': grid.x['data'],
            'y_coords': grid.y['data'],
            'radar_lat': radar.latitude['data'][0],
            'radar_lon': radar.longitude['data'][0]
        }

        return grid_2d, metadata
```

---

### Sprint 2: PySTEPS Engine (Week 2)

#### NOW-005: Implement PySTEPS nowcast engine
**Dependencies**: NOW-004
**Effort**: X-Large (12h)
**Priority**: P0 (Critical Path)

**Description**: Core PySTEPS pipeline for optical flow nowcasting

**Files to Create**:
- `app/core/nowcast/engines/pysteps_engine.py`
- `tests/unit/nowcast/engines/test_pysteps_engine.py`

**Acceptance Criteria**:
- [ ] Can compute Lucas-Kanade motion field from 2 radar grids
- [ ] Can decompose field into 8 cascade levels
- [ ] Can generate 10-member ensemble nowcast
- [ ] Output is xarray Dataset with correct dimensions
- [ ] Unit tests with synthetic data (moving Gaussian blob)
- [ ] Integration test with real NEXRAD data

**Reference**: See Document 06 (Development Spec) Section 3.1 for complete implementation

---

#### NOW-006: Implement grid point extractor
**Dependencies**: NOW-005
**Effort**: Medium (6h)
**Priority**: P0 (Critical Path)

**Description**: Extract point forecasts from gridded nowcasts

**Files to Create**:
- `app/core/nowcast/engines/grid_manager.py`
- `tests/unit/nowcast/engines/test_grid_manager.py`

**Acceptance Criteria**:
- [ ] Can convert lat/lon to grid coordinates (pyproj)
- [ ] Can extract time series at a point (nearest neighbor)
- [ ] Can compute ensemble statistics (mean, p10, p50, p90)
- [ ] Can compute exceedance probabilities (>1mm/h, >5mm/h)
- [ ] Unit tests verify coordinate transformations
- [ ] Integration test with real nowcast grid

**Reference**: See Document 06 Section 3.2

---

#### NOW-007: Add nowcast scheduler jobs
**Dependencies**: NOW-005
**Effort**: Medium (4h)
**Priority**: P1

**Description**: Integrate nowcast generation into VortexScheduler

**Files to Modify**:
- `app/core/scheduler.py`

**Acceptance Criteria**:
- [ ] `_setup_nowcast_jobs()` method added
- [ ] NEXRAD download job runs every 5 minutes
- [ ] Nowcast generation job runs every 5 minutes
- [ ] Jobs have proper error handling and logging
- [ ] Scheduler starts without errors
- [ ] Jobs execute on schedule (verify with logs)

**Code Structure**:
```python
# app/core/scheduler.py (additions)
from app.core.nowcast.data.nexrad_downloader import NEXRADDownloader
from app.core.nowcast.engines.pysteps_engine import PySTEPSNowcastEngine

class VortexScheduler:
    def __init__(self):
        # ... existing init ...
        self.nexrad_downloader = NEXRADDownloader()
        self.nowcast_engine = PySTEPSNowcastEngine()

    def _setup_jobs(self):
        self._setup_forecast_jobs()
        self._setup_validation_jobs()
        self._setup_nowcast_jobs()  # NEW

    def _setup_nowcast_jobs(self):
        """Setup nowcast generation jobs"""

        # NEXRAD download every 5 minutes
        self.scheduler.add_job(
            self.nowcast_download_radar,
            trigger=IntervalTrigger(minutes=5),
            id="nowcast_radar_download",
            max_instances=1
        )

        # Nowcast generation every 5 minutes (offset by 2 min)
        self.scheduler.add_job(
            self.nowcast_generate_forecast,
            trigger=IntervalTrigger(minutes=5, start_date=datetime.now() + timedelta(minutes=2)),
            id="nowcast_generate",
            max_instances=1,
            misfire_grace_time=120
        )

    async def nowcast_download_radar(self):
        """Download latest NEXRAD scans"""
        try:
            for station in ["KDTX", "KAPX"]:
                await self.nexrad_downloader.get_latest_scan(station)
        except Exception as e:
            logger.error(f"NEXRAD download failed: {e}")

    async def nowcast_generate_forecast(self):
        """Generate nowcast from latest radar"""
        try:
            # Get latest scans
            # Run PySTEPS
            # Cache result
            pass  # Implementation in NOW-011
        except Exception as e:
            logger.error(f"Nowcast generation failed: {e}")
```

---

### Sprint 3: API Endpoint (Week 3)

#### NOW-008: Define API request/response models
**Dependencies**: NOW-006
**Effort**: Small (3h)
**Priority**: P0

**Description**: Pydantic models for nowcast API

**Files to Modify**:
- `app/api/v2/models.py`

**Acceptance Criteria**:
- [ ] `PrecipNowcastRequest` model with validation
- [ ] `PrecipNowcastTimestep` model
- [ ] `PrecipNowcastResponse` model
- [ ] `NowcastStatusResponse` model
- [ ] Models have OpenAPI examples
- [ ] Validation tests pass (invalid lat/lon, negative lead time)

**Reference**: See Document 06 Section 1.1

---

#### NOW-009: Implement nowcast API router
**Dependencies**: NOW-008
**Effort**: Large (8h)
**Priority**: P0 (Critical Path)

**Description**: FastAPI router for nowcast endpoints

**Files to Create**:
- `app/api/v2/nowcast.py`
- `tests/integration/nowcast/test_api_endpoints.py`

**Acceptance Criteria**:
- [ ] `POST /api/v2/nowcast/precipitation` endpoint works
- [ ] `GET /api/v2/nowcast/precipitation/stream` SSE stream works
- [ ] `GET /api/v2/nowcast/status` endpoint works
- [ ] Error handling for stale radar data (503)
- [ ] Error handling for invalid coordinates (400)
- [ ] Integration tests pass (mocked cache)

**Code Structure**:
```python
# app/api/v2/nowcast.py
from fastapi import APIRouter, HTTPException, status
from app.api.v2.models import PrecipNowcastRequest, PrecipNowcastResponse
from app.core.nowcast.services.cache_service import NowcastCacheService

router = APIRouter(prefix="/nowcast", tags=["Nowcast"])
cache_service = NowcastCacheService()

@router.post("/precipitation", response_model=PrecipNowcastResponse)
async def get_precipitation_nowcast(request: PrecipNowcastRequest):
    """Get precipitation nowcast for a location"""

    # Get from cache (Tier 1 or Tier 2)
    cache_key = make_cache_key(request.latitude, request.longitude, request.lead_minutes)
    cached_forecast = cache_service.get_point_forecast(cache_key)

    if cached_forecast:
        return PrecipNowcastResponse(**cached_forecast)

    # Generate fresh nowcast
    # ... (implementation in NOW-011)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Radar data unavailable"
    )
```

---

#### NOW-010: Register nowcast router in main app
**Dependencies**: NOW-009
**Effort**: Small (1h)
**Priority**: P0

**Description**: Add nowcast router to FastAPI application

**Files to Modify**:
- `app/main.py`

**Acceptance Criteria**:
- [ ] Nowcast router imported
- [ ] Router registered with `/api/v2` prefix
- [ ] App starts without errors
- [ ] Swagger docs show nowcast endpoints
- [ ] Can access http://localhost:8000/docs and see endpoints

**Code**:
```python
# app/main.py
from app.api.v2 import weather, health, metrics, nowcast  # Add nowcast

app.include_router(nowcast.router, prefix="/api/v2", tags=["nowcast"])
```

---

### Sprint 4: Caching (Week 4)

#### NOW-011: Implement multi-tier cache service
**Dependencies**: NOW-006
**Effort**: Medium (6h)
**Priority**: P0 (Critical Path)

**Description**: SQLite + LRU cache for nowcast data

**Files to Create**:
- `app/core/nowcast/services/cache_service.py`
- `tests/unit/nowcast/services/test_cache_service.py`

**Acceptance Criteria**:
- [ ] SQLite database initialized with schema
- [ ] Tier 1 (LRU) cache for point forecasts
- [ ] Tier 2 (SQLite) cache for gridded nowcasts
- [ ] TTL expiration works (2min for Tier 1, 5min for Tier 2)
- [ ] `cleanup_expired()` removes old entries
- [ ] `get_cache_stats()` returns metrics
- [ ] Unit tests verify cache hit/miss logic

**Reference**: See Document 06 Section 4.2

---

#### NOW-012: Integrate cache with API endpoint
**Dependencies**: NOW-011, NOW-009
**Effort**: Small (3h)
**Priority**: P1

**Description**: Connect cache service to API router

**Files to Modify**:
- `app/api/v2/nowcast.py`

**Acceptance Criteria**:
- [ ] API checks Tier 1 cache first
- [ ] API falls back to Tier 2 on miss
- [ ] API generates fresh nowcast on both misses
- [ ] Fresh nowcast cached in both tiers
- [ ] Cache metrics incremented correctly
- [ ] Integration test verifies cache behavior

---

### Sprint 5: Verification (Week 5)

#### NOW-013: Implement MRMS downloader
**Dependencies**: NOW-003
**Effort**: Medium (6h)
**Priority**: P2

**Description**: Download MRMS QPE data for verification

**Files to Create**:
- `app/core/nowcast/data/mrms_downloader.py`
- `tests/unit/nowcast/data/test_mrms_downloader.py`

**Acceptance Criteria**:
- [ ] Can download MRMS QPE from NOAA server
- [ ] Downloads cover same time window as forecasts
- [ ] Files cached locally (30-day retention)
- [ ] Handles missing data gracefully
- [ ] Unit tests with mocked HTTP responses

---

#### NOW-014: Implement verification service
**Dependencies**: NOW-013, NOW-006
**Effort**: Large (8h)
**Priority**: P2

**Description**: Compute skill scores from forecast-observation pairs

**Files to Create**:
- `app/core/nowcast/services/verification_service.py`
- `tests/unit/nowcast/services/test_verification_service.py`

**Acceptance Criteria**:
- [ ] Can match forecast grids to MRMS observations
- [ ] Computes categorical metrics (hit, false alarm, miss, correct negative)
- [ ] Computes CSI, POD, FAR for multiple thresholds
- [ ] Computes continuous metrics (MAE, RMSE)
- [ ] Writes verification pairs to TimescaleDB
- [ ] Unit tests verify metric calculations

**Code Structure**:
```python
# app/core/nowcast/services/verification_service.py
class VerificationService:
    def __init__(self, db_conn):
        self.db_conn = db_conn

    async def verify_nowcast(
        self,
        forecast_grid: np.ndarray,
        observation_grid: np.ndarray,
        forecast_time: datetime,
        valid_time: datetime,
        lead_minutes: int,
        thresholds: list = [1.0, 5.0, 10.0]
    ):
        """Compute verification metrics"""

        for threshold in thresholds:
            # Categorical metrics
            hits, false_alarms, misses, correct_negatives = self._compute_categorical(
                forecast_grid,
                observation_grid,
                threshold
            )

            # Skill scores
            csi = hits / (hits + false_alarms + misses) if (hits + false_alarms + misses) > 0 else 0
            pod = hits / (hits + misses) if (hits + misses) > 0 else 0
            far = false_alarms / (hits + false_alarms) if (hits + false_alarms) > 0 else 0

            # Write to database
            await self._write_verification(
                forecast_time,
                valid_time,
                lead_minutes,
                threshold,
                csi,
                pod,
                far
            )
```

---

#### NOW-015: Add verification scheduler job
**Dependencies**: NOW-014
**Effort**: Small (3h)
**Priority**: P2

**Description**: Scheduled job to run verification

**Files to Modify**:
- `app/core/scheduler.py`

**Acceptance Criteria**:
- [ ] Verification job runs every 15 minutes
- [ ] Job fetches MRMS data asynchronously
- [ ] Job computes skill scores for recent forecasts
- [ ] Job updates TimescaleDB continuous aggregates
- [ ] Errors logged but don't block nowcast generation

---

### Sprint 6: Monitoring & Testing (Week 6)

#### NOW-016: Add Prometheus metrics
**Dependencies**: NOW-009, NOW-011, NOW-014
**Effort**: Medium (4h)
**Priority**: P1

**Description**: Instrument nowcast system with Prometheus metrics

**Files to Modify**:
- `app/core/metrics.py`
- `app/api/v2/nowcast.py`
- `app/core/nowcast/engines/pysteps_engine.py`

**Acceptance Criteria**:
- [ ] Request metrics (total, duration histogram)
- [ ] Generation metrics (duration, errors)
- [ ] Cache metrics (hits, misses, size)
- [ ] Data freshness metrics (radar age, quality score)
- [ ] Skill score metrics (CSI, MAE, RMSE)
- [ ] Metrics exported at `/metrics` endpoint
- [ ] Prometheus scrapes successfully

**Reference**: See Document 06 Section 5.1

---

#### NOW-017: Create Grafana dashboard
**Dependencies**: NOW-016
**Effort**: Medium (4h)
**Priority**: P1

**Description**: Grafana dashboard for nowcast monitoring

**Files to Create**:
- `grafana/dashboards/nowcasting.json`

**Acceptance Criteria**:
- [ ] Panel for API request rate
- [ ] Panel for P95 latency (threshold: 2s)
- [ ] Panel for cache hit rate (threshold: 80%)
- [ ] Panel for radar data age (threshold: 10min)
- [ ] Panel for CSI by lead time
- [ ] Dashboard imports successfully into Grafana

**Reference**: See Document 06 Section 5.2

---

#### NOW-018: Configure alerting rules
**Dependencies**: NOW-016
**Effort**: Small (2h)
**Priority**: P2

**Description**: Prometheus alerting for critical issues

**Files to Create**:
- `prometheus/alerts/nowcasting.yml`

**Acceptance Criteria**:
- [ ] Alert: Radar data stale (>15 min)
- [ ] Alert: API latency high (P95 > 5s)
- [ ] Alert: Cache hit rate low (<70%)
- [ ] Alert: CSI degraded (<0.30 @ 60min)
- [ ] Alert: Generation errors (>10% failure rate)
- [ ] Alerts fire correctly in test scenario

**Reference**: See Document 06 Section 5.3

---

#### NOW-019: Write unit tests for PySTEPS engine
**Dependencies**: NOW-005
**Effort**: Medium (6h)
**Priority**: P1

**Description**: Comprehensive unit tests for nowcast engine

**Files to Create**:
- `tests/unit/nowcast/engines/test_pysteps_engine.py`

**Acceptance Criteria**:
- [ ] Test reflectivity conversion
- [ ] Test motion field computation
- [ ] Test cascade decomposition
- [ ] Test ensemble generation
- [ ] Test full pipeline integration
- [ ] Coverage >90% for pysteps_engine.py

---

#### NOW-020: Write unit tests for cache service
**Dependencies**: NOW-011
**Effort**: Small (4h)
**Priority**: P1

**Description**: Unit tests for multi-tier cache

**Files to Create**:
- `tests/unit/nowcast/services/test_cache_service.py`

**Acceptance Criteria**:
- [ ] Test cache set/get operations
- [ ] Test TTL expiration
- [ ] Test cleanup of expired entries
- [ ] Test cache statistics
- [ ] Coverage >90% for cache_service.py

---

#### NOW-021: Write integration tests for API
**Dependencies**: NOW-012
**Effort**: Medium (6h)
**Priority**: P1

**Description**: End-to-end API integration tests

**Files to Create**:
- `tests/integration/nowcast/test_api_endpoints.py`

**Acceptance Criteria**:
- [ ] Test successful nowcast request
- [ ] Test invalid coordinates (422 error)
- [ ] Test stale radar data (503 error)
- [ ] Test SSE stream connection
- [ ] Test status endpoint
- [ ] All tests pass with test database

---

#### NOW-022: Create test fixtures
**Dependencies**: NOW-019, NOW-020, NOW-021
**Effort**: Medium (4h)
**Priority**: P1

**Description**: Reusable test fixtures and sample data

**Files to Create**:
- `tests/fixtures/nowcast/sample_nexrad.gz`
- `tests/fixtures/nowcast/sample_mrms.grib2`
- `tests/conftest.py` (additions)

**Acceptance Criteria**:
- [ ] Sample NEXRAD file (small, <10MB)
- [ ] Sample MRMS file (small, <10MB)
- [ ] Pytest fixtures for common objects (engine, cache, etc.)
- [ ] Fixtures load without errors
- [ ] Tests use fixtures instead of duplicating setup

---

### Additional Tasks (Post-MVP Enhancements)

#### NOW-023: Add geographic utilities
**Dependencies**: NOW-006
**Effort**: Small (3h)
**Priority**: P2

**Description**: Helper functions for geospatial operations

**Files to Create**:
- `app/core/nowcast/utils/geo_utils.py`

---

#### NOW-024: Implement quality control checks
**Dependencies**: NOW-004
**Effort**: Medium (4h)
**Priority**: P2

**Description**: Advanced QC for radar data (velocity dealiasing, attenuation correction)

**Files to Modify**:
- `app/core/nowcast/data/radar_preprocessor.py`

---

#### NOW-025: Add database migration scripts
**Dependencies**: NOW-014
**Effort**: Small (2h)
**Priority**: P1

**Description**: Alembic migrations for nowcast tables

**Files to Create**:
- `alembic/versions/xxx_add_nowcast_tables.py`

---

#### NOW-026: Create API documentation
**Dependencies**: NOW-010
**Effort**: Small (3h)
**Priority**: P2

**Description**: Comprehensive API docs and examples

**Files to Create**:
- `docs/api/nowcast.md`

---

#### NOW-027: Add performance benchmarks
**Dependencies**: NOW-005
**Effort**: Small (3h)
**Priority**: P2

**Description**: Performance tests for critical paths

**Files to Create**:
- `tests/performance/test_nowcast_latency.py`

**Reference**: See Document 06 Section 6.3

---

#### NOW-028: Implement radar composite
**Dependencies**: NOW-004
**Effort**: Medium (6h)
**Priority**: P3 (Phase 2)

**Description**: Multi-radar compositing (KDTX + KAPX)

---

#### NOW-029: Add GOES satellite integration
**Dependencies**: NOW-005
**Effort**: Large (10h)
**Priority**: P3 (Phase 2)

**Description**: Integrate GOES-16/17 satellite data for cloud motion

---

#### NOW-030: Implement U-Net ML refinement
**Dependencies**: NOW-005
**Effort**: X-Large (20h)
**Priority**: P3 (Phase 2)

**Description**: ML model to refine PySTEPS output

---

#### NOW-031: Add ensemble calibration
**Dependencies**: NOW-006
**Effort**: Medium (6h)
**Priority**: P3 (Phase 2)

**Description**: Post-processing to calibrate ensemble spread

---

#### NOW-032: Implement SSE authentication
**Dependencies**: NOW-009
**Effort**: Small (3h)
**Priority**: P2

**Description**: Token-based auth for SSE streams

---

#### NOW-033: Add rate limiting
**Dependencies**: NOW-009
**Effort**: Small (3h)
**Priority**: P2

**Description**: Per-IP rate limiting (10 req/min)

---

#### NOW-034: Create Docker deployment
**Dependencies**: NOW-010
**Effort**: Medium (5h)
**Priority**: P1

**Description**: Dockerfile and docker-compose for deployment

**Files to Create**:
- `docker/Dockerfile.nowcast`
- `docker-compose.nowcast.yml`

---

#### NOW-035: Add Kubernetes manifests
**Dependencies**: NOW-034
**Effort**: Medium (5h)
**Priority**: P1

**Description**: K8s deployment with HPA

**Files to Create**:
- `k8s/nowcast-deployment.yaml`
- `k8s/nowcast-hpa.yaml`
- `k8s/nowcast-service.yaml`

**Reference**: See Document 05 Section 1.5

---

#### NOW-036: Implement health checks
**Dependencies**: NOW-010
**Effort**: Small (2h)
**Priority**: P1

**Description**: Kubernetes liveness/readiness probes

---

#### NOW-037: Add CI/CD pipeline
**Dependencies**: NOW-022
**Effort**: Medium (4h)
**Priority**: P1

**Description**: GitHub Actions for testing and deployment

**Files to Create**:
- `.github/workflows/nowcast-test.yml`
- `.github/workflows/nowcast-deploy.yml`

---

#### NOW-038: Write deployment documentation
**Dependencies**: NOW-035
**Effort**: Small (3h)
**Priority**: P1

**Description**: Complete deployment guide

**Files to Create**:
- `docs/deployment/nowcast.md`

---

## Sprint Breakdown

### Sprint 1 (Week 1): Foundation
**Goal**: Set up infrastructure and data pipeline
**Tasks**: NOW-001 → NOW-004
**Deliverable**: Can download and preprocess NEXRAD data

### Sprint 2 (Week 2): PySTEPS Engine
**Goal**: Core nowcast generation working
**Tasks**: NOW-005 → NOW-007
**Deliverable**: Can generate 120-minute nowcasts

### Sprint 3 (Week 3): API Endpoint
**Goal**: API accessible to users
**Tasks**: NOW-008 → NOW-010
**Deliverable**: Working `/api/v2/nowcast/precipitation` endpoint

### Sprint 4 (Week 4): Caching
**Goal**: Performance optimization
**Tasks**: NOW-011 → NOW-012
**Deliverable**: <2s P95 API latency with 80%+ cache hit rate

### Sprint 5 (Week 5): Verification
**Goal**: Automated quality monitoring
**Tasks**: NOW-013 → NOW-015
**Deliverable**: Real-time CSI tracking on Grafana

### Sprint 6 (Week 6): Monitoring & Testing
**Goal**: Production readiness
**Tasks**: NOW-016 → NOW-022
**Deliverable**: Comprehensive test suite + monitoring dashboard

---

## Critical Path Analysis

**Longest dependency chain** (defines minimum timeline):

```
NOW-001 (2h) → NOW-002 (1h) → NOW-003 (8h) → NOW-004 (6h)
→ NOW-005 (12h) → NOW-006 (6h) → NOW-008 (3h) → NOW-009 (8h)
→ NOW-011 (6h) → NOW-012 (3h)

Total: 55 hours critical path
```

**Parallelizable work**: NOW-013 through NOW-022 can run concurrently with critical path completion.

---

## Effort Summary

| Effort Level | Hours | Count | Total Hours |
|--------------|-------|-------|-------------|
| Small        | 2-3   | 14    | ~35         |
| Medium       | 4-6   | 15    | ~75         |
| Large        | 8-10  | 7     | ~60         |
| X-Large      | 12+   | 2     | ~32         |
| **TOTAL**    | -     | **38**| **~202**    |

**Contingency**: +20% = 242 hours total (6 weeks @ 40h/week)

---

## Success Criteria (Phase 1 MVP)

| Metric | Target | Verification |
|--------|--------|--------------|
| **CSI @ 60min** | >0.35 | MRMS verification (NOW-014) |
| **API P95 latency** | <2s | Prometheus metrics (NOW-016) |
| **Cache hit rate** | >80% | Cache metrics (NOW-011) |
| **Radar data age** | <10min | Freshness gauge (NOW-016) |
| **Test coverage** | >85% | pytest-cov (NOW-019 → NOW-022) |
| **Uptime (7 days)** | >99% | Health checks (NOW-036) |

---

## Risk Mitigation

### Risk 1: PySTEPS Performance (NOW-005)
- **Mitigation**: Benchmark early (Sprint 2), optimize grid tiling if needed
- **Fallback**: Reduce ensemble size from 10 to 5 members

### Risk 2: S3 Rate Limiting (NOW-003)
- **Mitigation**: Exponential backoff implemented, local cache 7 days
- **Fallback**: Reduce download frequency from 5min to 10min

### Risk 3: Cache Complexity (NOW-011)
- **Mitigation**: Start with Tier 2 (SQLite) only, add Tier 1 (LRU) if needed
- **Fallback**: Single-tier cache acceptable for MVP

---

## Dependencies (External)

- **AWS Access**: S3 bucket `noaa-nexrad-level2` (public, no credentials required)
- **NOAA MRMS**: HTTP access to MRMS QPE data (public)
- **PostgreSQL**: Existing VortexV2 database with TimescaleDB extension
- **Prometheus**: Existing VortexV2 monitoring stack
- **Grafana**: Existing VortexV2 visualization

---

## Next Steps

1. **Review this implementation plan** for completeness and feasibility
2. **Assign tasks** to development team (or personal sprint backlog)
3. **Begin Sprint 1** with NOW-001 (module structure)
4. **Daily standups** to track progress and blockers
5. **Sprint reviews** at end of each week to demo working features

---

**Implementation Guide**:
- Start with critical path tasks (P0) before P1/P2/P3
- Complete each task's acceptance criteria before moving to next
- Run tests continuously (`pytest -v tests/`)
- Update Grafana dashboard as metrics are added
- Document decisions in code comments

---

**Document Version**: 1.0
**Last Updated**: 2026-01-18
**Status**: ✅ Ready for execution
**Total Estimated Effort**: 202 hours (6 weeks)
