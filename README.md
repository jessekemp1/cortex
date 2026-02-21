# 🧠 Cortex — Persistent Intelligence for LLM Agents

**Cortex solves session amnesia.** Every time you start a new Claude (or GPT-4, or Gemini) session, it forgets everything: decisions made last week, which approach failed last month, which patterns work in your codebase. Cortex is the infrastructure layer that compensates for this.

> "Cortex is like giving a consultant a well-organized notebook. Same intelligence, vastly different effectiveness."

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-600%2B%20passing-green.svg)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](setup.py)

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
| **Three-tier memory** | Working (session) → episodic (past events) → semantic with hybrid BM25 + embedding retrieval |
| **Anti-pattern database** | Stores learned mistakes with prevention context. Surfaces them before the bug repeats. |
| **Proactive signal detection** | Background monitoring retrieves relevant patterns without being asked |
| **Contract-based task management** | Tasks persist with full context between sessions |
| **Implicit feedback loop** | Tracks signals (time-on-task, repeat queries) to weight what gets surfaced |

---

## Quick Start

```bash
pip install cortex-intelligence        # or: pip install -e . from source
export ANTHROPIC_API_KEY=sk-...
cortex init                            # creates ~/.cortex/config.yaml
cortex remember "Always use ruff for formatting in this project"
cortex intelligence "What should I work on next?"
cortex briefing                        # morning context briefing
```

Set `CORTEX_ROOT_DIR=/path/to/projects` to point Cortex at your workspace.

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

Performance: bridge initialization under 10ms, context retrieval under 100ms, intelligence queries under 1s.

---

## CLI Reference

```bash
# Session and status
cortex status                             # current session context
cortex briefing                           # daily intelligence briefing
cortex health                             # system health check

# Memory operations
cortex remember "<fact>"                  # store a memory
cortex intelligence "<query>"             # query the intelligence system

# Portfolio (multi-project)
python bridge.py portfolio stats          # cross-project statistics
python bridge.py portfolio patterns       # cross-project patterns
python bridge.py portfolio lessons        # lessons learned

# Dependency analysis
python bridge.py deps <project>           # dependency graph
python bridge.py deps-health <project>    # health score
python bridge.py deps-circular <project>  # circular dependency detection
python bridge.py deps-graph <project> mermaid  # visual export
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

Once registered, Claude can call `cortex_intelligence`, `cortex_recommendations`, and `cortex_anomalies` without prompt engineering on your end.

---

## Comparison with Alternatives

| Tool | Strength | Gap vs. Cortex |
|---|---|---|
| **LangGraph** | Intra-run checkpoints for workflow pipelines | No cross-session memory, no proactive signals |
| **Mem0** | Multi-tenant user profile memory at scale | Built for SaaS apps with many users, not single-owner portfolio intelligence |
| **MemGPT** | Research-grade recursive memory management | High latency, not production-oriented |
| **OpenAI memory** | Zero-config cloud memory | Cloud-only, black box, no audit trail, no local ownership |
| **Cortex** | Single-owner portfolio intelligence | Local, inspectable, sub-second retrieval, anti-pattern database |

Cortex is optimized for one use case: **a developer or small team using LLM agents across a multi-project portfolio over months or years.** For multi-tenant user memory, use Mem0. For intra-run pipeline state, use LangGraph. For persistent cross-session intelligence on your own work, Cortex is the right tool.

---

## Data Storage

All data is local by default. Nothing leaves your machine unless you configure an external embedding provider.

```
~/.cortex/
├── config.yaml          # configuration
├── memories/            # episodic and semantic store
├── anti_patterns/       # learned mistakes with prevention context
├── metrics/             # observability logs (append-only JSONL)
│   ├── bias_corrections.jsonl
│   ├── adaptive_weight_updates.jsonl
│   └── scheduler_jobs.jsonl
└── batch/               # async job results
```

---

## Installation

**From source:**

```bash
git clone https://github.com/your-org/cortex
cd cortex
pip install -e .            # core only
pip install -e ".[server]"  # + FastAPI server (uvicorn, apscheduler)
pip install -e ".[all]"     # + analytics (xgboost, shap, openai)
```

**Requirements:** Python 3.11+. `ANTHROPIC_API_KEY` required for embedding and intelligence features.

---

## Testing

```bash
pytest tests/ -v
```

600+ tests covering memory retrieval accuracy, anti-pattern surfacing, hybrid BM25/embedding scoring, implicit feedback weighting, and the MCP server contract.

---

## Paper

**Cortex: Persistent Intelligence Architecture for LLM-Powered Agents**
DOI: coming February 24, 2026.

Covers the three-tier memory architecture, implicit feedback weighting, and measured outcomes from production use across a multi-project portfolio.

---

## Contributing

Issues and pull requests welcome. Before contributing:

1. Run `pytest tests/ -v` — all tests must pass
2. Run `ruff check .` — no lint errors
3. New memory retrieval logic requires tests with specific recall assertions (not `assert result is not None`)

---

## License

Apache 2.0. See [LICENSE](LICENSE).
