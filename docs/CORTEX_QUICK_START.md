# Cortex Quick Start

Get productive with Cortex in 5 minutes.

---

## Prerequisites

- Python 3.11+
- Git
- An Anthropic API key (required for intelligence and embedding features)

---

## Installation

```bash
git clone https://github.com/your-org/cortex
cd cortex

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Cortex
pip install -e .               # core only
# pip install -e ".[server]"   # + FastAPI server (uvicorn, apscheduler)
# pip install -e ".[all]"      # + analytics (xgboost, shap, openai)

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
```

Optionally set `CORTEX_ROOT_DIR` to point Cortex at your project workspace:

```bash
export CORTEX_ROOT_DIR=/path/to/your/projects
```

---

## First Command

Initialize Cortex and verify it works:

```bash
cortex init       # creates ~/.cortex/config.yaml
cortex status     # check system health
```

If `cortex status` returns without errors, you are ready to go.

---

## Core Workflows

### 1. Start of Day -- What Should I Work On?

```bash
cortex briefing
```

Returns a daily intelligence briefing: active goals, recent activity, and recommended next actions across your portfolio.

### 2. Query the Intelligence System

```bash
cortex intelligence "implement rate limiting"
```

Searches across memory, anti-patterns, and project context. Returns similar work from other projects, applicable patterns, and relevant lessons.

### 3. Store a Memory

```bash
cortex remember "Always use ruff for formatting in this project"
```

Stores the fact so Cortex can surface it in future sessions before you hit the same issue again.

### 4. Check System Health

```bash
cortex health
```

Shows project health scores, anomalies, and portfolio-wide metrics.

---

## Common Commands

| Command | What It Does |
|---------|-------------|
| `cortex init` | Initialize Cortex (creates config) |
| `cortex status` | Current session and system status |
| `cortex briefing` | Daily intelligence briefing |
| `cortex health` | System and project health check |
| `cortex intelligence "<query>"` | Query the intelligence system |
| `cortex remember "<fact>"` | Store a memory for future sessions |

---

## Troubleshooting

### "Module not found" errors

```bash
# Ensure your virtual environment is active
source .venv/bin/activate

# Reinstall
pip install -e .
```

### "No projects found"

Set `CORTEX_ROOT_DIR` to the directory containing your projects:

```bash
export CORTEX_ROOT_DIR=/path/to/your/projects
```

### API errors

```bash
# Verify your API key is set
echo $ANTHROPIC_API_KEY
```

If empty, export it again. Intelligence and embedding features require a valid Anthropic API key.

### Slow queries

Intelligence queries may take 2-5 seconds on first run. Subsequent queries use caching and are faster.

---

## Next Steps

1. Run `cortex briefing` each morning for a week to build baseline context
2. Use `cortex intelligence` before starting new work to check for existing patterns
3. Use `cortex remember` to capture gotchas and decisions as you discover them
4. Explore the [Python SDK](../README.md#python-sdk) and [MCP integration](../README.md#mcp-integration) for deeper integration

---

## Getting Help

```bash
cortex --help
```

**Documentation:**
- `docs/CORTEX_TECH_SPEC.md` -- Technical specification
- `docs/CORTEX_ARCHITECTURE.md` -- System architecture
- `README.md` -- Full reference including SDK and MCP setup
