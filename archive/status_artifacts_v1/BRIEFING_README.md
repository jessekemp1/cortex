# Cortex Daily Briefing System

Automated daily briefing system that synthesizes status across all projects.

## Features

- **Portfolio Pulse**: Active projects, recent commits, blockers
- **Priority Actions**: Top 3 recommended next steps
- **Patterns Noticed**: Activity trends, productivity patterns
- **Waiting On**: Decisions needed from user

## Quick Start

### Basic Usage

```bash
# Generate daily briefing (from /Users/jesse.kemp/Dev directory)
cd /Users/jesse.kemp/Dev
python3 cortex/cli.py briefing

# Or use the wrapper script
./cortex/cortex briefing
```

### Output Formats

```bash
# Text format (default, with colors)
python3 cortex/cli.py briefing

# Text format without colors
python3 cortex/cli.py briefing --no-color

# JSON format (machine-readable)
python3 cortex/cli.py briefing --format=json
```

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
     Priority A goal from ACTION_PLAN.md.
  2. [MEDIUM] Maximize momentum in keto-tracker
     Project: keto-tracker
     High activity indicates good flow state and deep context.
  3. [MEDIUM] Alpha Arena - Trading Engine Hardening
     Project: alpha_arena
     Priority B goal from ACTION_PLAN.md.

PATTERNS NOTICED
  keto-tracker momentum: 13 commits this week

WAITING ON YOU
  Nothing waiting on your input
================================================================
```

## Scheduling

### Using Cron (Recommended)

Schedule daily briefing at 8 AM:

```bash
# Add to crontab
crontab -e

# Add this line:
0 8 * * * cd /Users/jesse.kemp/Dev && python3 cortex/cli.py briefing > ~/briefing.txt
```

### Using Python Scheduler

```bash
# Schedule briefing using built-in scheduler
cd /Users/jesse.kemp/Dev/cortex
python3 scheduler.py --schedule "0 8 * * *"

# Check schedule status
python3 scheduler.py --status

# Unschedule
python3 scheduler.py --unschedule

# Run briefing manually
python3 scheduler.py --run
```

### Cron Schedule Examples

```
0 8 * * *      # Daily at 8:00 AM
0 9 * * 1      # Every Monday at 9:00 AM
0 17 * * 5     # Every Friday at 5:00 PM
0 */6 * * *    # Every 6 hours
```

## Advanced Usage

### Save to File

```bash
# Save to file
python3 cortex/cli.py briefing --no-color > ~/daily-briefing.txt

# Save JSON to file
python3 cortex/cli.py briefing --format=json > ~/briefing.json
```

### Email Delivery

Configure email delivery using scheduler:

```bash
cd /Users/jesse.kemp/Dev/cortex
python3 -c "
from scheduler import BriefingScheduler

scheduler = BriefingScheduler()
scheduler.schedule_briefing(
    cron_expression='0 8 * * *',
    output_file='/tmp/briefing.txt',
    email_to='your-email@example.com'
)
"
```

Note: Email delivery requires local sendmail or SMTP configuration.

## Data Sources

The briefing system integrates with:

1. **ai_intelligence.py** - Scans all projects for git activity
2. **goal_parser.py** - Parses ACTION_PLAN.md for goals and priorities
3. **recommendation_engine.py** - Generates strategic recommendations
4. **context_intelligence.py** - Predicts needed context (optional)

## Customization

### Custom Root Directory

```bash
# Use different root directory
python3 cortex/cli.py briefing --root /path/to/projects
```

### Programmatic Usage

```python
from pathlib import Path
from briefing import generate_daily_briefing, format_briefing

# Generate briefing
briefing = generate_daily_briefing(root_dir=Path("/Users/jesse.kemp/Dev"))

# Format as text
output = format_briefing(briefing, use_color=True)
print(output)

# Access raw data
print(f"Active projects: {briefing.active_projects}")
print(f"Recent commits (24h): {briefing.recent_commits_24h}")
print(f"Priority actions: {briefing.priority_actions}")
```

## Troubleshooting

### No Projects Detected

If no projects are detected, ensure:

1. Running from correct directory: `/Users/jesse.kemp/Dev`
2. Projects have `.git` directories
3. Projects have recent commits

### No Recommendations

If no recommendations appear:

1. Check that `recommendation_engine.py` is in `/Users/jesse.kemp/Dev/scripts/`
2. Verify ACTION_PLAN.md exists at `/Users/jesse.kemp/Dev/ACTION_PLAN.md`
3. Check for Python import errors

### Colors Not Working

If colors don't appear:

1. Install colorama: `pip install colorama`
2. Or use `--no-color` flag for plain text

## Architecture

```
briefing.py
├── BriefingGenerator
│   ├── generate_daily_briefing()    # Main entry point
│   ├── _get_active_projects()       # Portfolio analysis
│   ├── _get_priority_actions()      # Recommendation synthesis
│   ├── _detect_patterns()           # Activity pattern detection
│   └── _get_waiting_on()            # Blocker detection
│
├── format_briefing()                # Text formatter
└── format_briefing_json()           # JSON formatter

scheduler.py
├── BriefingScheduler
│   ├── schedule_briefing()          # Schedule with cron
│   ├── run_briefing()               # Execute briefing
│   └── unschedule_briefing()        # Remove schedule

cli.py
└── cmd_briefing()                   # CLI command handler
```

## File Locations

```
/Users/jesse.kemp/Dev/
├── cortex/
│   ├── briefing.py              # Briefing generator
│   ├── scheduler.py             # Scheduling system
│   ├── cli.py                   # CLI with briefing command
│   └── cortex                   # Wrapper script
├── scripts/
│   ├── ai_intelligence.py       # Project scanner
│   ├── goal_parser.py           # Goal parser
│   └── recommendation_engine.py # Recommendation engine
└── ACTION_PLAN.md               # Goals and priorities
```

## Future Enhancements

Potential improvements:

1. **Slack/Discord integration** - Send briefings to team channels
2. **Time-based patterns** - "Most productive: Morning sessions (9-11am)"
3. **Velocity tracking** - Commits/day trends over time
4. **Goal progress tracking** - % completion visualization
5. **Interactive mode** - Ask follow-up questions
6. **Multiple output formats** - HTML, PDF, Markdown
7. **Historical analysis** - Compare with previous briefings

## See Also

- [Cortex README](README.md) - Main Cortex documentation
- [Design Spec](DESIGN_SPEC.md) - Architecture and design
- [Integration Guide](INTEGRATION_GUIDE.md) - Integration with other tools
