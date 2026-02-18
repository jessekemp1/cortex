# Cortex Metrics System

**Version**: 1.0  
**Status**: Production  
**Last Updated**: 2025-12-23

---

## Overview

Cortex tracks 4 key metrics to measure system effectiveness and demonstrate ROI:

1. **Velocity**: Development time savings
2. **Mistakes**: Prevention of repeated mistakes
3. **Calibration**: Prediction accuracy
4. **ROI**: Investment vs benefits

All metrics are stored in `~/.claude/portfolio/metrics.json`.

---

## Metrics Tracker API

### Initialization

```python
from cortex.metrics_tracker import MetricsTracker

tracker = MetricsTracker()
```

---

## 1. Velocity Tracking

Measures development time savings by comparing baseline estimates to actual time with Cortex.

### `record_velocity(task, time_without_cortex, time_with_cortex, project, notes="")`

Record a velocity measurement.

**Parameters**:
- `task`: Task description
- `time_without_cortex`: Estimated time without Cortex (minutes)
- `time_with_cortex`: Actual time with Cortex (minutes)
- `project`: Project name
- `notes`: Optional context

**Returns**: Savings in minutes

**Example**:
```python
savings = tracker.record_velocity(
    task="Implement API rate limiting",
    time_without_cortex=60,  # Would take 1 hour without Cortex
    time_with_cortex=20,     # Actually took 20 minutes
    project="cortex",
    notes="Used spec search to find existing pattern"
)
# Returns: 40 (minutes saved)
```

### `get_velocity_stats(days=30)`

Get velocity statistics for the last N days.

**Returns**: Dict with:
- `total_tasks`: Number of tasks tracked
- `total_savings_minutes`: Total time saved
- `avg_improvement_pct`: Average improvement percentage
- `tasks`: List of recent tasks

**Example**:
```python
stats = tracker.get_velocity_stats(days=7)
# Returns: {
#   "total_tasks": 10,
#   "total_savings_minutes": 240,
#   "avg_improvement_pct": 81.5,
#   "tasks": [...]
# }
```

---

## 2. Mistake Prevention

Tracks whether lessons learned prevented mistakes from being repeated.

### `record_mistake(mistake_type, was_prevented, lesson_id, project, impact_minutes, notes="")`

Record a mistake event (prevented or not).

**Parameters**:
- `mistake_type`: Category of mistake (e.g., "data_validation")
- `was_prevented`: Whether Cortex prevented the mistake
- `lesson_id`: ID of lesson that applied (if prevented)
- `project`: Project name
- `impact_minutes`: Time that would have been lost
- `notes`: Optional context

**Returns**: None

**Example**:
```python
tracker.record_mistake(
    mistake_type="data_validation",
    was_prevented=True,
    lesson_id="grib_index_check",
    project="VortexV2",
    impact_minutes=60,
    notes="Remembered to check GRIB index before download"
)
```

### `get_mistake_stats(days=30)`

Get mistake prevention statistics.

**Returns**: Dict with:
- `total_mistakes`: Total mistakes encountered
- `prevented_count`: Number prevented
- `prevention_rate`: Prevention percentage
- `total_time_saved`: Time saved by prevention

**Example**:
```python
stats = tracker.get_mistake_stats(days=30)
# Returns: {
#   "total_mistakes": 5,
#   "prevented_count": 4,
#   "prevention_rate": 80.0,
#   "total_time_saved": 240
# }
```

---

## 3. Calibration Tracking

Measures prediction accuracy (confidence vs actual outcomes).

### `record_prediction(prediction_id, task, predicted_outcome, confidence, predicted_time, project)`

Record a prediction.

**Parameters**:
- `prediction_id`: Unique prediction identifier
- `task`: Task description
- `predicted_outcome`: Expected outcome (e.g., "success", "failure")
- `confidence`: Confidence level (0.0-1.0)
- `predicted_time`: Predicted time in minutes
- `project`: Project name

**Returns**: None

**Example**:
```python
tracker.record_prediction(
    prediction_id="pred_001",
    task="Implement integration",
    predicted_outcome="success",
    confidence=0.85,
    predicted_time=30,
    project="cortex"
)
```

### `record_outcome(prediction_id, actual_outcome, actual_time)`

Record the actual outcome for a prediction.

**Parameters**:
- `prediction_id`: Prediction identifier
- `actual_outcome`: Actual outcome
- `actual_time`: Actual time in minutes

**Returns**: None

**Example**:
```python
tracker.record_outcome(
    prediction_id="pred_001",
    actual_outcome="success",
    actual_time=25
)
```

### `get_calibration_stats(days=30)`

Get calibration statistics.

**Returns**: Dict with:
- `total_predictions`: Number of predictions
- `accuracy`: Prediction accuracy percentage
- `calibration_curve`: Confidence vs accuracy mapping
- `time_accuracy`: Time prediction accuracy

**Example**:
```python
stats = tracker.get_calibration_stats(days=30)
# Returns: {
#   "total_predictions": 10,
#   "accuracy": 80.0,
#   "calibration_curve": {...},
#   "time_accuracy": 75.0
# }
```

---

## 4. ROI Tracking

Measures return on investment (time invested vs time saved).

### `record_investment(activity, time_minutes, category)`

Record time invested in Cortex.

**Parameters**:
- `activity`: Description of activity
- `time_minutes`: Time spent in minutes
- `category`: Category (e.g., "setup", "maintenance")

**Returns**: None

**Example**:
```python
tracker.record_investment(
    activity="Week 1 setup",
    time_minutes=42,
    category="setup"
)
```

### `record_benefit(source, time_saved_minutes)`

Record time saved from Cortex.

**Parameters**:
- `source`: Source of benefit (e.g., "velocity_improvement", "mistake_prevention")
- `time_saved_minutes`: Time saved in minutes

**Returns**: None

**Example**:
```python
tracker.record_benefit(
    source="velocity_improvement",
    time_saved_minutes=240
)
```

### `get_roi_stats()`

Get ROI statistics.

**Returns**: Dict with:
- `total_investment_minutes`: Total time invested
- `total_benefits_minutes`: Total time saved
- `net_minutes`: Net benefit (saved - invested)
- `roi_ratio`: ROI ratio (benefits / investment)
- `break_even`: Whether system has broken even

**Example**:
```python
roi = tracker.get_roi_stats()
# Returns: {
#   "total_investment_minutes": 42,
#   "total_benefits_minutes": 240,
#   "net_minutes": 198,
#   "roi_ratio": 5.71,
#   "break_even": True
# }
```

---

## Unified Dashboard

### `get_dashboard(days=30)`

Get unified dashboard with all metrics.

**Parameters**:
- `days`: Number of days to analyze

**Returns**: Dict with all metric summaries

**Example**:
```python
dashboard = tracker.get_dashboard(days=7)
# Returns: {
#   "velocity": {...},
#   "mistakes": {...},
#   "calibration": {...},
#   "roi": {...},
#   "summary": {
#     "total_savings": 240,
#     "roi_ratio": 5.71,
#     "break_even": True
#   }
# }
```

---

## Data Storage

All metrics are stored in `~/.claude/portfolio/metrics.json`:

```json
{
  "meta": {
    "created_at": "2025-12-23T...",
    "last_updated": "2025-12-23T...",
    "version": "1.0"
  },
  "velocity": [
    {
      "timestamp": "2025-12-23T...",
      "task": "Implement feature X",
      "project": "cortex",
      "baseline_minutes": 60,
      "actual_minutes": 20,
      "savings_minutes": 40,
      "improvement_pct": 66.7,
      "notes": "..."
    }
  ],
  "mistakes": [...],
  "calibration": [...],
  "roi": [...]
}
```

---

## Best Practices

1. **Record velocity for every significant task**
   - Estimate baseline honestly
   - Record actual time accurately
   - Include notes about what helped

2. **Track mistakes proactively**
   - Record when you catch a mistake before it causes problems
   - Link to lesson IDs when applicable
   - Estimate impact honestly

3. **Use predictions for planning**
   - Record predictions before starting work
   - Record outcomes after completion
   - Review calibration regularly

4. **Track investment honestly**
   - Record setup time
   - Record maintenance time
   - Don't inflate benefits

5. **Review dashboard weekly**
   - Check ROI status
   - Identify trends
   - Adjust usage patterns

---

## Example Workflow

```python
from cortex.metrics_tracker import MetricsTracker

tracker = MetricsTracker()

# Before starting task
tracker.record_prediction(
    prediction_id="task_001",
    task="Add dependency visualization",
    predicted_outcome="success",
    confidence=0.90,
    predicted_time=120,
    project="cortex"
)

# After completing task
tracker.record_velocity(
    task="Add dependency visualization",
    time_without_cortex=180,  # Would take 3 hours without Cortex
    time_with_cortex=120,     # Actually took 2 hours
    project="cortex",
    notes="Used existing dependency mapper, added visualization methods"
)

tracker.record_outcome(
    prediction_id="task_001",
    actual_outcome="success",
    actual_time=120
)

# Weekly review
dashboard = tracker.get_dashboard(days=7)
print(f"ROI: {dashboard['roi']['roi_ratio']:.2f}x")
print(f"Total savings: {dashboard['summary']['total_savings']} minutes")
```

---

## Performance

- **Recording**: <1ms per operation
- **Dashboard generation**: <10ms
- **Storage**: JSON file, human-readable
- **Backup**: File can be manually backed up

---

## References

- Metrics Tracker source: `cortex/metrics_tracker.py`
- [Architecture Documentation](ARCHITECTURE.md)
- [API Documentation](API.md)
