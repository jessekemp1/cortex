# Model Selection - Quick Start Guide

**Status:** ✅ Integrated and Tested
**Date:** 2026-01-15

---

## 🚀 Quick Start (3 Steps)

### Step 1: Verify Installation

```bash
export PYTHONPATH="/Users/jesse.kemp/Dev/cortex:$PYTHONPATH"

# Test imports
python3 -c "from intelligence.model_selection import ContextAwareModelRecommender; print('✅ Ready')"
```

### Step 2: Run Integration Test

```bash
# Test the complete integration
python3 test_next_integration.py
```

**Expected output:**
```
✅ Display test PASSED

📊 Recommended Model
Model: SONNET (confidence: 60%)
Cost: ~$0.0112 (~1500 tokens)
Reasoning: [RULES] Task type 'bug_fix' typically uses sonnet
```

### Step 3: Use in Real Workflow

```bash
# Run the complete example
python3 examples/model_selection_example.py
```

---

## 📊 What You Get

### Context-Aware Recommendations

```python
from intelligence.model_selection import ContextAwareModelRecommender, OrchestrationContext
from datetime import timedelta

recommender = ContextAwareModelRecommender()

context = OrchestrationContext(
    remaining_budget=5.00,      # Your budget
    remaining_time=timedelta(hours=2),
    task_priority="high",       # Task priority
    files=["auth.py"]          # Files involved
)

rec = recommender.recommend(
    task_description="Fix authentication timeout bug",
    task_type="bug_fix",
    context=context
)

print(f"Use {rec.model.upper()}: {rec.reasoning}")
print(f"Estimated cost: ${rec.estimated_cost_usd:.4f}")
```

### Outcome Logging

```python
from intelligence.outcome_logger import log_task_outcome

# After completing a task
log_task_outcome(
    task_id="task_001",
    task_type="bug_fix",
    description="Fixed auth timeout",
    model_used="sonnet",
    outcome="success",
    tokens=2850,
    time_seconds=1800,
    cost_usd=0.0214
)
```

---

## 🎯 Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| **Budget Constraints** | ✅ | Never exceed budget (hard limit) |
| **Priority Aware** | ✅ | High priority → better models |
| **Retry Intelligence** | ✅ | Failed task → upgrade model |
| **Time Pressure** | ✅ | Tight deadline → faster models |
| **Outcome Logging** | ✅ | Track for learning (Week 2) |

---

## 📁 Key Files

**Use These:**
- `intelligence/outcome_logger.py` - Log task outcomes
- `test_next_integration.py` - Verify integration works
- `examples/model_selection_example.py` - Complete workflow

**Read These:**
- `INTEGRATION_COMPLETE.md` - Full integration details
- `intelligence/model_selection/INTEGRATION_GUIDE.md` - API reference
- `WEEK1_IMPLEMENTATION_SUMMARY.md` - Week 1 summary

---

## ✅ Verification Checklist

- [x] Model selection imports work
- [x] Recommendations consider budget/priority/retry
- [x] Budget constraints are never violated
- [x] Outcome logging stores to ~/.cortex/
- [x] Integration test passes
- [x] Complete workflow example works
- [x] All 8 unit tests pass

---

## 🎓 Example Scenarios

### Scenario 1: Budget-Constrained
```python
context = OrchestrationContext(
    remaining_budget=0.30,  # Low budget
    task_priority="high"
)
# Result: HAIKU (budget overrides priority)
```

### Scenario 2: High-Priority Retry
```python
context = OrchestrationContext(
    remaining_budget=5.00,
    task_priority="high",
    is_retry=True,
    previous_model="haiku"
)
# Result: SONNET (upgrade for reliability)
```

### Scenario 3: Time Pressure
```python
context = OrchestrationContext(
    remaining_budget=5.00,
    remaining_time=timedelta(minutes=10)
)
# Result: SONNET (avoid slow Opus)
```

---

## 🐛 Troubleshooting

### Import Errors
```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Should include: /Users/jesse.kemp/Dev/cortex
export PYTHONPATH="/Users/jesse.kemp/Dev/cortex:$PYTHONPATH"
```

### Test Failures
```bash
# Run tests verbosely
pytest tests/test_model_selection.py -vv

# Run specific test
python3 test_next_integration.py
```

### No Data in ~/.cortex/
```bash
# Check directory
ls -la ~/.cortex/

# Create if missing
mkdir -p ~/.cortex/

# Run logging example
python3 intelligence/outcome_logger.py

# Verify
tail ~/.cortex/model_outcomes.jsonl
```

---

## 📈 Collect Data (This Week)

To enable Week 2 learning, collect 20-30 outcomes:

```python
# After each task you complete
from intelligence.outcome_logger import log_task_outcome

log_task_outcome(
    task_id=f"task_{uuid4().hex[:8]}",
    task_type="bug_fix",           # or "implement", "refactor", etc.
    description="What you did",
    model_used="sonnet",            # Model you actually used
    outcome="success",              # or "partial", "failed"
    tokens=2500,                    # Token count
    time_seconds=1800,              # Time taken
    error_count=1,                  # Corrections needed
    cost_usd=0.019,                 # Actual cost
    project="cortex",
    files=["file1.py", "file2.py"]
)
```

**Check progress:**
```bash
# Count outcomes
wc -l ~/.cortex/model_outcomes.jsonl

# View recent
tail -5 ~/.cortex/model_outcomes.jsonl | jq .
```

**Target:** 20-30 outcomes before Week 2

---

## 🚦 What's Next

### Week 2: Learning Pipeline
- Analyze historical outcomes
- Learn which models work best for which tasks
- Hybrid recommender (learned + rules)
- Confidence-based switching

### Week 3: Orchestration
- Multi-objective resource allocation
- Wave-based parallelization
- Session-level planning

---

## 💡 Pro Tips

1. **Start logging outcomes immediately** - Even 5-10 outcomes help
2. **Test different scenarios** - Low budget, high priority, retries
3. **Monitor reasoning** - Understand why models are chosen
4. **Check alternatives** - Sometimes cheaper/faster options exist

---

## ✅ Status

**Week 1 Foundation:** ✅ COMPLETE
**Integration:** ✅ COMPLETE
**Testing:** ✅ ALL PASSING
**Documentation:** ✅ COMPLETE

**Ready for:** Production use + data collection

---

**Questions?**
- Full docs: `INTEGRATION_COMPLETE.md`
- API reference: `intelligence/model_selection/INTEGRATION_GUIDE.md`
- Run examples: `examples/model_selection_example.py`

**Data location:** `~/.cortex/model_outcomes.jsonl`
