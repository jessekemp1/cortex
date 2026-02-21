# Cortex Daily Automation - START HERE

**Status:** ✅ Complete and Ready
**Setup Time:** 30 seconds
**Daily Time:** 5 minutes

## Quick Start (30 seconds)

```bash
cd /Users/jesse.kemp/Dev/cortex

# Run your first daily scan
./daily_scan.sh

# Done! Review the output for high-priority signals.
```

## What Just Happened?

The scan checked:
- ✅ System health (queue, success rate, cycle time)
- 🔍 All projects for improvement opportunities
- 🎯 High-priority signals (critical and high severity)
- 💾 Saved results to `~/.cortex/latest_scan.json`

Look for signals marked:
- 🔴 **CRITICAL** - >10% improvement, deploy immediately
- 🟡 **HIGH** - 5-10% improvement, schedule this week
- 💡 **MEDIUM** - Test failures, security checks, add to backlog

## Next Steps

### Today (5 minutes)
1. **View the dashboard:**
   ```bash
   ./launch_dashboard.sh
   ```
   Opens at http://localhost:8501 with interactive intelligence view

2. **Take action on critical signals:**
   ```bash
   # Generate improvement plan
   ./cortex_mvp generate <signal_id>

   # Execute improvement
   ./cortex_mvp execute <contract_id> --auto
   ```

### This Week
1. Run `./daily_scan.sh` manually each morning
2. Review signals and execute 1-2 high-priority improvements
3. Get comfortable with the workflow

### Next Week
1. **Enable automation:**
   ```bash
   ./install_automation.sh
   ```
   This runs daily scans automatically at 8am

2. **Run weekly report:**
   ```bash
   ./weekly_report.sh
   ```
   Shows activity summary and cumulative impact

## File Guide

| File | What It Does |
|------|--------------|
| **daily_scan.sh** | Run this daily (manual or auto at 8am) |
| **weekly_report.sh** | Run this weekly for activity summary |
| **install_automation.sh** | Enable automatic 8am scans |
| **uninstall_automation.sh** | Disable automation |
| **launch_dashboard.sh** | Open interactive intelligence view |
| **cortex_mvp** | Generate contracts and execute improvements |

## Documentation

| Document | Read When |
|----------|-----------|
| **DAILY_QUICK_START.md** | Right now (5 min read) |
| **DAILY_WORKFLOW.md** | After first week (15 min read) |
| **automation/README.md** | Before enabling automation (10 min read) |
| **AUTOMATION_SETUP_COMPLETE.md** | For technical details |
| **README_DAILY_AUTOMATION.md** | For comprehensive overview |

## Example Workflow

### Monday Morning (5 minutes)
```bash
# 1. Scan (automatic or manual)
./daily_scan.sh

# Example output:
# 🔴 CRITICAL: Deploy ecmwf for wind_direction - +12.0% improvement
# 🟡 HIGH: Deploy ecmwf for wind_speed - +6.7% improvement
# 💡 MEDIUM: Fix 9 recurring test failures in VortexV2

# 2. Take action on critical
./cortex_mvp generate validation_gap_ecmwf_wind_direction_20260125
./cortex_mvp execute contract_xyz123 --auto

# Done! Total time: 3 minutes
```

### Friday Afternoon (15 minutes)
```bash
# Weekly review
./weekly_report.sh

# Example output:
# Contracts Generated: 7
# Executions Completed: 5
# Cumulative improvements: VortexV2 wind accuracy +12%

# Review dashboard
./launch_dashboard.sh
# Check execution outcomes
# Plan next week's priorities
```

## What Makes This Different?

Traditional approach:
- Manual code reviews
- Occasional refactoring sprints
- Miss small improvements
- Improvements languish undeployed

Cortex approach:
- **Daily detection** - Automatic opportunity scanning
- **Small validated changes** - Deploy frequently, low risk
- **Closed feedback loop** - Learning from outcomes
- **5 minutes daily** - Sustainable habit, not a chore

## Success Metrics

After 1 month, you should see:
- **Detection rate > 80%** - Most improvements caught automatically
- **Execution rate > 60%** - High-quality signals worth deploying
- **Impact > 5% per project** - Cumulative accuracy gains
- **Velocity < 48 hours** - Fast deployment of critical improvements

## Troubleshooting

### No signals detected?
Projects may need validation data first. Check:
```bash
./cortex_mvp health
```

### Script won't run?
Make sure you're in the cortex directory:
```bash
cd /Users/jesse.kemp/Dev/cortex
./daily_scan.sh
```

### Dashboard won't open?
Install Streamlit:
```bash
source venv/bin/activate
pip install streamlit
./launch_dashboard.sh
```

## Philosophy

**Make continuous improvement a habit, not a chore.**

- 5 minutes daily → Quick scan and prioritize
- 15 minutes weekly → Review and adjust
- 30 minutes monthly → Optimize and tune

The goal: Deploy small, validated improvements continuously rather than big refactoring sprints occasionally.

## Getting Help

- Quick questions: Read `DAILY_QUICK_START.md`
- Full workflow: Read `DAILY_WORKFLOW.md`
- Health check: Run `./cortex_mvp health`
- View logs: Check `~/.cortex/logs/`

## Your First Action

**Right now, run:**
```bash
./daily_scan.sh
```

**Then read the output and decide:**
- Any critical signals? → Generate and execute contract
- Any high signals? → Schedule for this week
- Medium signals? → Add to backlog

**That's it. You're using Cortex intelligence.**

---

**System Status:** ✅ All 24 tests passed
**Documentation:** ✅ Complete (5 guides, 34 KB)
**Scripts:** ✅ Tested and working
**Automation:** ✅ Ready to enable

**Start now:** `./daily_scan.sh`
