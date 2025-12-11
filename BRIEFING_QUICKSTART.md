# Daily Briefing - Quick Start

## TL;DR

```bash
cd /Users/jesse.kemp/Dev
python3 cortex/cli.py briefing
```

## Common Commands

```bash
# Daily briefing (text)
python3 cortex/cli.py briefing

# Daily briefing (JSON)
python3 cortex/cli.py briefing --format=json

# No colors (for piping)
python3 cortex/cli.py briefing --no-color

# Save to file
python3 cortex/cli.py briefing > briefing.txt
```

## Schedule Daily (Cron)

```bash
# Edit crontab
crontab -e

# Add this line for daily 8 AM briefing
0 8 * * * cd /Users/jesse.kemp/Dev && python3 cortex/cli.py briefing > ~/briefing.txt
```

## What You Get

- **Portfolio Pulse**: Active projects, commits, blockers
- **Priority Actions**: Top 3 recommended next steps
- **Patterns**: Activity trends (momentum, sprints)
- **Waiting On**: Decisions needed from you

## Example Output

```
================================================================
DAILY BRIEFING - December 09, 2025
================================================================

PORTFOLIO PULSE
  Active projects: 2 (keto-tracker, claude-usage-optimizer)
  Recent commits: 2 in last 24h, 16 in last 7d
  Blockers: None

PRIORITY ACTIONS
  1. [HIGH] Git Repository Cleanup
  2. [MEDIUM] Maximize momentum in keto-tracker
  3. [MEDIUM] Alpha Arena - Trading Engine Hardening

PATTERNS NOTICED
  keto-tracker momentum: 13 commits this week

WAITING ON YOU
  Nothing waiting on your input
================================================================
```

## Help

```bash
# Full help
python3 cortex/cli.py briefing --help

# Full documentation
cat /Users/jesse.kemp/Dev/cortex/BRIEFING_README.md
```

## Troubleshooting

**No projects detected?**
- Make sure you're in `/Users/jesse.kemp/Dev` directory
- Projects need `.git` directories

**No colors?**
- Install colorama: `pip install colorama`
- Or use `--no-color` flag

## Files

- `/Users/jesse.kemp/Dev/cortex/briefing.py` - Generator
- `/Users/jesse.kemp/Dev/cortex/scheduler.py` - Scheduler
- `/Users/jesse.kemp/Dev/cortex/cli.py` - CLI
