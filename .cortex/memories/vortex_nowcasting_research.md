# VortexV2 Nowcasting System: Deep Research & Design Document

**Created**: 2026-01-16
**Status**: Research Complete - Ready for Implementation Planning
**Author**: Strategic Planning Supervisor
**Priority**: IMMEDIATE

---

## Executive Summary

This document presents a comprehensive research and design plan for implementing a nowcasting system within VortexV2, targeting 0-120 minute ultra-accurate forecasts. The recommended architecture is a **hybrid optical flow + ML refinement approach** using PySTEPS as the foundation with U-Net/ConvLSTM enhancement layers, integrated with VortexV2's existing ensemble framework.

### Key Recommendations

1. **Primary Architecture**: PySTEPS optical flow + U-Net refinement (Phase 1), adding DGMR-style generative model (Phase 2)
2. **Data Sources**: NEXRAD Level-II radar (primary), GOES-16/17 satellite (secondary), MRMS composites (validation)
3. **Target Performance**: CSI > 0.6 for precipitation thresholds, < 5 min inference time for 2-hour forecast
4. **Integration Strategy**: Separate API endpoint with failover to 6-hour ensemble forecasts

---

## 1. State-of-the-Art Literature Review

### 1.1 PySTEPS (Radar Extrapolation)

**Overview**: PySTEPS is an open-source Python library for probabilistic precipitation nowcasting, representing the current state-of-the-art in operational extrapolation-based systems.

**Key Capabilities**:
- Optical flow methods (Lucas-Kanade, Dense)
- STEPS stochastic ensemble generation
- Probabilistic predictions with uncertainty quantification
- Demonstrated 3-hour skillful predictions over maritime regions

**Performance Benchmarks** (2024 Studies):
- Maritime Continent (February 2024): AUC score of 0.8 over sea (morning), 0.71 over land
- Central Mexico (January 2024): PoD > 70%, FAR reaching 40% for 15-minute predictions
- Netherlands Evaluation: CSI competitive with deep learning through 60-minute lead times

**Strengths**:
- Well-documented, community-driven
- Modular architecture for customization
- Supports multiple input/output formats
- Proven operational use at national met services

**Weaknesses**:
- Struggles with convective initiation (genesis from clear air)
- Assumes quasi-linear motion (fails for rapidly evolving systems)
- No inherent physics beyond advection

**Source**: [PySTEPS Documentation](https://pysteps.github.io/)

### 1.2 DeepMind DGMR (Generative Nowcasting)

**Overview**: Deep Generative Model of Radar (DGMR) uses conditional GANs for probabilistic precipitation prediction, published in Nature 2021.

**Architecture**:
- Conditioning stack: Processes 4 radar frames (20 minutes) at multiple resolutions
- Latent conditioning stack: Samples from Gaussian distribution
- Sampler: Recurrent ConvGRU network predicting 18 frames (90 minutes)
- Two discriminators: Spatial consistency + temporal consistency

**Performance**:
- Ranked first by 58 expert meteorologists in 89% of test cases
- Outperforms PySTEPS on medium-to-heavy precipitation events
- Maintains intensity and extent better than advection methods
- Single inference: ~1 second on NVIDIA V100

**Strengths**:
- Handles non-linear precipitation dynamics
- Generates realistic ensemble members
- Captures convective evolution better than extrapolation

**Weaknesses**:
- Requires extensive training data (3 years UK radar)
- Limited to 90-minute forecasts
- Computationally expensive training
- Struggles with rare, extreme events

**Source**: [Nature Article](https://www.nature.com/articles/s41586-021-03854-z)

### 1.3 Google MetNet (Neural Weather Model)

**Overview**: MetNet family (MetNet, MetNet-2, MetNet-3, Global MetNet) uses direct observations for neural weather prediction.

**Evolution**:
- **MetNet (2020)**: 8-hour forecasts, 1km resolution, 2-minute temporal resolution
- **MetNet-2 (2021-2022)**: 12-hour predictions, outperforms HRRR for lead times < 12 hours
- **MetNet-3 (2023)**: 24-hour forecasts, expanded variables (precipitation, temperature, wind, dew point), uses "densification" technique
- **Global MetNet (2024-2025)**: Global coverage using geostationary satellite data

**Key Innovation**: Densification merges data assimilation and simulation into single neural network pass.

**Strengths**:
- Uses direct observations (higher fidelity than NWP outputs)
- Inference in seconds vs. hours for traditional models
- Handles data-sparse regions via satellite integration

**Weaknesses**:
- Proprietary (not publicly available)
- Requires massive training infrastructure
- Regional training needed for optimal performance

**Source**: [Google Research](https://research.google/blog/metnet-3-a-state-of-the-art-neural-weather-model-available-in-google-products/)

### 1.4 NOAA MRMS (Multi-Radar Multi-Sensor)

**Overview**: Operational system combining 160+ NEXRAD radars, satellites, surface observations, and NWP models.

**Specifications**:
- 1km spatial resolution
- 33 vertical levels
- 2-minute update cycle
- 100+ products including QPE, storm tracking, severe weather indices

**Nowcasting Capabilities**:
- ProbSevere: 60-minute probabilistic severe weather nowcasts
- Storm motion vectors
- Hail, tornado, lightning hazard guidance

**Relevance for VortexV2**: MRMS provides high-quality composite radar data that can serve as input for our nowcasting model, plus validation targets.

**Source**: [NSSL MRMS Project](https://www.nssl.noaa.gov/projects/mrms/)

### 1.5 Transformer-Based Models (2024-2025)

**Recent Developments**:

| Model | Key Innovation | Performance |
|-------|----------------|-------------|
| **NowcastingGPT** | Extreme Value Loss regularization | Superior for heavy precipitation |
| **SwinNowcast** | Swin Transformer + multi-scale feature balancing | SOTA on radar datasets |
| **EF4INCA** | Earthformer-based, multi-source integration | 90-min forecasts, 1km/5min resolution |
| **Diffusion Transformer** | Causal attention + diffusion models | Strong temporal consistency |
| **FuXi-Nowcast** | 3D ML forecast integration | Captures convective initiation |

**Key Finding**: Transformer-based models outperform CNN/ConvLSTM for longer lead times (> 60 min) due to better long-range dependency capture.

**Source**: [arXiv Transformer Nowcasting Papers](https://arxiv.org/abs/2403.03929)

### 1.6 Comparison Matrix

| Method | Lead Time | CSI (16mm/h) | Convective Initiation | Inference Time | Training Data |
|--------|-----------|--------------|----------------------|----------------|---------------|
| PySTEPS | 0-3h | 0.4-0.6 | Poor | <1s | None (rule-based) |
| DGMR | 0-90min | 0.3-0.5 | Moderate | ~1s | 3 years |
| MetNet-3 | 0-24h | 0.5-0.7 | Good | <1s | Years |
| ConvLSTM | 0-2h | 0.3-0.5 | Poor | <1s | Months |
| U-Net | 0-2h | 0.4-0.6 | Moderate | <1s | Months |
| FuXi-Nowcast | 0-6h | 0.5-0.7 | Good | ~5s | Years |

---

## 2. Data Requirements Analysis

### 2.1 NEXRAD Radar Data

#### Level-II vs Level-III Comparison

| Aspect | Level-II (Base Data) | Level-III (Derived Products) |
|--------|---------------------|------------------------------|
| **Resolution** | 0.5° x 250m (Super Resolution) | Reduced resolution |
| **Update Frequency** | 4.5-10 min (VCP dependent) | Same as Level-II |
| **Variables** | Reflectivity, velocity, spectrum width, dual-pol | 40+ derived products |
| **Data Size** | 50-100 MB/volume | 1-10 MB/product |
| **Processing** | Requires heavy processing | Ready to use |
| **Recommendation** | **Primary for ML training** | Validation/features |

**Recommended Approach**: Use Level-II for model training and inference (full resolution), Level-III for additional features (storm tracks, VIL, echo tops).

#### Dual-Polarization Variables (Post-2011)
- Differential reflectivity (ZDR): Raindrop size/shape
- Correlation coefficient (CC): Precipitation type
- Differential phase (KDP): Rain rate estimation

**Access Options**:
- AWS Open Data: Real-time (seconds latency) + archive
- NOAA NODD: Official source, multiple cloud providers
- Cost: Free (open data)

### 2.2 GOES-16/17 Satellite Data

#### Relevant ABI Bands for Nowcasting

| Band | Wavelength | Use Case |
|------|------------|----------|
| **1 (Blue)** | 0.47 μm | Aerosols, smoke, haze |
| **2 (Red)** | 0.64 μm | Clouds, fog (highest res: 0.5km) |
| **13 (Clean Window)** | 10.3 μm | Cloud-top temperature, IR composites |
| **14 (Longwave)** | 11.2 μm | Night microphysics, precipitation |
| **16 (CO2)** | 13.3 μm | Cloud heights |

**Scanning Modes**:
- Mode 6 (default): Full disk every 10 min, CONUS every 5 min, mesoscale every 60 sec
- Mesoscale sectors: 1000x1000 km regions, 60-second updates

**Note**: GOES-17 had IR detector cooling issues (bands 8-16 degraded 2-6 hours/night during equinox seasons). GOES-19 became operational GOES-East April 2025.

### 2.3 Surface Observations

| Source | Update Frequency | Coverage | Use Case |
|--------|-----------------|----------|----------|
| **METAR** | Hourly + SPECI | Airports | Ground truth validation |
| **ASOS/AWOS** | 1-minute | Dense airport network | High-frequency validation |
| **NDBC Buoys** | 10-minute | Coastal/marine | Marine nowcasting |
| **PWS Networks** | 1-15 min | Variable density | Gap filling |
| **Lightning Networks** | Real-time | CONUS+ | Convective initiation |

### 2.4 Data Pipeline Requirements

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  NEXRAD L2 ──┬──> AWS S3 ──> Kafka ──┬──> Preprocessing ──┐     │
│              │                        │                    │     │
│  GOES-16 ───┼──> AWS S3 ──> Kafka ──┤                    ├──>   │
│              │                        │                    │     │
│  MRMS QPE ──┴──> NOAA LDM ──> Kafka ─┴──> Feature Store ──┘     │
│                                                                  │
│  Target Latency: < 2 minutes from observation to inference      │
│  Storage: ~50 GB/day (compressed)                               │
│  Retention: 7 days hot, 90 days warm, archive cold              │
└─────────────────────────────────────────────────────────────────┘
```

**Storage Requirements** (per month):
- NEXRAD Level-II: ~500 GB
- GOES-16 (subset): ~200 GB
- MRMS products: ~100 GB
- Total with redundancy: ~1.5 TB/month

---

## 3. Model Architecture Evaluation

### 3.1 Recommended Architecture: Hybrid Approach

```
┌─────────────────────────────────────────────────────────────────┐
│              VORTEX NOWCAST ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐    ┌──────────────┐    ┌───────────────┐      │
│   │   Radar     │    │   Optical    │    │   U-Net       │      │
│   │   Input     ├───>│   Flow       ├───>│   Refinement  │      │
│   │   (4 frames)│    │   (PySTEPS)  │    │   Network     │      │
│   └─────────────┘    └──────────────┘    └───────┬───────┘      │
│                                                   │              │
│   ┌─────────────┐    ┌──────────────┐            │              │
│   │   Satellite │    │   ConvLSTM   │            │              │
│   │   Features  ├───>│   Encoder    ├────────────┤              │
│   └─────────────┘    └──────────────┘            │              │
│                                                   │              │
│   ┌─────────────┐    ┌──────────────┐    ┌───────v───────┐      │
│   │   NWP       │    │   Blending   │    │   Ensemble    │      │
│   │   Background├───>│   Weights    ├───>│   Generator   │──>   │
│   │   (HRRR)    │    │              │    │   (N=20)      │      │
│   └─────────────┘    └──────────────┘    └───────────────┘      │
│                                                                  │
│   Output: 2-hour probabilistic precipitation forecast            │
│   Resolution: 1km, 5-minute intervals                           │
│   Update cycle: Every 5-10 minutes                              │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Selection Rationale

#### 3.2.1 Optical Flow Layer: PySTEPS (Lucas-Kanade)

**Justification**:
- Proven operational performance
- No training required (physics-based)
- Provides reliable baseline for extrapolation
- Subpixel accuracy with Pyramid Lucas-Kanade

**Configuration**:
```python
# Recommended PySTEPS parameters
motion_estimator = "lucaskanade"  # or "darts" for dense
n_cascade_levels = 8
extrap_method = "semilagrangian"
noise_method = "nonparametric"
```

#### 3.2.2 Refinement Network: U-Net + ConvLSTM

**Architecture**:
- Encoder: 4 downsampling blocks with residual connections
- Bottleneck: ConvLSTM for temporal encoding
- Decoder: 4 upsampling blocks with skip connections
- Output: 12 channels (6 time steps x 2 for mean/variance)

**Key Features**:
- Depthwise separable convolutions (efficiency)
- Attention gates in skip connections
- Multi-resolution input (1km, 4km, 16km)

**Expected Parameters**: ~15M trainable parameters

#### 3.2.3 Ensemble Generation

**Method**: Stochastic perturbation of latent space
- Generate 20-member ensemble per forecast
- Calibrated uncertainty from historical verification
- Rank histogram diagnostics for reliability

### 3.3 Performance Constraints Validation

| Constraint | Target | Expected Performance |
|------------|--------|---------------------|
| Inference time (2hr forecast) | < 5 min | ~30 sec (GPU) |
| CSI for precipitation (0.5mm/h) | > 0.6 | 0.65-0.75 |
| Update frequency | Every 5-10 min | Every 5 min |
| Memory footprint | < 8 GB GPU | ~4 GB |
| API response latency | < 500 ms | ~200 ms (cached) |

### 3.4 Alternative Architectures Considered

| Architecture | Pros | Cons | Recommendation |
|--------------|------|------|----------------|
| Pure PySTEPS | Simple, fast | No learning | Phase 1 baseline |
| DGMR Clone | SOTA quality | Training complexity | Phase 2+ |
| MetNet-style | Best long-term | Proprietary, massive data | Not feasible |
| Transformer-only | Latest research | Inference cost, training | Phase 3+ |
| **Hybrid (Recommended)** | Balanced | Moderate complexity | **Phase 1 target** |

---

## 4. Validation Framework Design

### 4.1 Skill Metrics

#### Primary Metrics

| Metric | Formula | Threshold | Use Case |
|--------|---------|-----------|----------|
| **CSI** | TP/(TP+FP+FN) | > 0.6 | Overall skill |
| **POD** | TP/(TP+FN) | > 0.7 | Detection ability |
| **FAR** | FP/(TP+FP) | < 0.4 | False alarm rate |
| **FSS** | Neighborhood comparison | > 0.5 | Spatial skill scale |
| **CRPS** | Probabilistic score | Lower is better | Ensemble quality |

#### Thresholds for Evaluation

```python
PRECIP_THRESHOLDS = [
    0.1,   # Any precipitation (mm/h)
    1.0,   # Light rain
    4.0,   # Moderate rain
    16.0,  # Heavy rain
    32.0,  # Severe
]

LEAD_TIMES = [15, 30, 60, 90, 120]  # minutes
```

### 4.2 Fractions Skill Score (FSS)

**Key Insight**: FSS measures skill at different spatial scales, identifying where forecasts become useful.

**Implementation**:
```python
def calculate_fss(forecast, observed, threshold, neighborhood_sizes):
    """
    Calculate FSS for multiple neighborhood sizes.

    Returns FSS values and the scale at which FSS > 0.5 (useful skill)
    """
    results = {}
    for n in neighborhood_sizes:  # e.g., [1, 3, 9, 27, 81] km
        forecast_frac = uniform_filter(forecast > threshold, n)
        observed_frac = uniform_filter(observed > threshold, n)

        mse = mean((forecast_frac - observed_frac)**2)
        mse_ref = mean(forecast_frac**2) + mean(observed_frac**2)

        results[n] = 1 - mse/mse_ref if mse_ref > 0 else 0

    return results
```

**Target**: FSS > 0.5 at 5km scale for 60-minute forecasts

### 4.3 Verification Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                   VERIFICATION PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DATA COLLECTION                                              │
│     ├── Archive forecasts with timestamps                       │
│     ├── Match to MRMS verification data                         │
│     └── Apply quality control (no missing, bad data)            │
│                                                                  │
│  2. SKILL CALCULATION                                            │
│     ├── Calculate CSI, POD, FAR for each threshold              │
│     ├── Calculate FSS at multiple scales                        │
│     ├── Calculate CRPS for probabilistic evaluation             │
│     └── Stratify by: lead time, intensity, season, region       │
│                                                                  │
│  3. BASELINE COMPARISON                                          │
│     ├── Persistence (no change from current)                    │
│     ├── PySTEPS-only (optical flow baseline)                    │
│     ├── HRRR (NWP baseline for longer leads)                    │
│     └── Statistical significance testing                        │
│                                                                  │
│  4. REPORTING                                                    │
│     ├── Daily skill score dashboard                             │
│     ├── Reliability diagrams for probabilistic forecasts        │
│     └── Case study analysis for notable events                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Benchmarks from Literature

| System | CSI (16mm/h, 60min) | Source |
|--------|---------------------|--------|
| Persistence | 0.15-0.25 | Universal baseline |
| PySTEPS | 0.35-0.45 | Copernicus 2024 |
| DGMR | 0.30-0.40 | DeepMind 2021 |
| NowcastNet | 0.30 (median) | Nature 2024 |
| FlowCast | 0.20 (SEVIR) | arXiv 2024 |
| **VortexV2 Target** | **0.40-0.50** | Phase 1 goal |

---

## 5. VortexV2 Integration Strategy

### 5.1 API Endpoint Design

```python
# Separate nowcast endpoint
@app.get("/api/v2/nowcast/precipitation")
async def nowcast_precipitation(
    lat: float,
    lon: float,
    lead_minutes: int = 120,  # Max 2 hours
    ensemble_size: int = 10,
    include_uncertainty: bool = True,
) -> NowcastResponse:
    """
    Ultra-short-range precipitation nowcast.

    Returns probabilistic precipitation forecast for 0-120 minutes.
    Updates every 5-10 minutes.
    Graceful fallback to 6-hour ensemble if nowcast unavailable.
    """
    ...

# Response model
class NowcastResponse(BaseModel):
    location: Location
    issued_at: datetime
    forecasts: List[NowcastPoint]  # 5-min intervals
    ensemble_members: Optional[List[EnsembleMember]]
    confidence: float  # Based on recent verification
    data_sources: List[str]  # ["nexrad", "goes16", "mrms"]
    fallback_used: bool
```

### 5.2 Caching Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    CACHING ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: Edge Cache (Cloudflare/Fastly)                        │
│  ├── TTL: 60 seconds (matching update cycle)                    │
│  ├── Cache key: lat/lon rounded to 0.01 degrees                 │
│  └── Stale-while-revalidate enabled                             │
│                                                                  │
│  LAYER 2: Application Cache (Redis)                             │
│  ├── TTL: 300 seconds                                           │
│  ├── Pre-computed grid: 1km CONUS = ~8M points                  │
│  └── Tile-based caching for map rendering                       │
│                                                                  │
│  LAYER 3: Model Output Cache                                     │
│  ├── Full nowcast grids: 2-hour retention                       │
│  ├── Ensemble members: Lazy generation on request               │
│  └── Verification archive: 7-day retention                      │
│                                                                  │
│  Target: < 500ms API response (< 50ms for cached)               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Failover Strategy

```python
async def get_forecast(lat: float, lon: float, lead_hours: int):
    """
    Intelligent forecast selection with graceful degradation.
    """
    if lead_hours <= 2:  # 0-2 hours: Nowcast preferred
        try:
            nowcast = await nowcast_service.get_forecast(lat, lon)
            if nowcast.is_valid and nowcast.age_minutes < 15:
                return nowcast
        except NowcastUnavailable:
            pass

        # Fallback to ensemble
        logger.warning("Nowcast unavailable, falling back to ensemble")
        return await ensemble_service.get_forecast(lat, lon, lead_hours)

    else:  # 2-72 hours: Standard ensemble
        return await ensemble_service.get_forecast(lat, lon, lead_hours)
```

### 5.4 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [NEXRAD L2]─────┐                                              │
│                   ├──>[Radar Preprocessor]──┐                    │
│   [GOES-16]───────┤                         │                    │
│                   │                         v                    │
│   [MRMS QPE]──────┴──>[Feature Store]──>[Nowcast Model]         │
│                                              │                   │
│                                              v                   │
│   [HRRR Background]──>[Blending]──>[Output Grid]──>[API Cache]  │
│                                              │                   │
│                                              v                   │
│                                         [Verification]           │
│                                              │                   │
│                                              v                   │
│                                   [Skill Score Dashboard]        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Technical Implementation

### 6.1 Language/Framework Decision

**Recommendation**: Python/PyTorch with C++/CUDA optimization for critical paths

| Component | Technology | Justification |
|-----------|------------|---------------|
| Data pipeline | Python + Dask | Parallel processing, PySTEPS compatibility |
| Model training | PyTorch | Best ecosystem, research alignment |
| Model serving | FastAPI + TensorRT | Low latency, GPU optimization |
| Radar processing | C++ bindings | Performance-critical I/O |
| Storage | Apache Arrow + Parquet | Columnar, efficient |

### 6.2 Model Serving Infrastructure

```yaml
# Kubernetes deployment spec (simplified)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vortex-nowcast
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: nowcast-inference
        image: vortex/nowcast:v1.0
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "16Gi"
            cpu: "4"
        env:
        - name: MODEL_PATH
          value: "/models/nowcast_hybrid_v1.pt"
        - name: BATCH_SIZE
          value: "8"
```

### 6.3 Inference Optimization

**Target**: < 30 seconds for full 2-hour forecast

**Optimizations**:
1. **TensorRT conversion**: 2-3x speedup for inference
2. **FP16 quantization**: 2x memory reduction, minor accuracy loss
3. **Batched processing**: Process 8 grid tiles simultaneously
4. **Model pruning**: Remove 30% of weights, minimal skill loss
5. **ONNX export**: Cross-platform deployment

```python
# TensorRT optimization example
import torch_tensorrt

model_trt = torch_tensorrt.compile(
    model,
    inputs=[torch_tensorrt.Input(
        shape=(1, 4, 256, 256),
        dtype=torch.half
    )],
    enabled_precisions={torch.half},
    workspace_size=1 << 30,
)
```

### 6.4 Monitoring & Alerting

```python
METRICS = {
    # Latency metrics
    "nowcast_inference_seconds": Histogram,
    "nowcast_api_latency_ms": Histogram,
    "radar_ingestion_delay_seconds": Gauge,

    # Accuracy metrics (updated hourly)
    "nowcast_csi_60min": Gauge,
    "nowcast_pod_60min": Gauge,
    "nowcast_far_60min": Gauge,

    # System metrics
    "nowcast_model_version": Info,
    "radar_data_age_minutes": Gauge,
    "nowcast_cache_hit_rate": Counter,
}

ALERTS = [
    Alert("NowcastLatencyHigh",
          expr="nowcast_inference_seconds > 60",
          for_="5m"),
    Alert("RadarDataStale",
          expr="radar_data_age_minutes > 30",
          for_="10m"),
    Alert("NowcastSkillDegraded",
          expr="nowcast_csi_60min < 0.4",
          for_="1h"),
]
```

---

## 7. Special Cases & Edge Conditions

### 7.1 Convective Initiation

**Challenge**: Predicting thunderstorm genesis from clear air is the "holy grail" of nowcasting.

**Current SOTA**: FuXi-Nowcast (December 2024) demonstrates improved CI detection by integrating 3D atmospheric fields from FuXi-2.0 with radar/surface observations.

**VortexV2 Approach**:
1. **Satellite features**: Monitor GOES-16 cloud-top cooling rates
2. **Surface convergence**: Track low-level wind patterns from HRRR
3. **Instability indices**: CAPE, CIN from real-time soundings
4. **ML CI classifier**: Random forest probability of CI in next 60 min

**Expected Performance**: 50-60% POD for CI, 30-40% FAR (industry-leading would be 70%+ POD)

### 7.2 Winter Precipitation Type Discrimination

**Challenge**: Distinguishing rain/snow/sleet near 0C is fundamentally limited by physics.

**Research Finding** (UMich 2025): Rain and snow are equally likely between -3C and 5C. ML methods only improve 0.6% over traditional methods.

**VortexV2 Approach**:
1. **Dual-pol radar**: Use ZDR, CC for hydrometeor classification
2. **Temperature profiles**: Integrate HRRR temperature soundings
3. **Surface observations**: Real-time METAR precip type reports
4. **Uncertainty**: Explicitly flag mixed-phase probability

**Output**: Categorical probability (rain: 40%, snow: 35%, sleet: 25%) rather than deterministic type

### 7.3 Fog and Low Cloud Formation

**Challenge**: Fog forms rapidly in localized areas, driven by ground cooling and humidity.

**VortexV2 Approach**:
1. **Satellite-based**: GOES-16 night microphysics RGB (bands 7, 13, 15)
2. **ML detection**: CNN trained on labeled fog events
3. **Persistence-based**: Fog dissipation time estimation
4. **Not included in Phase 1**: Focus on precipitation nowcasting first

### 7.4 Rapid Intensification

**Challenge**: Thunderstorms can intensify from 40 dBZ to 60+ dBZ in 15-30 minutes.

**VortexV2 Approach**:
1. **Growth rate tracking**: Monitor reflectivity gradient evolution
2. **Updraft proxies**: Vertically integrated liquid, echo tops
3. **Lightning data**: Integrate GOES GLM for electrification trends
4. **Adaptive ensemble weights**: Increase uncertainty for rapidly evolving cells

---

## 8. Implementation Roadmap

### Phase 1: MVP (4-6 weeks)

**Goal**: Functional nowcasting with PySTEPS baseline

**Deliverables**:
- [ ] NEXRAD Level-II ingestion pipeline (AWS S3)
- [ ] PySTEPS integration for optical flow extrapolation
- [ ] Basic API endpoint (`/api/v2/nowcast/precipitation`)
- [ ] Redis caching layer
- [ ] MRMS-based verification pipeline
- [ ] Prometheus metrics and Grafana dashboard

**Success Criteria**:
- CSI > 0.35 at 60 minutes (PySTEPS baseline)
- API response < 2 seconds
- 99% uptime for data ingestion

### Phase 2: Production (6-8 weeks)

**Goal**: ML-enhanced nowcasting with uncertainty quantification

**Deliverables**:
- [ ] U-Net refinement network training
- [ ] ConvLSTM temporal encoder integration
- [ ] Ensemble generation (20 members)
- [ ] GOES-16 satellite feature integration
- [ ] TensorRT optimization
- [ ] Edge caching (Cloudflare)
- [ ] Confidence calibration system

**Success Criteria**:
- CSI > 0.50 at 60 minutes (10%+ improvement over Phase 1)
- API response < 500 ms (cached)
- Reliable probabilistic outputs (rank histogram calibrated)

### Phase 3: Advanced (8-12 weeks)

**Goal**: Convective initiation detection, winter weather, severe hazards

**Deliverables**:
- [ ] Convective initiation classifier
- [ ] Winter precipitation type discrimination
- [ ] Severe weather nowcasting (hail, tornado, wind)
- [ ] DGMR-style generative model (optional, research)
- [ ] Transformer architecture exploration
- [ ] Mobile push notifications for severe weather

**Success Criteria**:
- CI POD > 50%
- Winter ptype accuracy > 80%
- DGMR-comparable quality for heavy precipitation

---

## 9. Resource Requirements

### 9.1 Compute

| Resource | Phase 1 | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| Training GPU | 1x V100 | 4x A100 | 8x A100 |
| Inference GPU | 1x T4 | 2x T4 | 4x T4 |
| CPU (data processing) | 8 vCPU | 16 vCPU | 32 vCPU |
| Memory | 32 GB | 64 GB | 128 GB |

### 9.2 Storage

| Data Type | Daily Volume | Monthly Cost (S3) |
|-----------|--------------|-------------------|
| NEXRAD Level-II | ~15 GB | ~$10 |
| GOES-16 subset | ~5 GB | ~$3 |
| MRMS products | ~3 GB | ~$2 |
| Model artifacts | ~1 GB | ~$1 |
| **Total** | ~25 GB/day | **~$20/month** |

### 9.3 Data Acquisition

| Data Source | Cost | Access Method |
|-------------|------|---------------|
| NEXRAD | Free | AWS Open Data |
| GOES-16/17 | Free | AWS Open Data |
| MRMS | Free | NOAA NODD |
| HRRR | Free | AWS Open Data |
| Lightning (GLM) | Free | AWS Open Data |
| **Total** | **$0** | Public data |

### 9.4 Engineering Time

| Phase | Duration | FTE Required |
|-------|----------|--------------|
| Phase 1 | 4-6 weeks | 1.5 FTE |
| Phase 2 | 6-8 weeks | 2.0 FTE |
| Phase 3 | 8-12 weeks | 2.5 FTE |
| **Total** | 18-26 weeks | ~2 FTE average |

---

## 10. Risk Assessment & Mitigation

### 10.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Radar data gaps | Medium | High | MRMS fallback, multi-radar compositing |
| Model skill degradation | Medium | High | Real-time verification, automatic alerts |
| Inference latency issues | Low | Medium | TensorRT, caching, horizontal scaling |
| Training data quality | Medium | Medium | Rigorous QC, holdout validation |

### 10.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AWS data source changes | Low | High | Multi-cloud data access, local caching |
| GPU availability | Low | Medium | Spot instance fallback, CPU inference option |
| Model versioning issues | Medium | Medium | MLflow tracking, blue-green deployment |

### 10.3 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Competition from NWS products | High | Medium | Differentiate with VortexV2 integration |
| User adoption | Medium | High | Free tier, seamless API experience |
| Maintenance burden | Medium | Medium | Automated monitoring, documentation |

---

## 11. References

### Primary Sources

1. Pulkkinen, S., et al. (2019). "Pysteps: an open-source Python library for probabilistic precipitation nowcasting (v1.0)." *Geoscientific Model Development*, 12, 4185-4219. [GMD Paper](https://gmd.copernicus.org/articles/12/4185/2019/)

2. Ravuri, S., et al. (2021). "Skilful precipitation nowcasting using deep generative models of radar." *Nature*, 597, 672-677. [Nature Article](https://www.nature.com/articles/s41586-021-03854-z)

3. Sonderby, C.K., et al. (2020). "MetNet: A Neural Weather Model for Precipitation Forecasting." [Google Research](https://research.google/pubs/metnet-a-neural-weather-model-for-precipitation-forecasting/)

4. Zhang, J., et al. (2016). "Multi-Radar Multi-Sensor (MRMS) Quantitative Precipitation Estimation." *BAMS*, 97(9). [AMS Journal](https://journals.ametsoc.org/view/journals/bams/97/9/bams-d-14-00173.1.xml)

5. Roberts, N. and Lean, H. (2008). "Scale-selective verification of rainfall accumulations from high-resolution forecasts of convective events." [Weather Forecasting Journal](https://journals.ametsoc.org/view/journals/wefo/25/1/2009waf2222260_1.xml)

### Recent Research (2024-2025)

6. "FuXi-Nowcast: Meet the longstanding challenge of convective initiation in nowcasting." arXiv, December 2024.

7. "SwinNowcast: A Swin Transformer-Based Model for Radar-Based Precipitation Nowcasting." MDPI Remote Sensing, 2025.

8. "Hybrid physics-AI outperforms numerical weather prediction for extreme precipitation nowcasting." *npj Climate and Atmospheric Science*, 2024.

---

## 12. Conclusion

This document provides a comprehensive roadmap for implementing a production-grade nowcasting system within VortexV2. The recommended hybrid approach balances proven optical flow techniques with modern ML refinement, ensuring reliable performance while enabling continuous improvement.

**Next Steps**:
1. Review and approve architecture decisions
2. Begin Phase 1 implementation (NEXRAD ingestion + PySTEPS)
3. Establish baseline metrics with MRMS verification
4. Iterate toward Phase 2 ML enhancement

**Document Version**: 1.0
**Last Updated**: 2026-01-16
