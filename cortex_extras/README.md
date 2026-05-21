# cortex_extras

Holding pen for subsystems on the path to extraction into sibling repos.

Each subdirectory here is **not on the cortex core path** (none of the 18 MCP
tools strictly require any of them). They are kept inside the cortex repo
temporarily so that:

1. Existing functionality is preserved while the migration is staged.
2. Imports from the core (`bridge.py`, `bridge_intelligence.py`,
   `api/bridge_endpoint.py`, `cli/commands/compact.py`) continue to work via
   `cortex_extras.<subsystem>` paths until the sibling repos exist.

## Roadmap

| Subdir | LOC | Target sibling repo | Status |
|---|---|---|---|
| `synthetic/` | ~16,000 | `cortex-synthetic` | Used by bridge via optional import; 2 core sites updated |
| `cortexdbx/` | ~1,900 | `cortex-databricks` | Self-contained, zero core imports |
| `mvp/` | ~1,100 | `cortex-dashboard` | Self-contained Streamlit dashboard |
| `plugins/` | ~2,900 | `cortex-plugins` | Loader+registry exist but CLI never wires them |
| `tui/` | ~700 | `cortex-tui` | Used by `cli/commands/compact.py` optional code path; 1 site updated |
| `lean/` | ~800 | (delete) | Per-ROADMAP research artifact, zero importers |

Note: `gateway/` (telegram bot + web chat) was moved to `archive/gateway/`
when the UI surfaces were archived — the bridge now serves only local
agents (Hermes).

## Migrating an item to its sibling repo

1. Create the sibling repo (e.g. `cortex-synthetic`).
2. Copy the subdirectory contents preserving git history (`git filter-repo` or
   similar).
3. In this repo, replace the `from cortex_extras.<sub> import ...` sites with
   `try: from cortex_<sub> import ...; except ImportError: ... = None` so the
   extra becomes a pip-extra.
4. Add the optional dependency to `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   synthetic = ["cortex-synthetic>=0.1"]
   ```
5. Delete the subdirectory from `cortex_extras/`.
6. Verify: `pytest tests/contract/ && python scripts/smoke_mcp.py`.

## Core code referencing this directory

After Phase 3 (this move):

- `bridge.py:146-147` — `from cortex_extras.synthetic.generator/.schemas import ...`
- `bridge_intelligence.py:45-46` — same
- `cli/commands/compact.py:21` — `from cortex_extras.tui.data import ...`

All are wrapped in try/except so a missing extra degrades gracefully.
