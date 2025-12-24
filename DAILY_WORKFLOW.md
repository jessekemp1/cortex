# Cortex Daily Workflow - Quick Reference

**Goal**: Use Cortex consistently to demonstrate ROI within 7 days

---

## ⏰ MORNING ROUTINE (5 minutes)

### 1. Check Session Context
```bash
cd ~/Dev/cortex
python3 bridge.py session-context
```
**Why**: See current project, recent work, goals

### 2. Review Portfolio Stats
```bash
python3 bridge.py portfolio stats
```
**Why**: Understand your project landscape

### 3. Check Metrics
```python
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()
print(tracker.get_dashboard())
```
**Why**: Track progress toward ROI

---

## 💼 BEFORE EACH TASK (2-5 minutes)

### 1. Search Specs for Similar Work
```bash
python3 bridge.py intelligence similar-work "your topic" --project ProjectName
```

**Examples**:
```bash
# Before GRIB work
python3 bridge.py intelligence similar-work "GRIB processing" --project VortexV2

# Before API work
python3 bridge.py intelligence similar-work "API endpoints" --project VortexV2

# Before trading logic
python3 bridge.py intelligence similar-work "position management" --project AlphaArena
```

**Why**: Find existing solutions, avoid reinventing

### 2. Check Relevant Patterns
```python
from portfolio_memory import PortfolioMemory
pm = PortfolioMemory()

# If doing data work, review data patterns
# If doing API work, review API patterns
```

**Why**: Reuse proven approaches

### 3. Review Relevant Lessons
```bash
cat ~/.claude/portfolio/lessons.json | grep "category"
```

**Why**: Avoid repeating mistakes

---

## 📝 DURING TASK (30 seconds at start)

### Estimate Baseline Time
**Before starting**, ask yourself:
> "If I didn't have Cortex (no spec search, no patterns, no lessons), how long would this take?"

**Write it down** (mental note or comment):
```python
# BASELINE ESTIMATE: 45 minutes (would have to figure out GRIB processing from scratch)
# ACTUAL: TBD
```

---

## ✅ AFTER EACH TASK (2 minutes)

### 1. Record Velocity
```python
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()

tracker.record_velocity(
    task="Brief description of what you did",
    time_without_cortex=45,  # Your baseline estimate
    time_with_cortex=15,     # Actual time taken
    project="ProjectName",
    notes="Used spec search to find existing GRIB code"
)
```

### 2. Record Mistakes (if applicable)
**If you avoided a mistake** because of a lesson:
```python
tracker.record_mistake(
    mistake_type="data_validation",
    was_prevented=True,
    lesson_id="grib_index_check",
    project="VortexV2",
    impact_minutes=60,
    notes="Remembered to check GRIB index first, saved 1 hour"
)
```

**If you made a NEW mistake**:
```python
tracker.record_mistake(
    mistake_type="category_name",
    was_prevented=False,
    project="ProjectName",
    impact_minutes=30,
    notes="What went wrong and how to prevent next time"
)
```

### 3. Document New Patterns (if significant)
**If you found a good approach**:
```python
# Add to ~/.claude/portfolio/patterns.json manually, or:
# TODO: Add pattern via API (future feature)
```

---

## 🌙 EVENING ROUTINE (5 minutes)

### 1. Review Daily Metrics
```python
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()
dashboard = tracker.get_dashboard(days=1)

print(f"Today's velocity: {dashboard['velocity']['total_savings_hours']} hours saved")
print(f"Tasks tracked: {dashboard['velocity']['total_tasks']}")
print(f"Mistakes prevented: {dashboard['mistakes']['prevented']}")
```

### 2. Quick Reflection
**Ask yourself**:
- Did I search specs before coding? (goal: every task)
- Did I track my time estimates? (goal: every task)
- Did I use patterns/lessons? (goal: when relevant)

### 3. Plan Tomorrow
**Identify**:
- Tasks that could benefit from spec search
- Areas where patterns might apply
- Potential mistake risks (check lessons)

---

## 📅 FRIDAY REVIEW (15 minutes)

### 1. Run Portfolio Analysis
```bash
cd ~/Dev/cortex
python3 portfolio_analyzer.py
```

### 2. Check ROI
**Critical questions**:
- Total hours saved vs invested?
- Break-even achieved?
- ROI ratio > 1.5x?

### 3. Make Decision
**If ROI > 2x**:
- ✅ System is working
- ✅ Continue usage
- ✅ Consider integrations (Agents 6-7)

**If ROI < 2x**:
- 🔍 Analyze why
- 🛠️ Optimize workflow
- 📊 Try different approaches

---

## 🎯 TARGETS (7-Day Goals)

### Quantity
- ☐ Track 10+ tasks
- ☐ Search specs 5+ times
- ☐ Record 3+ prevented mistakes
- ☐ Document 2+ new patterns

### Quality
- ☐ Average velocity improvement > 50%
- ☐ Mistake prevention rate > 80%
- ☐ Spec search saves > 20 min per use

### ROI
- ☐ Break-even (ROI ≥ 1.0x)
- ☐ Stretch goal: ROI ≥ 2.0x

---

## ⚡ QUICK COMMANDS CHEAT SHEET

```bash
# Session context
python3 bridge.py session-context

# Portfolio stats
python3 bridge.py portfolio stats

# Search specs
python3 bridge.py intelligence similar-work "query" --project ProjectName

# View metrics
python3 -c "from metrics_tracker import MetricsTracker; print(MetricsTracker().get_dashboard())"

# Full analysis
python3 portfolio_analyzer.py

# Spec count
python3 -c "from spec_knowledge_base import SpecKnowledgeBase; kb = SpecKnowledgeBase(); print(f'{kb.count()} specs across {len(kb.list_projects())} projects')"
```

---

## 🚫 COMMON PITFALLS

### 1. Forgetting to Track
**Symptom**: Working all day, no metrics recorded
**Fix**: Set timer/reminder every 2 hours: "Did you track that?"

### 2. Optimistic Baselines
**Symptom**: "Would take 10 min without Cortex" (but actually would take 60)
**Fix**: Be honest. Overestimate if unsure. Integrity > looking good.

### 3. Not Searching Specs
**Symptom**: Writing code from scratch when examples exist
**Fix**: Make it automatic: "Search first, code second"

### 4. Not Recording Prevented Mistakes
**Symptom**: Avoided a mistake but didn't track it
**Fix**: Every time you think "Oh yeah, the lesson said...", record it!

---

## 💡 PRO TIPS

### Tip 1: Batch Tracking
**If you forget during task**:
- Track at end of day
- Estimate times retroactively
- Better late than never

### Tip 2: Use Comments
**In your code**:
```python
# CORTEX: Found this pattern in VortexV2 spec
# CORTEX: Would have taken 30 min without spec search
# CORTEX: Baseline estimate: 60 min, Actual: 15 min
```

### Tip 3: Document As You Go
**When you solve something**:
1. Solve the problem
2. Immediately add to patterns/lessons
3. Don't wait until "later" (you'll forget)

### Tip 4: Spec Search Templates
**Save common searches**:
```bash
# In ~/.zshrc or ~/.bashrc
alias cortex-search='python3 ~/Dev/cortex/bridge.py intelligence similar-work'
alias cortex-stats='python3 ~/Dev/cortex/bridge.py portfolio stats'
alias cortex-metrics='python3 -c "from metrics_tracker import MetricsTracker; print(MetricsTracker().get_dashboard())"'
```

---

## 🎓 LEARNING CURVE

### Day 1-2: Awkward
- Feels like extra work
- Forgetting to track
- Unsure what to search

**Normal. Keep going.**

### Day 3-4: Getting Used To It
- Starting to remember
- Finding useful specs
- Seeing some time savings

**This is the hump. Push through.**

### Day 5-7: Habitual
- Automatic workflow
- Search before coding feels natural
- Tracking takes 30 seconds

**You've made it. Now it compounds.**

---

## 📊 EXAMPLE DAY

### 8:00 AM - Start Work
```bash
python3 bridge.py session-context  # See what I'm working on
python3 bridge.py portfolio stats  # Orient to portfolio
```

### 8:05 AM - New Task: "Add validation to forecast ingestion"
```bash
python3 bridge.py intelligence similar-work "validation" --project VortexV2
# Found: Existing validation patterns in GRIB processing spec
# Baseline estimate: 45 min (would have written from scratch)
```

### 8:25 AM - Task Complete
**Actual time**: 20 min (used existing pattern)
```python
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()
tracker.record_velocity(
    task="Add validation to forecast ingestion",
    time_without_cortex=45,
    time_with_cortex=20,
    project="VortexV2",
    notes="Reused validation pattern from GRIB spec"
)
# Savings: 25 minutes (56% improvement)
```

### 10:00 AM - New Task: "Fix API rate limiting bug"
**Check lessons**:
```bash
cat ~/.claude/portfolio/lessons.json | grep "api"
# Found: "Use exponential backoff for API calls"
# Applied the fix from the lesson
# Prevented: Would have used simple retry, hit limits again (30 min wasted)
```

**Track prevented mistake**:
```python
tracker.record_mistake(
    mistake_type="api_integration",
    was_prevented=True,
    lesson_id="api_backoff",
    project="VortexV2",
    impact_minutes=30,
    notes="Used exponential backoff from lessons, avoided rate limit loop"
)
```

### 5:00 PM - End of Day
```python
dashboard = tracker.get_dashboard(days=1)
print(f"Today: {dashboard['velocity']['total_savings_hours']} hours saved")
# Result: 1.2 hours saved today
```

**7 days of this = 8.4 hours saved**
**Investment: 42 min setup + 10 min/day tracking = 112 min (1.9 hours)**
**Net: 6.5 hours saved**
**ROI: 4.4x** ✅✅✅

---

## ✅ DAILY CHECKLIST

Print this, stick on monitor:

```
CORTEX DAILY WORKFLOW

MORNING (5 min):
☐ Check session context
☐ Review portfolio stats
☐ Check metrics dashboard

BEFORE EACH TASK (2-5 min):
☐ Search specs for similar work
☐ Review relevant patterns
☐ Check relevant lessons
☐ Estimate baseline time (no Cortex)

AFTER EACH TASK (2 min):
☐ Record velocity (baseline vs actual)
☐ Record mistakes (prevented or new)
☐ Document patterns (if significant)

EVENING (5 min):
☐ Review daily metrics
☐ Reflect on usage
☐ Plan tomorrow

FRIDAY (15 min):
☐ Run portfolio analysis
☐ Check ROI
☐ Make decisions
```

---

**Pin this file. Reference daily. Build the habit.**

**After 7 days, Cortex will feel as natural as git.**

**That's when the magic happens.**
