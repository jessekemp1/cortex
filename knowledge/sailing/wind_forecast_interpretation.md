# Wind Forecast Interpretation for Sailing

## Model Strengths by Range and Domain

### HRRR (High-Resolution Rapid Refresh)
- Best for: Short-range coastal forecasts (0-18h)
- Resolution: 3km grid spacing
- Update frequency: Hourly
- Strengths: Captures sea breeze, coastal convergence, convective outflow
- Weaknesses: Limited offshore domain (CONUS only), no wave data
- Use when: Planning coastal departures, harbor approaches, or inshore racing within 12h

### ECMWF (European Centre for Medium-Range Weather Forecasts)
- Best for: Offshore and medium-range forecasts (24-120h)
- Resolution: 9km (HRES), ensemble at 18km
- Update frequency: 6-hourly
- Strengths: Superior synoptic-scale accuracy, best pressure gradient forecasts, reliable for ocean passages
- Weaknesses: Can miss mesoscale coastal effects, slower update cycle
- Use when: Planning offshore passages, multi-day routing, assessing weather windows

### GFS (Global Forecast System)
- Best for: Reliable backup and global coverage
- Resolution: 13km (0.125 degree)
- Update frequency: 6-hourly
- Strengths: Consistent global coverage, good for large-scale pattern recognition, free and widely available
- Weaknesses: Lower resolution than ECMWF, can be slow to capture rapid development
- Use when: Cross-checking ECMWF, global routing, or when other models unavailable

## Wind Speed Interpretation for Sailing

### Beaufort Scale Quick Reference
- 0-3 kt: Calm to light air — motorsailing likely
- 4-6 kt: Light breeze — large genoa, patience required
- 7-10 kt: Gentle breeze — ideal light-air sailing
- 11-16 kt: Moderate breeze — optimal cruising conditions
- 17-21 kt: Fresh breeze — first reef consideration
- 22-27 kt: Strong breeze — reef main, smaller headsail
- 28-33 kt: Near gale — deep reef, storm jib
- 34+ kt: Gale conditions — survival tactics

### Model Bias Awareness
- GFS tends to under-predict light winds and over-predict strong winds by 1-2 kt
- ECMWF has best calibration overall but can miss local thermal effects
- HRRR captures thermal winds (sea breeze) that other models miss entirely
- All models struggle with wind in complex terrain (islands, straits, headlands)
- EMOS calibration improves raw model output by 23-30% CRPS when active
