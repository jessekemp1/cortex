# Cortex Quick Start

Get productive with Cortex in 5 minutes.

---

## Prerequisites

- Python 3.11+
- Git
- Anthropic API key (for AI features)

---

## Installation

```bash
cd /Users/jesse.kemp/Dev/cortex

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-lock.txt

# Set up environment
cp .env.template .env
# Edit .env and add your ANTHROPIC_API_KEY
```

---

## First Command

Check your portfolio status:

```bash
python bridge.py portfolio stats
```

**Expected output:**
```json
{
  "total_projects": 10,
  "active_projects": 7,
  "top_technologies": {
    "python": 8,
    "fastapi": 4
  }
}
```

If you see this, Cortex is working.

---

## Core Workflows

### 1. Start of Day - What Should I Work On?

```bash
# Get intelligent recommendation
python cli.py next

# Or with full briefing
python cli.py briefing
```

This queries all sources (portfolio, health, goals) and suggests the highest-impact action.

### 2. Switching Projects - Resume Context

```bash
cd /path/to/project

# Get session context
python bridge.py session-context
```

Shows: current branch, recent commits, uncommitted work, what you were doing.

### 3. Before Starting Work - Check for Patterns

```bash
# "Has anyone solved this before?"
python bridge.py intelligence "implement rate limiting" --project vortex
```

Returns: similar work from other projects, applicable patterns, relevant lessons.

### 4. Check Project Health

```bash
# Portfolio overview
python bridge.py health summary --days 7

# Specific project
python bridge.py health project VortexV2
```

Shows: commit activity, health score, anomalies detected.

### 5. Queue Background Work

```bash
# Add task for batch processing (50% cheaper)
python orchestration/cli.py add \
  --title "Update documentation" \
  --description "Refresh API docs" \
  --priority C

# Check queue
python orchestration/cli.py list
```

---

## Common Commands

| Command | What It Does |
|---------|--------------|
| `python bridge.py portfolio stats` | Portfolio overview |
| `python bridge.py portfolio patterns` | Cross-project patterns |
| `python bridge.py portfolio lessons` | Lessons learned |
| `python bridge.py intelligence "query"` | Query all sources |
| `python bridge.py session-context` | Current work context |
| `python bridge.py health summary` | Health overview |
| `python cli.py next` | Next recommended action |
| `python cli.py briefing` | Daily briefing |
| `python cli.py status` | Current status |

---

## Dashboard

Launch the visual dashboard:

```bash
./launch_dashboard.sh
# Opens http://localhost:8502
```

Shows: project health, anomalies, recommendations in one view.

---

## Daily Scan

Run the automated daily scan:

```bash
./daily_scan.sh
```

Checks: system health, project activity, improvement opportunities.
Results saved to: `~/.cortex/latest_scan.json`

---

## Troubleshooting

### "Module not found" errors

```bash
# Ensure virtual environment is active
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements-lock.txt --force-reinstall
```

### "No projects found"

The portfolio index needs to be populated:

```bash
# Check if index exists
cat ~/.claude/portfolio/project_index.json

# If missing, the system will create it on first use
```

### API errors

```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Check .env file
cat .env | grep ANTHROPIC
```

### Slow queries

Intelligence queries can take 2-5 seconds on first run. This is normal - subsequent queries use caching.

For faster response, use specific project filters:
```bash
# Slower: searches all projects
python bridge.py intelligence "auth"

# Faster: scoped to one project
python bridge.py intelligence "auth" --project vortex
```

### Dashboard won't start

```bash
# Install Streamlit
pip install streamlit

# Run manually
streamlit run dashboard/app.py --server.port 8502
```

---

## Directory Structure

```
~/.cortex/
├── queue/tasks.db      # Task queue
├── latest_scan.json    # Last scan results
└── logs/               # Log files

~/.claude/
├── portfolio/
│   └── project_index.json   # Portfolio data
├── specs/              # Indexed specifications
└── session/
    └── context.json    # Session context
```

---

## Next Steps

1. **Run daily scan** for one week to build baseline
2. **Query patterns** before starting new work
3. **Check health** to identify stale projects
4. **Use queue** for non-urgent work

---

## Getting Help

```bash
# All commands
python bridge.py --help

# Specific command help
python bridge.py portfolio --help
python bridge.py intelligence --help
```

**Docs:**
- `docs/CORTEX_TECH_SPEC.md` - Technical details
- `docs/CORTEX_PRD.md` - Product requirements
- `docs/CORTEX_ARCHITECTURE.md` - System design
