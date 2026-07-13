# Cortex Master Narrative

**Purpose of this file:** the single source of truth for how Cortex is described anywhere — README, talks, Show HN, beta onboarding, the paper. If an artifact says something this file doesn't support, the artifact is wrong. Update this file first, then let changes flow outward. See §9 for the derivation map.

---

## 1. Canonical one-liner and elevator

**One-liner (frozen):**

> Your agent isn't dumb, it's amnesiac — session memory is an infrastructure problem, and Cortex is a local-first, open-source fix you can verify in 30 seconds with `cortex demo`.

**Elevator (3 sentences):**

Every new LLM session starts from zero: decisions made last week, bugs debugged last month, and patterns validated over months are invisible to the agent — you are the continuity layer, not the system. Cortex is a local-first persistent intelligence layer that fixes this with three-tier memory, an anti-pattern database, outcome learning, and model routing, exposed to any agent via MCP. It does not make the LLM smarter; it gives the LLM the right context at the right time.

**Canonical analogy:**

> "Cortex is like giving a consultant a well-organized notebook. Same intelligence, vastly different effectiveness."

## 2. Problem statement

LLM-powered development agents exhibit **session amnesia**. Each new conversation discards all prior context. The result is a systematic productivity tax:

- Repeating context on every session start ("remember, we use ruff for formatting…")
- Re-discovering the same bugs ("oh right, that's the circular import issue")
- Re-explaining architectural decisions settled weeks ago
- No accumulation of learned patterns across a project portfolio

> "This is not an intelligence problem. It is an infrastructure problem. Cortex is the fix."

Target user, stated narrowly on purpose: **a developer or small team using LLM agents across a multi-project portfolio over months or years.**

## 3. Claims table — the only numbers any artifact may quote

Rule: no deck, post, or doc quotes a number absent from this table. To use a new number, add it here first with source and caveat. This rule exists because we shipped an inflated test count once (see §5, beat 4) and never want to again.

| Claim | Value | Source | Verified | Caveat |
|---|---|---|---|---|
| Tests passing on fresh clone | 1,855 | README badge; `docs/AUDIT_FINDINGS.md` | 2026-06 | Hermetic subset; integration/network-marked tests excluded by default |
| Trivial-assertion rate | 1.8% | AST meta-testing; paper §Testing | 2026-03 | Self-measured methodology |
| Retrieval recall@10 | 80% | `tests/test_retrieval_benchmark.py`; paper abstract | 2026-03 | Domain-specific internal benchmark, no external baseline |
| Retrieval MRR | 0.643 | same | 2026-03 | Same caveat; strict MRR ≥ 0.40 gate requires `VOYAGE_API_KEY` |
| Context dedup savings | 21.2% | paper; README | 2026-03 | Measured on author's corpus |
| Routing quality score (PQS) | 0.94 | paper; Show HN draft | 2026-03 | Author's test set |
| API cost reduction | ~50% | Anthropic Batch API + routing; paper | 2026-03 | Vs. routing everything to the largest model |
| Bridge init latency | 6.8 ms | paper §Entry Points | 2026-03 | Local machine measurement |
| Codebase size | ~197k lines of Python, 621 files | `git ls-files` count | 2026-07 | Includes tests |
| Build effort | 496 commits, 103 active days, ~7 months, single author | git history (2025-12-11 → 2026-06-30) | 2026-07 | Heavily AI-assisted (authored with Claude) |
| MCP tools exposed | 18 | `mcp_server.py` | 2026-07 | — |
| Author's live corpus | 213 decisions, 1,663 outcomes, 39 implicit-feedback signals | `~/.cortex/` (author's machine) | 2026-07 | Single-user data; grows daily |
| Corpus outcome skew | 95.7% success, 1 recorded failure | author's `outcomes.jsonl` | 2026-07 | Optimistic skew — cited as a *limitation*, never as a quality claim |
| Portfolio spread of decisions | ~3 of 4 recorded decisions concern projects other than Cortex | author's `decisions.jsonl` | 2026-07 | Evidence it's portfolio memory, not a changelog |
| Outcome learning signal | Implicit feedback ≈ 10–100x more signal than explicit rating | paper §Learning | 2026-03 | Design claim, not an external measurement |
| Releases | v1.0.0 (2026-06-02), v1.0.1 (2026-06-24), v1.1.0 (2026-06-29) | git tags | 2026-07 | — |

## 4. Capability map — the four primitives

1. **Three-tier memory.** Working (session, in-memory LRU) → episodic (past events, SQLite) → semantic (permanent, hybrid BM25 + embedding retrieval merged by reciprocal rank fusion). Memory is table stakes; the next three are the differentiators.
2. **Anti-pattern database.** Failure mode + trigger + prevention context, stored as a distinct retrieval-boosted type. Canonical quote: *"It's not just 'remember this happened' — it's 'here's why this approach fails and what to do instead.'"*
3. **Outcome learning.** Learning signals derived from what the user actually does (followed / overridden / ignored) rather than explicit ratings. Guardrail rule, recorded as a decision on 2026-06-01: *log success only where there is direct evidence — fabricated outcomes poison the calibration data that makes the memory worth having.*
4. **Model routing + goal-to-task pipeline.** Route tasks to cost-appropriate model tiers by complexity; parse goals into prioritized, dispatchable work. This is the orchestration half that memory-only competitors don't have.

Delivery surfaces: MCP server (18 tools — native in Claude Code / Claude Desktop), Python SDK (`CortexBridge`), CLI (`cortex` / `cx`), local FastAPI bridge. Everything lives in `~/.cortex/`; nothing leaves the machine unless an external backend is configured.

## 5. Story beats (chronological)

1. **Origin (Dec 2025).** Born inside a personal monorepo, next to a weather-forecasting ensemble and a trading bot, as the shared intelligence layer between them. First commit 2025-12-11.
2. **Depth over speed (Jan 2026).** Deliberate reversal of a "<500 ms startup" constraint: accept seconds of startup for comprehensive analysis. Documented in `DESIGN_PRINCIPLES.md`.
3. **The strategic pivot (Mar 2026).** Explicit decision *not* to compete with Mem0/Supermemory on retrieval quality — compete on what nobody else has: task orchestration + memory in one system, anti-pattern primitives, the goal-to-task pipeline. Documented in `ROADMAP.md`.
4. **The audit (Jun 2026) — the candor beat.** A pre-release adversarial self-audit found the package **did not import on a fresh clone**: 82 files imported `cortex.X`, but no `cortex/` package existed — a sibling editable install had masked it for months. Fixed with a one-line namespace shim rather than an 82-file refactor. The same audit retracted an inflated test badge (2,361+ → 1,855), removed personal-path leaks, and replaced a silent no-API-key hang with a fast, actionable exit. Full record: `docs/AUDIT_FINDINGS.md`. Consequence: `cortex demo` exists as a 30-second falsifiable proof — no API key, no network, real code paths.
5. **Productization sprint (Jun 2026).** v1.0.0 "survive the adversarial audit" → v1.0.1 "make Cortex work for a second user" → v1.1.0 "recall quality" (local semantic embeddings, decisions as a durable first-class recall source). The memory system also hardened its own uptime after an outage (dedicated keep-alive supervision for the bridge).
6. **Dogfooding, continuously.** Cortex recorded the decisions made while building Cortex — including its own reversals and process failures. Roughly 3 of 4 decisions in the author's live corpus are about *other* projects: it functions as portfolio memory, not a project changelog.

## 6. Positioning and honest comparisons

- **Mem0** (~49K stars): the established general-purpose agent-memory player with a large ecosystem. If you're building a product that needs memory for thousands of users, Mem0 is probably the right choice.
- **Supermemory** (~17K stars): excellent retrieval benchmarks. Cortex trades some retrieval performance for task-orchestration primitives Supermemory doesn't have.
- Frozen tone rule: *"Neither comparison is a clean win — it depends on the use case."* No competitor bashing, anywhere, ever.

**What Cortex doesn't do:** no cloud sync, no hosted service, no native OpenAI/Gemini clients (though MCP is provider-agnostic at the protocol level).

## 7. Weaknesses and disruption risks (kept in sync with ROADMAP.md)

Stated unflinchingly, because the candor is load-bearing:

- **Zero community.** No external users yet; the first external feedback report will surface findings the self-audit missed.
- **Single-developer validation.** Every metric in §3 is self-measured; no external baselines.
- **The learning loop was broken for 4 days** without notice before detection — reliability of the feedback pipeline is not yet proven.
- **Retrieval is mediocre.** The bottleneck is retrieval precision, not corpus content; near-duplicate decisions blur top-3 results.
- **The outcome store skews optimistic** (95.7% success). This is why the evidence-only logging rule exists, and why the skew is cited as a limitation.

**Top disruption risk (self-assessed):** Anthropic ships a native memory API — estimated 60% likely by Sep 2026. Hedge: MCP is the right abstraction layer; every Cortex feature should work with any LLM agent, and the orchestration + anti-pattern layers sit *above* whatever memory primitive the platform provides.

## 8. Asks by audience

| Audience | Ask |
|---|---|
| Technical peers (talks) | (1) Be the second user: 2–3 beta testers, ~15-min install via `BETA_ONBOARDING.md`, one week of normal use, one 30-min feedback call. (2) Answer two questions: *where does agent-memory friction actually come from for you?* and *does the anti-pattern database resonate, or does it sound like manual overhead?* (3) "Audit me": fresh-clone it, try to break it in 15 minutes, file issues — find the next S0. |
| Show HN | The two feedback questions above, plus install-and-verify (`cortex demo`). |
| Beta users | Follow `BETA_ONBOARDING.md`; report friction, not praise. |

## 9. Derivation map

| Artifact | Derives from |
|---|---|
| `README.md` | §1, §2, §4, §3 (numbers) |
| `docs/show_hn_draft.md` | §1, §2, §6, §8, §3 (numbers) |
| Talks / decks | all sections; slide numbers must trace to §3 |
| `BETA_ONBOARDING.md` | §1, §8 |
| `docs/cortex_paper.md` | §3, §4 (paper is the primary source for benchmark methodology) |

Maintenance: when a number changes, update §3 first (value + verified date), then sweep derived artifacts. `grep -rn "<old number>" README.md docs/` before any release or external post.
