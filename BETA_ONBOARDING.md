# Cortex Beta — Mac + Claude Code Setup

## What This Is

Cortex is persistent session memory for Claude. Every decision, pattern, and gotcha gets stored locally and surfaced in future sessions — no more context re-explaining, no more re-discovering the same bugs.

## Prerequisites

- Python 3.11+
- Claude Code (already running on your Mac)
- Anthropic API key in your shell: `export ANTHROPIC_API_KEY=sk-ant-...`

## Install (5 steps)

```bash
# 1. Clone
git clone https://github.com/jessekemp1/cortex ~/Dev/cortex
cd ~/Dev/cortex

# 2. Create venv
python3 -m venv .venv && source .venv/bin/activate

# 3. Install
pip install -e .

# 4. Initialize (point to your projects)
cortex init --root-dir ~/Dev

# 5. Verify
cortex status
```

You should see git branch, recent commits, and GOALS.md context. If you see module errors, run `pip install -e ".[all]"`.

## Wire Into Claude Code (Critical Step)

Cortex talks to Claude Code through MCP. Update `.mcp.json` at your Dev root:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "/Users/YOUR_USER/Dev/cortex/.venv/bin/python",
      "args": ["/Users/YOUR_USER/Dev/cortex/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/YOUR_USER/Dev"
      }
    }
  }
}
```

Replace `YOUR_USER` with your actual username. Claude Code will pick this up on next restart.

## First Session (Verify It Works)

```bash
# 1. Status — shows your context
cortex status

# 2. Query intelligence — try asking about your project
cortex intelligence "What are the key gotchas in this codebase?"

# 3. Daily briefing
cortex briefing
```

In Claude Code, you'll now have three new tools: `cortex_intelligence`, `cortex_recommendations`, `cortex_anomalies`.

## What to Expect

**First 2–3 sessions**: Intelligence is sparse. Cortex is learning your git history and patterns.

**After a week**: Cross-session context emerges. Briefings surface relevant errors before you hit them.

**Key**: The more you use it, the more useful it gets. Don't expect magic on day one.

## Issues & Feedback

- Install friction → https://github.com/jessekemp1/cortex/issues
- Feature requests → same
- Crash/hang → note exact command, include output
