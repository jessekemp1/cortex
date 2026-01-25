# Cortex Daily Workflow Automation - Setup Complete

**Date:** 2026-01-25
**Status:** ✅ Ready for Use

## What Was Built

A comprehensive automated daily workflow system for continuous Cortex intelligence.

### 1. Daily Scan Script (`daily_scan.sh`)
Automated morning scan that:
- Checks system health (queue depth, success rate, cycle time)
- Scans all projects for improvement opportunities
- Surfaces high-priority signals (critical and high severity)
- Logs results to `~/.cortex/logs/daily_scan.log`

**Usage:**
```bash
./daily_scan.sh
```

**Output:**
- System health metrics
- Signal count by severity
- High-priority signals with IDs and impact
- Link to dashboard for details

### 2. Weekly Report Script (`weekly_report.sh`)
Comprehensive weekly summary that:
- Counts activity (contracts, executions, signals, memories)
- Shows recent improvements and configurations
- Lists recent contracts and executions
- Generates timestamped report logs

**Usage:**
```bash
./weekly_report.sh
```

**Output:**
- Activity metrics for last 7 days
- VortexV2 production config status
- Recent contracts with creation times
- Recent executions with completion times
- Saved to `~/.cortex/logs/weekly_report_YYYYMMDD.log`

### 3. LaunchAgent Configuration (`automation/com.cortex.daily.plist`)
macOS LaunchAgent for automated scheduling:
- Runs daily at 8:00 AM
- Logs to `~/.cortex/logs/daily_scan.log`
- Errors to `~/.cortex/logs/daily_scan_error.log`
- Configurable schedule, weekday-only option

**Features:**
- Automatic environment setup (PATH, working directory)
- Background execution (no terminal required)
- Persistent across reboots
- Standard macOS automation

### 4. Installation Scripts
Easy setup and removal:

**`install_automation.sh`**
- Checks prerequisites
- Copies LaunchAgent plist
- Loads agent with launchctl
- Verifies installation
- Shows test commands

**`uninstall_automation.sh`**
- Unloads LaunchAgent
- Removes plist file
- Clean removal with confirmation

### 5. Documentation

**`DAILY_WORKFLOW.md` (9.9 KB)**
Comprehensive guide covering:
- Morning routine (5 min)
- When to generate contracts
- When to execute (auto vs manual)
- Weekly review process (15 min)
- Monthly optimization (30 min)
- Automation setup
- Best practices and troubleshooting
- Integration with other tools
- Success metrics and philosophy

**`DAILY_QUICK_START.md` (7.2 KB)**
Quick reference with:
- TL;DR commands
- First run walkthrough
- Daily and weekly routines
- Signal prioritization guide
- Contract understanding
- File locations
- Troubleshooting
- Next steps

**`automation/README.md` (5.2 KB)**
LaunchAgent-specific documentation:
- Installation steps
- Testing procedures
- Monitoring and logs
- Configuration customization
- Linux/cron alternative
- Troubleshooting
- Security considerations

### 6. Log Directory
Created `~/.cortex/logs/` for:
- `daily_scan.log` - Standard output from daily scans
- `daily_scan_error.log` - Error output from daily scans
- `weekly_report_YYYYMMDD.log` - Weekly reports with timestamps

## File Structure

```
/Users/jesse.kemp/Dev/cortex/
├── daily_scan.sh                    # Morning scan script
├── weekly_report.sh                 # Weekly summary script
├── install_automation.sh            # Install LaunchAgent
├── uninstall_automation.sh          # Remove LaunchAgent
├── DAILY_WORKFLOW.md                # Comprehensive guide
├── DAILY_QUICK_START.md             # Quick reference
├── automation/
│   ├── com.cortex.daily.plist      # LaunchAgent config
│   └── README.md                    # Automation docs
└── (existing files: cortex_mvp, launch_dashboard.sh, etc.)

~/.cortex/
├── logs/
│   ├── daily_scan.log              # Scan output
│   ├── daily_scan_error.log        # Scan errors
│   └── weekly_report_*.log         # Weekly reports
├── latest_scan.json                # Most recent scan
├── signals/                        # All signals
├── contracts/                      # Generated plans
└── execution_results/              # Applied improvements
```

## Quick Start

### Run First Scan
```bash
cd /Users/jesse.kemp/Dev/cortex
./daily_scan.sh
```

### View Dashboard
```bash
./launch_dashboard.sh
```

### Enable Automation
```bash
./install_automation.sh
```

## Tested Features

### ✅ Daily Scan Script
- [x] Executable and runs successfully
- [x] Activates venv automatically
- [x] Runs health check
- [x] Performs scan
- [x] Surfaces high-priority signals
- [x] Logs to file
- [x] Shows summary statistics
- [x] Provides next actions

**Test output:**
```
🌅 Cortex Daily Scan - Sun 25 Jan 2026 18:11:29 EST

📊 System Health:
✅ Queue Depth: 7 (optimal: 3-8)
✅ Success Rate: 100.0% (optimal: >85%)

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

📝 Log saved to: /Users/jesse.kemp/.cortex/logs/daily_scan.log
```

### ✅ Weekly Report Script
- [x] Executable and runs successfully
- [x] Counts activity from last 7 days
- [x] Shows recent improvements
- [x] Lists contracts and executions
- [x] Generates timestamped report
- [x] Provides summary statistics

**Test output:**
```
📈 Cortex Weekly Report - Week of 2026-01-25
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Activity (Last 7 Days):
  Contracts Generated: 7
  Executions Completed: 5
  Signals Detected: 5
  Memories Captured: 1

🎯 Recent Improvements:
  VortexV2 Production Config:
    Last updated: 2026-01-25 18:11

📋 Recent Contracts: [list of 5 most recent]
⚡ Recent Executions: [list of 5 most recent]

✅ Weekly report complete
📝 Report saved to: /Users/jesse.kemp/.cortex/logs/weekly_report_20260125.log
```

### ✅ Automation Scripts
- [x] Install script created and executable
- [x] Uninstall script created and executable
- [x] Prerequisites checking implemented
- [x] Error handling included
- [x] User feedback and verification
- [x] Test commands provided

### ✅ Documentation
- [x] Comprehensive workflow guide (DAILY_WORKFLOW.md)
- [x] Quick start reference (DAILY_QUICK_START.md)
- [x] Automation-specific docs (automation/README.md)
- [x] Examples and troubleshooting included
- [x] File locations and commands documented

### ✅ Log Directory
- [x] Created at `~/.cortex/logs/`
- [x] Writable by scripts
- [x] Ready for LaunchAgent output

## Success Criteria - All Met

1. ✅ **Scripts are executable and tested** - Both daily_scan.sh and weekly_report.sh work
2. ✅ **Daily scan runs successfully** - Outputs health check and signals
3. ✅ **Documentation is clear and actionable** - Three comprehensive guides created
4. ✅ **Automation is optional but ready to enable** - Install script ready, not auto-enabled
5. ✅ **Log directory created** - `~/.cortex/logs/` exists and ready

## Usage Workflow

### Daily (5 minutes)
1. Run scan (manual or automatic at 8am)
2. Review high-priority signals
3. Generate contracts for critical items
4. Execute low-risk improvements

### Weekly (15 minutes)
1. Run weekly report
2. Review cumulative metrics
3. Check execution success rate
4. Plan test fixes and security items

### Monthly (30 minutes)
1. Analyze trends and patterns
2. Tune detection thresholds
3. Update learning memory
4. Optimize automation

## Next Steps for User

### Immediate (Today)
1. Run first daily scan: `./daily_scan.sh`
2. Explore dashboard: `./launch_dashboard.sh`
3. Read quick start: `DAILY_QUICK_START.md`

### This Week
1. Run manual scans for 2-3 days
2. Generate and execute 1-2 contracts
3. Get comfortable with workflow
4. Read full workflow guide: `DAILY_WORKFLOW.md`

### Next Week
1. Enable automation: `./install_automation.sh`
2. Run first weekly report: `./weekly_report.sh`
3. Start tracking success metrics
4. Establish improvement velocity

## Integration Points

### With Existing Cortex Tools
- **`cortex_mvp`** - Main CLI for generate/execute
- **`launch_dashboard.sh`** - Interactive intelligence view
- **`~/.cortex/` data** - All scans read from existing data structures

### With Claude Commands
- **`/status`** - Can include Cortex signal count
- **`/next`** - Can pull from highest-priority signal
- **`/briefing`** - Can include daily scan summary

### With Projects
- **VortexV2** - Validation gap detection
- **Alpha Arena** - Trading outcome learning
- **Cortex** - Self-improvement signals

## Customization Options

### Change Scan Time
Edit `automation/com.cortex.daily.plist`:
```xml
<key>Hour</key>
<integer>9</integer>  <!-- Change to 9am -->
```

### Weekdays Only
Add to plist:
```xml
<key>Weekday</key>
<integer>1-5</integer>  <!-- Monday-Friday -->
```

### Multiple Daily Scans
Create array of intervals in plist (see automation/README.md)

### Custom Thresholds
Modify scan parameters in `mvp/cli.py` or add flags to scripts

## Maintenance

### Weekly
- Check logs for errors: `cat ~/.cortex/logs/daily_scan_error.log`
- Review scan output: `tail -50 ~/.cortex/logs/daily_scan.log`
- Verify automation is running: `launchctl list | grep cortex`

### Monthly
- Review false positive rate
- Tune detection thresholds
- Update documentation with learnings
- Backup important contracts and results

### As Needed
- Update scripts from git: `git pull`
- Reload LaunchAgent after updates: `./uninstall_automation.sh && ./install_automation.sh`
- Clear old logs: `find ~/.cortex/logs -mtime +30 -delete`

## Philosophy

This automation system is designed to make Cortex intelligence a **daily habit** rather than an occasional tool:

- **Minimal friction** - 5 minutes daily, 15 weekly
- **Actionable insights** - Clear priorities and next steps
- **Optional automation** - Start manual, enable when ready
- **Continuous improvement** - Small validated changes frequently

The goal is to build a **feedback loop** where:
1. Cortex detects opportunities daily
2. You deploy validated improvements quickly
3. Outcomes improve Cortex's recommendations
4. Velocity increases over time

## Support

- Quick start: `DAILY_QUICK_START.md`
- Full workflow: `DAILY_WORKFLOW.md`
- Automation help: `automation/README.md`
- Test health: `./cortex_mvp health`
- Check logs: `~/.cortex/logs/`

## Deliverables Summary

| Item | Status | Location |
|------|--------|----------|
| daily_scan.sh | ✅ Tested | `/Users/jesse.kemp/Dev/cortex/` |
| weekly_report.sh | ✅ Tested | `/Users/jesse.kemp/Dev/cortex/` |
| LaunchAgent plist | ✅ Ready | `automation/com.cortex.daily.plist` |
| DAILY_WORKFLOW.md | ✅ Complete | `/Users/jesse.kemp/Dev/cortex/` |
| DAILY_QUICK_START.md | ✅ Complete | `/Users/jesse.kemp/Dev/cortex/` |
| automation/README.md | ✅ Complete | `automation/` |
| install_automation.sh | ✅ Ready | `/Users/jesse.kemp/Dev/cortex/` |
| uninstall_automation.sh | ✅ Ready | `/Users/jesse.kemp/Dev/cortex/` |
| ~/.cortex/logs/ | ✅ Created | User home directory |

## Outcome

User now has a **clear, documented daily rhythm** that makes Cortex a habit rather than a tool they remember occasionally.

The system is:
- ✅ **Tested** - Both scripts work correctly
- ✅ **Documented** - Three comprehensive guides
- ✅ **Flexible** - Manual or automated operation
- ✅ **Production-ready** - Can enable today
- ✅ **Maintainable** - Clear logs and troubleshooting
- ✅ **Extensible** - Easy to customize

**Ready for immediate use.**
