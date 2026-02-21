# Cortex — Repository Structure

## Entry Points

| File | Purpose |
|------|---------|
| `cli.py` | CLI entry point (`cortex` command). 4,300 lines — use `def cmd_` to navigate command handlers. Decomposition planned for v1.1. |
| `mcp_server.py` | MCP server for Claude Desktop and compatible clients. |
| `bridge.py` | Python SDK. `CortexBridge` is the public class. Start here for programmatic use. |

## Package Layout

```
cortex/
├── bridge.py               # SDK entry point — CortexBridge class
├── bridge_intelligence.py  # Intelligence mixin for CortexBridge (query, retrieval)
├── bridge_system.py        # System/ops mixin for CortexBridge (git, deps, portfolio)
├── cli.py                  # CLI (monolith, refactor in progress)
├── mcp_server.py           # MCP server
├── config.py               # CortexConfig dataclass + load_config()
├── briefing.py             # Daily briefing generation
├── orchestrator.py         # Task orchestration
├── scheduler.py            # Background job scheduler
├── learning.py             # Feedback and learning loop
│
├── intelligence/           # Core algorithms (importable subpackage)
│   ├── memory/             # Three-tier memory (tiered_memory.py, hybrid_retriever.py)
│   ├── monitoring/         # Trend analysis, anomaly detection, alert generation
│   ├── signals.py          # Signal detection
│   ├── unified_intelligence.py  # Aggregates all intelligence sources
│   └── ...
│
├── tests/                  # 600+ tests
├── examples/               # Runnable demos (demo_tiered_memory.py, etc.)
├── batch/                  # Async batch job infrastructure
├── scripts/                # Utilities
│   └── internal/           # Internal tooling (not for external use)
├── docs/
│   ├── API.md              # Full API reference
│   ├── user_guide/         # Getting started guides
│   └── archive/internal/   # Session logs and implementation notes (historical)
└── agents/                 # Data agents for portfolio analysis
```

## Bridge Architecture (Mixin Pattern)

`CortexBridge` uses Python mixins to keep the class navigable:

```python
# bridge.py — defines CortexBridge + core init/storage
class CortexBridge(BridgeIntelligenceMixin, BridgeSystemMixin):
    def __init__(self, root_dir=None): ...
    def get_context(self, task, project): ...          # Core retrieval
    def inject_recommendation(self, title, ...): ...   # Store to memory

# bridge_intelligence.py — intelligence queries
class BridgeIntelligenceMixin:
    def query_intelligence(self, request, project, ...): ...
    def get_recommendations(self): ...
    def get_anomalies(self, project): ...

# bridge_system.py — system/portfolio operations
class BridgeSystemMixin:
    def get_session_context(self): ...
    def get_portfolio_stats(self): ...
    def get_dependency_graph(self, project): ...
```

## Configuration

Cortex stores user data in `~/.cortex/` (never in the repo).

Key env vars:
- `CORTEX_ROOT_DIR` — path to your projects root (default: cwd)
- `ANTHROPIC_API_KEY` — required for embedding and intelligence features
- `CORTEX_ANTI_PATTERNS_SCRIPT` — path to custom anti-pattern mining script (optional)

Config file: `~/.cortex/config.yaml` (created by `cortex init`)

## Known Technical Debt

- `cli.py` is a monolith (4,311 lines). Decomposition into `commands/` is planned for v1.1.
- Internal imports use bare module names (`from formatter import ...`) rather than `from cortex.formatter import ...`. This works with the current `package_dir` setup but will be migrated to proper package imports in v1.1.
- `sys.path.insert` calls in several files are a legacy workaround for the above.

## Contributing

1. Run `pytest tests/ -v` — all tests must pass before submitting a PR.
2. Run `ruff check .` — no lint errors.
3. New memory or retrieval logic requires tests with **specific value assertions** (not `assert result is not None`).
4. See `tests/KNOWN_ISSUES.md` for the current state of test quality.
