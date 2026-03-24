# Cortex — Repository Structure

## Entry Points

| File | Purpose |
|------|---------|
| `cli.py` | CLI entry point (`cortex` command). ~5,200 lines — use `def cmd_` to navigate command handlers. |
| `cortex_setup.py` | Interactive setup wizard for new users (`cortex setup`). |
| `mcp_server.py` | MCP server for Claude Desktop and compatible clients. |
| `bridge.py` | Python SDK. `CortexBridge` is the public class. Start here for programmatic use. |

## Package Layout

```
cortex/
├── bridge.py               # SDK entry point — CortexBridge class
├── bridge_intelligence.py  # Intelligence mixin for CortexBridge (query, retrieval)
├── bridge_system.py        # System/ops mixin for CortexBridge (git, deps, portfolio)
├── cli.py                  # CLI (monolith)
├── cortex_setup.py         # Interactive setup wizard
├── mcp_server.py           # MCP server
├── config.py               # CortexConfig dataclass + load_config()
├── briefing.py             # Daily briefing generation
├── orchestrator.py         # Task orchestration
├── learning.py             # Feedback and learning loop
├── goal_parser.py          # GOALS.md / ACTION_PLAN.md parser
├── feedback.py             # Feedback logging
├── portfolio_memory.py     # Cross-project pattern memory
│
├── intelligence/           # Core algorithms (importable subpackage)
│   ├── ensemble_decider.py      # Field-level ensemble decisions (Vortex-inspired)
│   ├── temporal_router.py       # Temporal horizon routing (immediate/session/strategic)
│   ├── verifiable_expertise.py  # Verifiable prediction track record
│   ├── unified_intelligence.py  # Aggregates all intelligence sources
│   ├── signals.py               # Autonomous signal detection
│   ├── contracts.py             # Task contract generation
│   ├── executor.py              # Contract execution engine
│   ├── memory/                  # Three-tier memory (tiered_memory.py, hybrid_retriever.py)
│   ├── model_selection/         # Context-aware model recommendation
│   │   ├── classifier.py        # Task complexity classification
│   │   ├── rules.py             # Rule-based model selection
│   │   ├── recommender.py       # Context-aware recommender (learned + rules)
│   │   └── models.py            # Data classes
│   ├── monitoring/              # Trend analysis, anomaly detection, alerts
│   ├── process_monitor/         # System process monitoring
│   ├── safety/                  # Injection detection, behavioral firewall, guardrails
│   └── ...
│
├── batch/                  # Batch processing & subscription optimization
│   ├── routing_framework.py       # Request routing (batch vs interactive)
│   ├── subscription_optimizer.py  # Token utilization tracking & waste analysis
│   ├── utilization_learning.py    # Closed-loop learning for utilization policies
│   ├── batch_api_client.py        # Anthropic Batch API wrapper
│   ├── queue_manager.py           # Auto-submission queue
│   └── ...
│
├── conductor/              # Multi-provider orchestration
│   ├── config.py            # Provider definitions, routing tables
│   ├── caller.py            # Execution engine
│   ├── router.py            # Smart provider selection
│   └── cost_tracker.py      # Per-provider cost tracking
│
├── engines/                # Augmentation, synthesis, ingestion
├── integration/            # Git sync, feedback loops, history analysis
├── tests/                  # 765+ tests
├── examples/               # Runnable demos
├── scripts/                # Utilities and test scripts
│   └── test_fresh_install.sh  # Fresh container beta test
├── docs/                   # User guides, API reference, architecture
└── agents/                 # Data agents for portfolio analysis
```

## Bridge Architecture (Mixin Pattern)

`CortexBridge` uses Python mixins to keep the class navigable:

```python
# bridge.py — defines CortexBridge + core init/storage
class CortexBridge(IntelligenceMixin, SystemMixin):
    def __init__(self, root_dir=None): ...
    def get_context(self, task, project): ...          # Core retrieval
    def inject_recommendation(self, title, ...): ...   # Store to memory

# bridge_intelligence.py — intelligence queries
class IntelligenceMixin:
    def query_intelligence(self, request, project, ...): ...
    def get_recommendations(self): ...
    def get_anomalies(self, project): ...

# bridge_system.py — system/portfolio operations
class SystemMixin:
    def get_session_context(self): ...
    def get_portfolio_stats(self): ...
    def get_dependency_graph(self, project): ...
```

## Configuration

Cortex stores user data in `~/.cortex/` (never in the repo).

Key env vars:
- `CORTEX_ROOT_DIR` — path to your projects root (default: cwd)
- `ANTHROPIC_API_KEY` — required for intelligence features
- `CORTEX_BRIDGE_URL` — bridge API URL (default: http://localhost:8765)

Config file: `~/.cortex/config.yaml` (created by `cortex init` or `cortex setup`)

## Dependencies

Core (always installed): `rich`, `requests`, `PyYAML`, `pytz`

Optional groups:
- `[llm]` — Anthropic SDK (batch API, intelligence queries)
- `[embeddings]` — numpy (semantic memory search)
- `[monitoring]` — psutil, structlog, python-dotenv
- `[server]` — FastAPI, uvicorn, MCP
- `[analytics]` — pydantic, xgboost, shap
- `[orchestration]` — litellm, httpx
- `[all]` — everything

## Contributing

1. Run `pytest tests/ -v` — all tests must pass before submitting a PR.
2. Run `ruff check .` — no lint errors.
3. New memory or retrieval logic requires tests with **specific value assertions** (not `assert result is not None`).
4. See `tests/KNOWN_ISSUES.md` for the current state of test quality.
