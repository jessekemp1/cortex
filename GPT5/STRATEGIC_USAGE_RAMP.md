# Converx Strategic Usage Ramp: 90-Day Path to Maximum Potential

## Overview

This document provides a **tactical 90-day adoption plan** to bring Converx from "new tool" to "daily decision intelligence OS." Each phase builds on the previous, with concrete rituals, metrics, and checkpoints.

**Goal**: Transform Converx from a utility you occasionally use into the **first and last command of your day**—your strategic co-pilot for all decisions.

---

## Phase 0: Setup & Sanity Check (Days 1-3)

### Objective
Verify Converx works in your environment and understand basic output.

### Daily Ritual
```bash
# Morning (first thing)
cd /Users/jesse.kemp/Dev
python -m converx.cli next

# Evening (before closing laptop)
python -m converx.cli status
```

### Tasks
1. **Day 1**: Run `converx next` and `converx status`. Verify all tools are wired correctly (`ai_intelligence.py`, `goal_parser.py`, `recommendation_engine.py`, `context_intelligence.py`).
2. **Day 2**: Try project-specific filtering: `converx next vortexv2` (or your most active project).
3. **Day 3**: Try with context: `converx next --with-context`. See if context predictions are useful.

### Success Criteria
- [ ] Converx runs without errors
- [ ] Recommendations are relevant (even if not perfect)
- [ ] You understand the output format
- [ ] You can identify which tool is providing which data

### Checkpoint
**After Day 3**: If Converx is working, proceed to Phase 1. If not, debug tool integrations first.

---

## Phase 1: Daily Operating System (Days 4-14)

### Objective
Make Converx the **first and last command of your day**. Build the habit of checking strategic state before making decisions.

### Morning Ritual (First Command of Day)
```bash
# When you sit down to work
cd /Users/jesse.kemp/Dev
python -m converx.cli next --with-context > ~/converx-morning-$(date +%Y%m%d).txt
cat ~/converx-morning-$(date +%Y%m%d).txt

# Review:
# 1. What's the top priority?
# 2. What are the blockers?
# 3. What context do I need?
```

### Decision Points
Before starting any significant work session:
```bash
# Quick check: "What should I focus on?"
python -m converx.cli next PROJECT_NAME

# If working on multiple projects:
python -m converx.cli next
```

### Evening Ritual (Last Command of Day)
```bash
# Before closing laptop
python -m converx.cli status > ~/converx-evening-$(date +%Y%m%d).txt

# Review:
# 1. What did I complete today?
# 2. What's the state for tomorrow?
# 3. Any new blockers?
```

### Weekly Review (End of Week)
```bash
# Review the week's morning/evening outputs
ls -lt ~/converx-morning-*.txt | head -7
ls -lt ~/converx-evening-*.txt | head -7

# Questions to ask:
# 1. Were recommendations accurate 70%+ of the time?
# 2. Did Converx catch blockers I missed?
# 3. Did context predictions help?
```

### Metrics to Track
- **Recommendation accuracy**: How often was the top recommendation actually what you should do? (Target: 70%+)
- **Decision friction reduction**: How much faster do you decide what to work on? (Target: 50%+ reduction)
- **Blocker detection**: Did Converx identify blockers before you hit them? (Target: 1+ per week)

### Success Criteria
- [ ] You run `converx next` at least once per day
- [ ] You check `converx status` at end of day
- [ ] Recommendations feel relevant 70%+ of the time
- [ ] You notice reduced decision friction

### Checkpoint
**After Day 14**: If Converx is providing daily value, proceed to Phase 2. If not, identify what's missing (better goals in ACTION_PLAN.md? More active projects?).

---

## Phase 2: Multi-Domain Integration (Days 15-30)

### Objective
Extend Converx beyond work/code to include **finance, health, and learning domains**. Build the Life Weather Map foundation.

### Setup Tasks
1. **Finance Domain** (Day 15-17):
   - Ensure `financial-aggregator` outputs are accessible
   - If using `Alpha Arena`, verify portfolio status is readable
   - Add financial goals to `ACTION_PLAN.md` (e.g., "Maintain runway > 6 months")

2. **Health Domain** (Day 18-20):
   - If using `keto-tracker`, verify data is accessible
   - Add health goals to `ACTION_PLAN.md` (e.g., "Maintain sleep >= 7h")
   - Consider Google Fit integration if available

3. **Learning Domain** (Day 21-23):
   - Add learning goals to `ACTION_PLAN.md` (e.g., "Complete X course by Y date")
   - If using `personal-ai-dataset`, verify knowledge search works

### Enhanced Daily Ritual
```bash
# Morning: Full multi-domain check
python -m converx.cli next --with-context

# Review across domains:
# - Work: What's the top priority project?
# - Finance: Any runway concerns?
# - Health: Any energy/stress signals?
# - Learning: What skill gaps need attention?
```

### Weekly Multi-Domain Review
```bash
# End of week: Review state across all domains
python -m converx.cli status

# Questions:
# 1. How did work decisions affect health this week?
# 2. Did financial runway change?
# 3. Are learning goals on track?
# 4. Any cross-domain conflicts? (e.g., work deadline vs. health goal)
```

### Cross-Domain Decision Pattern
Before making a significant decision:
```bash
# Check impact across domains
python -m converx.cli next

# Ask:
# 1. Does this work decision risk health domain?
# 2. Does this financial move affect work runway?
# 3. Does this learning goal conflict with work deadlines?
```

### Metrics to Track
- **Cross-domain awareness**: How often do you consider multiple domains when deciding? (Target: 80%+ for significant decisions)
- **Domain conflict detection**: Did Converx identify conflicts between domains? (Target: 1+ per week)
- **Multi-domain goal tracking**: Are goals across domains visible in recommendations? (Target: Yes)

### Success Criteria
- [ ] You have goals in at least 3 domains (work, finance, health, learning)
- [ ] Converx recommendations consider multiple domains
- [ ] You notice cross-domain impacts in recommendations
- [ ] Weekly reviews include all domains

### Checkpoint
**After Day 30**: If multi-domain awareness is providing value, proceed to Phase 3. If not, ensure goals are properly structured in `ACTION_PLAN.md`.

---

## Phase 3: Risk/Opportunity Radar (Days 31-60)

### Objective
Use Converx as an **early-warning system** for risks and opportunities. Build patterns for proactive decision-making.

### Risk Detection Pattern
```bash
# Daily: Check for emerging risks
python -m converx.cli next --with-context

# Look for:
# - Blockers that might become critical
# - Domain conflicts (work vs. health, finance vs. learning)
# - Momentum degradation (projects going dormant)
# - Resource constraints (time, energy, runway)
```

### Opportunity Sensing Pattern
```bash
# Weekly: Identify high-leverage moments
python -m converx.cli status

# Look for:
# - Clear runway (no blockers, high energy)
# - Optimal timing (deadlines far enough, momentum high)
# - Cross-domain alignment (work + health + finance all positive)
# - Learning opportunities (skill gaps that unlock projects)
```

### Risk/Opportunity Log
Create `~/converx-risks-opportunities.md`:
```markdown
# Risk/Opportunity Log

## Week of [DATE]

### Risks Detected
- [Date] [Risk] [Domain] [Action Taken]

### Opportunities Identified
- [Date] [Opportunity] [Domain] [Action Taken]
```

### Weekly Risk/Opportunity Review
```bash
# End of week: Review risks and opportunities
cat ~/converx-risks-opportunities.md

# Questions:
# 1. Did Converx detect risks before they became blockers?
# 2. Did Converx identify opportunities you would have missed?
# 3. How accurate were the predictions? (Track predicted vs. actual)
```

### Advanced Pattern: Scenario Thinking
Even though Phase 1 (scenario bands) isn't built yet, start thinking in scenarios:
```bash
# When Converx recommends an action, ask:
# 1. Optimistic scenario: What if everything goes well?
# 2. Likely scenario: What's the realistic outcome?
# 3. Conservative scenario: What if blockers emerge?
```

### Metrics to Track
- **Risk detection accuracy**: How often did Converx identify risks before they became blockers? (Target: 80%+)
- **Opportunity identification**: How many opportunities did Converx surface that you would have missed? (Target: 1+ per week)
- **Prediction accuracy**: How accurate were risk/opportunity predictions? (Target: 70%+)

### Success Criteria
- [ ] You check for risks daily
- [ ] You review opportunities weekly
- [ ] Converx detects risks before they become blockers 80%+ of the time
- [ ] You maintain a risk/opportunity log

### Checkpoint
**After Day 60**: If risk/opportunity sensing is providing value, proceed to Phase 4. If not, refine goal structure and blocker detection in `ACTION_PLAN.md`.

---

## Phase 4: Virtual Twin & Scenarios (Days 61-90)

### Objective
Build **design-level habits** for scenario thinking and virtual twin concepts, even before Phase 1-5 features are implemented. Prepare for future capabilities.

### Scenario Thinking Ritual
```bash
# Before major decisions: Think in scenarios
python -m converx.cli next

# Manually evaluate:
# 1. Optimistic: Best-case outcome (no blockers, high momentum)
# 2. Likely: Realistic outcome (some blockers, normal pace)
# 3. Conservative: Worst-case outcome (blockers, low momentum)

# Document in ~/converx-scenarios.md
```

### Virtual Twin Preparation
Even though the virtual twin isn't built yet, start tracking data that will feed it:
```bash
# Weekly: Track key variables
# - Focus hours per week
# - Energy levels (1-10)
# - Blocker frequency
# - Goal completion rate
# - Cross-domain conflicts

# Store in ~/converx-twin-data.md
```

### Forward Simulation Practice
Before committing to a route, practice forward simulation:
```bash
# When Converx recommends a route, ask:
# 1. If I take this route, what's my state in 1 week?
# 2. What's my state in 1 month?
# 3. What domains are affected?
# 4. What are the risks at each horizon?
```

### Weekly Scenario Review
```bash
# End of week: Review scenarios vs. actual
cat ~/converx-scenarios.md

# Questions:
# 1. Which scenario did you actually track? (optimistic/likely/conservative)
# 2. How accurate were your predictions?
# 3. What did you learn about your patterns?
```

### Metrics to Track
- **Scenario accuracy**: How often did the "likely" scenario match actual outcomes? (Target: 70%+)
- **Forward simulation value**: Did thinking ahead help avoid problems? (Target: 1+ per week)
- **Pattern recognition**: Are you noticing patterns in your decision-making? (Target: Yes)

### Success Criteria
- [ ] You think in scenarios for major decisions
- [ ] You track key variables weekly
- [ ] You practice forward simulation before committing to routes
- [ ] You review scenarios vs. actual outcomes weekly

### Checkpoint
**After Day 90**: You should have:
- Converx as your daily decision OS
- Multi-domain awareness across work, finance, health, learning
- Risk/opportunity radar patterns established
- Scenario thinking habits built
- Data collection for future virtual twin

---

## Beyond 90 Days: Continuous Improvement

### Monthly Reviews
```bash
# End of month: Comprehensive review
# 1. Review all converx outputs from the month
# 2. Identify patterns in recommendations
# 3. Assess accuracy of predictions
# 4. Refine goals in ACTION_PLAN.md
# 5. Update risk/opportunity patterns
```

### Quarterly Upgrades
As Converx phases are implemented (Phase 1-5), integrate new features:
- **Phase 1**: Use weather map and scenario bands
- **Phase 2**: Use routes and waypoints
- **Phase 3**: Connect real data sources
- **Phase 4**: Use playbooks for automation
- **Phase 5**: Use virtual twin for simulation

### Continuous Calibration
- Refine goals based on what Converx learns
- Update risk/opportunity patterns based on accuracy
- Adjust scenario thinking based on outcomes
- Expand domains as new data sources become available

---

## Troubleshooting

### "Recommendations feel irrelevant"
- **Check**: Are goals in `ACTION_PLAN.md` clear and prioritized?
- **Check**: Are projects active (recent commits)?
- **Check**: Is `recommendation_engine.py` working correctly?

### "Not seeing multi-domain awareness"
- **Check**: Do you have goals in multiple domains in `ACTION_PLAN.md`?
- **Check**: Are domain-specific tools integrated (financial-aggregator, keto-tracker, etc.)?

### "Risk detection isn't working"
- **Check**: Are blockers properly identified in project analysis?
- **Check**: Are goals structured with dependencies and risks?
- **Check**: Is `ai_intelligence.py` scanning projects correctly?

### "Scenarios feel forced"
- **Start simple**: Just ask "optimistic/likely/conservative" for major decisions
- **Build habit**: Do it weekly, then daily
- **Track outcomes**: Compare predictions to actuals

---

## Success Metrics Summary

**By Day 14**: Converx is your daily decision OS
- Run `converx next` daily
- Recommendations accurate 70%+
- Decision friction reduced 50%+

**By Day 30**: Multi-domain awareness active
- Goals in 3+ domains
- Cross-domain impacts visible
- Weekly multi-domain reviews

**By Day 60**: Risk/opportunity radar working
- Risk detection 80%+ accuracy
- 1+ opportunity identified per week
- Risk/opportunity log maintained

**By Day 90**: Scenario thinking habits built
- Scenario evaluation for major decisions
- Forward simulation practice
- Pattern recognition emerging

---

## The Ultimate Goal

**After 90 days, Converx should be:**
- The first command you run each day
- The last command you run each day
- Your go-to tool for any significant decision
- Your early-warning system for risks and opportunities
- Your strategic co-pilot across all life domains

**You should feel**: Clearer decisions, earlier risk detection, better opportunity sensing, reduced decision friction, and a sense of strategic awareness across all domains.

**That's maximum potential.**
