# EMOS Calibration for Marine Weather Forecasting

## What is EMOS?

EMOS (Ensemble Model Output Statistics) is a statistical post-processing technique that calibrates raw NWP model output against recent observations. It corrects systematic biases and provides calibrated uncertainty estimates.

## Current Vortex EMOS Status

- Active models: 3 (GFS, ECMWF, HRRR)
- Calibration method: Lead-time stratified (separate calibration coefficients for each forecast lead time)
- Performance improvement: +23-30% CRPS compared to raw ensemble output
- Observation sources: NDBC buoys (23 stations) + Copernicus (9 stations), 14 regions
- Competition pairs: 300,000+ accumulated
- Persistence calibration: Stale flag implemented to prevent using outdated coefficients

## How EMOS Improves Forecasts

### Bias Correction
Raw model output often has systematic biases:
- GFS over-predicts strong winds by 1-2 kt
- HRRR can under-predict overnight wind drops in coastal areas
- ECMWF has slight cold bias affecting thermal wind patterns
EMOS learns these biases from recent observation-forecast pairs and corrects them.

### Spread Calibration
Raw ensemble spread is often under-dispersive (too confident). EMOS calibrates the spread to match observed forecast error distributions, giving more reliable uncertainty estimates.

### Lead-Time Stratification
Forecast skill degrades with lead time. EMOS calibration coefficients are stratified by lead time:
- 0-6h lead time: Coefficients emphasize recent observation persistence
- 6-24h: Coefficients balance model dynamics with statistical correction
- 24-72h: Coefficients rely more on model dynamics, less on persistence
- 72h+: Minimal correction, model physics dominates

## When EMOS is Most Valuable

1. **Departure decisions**: Calibrated uncertainty estimates tell you not just the forecast, but how confident to be
2. **Light wind forecasts**: Raw models often struggle below 8 kt; EMOS corrects systematic biases in this regime
3. **Post-frontal conditions**: Models consistently under-predict wind speed jumps during frontal passages; EMOS learns this
4. **Overnight coastal winds**: Land-sea breeze transitions are systematically mis-handled by coarse models; EMOS compensates

## When EMOS Cannot Help

1. **Novel weather patterns**: EMOS learns from recent history; truly unprecedented conditions have no training data
2. **Stale calibration**: If observations stop flowing, EMOS coefficients become outdated (stale flag prevents this)
3. **Wrong model physics**: EMOS corrects statistical biases, not fundamental model errors in storm track prediction
4. **Sparse observation areas**: EMOS needs observation-forecast pairs; open ocean with no buoys = no calibration data

## Interpreting EMOS-Calibrated Output

- Point forecast: Best estimate after bias correction
- Prediction interval (10th-90th percentile): 80% of observations should fall within this range
- If observed conditions consistently fall outside the prediction interval, EMOS recalibration is needed
- Narrow interval = high confidence; wide interval = uncertain conditions
- CRPS score < 2.0 kt for wind speed indicates well-calibrated output
