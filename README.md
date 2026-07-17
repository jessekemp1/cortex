# 🧠 Cortex — Persistent Intelligence for LLM Agents

**Cortex solves session amnesia.** Every time you start a new Claude (or GPT-4, or Gemini) session, it forgets everything: decisions made last week, which approach failed last month, which patterns work in your codebase. Cortex is the infrastructure layer that compensates for this.

> "Cortex is like giving a consultant a well-organized notebook. Same intelligence, vastly different effectiveness."

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1855%20passing-green.svg)](tests/)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/jessekemp1/cortex/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

---

## The Problem

LLMs have no memory between sessions. This creates a systematic productivity tax:

- Repeating context on every session start ("remember, we use ruff for formatting...")
- Re-discovering the same bugs ("oh right, that's the circular import issue")
- Re-explaining architectural decisions that were settled weeks ago
- No accumulation of learned patterns across a project portfolio

This is not an intelligence problem. It is an infrastructure problem. Cortex is the fix.

---

## How It Works in 30 Seconds

```
Session A: You discover a gotcha with GRIB longitude handling.
           Cortex stores it as an anti-pattern with full context.

Session B (next week): You start working on a related module.
           Cortex surfaces the anti-pattern before you hit the bug.
           Claude reads it. You never repeat the mistake.
```

Cortex does not make the LLM smarter. It gives the LLM the right context at the right time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your LLM Agent                       │
│          (Claude / GPT-4 / Gemini / any)                │
└──────────────────────┬──────────────────────────────────┘
                       │ MCP or Python SDK
┌──────────────────────▼──────────────────────────────────┐
│                      Cortex                             │
│                                                         │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Working   │  │   Episodic   │  │   Semantic     │  │
│  │  Memory    │  │   Memory     │  │   Memory       │  │
│  │ (session)  │  │ (past events)│  │(BM25+embedding)│  │
│  └────────────┘  └──────────────┘  └────────────────┘  │
│                                                         │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Anti-      │  │  Signal      │  │  Contract      │  │
│  │ Patterns   │  │  Detection   │  │  Tasks         │  │
│  └────────────┘  └──────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │   ~/.cortex/    │
              │  (local store)  │
              └─────────────────┘
```

---

## Core Capabilities

| Capability | What it does |
|---|---|
| **Three-tier memory** | Short-term (session) → working (recent events, SQLite) → long-term with hybrid BM25 + embedding retrieval. Promotion between the first two tiers is automatic; the long-term index is built explicitly. |
| **Anti-pattern warnings** | 37 seeded anti-patterns (failure mode + prevention) surface as pre-task warnings when task context matches. Custom gotcha capture is early — record gotchas as decisions to make them retrievable today. |
| **Intelligent model routing** | Routes tasks to haiku/sonnet/opus by task-complexity classification (keywords, scope, length). Learns from outcome data to adjust selection. |
| **Goal-to-task pipeline** | Parses GOALS.md into prioritized work items. Discovers tasks from multiple sources. |
| **Interaction capture** | Hooks capture prompts, tool outcomes, and session patterns. Derives implicit feedback signals (corrections, approvals, failure rates). |

---

## Quick Start

```bash
# 1. Install from source
git clone https://github.com/jessekemp1/cortex && cd cortex
pip install -e ".[server,dev]"  # core + bridge + pytest

# 2. Run the 30-second proof — NO API key, NO network
cortex demo
```

> Prefer the bundled installer? `./install.sh` (or `./install.sh --full`)
> sets up the venv, state dirs, PATH, and (on macOS) LaunchAgents in one
> shot — same `[server,dev]` extras as above.

The demo synthesizes 5 prompts and 3 commits, runs the real `outcome_linker`
against them, and prints the FK trail with computed scores. If you see three
linked entries with `score 0.80`, the compounding-intelligence claim is live
in your install. This is the falsifiable headline artifact — try it before
you trust anything else here.

```bash
# 3. For the LLM-backed surface, set your key
export ANTHROPIC_API_KEY=sk-ant-...

cortex doctor                              # full environment health check
cortex status                              # see current session context
cortex briefing                            # daily context briefing
cortex intelligence "what should I work on next?"
```

Without `ANTHROPIC_API_KEY` set, the LLM-backed commands exit fast with an
actionable message — no silent hangs.

Set `CORTEX_ROOT_DIR=/path/to/projects` to point Cortex at your workspace.

---

## Demo

![Cortex terminal demo — briefing + intelligence query](docs/assets/demo.png)

### Conductor — Human-AI Collaboration Cockpit

![Conductor cockpit — startup wizard with project health, intent levels, and prompt composition](docs/assets/conductor.png)

The Conductor panel provides a structured startup workflow: select your project, set an intent level (advisory → autonomous), and compose context-rich prompts with one click. It tracks prompt history, monitors active Claude sessions, and surfaces portfolio health across all projects.

**The Compound Intelligence Effect: A realistic morning session**

You open Claude Code to work on your FastAPI project. Last week you debugged a tricky circular import in the auth module. Two months ago you discovered that Redis connection pooling needs specific timeout settings for your use case. Without Cortex, Claude starts fresh — no memory of either lesson.

With Cortex, your session begins differently:

```bash
$ cortex briefing
📊 CORTEX INTELLIGENCE BRIEFING — March 27, 2026

🎯 ACTIVE PROJECTS (3)
  • fastapi-backend: 2 commits since yesterday, tests passing
  • data-pipeline: scheduled job failed 6hrs ago (memory threshold)
  • frontend-react: no recent activity, goal deadline in 3 days

⚠️  NEEDS ATTENTION
  • data-pipeline: investigate memory usage spike
  • frontend-react: authentication integration overdue

🧠 RELEVANT PATTERNS
  • Redis connection pooling: timeout settings matter for long-running tasks
  • FastAPI circular imports: resolved via lazy imports in auth module

🎯 TODAY'S FOCUS
  • Complete Redis caching layer for FastAPI backend
  • Debug data-pipeline memory issue
```

You ask Claude: *"Should I use Redis for caching the user session data?"*

Behind the scenes, Cortex surfaces relevant context to Claude via MCP:

```bash
$ cortex intelligence "should I use Redis for caching user sessions?"

🔍 INTELLIGENCE QUERY RESULTS

📋 SIMILAR WORK
  • 2024-12-15: Implemented Redis caching for API rate limiting
  • 2024-11-28: Session storage comparison (Redis vs PostgreSQL)

🎯 APPLICABLE PATTERNS
  • Redis connection pooling requires max_connections=20, timeout=30s for this deployment
  • Use redis-py with connection_pool for FastAPI background tasks
  • Separate Redis DB indices: 0=cache, 1=sessions, 2=rate_limiting

⚠️  ANTI-PATTERNS
  • DON'T use default Redis timeout (causes 502 errors under load)
  • AVOID storing large objects (>1MB) — use PostgreSQL for user profiles

✅ RECOMMENDATIONS
  • Start with TTL=3600 for user sessions, monitor hit rates
  • Use RedisJSON extension if storing complex session data
  • Set up monitoring on connection pool exhaustion
```

Claude reads this context and gives you a targeted answer — not generic Redis advice, but specific guidance based on what worked (and what failed) in your previous projects.

Later, you're refactoring imports when Cortex proactively surfaces a warning:

```bash
⚠️  ANTI-PATTERN DETECTED: Circular Import Risk

Pattern: importing 'auth.models' at module level in 'models/user.py'
Previous incident: 2024-12-08 in fastapi-backend
Resolution: moved import inside get_current_user() function

Prevent this? [y/N] y
```

**The compound effect**: Over time, your briefings accumulate real context from your project history. Anti-patterns you've documented get surfaced before you repeat them. Session context builds on previous sessions. The more you use it, the more relevant the context becomes.

This is not magic — it is infrastructure. Cortex stores what you've learned so your LLM agent doesn't have to re-learn it every session.

---

## Python SDK

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge(root_dir="/path/to/projects")

# Retrieve relevant context for the current task
context = bridge.get_context("GRIB data processing", project="my-project")

# Query the unified intelligence system
result = bridge.query_intelligence(
    "implement API rate limiting",
    project="my-api",
    query_type="impl"
)
# Returns: similar_work, applicable_patterns, lessons, warnings, recommendations

# Store an anti-pattern so it is surfaced before it recurs
bridge.inject_recommendation(
    title="Never pass raw lon to ds.interp() on 0-360 grids",
    rationale="xarray extrapolates instead of wrapping — returns NaN silently",
    priority="high",
    type="anti_pattern"
)

# Get session context (git branch, recent commits, active goals)
session = bridge.get_session_context()
print(f"Branch: {session['git']['branch']}")
print(f"Active goals: {session['goals']}")
```

Performance: retrieval-only paths (recall, context, briefing file tier) respond in well under a second. LLM-backed intelligence queries make a synchronous Anthropic call and take seconds (~10s measured) — they are network-bound, not retrieval-bound. No latency figure here is benchmark-enforced yet.

---

## CLI Reference

```bash
# Session and status
cortex status                             # current session context
cortex briefing                           # daily intelligence briefing
cortex health                             # system health check

# Intelligence operations
cortex intelligence "<query>"             # query the intelligence system
cortex learn                              # show learning metrics and patterns

# Portfolio (multi-project)
cortex portfolio patterns                 # cross-project patterns
cortex portfolio patterns --switching-cost  # incl. switching-cost analysis

# Dependency analysis
cortex deps <project>                     # dependency graph
cortex deps <project> --cross-project     # cross-project dependencies
```

---

## MCP Integration

Cortex exposes a Model Context Protocol server so Claude Desktop and compatible clients can query it as a native tool.

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["/path/to/cortex/mcp_server.py"]
    }
  }
}
```

Once registered, Claude gets the **core 8** memory-loop tools —
`cortex_record_decision`, `cortex_intelligence`, `cortex_recommendations`,
`cortex_outcomes`, `cortex_plan_create`, `cortex_plan_progress`,
`cortex_projects`, `cortex_doctor` — all of which run in-process and keep
working when the bridge daemon is down (decision writes are crash-proof:
direct append with a spool fallback, flushed by `cortex doctor --fix`).
Set `CORTEX_EXPERIMENTAL=1` in the server's env to also register the 10
experimental/ops tools (bridge passthroughs like `cortex_service_health`,
`cortex_taskboard`, `cortex_graph_query`, …).

The :8765 bridge daemon (passthrough tools + session briefing) is supervised
by launchd — `bash scripts/install_launchagents.sh` installs and loads
`com.cortex.bridge` with keep-alive, so it survives crashes and reboots.
A foreground `python api/bridge_endpoint.py` is for debugging only.

---

## Comparison with Alternatives

| Tool | Strength | Where Cortex differs |
|---|---|---|
| **Mem0** (49K stars) | Universal memory layer, multi-tenant, great retrieval benchmarks | General-purpose. No developer-workflow primitives (anti-patterns, goal parsing, model routing). |
| **claude-mem** (34K stars) | Claude Code plugin, auto-capture, citation system | Record/replay memory. No task orchestration, no implicit feedback analysis. |
| **Supermemory** (17K stars) | #1 LongMemEval, temporal contradiction handling, auto-forget | Sophisticated retrieval. No work discovery, no cost-optimized model routing. |
| **Windsurf** | Auto-generated memories during conversations | Workspace-isolated. No cross-project transfer, no learning from outcomes. |
| **Cortex** | Developer-workflow-specific: goal parsing, model routing, anti-patterns, orchestration | Smaller community. Memory retrieval less benchmarked than Mem0/Supermemory. |

Cortex is optimized for one use case: **a developer or small team using LLM agents across a multi-project portfolio over months or years.** It combines memory + orchestration in a single system. For multi-tenant user memory at scale, use Mem0. For best-in-class retrieval benchmarks, use Supermemory. For persistent developer intelligence with task routing and cost optimization, Cortex is the right tool.

---

## Data Storage

The memory store is entirely local and there is no telemetry. Outbound traffic happens only for the services you configure: Anthropic API calls for LLM-backed commands, Voyage for optional external embeddings, Slack/Telegram for optional notifications. With no keys set, nothing leaves your machine.

```
~/.cortex/
├── config.yaml               # configuration (root_dir, feature flags)
├── decisions.jsonl           # recorded decisions — re-read fresh on every recall
├── outcomes.jsonl            # outcome tracking (feeds per-project retrieval boosts)
├── implicit_feedback.jsonl   # followed / overridden / ignored signals
├── interaction_queue.jsonl   # hook-captured prompts and tool events
├── working_memory.db         # 7-day working-memory tier (SQLite)
├── patterns/                 # long-term index: patterns.json + embeddings.pkl
├── memory/anti_patterns/     # captured gotchas (see USING_CORTEX.md for caveats)
├── metrics/                  # observability logs (append-only JSONL)
├── batch/                    # async job results
└── logs/                     # bridge and agent logs
```

---

## Installation

**From source:**

```bash
git clone https://github.com/jessekemp1/cortex
cd cortex
pip install -e .                  # core only
pip install -e ".[server]"        # + FastAPI bridge (uvicorn, apscheduler)
pip install -e ".[dev]"           # + pytest, ruff, mypy
pip install -e ".[server,dev]"    # recommended for contributors
pip install -e ".[all,server,dev]" # everything (analytics, orchestration, …)
```

Or run `./install.sh` (`--full` for everything) — the bundled installer
applies the recommended `[server,dev]` extras, creates `~/.cortex/`,
links `cortex` to `~/.local/bin/`, and (on macOS) installs LaunchAgents.

**Requirements:** Python 3.11+. `ANTHROPIC_API_KEY` required for embedding and intelligence features.

---

## Testing

```bash
pytest tests/ -v
```

1,855 tests passing on a fresh clone, covering memory retrieval, context optimization, work discovery, model routing, interaction capture, autonomous operations, and the MCP server contract. Assertion quality enforced by AST-based meta-testing (1.8% trivial rate).

---

## Paper

**Cortex: Persistent Intelligence Architecture for LLM-Powered Development Agents**
[PDF](docs/cortex_paper.pdf) *(DOI pending Zenodo upload)*

9-page technical paper covering three-tier memory architecture, hybrid BM25/embedding retrieval, implicit feedback weighting, autonomous operations, AST-based meta-testing, and measured production outcomes (21.2% dedup, 0.94 PQS, 50% batch savings).

---

## Contributing

Issues and pull requests welcome. Before contributing:

1. Run `pytest tests/ -v` — all tests must pass
2. Run `ruff check .` — no lint errors
3. New memory retrieval logic requires tests with specific recall assertions (not `assert result is not None`)

---

## License

Apache 2.0. See [LICENSE](LICENSE).
