# Cortex — Repository Structure

## Entry Points

| Path | Purpose |
|------|---------|
| `mcp_server.py` | **Primary interface.** MCP server for Claude Code / Claude Desktop. Since the Phase 5 bridge collapse, all 18 tools run in-process — no HTTP, no daemon. |
| `cli/` | CLI package (`cortex` command). `cli/__init__.py:main()` dispatches to handlers in `cli/commands/`. |
| `bridge.py` | `CortexBridge` — the backing intelligence class. Used directly (in-process) by the MCP server and as a Python SDK. |
| `api/bridge_endpoint.py` | Optional FastAPI HTTP shim. Only needed by local agents (e.g. Hermes) — not by MCP clients. |

## Package Layout

```
cortex/
├── mcp_server.py           # MCP server — 18 tools, in-process
├── mcp_handlers.py         # Stdlib-only handlers backing MCP tools (no HTTP)
├── health_probe.py         # Stdlib-only service-health probes
├── bridge.py               # CortexBridge class — core init/storage + composition
├── bridge_intelligence.py  # IntelligenceMixin (query, retrieval, recommendations)
├── bridge_system.py        # SystemMixin (git, deps, portfolio, graph, batch ops)
├── briefing.py             # Daily briefing generation (incl. resilient tiered path)
├── orchestrator.py         # Task orchestration
├── recommendation_engine.py# Task-level recommendations
├── recommendations.py      # PortfolioRecommender — portfolio-level reports
├── scheduler.py            # Background job scheduler
├── learning.py             # Feedback and learning loop
├── config.py               # CortexConfig dataclass + load_config()
│
├── cli/                    # CLI package
│   ├── __init__.py         #   main() entry point + dispatcher
│   └── commands/           #   command handlers (one module per area)
│
├── api/
│   └── bridge_endpoint.py  # Optional HTTP shim (FastAPI) for non-MCP consumers
│
├── intelligence/           # Core algorithms (importable subpackage)
│   ├── memory/             #   tiered_memory.py, hybrid_retriever.py
│   ├── monitoring/         #   trend analysis, anomaly detection, alerts
│   ├── unified_intelligence.py
│   └── ...
│
├── batch/                  # Async batch infrastructure (Phase 6 redesign planned)
├── engines/, supervisor/   # Orchestration + research agent
├── cortex_extras/          # Subsystems staged for extraction to sibling repos
│   │                       #   (synthetic, cortexdbx, mvp, plugins, tui, lean)
├── archive/                # Frozen code — not built/tested (site UI, gateway)
│
├── tests/
│   ├── contract/           # MCP-tool + bridge-endpoint contract tests
│   └── ...                 # ~93 test files
└── docs/
```

## Bridge Architecture (Mixin Pattern)

`CortexBridge` composes two mixins to keep the class navigable:

```python
# bridge.py — defines CortexBridge + core init/storage
class CortexBridge(IntelligenceMixin, SystemMixin):
    def __init__(self, root_dir=None): ...
    def get_context(self, task, project): ...          # core retrieval
    def query_graph(self, node_type, filters): ...     # context graph

# bridge_intelligence.py
class IntelligenceMixin:
    def query_intelligence(self, request, project, ...): ...
    def get_recommendations(self): ...

# bridge_system.py
class SystemMixin:
    def get_portfolio_health_summary(self): ...
    def get_batch_status(self, batch_id): ...
```

The MCP server reaches `CortexBridge` through a lazy singleton (`mcp_server._get_bridge`)
— construction loads ML/embedding modules and is deferred until the first
tool call that needs it.

## Configuration

Cortex stores user data in `~/.cortex/` (never in the repo).

Key env vars:
- `CORTEX_ROOT_DIR` — path to your projects root (default: cwd)
- `ANTHROPIC_API_KEY` — required for embedding and intelligence features
- `CORTEX_STATE_DIR` / `CORTEX_HOME` — override the `~/.cortex/` state location

Config file: `~/.cortex/config.yaml` (created by `cortex init`)

## Known Technical Debt

- Internal imports use bare module names (`from formatter import ...`) rather
  than `from cortex.formatter import ...`. This works with the current
  `package_dir` setup but is a real hazard: importing the same file via both
  `bridge` and `cortex.bridge` produces two distinct module objects. New code
  should pick one canonical path.
- `sys.path.insert` calls in several files are a legacy workaround for the above.
- `batch/` (~14.7K LOC) is over-built around an always-full cloud queue —
  ROADMAP Phase 6 tracks the local-first redesign.

## Contributing

1. Run `pytest tests/ -v` — all tests must pass before submitting a PR.
2. Run `pytest tests/contract/` — the MCP/bridge contract suite must stay green.
3. Run `ruff check .` — no lint errors.
4. New memory or retrieval logic requires tests with **specific value
   assertions** (not `assert result is not None`).
5. See `tests/KNOWN_ISSUES.md` for the test-quality policy.
