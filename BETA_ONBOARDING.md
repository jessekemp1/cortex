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

## Install the Background Agents (Supervised Bridge)

The memory loop's core MCP tools (`cortex_record_decision`, `cortex_intelligence`,
`cortex_recommendations`, …) run **in-process** — they work even when the bridge
daemon is down, and a decision can never be lost to a dead bridge. The bridge on
:8765 powers the extra passthrough tools and the session briefing; install it
supervised (launchd keeps it alive across crashes and reboots):

```bash
bash scripts/install_launchagents.sh   # installs + loads com.cortex.bridge et al.

# Verify
cortex doctor          # checks bridge reachability, launchd agent, decision spool
curl -s http://127.0.0.1:8765/health | python3 -m json.tool
```

(Debugging only: a foreground bridge is `python api/bridge_endpoint.py`.)

## First Session (Verify It Works)

```bash
# 1. Status — shows your context
cortex status

# 2. Query intelligence (requires bridge running)
cortex intelligence "What are the key gotchas in this codebase?"

# 3. Daily briefing
cortex briefing
```

In Claude Code, you'll now have the **core 8** MCP tools — the memory loop:
`cortex_record_decision`, `cortex_intelligence`, `cortex_recommendations`,
`cortex_outcomes`, `cortex_plan_create`, `cortex_plan_progress`,
`cortex_projects`, `cortex_doctor`. Set `CORTEX_EXPERIMENTAL=1` in the MCP
server's env to also register the 10 experimental/ops tools.

## What to Expect

**After onboarding**: Your projects are detected, recent git history is seeded, and 37 anti-pattern seeds are loaded. Intelligence queries will already have context.

**After a few sessions**: Cross-session patterns emerge. Briefings surface relevant context before you ask.

**Key**: The more you use it, the more useful it gets. Onboarding gives you a head start.

## Issues & Feedback

- Install friction → https://github.com/jessekemp1/cortex/issues
- Feature requests → same
- Crash/hang → note exact command, include output
