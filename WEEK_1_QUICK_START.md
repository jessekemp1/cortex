# Week 1 Foundation Calibration - Quick Start

**Welcome to Week 1!** 🎉

This is your foundation calibration week. The goal is simple: **use Cortex daily and learn your actual patterns**.

---

## Your Daily Routine (5 minutes)

### Every Morning:

1. **Get your next action**:
   ```bash
   cd /Users/jesse.kemp/Dev
   python3 "cortex/cli.py" next
   ```

2. **Execute the recommended action** (or decide not to - that's feedback too!)

3. **Log your feedback**:
   ```bash
   python3 "cortex/cli.py" feedback \
     --action-title "Action Name" \
     --useful yes \
     --notes "What happened? Was it right?"
   ```

4. **Quick note any friction**:
   ```bash
   python3 "cortex/cli.py" feedback --log "Friction: ..."
   ```

---

## Week 1 Success Criteria

By the end of Week 1, you should have:

- ✅ Used Cortex daily for 7 days
- ✅ Recommendations were actionable 70%+ of time
- ✅ Identified at least 3 value points
- ✅ Documented at least 2 friction points

---

## Tracking Your Progress

### Option 1: Use the Tracking Document
Edit `WEEK_1_TRACKING.md` daily with your observations.

### Option 2: Use Feedback Commands
Just log feedback - the system tracks it automatically:
```bash
# Check your progress
python3 "cortex/cli.py" feedback --stats
```

---

## What You're Learning

This week, you're discovering:

1. **Your actual work patterns** (not imagined ones)
2. **What recommendations are most valuable** to you
3. **Where the system needs improvement**
4. **Your baseline decision-making patterns**

---

## Decision Point: End of Week 1

After 7 days, ask yourself:

- Did I use it daily? ✅/❌
- Were recommendations actionable 70%+ of time? ✅/❌
- Did I identify value? ✅/❌
- Did I document friction? ✅/❌

**If YES to all**: Proceed to Week 2 (Context Integration)  
**If NO**: Identify blockers and address them before building new features

---

## Quick Commands Cheat Sheet

```bash
# Get next action
python3 "cortex/cli.py" next

# Get next action for specific project
python3 "cortex/cli.py" next vortexv2

# With context
python3 "cortex/cli.py" next --with-context

# Log feedback
python3 "cortex/cli.py" feedback --action-title "Action" --useful yes --notes "Notes"

# Quick log
python3 "cortex/cli.py" feedback --log "Quick note"

# Check stats
python3 "cortex/cli.py" feedback --stats

# Check system health
python3 "cortex/cli.py" health

# Show status
python3 "cortex/cli.py" status
```

---

## Remember

- **This is calibration, not perfection** - the system learns from you
- **Be honest in feedback** - it helps the system improve
- **Document friction** - that's how we improve
- **Focus on value** - what's actually helping?

---

**You've got this!** 🚀

Start with Day 1: Run `cortex next` and see what it recommends.

