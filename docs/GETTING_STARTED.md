# Getting Started with Cortex

This is the one canonical setup guide. An agent or a human can run it top to
bottom on a clean machine and end with a working memory loop — proven live, not
assumed.

Cortex is persistent memory for LLM agents. Every decision, pattern, and gotcha
is stored on your machine and surfaced in future sessions, so you stop
re-explaining context and stop re-hitting the same bugs.

> **Beta status.** This is `v1.2.0-beta.1`, git-clone-only (no published wheel).
> A few commands below are shipping in a parallel workstream and are marked
> **(beta, arriving with this release)**. Command names and flags are exact;
> where you cannot run one yet, the guide says so.

---

## 1. The promise

By day 7, `cortex stats` shows you these numbers **(beta, arriving with this
release)**:

- **Memory is being used** — count of decisions recorded and interactions
  captured this week.
- **Decisions recalled** — how many past decisions Cortex surfaced back to you
  in a query or briefing.
- **Follow-rate** — once you have at least 10 rated recommendations (n ≥ 10),
  the share you acted on vs. overrode. Below 10, `cortex stats` says
  "too few to rate" rather than inventing a percentage.

These are real receipts from your own usage — no seeded vanity numbers.

**Honest caveat:** recall precision is still rough in this beta. A freshly
recorded decision may not surface on a related query until the long-term index
has been built, and some queries return more or fewer hits than you'd expect.
The loop works; the ranking is still being tuned.

---

## 2. Prerequisites

- macOS or Linux
- Python 3.11 or newer
- git

**No API key is needed** for the golden path — the memory loop (record, recall,
`cortex demo`, `cortex doctor`, `cortex stats`) runs entirely locally with no
network call. An `ANTHROPIC_API_KEY` only unlocks the LLM-backed briefing
(`cortex briefing`) and the natural-language `cortex intelligence` query.

---

## 3. Mode A — agent-guided runbook (recommended)

This is the headline path. An agent executes these steps in order. Each step is
one command, the output to expect, and the single repair to try if it looks
wrong. Every command is copy-pasteable.

**The universal repair is `cortex doctor --fix`.** Whenever a step looks wrong,
run it, then re-run the step. If it still looks wrong, capture
`cortex doctor --json` **(beta, arriving with this release)** and report it.

### Step 1 — Clone and install

```bash
git clone https://github.com/jessekemp1/cortex && cd cortex
./install.sh --yes
```

`./install.sh --yes` runs non-interactively **(beta, arriving with this
release — the `--yes` flag)**: it creates the venv, installs the recommended
extras, sets up `~/.cortex/`, links `cortex` onto your PATH, and (on macOS)
installs the supervised background agents. It needs **no API key** for the
golden path.

**Expect:** an install-verification block ending in `Install complete.` with
`cortex package importable` and `~/.cortex/ state directory ready` checked off.

**If it looks wrong:** re-run `./install.sh --yes`; the installer is idempotent.
Then continue to Step 2 — `cortex doctor` will tell you exactly what is missing.

### Step 2 — Health check

```bash
cortex doctor
```

**Expect:** a `CORTEX DOCTOR` banner with `[PASS]` lines for `Python >= 3.11`,
`anthropic importable`, `sklearn importable`, `~/.cortex/ exists`,
`bridge :8765 reachable`, and `decision spool empty`. On the golden path (no
key) the `ANTHROPIC_API_KEY set` line reads `missing` — that is expected and does
not block the memory loop.

**If it looks wrong:** run the universal repair —

```bash
cortex doctor --fix
```

`--fix` flushes any decisions stranded in the spool back into
`decisions.jsonl`, then re-runs every check. Re-read the banner.

**Then report:** capture machine-readable state with

```bash
cortex doctor --json      # (beta, arriving with this release)
```

### Step 3 — Prove the local loop with the demo

```bash
cortex demo
```

**Expect:** a `CORTEX DEMO` banner, then an `FK trail` of three linked entries,
each showing `[score 0.80]`, and the closing line
`This output was generated with NO API key and NO network call.` Three linked
entries at `score 0.80` means the compounding-intelligence loop is live in your
install.

**If it looks wrong:** run `cortex doctor --fix`, then re-run `cortex demo`.
Report `cortex doctor --json`.

### Step 4 — See your session context

```bash
cortex status
```

**Expect:** a `CORTEX - STRATEGIC INTELLIGENCE` banner with strategic focus,
next action, and portfolio status sections. This works with no key.

**If it looks wrong:** `cortex doctor --fix`, then re-run. Report
`cortex doctor --json`.

### Step 5 — PAYOFF: record a real decision, then recall it live

This is the whole point. First record a decision. The crash-proof path is the
MCP tool `cortex_record_decision` (call it from your agent):

```
cortex_record_decision(
  decision="Use DuckDB for the local analytics cache",
  context="Evaluating the embedded store for the reporting path",
  alternatives="SQLite, Postgres",
  rationale="Columnar + zero-server fits a single-user workload",
  project="my-project"
)
```

**Expect:** a JSON envelope `{"recorded": true, "decision_id": "dec_...",
"timestamp": "..."}`. The decision is appended to `~/.cortex/decisions.jsonl`
immediately — it is never lost to a dead bridge daemon.

Then recall it — ask Cortex about the same topic:

```
cortex_intelligence(query="analytics cache decision", project="my-project")
```

**Expect:** a JSON envelope with `similar_work`, `applicable_patterns`,
`lessons`, `warnings`, and `recommendations` keys plus your `session_context`.
Your decision feeds this retrieval path. (Beta honesty: right after recording,
`similar_work` may still be empty until the long-term index is built — the write
is durable regardless, and it will surface as the index catches up.)

**If it looks wrong:** `cortex doctor --fix` (this flushes the decision spool),
then re-run the recall. Report `cortex doctor --json`.

That is the loop: **record → recall**. Everything else is scale and polish.

---

## 4. Mode B — one-liner

For a human who just wants it running:

```bash
git clone https://github.com/jessekemp1/cortex && cd cortex && ./install.sh --yes
```

Then **restart Claude Code** so it picks up the Cortex MCP server. Done —
skip to *Prove it* below.

---

## 5. Prove it

The exact steps to watch the loop work, end to end:

1. **Record** a decision via the MCP tool `cortex_record_decision` (see Mode A,
   Step 5). Expect `{"recorded": true, "decision_id": "dec_..."}`.
2. **Recall** it via `cortex_intelligence` with a query on the same topic.
   Expect the intelligence envelope; your decision feeds `similar_work`.
3. **Count it** with `cortex stats` **(beta, arriving with this release)** — the
   recorded decision shows up in this week's totals.

### What "good" looks like on day 1 (empty-state checklist)

On a fresh install, `cortex stats` **(beta, arriving with this release)** shows
an empty-state milestone checklist, not fake numbers. You're on track when:

- [ ] `cortex doctor` is all `[PASS]` (except `ANTHROPIC_API_KEY` on the
      golden path, which is expected `missing`).
- [ ] `cortex demo` prints three FK entries at `score 0.80`.
- [ ] You have recorded at least one real decision (`"recorded": true`).
- [ ] Cortex is registered in Claude Code (restart done; MCP tools available).

### What day 7 looks like

`cortex stats` reports real receipts: decisions recorded this week,
interactions captured, decisions recalled, and — once n ≥ 10 rated
recommendations — a real follow-rate. See *First-week arc* for the shape of the
climb.

---

## 6. First-week arc

Cortex gets more useful as data accrues. Expect this progression:

- **Day 1:** empty state. `cortex demo` proves the mechanism on synthetic data;
  your own history is still thin. `cortex stats` shows the milestone checklist,
  not rates.
- **Days 2–6:** decisions and interactions accumulate. Recall starts returning
  your own entries. Follow-rate is still shown as **"too few to rate"** while
  you have fewer than 10 rated recommendations (n < 10) — Cortex will not
  fabricate a percentage from a tiny sample.
- **Day 7+:** with n ≥ 10, `cortex stats` switches from "too few to rate" to
  **real rates**: follow-rate, recall counts, weekly capture totals. This is the
  compound effect — the numbers are yours, earned from actual use.

---

## 7. Troubleshooting

The universal first move for any symptom is `cortex doctor --fix`, then re-run
the command. If it persists, escalate with `cortex doctor --json` **(beta,
arriving with this release)** attached.

| Symptom | First: `cortex doctor --fix` | Escalation |
|---|---|---|
| **Bridge down** (`bridge :8765 reachable: not running`) | `cortex doctor --fix` re-checks reachability. Reinstall the supervisor: `bash scripts/install_launchagents.sh`, then `cortex doctor`. | The memory loop (record/recall) works with the bridge down — only briefings and passthrough tools need it. File an issue with `cortex doctor --json`. |
| **MCP not registered in Claude Code** (no `cortex_*` tools) | Confirm the server is healthy: `bash scripts/install_launchagents.sh` then `cortex doctor`. | **Restart Claude Code** — it registers MCP servers on startup. Verify the `cortex` block in your `.mcp.json` points at the venv Python and `mcp_server.py`. Re-run `./install.sh --yes`. |
| **Key saved but "missing"** (`.env` has it, doctor says `missing`) | `cortex doctor` reads the live environment, not `.env`. Export it in the current shell: `export ANTHROPIC_API_KEY=sk-ant-...`, then re-check. | For the MCP server, put the key in the `env` block of its `.mcp.json` entry and restart Claude Code. The `.env` file is loaded by the bridge/runtime, not by every CLI invocation. |
| **Spool backlog** (`decision spool empty: N pending`) | `cortex doctor --fix` flushes spooled decisions into `decisions.jsonl` and reports `N flushed`. | If entries remain, check `~/.cortex/` permissions (`chmod 755 ~/.cortex`) and disk space, then re-run `--fix`. File an issue with `cortex doctor --json`. |
| **LaunchAgent not loaded** (macOS: `com.cortex.bridge loaded: not loaded`) | Load it: `bash scripts/install_launchagents.sh`, then `cortex doctor`. | Confirm with `launchctl list \| grep com.cortex`. Stop a stuck agent with `launchctl bootout` (not `server stop`). File an issue with `cortex doctor --json`. |
| **Anything else looks wrong** | `cortex doctor --fix`, then re-run the command. | Capture `cortex doctor --json` and file an issue (see *Experimental note & feedback*). |

---

## 8. Reset / uninstall

**(both beta, arriving with this release)**

Wipe accumulated state but keep Cortex installed:

```bash
cortex reset          # clears ~/.cortex/ state (decisions, memory, metrics)
```

Remove Cortex entirely:

```bash
./uninstall.sh        # removes the venv, PATH links, and (macOS) LaunchAgents
```

Until these ship, remove state manually with `rm -rf ~/.cortex` and unload the
agents with `launchctl bootout` (macOS).

---

## 9. Experimental note & feedback

The beta ships the **smallest credible surface**. Everything outside it is
hidden and refuses to run:

- **MCP tools — the golden five** (always available):
  `cortex_intelligence`, `cortex_record_decision`, `cortex_outcomes`,
  `cortex_service_health`, `cortex_doctor`.
- **CLI — the visible commands:** `init`, `onboard`, `doctor`, `demo`,
  `briefing`, `stats`, `status`, `recall`, `intelligence`, `feedback`,
  `learn`, `reflect`, `reset`, `config`.

Everything else is experimental. An experimental CLI command exits `2` with:

```
'cortex <name>' is experimental in this beta. Enable with CORTEX_EXPERIMENTAL=1 (unsupported).
```

To enable the full surface (unsupported in beta — expect rough edges):

```bash
export CORTEX_EXPERIMENTAL=1
```

Set the same variable in the MCP server's `env` block to register the extra
tools. **Experimental features are unsupported in this beta** — no stability
guarantees, and issues against them are lowest priority.

### Filing issues

File at **https://github.com/jessekemp1/cortex/issues**. The issue template asks
for your `cortex doctor --json` **(beta, arriving with this release)** output —
paste it in. It captures Python version, dependency state, key presence, bridge
reachability, and spool depth, which resolves most reports without a back-and-forth.
