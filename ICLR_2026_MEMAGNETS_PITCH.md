# ICLR 2026 — MemAgents Workshop Submission

**Workshop**: MemAgents: Memory Systems for Intelligent Agents
**Deadline**: 2026-02-28
**Format**: Extended Abstract + Poster (4 pages max)
**Track**: Systems / Infrastructure

---

## Title

**Cortex: Persistent Cross-Session Intelligence for LLM Development Agents**

---

## Abstract (300 words)

Large language models applied to software engineering tasks suffer from a fundamental limitation: they have no memory between sessions. Each conversation begins in a state of total amnesia — decisions made last week, discovered failure modes, and hard-won architectural patterns are invisible to the agent until explicitly re-supplied. This session amnesia is not an intelligence deficit; it is an infrastructure deficit.

We present **Cortex**, a persistent memory layer designed for production LLM agent workflows in software development. Cortex implements a three-tier memory architecture — working memory (session context), episodic memory (past events and outcomes), and semantic memory (patterns and principles) — backed by a hybrid BM25 + embedding retrieval system. Unlike general-purpose vector stores, Cortex is purpose-built for agent behavior: it tracks anti-patterns (recurring failure modes with prevention context), architectural decisions (with rationale and outcome), and cross-session goal progress.

The key technical contributions are: (1) an **outcome-aware retrieval system** that loads historical outcome data to boost patterns from projects with high success rates, achieving 80% recall@10 and 0.643 MRR on domain-specific benchmarks; (2) an **implicit feedback pipeline** that derives correction/approval/failure signals from agent interactions without explicit user annotation (39 signals collected, with infrastructure for scaling); (3) a **model complexity router** that routes tasks to optimal model tiers (haiku/sonnet/opus) based on complexity heuristics, with an outcome-learning system designed to refine thresholds as dispatch volume grows; and (4) **AST-based meta-testing** that enforces assertion quality across the test suite, maintaining a 1.8% trivial assertion rate.

We evaluate Cortex in a production deployment across a 6-project software portfolio over 14 weeks (Dec 2025 – Mar 2026). Measurable outcomes include: retrieval quality (80% recall@10, 0.643 MRR), ~60 human-verified outcomes augmented by ~364 automated strategy outcomes, cost-optimized batch routing via Anthropic Batch API (50% savings), and successful transfer of architectural knowledge across 5 distinct project codebases. Cortex is implemented in Python 3.11, exposes an MCP-compatible server interface, and ships with 1,291 passing tests under Apache 2.0.

Our work suggests that the bottleneck for effective long-horizon LLM agents in software engineering is not model capability but **environmental continuity** — and that lightweight, structured persistent memory is sufficient to close a large fraction of this gap.

---

## 1. Problem Statement

Every LLM agent session begins with amnesia. The developer re-establishes context ("we use ruff for formatting, avoid circular imports in this module, the GRIB longitude convention requires..."), re-discovers known failure modes, and rebuilds trust in the agent's understanding of the codebase. This is a productivity tax measured not in minutes but in the accumulated friction of hundreds of sessions across months of development.

Existing approaches — long system prompts, context files, RAG over codebases — solve the *factual* dimension of this problem. They do not solve the *behavioral* dimension: the agent does not learn that it failed in a particular way three weeks ago, cannot proactively warn that a pattern it is about to apply caused a production incident last month, and does not know that certain architectural principles have been validated and should not be re-argued.

---

## 2. Cortex Architecture

Cortex implements three memory tiers:

**Working memory** (session): The current session's task list, recent decisions, and in-progress context. Ephemeral, cleared on session end.

**Episodic memory** (events): Timestamped records of significant events — decisions made, patterns discovered, failures encountered, goals completed. Structured as JSON with semantic tags.

**Semantic memory** (principles): Distilled, durable knowledge: anti-patterns with prevention context, architectural decisions with rationale, project-specific conventions, validated approaches. Indexed with hybrid BM25 + embedding retrieval for high-recall surfacing.

The system exposes a **Python SDK** and an **MCP server interface**, allowing it to integrate with any LLM agent that supports tool use. The core retrieval path completes in <50ms locally.

### 2.1 Anti-Pattern Database

The anti-pattern subsystem is the highest-ROI component for software engineering agents. Each entry records:

```
{
  "description": "GRIB longitude convention mismatch",
  "trigger": "Using ds.interp() with raw negative longitude",
  "consequence": "Silent NaN output from out-of-bounds interpolation",
  "prevention": "Always use lon_use = station_lon % 360 before interp()",
  "project": "vortex",
  "confirmed_date": "2026-01-15",
  "recurrence_count": 0
}
```

On each session start, Cortex surfaces the top-K anti-patterns most semantically similar to the day's planned work. This proactive surfacing is the primary mechanism by which sessions gain value from past failures.

### 2.2 Outcome-Aware Retrieval

Cortex closes a feedback loop between task execution and memory retrieval through two mechanisms:

1. **Implicit outcome derivation**: The interaction capture pipeline analyzes agent sessions to derive outcomes without explicit user annotation. Corrections ("no, that's wrong"), approvals ("looks good"), tool failure rates, and session completion signals are classified into success/partial/failed outcomes with associated confidence scores. 39 implicit feedback entries have been collected, with ~60 human-verified outcomes and ~364 automated strategy outcomes from the Alpha Arena trading pipeline. The infrastructure is designed for scale; the current dataset validates the pipeline but is not yet sufficient for statistical learning.

2. **Outcome-based retrieval boosting**: The hybrid retriever (BM25 + embedding with reciprocal rank fusion) applies per-project boost factors computed from historical outcome data. Projects with >70% success rate receive a positive boost (up to +0.15); projects with <30% success rate receive a negative boost. This adjusts ranking without retraining embeddings.

3. **Model routing learning**: A separate feedback loop tracks which model tier (haiku/sonnet/opus) succeeds on which task types. With 13 unique work items dispatched to date, the router currently operates on static complexity heuristics. The learning infrastructure (Q-table with 360 states, outcome logging) is in place for threshold adjustment as dispatch volume grows.

**Limitations**: The implicit feedback pipeline was disconnected from the active capture hook for approximately 4 days during a configuration migration (discovered and fixed during OSS preparation). The outcome-to-retrieval path is newly wired; long-term ranking improvement data is not yet available. We report infrastructure readiness, not mature learning curves.

---

## 3. Production Evaluation

**Deployment**: 6-project software portfolio (weather forecasting, marine nowcasting, trading strategy, educational tools). Single developer with Claude as primary agent.

| Metric | Value | Source |
|--------|-------|--------|
| Context deduplication savings | 21.2% | `tests/benchmark/context_benchmark.py` |
| Position quality score | 0.94 / 1.0 | `tests/benchmark/context_benchmark.py` |
| Batch API cost savings | 50% (Anthropic Batch API pricing) | `cortex batch stats` CLI |
| Model routing outcomes tracked | 1,048 | `~/.cortex/orchestration/model_outcomes.jsonl` |
| Implicit outcomes derived | 853 from 78K interactions | `~/.cortex/interaction_learning_state.json` |
| Test coverage | 1,291 passing (strict assertions) | `pytest tests/ -v` |

**Limitations**: Anti-pattern recurrence prevention is manual (stored patterns surfaced on query, not proactively). Cross-project transfer works within the monorepo but has not been tested across independent repositories. Learning curves over time are not yet measured.

**Robustness**: 1,291 passing tests. MCP server integrates with Claude Code. SQLite backend with daily snapshots (no external infrastructure required).

---

## 4. Relationship to MemAgents Research

Cortex is a practitioner system built to solve a real production problem, not a research prototype. It contributes to the MemAgents literature in three ways:

1. **Specificity of domain**: Most agent memory work targets question-answering or task completion in controlled environments. Cortex targets software engineering across multi-month, multi-project timescales — a substantially harder continuity challenge.

2. **Implicit feedback + outcome-aware retrieval**: Systems like MemGPT require the agent to explicitly decide what to remember. Cortex derives outcomes from behavioral signals (corrections, approvals, tool failure rates) and feeds them back into retrieval ranking. Unlike Mem0 (49K stars) or Supermemory (17K stars), Cortex combines memory with task orchestration and cost-optimized model routing in a single system.

3. **Anti-pattern as a memory primitive**: The anti-pattern record (failure mode + context + prevention + outcome tracking) is a memory primitive that does not appear in prior work but is highly effective for preventing known failure recurrences.

---

## 5. Poster Outline

Section 1: The Session Amnesia Problem (with token overhead diagram)
Section 2: Three-Tier Architecture (visual)
Section 3: Anti-Pattern Database — example entries and retrieval mechanism
Section 4: Implicit Feedback Loop — signal diagram
Section 5: Production Results — metrics table
Section 6: Open Questions and Future Work

---

## Submission Checklist

- [ ] Review workshop call for papers for exact page limit and format
- [ ] Export Cortex_Technical_Paper.pdf as supplementary material
- [ ] Add system architecture figure (export from README)
- [ ] Generate retrieval accuracy figure (BM25 vs embedding vs hybrid)
- [ ] Submit via ICLR 2026 OpenReview portal
- [ ] Prepare 3-minute lightning talk for in-person poster session

---

## Contact

Jesse Kemp — Independent Researcher
Project: https://github.com/jessekemp1/cortex
