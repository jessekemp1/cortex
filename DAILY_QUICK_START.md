# Cortex Daily Workflow - Quick Start

Get started with automated daily Cortex intelligence in 5 minutes.

## TL;DR

```bash
cd /Users/jesse.kemp/Dev/cortex

# Run your first daily scan
./daily_scan.sh

# View the interactive dashboard
./launch_dashboard.sh

# (Optional) Enable automatic daily scans at 8am
./install_automation.sh
```

## What You Get

1. **Daily Scan** - Automatic detection of improvement opportunities
   - Validation gaps (better models validated but not deployed)
   - Test failures (recurring test issues to fix)
   - Security issues (exposed secrets, vulnerabilities)

2. **Weekly Report** - Summary of activity and improvements
   - Contracts generated
   - Improvements deployed
   - Cumulative impact metrics

3. **Interactive Dashboard** - Real-time intelligence view
   - All signals with severity levels
   - System health status
   - Contract details and execution history

## First Run

### 1. Run Daily Scan

```bash
./daily_scan.sh
```

This will:
- Check system health
- Scan all projects for opportunities
- Show high-priority signals
- Save results to `~/.cortex/latest_scan.json`

Example output:
```
🌅 Cortex Daily Scan - 2026-01-25

📊 System Health:
✅ Queue Depth: 7 (optimal: 3-8)
✅ Success Rate: 100.0% (optimal: >85%)

🔍 Scanning for new opportunities...
Found 6 signals

🎯 High-Priority Signals:
  🔴 CRITICAL: Deploy ecmwf for wind_direction - +12.0% improvement
     Impact: +12.0% wind_direction forecast accuracy improvement
     ID: validation_gap_ecmwf_wind_direction_20260125

  🟡 HIGH: Deploy ecmwf for wind_speed - +6.7% improvement
     Impact: +6.7% wind_speed forecast accuracy improvement
     ID: validation_gap_ecmwf_wind_speed_20260125
```

### 2. Review in Dashboard

```bash
./launch_dashboard.sh
```

Opens at `http://localhost:8501` with:
- **Signals tab** - All detected opportunities sorted by severity
- **Health tab** - System status and data availability
- **Contracts tab** - Generated improvement plans
- **Executions tab** - Applied improvements and outcomes

### 3. Take Action on High-Priority Signals

For a critical signal (>10% improvement):

```bash
# Generate a contract (improvement plan)
./cortex_mvp generate validation_gap_ecmwf_wind_direction_20260125

# Review the plan in dashboard, then execute
./cortex_mvp execute <contract_id> --auto
```

## Daily Routine (5 minutes)

### Morning

```bash
# 1. Run scan (or it runs automatically at 8am)
./daily_scan.sh

# 2. Check for critical signals in output
# Look for: 🔴 CRITICAL or 🟡 HIGH

# 3. Generate and execute high-priority contracts
./cortex_mvp generate <signal_id>
./cortex_mvp execute <contract_id> --auto
```

### Review (when you have time)

```bash
# Open dashboard for detailed view
./launch_dashboard.sh

# Review medium-priority signals
# Schedule test fixes, security checks
```

## Weekly Routine (15 minutes)

```bash
# Run weekly report
./weekly_report.sh

# Review metrics:
# - How many improvements deployed?
# - What was the cumulative impact?
# - Any patterns in unexecuted contracts?
```

## Automation Setup

To run daily scans automatically at 8am:

```bash
./install_automation.sh
```

This will:
1. Copy LaunchAgent plist to `~/Library/LaunchAgents/`
2. Load the agent with `launchctl`
3. Verify it's scheduled
4. Show log locations

To disable later:
```bash
./uninstall_automation.sh
```

## What to Do with Signals

### Critical Signals (🔴)
**>10% improvement, deploy immediately**

```bash
./cortex_mvp generate <signal_id>
./cortex_mvp execute <contract_id> --auto
```

### High Signals (🟡)
**5-10% improvement, schedule this week**

```bash
./cortex_mvp generate <signal_id>
# Review in dashboard, then:
./cortex_mvp execute <contract_id> --review
```

### Medium Signals (💡)
**Test failures, security checks, add to backlog**

- Review in dashboard
- Group related signals
- Schedule dedicated time for test fixes

### Low Signals (ℹ️)
**Minor improvements, defer or ignore**

- Review monthly
- Good candidates for automated execution
- Low risk, low impact

## Understanding Contracts

A contract is a detailed plan for implementing an improvement:

```json
{
  "signal_id": "validation_gap_ecmwf_wind_speed_20260124",
  "title": "Deploy ecmwf for wind_speed",
  "steps": [
    "Update production_config.json",
    "Run validation tests",
    "Deploy to API",
    "Monitor metrics"
  ],
  "risk_level": "low",
  "rollback_plan": "Revert config to previous model",
  "success_metrics": ["MAE reduction", "API response time"]
}
```

Generate with:
```bash
./cortex_mvp generate <signal_id>
```

Execute with:
```bash
# Automatic (low risk)
./cortex_mvp execute <contract_id> --auto

# Manual review (high risk)
./cortex_mvp execute <contract_id> --review

# Dry run (preview changes)
./cortex_mvp execute <contract_id> --dry-run
```

## File Locations

| File | Location |
|------|----------|
| Scripts | `/Users/jesse.kemp/Dev/cortex/` |
| Scan results | `~/.cortex/latest_scan.json` |
| Signals | `~/.cortex/signals/` |
| Contracts | `~/.cortex/contracts/` |
| Executions | `~/.cortex/execution_results/` |
| Logs | `~/.cortex/logs/` |
| Dashboard data | `~/.cortex/` (various JSON files) |

## Troubleshooting

### "No signals detected"

Possible causes:
1. Projects don't have validation data yet
2. Scan thresholds are too high
3. No improvements available (rare!)

Fix:
```bash
./cortex_mvp scan --verbose --threshold-low
```

### "Command not found: cortex_mvp"

The script is in the cortex directory:
```bash
cd /Users/jesse.kemp/Dev/cortex
./cortex_mvp health
```

### "Dashboard won't open"

Check if Streamlit is installed:
```bash
source venv/bin/activate
pip install streamlit
./launch_dashboard.sh
```

### "Execution failed"

Check the execution result:
```bash
cat ~/.cortex/execution_results/<contract_id>_result.json
```

Common issues:
- Git working directory not clean
- Missing dependencies
- File permission errors

## Tips for Success

1. **Start with manual execution** - Get comfortable with the workflow before enabling auto-execution
2. **Review outcomes** - After deploying an improvement, verify it actually improved metrics
3. **Tune detection** - If you get too many false positives, adjust thresholds
4. **Close the loop** - Tell Cortex about manual improvements so it learns
5. **Check logs** - If automation is enabled, review logs weekly for issues

## Next Steps

1. Read the full guide: `DAILY_WORKFLOW.md`
2. Explore the dashboard: Click through all tabs
3. Review a contract: Generate one and read the plan
4. Execute your first improvement: Start with a low-risk config change
5. Enable automation: Set up daily scans at 8am

## Philosophy

Cortex is designed to make continuous improvement a **habit**, not a chore:

- **5 minutes daily** - Quick scan and prioritize
- **15 minutes weekly** - Review and adjust
- **30 minutes monthly** - Optimize and tune

The goal: Deploy small, validated improvements continuously rather than big refactoring sprints occasionally.

## Getting Help

- Check health: `./cortex_mvp health`
- View stats: `./cortex_mvp stats`
- Full docs: `DAILY_WORKFLOW.md`
- Automation help: `automation/README.md`
