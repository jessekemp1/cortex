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

# 5. Onboard — auto-detect projects and seed memory
cortex onboard --root ~/Dev

# 6. Verify
cortex doctor
```

You should see your projects listed with languages and test frameworks detected. If you see module errors, run `pip install -e ".[all]"`.

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

## No Bridge Needed

The MCP server runs fully in-process — all 18 tools work without starting any
background server. (The optional HTTP bridge at `:8765` exists only for local
agents like Hermes; MCP users can ignore it.)

## First Session (Verify It Works)

```bash
# 1. Status — shows your context
cortex status

# 2. Query intelligence
cortex intelligence "What are the key gotchas in this codebase?"

# 3. Daily briefing
cortex briefing
```

In Claude Code, you'll now have 18 MCP tools: `cortex_intelligence`, `cortex_recommendations`, `cortex_anomalies`, `cortex_doctor`, and more — all served in-process.

## What to Expect

**After onboarding**: Your projects are detected, recent git history is seeded, and 37 anti-pattern seeds are loaded. Intelligence queries will already have context.

**After a few sessions**: Cross-session patterns emerge. Briefings surface relevant context before you ask.

**Key**: The more you use it, the more useful it gets. Onboarding gives you a head start.

## Issues & Feedback

- Install friction → https://github.com/jessekemp1/cortex/issues
- Feature requests → same
- Crash/hang → note exact command, include output
