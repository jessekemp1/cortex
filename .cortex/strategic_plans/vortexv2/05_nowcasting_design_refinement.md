# VortexV2 Nowcasting System - Design Refinement

**Created**: 2026-01-17
**Status**: Architecture decisions finalized
**Purpose**: High-level design decisions with trade-off analysis

---

## 1. Architecture Decisions

### 1.1 PySTEPS Configuration

**Decision**: Lucas-Kanade motion estimator with 8 cascade levels

| Option | Pros | Cons | Performance |
|--------|------|------|-------------|
| **Lucas-Kanade (Selected)** | Fast (<5s), reliable | Struggles with rotation | Best for our use case |
| DARTS | Handles rotation well | Slower (10-15s) | Overkill for Lake Huron |
| Sparse matching | Very fast (<2s) | Less accurate | Too simple |

**Justification**:
- Lake Huron weather patterns are primarily translational (frontal systems, lake effect)
- Rotational motion (tropical systems) rare in Great Lakes
- Speed matters for 5-min update cycle
- **Chosen: Lucas-Kanade with 8 cascade levels** (industry standard)

**Configuration**:
```python
PYSTEPS_MOTION = "lucaskanade"
PYSTEPS_CASCADE_LEVELS = 8  # Multi-scale decomposition
PYSTEPS_EXTRAP_METHOD = "semilagrangian"  # Stable advection
PYSTEPS_NOISE_METHOD = "nonparametric"  # Realistic uncertainty
```

---

### 1.2 Data Pipeline Design

**Decision**: Hybrid streaming + batch with aggressive caching

| Approach | Pros | Cons | Chosen |
|----------|------|------|--------|
| **Pure streaming** | Low latency | Complex, expensive | ❌ |
| **Pure batch** | Simple, cheap | High latency | ❌ |
| **Hybrid (Selected)** | Balanced | Moderate complexity | ✅ |

**Architecture**:
```
NEXRAD S3 → Download every 5 min (batch)
           ↓
       Local cache (streaming access)
           ↓
    PySTEPS (batch generation)
           ↓
       Redis cache (streaming reads)
```

**Rationale**:
- NEXRAD updates every 4-6 minutes → batch download is fine
- API needs <2s response → cache required
- Cost: Batch cheaper than streaming S3 reads

---

### 1.3 API Design

**Decision**: REST with SSE (Server-Sent Events) for updates

| Option | Pros | Cons | Use Case |
|--------|------|------|----------|
| **REST only** | Simple, cacheable | No real-time | ❌ |
| **GraphQL** | Flexible queries | Overhead, caching hard | ❌ |
| **WebSocket** | Bidirectional | Complex, stateful | ❌ |
| **REST + SSE (Selected)** | Best of both | One-way only | ✅ |

**Endpoints**:
```
POST /api/v2/nowcast/precipitation
  - Standard REST for one-time forecast requests
  - Cacheable, fast (<500ms with cache)

GET /api/v2/nowcast/precipitation/stream
  - SSE for real-time updates every 5 min
  - Auto-reconnect, HTTP/2 compatible
```

**Justification**:
- REST fits VortexV2 existing patterns (`/api/v2/weather/forecast`)
- SSE simpler than WebSocket for one-way updates
- GraphQL overkill for simple nowcast queries

---

### 1.4 Database Schema

**Decision**: TimescaleDB hypertables with daily partitioning

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **PostgreSQL (plain)** | Simple | Slow time-series | ❌ |
| **TimescaleDB (Selected)** | Time-series optimized | Requires extension | ✅ |
| **InfluxDB** | Purpose-built | Separate database | ❌ |

**Schema Design**:
```sql
-- Verification pairs table (hypertable)
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
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable with daily partitions
SELECT create_hypertable('nowcast_verification', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- Continuous aggregate for skill scores
CREATE MATERIALIZED VIEW nowcast_skill_scores_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    lead_minutes,
    threshold_mm_h,
    SUM(CASE WHEN hit THEN 1 ELSE 0 END)::REAL /
        NULLIF(SUM(CASE WHEN hit OR false_alarm OR miss THEN 1 ELSE 0 END), 0) AS csi,
    AVG(ABS(forecast_precip_rate - observed_precip_rate)) AS mae
FROM nowcast_verification
GROUP BY hour, lead_minutes, threshold_mm_h;
```

**Rationale**:
- VortexV2 already uses TimescaleDB for validation data
- Continuous aggregates enable real-time skill monitoring
- Daily partitioning supports 90-day retention with fast queries

---

### 1.5 Deployment Architecture

**Decision**: Docker containers with horizontal pod autoscaling

| Component | Scaling | Justification |
|-----------|---------|---------------|
| **API Server** | 2-4 pods (HPA) | Handle concurrent requests |
| **Scheduler** | 1 pod (singleton) | Download + generation jobs |
| **Redis Cache** | 1 instance (shared) | State coordination |
| **PostgreSQL** | 1 instance (managed) | Existing VortexV2 database |

**Infrastructure**:
```yaml
# Kubernetes deployment (simplified)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vortex-nowcast-api
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: api
        image: vortex-nowcast:latest
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vortex-nowcast-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vortex-nowcast-api
  minReplicas: 2
  maxReplicas: 4
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 2. Integration Points with VortexV2

### 2.1 API Router Integration

**Pattern**: Follow existing `/api/v2/weather.py` structure

```python
# app/main.py (existing)
from app.api.v2 import weather, health, metrics
app.include_router(weather.router, prefix="/api/v2", tags=["weather"])

# NEW: Add nowcast router
from app.api.v2 import nowcast
app.include_router(nowcast.router, prefix="/api/v2", tags=["nowcast"])
```

**Compatibility**: Nowcast endpoints follow same patterns as forecast endpoints

---

### 2.2 Scheduler Integration

**Pattern**: Extend `VortexScheduler` with nowcast jobs

```python
# app/core/scheduler.py (modify)
class VortexScheduler:
    def _setup_jobs(self):
        # Existing jobs...
        self._setup_forecast_jobs()
        self._setup_validation_jobs()

        # NEW: Nowcast jobs
        self._setup_nowcast_jobs()

    def _setup_nowcast_jobs(self):
        # NEXRAD download every 5 minutes
        self.scheduler.add_job(
            self.nowcast_download_radar,
            trigger=IntervalTrigger(minutes=5),
            id="nowcast_radar_download"
        )

        # Nowcast generation every 5 minutes
        self.scheduler.add_job(
            self.nowcast_generate_forecast,
            trigger=IntervalTrigger(minutes=5),
            id="nowcast_generate",
            misfire_grace_time=120
        )
```

---

### 2.3 Cache Integration

**Pattern**: Extend `SQLiteCache` for nowcast-specific caching

```python
# app/core/cache.py (existing pattern)
class SQLiteCache:
    # Existing forecast caching...

# app/core/nowcast/services/cache_service.py (new)
from app.core.cache import SQLiteCache

class NowcastCacheService(SQLiteCache):
    """Specialized cache for nowcast data"""
    DEFAULT_TTL = 120  # 2 minutes for nowcast

    def cache_point_forecast(self, lat: float, lon: float, forecast: dict):
        key = f"nowcast:point:{round(lat,2)}:{round(lon,2)}"
        self.set(key, forecast, ex=self.DEFAULT_TTL)
```

---

### 2.4 Metrics Integration

**Pattern**: Add to existing Prometheus registry

```python
# app/core/metrics.py (modify)
from prometheus_client import Counter, Histogram, Gauge

# NEW: Nowcast metrics
nowcast_generation_seconds = Histogram(
    "vortex_nowcast_generation_seconds",
    "Time to generate nowcast",
    ["method"],
    buckets=(1, 2, 5, 10, 30, 60)
)

nowcast_csi_60min = Gauge(
    "vortex_nowcast_csi_60min",
    "Critical Success Index at 60-minute lead",
    ["threshold"]
)

nowcast_radar_age_minutes = Gauge(
    "vortex_nowcast_radar_age_minutes",
    "Age of most recent radar data"
)
```

---

## 3. Performance Requirements

### 3.1 API Latency Targets

| Metric | Target | Stretch Goal | Monitoring |
|--------|--------|--------------|------------|
| **P50 latency** | < 500ms | < 200ms | Prometheus histogram |
| **P95 latency** | < 2s | < 1s | Alert if > 2s |
| **P99 latency** | < 5s | < 2s | Alert if > 5s |
| **Cache hit rate** | > 80% | > 90% | Counter |

**Measurement**: `histogram_quantile(0.95, nowcast_generation_seconds)`

---

### 3.2 Data Freshness Requirements

| Data Source | Max Age | Degradation Strategy |
|-------------|---------|---------------------|
| **NEXRAD radar** | 10 minutes | Use persistence forecast if > 10min |
| **MRMS QPE** | 15 minutes | Skip verification if > 15min |
| **PySTEPS forecast** | 5 minutes | Regenerate every 5min |

---

### 3.3 Concurrent User Capacity

| Load Level | Users | Requests/sec | Infrastructure |
|------------|-------|--------------|----------------|
| **Normal** | 10-20 | 5-10 | 2 API pods |
| **Peak** | 50-100 | 20-30 | 4 API pods (HPA) |
| **Stress** | 200+ | 50+ | Graceful degradation |

---

## 4. Risk Analysis

### 4.1 Technical Risks

#### Risk 1: AWS S3 Rate Limiting
- **Probability**: Medium
- **Impact**: High (system stops working)
- **Mitigation**:
  - Implement exponential backoff (2s, 4s, 8s, 16s)
  - Local NEXRAD cache (7-day retention)
  - Request batching (download multiple scans at once)
  - Fallback to previous forecast if download fails

#### Risk 2: PySTEPS Memory Usage
- **Probability**: Medium
- **Impact**: Medium (OOM crashes)
- **Mitigation**:
  - Grid tiling for large domains (256x256 max)
  - Memory limits in Kubernetes (8GB hard limit)
  - Garbage collection after each forecast
  - Monitoring: `process_resident_memory_bytes`

#### Risk 3: Disk Space Exhaustion
- **Probability**: Low
- **Impact**: High (system failure)
- **Mitigation**:
  - Automated cleanup (delete radar > 7 days)
  - Disk usage alerts (> 80% usage)
  - Compression for archived data (gzip)
  - Monitoring: `node_filesystem_avail_bytes`

---

### 4.2 Data Risks

#### Risk 1: NEXRAD Coverage Gaps
- **Probability**: Medium (weather events cause outages)
- **Impact**: Medium (degraded nowcasts)
- **Mitigation**:
  - Multi-station compositing (KDTX + KAPX)
  - Graceful degradation to persistence
  - Quality score in response (0-1)
  - User notification when data stale

#### Risk 2: MRMS Verification Latency
- **Probability**: Low
- **Impact**: Low (delayed skill monitoring)
- **Mitigation**:
  - Asynchronous verification (doesn't block API)
  - 15-minute tolerance for matching
  - Continuous aggregates show trends
  - Manual validation option

---

### 4.3 Operational Risks

#### Risk 1: Scheduler Failure
- **Probability**: Low
- **Impact**: High (no new forecasts)
- **Mitigation**:
  - APScheduler persistent job store
  - Systemd watchdog for auto-restart
  - Health check endpoint (`/api/v2/nowcast/status`)
  - Alert on missed jobs (> 10 min)

#### Risk 2: Cache Stampede
- **Probability**: Low
- **Impact**: Medium (latency spike)
- **Mitigation**:
  - Cache locking (only one generation per location)
  - Stale-while-revalidate pattern
  - Background cache warming
  - Rate limiting (10 req/min per IP)

---

## 5. Trade-Off Decisions Summary

| Decision | Choice | Rationale | Trade-Off |
|----------|--------|-----------|-----------|
| **Motion Estimator** | Lucas-Kanade | Speed + accuracy balance | Can't handle rotation well |
| **Data Pipeline** | Hybrid batch+stream | Cost + latency balance | More complex than pure approach |
| **API Protocol** | REST + SSE | Simple + real-time | SSE is one-way only |
| **Database** | TimescaleDB | Time-series optimized | Requires extension install |
| **Deployment** | Docker + K8s HPA | Scalable + resilient | More complex than monolith |

---

## 6. Success Criteria

### Phase 1 Launch (MVP)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **CSI @ 60min** | > 0.35 | MRMS verification |
| **API P95** | < 2s | Prometheus |
| **Uptime** | > 99% | Health checks |
| **Cache hit** | > 80% | Counter |
| **Data age** | < 10min | Gauge |

### Phase 2 Enhancement (3 months)

| Metric | Target | Improvement |
|--------|--------|-------------|
| **CSI @ 60min** | > 0.50 | +15 points (U-Net) |
| **API P95** | < 1s | -50% (TensorRT) |
| **Ensemble size** | 20 members | 2x (confidence) |

---

## 7. Architectural Principles

1. **Simplicity Over Perfection**: Use PySTEPS baseline (proven) before adding ML complexity
2. **Cache Everything**: Radar, grids, point forecasts - multiple tiers
3. **Fail Gracefully**: Always have fallback (persistence forecast, cached data)
4. **Monitor Actively**: Metrics for every component, alerts for degradation
5. **Iterate Quickly**: Ship Phase 1 in 6 weeks, enhance in Phase 2

---

## 8. Deferred Decisions (Phase 2)

| Decision | Deferred Until | Reason |
|----------|----------------|--------|
| U-Net ML refinement | After CSI baseline | Need baseline performance first |
| GOES satellite integration | After NEXRAD stable | One data source at a time |
| DGMR generative model | Research phase | Requires extensive training |
| Transformer architecture | Performance evaluation | Inference cost unclear |

---

**Next Steps**:
1. Review and approve all architecture decisions
2. Proceed to Development Specification (Document 06)
3. Begin implementation with NOW-001

**Approval Required**: ✅ Architecture finalized, ready for detailed spec

---

**Document Version**: 1.0
**Last Updated**: 2026-01-17
**Status**: ✅ Design decisions finalized
