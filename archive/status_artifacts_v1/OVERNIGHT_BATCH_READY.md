# Layers 3-4 Overnight Batch Implementation - Ready to Submit! ✅

## Executive Summary

The Cortex Intelligence Stack Layers 3-4 implementation is **ready for overnight batch processing**.

**What's Ready:**
- ✅ 8 batch tasks created (4 for Layer 3, 4 for Layer 4)
- ✅ Batch submission script configured
- ✅ Overnight monitoring script ready
- ✅ Automatic code application and testing
- ✅ Local orchestrator integration
- ✅ Complete documentation

**Expected Outcome:**
- Submit batch tonight (5 minutes)
- Processing completes overnight (12-24 hours)
- Code automatically applied and tested
- Wake up to completed implementation
- Review and test in the morning (30 minutes)

**Cost:** ~$5.40 (50% batch discount)
**Value:** ~12.5 hours of implementation work

---

## Quick Start (3 Commands)

```bash
# 1. Generate batch specification
cd /Users/jesse.kemp/Dev/cortex
python batch/layer3_4_batch_spec.py

# 2. Submit batch (interactive, confirms cost)
python batch/submit_layer3_4_batch.py

# 3. Monitor overnight (runs until complete)
python batch/monitor_batch_overnight.py <batch_id>
```

**That's it!** Go to sleep. Wake up to completed Layers 3-4.

---

## What Gets Implemented Overnight

### Layer 3: Warning System

**Files Created:**
- `intelligence/monitoring/metric_tracker.py` (~300 lines)
  - SQLite-based metric tracking
  - Track coverage, violations, commits, files
  - Store time-series data to ~/.cortex/metrics.db

- `intelligence/monitoring/trend_analyzer.py` (~250 lines)
  - Statistical trend analysis (linear regression)
  - Detect degradation (coverage drops, violation increases)
  - Alert level calculation (critical, warning, none)

- `intelligence/monitoring/alert_generator.py` (~200 lines)
  - Generate alerts for degradation, activity, critical files
  - Format alerts for context injection and CLI
  - Alert rules and thresholds

**Files Modified:**
- `.claude/hooks/inject_context.py`
  - Integrate Layer 3 alerts
  - Show critical alerts in context
  - Example: `Project: cortex (Python/FastAPI) | 🔴 Coverage dropped 8%`

**New Features:**
- `cortex alerts` - Show all active alerts
- `cortex metrics <project>` - Show metric history
- `cortex track` - Manually trigger tracking

### Layer 4: Smart Recommendations

**Files Created:**
- `intelligence/recommendations/file_selector.py` (~200 lines)
  - Select specific files to work on
  - Algorithms for coverage, goal work, critical files
  - Priority scoring and deduplication

- `intelligence/recommendations/smart_generator.py` (~400 lines)
  - Generate smart recommendations using all layers
  - File-level guidance
  - Step-by-step action plans
  - Pattern integration

**Files Modified:**
- `cortex/recommendation_engine.py`
  - Replace generic generators with SmartGenerator
  - Integrate all 4 layers
  - Enrich recommendations with files and steps

**New Features:**
- All recommendations include specific files
- All recommendations include 3-5 actionable steps
- Alert-based recommendations for critical issues
- Pattern-enhanced recommendations

### Documentation

**Files Created:**
- `intelligence/monitoring/README.md` - Layer 3 guide
- `intelligence/recommendations/README.md` - Layer 4 guide
- `INTELLIGENCE_STACK.md` - Complete stack overview

---

## Expected Results (Morning Review)

### Before (Current State)

**Recommendation:**
```
[MEDIUM] Continue momentum on cortex

Why: cortex is active with 7 commits this week

Next Steps:
  • Review recent changes
  • Identify next logical step
  • Continue from last commit
```

**Context:**
```xml
<cortex_context>Project: cortex (Python/FastAPI) | Branch: main | ⚠️  No linter configured for Python</cortex_context>
```

### After (Layers 3-4 Complete)

**Recommendation:**
```
[HIGH] Fix test coverage degradation in cortex

Why: Coverage dropped 8% (45% → 37%) in last 7 days [Layer 3 Alert]
Tech: Python/FastAPI [Layer 1]
Similar: VortexV2 added 15 tests (tests/unit/) [Layer 2]

Files to work on:
- intelligence/analysis/project_profiler.py (0% coverage, 650 lines)
- intelligence/memory/pattern_indexer.py (0% coverage, 580 lines)
- intelligence/memory/pattern_memory.py (0% coverage, 380 lines)

Next Steps:
1. Create tests/intelligence/test_project_profiler.py
2. Add unit tests for tech stack detection
   - Test: test_detect_python_stack()
   - Test: test_detect_js_stack()
3. Run: pytest --cov=intelligence --cov-report=html
4. Target: 70% coverage for new modules

Effort: 2-3h | Confidence: 90%
```

**Context:**
```xml
<cortex_context>Project: cortex (Python/FastAPI) | Branch: main | 🔴 Coverage dropped 8% (45%→37% in 7d)</cortex_context>
```

---

## Batch Task Breakdown

| Task | File | Lines | Model | Purpose |
|------|------|-------|-------|---------|
| **Layer 3** |
| layer3_metric_tracker | metric_tracker.py | 300 | Opus | SQLite metric tracking |
| layer3_trend_analyzer | trend_analyzer.py | 250 | Opus | Statistical analysis |
| layer3_alert_generator | alert_generator.py | 200 | Opus | Alert generation |
| layer3_inject_integration | inject_context.py | 50 | Sonnet | Context integration |
| **Layer 4** |
| layer4_file_selector | file_selector.py | 200 | Opus | File selection |
| layer4_smart_generator | smart_generator.py | 400 | Opus | Smart recommendations |
| layer4_engine_integration | recommendation_engine.py | 100 | Sonnet | Engine integration |
| layer3_4_cli_docs | Multiple docs | N/A | Sonnet | Documentation |

**Total:** ~1500 lines of production code

---

## Submission Checklist

Before submitting tonight:

### Prerequisites
- [ ] API key set: `echo $ANTHROPIC_API_KEY`
- [ ] Cortex working: `python cortex/cli.py status`
- [ ] Batch spec generated: `python batch/layer3_4_batch_spec.py`

### Submission
- [ ] Review batch tasks: `cat batch/layer3_4_batch.json` (optional)
- [ ] Submit batch: `python batch/submit_layer3_4_batch.py`
- [ ] Note batch ID (saved automatically)

### Monitoring
- [ ] Start monitor: `python batch/monitor_batch_overnight.py <batch_id>`
- [ ] Leave terminal running overnight (or use tmux/screen)
- [ ] Optional: Add orchestrator task for automatic monitoring

### Morning (After Completion)
- [ ] Check summary: `cat ~/.cortex/batches/<batch_id>/IMPLEMENTATION_REPORT.md`
- [ ] Review files: `ls intelligence/monitoring/ intelligence/recommendations/`
- [ ] Run tests: `pytest intelligence/ -v`
- [ ] Test features: `cortex alerts`, `cortex next`
- [ ] Commit: `git add . && git commit -m "feat: implement Layers 3-4"`

---

## Cost & ROI Analysis

### Batch API Cost (50% Discount)
- 8 tasks × $0.675 = **$5.40**
- Saves $5.40 vs real-time API (50% discount)

### Value Delivered
- ~1500 lines of production code
- ~12.5 hours equivalent work
- 4 new features (alerts, metrics, smart recs, file guidance)
- Complete documentation

### ROI
- **Cost:** $5.40
- **Value:** 12.5 hours × $100/hr = $1,250
- **ROI:** 23,048% return

### Time Saved
- **Manual implementation:** 12.5 hours
- **Batch submission:** 5 minutes
- **Morning review:** 30 minutes
- **Total saved:** ~11.5 hours

---

## Monitoring Options

### Option A: Overnight Script (Recommended)

Start the monitoring script and leave it running:

```bash
# In a tmux/screen session or dedicated terminal
python batch/monitor_batch_overnight.py <batch_id>
```

**Pros:**
- Automatic code application when complete
- No manual intervention needed
- Results ready in the morning

**Cons:**
- Need to leave terminal/computer running

### Option B: Local Orchestrator

Add to orchestrator to check every 30 minutes:

```bash
# The task is already created at:
# local-orchestrator/tasks/cortex_layer3_4_batch.py

# Run orchestrator with this task enabled
cd /Users/jesse.kemp/Dev/local-orchestrator
python orchestrator.py
```

**Pros:**
- Runs in background automatically
- Integrated with other tasks
- Notifications when complete

**Cons:**
- Requires orchestrator setup

### Option C: Manual Check (Morning)

Just check in the morning:

```bash
# Morning: check status
python batch/check_batch_status.py <batch_id>

# If complete, download and apply
python batch/monitor_batch_overnight.py <batch_id>
```

**Pros:**
- Simplest approach
- No overnight processes

**Cons:**
- Manual morning work required
- Results not applied automatically

---

## What Happens Overnight

### Hour 0: Submission
```
[23:00] Batch submitted: batch_abc123
[23:00] Status: validating
[23:01] Status: in_progress
[23:01] Request counts: 8 processing
```

### Hours 1-12: Processing
```
[00:30] Check #2: 3 succeeded, 5 processing
[01:00] Check #3: 5 succeeded, 3 processing
...
[11:00] Check #23: 8 succeeded, 0 processing
```

### Hour 12: Completion
```
[11:30] Check #24: Batch complete!
[11:30] Downloading results...
[11:30] Downloaded 8 results
[11:31] Applying code changes...
[11:31]   ✅ Created: intelligence/monitoring/metric_tracker.py
[11:31]   ✅ Created: intelligence/monitoring/trend_analyzer.py
[11:31]   ✅ Created: intelligence/monitoring/alert_generator.py
[11:31]   ✅ Modified: .claude/hooks/inject_context.py
[11:31]   ✅ Created: intelligence/recommendations/file_selector.py
[11:31]   ✅ Created: intelligence/recommendations/smart_generator.py
[11:31]   ✅ Modified: recommendation_engine.py
[11:32] Running tests...
[11:32]   ✅ All tests passed
[11:32] Summary report saved to: ~/.cortex/batches/batch_abc123/IMPLEMENTATION_REPORT.md
[11:32] BATCH PROCESSING COMPLETE
```

### Morning: Review
```
[08:00] You wake up
[08:01] cat ~/.cortex/batches/batch_abc123/IMPLEMENTATION_REPORT.md
[08:05] pytest intelligence/ -v  # Verify tests
[08:10] cortex alerts  # Test new feature
[08:15] cortex next  # See smart recommendations
[08:20] git add . && git commit  # Commit changes
[08:30] Done! ✅
```

---

## Troubleshooting

### Batch Submission Fails

**Error:** "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY='your-key-here'
```

**Error:** "anthropic SDK not installed"
```bash
pip install anthropic
```

### Monitoring Script Fails

**Error:** Timeout or connection issues
- Monitor script retries automatically every 30 minutes
- Check internet connection
- Verify API key is valid

### Code Application Fails

**Files not created:**
- Check `~/.cortex/batches/<batch_id>/*_response.txt`
- Manually extract code blocks if needed

**Tests fail:**
- Review test output in implementation report
- Fix syntax errors if any
- Re-run specific tests: `pytest path/to/test.py -v`

### Batch Takes Too Long

**Still processing after 24 hours:**
- Check Anthropic API dashboard
- Contact support if needed
- Batch SLA is 24 hours

---

## Next Steps

### Tonight (5 minutes)

1. **Generate batch spec:**
   ```bash
   cd /Users/jesse.kemp/Dev/cortex
   python batch/layer3_4_batch_spec.py
   ```

2. **Submit batch:**
   ```bash
   python batch/submit_layer3_4_batch.py
   # Type 'yes' when prompted
   ```

3. **Start monitoring:**
   ```bash
   python batch/monitor_batch_overnight.py <batch_id>
   # Leave running overnight
   ```

### Tomorrow Morning (30 minutes)

1. **Check results:**
   ```bash
   cat ~/.cortex/batches/<batch_id>/IMPLEMENTATION_REPORT.md
   ```

2. **Run tests:**
   ```bash
   pytest intelligence/ -v
   ```

3. **Test features:**
   ```bash
   cortex alerts
   cortex next
   echo "test" | .claude/hooks/inject_context.py
   ```

4. **Commit:**
   ```bash
   git add .
   git commit -m "feat: implement Layers 3-4 via batch API"
   ```

---

## Files Created by This Setup

```
cortex/batch/
├── layer3_4_batch_spec.py          # Batch specification generator
├── submit_layer3_4_batch.py        # Batch submission script
├── monitor_batch_overnight.py      # Overnight monitoring
├── check_batch_status.py           # Quick status checker
└── OVERNIGHT_BATCH_GUIDE.md        # Detailed guide

cortex/intelligence/
├── monitoring/                      # Layer 3 (created overnight)
│   ├── __init__.py
│   ├── metric_tracker.py           # To be created by batch
│   ├── trend_analyzer.py           # To be created by batch
│   └── alert_generator.py          # To be created by batch
│
└── recommendations/                 # Layer 4 (created overnight)
    ├── __init__.py
    ├── file_selector.py            # To be created by batch
    └── smart_generator.py          # To be created by batch

local-orchestrator/tasks/
└── cortex_layer3_4_batch.py        # Orchestrator integration

cortex/
├── LAYERS_3_4_STRATEGIC_PLAN.md    # Strategic plan
└── OVERNIGHT_BATCH_READY.md        # This file
```

---

## Summary

**You're ready to submit!**

✅ Batch specification created
✅ Submission script ready
✅ Monitoring configured
✅ Documentation complete
✅ Orchestrator integrated

**Expected timeline:**
- Tonight (11pm): Submit batch (5 min)
- Overnight: Processing (12-24 hours)
- Tomorrow (11am): Results ready
- Tomorrow morning: Review and test (30 min)

**Expected outcome:**
- 1500 lines of production code
- Layer 3: Warning System operational
- Layer 4: Smart Recommendations operational
- All 4 pain points addressed
- 100% intelligence stack complete

**Cost:** $5.40
**Value:** 12.5 hours of work
**ROI:** Wake up to a completed intelligence stack!

🚀 **Ready to submit? Run the 3 commands above!**
