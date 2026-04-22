# Cortex Agent Operating Policy

**Audience**: Any Claude Code session operating in this repository (interactive
or dispatched via `cortex/supervisor/`).

**Precedence**: This file overrides default Claude Code habits. The harness
injects it as a system-prompt addendum at session start. Do not disregard.

See `DESIGN_PRINCIPLES.md` for broader architecture; this file is about agent
behavior only.

---

## 1. Rollover Policy — the harness decides, not you

Do NOT recommend, suggest, or voluntarily trigger session rollover:

- Never suggest `/compact`, `/clear`, "fresh session", or "new session" in
  user-facing output.
- Never estimate context percentage in user-facing output ("Context at 90%",
  "Context is tight", "approaching limit"). Your self-estimates are unreliable
  and pre-emptively train the user into a `/clear` ritual that costs more
  tokens than it saves.
- Never pre-emptively write a multi-section checkpoint to `progress.md`
  because you *think* context is filling up. The act of writing the
  checkpoint burns the runway you were trying to save.

The harness (Claude Code's native compaction + `cortex/session_watcher.py`)
owns rollover decisions. When you are near a real limit, do one of:

1. Finish the current atomic unit (a commit, a passing test, a single file
   edit).
2. Append up to six YAML fields to `.workflow/current/handoff.yaml`
   (`done`, `verified`, `open_questions`, `next_action`, `gate_command`,
   `confidence`).
3. Stop. Do not write a 60-line narrative. Do not ask the user to `/clear`.

## 2. Delegation over self-rotation

When a work unit is genuinely large or context is getting tight:

- Invoke a `Task()` sub-agent with a self-contained brief and return its
  structured summary to the parent turn.
- Keep the parent's context lean by not inlining research, file surveys,
  or diagnostic output that the sub-agent already summarized.
- Do NOT tell the user "delegate this to a sub-agent in a fresh session" —
  that is a self-rotation in disguise. Invoke the sub-agent yourself, now.

## 3. Handoff writes — split ownership, no silent skips

| Path                                     | Owner         | Agent allowed to write? |
|------------------------------------------|---------------|-------------------------|
| `.workflow/current/progress.md`          | Cortex daemon | No (read-only)          |
| `.workflow/current/handoff.yaml`         | Agent         | Yes                     |
| `.workflow/current/metadata.json`        | Either        | Yes (via MCP)           |
| `.workflow/current/plan.md`              | Agent         | Yes (at /plan time)     |

- If a write to `handoff.yaml` fails, log the error inline and continue. Do
  NOT say "skipping file write to preserve context" — that silent-skip
  behavior corrupts handoffs and is the single largest cause of lossy
  resumption.
- `progress.md` is rebuilt by the daemon from `handoff.yaml` plus git state.
  Do not write to it directly; you will race the daemon.

## 4. Scope discipline — project, not monorepo

`<project>/.workflow/current/` is the only valid handoff location.

Never write to a monorepo-level `.workflow/`. Monorepo-level handoffs cause
project drift (e.g. a Hotspex handoff poisoning a pupil session via
`Dev/.workflow/current/progress.md`). If you find a monorepo-level
`.workflow/` on disk, treat it as stale and ignore it.

## 5. Gates and verification on resume

When you resume from a handoff.yaml, the first action is:

1. Run the `gate_command` listed in the handoff.
2. If the gate passes → continue with `next_action`.
3. If the gate fails → STOP. Report the failure. Escalate to the user. Do
   NOT silently retry or patch the handoff to mask drift.

One retry is allowed only for transient infrastructure failures (network,
process-not-found). Anything else is a human-level escalation.

## 6. Model routing — don't override the conductor

`cortex/conductor/router.py` chooses provider+model per use case. If you
think the wrong tier was chosen (e.g. routed to Sonnet when the task needs
Opus judgment), say so and stop. Do NOT call a different model directly;
let the router adjust.

## 7. Escalation — five hard triggers that halt work

Halt and ask the user when:

1. **Ambiguity**: a judgment call with two or more defensible options.
   Write `{question, options, recommended, confidence}` to handoff.yaml
   and stop.
2. **Gate failure ×2**: one retry allowed, second failure escalates.
3. **Scope drift**: files changed outside the `<files>` list declared in
   `plan.md`.
4. **Budget overrun**: dollar or wall-clock exceeds plan estimate by >2×.
5. **Cross-project blast radius**: writes (not reads) outside the current
   project directory.

Do NOT resolve these silently.

---

## Anti-patterns seen in the wild

| Observed pattern                                       | Do this instead                                                   |
|--------------------------------------------------------|-------------------------------------------------------------------|
| "Context is tight. Checkpointing."                     | Finish the atomic unit. The harness will rotate when needed.      |
| "Context at 90% — recommend /compact or fresh session" | Delete that line. Never mention context % in user output.         |
| "Start fresh session, run /start, then /implement"     | Invoke `Task()` with the brief. Don't punt to the user.           |
| "Skipping file write to preserve context"              | Write the file. A few hundred tokens is not worth a lossy handoff.|
| Rewriting `progress.md` with a 60-line update          | Append six fields to `handoff.yaml`. Daemon will assemble the rest.|
| "Delegate Phase X to an agent" (as a suggestion)       | Invoke the sub-agent now. Don't describe the plan; execute it.    |
