# Cortex P0 De-Authoring Plan — make it work for a second user

**Goal:** a user who is *not* the author can install cortex, point it at their own
workspace, and get correctly-scoped answers (incl. under Omnigent via MCP).
**Scope:** the 6 P0 blockers only (the "looks healthy, answers wrong" bugs).
P1 install/LaunchAgent items are listed at the end, out of scope for this pass.
**Estimated effort:** ~0.5–1 day. Most P0s collapse into one root fix
(stop hardcoding `~/Dev` + the author's project list; discover from `CORTEX_ROOT_DIR`).

---

## Root cause (one sentence)

The MCP shim is portable, but the **bridge** hardcodes the author's workspace
(`~/Dev`), a fixed project list (`vortex/alpha_arena/cortex/pupil`), and a
literal default project `"cortex"`. A second user starts the bridge fine and
then gets the author's scaffolding or empty results — with no error.

---

## Foundation fix (do this first — items 1–4 and 6 depend on it)

Add one shared discovery helper and reuse it everywhere a project list or
workspace path is currently hardcoded. Suggested home: `config.py` (or a new
`project_registry.py`).

```python
# config.py (or project_registry.py)
import os
from pathlib import Path

def workspace_root() -> Path:
    """Projects workspace root. NOT the state dir (~/.cortex)."""
    return Path(os.environ.get("CORTEX_ROOT_DIR", Path.home() / "Dev")).expanduser()

def discover_projects(root: Path | None = None, depth: int = 2) -> list[dict]:
    """A project = a git repo found under the workspace root (depth-limited)."""
    root = (root or workspace_root())
    found = {}
    if not root.exists():
        return []
    # depth 1 (root/<proj>) and depth 2 (root/<group>/<proj>)
    for d in root.iterdir():
        if (d / ".git").exists():
            found[d.name] = {"name": d.name, "path": str(d), "rel": d.name}
        elif d.is_dir() and depth >= 2:
            for sub in d.iterdir():
                if (sub / ".git").exists():
                    found[sub.name] = {"name": sub.name, "path": str(sub), "rel": f"{d.name}/{sub.name}"}
    return list(found.values())
```

Acceptance for the foundation: with `CORTEX_ROOT_DIR=/tmp/ws` containing two
`git init`'d dirs, `discover_projects()` returns exactly those two.

---

## P0 punch-list (file-by-file)

### P0-1 — `cortex_intelligence` defaults every query to project `"cortex"`
**Breaks:** a second user's NL queries are scoped to a non-existent project → empty/irrelevant.
**Evidence:**
- `mcp_server.py:~108` — `cortex_intelligence(query, query_type)` POSTs `{"request","domain","query_type"}` with **no `project`**.
- `api/routes/intelligence.py:43` — `project: str = Field(default="cortex")`.
- `bridge.py:407` — `_detect_current_project()` returns literal `"cortex"` fallback.

**Fix:**
1. `mcp_server.py` — add an optional `project` arg and pass it through:
   ```python
   @mcp.tool()
   def cortex_intelligence(query: str, query_type: str = "research", project: str | None = None) -> str:
       payload = {"request": query, "domain": DOMAIN, "query_type": query_type}
       if project:
           payload["project"] = project
       result = _bridge_post("/intelligence/query", payload)
       ...
   ```
2. `api/routes/intelligence.py:43` — change default to `None`:
   `project: str | None = Field(default=None, description="Project; auto-detected if omitted")`
   and in the handler, when `project is None`, resolve via the bridge's detector (item P0-1.3).
3. `bridge.py:407` — replace the hardcoded fallback:
   ```python
   return os.environ.get("CORTEX_DEFAULT_PROJECT") or self.root_dir.name or "unknown"
   ```
**Accept:** with `CORTEX_ROOT_DIR=/tmp/ws/proj-a`, `cortex_intelligence("…")` scopes to `proj-a`, not `cortex`.

---

### P0-2 — `/projects` hardcodes `~/Dev` + the author's 5-project list
**Evidence:** `api/bridge_endpoint.py:597` `workspace = Path.home()/"Dev"`; `:600-606` fixed `project_defs` (Vortex/backend, Vortex/frontend, cortex, alpha_arena, pupil).
**Fix:** replace the hardcoded block with `discover_projects()`:
```python
@app.get("/projects")
async def list_projects():
    projects = []
    for p in discover_projects():
        path = Path(p["path"])
        # keep the existing last-commit / status enrichment, but use path
        ...
    return projects
```
**Accept:** `cortex_projects` returns the user's git repos under `CORTEX_ROOT_DIR`; the author's projects never appear on a fresh machine.

---

### P0-3 — `/status` and `/anomalies` hardcode `active_projects`
**Evidence:** `api/bridge_endpoint.py:349-351` and `:403-405` both set
`"active_projects": ["cortex","vortex","alpha_arena"]` and `:357` `"available_projects": ["cortex","vortex","alpha_arena","kempion"]`.
**Fix:** build from discovery once and reuse:
```python
names = [p["name"] for p in discover_projects()]
context = {"active_projects": names, "total_projects": len(names), ...}
# /status: "available_projects": names
```
**Accept:** anomaly context + `/status` reflect the user's real projects; no `vortex/kempion` leakage.

---

### P0-4 — Intelligence keyword-routing + git-log are the author's portfolio
**Evidence:** `api/routes/intelligence.py:64-79` `_PROJECT_KEYWORDS`/`_PROJECT_DIRS` (vortex/alpha_arena/cortex/pupil); `:86-90` `_auto_detect_project` defaults `"cortex"`; `:184-210` `git log/diff` against `_PROJECT_DIRS.get(project)` under `_workspace_root()`.
**Fix:**
1. Derive `_PROJECT_DIRS` from discovery at call time (map `name -> rel path`); drop the static author map (keep keyword map *optional*, defaulting keywords to the project name token).
2. `_auto_detect_project` default → the current detected project (`workspace_root().name` or bridge detector), not `"cortex"`.
3. Confirm `_workspace_root()` (intelligence.py:94+) resolves from `CORTEX_ROOT_DIR` (align it to `workspace_root()` from the foundation); the `git log` `cwd`/`-- <dir>` must use the **discovered** project path.
**Accept:** a query mentioning the user's project routes to it; git context comes from their repo, not `~/Dev/Vortex`.

---

### P0-5 — `.env.example` misdocuments `CORTEX_ROOT_DIR`
**Evidence:** `.env.example:7-10` calls `CORTEX_ROOT_DIR` the "Root directory for Cortex **state** (databases, logs, prompts)" with default `~/.cortex`. But the code uses it as the **projects workspace root** (`config.py:87`, `bridge.py:217`, `mcp_server.py:53` `GOALS_FILE = CORTEX_ROOT_DIR/GOALS.md`, default `~/Dev`). State actually lives at the fixed `~/.cortex` (METRICS_DIR/PROMPTS_DIR). `install.sh` already (correctly) prompts for it as "Projects root directory" — so `.env.example` is the wrong artifact.
**Fix:** correct `.env.example`:
```
# [REQUIRED] Root directory that CONTAINS your projects (git repos).
# Used for project detection and git scanning. Example: ~/Dev or ~/code
CORTEX_ROOT_DIR=~/Dev
# (Cortex state — databases, logs, prompts — lives at ~/.cortex and is not configurable here.)
```
**Accept:** copying `.env.example` verbatim yields correct project detection on first run.

---

### P0-6 — `/docs/tree` and `/docs/content` hardcode `~/Dev`
**Evidence:** `api/bridge_endpoint.py:1029,1100` build paths under `~/Dev` (+ a `DOCS_INDEX.md` there).
**Fix:** resolve from `workspace_root()`; if the docs-index feature is author-specific, gate it behind existence checks so it no-ops cleanly for other users instead of erroring/leaking.
**Accept:** `/docs/*` either reflect the user's workspace or return empty gracefully.

---

## Verification — "second user" smoke test (run after the fixes)

```bash
# 1. fake a second user's workspace
mkdir -p /tmp/ws/proj-a /tmp/ws/proj-b && (cd /tmp/ws/proj-a && git init -q) && (cd /tmp/ws/proj-b && git init -q)
export CORTEX_ROOT_DIR=/tmp/ws

# 2. start the bridge fresh, then:
.venv/bin/python -c "import urllib.request,json; print(urllib.request.urlopen('http://127.0.0.1:8765/projects').read())"
#   -> expect proj-a, proj-b ; NOT cortex/vortex/alpha_arena

# 3. via MCP (cortex_doctor then cortex_intelligence) — confirm bridge reachable + scope correct
```
Pass criteria: no occurrence of `cortex`, `vortex`, `alpha_arena`, `pupil`, or `~/Dev`
in `/projects`, `/status`, `/anomalies`, or intelligence context when
`CORTEX_ROOT_DIR=/tmp/ws`.

Add a regression test: `tests/test_deauthoring.py` that sets `CORTEX_ROOT_DIR`
to a tmp workspace and asserts discovery returns only the tmp projects.

---

## Out of scope here (P1 — next pass, needed for a *clean* install)

- **P1-7** `install.sh` installs unsubstituted-placeholder LaunchAgents (`install.sh:248-256`); should call `scripts/install_launchagents.sh` (does substitution + Linux systemd).
- **P1-8** Bridge never auto-starts (`mcp_server.py:69` returns "Bridge unavailable"); add a supervised start (LaunchAgent/systemd) + a `cortex bridge start` one-liner.
- **P1-9** macOS-only main install path; `heartbeat.plist:10` hardcodes `/usr/local/bin/python`.

---

## Omnigent hookup (after P0 lands — trivial)

Register the MCP shim in the agent's MCP config (venv python + absolute path + env):
```json
{ "mcpServers": { "cortex": {
  "command": "/abs/path/cortex/.venv/bin/python",
  "args": ["/abs/path/cortex/mcp_server.py"],
  "env": { "ANTHROPIC_API_KEY": "sk-ant-…", "CORTEX_ROOT_DIR": "/abs/path/to/your/projects", "CORTEX_DOMAIN": "aidev" }
}}}
```
Prereqs: bridge running and reachable at host `127.0.0.1:8765` (if Omnigent
sandboxes the agent, ensure host-network / port-forward); verify with `cortex_doctor`.
