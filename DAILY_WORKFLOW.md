# Cortex Daily Workflow

A comprehensive guide to making Cortex intelligence a daily habit that continuously improves your projects.

## Overview

Cortex operates in a continuous improvement cycle:
1. **Scan** - Detect opportunities (validation gaps, test failures, security issues)
2. **Analyze** - Generate actionable contracts for improvements
3. **Execute** - Apply improvements automatically or manually
4. **Learn** - Record outcomes to improve future recommendations

## Morning Routine (5 minutes)

### 1. Daily Scan

Run the automated scan to detect opportunities:

```bash
cd /Users/jesse.kemp/Dev/cortex
./daily_scan.sh
```

This will:
- Check system health (API access, data availability)
- Scan all projects for improvement opportunities
- Surface high-priority signals (critical and high severity)
- Log results to `~/.cortex/logs/daily_scan.log`

**What to look for:**
- 🔴 **Critical signals** - Deploy immediately (>10% improvement)
- 🟡 **High signals** - Schedule for this week (5-10% improvement)
- 🟢 **Medium signals** - Add to backlog (test failures, security checks)

### 2. Review Dashboard

Open the interactive dashboard:

```bash
./launch_dashboard.sh
```

Navigate through:
- **Signals Tab** - All detected opportunities with details
- **Health Tab** - System status and data freshness
- **Contracts Tab** - Generated improvement plans
- **Executions Tab** - Applied improvements and outcomes

### 3. Prioritize Actions

Based on the scan results, decide:
- **Auto-execute** - High-confidence, low-risk improvements
- **Manual review** - Changes requiring verification
- **Defer** - Lower priority items for later

## When to Generate Contracts

Contracts are detailed improvement plans. Generate them for:

### High-Priority Signals
When you see a validated improvement ready to deploy:

```bash
./cortex_mvp generate <signal_id>
```

Example:
```bash
./cortex_mvp generate validation_gap_ecmwf_wind_speed_20260124
```

This creates:
- Detailed implementation plan
- Risk assessment
- Rollback strategy
- Test validation steps
- Success metrics

### Batch Processing
For multiple related improvements:

```bash
./cortex_mvp generate --batch --severity critical,high
```

This generates contracts for all critical and high-severity signals.

## When to Execute

### Automatic Execution (Recommended)

For low-risk, high-confidence improvements:

```bash
./cortex_mvp execute <contract_id> --auto
```

**Use auto-execute for:**
- Configuration changes with validation data
- Dependency updates with passing tests
- Documentation improvements
- Test fixes with clear solutions

### Manual Execution

For changes requiring human oversight:

```bash
./cortex_mvp execute <contract_id> --review
```

This will:
1. Show the detailed plan
2. Ask for confirmation at each step
3. Allow you to modify or skip steps
4. Pause for verification points

**Use manual execute for:**
- Production config changes
- Database migrations
- API contract changes
- Security-related updates

### Dry Run

To see what would happen without making changes:

```bash
./cortex_mvp execute <contract_id> --dry-run
```

## Weekly Review Process (15 minutes)

Run every Monday morning:

```bash
./weekly_report.sh
```

This generates a comprehensive report showing:
- Activity metrics (contracts, executions, signals, memories)
- Recent improvements deployed
- Active improvement percentages by project
- Top contracts and executions from the week

### Review Questions

1. **Velocity** - Are we detecting and deploying improvements regularly?
2. **Impact** - What accuracy gains did we achieve this week?
3. **Coverage** - Are all projects being scanned and improved?
4. **Blockers** - Are there recurring signals not being addressed?

### Action Items

Based on the weekly report:
- Identify patterns in unexecuted contracts
- Schedule time for manual-review items
- Adjust auto-execution thresholds
- Update project-specific scan rules

## Monthly Optimization (30 minutes)

First Monday of each month:

### 1. Performance Analysis

Review the cumulative impact:

```bash
./cortex_mvp stats --period 30d
```

Metrics to track:
- Total improvements deployed
- Cumulative accuracy gains by project
- Contract success rate
- Execution error rate
- Signal detection accuracy

### 2. Tune Detection Rules

Based on false positives or missed opportunities:

```bash
./cortex_mvp tune --analyze
```

This shows:
- Signal types with low execution rate (possibly false positives)
- Gaps in detection (manually deployed improvements not caught by Cortex)
- Threshold adjustments for severity levels

### 3. Update Learning Memory

Review and curate the memory bank:

```bash
./cortex_mvp memory --review
```

- Archive outdated patterns
- Tag high-value learnings
- Update anti-patterns
- Merge similar memories

## Automation Setup (Optional)

To run daily scans automatically at 8am, set up a LaunchAgent.

### Step 1: Create LaunchAgent

Copy the plist file from this directory:

```bash
cp automation/com.cortex.daily.plist ~/Library/LaunchAgents/
```

### Step 2: Load the Agent

```bash
launchctl load ~/Library/LaunchAgents/com.cortex.daily.plist
```

### Step 3: Verify

Check that it's scheduled:

```bash
launchctl list | grep cortex
```

### Step 4: Monitor

Logs are written to:
- Standard output: `~/.cortex/logs/daily_scan.log`
- Errors: `~/.cortex/logs/daily_scan_error.log`

### Disable Automation

If you prefer manual scans:

```bash
launchctl unload ~/Library/LaunchAgents/com.cortex.daily.plist
```

## Best Practices

### 1. Start Small
- First week: Run daily scan, observe signals
- Second week: Execute 1-2 high-confidence contracts manually
- Third week: Enable auto-execution for config changes
- Fourth week: Full automation with weekly reviews

### 2. Trust but Verify
- Always review execution results in the dashboard
- Check that deployed improvements actually improved metrics
- Report false positives to improve detection

### 3. Close the Loop
- After manual deployments, tell Cortex about them:
  ```bash
  ./cortex_mvp feedback --execution <exec_id> --outcome success
  ```
- This improves future recommendations

### 4. Maintain Signal Quality
- If a signal type consistently produces poor contracts, tune it:
  ```bash
  ./cortex_mvp tune --signal-type validation_gap --threshold 8.0
  ```
- Balance between sensitivity (catch everything) and specificity (only high-quality signals)

## Troubleshooting

### No Signals Detected

Possible causes:
1. **No validation data** - Ensure validation jobs are running
2. **Scan scope too narrow** - Check scan configuration
3. **Thresholds too high** - Lower severity thresholds

Fix:
```bash
./cortex_mvp scan --verbose --threshold-low
```

### Execution Failures

Common issues:
1. **Missing dependencies** - Check venv is activated
2. **File permissions** - Ensure write access to target files
3. **Git conflicts** - Clean working directory required

Fix:
```bash
./cortex_mvp health --check-dependencies
git status  # Ensure clean state
```

### High False Positive Rate

If contracts are generated but not worth executing:
1. Review detection rules
2. Adjust minimum improvement thresholds
3. Add project-specific filters

Fix:
```bash
./cortex_mvp tune --signal-type <type> --min-improvement 10.0
```

## Integration with Other Tools

### With /status Command

Check Cortex health as part of project status:

```bash
/status
# Includes Cortex signal count and recent activity
```

### With /next Command

Get Cortex-powered recommendations:

```bash
/next
# Shows highest-priority signal as next recommended action
```

### With /briefing Command

Morning briefing includes Cortex scan results:

```bash
/briefing
# Includes critical signals and recommended actions
```

## File Locations

- **Scripts**: `/Users/jesse.kemp/Dev/cortex/`
  - `daily_scan.sh` - Morning scan script
  - `weekly_report.sh` - Weekly summary
  - `launch_dashboard.sh` - Interactive dashboard
  - `cortex_mvp` - Main CLI wrapper

- **Data**: `~/.cortex/`
  - `latest_scan.json` - Most recent scan results
  - `signals/` - All detected signals
  - `contracts/` - Generated improvement plans
  - `execution_results/` - Applied improvements
  - `logs/` - Scan and report logs

- **Automation**: `~/Library/LaunchAgents/`
  - `com.cortex.daily.plist` - Daily scan scheduler

## Quick Reference

| Task | Command |
|------|---------|
| Run daily scan | `./daily_scan.sh` |
| View dashboard | `./launch_dashboard.sh` |
| Generate contract | `./cortex_mvp generate <signal_id>` |
| Execute contract | `./cortex_mvp execute <contract_id>` |
| Weekly report | `./weekly_report.sh` |
| Check health | `./cortex_mvp health` |
| View stats | `./cortex_mvp stats` |
| Tune detection | `./cortex_mvp tune` |
| Provide feedback | `./cortex_mvp feedback` |

## Success Metrics

Track these to measure Cortex effectiveness:

1. **Detection Rate** - % of improvements caught by Cortex vs manual
2. **Execution Rate** - % of signals that become deployed improvements
3. **Impact** - Cumulative accuracy improvements across projects
4. **Velocity** - Time from signal detection to production deployment
5. **Quality** - % of executions that improve metrics vs no effect/regression

Target goals:
- Detection rate > 80% (most improvements caught automatically)
- Execution rate > 60% (high-quality signals)
- Impact > 5% cumulative improvement per month per project
- Velocity < 48 hours for critical signals
- Quality > 90% (very few false positives or regressions)

## Philosophy

Cortex is designed to be a **continuous improvement assistant**, not a replace-your-judgment tool:

- **You decide** which improvements to deploy
- **Cortex detects** opportunities you might miss
- **You verify** that improvements actually improve
- **Cortex learns** from your decisions

The goal is to make quality improvements a daily habit rather than occasional refactoring sprints.
