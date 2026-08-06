# Spec — Cortex decision-store curation (P1)

## Context
The research comparison (STORM-Opus + /deep-research, cortex `dec_824f8f0f2bd4`) independently
concluded: **a decision store that only grows recalls worse — curation, not capacity, separates
useful memory from noise.** Cortex today appends every decision unconditionally
(`mcp_handlers.record_learning_decision` → `_append_line` → `~/.cortex/decisions.jsonl`) and recall
(`hybrid_retriever._load_decision_patterns`) indexes every line. This is why `cortex_intelligence`
returns low-confidence / empty `similar_work`: real SA decisions compete in top-k against accumulated
noise (test rows, anomaly echoes, superseded entries). This is the same problem the vortex decouple
started fixing on the ingestion side; P1 fixes it on the decision-store side.

## Definition of Done
- **Write path** annotates each decision with an `importance` score and a `low_signal` flag; supports
  explicit `supersedes` linkage. Never drops or mutates (append-only + annotate — preserves cortex's
  never-lose-a-decision guarantee).
- **Read path** (`hybrid_retriever`) skips `superseded_by` entries and down-weights `low_signal` /
  low-importance / stale entries during RRF merge, reusing the existing `_load_outcome_boosts` pattern.
- **Backfill** scores + annotates the existing ~1,700-row history once (idempotent).
- **Observable success:** on a seeded fixture, a low-signal/superseded decision ranks below a
  high-signal one for the same query; recall precision on the benchmark improves or holds.

## Work Classification
**Improvement** — better than current, ships to cortex `main` (personal repo). If validation passes,
the production wiring is already in-place (edits are to the live writer + retriever, not a parallel
copy). If validation fails (recall benchmark regresses), revert the retriever change and keep only
the write-path annotation (inert without the read-side change).

## Gray-area decisions (autonomous)
1. **Reject vs annotate low-signal?** → Annotate (`low_signal: true`), never drop. Cortex ethos =
   crash-proof, never lose a decision. Recall down-weights; audit trail intact.
2. **Importance scoring: LLM or heuristic?** → Ship heuristic first (length/emptiness/template
   detection — no model call, zero latency). LLM 1–10 scoring is a flag-gated Phase 2 add.
3. **Supersession: explicit or automatic?** → Explicit (`supersedes: <dec_id>` param) first;
   embedding-similarity auto-linking is a gated later phase (false-supersession risk).
4. **Backfill destructive?** → No. Appends annotation tombstones / rewrites JSONL atomically with a
   `.bak`; reversible.
5. **Config surface** → module constants (`IMPORTANCE_FLOOR`, `DECAY_HALF_LIFE_DAYS`) with env
   overrides; no new config system.
