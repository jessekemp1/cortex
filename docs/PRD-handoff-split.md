# PRD: Handoff Split — Daemon vs Agent File Ownership

**Author:** Cortex Agent | **Date:** 2026-04-22 | **Status:** READY TO SHIP
**Effort:** ~2h implementation, ~0.5h testing | **Deploy:** Same day
**Precedent:** CLAUDE.md §3 (documents the intended split, not yet enforced in code)

---

## Problem

The transcript captured from the last pupil/ session contains this line:

> "Progress.md is being written to concurrently (daemon). Skipping the file
> write to preserve context — reporting state here instead."

This is a handoff-destroying bug. Agents and the Cortex daemon both own
`.workflow/current/progress.md` today:

- `cortex/session_snapshot.py:write_progress_snapshot` — called by
  `session_watcher.py:rotate_session` (daemon path).
- Every skill, `/implement`, `/plan`, and ad-hoc agent session — tries to
  `Write`/`Edit` `progress.md` directly.

When the daemon holds the file, the agent gives up the write to "preserve
context." The structured checkpoint the agent was about to emit is
destroyed, and the next session resumes with only whatever the daemon
managed to render.

CLAUDE.md §3 already declares the split as policy:

| Path                             | Owner         | Agent writes? |
|----------------------------------|---------------|---------------|
| `.workflow/current/progress.md`  | Cortex daemon | No            |
| `.workflow/current/handoff.yaml` | Agent         | Yes           |

Nothing in code enforces this. `handoff.yaml` doesn't exist as a file
contract. There is no schema, no writer, no reader, no test.

## Goals

1. Land a canonical YAML schema for `handoff.yaml` — 6 fields, no more.
2. Provide a single agent-facing API that writes it atomically.
3. Extend `session_snapshot.py` so the daemon reads any present
   `handoff.yaml` and renders its fields into `progress.md` — so the
   agent's structured handoff reaches the next session through the
   daemon's output path, not through the agent racing the daemon.
4. Never silently drop a handoff. If YAML serialization fails, log loud.

## Non-goals

- File locking on `progress.md`. Ownership is the discipline; locks are
  a symptom patch.
- Migrating existing `progress.md` content. Daemon continues to write it;
  the handoff.yaml section is additive.
- Cross-project handoff routing. `<project>/.workflow/current/` only,
  consistent with CLAUDE.md §4.
- Automatic invocation of the writer by agents. Policy (CLAUDE.md §1)
  directs agents when to write; this PRD provides the how.

## Schema

`.workflow/current/handoff.yaml` — exactly these keys. Unknown keys are
preserved on read but warned in logs. Missing keys default as shown.

```yaml
# Written by the agent. Read by cortex/session_snapshot.py.
# See CLAUDE.md §1 for when to update this.

done: []                 # list[str] — atomic units completed this session
verified: []             # list[str] — gate_commands that passed, one per line
open_questions: []       # list[str] — ambiguities blocking progress
next_action: ""          # str — one sentence, imperative
gate_command: ""         # str — shell command the next session must run first
confidence: 0.0          # float in [0.0, 1.0]

# Auto-populated by write_handoff(); agents should not set.
_written_at: "2026-04-22T..."
_branch: "phase-1b-..."
```

Why these six: they match the fields the transcript's hand-written
checkpoints converged on (done, next atomic unit, gate command, open
questions), plus `confidence` because CLAUDE.md §7 requires it for the
ambiguity escalation path.

## File manifest

**New files**
- `cortex/runtime/handoff.py` — agent API (`HandoffFields`, `write_handoff`,
  `read_handoff`, path resolution). ~120 LOC.
- `tests/test_handoff.py` — roundtrip, missing file, malformed YAML,
  unknown keys, integration with `session_snapshot.py`. ~180 LOC.

**Modified files**
- `cortex/session_snapshot.py` — add `_render_handoff_section` that loads
  `.workflow/current/handoff.yaml` via `runtime.handoff.read_handoff` and
  emits a markdown block. ~30 LOC added.
- `CLAUDE.md` — tighten §3 to reference `runtime/handoff.py` as the
  sanctioned writer. ~2 LOC edit.

## API

```python
from cortex.runtime.handoff import HandoffFields, write_handoff, read_handoff

# Agent-side write at a natural boundary (post-commit, post-gate).
write_handoff(
    HandoffFields(
        done=["commit phase-1a", "verify snapshot freeze"],
        verified=["pytest tests/test_echelon_snapshot.py -q"],
        open_questions=["PE definition — value-only vs value+bizeq?"],
        next_action="Write us_calibration.json with 50-state weights.",
        gate_command="pytest pupil/tests/test_echelon_snapshot.py -q",
        confidence=0.8,
    )
)

# Daemon-side read during snapshot assembly.
fields = read_handoff()  # → HandoffFields | None
```

Path resolution:
1. Explicit `workflow_dir` kwarg, else
2. `$CORTEX_WORKFLOW_DIR` env var, else
3. `Path.cwd() / ".workflow" / "current"`.

Never the monorepo root (CLAUDE.md §4).

## Behavior

- `write_handoff` writes atomically: temp file + `os.replace`. An
  incomplete write never leaves partial YAML for the daemon.
- `read_handoff` returns `None` on missing file, unparseable YAML, or
  schema violation. Never raises upward — the daemon must not crash
  because an agent wrote bad YAML.
- `session_snapshot.write_progress_snapshot` now reads the handoff and
  renders it into `progress.md` as a `## Agent Handoff` block above the
  existing "Resume Instructions" section. If no handoff present, the
  block is omitted.
- `confidence` outside `[0.0, 1.0]` is clamped, not rejected.

## Test plan

| Test | Asserts |
|---|---|
| `test_roundtrip` | `read_handoff(write_handoff(fields))` returns equal fields |
| `test_missing_file_returns_none` | No file → `read_handoff()` returns `None` |
| `test_malformed_yaml_returns_none` | Garbage YAML → `None` + log, no raise |
| `test_schema_violation_returns_none` | `done: "not a list"` → `None` |
| `test_unknown_keys_preserved_on_read` | Forward-compat: extra keys don't crash |
| `test_atomic_write_no_partial_file` | Interrupted write leaves prior version intact |
| `test_confidence_clamped` | `1.5` → `1.0`, `-0.2` → `0.0` |
| `test_auto_timestamp_added` | `_written_at` present after write |
| `test_path_respects_cwd` | `chdir` → writes to correct `.workflow/current/` |
| `test_path_respects_env_override` | `CORTEX_WORKFLOW_DIR` takes precedence |
| `test_progress_md_includes_handoff_section` | Integration: daemon renders agent fields |
| `test_progress_md_without_handoff_no_crash` | No handoff.yaml → progress.md still renders |

12 tests, target all pass in <1s.

## Rollout

1. Land this PR. Nothing starts writing `handoff.yaml` automatically —
   behavior is unchanged until an agent calls `write_handoff`.
2. Next: update `/ship`, `/implement`, `/plan` skills (off-repo) to call
   `runtime.handoff.write_handoff` instead of `Edit(progress.md)`.
3. Measure: count `progress.md` write errors in session logs for 7 days.
   Expect drop to ~0 for agent writers.

## Rollback

Delete `cortex/runtime/handoff.py`, revert `session_snapshot.py` diff.
No data migration — handoff.yaml files are ephemeral per-session.

## Success criteria

- 12/12 tests pass.
- `progress.md` rendered by daemon contains both its existing sections
  and an `## Agent Handoff` section when `handoff.yaml` is present.
- Full orchestration test suite (71+11+18) stays green.
- No new pre-existing test failures introduced.
