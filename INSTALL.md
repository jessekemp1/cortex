# Cortex — Install Guide

This guide gets you from zero to working in ~5 minutes.

## Prerequisites

- Python 3.11+
- Git

## Install

```bash
# Clone and install
git clone https://github.com/jessekemp1/cortex && cd cortex
python -m venv .venv && source .venv/bin/activate
pip install -e .              # Core (memory, routing, ensemble, learning)

# Optional: install extras for specific features
pip install -e ".[llm]"       # Anthropic SDK (batch API, intelligence queries)
pip install -e ".[embeddings]" # numpy (semantic memory search)
pip install -e ".[all]"       # Everything
```

## Quick Setup

```bash
# Option A: Interactive setup wizard (recommended for new users)
cortex setup

# Option B: Manual setup
cortex init --root-dir /path/to/your/projects
export ANTHROPIC_API_KEY=sk-ant-...
cortex status
```

The setup wizard auto-detects your projects, configures subscription tracking,
and verifies everything works. It takes about 2 minutes.

## Configuration

```bash
# Required for intelligence features
export ANTHROPIC_API_KEY=sk-ant-...

# Optional: additional providers for multi-model routing
export GROQ_API_KEY=gsk_...     # Fast classification (Groq)
export OPENAI_API_KEY=sk-...    # GPT models
export XAI_API_KEY=xai-...      # Grok (long context)

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

## Core Features (No API Key Required)

These work with just `pip install -e .` (no optional deps):

- **Field-level ensemble decisions** — decomposes routing/model/context decisions into independent fields with Bayesian-weighted predictor voting
- **Temporal horizon routing** — classifies tasks as immediate/session/strategic, picks different model/context strategies per horizon
- **Verifiable expertise** — logs every prediction, verifies against outcomes, builds provable track record with calibration scoring
- **Subscription optimization** — tracks token utilization, detects waste, suggests capacity-fill work
- **Utilization learning engine** — closed-loop learning: observe → learn → adapt → act

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
from bridge import CortexBridge

bridge = CortexBridge(root_dir="/path/to/projects")

# Query intelligence
result = bridge.query_intelligence("implement caching", project="my-api")

# Get session context
session = bridge.get_session_context()
```

## What to Expect

- **First session**: Cortex starts with empty memory. Core features (ensemble decisions, routing, expertise tracking) work immediately. Intelligence queries learn from your git history.
- **After a few sessions**: Anti-patterns and insights accumulate. Model recommendations improve from outcome data. Expertise credentials start building.
- **After a week+**: Cross-session patterns emerge. Temporal routing learns which models work best per horizon. Subscription utilization is optimized.

The more you use it, the more context it builds. This is the compound intelligence effect.

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: anthropic` | `pip install -e ".[llm]"` (optional dep for intelligence) |
| `cortex: command not found` | Activate your venv: `source .venv/bin/activate` |
| `ANTHROPIC_API_KEY not set` | Export the key: `export ANTHROPIC_API_KEY=sk-ant-...` |
| `Permission denied: ~/.cortex/` | `mkdir -p ~/.cortex && chmod 755 ~/.cortex` |
| Intelligence queries return empty | Normal on first run — needs interaction history |

## Fresh Install Testing

To verify a fresh install works correctly:

```bash
bash scripts/test_fresh_install.sh
```

This runs a comprehensive test suite covering imports, unit tests, setup wizard, and functional smoke tests.

## Feedback

1. **Install friction** — anything confusing or broken in setup?
2. **First impressions** — does the value prop click within 5 minutes?
3. **Missing features** — what would make this 10x more useful for your workflow?
4. **Bugs** — anything that crashes, hangs, or returns garbage?

File issues at https://github.com/jessekemp1/cortex/issues.
