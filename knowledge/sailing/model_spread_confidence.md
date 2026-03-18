# Model Spread and Forecast Confidence Assessment

## When Model Spread Matters

Model spread is the difference between the highest and lowest wind speed forecasts from different NWP models at the same location and time. It is the single most important indicator of forecast confidence for sailing decisions.

## Spread Thresholds

### Low Spread (< 3 kt difference)
- Confidence: HIGH
- All models agree on wind conditions
- Safe to make routing decisions based on any single model
- Ensemble output is highly reliable
- Action: Proceed with planned route

### Moderate Spread (3-5 kt difference)
- Confidence: MEDIUM
- Models show general agreement but differ on intensity
- Check which model is the outlier
- Look at the synoptic chart to understand WHY models diverge
- Action: Plan for the range, carry appropriate sail selection for both ends

### High Spread (> 5 kt difference)
- Confidence: LOW
- Models fundamentally disagree on conditions
- MUST check the synoptic chart before making decisions
- Common causes: frontal timing differences, convective uncertainty, model initialization disagreement
- Action: Delay departure if possible, or plan conservative route assuming worst case

### Very High Spread (> 10 kt difference)
- Confidence: VERY LOW
- Active weather situation with high uncertainty
- Often indicates approaching front, developing low, or rapid cyclogenesis
- Action: Do NOT depart. Wait for model convergence (usually 12-24h before event)

## Synoptic Patterns That Cause High Spread

1. **Frontal passages**: Models disagree on frontal timing by 6-12h, causing huge wind differences at any given forecast hour
2. **Lee cyclogenesis**: Developing lows in the lee of mountain ranges are notoriously hard to predict
3. **Tropical transitions**: Subtropical systems gaining or losing tropical characteristics
4. **Jet streak interactions**: Upper-level dynamics affecting surface wind through pressure gradient changes
5. **Convective initiation**: Thunderstorm outflow boundaries are essentially unpredictable beyond 6h

## How Vortex Ensemble Handles Spread

Vortex does NOT simply average model forecasts. It selects the winning model PER FIELD based on recent competition accuracy:
- If HRRR has best recent wind_speed accuracy but GFS has best wind_direction accuracy, ensemble uses HRRR wind_speed + GFS wind_direction
- This field-level selection outperforms simple averaging because model skill varies by parameter
- High model spread means the field selection matters MORE, not less
