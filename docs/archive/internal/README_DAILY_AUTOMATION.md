# Cortex Daily Automation System

**Quick Start:** Run `./daily_scan.sh` to get started immediately.

## What This Is

An automated daily workflow system that makes Cortex continuous improvement intelligence a habit, not a tool you occasionally remember.

## Key Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `daily_scan.sh` | Morning scan for opportunities | `./daily_scan.sh` |
| `weekly_report.sh` | Weekly activity summary | `./weekly_report.sh` |
| `install_automation.sh` | Enable 8am daily scans | `./install_automation.sh` |
| `uninstall_automation.sh` | Disable automation | `./uninstall_automation.sh` |

## Documentation

| Document | What It Covers |
|----------|----------------|
| **DAILY_QUICK_START.md** | Get started in 5 minutes |
| **DAILY_WORKFLOW.md** | Complete workflow guide |
| **automation/README.md** | LaunchAgent setup details |
| **AUTOMATION_SETUP_COMPLETE.md** | Implementation summary |

## 30-Second Start

```bash
# 1. Run your first scan
./daily_scan.sh

# 2. View results in dashboard
./launch_dashboard.sh

# 3. (Optional) Enable automatic daily scans
./install_automation.sh
```

## What You Get

### Daily (5 minutes)
- Automated scan for improvement opportunities
- High-priority signals surfaced clearly
- Clear next actions (generate contracts, execute improvements)
- Logged to `~/.cortex/logs/daily_scan.log`

### Weekly (15 minutes)
- Activity summary (contracts, executions, memories)
- Recent improvements and impact metrics
- Execution history with timestamps
- Saved to `~/.cortex/logs/weekly_report_YYYYMMDD.log`

### Continuous
- Validation gaps detected (better models not deployed)
- Test failures tracked (recurring issues)
- Security issues flagged (exposed secrets)
- Learning from outcomes (closed feedback loop)

## File Locations

```
/Users/jesse.kemp/Dev/cortex/
├── daily_scan.sh              # Morning scan
├── weekly_report.sh           # Weekly summary
├── install_automation.sh      # Enable automation
├── uninstall_automation.sh    # Disable automation
├── DAILY_QUICK_START.md       # Quick reference
├── DAILY_WORKFLOW.md          # Complete guide
└── automation/
    ├── com.cortex.daily.plist # LaunchAgent config
    └── README.md              # Automation docs

~/.cortex/
├── logs/
│   ├── daily_scan.log         # Scan output
│   └── weekly_report_*.log    # Weekly reports
├── latest_scan.json           # Most recent scan
├── signals/                   # All detected signals
├── contracts/                 # Generated plans
└── execution_results/         # Applied improvements
```

## Signal Types

| Type | What It Detects | Priority |
|------|-----------------|----------|
| **validation_gap** | Better model validated but not deployed | Critical/High |
| **test_failure** | Recurring test failures | Medium |
| **security** | Exposed secrets, vulnerabilities | High |

## Daily Workflow

1. **Morning scan** (automatic at 8am or manual)
   ```bash
   ./daily_scan.sh
   ```

2. **Review signals** (check output or dashboard)
   - 🔴 Critical (>10% improvement) → Deploy immediately
   - 🟡 High (5-10% improvement) → Schedule this week
   - 💡 Medium (test fixes, security) → Add to backlog

3. **Take action** (generate and execute contracts)
   ```bash
   ./cortex_mvp generate <signal_id>
   ./cortex_mvp execute <contract_id> --auto
   ```

4. **Verify** (check dashboard for outcomes)
   ```bash
   ./launch_dashboard.sh
   ```

## Automation

### Enable Daily Scans at 8am
```bash
./install_automation.sh
```

This sets up a macOS LaunchAgent that:
- Runs `daily_scan.sh` every day at 8:00 AM
- Logs output to `~/.cortex/logs/daily_scan.log`
- Logs errors to `~/.cortex/logs/daily_scan_error.log`
- Persists across reboots

### Test It Now
```bash
launchctl start com.cortex.daily
```

### Disable Automation
```bash
./uninstall_automation.sh
```

You can still run manual scans anytime.

## Examples

### Example Daily Scan Output
```
🌅 Cortex Daily Scan - 2026-01-25

📊 System Health:
✅ Queue Depth: 7 (optimal: 3-8)
✅ Success Rate: 100.0% (optimal: >85%)
✅ Avg Cycle Time: 1.0h (optimal: <4h)

🔍 Scanning for new opportunities...
Found 4 signals

🎯 High-Priority Signals:
  🟡 HIGH: Check for exposed .env files in git history
     Impact: Prevent secret exposure and security vulnerabilities
     ID: security_env_files_20260125

📈 Total Signals: 4
   Critical: 0
   High: 1
   Medium: 3
   Low: 0

✅ Daily scan complete. Review signals in dashboard:
   ./launch_dashboard.sh
```

### Example Weekly Report Output
```
📈 Cortex Weekly Report - Week of 2026-01-25

📊 Activity (Last 7 Days):
  Contracts Generated: 7
  Executions Completed: 5
  Signals Detected: 5
  Memories Captured: 1

🎯 Recent Improvements:
  VortexV2 Production Config:
    Last updated: 2026-01-25 18:11

📋 Recent Contracts: [5 most recent with timestamps]
⚡ Recent Executions: [5 most recent with timestamps]

✅ Weekly report complete
```

## Troubleshooting

### No signals detected
```bash
# Lower detection thresholds
./cortex_mvp scan --verbose --threshold-low
```

### Scripts won't run
```bash
# Make executable
chmod +x *.sh
```

### Dashboard won't open
```bash
# Install Streamlit
source venv/bin/activate
pip install streamlit
```

### Automation not running
```bash
# Check if loaded
launchctl list | grep cortex

# Reinstall if needed
./uninstall_automation.sh
./install_automation.sh
```

## Philosophy

**Make continuous improvement a habit:**
- 5 minutes daily - Quick scan and prioritize
- 15 minutes weekly - Review and adjust
- 30 minutes monthly - Optimize and tune

**Deploy small validated improvements frequently** rather than big refactoring sprints occasionally.

## Success Metrics

Track these to measure effectiveness:
- **Detection Rate** - % of improvements caught by Cortex vs manual
- **Execution Rate** - % of signals that become deployed improvements
- **Impact** - Cumulative accuracy improvements across projects
- **Velocity** - Time from signal detection to production deployment
- **Quality** - % of executions that improve metrics

Target goals:
- Detection rate > 80%
- Execution rate > 60%
- Impact > 5% per month per project
- Velocity < 48 hours for critical signals
- Quality > 90%

## Integration

### With Existing Tools
- **cortex_mvp** - Main CLI for generate/execute
- **launch_dashboard.sh** - Interactive view
- **Claude commands** - /status, /next, /briefing

### With Projects
- **VortexV2** - Validation gap detection
- **Alpha Arena** - Trading outcome learning
- **Cortex** - Self-improvement signals

## Getting Help

- **Quick start**: Read `DAILY_QUICK_START.md`
- **Full guide**: Read `DAILY_WORKFLOW.md`
- **Automation**: Read `automation/README.md`
- **Health check**: Run `./cortex_mvp health`
- **View logs**: Check `~/.cortex/logs/`

## Status

✅ **Tested and ready for use**
- All scripts work correctly
- Documentation complete
- Automation optional but ready
- Production-ready

Start now: `./daily_scan.sh`
