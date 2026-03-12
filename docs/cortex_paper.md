---
title: "Cortex: Persistent Intelligence Architecture for LLM-Powered Development Agents"
author: "Jesse Kemp"
date: "March 2026"
abstract: |
  Large language models exhibit session amnesia — each new conversation discards all prior context, forcing developers to repeatedly re-explain decisions, rediscover bugs, and re-establish architectural understanding. We present Cortex, a persistent intelligence layer that compensates for this limitation by maintaining structured memory, learning from implicit feedback signals, and routing tasks to cost-appropriate model tiers. Deployed across a six-project portfolio for eight weeks, Cortex achieves 21.2% context deduplication savings, 0.94 position quality score on retrieved context, and 50% cost reduction via intelligent batch routing. The system processes 958+ validated tests with behavioral assertions enforced by AST-based meta-testing. We describe the three-tier memory architecture, hybrid BM25/embedding retrieval, quality-weighted learning from 557+ tracked outcomes, and autonomous operations including platform-agnostic monitoring, approval gates, and crash-resilient state persistence.
geometry: margin=1in
fontsize: 11pt
numbersections: true
toc: true
header-includes: |
  \usepackage{booktabs}
---

# Introduction

The adoption of LLM-powered development agents (Claude Code, GitHub Copilot, Cursor) has introduced a systematic productivity tax: **session amnesia**. Every new conversation starts from zero. Decisions made last week, bugs debugged last month, and architectural patterns validated over months are invisible to the agent.

This is not an intelligence problem — it is an infrastructure problem. The LLM's reasoning capability is unchanged between sessions; what changes is the quality and completeness of the context it receives.

Cortex addresses this by providing a persistent intelligence layer that:

1. **Maintains structured memory** across sessions with three-tier promotion (working → episodic → semantic)
2. **Learns from outcomes** via implicit feedback signals (10–100x more signal than explicit rating)
3. **Routes tasks** to cost-appropriate model tiers (haiku/sonnet/opus) based on complexity analysis
4. **Discovers work** by parsing goal files, git history, and anomaly detection
5. **Operates autonomously** with platform-agnostic monitoring, approval gates, and crash-resilient state

## Contributions

- A three-tier memory architecture with weighted retrieval and evidence-based promotion criteria
- An implicit feedback system that derives learning signals from user behavior without explicit annotation
- A hybrid BM25 + embedding retrieval pipeline with reciprocal rank fusion
- Measured production results: 21.2% dedup savings, 0.94 position quality, 50% batch cost savings
- AST-based meta-testing that enforces assertion quality across the test suite
- Autonomous operations: platform-agnostic alert monitoring (macOS/Linux), 3-policy approval gates, atomic state snapshots

# System Architecture

Cortex is organized into four layers: Entry Points, Safety, Retrieval/Memory, and Learning.

## Layer 1: Entry Points

Five entry points serve different interaction patterns:

| Entry Point | Purpose | Latency |
|---|---|---|
| `bridge.py` | Universal CLI interface | 6.8ms init |
| `cli.py` | Full command suite (40+ commands) | varies |
| `mcp_server.py` | Model Context Protocol for Claude Desktop | <100ms |
| Plugins | Custom extensions | varies |
| FastAPI server | Dashboard and API | <50ms |

The `CortexBridge` class provides the universal interface:

```python
class CortexBridge:
    def read_context(self, project: str) -> Dict
    def query_intelligence(self, request: str, project: str) -> IntelligenceResult
    def get_portfolio_stats(self) -> Dict
```

## Layer 2: Safety

All queries pass through a defensive prompting pipeline before reaching intelligence layers:

1. **Input Validation** — length checks, scope verification, encoding normalization
2. **Injection Detection** — 28 compiled regex patterns across 4 severity levels (CRITICAL/HIGH/MEDIUM/LOW). Performance: <0.5ms per query, 0% false positive rate on legitimate queries
3. **Output Validation** — format verification, confidence thresholds, hallucination marker detection
4. **Guardrails** — query templates that constrain response scope

## Layer 3: Retrieval and Memory

### Three-Tier Memory

Items are stored and promoted through three tiers based on access patterns and outcome data:

| Tier | Retention | Storage | Weight | Promotion Criteria |
|---|---|---|---|---|
| Short-term | Session | In-memory (50 items, LRU) | 1.5x | Entry point for all new items |
| Working | 7 days | SQLite | 1.2x | 3+ accesses OR has outcome |
| Long-term | Permanent | JSON file | 1.0x | 10+ accesses AND consistent success |

The weighting scheme is counterintuitive: short-term items receive the *highest* weight (1.5x). This reflects the recency bias that is appropriate for development work — the pattern you discovered 10 minutes ago is more likely relevant than one from last month.

### Hybrid Retrieval

Queries are processed through a dual-pipeline retrieval system:

1. **BM25 Search** — keyword matching for exact terminology (function names, error codes)
2. **Embedding Search** — semantic similarity for conceptual queries ("how do we handle auth?")
3. **Reciprocal Rank Fusion** — merges both ranked lists with configurable alpha (default 0.5)

The alpha parameter tunes the balance: 0.0 = pure BM25, 1.0 = pure embeddings. In practice, the balanced default captures both exact matches and semantic near-misses.

## Layer 4: Learning

### Implicit Feedback Collection

Rather than requiring explicit ratings, Cortex derives learning signals from observable user behavior:

| Signal | Detection Method | Weight |
|---|---|---|
| **Followed** | Similarity > 0.7 between recommendation and action | +1 |
| **Overridden** | Similarity 0.3–0.7 (modified but influenced) | 0 (neutral) |
| **Ignored** | Similarity < 0.3 or no action within session | -1 |

This produces 10–100x more signal than explicit feedback because every recommendation-action pair generates a data point automatically.

### AI-as-a-Judge Evaluation

For quality assessment, Claude Haiku scores responses on five dimensions (1–5 scale):

1. Relevance — does it address the query?
2. Clarity — is it understandable?
3. Accuracy — is it factually correct?
4. Actionability — can the user act on it?
5. Timeliness — is the information current?

### Data Quality Framework

Six dimensions are tracked continuously:

| Dimension | Score | Notes |
|---|---|---|
| Completeness | 100% | Required fields always present |
| Consistency | 100% | No contradictions detected |
| Accuracy | 100% | Factual verification via outcomes |
| Timeliness | 15% → improved | Addressed by three-tier memory weighting |
| Uniqueness | 91% | 21.2% deduplication savings measured |
| Validity | 100% | Schema validation enforced |

Overall quality: **86.4%** measured on 57 production outcomes.

# Orchestration System

## Task Queue

Tasks are managed in a SQLite-backed priority queue with three levels:

| Priority | Behavior | Example |
|---|---|---|
| A (Critical) | Always realtime execution | Security fix, production bug |
| B (Important) | Batch if deadline > 4h | Feature implementation |
| C (Background) | Always batch (50% cost savings) | Research, analysis |

## Intelligent Model Routing

The supervisor routes tasks to the cheapest capable model tier:

| Tier | Model | Use Case | Cost |
|---|---|---|---|
| Haiku | claude-haiku-4-5 | Ops tasks, git, formatting | $0.25/MTok |
| Sonnet | claude-sonnet-4-6 | Code edits, test writing | $3/MTok |
| Opus | claude-opus-4-6 | Architecture, research | $15/MTok |

The router learns from outcome data: if sonnet-tier tasks consistently succeed, they stay at sonnet. If they fail and require opus retry, the router adjusts thresholds.

## Batch API Integration

LOW-priority tasks are deferred to the Anthropic Batch API:

- **Submission window**: 2–6 AM UTC (off-peak)
- **Cost savings**: 50% vs realtime API calls
- **State persistence**: Queue survives process restarts via SQLite
- **Measured throughput**: 685 jobs verified in first deployment

# Autonomous Operations

## Platform-Agnostic Alert Monitor

The alert monitor detects anomalies and routes restart commands based on platform:

```python
def _detect_platform() -> str:
    if sys.platform == "darwin":
        return "macos"  # launchctl
    return "linux"  # systemctl
```

On macOS, services are managed via `launchctl`. On Linux (Hetzner production), via `systemctl`. The monitor checks service health on a configurable interval and dispatches alerts through the approval gate before taking action.

## Approval Gates

Three policies govern autonomous actions:

| Policy | Scope | Approval |
|---|---|---|
| `auto_approve` | Low-risk ops (status checks, reads) | Automatic |
| `human_approval` | Destructive ops (restarts, deployments) | Requires human confirmation |
| `deny` | Disallowed ops (force push, data deletion) | Always blocked |

## Crash-Resilient State Snapshots

State is persisted via atomic writes:

1. Serialize state to temporary file
2. `fsync()` the temporary file
3. Atomic `os.rename()` to final path

This guarantees either the old state or the new state is on disk — never a partial write. Recovery on startup reads the snapshot and resumes from the last consistent state.

# Testing and Quality Assurance

## Test Suite

958+ tests across the Cortex codebase, organized by component:

| Module | Tests | Coverage |
|---|---|---|
| Tiered Memory | 31 | 100% |
| Context Optimizer | 26 | 100% |
| Hybrid Retriever | 17 | 100% |
| Quality Judge | 23 | 100% |
| Implicit Feedback | 28 | 100% |
| Data Quality | 28 | 100% |
| Safety | 22 | 100% |
| Prompts | 32 | 100% |
| Orchestration | 50+ | 100% |
| Autonomous Ops | 34 | 100% |
| Integration | 30+ | 100% |

## AST-Based Meta-Testing

A novel contribution is the assertion quality gate — tests that test the tests. Three meta-tests scan the entire suite using Python's `ast` module:

1. **No Trivial-Only Test Files** — flags files where >50% of test functions use only `isinstance()`, `is not None`, or `in (True, False)` assertions
2. **Integration Tests Have Behavioral Calls** — verifies that integration tests actually call system methods (`.get_context()`, `.learn()`, `.dispatch()`) rather than just testing imports
3. **No Empty Test Bodies** — catches `pass`-only test functions that inflate test counts

A subtle implementation detail: `mock.assert_called_once()` is a *method call*, not a Python `assert` statement. The AST parser sees it as `ast.Call`, not `ast.Assert`. We convert these to explicit `assert mock.call_count == 1` to satisfy the quality gate while preserving the same verification logic.

# Production Results

## Measured Outcomes

| Metric | Value | Method |
|---|---|---|
| Context deduplication | 21.2% savings | A/B comparison on 100 queries |
| Position quality score | 0.94 / 1.00 | Relevance ranking of retrieved context |
| Batch cost savings | 50% ($16.22 saved) | Batch vs realtime API comparison |
| Test assertion quality | 1.8% trivial | AST meta-test measurement |
| Learning outcomes tracked | 557+ | Implicit + explicit feedback |
| Anti-patterns stored | 12+ | With full prevention context |

## Deployment Scale

- **6 projects** in active portfolio (Vortex weather API, Alpha Arena trading, Pupil simulation, Cortex itself, DJ-CoPilot, Kempion research site)
- **5,660+ tests** across the portfolio
- **8 weeks** of continuous production use
- **2 platforms**: macOS (development), Linux (Hetzner production)

# Related Work

| System | Approach | Difference from Cortex |
|---|---|---|
| Mem0 | Universal memory layer, multi-tenant | General-purpose; no developer-workflow primitives |
| claude-mem | Claude Code plugin, auto-capture | Record/replay; no task orchestration or implicit feedback |
| Supermemory | Temporal contradiction handling | Sophisticated retrieval; no work discovery or model routing |
| Windsurf | Auto-generated workspace memories | Workspace-isolated; no cross-project transfer |

Cortex is optimized for one use case: a developer or small team using LLM agents across a multi-project portfolio over months. It combines memory + orchestration in a single system with quality-weighted learning.

# Conclusion

Session amnesia is the dominant bottleneck in LLM-powered development workflows. Cortex demonstrates that structured memory, implicit feedback learning, and intelligent task routing can compensate for this limitation with measurable impact: 21.2% deduplication savings, 0.94 position quality, and 50% batch cost reduction.

The system's self-awareness mechanisms — AST-based meta-testing, data quality tracking, and autonomous monitoring — ensure that quality compounds rather than degrades over time. 958+ tests with behavioral assertion enforcement prevent the common failure mode of inflated test counts masking shallow coverage.

Future work includes temporal contradiction handling (detecting when stored patterns conflict with new evidence), cross-portfolio transfer learning, and integration with additional LLM providers beyond Anthropic.

# Appendix: Performance Characteristics

| Operation | Latency | Notes |
|---|---|---|
| Bridge initialization | 6.8ms | 99.5% faster than 1s target |
| Portfolio stats query | <1ms | 99.1% faster than target |
| Hybrid retrieval (cached) | 0.05ms | First search ~100ms |
| Tiered memory query | <50ms | Weighted merge across 3 tiers |
| Input validation | <1ms | Compiled regex |
| Injection detection | <0.5ms | 28 patterns |
| AI-as-Judge evaluation | <500ms | Claude Haiku |
| Quality assessment | ~1ms | Per item |
| Task enqueue | ~50ms | SQLite-backed |
| Intelligence query | 125ms–4s | Depends on sources queried |
