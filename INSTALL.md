# Cortex — Install Guide

This guide gets you from zero to working in ~5 minutes.

## Prerequisites

- Python 3.11+
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- Git

## Install

```bash
# Clone and install
git clone https://github.com/jessekemp1/cortex && cd cortex
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Initialize data directories and config
cortex init --root-dir /path/to/your/projects

# Verify the CLI works
cortex status
```

You should see session context output (project name, recent commits, focus area). If you see errors about missing modules, run `pip install -e ".[all]"` for the full dependency set.

## Configuration

```bash
# Required: set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Optional: point Cortex at your project workspace
export CORTEX_ROOT_DIR=/path/to/your/projects
```

Cortex stores all data locally in `~/.cortex/`. Nothing leaves your machine unless you configure an external embedding provider.

## First Commands to Try

```bash
# 1. Status — shows your current session context (git branch, recent work, goals)
cortex status

# 2. Intelligence query — ask Cortex anything about your project
cortex intelligence "What patterns should I watch out for?"

# 3. Briefing — daily context summary
cortex briefing

# 4. Health check — verify all subsystems
cortex health
```

## Claude Code / MCP Integration

If you use Claude Code (or any MCP-compatible client), add Cortex as a tool server:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["/path/to/cortex/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "CORTEX_ROOT_DIR": "/path/to/your/projects"
      }
    }
  }
}
```

This lets Claude query `cortex_intelligence`, `cortex_recommendations`, and `cortex_anomalies` as native tools — no prompt engineering needed.

## Python SDK

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge(root_dir="/path/to/projects")

# Query intelligence
result = bridge.query_intelligence("implement caching", project="my-api")

# Get session context
session = bridge.get_session_context()
```

## What to Expect

- **First session**: Cortex starts with an empty memory. It learns from your git history, commits, and interaction patterns.
- **After a few sessions**: Anti-patterns and insights start accumulating. Briefings become more useful.
- **After a week+**: Cross-session patterns emerge. Cortex surfaces relevant context before you ask for it.

The more you use it, the more context it builds. This is the compound intelligence effect.

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: anthropic` | Run `pip install -e .` (dependencies not installed) |
| `cortex: command not found` | Activate your venv: `source .venv/bin/activate` |
| `ANTHROPIC_API_KEY not set` | Export the key: `export ANTHROPIC_API_KEY=sk-ant-...` |
| `Permission denied: ~/.cortex/` | `mkdir -p ~/.cortex && chmod 755 ~/.cortex` |
| Intelligence queries return empty | Normal on first run — Cortex needs interaction history to surface patterns |

## Feedback

1. **Install friction** — anything confusing or broken in setup?
2. **First impressions** — does the value prop click within 5 minutes?
3. **Missing features** — what would make this 10x more useful for your workflow?
4. **Bugs** — anything that crashes, hangs, or returns garbage?

File issues at https://github.com/jessekemp1/cortex/issues.
