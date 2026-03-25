# Vortex Ensemble: Field-Level Model Selection

## How Vortex Ensemble Works

Vortex uses a fundamentally different approach from traditional ensemble averaging. Instead of blending all model outputs, it selects the BEST model for each individual forecast field based on recent competition accuracy.

## Field-Level Selection Explained

### The Problem with Averaging
Simple model averaging (e.g., mean of GFS, ECMWF, HRRR wind speed) destroys signal. If HRRR correctly forecasts 20 kt and GFS incorrectly forecasts 10 kt, the average of 15 kt is wrong by 5 kt in both directions. Neither model predicted 15 kt.

### Field-Level Competition
Vortex continuously scores each model's accuracy against real observations from NDBC buoys and Copernicus stations. Scoring happens PER FIELD:
- wind_speed: Which model has lowest MAE for wind speed in last 6 hours?
- wind_direction: Which model has lowest circular MAE for direction?
- wave_height: Which model best predicts significant wave height?
- pressure: Which model has best surface pressure accuracy?

### Selection Mechanism
At each location and forecast time:
1. Look up the winning model for each field from recent competition results
2. Take wind_speed from the model that won the wind_speed competition
3. Take wind_direction from the model that won the wind_direction competition
4. And so on for each field

This means the ensemble output might use HRRR wind_speed + GFS wind_direction + ECMWF wave_height — the best of each.

### Why This Works
- Different models have different strengths: HRRR excels at wind speed near coastlines but has no wave data
- Model skill varies by parameter: a model might nail wind speed but struggle with direction
- Field-level selection captures these per-parameter strengths automatically
- The competition scoring adapts as conditions change (e.g., during frontal passages, different models may temporarily become more accurate)

## Data Quality Requirements

Because ensemble selection depends entirely on competition accuracy:
- Competition data MUST be 100% accurate — contaminated data leads to wrong model selection
- Synthetic or backfilled observations must be excluded from competition scoring
- If one model shows 3x worse metrics than peers, investigate the DATA first, not the model
- Direction MAE > 90 degrees is a mathematical impossibility for real predictions — it means data corruption (random noise on a circle has expected MAE of exactly 90 degrees)

## EMOS Calibration Enhancement

EMOS (Ensemble Model Output Statistics) applies post-processing to the field-level ensemble:
- Calibrates the ensemble output against recent observation errors
- Improves CRPS (Continuous Ranked Probability Score) by 23-30% when active
- Currently active for 3 models with lead-time stratification
- Provides calibrated prediction intervals (not just point forecasts)
- Essential for confidence estimation in departure window analysis

## Practical Implications for Sailors

1. The Vortex ensemble is NOT a consensus forecast — it is an optimized selection
2. When model spread is high, the ensemble's value increases (it picks the best signal from noise)
3. Trust the ensemble more at locations with rich competition history (many observation pairs)
4. At locations with sparse observations, the ensemble reverts to ECMWF as default (most reliable)
5. Competition accuracy degrades over time without fresh observations — stale competition data = stale ensemble
