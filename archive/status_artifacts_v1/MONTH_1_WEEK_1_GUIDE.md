# Month 1, Week 1: Development Velocity Calibration

**Goal**: Record 20 development task predictions to establish calibration baseline
**Timeline**: 2 weeks (10 tasks/week average)
**Effort**: 2-3 minutes per task (start + completion)

---

## 🎯 OBJECTIVE

Measure your ability to predict:
1. **Task duration** (estimated vs actual time)
2. **Confidence calibration** (how accurate are your confidence levels?)
3. **Cortex impact** (time saved when using spec search/patterns)

---

## 🚀 QUICK START

### Before Starting a Task

```bash
cd ~/Dev/cortex
python3 start_calibration.py
```

**You'll be prompted for**:
- Task description (e.g., "Add validation to forecast API")
- Project (VortexV2/AlphaArena/Cortex)
- Baseline time estimate (WITHOUT using Cortex)
- Confidence level (0.50-0.95)
- Will you use Cortex? (y/n)

**Example**:
```
Task description: Add validation to forecast ingestion endpoint
Project: VortexV2
Baseline time (minutes): 45
Confidence (0.50-0.95): 0.75
Use Cortex? (y/n): y

✅ Prediction recorded: task_20251223_143022
📋 When task is complete, run:
   python3 complete_task.py
```

---

### After Completing the Task

```bash
python3 complete_task.py
```

**You'll be prompted for**:
- Actual time taken
- Outcome (success/partial/failure)
- Notes (what helped or hindered)

**Example**:
```
Actual time taken (minutes): 28
Outcome: success
Notes: Found existing validation pattern in spec search, saved 17 minutes

✅ Task complete!
   Predicted: 45 min
   Actual: 28 min
   Difference: -17 min (-37.8%)
   🎉 Saved 17 minutes with Cortex!
```

---

## 📋 TRACKING PROGRESS

### Check Current Status

```python
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()

# Get calibration data
cal_data = tracker.get_calibration_data()
print(f"Predictions recorded: {len(cal_data['predictions'])}")
print(f"Completed: {len(cal_data['outcomes'])}")
print(f"Pending: {len(cal_data['predictions']) - len(cal_data['outcomes'])}")

# Get velocity stats
vel_stats = tracker.get_velocity_stats()
print(f"\nVelocity tasks tracked: {vel_stats['total_tasks']}")
print(f"Average improvement: {vel_stats['avg_improvement_pct']:.1f}%")
```

---

## 🎯 WEEK 1-2 TARGETS

**Quantity**:
- [ ] 20+ predictions recorded
- [ ] 20+ outcomes recorded (complete all tasks)
- [ ] Mix of task types (bugs, features, docs, refactoring)

**Quality**:
- [ ] Honest baseline estimates (don't sandbag)
- [ ] Realistic confidence levels
- [ ] Detailed notes on what helped/hindered

**Analysis** (End of Week 2):
- [ ] Compute calibration curve
- [ ] Identify systematic biases (overconfident? pessimistic?)
- [ ] Measure Cortex impact (average time saved)

---

## 💡 TIPS FOR GOOD CALIBRATION DATA

### 1. Be Honest with Baseline Estimates
**Don't do this**: "Would take 60 min without Cortex, but I'll say 30 min"
**Do this**: "Honestly, without spec search, I'd spend 20 min figuring it out, then 40 min implementing = 60 min baseline"

### 2. Calibrate Your Confidence
**0.50**: Coin flip, no idea
**0.70**: Somewhat confident, could be off by 50%
**0.80**: Confident, likely within 20-30%
**0.90**: Very confident, likely within 10-20%
**0.95**: Extremely confident, certain within 10%

### 3. Note What Made You Faster/Slower
**Good notes**:
- "Found GRIB validation pattern in spec search, saved 15 min"
- "Forgot to check lessons, repeated API retry mistake, lost 20 min"
- "No spec search used, implemented from scratch, took full baseline time"

**Bad notes**:
- "Done"
- "OK"
- (empty)

---

## 📊 EXAMPLE CALIBRATION SESSION

### Day 1: 2 Tasks

**Task 1**: Add new FastAPI endpoint for lake-specific forecasts
- Baseline: 60 min (would research FastAPI patterns, write from scratch)
- Confidence: 0.75
- Used Cortex: Yes (searched "FastAPI endpoint" in specs)
- Actual: 35 min (found existing pattern, adapted it)
- **Saved: 25 minutes**

**Task 2**: Fix bug in GRIB decoding error handling
- Baseline: 30 min (debug + fix)
- Confidence: 0.80
- Used Cortex: Yes (checked lessons for GRIB errors)
- Actual: 25 min (lesson reminded me to check index first)
- **Saved: 5 minutes**

**Day 1 Total**: 30 minutes saved, 2/2 successful, calibration looking good

---

### Day 2: 2 Tasks

**Task 3**: Write documentation for bias correction algorithm
- Baseline: 45 min (would write from scratch)
- Confidence: 0.70
- Used Cortex: No (testing baseline)
- Actual: 50 min (took longer than expected, no pattern to reference)
- **Lost: 5 minutes** (but good data point - confirms Cortex helps)

**Task 4**: Refactor validation logic for better error messages
- Baseline: 40 min
- Confidence: 0.85
- Used Cortex: Yes (searched "validation error handling")
- Actual: 60 min (found pattern but had to adapt significantly, edge cases)
- **Lost: 20 minutes** (overconfident, task harder than expected)

**Day 2 Total**: 15 minutes lost, 2/2 successful, confidence needs adjustment

---

### Week 1 Analysis (10 tasks)

**Calibration Stats**:
- Predictions: 10
- Completed: 10
- Average baseline: 45 min
- Average actual: 38 min
- **Average savings: 7 min per task (15.6%)**

**Confidence Calibration**:
- 0.70-0.79 bucket: 3 tasks, 67% success (slightly underconfident)
- 0.80-0.89 bucket: 5 tasks, 60% success (overconfident!)
- 0.90+ bucket: 2 tasks, 100% success (well calibrated)

**Insights**:
- Overconfident in 0.80-0.89 range → adjust down
- Cortex saves ~15 min per task on average
- Spec search most valuable for API/validation patterns

---

## 🎓 LEARNING OBJECTIVES

By end of Week 2, you should:

1. **Know your biases**
   - Overconfident or underconfident?
   - Optimistic or pessimistic on time?
   - Which task types you estimate well/poorly?

2. **Quantify Cortex value**
   - Average time saved per task
   - Which features save most time (spec search? patterns? lessons?)
   - ROI: Is calibration tracking worth the 2 min/task overhead?

3. **Improve estimation**
   - Week 2 estimates more accurate than Week 1
   - Confidence levels better calibrated
   - Systematic biases identified and correcting

---

## ✅ END OF WEEK 2 CHECKLIST

- [ ] 20+ task predictions recorded
- [ ] All tasks completed (outcomes recorded)
- [ ] Calibration analysis run (script below)
- [ ] Systematic biases identified
- [ ] Week 3-4 plan updated based on learnings

### Run Analysis

```python
# At end of Week 2
from metrics_tracker import MetricsTracker
import json

tracker = MetricsTracker()
cal_data = tracker.get_calibration_data()

print(f"=== WEEK 1-2 CALIBRATION REPORT ===")
print(f"Predictions: {len(cal_data['predictions'])}")
print(f"Completed: {len(cal_data['outcomes'])}")

# Compute statistics
predictions = cal_data['predictions']
outcomes = cal_data['outcomes']

# Time accuracy
time_diffs = []
for pred in predictions:
    if pred['prediction_id'] in outcomes:
        outcome = outcomes[pred['prediction_id']]
        diff = outcome['actual_time'] - pred['predicted_time']
        diff_pct = (diff / pred['predicted_time']) * 100
        time_diffs.append(diff_pct)

avg_error = sum(abs(d) for d in time_diffs) / len(time_diffs)
print(f"\nTime Estimation Error: {avg_error:.1f}%")

# Confidence calibration
# (Group by confidence buckets, check actual success rate)

print("\n📊 Full report saved to calibration_report_week2.json")
```

---

## 🚦 DECISION POINT

**After Week 2, ask yourself**:

1. **Is calibration tracking valuable?**
   - Are you learning about your biases?
   - Is the data useful?
   - Worth the 2 min/task overhead?

2. **Is Cortex helping?**
   - Average time saved >10 min/task?
   - Spec search finding relevant patterns?
   - Lessons preventing mistakes?

3. **Should we continue?**
   - **YES** → Proceed to Week 3-4 (VortexV2 forecast calibration)
   - **NO** → Analyze what went wrong, adjust approach

**If YES and going well**: You're on track for Month 1 success! 🎉

---

## 📞 TROUBLESHOOTING

### "I forgot to record a task prediction"
**Solution**: Record it retroactively if you remember baseline estimate
```python
# Backfill prediction
tracker.record_prediction(
    prediction_id="task_20251223_backfill_1",
    task="Task I forgot to record",
    predicted_outcome="success",
    confidence=0.70,
    predicted_time=30,  # Best guess of what you thought
    project="VortexV2"
)
tracker.record_outcome(
    prediction_id="task_20251223_backfill_1",
    actual_outcome="success",
    actual_time=25  # Actual time
)
```

### "My estimates are wildly off"
**Normal for Week 1**. By Week 2 you should start improving. If still wildly off:
- Lower confidence levels (be more uncertain)
- Break tasks into smaller pieces
- Track interruptions separately

### "I'm not using Cortex for most tasks"
**Fine for baseline**. But make sure to:
- Try spec search for at least 5/20 tasks
- Check lessons for at least 3/20 tasks
- Compare: tasks with Cortex vs without

---

**Ready to start? Run:**

```bash
cd ~/Dev/cortex
python3 start_calibration.py
```

**Track your first prediction NOW!** 🚀
