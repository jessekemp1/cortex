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
# 1. Onboard — auto-detect your projects and seed memory
cortex onboard --root ~/Dev

# 2. Status — shows your current session context (git branch, recent work, goals)
cortex status

# 3. Health check — verify all subsystems
cortex doctor
```

## Starting the Bridge Server

The bridge server (`api/bridge_endpoint.py`) powers intelligence queries and MCP integration. Basic commands (`status`, `onboard`, `doctor`) work without it.

```bash
# Start the bridge (runs on :8765)
python api/bridge_endpoint.py

# Or with uvicorn directly
uvicorn api.bridge_endpoint:app --host 127.0.0.1 --port 8765

# Verify it's running
curl http://127.0.0.1:8765/health
```

Once the bridge is running, you can use:

```bash
# Intelligence query — ask Cortex anything about your project
cortex intelligence "What patterns should I watch out for?"

# Briefing — daily context summary
cortex briefing
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

## Gateway — Telegram Bot + Web Chat (Coming Soon)

Cortex includes a Gateway module for Telegram (`@KempionBot`) and web chat (`:8765/chat`). **This feature is not yet active by default.** To enable it, you'll need:

- A Telegram bot token (`CORTEX_TELEGRAM_TOKEN`) from [@BotFather](https://t.me/BotFather)
- The bridge server running (`cortex serve`)

See `cortex/gateway/` for configuration details.

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
