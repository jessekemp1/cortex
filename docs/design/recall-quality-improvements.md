# Design: Recall-quality improvements for cortex_intelligence

**Status:** P0 + P1 implemented & tested (branch `p0p1-recall`) · **Scope: P0+P1**

## Context

A small blind A/B probe (n=8 memory questions + 2 controls, single judge) compared answers **with** cortex's recall vs **cold**. Directional finding (not statistically powered — treat as a signal, not a target):

- When cortex surfaced the right decision, answers improved a lot (facts a cold session can't know).
- But it surfaced the right decision only ~half the time, often buried under an off-topic top hit; embedding scores were flat (~0.06), the signature of the local `HashingVectorizer`. Irrelevant recall sometimes *hurt*.
- **The bottleneck is retrieval, not corpus content** — the content drove every win.

Two fixes are no-regret on first principles (independent of the probe's exact numbers). Speculative tuning is deliberately deferred until real user testing surfaces real recall failures.

## P1 — Decisions as a durable, first-class source ✅ implemented

`pattern_indexer.load_patterns()` now always loads recorded decisions from
`~/.cortex/decisions.jsonl` (via `_load_decisions()`) as `Pattern`s
(`pattern_type="decision"`, project preserved), deduped, **independent of
`patterns.json`**. Verified: decisions load even with no `patterns.json` present,
so they survive a git pattern re-index and new decisions are picked up on the
next index build. This replaces the earlier fragile one-time backfill (which a
re-index would have wiped). *Files:* `intelligence/memory/pattern_indexer.py`.

Follow-up (cheap, deferred): an explicit cache-invalidate hook on the
decision-write path for immediate (vs next-build) freshness.

## P0 — Local semantic embeddings via optional Ollama addon ✅ implemented & tested

`embeddings_client.py` is now a pluggable backend: default `HashingVectorizer`
(unchanged, light), auto-detecting `Voyage (key) > Ollama (reachable) > hashing`,
selectable via `CORTEX_EMBED_BACKEND` (`auto|voyage|ollama|local`). The recommended
local backend is **Ollama** — it adds **zero Python dependencies** to cortex
(called over stdlib HTTP), runs as an external binary, and gives real semantic
embeddings offline/free. Config: `CORTEX_OLLAMA_HOST`, `CORTEX_OLLAMA_EMBED_MODEL`
(default `nomic-embed-text`, 768-dim; the required `search_query:`/`search_document:`
prefixes are applied automatically). Per-call graceful fallback to hashing.
`hybrid_retriever.py` records the active backend in the embeddings cache and
re-embeds on a backend switch (prevents querying stale hashing vectors with
semantic ones). *Files:* `intelligence/embeddings_client.py`,
`intelligence/memory/hybrid_retriever.py`.

**Addon install (optional):** install `ollama` → `ollama serve` →
`ollama pull nomic-embed-text`. The base install needs none of this. (A no-daemon
`cortex[semantic]` fastembed extra is a possible future alternative.)

**Measured** (same 8 memory questions, recall hit-rate of the exact source decision):

| metric | hashing | Ollama+nomic |
|---|:--:|:--:|
| hit@10 | 3/8 | **5/8** |
| hit@3 | 0/8 | 1/8 |
| hit@1 | 0/8 | 0/8 |

Semantic embeddings measurably improve ranking (more right-decisions surfaced,
better ranks), **but pinpoint top-3 precision stays weak** — the corpus holds many
near-duplicate decisions per topic (~19 Manulife-Genie alone), so the exact sibling
is hard to isolate by similarity alone. That's a retrieval-granularity problem, not
an embedding one → see Deferred (P3 is the real next lever).

## Validation

Re-run the recall probe (`tmp/cortex_eval/recall_ab.py`: same questions, hashing vs
Ollama, hit@k of the exact source decision) after any retrieval change. Confirms
direction; not a fixed numeric target.

## Deferred (revisit only after cortex is in real user testing)

**P3 — per-query project scoping (+ optional reranking)** is now the identified
next lever: the P0 data shows top-3 precision is limited by many near-duplicate
decisions, which project-scoping the candidate set (or a light reranker) directly
addresses. Plus P2 relevance-gating/thresholds and promoting the probe to a CI
regression suite. All deferred until cortex is in real user testing — optimize
against real recall failures, not the synthetic benchmark. (Reference: the
`cortex_outcomes` `/v2/outcomes` fix is on branch `corpus-ingest`.)
