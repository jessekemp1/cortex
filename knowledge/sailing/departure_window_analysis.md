# Departure Window Analysis Patterns

## Core Principle

A departure window is a period where forecast conditions are acceptable for the planned passage AND forecast confidence is sufficient to commit. Both criteria must be met.

## Convergence-Based Window Detection

### The 12-24h Convergence Rule
The most reliable departure windows appear when model forecasts converge as the departure time approaches:
- At T-48h: Models may show 8+ kt spread — too uncertain
- At T-24h: Spread narrows to 3-5 kt — window forming
- At T-12h: Spread under 3 kt — high confidence, commit to departure

If models DIVERGE as departure approaches (spread increasing), the weather situation is becoming MORE uncertain, not less. Delay.

### Forecast Run Consistency
Compare the same model across consecutive runs:
- GFS 00Z shows 15 kt, GFS 06Z shows 14 kt, GFS 12Z shows 15 kt = consistent, trustworthy
- GFS 00Z shows 15 kt, GFS 06Z shows 22 kt, GFS 12Z shows 12 kt = flip-flopping, DO NOT trust
- ECMWF is more stable run-to-run than GFS; if ECMWF is consistent, weight it heavily

## Passage Duration Considerations

### Short Passages (< 12h)
- Can use HRRR as primary guidance (within its domain)
- Single weather regime expected
- Key risk: afternoon sea breeze or evening wind drop
- Window: Look for stable morning conditions with no frontal passage expected

### Medium Passages (12-36h)
- ECMWF should be primary guidance
- May transit through one weather regime change
- Key risk: frontal timing error causing conditions to arrive 6-12h early
- Window: Depart with at least 12h of good conditions forecast, arrival conditions secondary

### Long Passages (36h+)
- ECMWF ensemble spread is critical
- Multiple regime changes likely
- Key risk: developing systems not in current model initialization
- Window: Look for large-scale pattern stability (blocking high, persistent ridge)

## Red Flags (Do Not Depart)

1. Model spread > 10 kt at any point during passage
2. Models disagree on frontal passage timing by > 12h
3. Gale warnings in adjacent forecast areas
4. ECMWF ensemble shows bimodal distribution (half members show calm, half show gale)
5. Rapidly deepening low within 500nm of track
6. Any model showing > 35 kt at any waypoint

## Green Flags (Good Window)

1. All models within 3 kt for first 24h
2. Consistent forecasts across last 3 model runs
3. High pressure dominant along track
4. No frontal passages expected within passage duration + 12h buffer
5. EMOS-calibrated ensemble confidence > 0.8
