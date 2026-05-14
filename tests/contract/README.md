# Contract Tests

Phase 0 deliverable from the slim-down plan
(`/root/.claude/plans/can-we-also-run-shimmying-globe.md`). These tests are the
safety net for every later phase — they exercise the bridge HTTP surface with
the **exact payloads** the MCP server and other in-repo consumers send.

## What's here

| File | Purpose |
|---|---|
| `test_mcp_contract.py` | One test per MCP tool. Documents the exact payload `mcp_server.py` sends and asserts the bridge accepts it. Four broken tools are `@pytest.mark.xfail(strict=True)` — they fail loudly today and the strict flag will catch the moment Phase 1 fixes them. |
| `test_bridge_endpoints.py` | Endpoints used by non-MCP consumers (gateway, supervisor, heartbeat, alert_monitor, compounding_risk). These are the endpoints that will survive when the bridge collapses to a thin shim in Phase 5. |
| `test_schema_invariant.py` | Asserts `signal_bus.db` DDL matches `tests/fixtures/cortex_state.sql`. The slim-down plan forbids schema drift; this test enforces it. |

## How to run

```bash
pip install pytest fastapi httpx pydantic mcp
pytest tests/contract/ -v
```

Expected baseline (pre-Phase-1):
```
19 passed, 6 xfailed
```

The 6 xfails are the 4 broken tools + the bridge-graph_query edge case + the AST drift check.

## Smoke script

For end-to-end exercise (actually spawning the bridge + MCP stdio server):

```bash
python scripts/smoke_mcp.py
```

Expected baseline (pre-Phase-1): 10 tools green, 4 known-broken, 4 env-dependent, exit 0.

## When to update

- **Phase 1 fixes a broken tool**: remove its `@pytest.mark.xfail` marker AND remove it from `KNOWN_BROKEN` in `scripts/smoke_mcp.py`. The strict-xfail will fail the run before you have a chance to forget.
- **A new MCP tool is added**: add a contract test for it. Add it to `TOOL_ARGS` in `scripts/smoke_mcp.py`. Update `test_all_18_tools_documented` if the surface count changes.
- **A non-MCP consumer adds an endpoint dependency**: add a test in `test_bridge_endpoints.py` so the bridge slim-down in Phase 5 doesn't accidentally drop it.
- **`engines/universal_signal_bus.py:_init_db` changes**: update `tests/fixtures/cortex_state.sql` AND mention the schema change in the PR description.
