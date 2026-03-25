# Standard Operating Procedure: Weather Assessment Workflow

## 7-Step SOP for Sailing Weather Assessment

This is the standard workflow for assessing weather conditions before a passage. Each step must be completed in order. Skipping steps leads to incomplete assessments and potentially dangerous decisions.

### Step 1: GRIB Data Acquisition
- Verify all model GRIB files are fresh (< 6h old for HRRR, < 12h for GFS/ECMWF)
- Check data completeness: all required fields present (u10, v10, msl, swh if offshore)
- If any model data is stale, note it and reduce confidence in that model
- Vortex auto-checks freshness via scheduler; verify via /api/v2/status

### Step 2: Data Integrity Verification
- Confirm observation data from NDBC buoys and Copernicus stations is flowing
- Cross-check: do current observations match the most recent model initialization?
- If observations diverge significantly from model nowcast, models may be initialized poorly
- Check competition scoring: are accuracy metrics reasonable? (direction MAE should be < 60 degrees; if > 90 degrees, data is corrupted not the model)

### Step 3: Synoptic Assessment
- Identify the large-scale weather pattern (ridge, trough, zonal flow, blocking)
- Locate all fronts, lows, and highs within 1000nm of planned track
- Assess pattern evolution: is it progressive (moving through) or stalled?
- Progressive patterns are more predictable; stalled patterns create extended uncertainty

### Step 4: Model Spread Analysis
- Compare wind speed and direction across all available models at key waypoints
- Calculate spread at departure, midpoint, and arrival
- Spread < 3 kt: high confidence
- Spread 3-5 kt: moderate confidence, check synoptic context
- Spread > 5 kt: low confidence, investigate cause, consider delaying
- Pay special attention to wind DIRECTION spread — direction errors affect routing more than speed errors

### Step 5: Route Optimization
- Use ensemble forecast (field-level best model selection) for primary routing
- Generate alternative routes if model spread is moderate-high
- Consider: upwind penalty, wave state, current effects, harbor approaches
- Time waypoints to avoid known problem areas (headlands, straits) in adverse conditions
- For offshore passages, optimize for VMG not shortest distance

### Step 6: Risk Assessment
- Identify worst-case scenario from model ensemble
- Calculate safety margin: how much worse can conditions get before route is untenable?
- Identify bail-out ports along the route
- Assess crew experience level against forecast conditions
- Check for any marine warnings or advisories in the passage area

### Step 7: Briefing Generation
- Summarize conditions in plain language: departure conditions, en-route changes, arrival conditions
- Highlight key decision points: "If wind exceeds X at waypoint Y, divert to Z"
- Include confidence level for each phase of the passage
- Note the next model run time — when will better information be available?
- Specify go/no-go criteria and the decision deadline

## Iteration
After Step 7, if confidence is not sufficient:
- Wait for next model run (GFS every 6h, ECMWF every 6h)
- Re-run from Step 1
- If three consecutive assessments show improving convergence, confidence is building
- If assessments show increasing spread, delay departure
