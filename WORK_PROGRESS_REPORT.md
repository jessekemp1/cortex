# Cortex Work Progress Report
**Last updated:** 2026-04-08 — Harsh completion sweep

## Verdict: NEEDS-WORK

## Verified Facts (2026-04-08 sweep)

### Tests: GREEN
1341 passed, 17 skipped, 5 xfailed — 62.91s. No failures.

### Self-Audit: DEGRADED
- Memory Bridge: CONNECTED
- Learning Loop: ACTIVE (59 outcomes, 39 feedback)
- Anti-Pattern Mechanisms: 6/7 (missing: "Time estimates in specs")

### Overnight Queue: WORKS (dry-run)
6 jobs queue correctly. Pipeline code is wired.

### Bridge Intelligence: BROKEN INTERFACE + POOR OUTPUT
- `bridge.py intelligence "<query>"` — FAILS. Requires `--project` flag not shown in CLAUDE.md docs.
- With `--project cortex`: returns similarity=0.07, git log dump as "recommendation", `lessons_count: 0`, `applicable_patterns: []`, project status="inactive" (wrong).
- Not actionable. Returns something, not something useful.

## Harsh Answers

**1. Batch pipeline end-to-end?** Partially. Code wired (commit 2827f9fe). Never verified in production. No run logs confirmed.

**2. Bridge returns useful intelligence?** No. 0 lessons, 0 patterns in live query. Git log dump ≠ intelligence.

**3. Learning loop actually learning?** No. 59 outcomes recorded but `lessons_count: 0`. outcomes.jsonl → ChromaDB embedding pipeline missing or not running.

**4. Claims vs Reality gap:**
| Claim | Reality |
|-------|---------|
| Pattern matching from outcomes | 0 patterns in live query |
| Learning from outcomes | outcomes written, not embedded |
| Bridge CLI as documented | Broken — missing --project |
| Intelligence seeding post-batch | Code wired, production unverified |

**5. Blocks tomorrow morning:**
1. Bridge CLI broken — every undocumented caller fails silently
2. ChromaDB empty — 59 outcomes not converted to patterns
3. No outcome→pattern extraction job exists

## Top 3 Fixes

1. **bridge.py CLI** — make `--project` optional, detect from cwd
2. **Force ChromaDB seeding** — run seed_intelligence.py, verify lessons_count > 0
3. **outcomes.jsonl → pattern extraction** — close the feedback loop

## What Works
- Test suite (1341 passing)
- Overnight queue scheduling
- Self-audit (6/7 checks)
- Data collection (outcomes written)

## What's Broken/Vestigial
- Bridge CLI interface (wrong documented usage)
- ChromaDB embeddings (empty)
- outcomes → pattern extraction (missing)
- Project status detection (returns "inactive" for active projects)
