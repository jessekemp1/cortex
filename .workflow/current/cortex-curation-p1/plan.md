# Plan — Cortex decision-store curation (P1): write-path importance filter + supersession

Classification: **Improvement** · Ships to cortex `main` · Est. > 2h (write path + read path + backfill + tests across 4+ files)

## Architecture

```
  cortex_record_decision (MCP)  ─┐
  POST /decisions/learning      ─┤→ mcp_handlers.record_learning_decision()
                                 │      │
                                 │      ├─ NEW: score = _importance_score(...)          [Change 1]
                                 │      ├─ NEW: entry["importance"]=score; low_signal flag
                                 │      ├─ NEW: if supersedes: append tombstone for old  [Change 2]
                                 │      └─ _append_line(decisions.jsonl, entry)  (unchanged sink)
                                 │
  hybrid_retriever.search() ─────┴→ _load_decision_patterns()
                                        ├─ NEW: skip entries with superseded_by         [Change 3a]
                                        └─ carry importance/age into Pattern
                                     _rrf_merge()
                                        └─ NEW: score *= importance_weight * decay       [Change 3b]
                                            (mirrors existing _load_outcome_boosts)
  scripts/memory_maintenance.py ──→ NEW: --backfill-importance  (one-time, idempotent)   [Change 4]
```

**Design invariants:** append-only (never mutate a line); annotate never drop; the read-side change is
the only thing that alters ranking, so write-path annotation is inert/safe if shipped alone.

## File manifest

Create:
- `intelligence/memory/importance.py` — `_importance_score()` + constants (pure, unit-testable, no I/O)
- `tests/test_importance_scoring.py`
- `tests/test_supersession.py`

Modify:
- `mcp_handlers.py` — `record_learning_decision()`: score + annotate + `supersedes` handling
- `mcp_server.py` — `cortex_record_decision()`: add optional `supersedes` param, pass through
- `api/routes/decisions.py` — `LearningDecisionRequest`: add optional `supersedes` field
- `intelligence/memory/hybrid_retriever.py` — `_load_decision_patterns()` skip superseded; add `_load_importance_weights()` + apply in `_rrf_merge` (alongside `_outcome_boosts`)
- `scripts/memory_maintenance.py` — add `--backfill-importance` subcommand
- `tests/test_hybrid_retriever.py`, `tests/test_learning.py` — extend for new behavior

## Test specifications (test-first)

- **Importance heuristic** (`test_importance_scoring.py`): `_importance_score("test integration", "", "", "")` → below `IMPORTANCE_FLOOR` (empty context+rationale, template text). `_importance_score(<real 200-char decision with context+alternatives+rationale>)` → above floor. Boundary: exactly-floor case.
- **Write annotation** (`test_learning.py` extend): call `record_learning_decision(decision="x", context="", rationale="")` → written entry has `importance` key and `low_signal: true`; a rich decision has `low_signal` absent/false. Assert entry still written (never dropped) and `decision_id` returned.
- **Supersession** (`test_supersession.py`): `record_learning_decision(..., supersedes="dec_OLD")` → new entry has `supersedes="dec_OLD"`; a tombstone line stamps `superseded_by=<new_id>` on the old id. `decisions.jsonl` line count = N+2 (new + tombstone), original line untouched.
- **Read-side skip** (`test_hybrid_retriever.py` extend): fixture jsonl with an entry + its tombstone → `_load_decision_patterns()` excludes the superseded id; a `low_signal` entry ranks below an equivalent high-signal entry for the same query in `search()`.
- **Backfill idempotent**: run `--backfill-importance` twice on a fixture → second run is a no-op (entries already scored), `.bak` created, line count stable.
- **Regression**: full `tests/test_retrieval_benchmark.py` recall metric ≥ pre-change baseline.

## XML task blocks

<task id="01" type="auto">
  <name>Create importance scoring module (pure heuristic)</name>
  <files>intelligence/memory/importance.py, tests/test_importance_scoring.py</files>
  <action>
    New module. `_importance_score(decision, context, alternatives, rationale) -> int` (1-10).
    Heuristic, NO model call: start at a base, subtract for empty context/rationale, subtract for
    template/test markers (regex: /^test[_ ]|integration test|^ok\b|placeholder/i), subtract for
    decision text under ~40 chars; add for presence of context+alternatives+rationale and length.
    Constants `IMPORTANCE_FLOOR = int(os.environ.get("CORTEX_IMPORTANCE_FLOOR", 3))`,
    exported. Pure function, deterministic (no Date.now / randomness). Write test_importance_scoring.py
    first with the boundary cases from the spec.
  </action>
  <verify>cd ~/dbx-dev/cortex && .venv/bin/python -m pytest tests/test_importance_scoring.py -xq</verify>
  <done>Empty/template decision scores below IMPORTANCE_FLOOR; rich decision scores above; tests green</done>
  <depends>none</depends>
</task>

<task id="02" type="auto">
  <name>Annotate importance + low_signal on write</name>
  <files>mcp_handlers.py, tests/test_learning.py</files>
  <action>
    In record_learning_decision(), before _append_line: import _importance_score + IMPORTANCE_FLOOR
    from intelligence.memory.importance; set entry["importance"]=score; if score < IMPORTANCE_FLOOR
    set entry["low_signal"]=True. Do NOT drop, do NOT change the spool path or return shape. Extend
    test_learning.py: assert importance key present, low_signal set for thin decision, absent for rich,
    entry still recorded.
  </action>
  <verify>cd ~/dbx-dev/cortex && .venv/bin/python -m pytest tests/test_learning.py -xq</verify>
  <done>Written entry carries importance + conditional low_signal; still never-drop; return shape unchanged</done>
  <depends>01</depends>
</task>

<task id="03" type="auto">
  <name>Explicit supersession on write (append tombstone)</name>
  <files>mcp_handlers.py, mcp_server.py, api/routes/decisions.py, tests/test_supersession.py</files>
  <action>
    Add optional supersedes:str="" param to record_learning_decision (mcp_handlers), thread through
    cortex_record_decision (mcp_server.py:498) and LearningDecisionRequest (decisions.py). When
    supersedes set: put entry["supersedes"]=supersedes on the new entry, then _append_line a tombstone
    {decision_id: supersedes, superseded_by: <new_id>, timestamp, source:"supersede"}. Append-only —
    never rewrite the original line. New test_supersession.py per spec.
  </action>
  <verify>cd ~/dbx-dev/cortex && .venv/bin/python -m pytest tests/test_supersession.py -xq</verify>
  <done>supersedes stamped on new entry; tombstone line added; original line byte-identical; N+2 lines</done>
  <depends>02</depends>
</task>

<task id="04" type="auto">
  <name>Read-side: skip superseded, down-weight low importance</name>
  <files>intelligence/memory/hybrid_retriever.py, tests/test_hybrid_retriever.py</files>
  <action>
    In _load_decision_patterns(): first pass collect superseded ids (entries with superseded_by);
    skip those ids when building Pattern list. Carry entry importance + timestamp onto the Pattern.
    Add _load_importance_weights() mirroring _load_outcome_boosts(): compute a per-decision multiplier
    = clamp(importance/BASE) * exp(-age_days / DECAY_HALF_LIFE_DAYS) with
    DECAY_HALF_LIFE_DAYS=int(os.environ.get("CORTEX_DECAY_HALF_LIFE_DAYS", 120)). Apply it in
    _rrf_merge at the same site outcome_boosts are applied. Extend test_hybrid_retriever.py: superseded
    excluded; low_signal ranks below high_signal for same query.
  </action>
  <verify>cd ~/dbx-dev/cortex && .venv/bin/python -m pytest tests/test_hybrid_retriever.py -xq</verify>
  <done>Superseded ids absent from patterns; low-importance/stale decisions rank lower; tests green</done>
  <depends>03</depends>
</task>

<task id="05" type="auto">
  <name>Backfill existing history (idempotent)</name>
  <files>scripts/memory_maintenance.py</files>
  <action>
    Add --backfill-importance subcommand: read decisions.jsonl, write .bak, for each entry lacking an
    importance key compute + add it (and low_signal), rewrite the file atomically (temp + rename).
    Idempotent: entries already scored are untouched; second run = no-op. Skip tombstone lines. Print
    counts (scored, skipped, flagged low_signal).
  </action>
  <verify>cd ~/dbx-dev/cortex && cp ~/.cortex/decisions.jsonl /tmp/dj.bak && .venv/bin/python scripts/memory_maintenance.py --backfill-importance && .venv/bin/python scripts/memory_maintenance.py --backfill-importance 2>&1 | grep -iE "scored 0|no-op|already"</verify>
  <done>First run scores all unscored entries + .bak written; second run is a no-op; line count stable</done>
  <depends>02</depends>
</task>

<task id="06" type="auto">
  <name>Full-suite + recall-benchmark regression gate</name>
  <files>tests/test_retrieval_benchmark.py</files>
  <action>
    Run the full cortex suite and the retrieval benchmark. Confirm no regression vs the known-good
    baseline (1,359 pass pre-change, modulo the 3 pre-existing test_doctor_json_reset failures).
    Recall metric on the benchmark must be >= baseline. Do not "fix" the 3 pre-existing doctor
    failures here (out of scope, proven unrelated).
  </action>
  <verify>cd ~/dbx-dev/cortex && .venv/bin/python -m pytest tests/ -q 2>&1 | tail -3</verify>
  <done>Suite pass count >= 1359 (+ new tests); only the 3 known pre-existing doctor failures remain; benchmark recall >= baseline</done>
  <depends>04, 05</depends>
</task>

## Validation checkpoints
- After 01: heuristic scores correctly on boundary cases (unit).
- After 02-03: write path annotates + supersedes without changing never-drop guarantee.
- After 04: ranking demonstrably favors high-signal/fresh over low-signal/stale/superseded.
- After 06: no suite regression; recall holds or improves — the actual P1 goal.
- **End-to-end proof:** re-run `cortex_intelligence(project="clio")` (or similar) and confirm real
  decisions surface with higher confidence than the pre-change empty/low-confidence result.

## Production deployment step
Edits are to the live writer + retriever (not a parallel copy), so passing Change 6 = production-ready.
Deploy = commit to cortex `main` (personal repo, user-reviewed — no autonomous commit). Restart the
bridge (`launchctl kickstart -k gui/$(id -u)/com.cortex.bridge`) so the running MCP picks up the new
writer/retriever. Run the backfill once post-deploy.

## Rollback strategy
- Write-path only (01-03,05) is inert without 04 — safe to leave if 04 regresses.
- Revert 04 (retriever) with `git revert` to restore prior ranking; annotations remain harmless.
- Backfill: restore `~/.cortex/decisions.jsonl` from the `.bak` the backfill wrote.
- No schema migration, no data loss (append-only + .bak).
