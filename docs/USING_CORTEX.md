# Using Cortex — and getting the most out of it

An operator's guide, written against the code (v1.1.0). Every claim here traces to an implementation path; where a documented feature is not yet wired, this guide says so instead of pretending. Companion to [NARRATIVE.md](NARRATIVE.md) (what Cortex is) — this is *how to run it well*.

## 1. Install and verify

Two install paths with one important difference:

- **`./install.sh`** (recommended): checks Python ≥ 3.11, creates a project-local `.venv`, installs `-e ".[server,dev]"`, creates `~/.cortex/` state dirs, writes `.env` (prompts for `ANTHROPIC_API_KEY` and `CORTEX_ROOT_DIR`), symlinks `cortex` and `cx` into `~/.local/bin`, and offers the macOS LaunchAgents.
- **Manual `pip install -e .`** installs the core only — **no FastAPI, no MCP**. The bridge and the MCP server will not run until you use `pip install -e ".[server,dev]"`. If you followed the README's bare command and MCP tools return "Bridge unavailable," this is why.

Verify with `cortex doctor` — it checks exactly six things: Python ≥ 3.11, `anthropic` importable, `sklearn` importable, `ANTHROPIC_API_KEY` set, `~/.cortex/` exists, and the bridge reachable on `127.0.0.1:8765`.

Then run the trust check: **`cortex demo`** — 30 seconds, no API key, no network. It synthesizes prompts and commits into a temp directory and runs the real `outcome_linker`. Three linked entries at score 0.80 = the prompt→outcome loop works in your install.

**MCP registration** (Claude Code `.mcp.json` — pin the venv python and PYTHONPATH):

```json
{ "mcpServers": { "cortex": {
  "command": "/path/to/cortex/.venv/bin/python",
  "args": ["/path/to/cortex/mcp_server.py"],
  "env": { "PYTHONPATH": "/path/to/parent-of-cortex" } } } }
```

The MCP server is a thin proxy to the bridge on `127.0.0.1:8765` — **the bridge must be running** or every tool errors. Keep it supervised: install `com.cortex.bridge.plist` (RunAtLoad + KeepAlive) rather than backgrounding `python api/bridge_endpoint.py` by hand.

## 2. The daily loop

1. **Session start:** `cortex briefing --compact` (~12 lines: next action, risks, plan progress). Or install `hooks/session_briefing.sh` as a SessionStart hook so every Claude Code session opens with it automatically.
2. **During work:** query recall with `cortex_intelligence` (MCP) or `cortex intelligence "<question>" -p <project>` — **always pass the project** (see §4).
3. **After any decision worth remembering:** `cortex_record_decision` with decision, context, alternatives, rationale. This is the highest-value habit in the system; §4 explains how to write entries that actually come back.
4. **Session end:** the interaction-capture hooks (if installed) queue the session for ingestion; `hooks/session_debrief.sh` nags you to record what you decided.

Of the 54 CLI commands, the daily drivers are `briefing`, `status`, `intelligence`, `recall`, `next`, `doctor`. Occasional: `init`, `onboard`, `reflect` (weekly), `portfolio`, `orchestrate`, `goal/task/blocker`, `batch`. The rest (`v2`, `iap`, `graph`, `runtime`, `bandwidth`, the flywheel daemons) are power-user/experimental surface — expect rough edges.

## 3. Configuration that matters

| Variable | Default | Why you'd set it |
|---|---|---|
| `CORTEX_ROOT_DIR` | `~/Dev` | Your projects workspace root — project discovery and `GOALS.md` location. Set it or discovery scans the wrong tree. |
| `ANTHROPIC_API_KEY` | unset | LLM-backed commands only. Without it, LLM commands exit fast with an actionable message; `recall`, `briefing` (file tier), `demo`, `doctor`, `status` all still work. |
| `CORTEX_DOMAIN` | `aidev` | Namespaces your memory (e.g. keep work and personal portfolios separate). Set it in the MCP `env` block. |
| `CORTEX_EMBED_BACKEND` | `auto` | `voyage` (external API, best quality) > `ollama` (local server) > `local` (sklearn hashing, zero-dependency default). Auto picks the best available. |
| `CORTEX_DEFAULT_PROJECT` | unset | Fallback project tag when git detection fails. |

Privacy model, stated precisely: **the memory store is entirely local** (`~/.cortex/` files + SQLite; bridge binds 127.0.0.1; no telemetry SDK exists). **LLM-backed queries call Anthropic**, Voyage embeddings call Voyage, and notifications call Slack/Telegram — each only if you configure the corresponding key. With no keys set, nothing leaves the machine and the retrieval stack still works on local hashing embeddings.

## 4. Getting the most out of it — the compounding levers

**Write decisions for the retriever, not the diary.** Recall indexes decisions two ways: BM25 keyword search reads **only the `tags` field** — which the MCP tool does not set — while the embedding side embeds your `decision + context + rationale` prose. Practical consequences: (a) MCP-recorded decisions are carried entirely by semantic search, so put the words you'll search for *in the prose* — name the project, the technology, the error message; (b) a decision like "fixed it" is unretrievable; "Fixed Lakebase OAuth 422 by repointing /decisions/learning route" comes back. If you need guaranteed keyword hits, append to `~/.cortex/decisions.jsonl` directly with a `tags: […]` list and a `project:` field.

**Always pass `project=`.** The bridge's auto-detection runs `git rev-parse` from *its own* working directory — a daemon started by launchd resolves to the cortex directory no matter where you're working. Scoped queries (`cortex_intelligence(..., project="myproject")`) are the difference between relevant recall and noise. Tag decisions with a project for the same reason (untagged decisions currently index under `cortex`).

**Feed GOALS.md in the grammar the parser reads.** `cortex orchestrate` / `cortex_plan_create` parse `$CORTEX_ROOT_DIR/GOALS.md`: headers containing `Immediate Actions`, `Next Phase`, or `This Week` make their items HIGH priority; `High/Medium/Low Priority` headers map accordingly; items are `- [ ]` checkboxes, bullets, or numbered lines; `[done: <criteria>]` sets completion criteria; items under one header are treated as sequentially dependent. Status markers: `[ ]` pending, `[x]` done, `[~]` on hold, `[!]` blocked.

**Reindex on a schedule.** Decisions and conversation digests are re-read fresh on every query, but git-derived patterns load from a cache that only an explicit reindex refreshes (`python -m intelligence.memory.pattern_indexer index-all <root>` or `PatternMemory.reindex()`). If recall feels stale about recent code, this is why. The prompt→outcome linker is also manual today: run `python intelligence/outcome_linker.py` periodically (there is no bundled schedule for it yet).

**Record gotchas with keywords.** 37 built-in seed anti-patterns surface automatically as pre-task warnings when your task text matches their keywords (70% of injected-context budget is reserved for warnings). Custom gotchas captured via `cortex onboard` are stored but **not yet queried by the live retrieval path** — the durable workaround is recording them as decisions with "anti-pattern" in the prose, which the decision recall path does index.

**Trust the degradation paths.** Everything that matters for recall works without an API key. If the bridge is down, `briefing` degrades to file-based intelligence from GOALS.md + git. `cortex doctor` first, always, when something looks wrong.

## 5. What doesn't work yet (honest edges)

- **Custom anti-pattern capture is write-only**: stored gotchas aren't queried by live retrieval; only seed anti-patterns surface. (Recording gotchas as decisions is the workaround above.)
- **Promotion into permanent memory is not automatic**: the tier-promotion rules for long-term memory currently log instead of persisting; the permanent tier is populated by explicit indexing.
- **Intelligence-query result fields have distinct sources**: your recorded decisions feed `related_patterns` and session context — the `similar_work`/`lessons` fields come from portfolio/spec-KB indexes, which are empty until those are built for your projects. An empty `lessons` array does not mean your decisions are lost.
- **Latency is honest-seconds, not milliseconds**, for LLM-backed queries: tier-2/3 intelligence queries make a synchronous Anthropic call (~10 s measured). Retrieval-only paths are fast; nothing sub-second is benchmarked.
- **No scheduled outcome-linker ships yet** — run it manually or add your own LaunchAgent.
