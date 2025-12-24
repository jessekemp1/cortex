# Cortex ↔ Local Orchestrator Integration

**Status:** Partial Integration ✅ (Daily automation exists, Enhancement scheduling added)

---

## Current Integration

### 1. Existing: Daily Cortex Automation ✅

**Location:** `local-orchestrator/tasks/cortex_automation.py`
**Schedule:** Daily at 7:00 AM
**Registration:** `local-orchestrator/orchestrator_all_tasks.py:54-67`

```python
# Registered in orchestrator
cortex_agent = ScheduledTaskAgent(
    agent_id="cortex_daily",
    name="Cortex Week 1 Automation",
    description="Daily Cortex recommendation and tracking",
    task_func=run_cortex_daily,
)
orchestrator.register_agent(cortex_agent, schedule="0 7 * * *")
```

**What it does:**
- Runs `cortex/week1_automation.py --daily`
- Tracks metrics to `week1_data.json`
- Automated daily health checks

---

### 2. NEW: Enhancement Implementation Tracking ✅

**Location:** `local-orchestrator/tasks/cortex_enhancements.py`
**Schedule:** Daily at 9:00 AM (to be registered)
**Purpose:** Track progress on cortex-enhancements-2025 plan

**What it does:**
- Loads `~/.cortex/plans/cortex-enhancements-2025.json`
- Checks for next pending step
- Reports what needs to be done
- Tracks completion status

**To schedule:** Add to `orchestrator_all_tasks.py`:
```python
# Cortex Enhancement Tracker (Daily at 9 AM)
try:
    from tasks.cortex_enhancements import run_cortex_enhancement_step

    enhancement_agent = ScheduledTaskAgent(
        agent_id="cortex_enhancements",
        name="Cortex Enhancement Tracker",
        description="Track progress on ML, notifications, GitHub Actions, VS Code extension",
        task_func=run_cortex_enhancement_step,
    )
    orchestrator.register_agent(enhancement_agent, schedule="0 9 * * *")
    logger.info("registered_agent", agent_id="cortex_enhancements")
except Exception as e:
    logger.warning("failed_to_register_cortex_enhancements", error=str(e))
```

---

## Why Cortex Plans Aren't Automatically Scheduled

### Current State:
- **Cortex Layer 5** creates plans (JSON files in `~/.cortex/plans/`)
- **Local Orchestrator** schedules cron tasks
- **No automatic bridge** between them (yet!)

### The Gap:
1. Cortex plans are **execution plans** (what to do, dependencies, time estimates)
2. Local orchestrator is a **scheduler** (when to run tasks, cron expressions)
3. They speak different languages:
   - Cortex: "Step 1 → Step 2 → Step 3" (dependency-based)
   - Orchestrator: "Run daily at 9 AM" (time-based)

### Why Not Auto-Schedule?

**Cortex plans are for INTERACTIVE work:**
- "Build Batch API analyzer" - requires coding, testing, debugging
- "Integrate ML with Planner" - requires code changes, validation
- These aren't fire-and-forget automation tasks

**Local orchestrator is for AUTOMATED work:**
- "Run tests daily" - automated
- "Send email summary" - automated
- "Collect metrics" - automated

**The enhancement plan is a GUIDE for interactive development, not automation.**

---

## Integration Strategy

### Option 1: Manual Execution with Tracking (CURRENT) ✅

**How it works:**
1. Cortex creates the plan → 14 steps defined
2. Orchestrator tracks progress → Daily reminder at 9 AM
3. You work interactively → Implement steps with Claude Code
4. Update plan status → Mark steps complete as you go

**Benefit:** Best of both worlds
- Cortex plans what needs to be done
- You build it interactively (with AI assistance)
- Orchestrator reminds you of progress

**This is RECOMMENDED for development work.**

---

### Option 2: Batch API Auto-Implementation (FUTURE)

**Concept:** Use Batch API to generate code for each step

```python
# Hypothetical future feature
def auto_implement_step(step):
    # Send to Batch API: "Implement this step: {step.description}"
    # Batch API returns: Full code implementation
    # Auto-commit and test
    # Mark step complete
```

**Why not now?**
- Risky (auto-generated code needs review)
- Complex (requires extensive validation)
- Expensive (Batch API for every step)
- Better to use AI interactively for quality

**Could be added later for simpler tasks.**

---

### Option 3: Hybrid Approach (BEST LONG-TERM)

**For automated tasks:**
- Cortex plan → Orchestrator schedules → Runs automatically
- Example: "Weekly ML model refresh" → Cron job

**For development tasks:**
- Cortex plan → Human + AI implement → Orchestrator tracks
- Example: "Build Batch API analyzer" → You code it with Claude

**This is the FUTURE direction.**

---

## Current Setup

### What's Scheduled:

| Task | Schedule | Type | Status |
|------|----------|------|--------|
| Cortex Daily Automation | 7:00 AM | Automated | ✅ Running |
| Cortex Enhancement Tracker | 9:00 AM | Tracking | ⏳ Not yet registered |

### What's Tracked:

| Plan | Steps | Type | Execution |
|------|-------|------|-----------|
| cortex-enhancements-2025 | 14 | Development | Interactive (with tracking) |

---

## How to Use This Integration

### 1. Schedule the Enhancement Tracker

```bash
# Add to local-orchestrator/orchestrator_all_tasks.py
# (See code block above)

# Restart orchestrator
cd /Users/jesse.kemp/Dev/local-orchestrator
python orchestrator_all_tasks.py
```

### 2. Start the Enhancement Plan

```bash
cd /Users/jesse.kemp/Dev/cortex
venv/bin/python -c "
from intelligence.planning import PlanExecutor
executor = PlanExecutor()
plan = executor.load_plan('cortex-enhancements-2025')
executor.start_plan(plan)
print(f'Plan started: {plan.title}')
"
```

### 3. Daily Workflow

**Morning (9:00 AM):**
- Orchestrator runs enhancement tracker
- Reports: "Next step: Build Batch API analyzer"
- Sends notification (if configured)

**During Day:**
- Work on step interactively with Claude Code
- Build, test, validate

**End of Day:**
- Mark step complete:
```bash
venv/bin/python -c "
from local_orchestrator.tasks.cortex_enhancements import update_step_status
result = update_step_status('p1-batch-analyzer', 'completed', 'Implemented and tested')
print(result)
"
```

### 4. Next Day

- Orchestrator detects step completed
- Moves to next step in dependency order
- Cycle continues

---

## Batch API Verification

### Background Task Status:

**Task ID:** bef5a15
**Status:** Running (with error)
**Error:** `AttributeError: 'BatchAPIClient' object has no attribute 'get_batch_results'`

**Issue:** Batch monitoring script has API method name mismatch
**Fix needed:** Update `cortex/batch/monitor_batch_overnight.py`:
```python
# Change:
results = client.get_batch_results(batch_id)

# To:
results = client.get_batch_status(batch_id)
# Or implement get_batch_results() method
```

### Batch API Plan Status:

✅ Batch API is planned in Phase 1, Step 1
✅ Budget allocated: $7.50 initial + $19.50/year
✅ Implementation ready to start

---

## Summary

### What's Connected:
✅ Cortex daily automation runs via orchestrator
✅ Enhancement tracker task created
✅ Plan exists and ready to track

### What's NOT Connected (BY DESIGN):
❌ Plans don't auto-execute (they're interactive dev guides)
❌ Steps don't auto-implement (requires human + AI collaboration)
❌ No cron schedule for implementation (development is on-demand)

### Why This Is Correct:
- Development work needs human oversight
- AI assists but doesn't auto-commit
- Orchestrator tracks progress, not execution
- Best practice: Plan → Human+AI Build → Track → Repeat

---

## Next Steps

1. **Register enhancement tracker** in orchestrator_all_tasks.py
2. **Start the plan** (mark as ACTIVE)
3. **Begin Step 1** - Build Batch API analyzer (interactively)
4. **Fix batch monitoring** - Update API method name
5. **Let orchestrator remind you** - Daily progress tracking at 9 AM

---

**Built with Claude Code**
**Created:** 2025-12-24
