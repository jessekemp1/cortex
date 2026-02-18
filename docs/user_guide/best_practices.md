# Cortex Best Practices

**Optimization tips and best practices for using Cortex**

This guide provides best practices for getting the most value from Cortex.

---

## Table of Contents

1. [Daily Workflow](#daily-workflow)
2. [Pattern Documentation](#pattern-documentation)
3. [Lesson Recording](#lesson-recording)
4. [Metrics Tracking](#metrics-tracking)
5. [Spec Indexing](#spec-indexing)
6. [Performance Tips](#performance-tips)

---

## Daily Workflow

### Morning Routine

**Best Practice**: Start each day with context

```bash
# 1. Get session context (automatic via hook)
# 2. Review portfolio stats
python bridge.py portfolio stats

# 3. Check metrics dashboard
python3 -c "from metrics_tracker import MetricsTracker; print(MetricsTracker().get_dashboard(days=7))"
```

**Why**: Orients you to current state and recent progress

---

### Before Starting Work

**Best Practice**: Search for similar work first

```bash
# Search before implementing
python bridge.py intelligence similar-work "your task" --project yourproject
```

**Why**: Avoids reinventing the wheel, finds existing patterns

---

### After Completing Work

**Best Practice**: Track metrics and document patterns

```python
# Track velocity
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()
tracker.record_velocity(
    task="Implemented feature X",
    time_without_cortex=60,
    time_with_cortex=20,
    project="yourproject"
)

# Document successful pattern (if reusable)
# Add to portfolio memory via patterns.json or API
```

**Why**: Builds compound learning, improves future recommendations

---

## Pattern Documentation

### When to Document Patterns

**Document patterns when**:
- Approach used successfully in 2+ projects
- Approach has measurable success metrics
- Approach is reusable across projects

**Example**:
```python
# Add pattern to portfolio memory
from portfolio_memory import PortfolioMemory

pm = PortfolioMemory()
pm.add_pattern(
    name="Async FastAPI Pattern",
    category="api",
    description="Async endpoints with proper error handling",
    projects=["VortexV2", "AlphaArena"],
    success_metrics={"uptime": "99.9%", "response_time": "<100ms"}
)
```

---

### Pattern Quality

**Good patterns include**:
- Clear description
- Implementation steps
- Success metrics
- Context (when to use)
- Lessons learned

**Example**:
```json
{
  "name": "GRIB Data Processing Pipeline",
  "category": "data_processing",
  "description": "Multi-stage pipeline for GRIB weather data",
  "context": "Processing large-scale meteorological data",
  "implementation": {
    "stage1": "Download with Herbie",
    "stage2": "Decode with eccodes",
    "stage3": "Validate data quality",
    "stage4": "Store in PostgreSQL"
  },
  "success_metrics": {
    "throughput": "~100 GRIB files/hour",
    "error_rate": "<1%"
  },
  "lessons_learned": ["Always validate before decoding"],
  "projects": ["VortexV2"]
}
```

---

## Lesson Recording

### When to Record Lessons

**Record lessons when**:
- You make a mistake that could be prevented
- You prevent a mistake using a lesson
- You discover a new prevention strategy

**Example**:
```python
from portfolio_memory import PortfolioMemory

pm = PortfolioMemory()
pm.add_lesson(
    title="Always check GRIB index files",
    category="data_validation",
    mistake="Downloaded 50GB without verifying",
    prevention="Use Herbie.inv() before download",
    project="VortexV2"
)
```

---

### Lesson Quality

**Good lessons include**:
- Clear mistake description
- Specific prevention strategy
- Context (when it applies)
- Impact (time/cost saved)

---

## Metrics Tracking

### Track Velocity Consistently

**Best Practice**: Track velocity for every significant task

```python
from metrics_tracker import MetricsTracker

tracker = MetricsTracker()

# Before starting: Estimate baseline
baseline_estimate = 120  # 2 hours

# After completing: Record actual
tracker.record_velocity(
    task="Implemented feature X",
    time_without_cortex=baseline_estimate,
    time_with_cortex=30,  # Actual time
    project="yourproject",
    notes="Used spec search to find existing pattern"
)
```

**Why**: Builds accurate ROI metrics, improves recommendations

---

### Track Mistake Prevention

**Best Practice**: Record when lessons prevent mistakes

```python
tracker.record_mistake(
    mistake_type="data_validation",
    was_prevented=True,
    lesson_id="grib_index_check",
    project="VortexV2",
    impact_minutes=60,
    notes="Remembered to check GRIB index first"
)
```

**Why**: Measures value of portfolio memory, improves lesson relevance

---

### Track Predictions

**Best Practice**: Record predictions and outcomes

```python
# Record prediction
prediction_id = "pred_001"
tracker.record_prediction(
    prediction_id=prediction_id,
    task="Implement feature",
    predicted_outcome="success",
    confidence=0.85,
    predicted_time=30,
    project="cortex"
)

# Later, record outcome
tracker.record_outcome(
    prediction_id=prediction_id,
    actual_outcome="success",
    actual_time=25
)
```

**Why**: Improves calibration, makes predictions more accurate

---

## Spec Indexing

### Index All Documentation

**Best Practice**: Index all project documentation

```bash
# Index architecture docs
python bridge.py index-spec docs/ARCHITECTURE.md --project cortex

# Index API docs
python bridge.py index-spec docs/API.md --project cortex

# Index design specs
python bridge.py index-spec DESIGN_SPEC.md --project cortex
```

**Why**: Enables semantic search across all documentation

---

### Keep Specs Updated

**Best Practice**: Re-index when specs change

```bash
# Force re-index
python bridge.py index-spec docs/ARCHITECTURE.md --project cortex --force

# Or index automatically on file change (future feature)
```

**Why**: Ensures search results are current

---

## Performance Tips

### Use Caching

**Best Practice**: Leverage built-in caching

```python
# Session context cached for 1 hour
context = bridge.get_session_context()  # Fast, cached

# Portfolio stats cached in memory
stats = bridge.get_portfolio_stats()  # Fast, cached
```

---

### Batch Operations

**Best Practice**: Batch similar operations

```python
# Instead of multiple individual calls
for project in projects:
    health = bridge.get_dependency_health(project)

# Use batch operation (if available)
portfolio_health = bridge.get_portfolio_health_summary()
```

---

### Lazy Loading

**Best Practice**: Initialize only what you need

```python
# Components initialize lazily
bridge = CortexBridge()  # Fast, components not loaded yet

# Load only when needed
if bridge.spec_kb:  # Only initialized if needed
    results = bridge.search_specs("query")
```

---

## Workflow Optimization

### Automate Routine Tasks

**Best Practice**: Automate daily routines

```bash
# Morning briefing script
#!/bin/bash
python bridge.py session-context
python bridge.py portfolio stats
```

**Why**: Saves time, ensures consistency

---

### Use Session Hooks

**Best Practice**: Set up automatic context injection

```bash
# ~/.claude/hooks/SessionStart.compact.sh
#!/bin/bash
cd ~/Dev/cortex
python3 bridge.py session-context 2>/dev/null
```

**Why**: Automatic context on every session start

---

## Data Management

### Regular Backups

**Best Practice**: Backup data regularly

```bash
# Daily backup script
tar -czf ~/cortex_backups/cortex_$(date +%Y%m%d).tar.gz ~/.claude/ ~/.cortex/
```

**Why**: Protects against data loss

---

### Clean Old Data

**Best Practice**: Clean old metrics periodically

```python
from metrics_tracker import MetricsTracker

tracker = MetricsTracker()
deleted = tracker.cleanup_old_metrics(days=90)  # Keep last 90 days
print(f"Deleted {deleted} old metrics")
```

**Why**: Prevents data bloat, maintains performance

---

## Integration Best Practices

### Use Bridge API

**Best Practice**: Use Bridge API for all access

```python
# Good: Use Bridge API
from cortex.bridge import CortexBridge
bridge = CortexBridge()
stats = bridge.get_portfolio_stats()

# Avoid: Direct module access (unless necessary)
from portfolio_memory import PortfolioMemory
pm = PortfolioMemory()  # Only if you need direct access
```

**Why**: Consistent interface, error handling, performance

---

### Error Handling

**Best Practice**: Always check for errors

```python
result = bridge.get_portfolio_stats()
if "error" in result:
    print(f"Error: {result['error']}")
    # Handle error appropriately
    return

# Use result safely
print(f"Total projects: {result['total_projects']}")
```

**Why**: Prevents crashes, enables graceful degradation

---

## Next Steps

- [Examples](examples.md) - See these practices in action
- [Advanced Usage](advanced_usage.md) - Advanced features
- [API Documentation](../API.md) - Complete API reference

---

**Version**: 1.0  
**Last Updated**: 2025-12-24
