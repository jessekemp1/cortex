# Cortex Architecture

**Version:** 2.0 (Post-AI Engineering)
**Last Updated:** 2026-02-01

This document provides detailed architectural diagrams and data flows for the Cortex intelligence system.

---

## System Overview

Cortex is organized into four layers: Entry Points, Safety, Retrieval/Memory, and Learning.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORTEX INTELLIGENCE SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         ENTRY POINTS                                    │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │bridge.py │  │  cli.py  │  │briefing  │  │ plugins  │  │   API    │ │ │
│  │  │(Universal│  │(Commands)│  │  .py     │  │ system   │  │endpoints │ │ │
│  │  │Interface)│  │          │  │          │  │          │  │          │ │ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │ │
│  └───────┼─────────────┼─────────────┼─────────────┼─────────────┼───────┘ │
│          └─────────────┴─────────────┼─────────────┴─────────────┘         │
│                                      ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         SAFETY LAYER                                    │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │ │
│  │  │ Input Validator │  │    Injection    │  │ Output Validator│        │ │
│  │  │                 │  │    Detector     │  │                 │        │ │
│  │  │ • Length check  │  │                 │  │ • Format check  │        │ │
│  │  │ • Scope check   │  │ • 28 patterns   │  │ • Confidence    │        │ │
│  │  │ • Encoding      │  │ • 4 severity    │  │ • Hallucination │        │ │
│  │  │                 │  │   levels        │  │   markers       │        │ │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘        │ │
│  │           └───────────────────┬┴───────────────────┘                   │ │
│  │                               ▼                                        │ │
│  │                    ┌─────────────────────┐                             │ │
│  │                    │     Guardrails      │                             │ │
│  │                    │  (Query Templates)  │                             │ │
│  │                    └──────────┬──────────┘                             │ │
│  └───────────────────────────────┼────────────────────────────────────────┘ │
│                                  ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    RETRIEVAL & MEMORY LAYER                             │ │
│  │                                                                         │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                    HYBRID RETRIEVER                               │  │ │
│  │  │                                                                   │  │ │
│  │  │   Query ──┬──▶ BM25 Search ──────────┐                           │  │ │
│  │  │           │    (Keyword matching)     │                           │  │ │
│  │  │           │                           ├──▶ RRF Merge ──▶ Results  │  │ │
│  │  │           └──▶ Embedding Search ──────┘    (Reciprocal            │  │ │
│  │  │                (Semantic similarity)        Rank Fusion)          │  │ │
│  │  │                                                                   │  │ │
│  │  │   Alpha: 0.0 (BM25 only) ◀────────────▶ 1.0 (Embeddings only)    │  │ │
│  │  │                     Default: 0.5 (Balanced)                       │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                  │                                      │ │
│  │                                  ▼                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                    THREE-TIER MEMORY                              │  │ │
│  │  │                                                                   │  │ │
│  │  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐     │  │ │
│  │  │  │   SHORT-TERM    │ │     WORKING     │ │    LONG-TERM    │     │  │ │
│  │  │  │                 │ │                 │ │                 │     │  │ │
│  │  │  │ • Current       │ │ • 7-day         │ │ • Permanent     │     │  │ │
│  │  │  │   session       │ │   retention     │ │   patterns      │     │  │ │
│  │  │  │ • In-memory     │ │ • SQLite-backed │ │ • JSON file     │     │  │ │
│  │  │  │ • 50 items max  │ │ • Frequently    │ │ • All validated │     │  │ │
│  │  │  │ • LRU eviction  │ │   accessed      │ │   patterns      │     │  │ │
│  │  │  │                 │ │                 │ │                 │     │  │ │
│  │  │  │ Weight: 1.5x    │ │ Weight: 1.2x    │ │ Weight: 1.0x    │     │  │ │
│  │  │  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘     │  │ │
│  │  │           │                   │                   │              │  │ │
│  │  │           │    PROMOTION      │    PROMOTION      │              │  │ │
│  │  │           │    ───────▶       │    ───────▶       │              │  │ │
│  │  │           │  (3+ accesses     │  (10+ accesses    │              │  │ │
│  │  │           │   OR outcome)     │   AND success)    │              │  │ │
│  │  │           │                   │                   │              │  │ │
│  │  └───────────┴───────────────────┴───────────────────┴──────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                  │                                          │
│                                  ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         LEARNING LAYER                                  │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │ │
│  │  │  AI-as-a-Judge  │  │    Implicit     │  │  Data Quality   │        │ │
│  │  │                 │  │    Feedback     │  │   Framework     │        │ │
│  │  │ • Claude Haiku  │  │                 │  │                 │        │ │
│  │  │ • 1-5 scoring   │  │ • Follows       │  │ • Completeness  │        │ │
│  │  │ • 5 dimensions: │  │ • Ignores       │  │ • Consistency   │        │ │
│  │  │   - Relevance   │  │ • Overrides     │  │ • Accuracy      │        │ │
│  │  │   - Clarity     │  │ • Time-to-      │  │ • Timeliness    │        │ │
│  │  │   - Accuracy    │  │   action        │  │ • Uniqueness    │        │ │
│  │  │   - Actionable  │  │                 │  │ • Validity      │        │ │
│  │  │   - Timeliness  │  │ 10-100x more    │  │                 │        │ │
│  │  │                 │  │ signal than     │  │ Overall: 86.4%  │        │ │
│  │  │                 │  │ explicit        │  │                 │        │ │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘        │ │
│  │           └───────────────────┬┴───────────────────┘                   │ │
│  │                               ▼                                        │ │
│  │                    ┌─────────────────────┐                             │ │
│  │                    │   Learning System   │                             │ │
│  │                    │ (Quality-Weighted)  │                             │ │
│  │                    └─────────────────────┘                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Intelligence Query Flow

When a query enters Cortex, it flows through these stages:

```
User Query
    │
    ▼
┌───────────────────────────────────┐
│  1. DEFENSIVE PROMPTING           │
│     • Validate input length       │
│     • Check for injection         │
│     • Validate scope              │
│     • Apply guardrails            │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  2. CONTEXT OPTIMIZATION          │
│     • Identify critical info      │
│     • Place at START/END          │
│     • Middle = supplementary      │
│     • Lost-in-middle mitigation   │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  3. HYBRID RETRIEVAL              │
│     • BM25 keyword search         │
│     • Embedding similarity        │
│     • RRF merge (alpha=0.5)       │
│     • Return ranked results       │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  4. TIERED MEMORY QUERY           │
│     • Search short-term (1.5x)    │
│     • Search working (1.2x)       │
│     • Search long-term (1.0x)     │
│     • Deduplicate and rank        │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  5. QUALITY EVALUATION            │
│     • AI-as-Judge scoring         │
│     • Filter by confidence        │
│     • Add quality metadata        │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  6. OUTPUT VALIDATION             │
│     • Check format                │
│     • Verify confidence           │
│     • Detect hallucination        │
│     • Return clean response       │
└───────────────┬───────────────────┘
                │
                ▼
           Response
```

---

## Feedback Loop

Cortex learns from user behavior through implicit and explicit signals:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FEEDBACK LOOP                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                    ┌─────────────────┐                                   │
│                    │ Recommendation  │                                   │
│                    │    Shown        │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│                             ▼                                            │
│            ┌────────────────────────────────┐                           │
│            │  ImplicitFeedbackCollector     │                           │
│            │  track_recommendation_shown()   │                           │
│            └────────────────┬───────────────┘                           │
│                             │                                            │
│                             ▼                                            │
│                    ┌─────────────────┐                                   │
│                    │  User Action    │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│                             ▼                                            │
│            ┌────────────────────────────────┐                           │
│            │  ImplicitFeedbackCollector     │                           │
│            │  track_action_taken()          │                           │
│            └────────────────┬───────────────┘                           │
│                             │                                            │
│              ┌──────────────┼──────────────┐                            │
│              ▼              ▼              ▼                             │
│      ┌───────────┐  ┌───────────┐  ┌───────────┐                        │
│      │  FOLLOWED │  │ OVERRIDDEN│  │  IGNORED  │                        │
│      │           │  │           │  │           │                        │
│      │ Similarity│  │ Similarity│  │ Similarity│                        │
│      │   > 0.7   │  │ 0.3 - 0.7 │  │   < 0.3   │                        │
│      │           │  │           │  │           │                        │
│      │ +1 signal │  │ Modified  │  │ -1 signal │                        │
│      └─────┬─────┘  └─────┬─────┘  └─────┬─────┘                        │
│            └──────────────┼──────────────┘                              │
│                           ▼                                              │
│            ┌────────────────────────────────┐                           │
│            │      Learning System           │                           │
│            │  (Quality-Weighted Updates)    │                           │
│            └────────────────┬───────────────┘                           │
│                             │                                            │
│                             ▼                                            │
│            ┌────────────────────────────────┐                           │
│            │    Pattern Confidence          │                           │
│            │    Adjustment                  │                           │
│            └────────────────────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Memory Promotion Flow

Items are promoted through tiers based on access patterns and outcomes:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MEMORY PROMOTION FLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  New Item                                                                │
│      │                                                                   │
│      ▼                                                                   │
│  ┌─────────────────┐                                                     │
│  │   SHORT-TERM    │  Criteria: Any new item                            │
│  │   (Session)     │  Storage: In-memory                                │
│  │                 │  Capacity: 50 items (LRU eviction)                 │
│  │   Weight: 1.5x  │                                                     │
│  └────────┬────────┘                                                     │
│           │                                                              │
│           │  Promotion Criteria:                                         │
│           │  • Accessed 3+ times, OR                                     │
│           │  • Has any outcome recorded                                  │
│           ▼                                                              │
│  ┌─────────────────┐                                                     │
│  │    WORKING      │  Criteria: Frequently accessed OR has outcome      │
│  │   (7 days)      │  Storage: SQLite database                          │
│  │                 │  Retention: 7 days (auto-cleanup)                  │
│  │   Weight: 1.2x  │                                                     │
│  └────────┬────────┘                                                     │
│           │                                                              │
│           │  Promotion Criteria:                                         │
│           │  • Accessed 10+ times, AND                                   │
│           │  • Consistent success outcomes                               │
│           ▼                                                              │
│  ┌─────────────────┐                                                     │
│  │   LONG-TERM     │  Criteria: Proven success over time                │
│  │  (Permanent)    │  Storage: patterns.json                            │
│  │                 │  Retention: Permanent                              │
│  │   Weight: 1.0x  │                                                     │
│  └─────────────────┘                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Prompt Versioning System

All prompts are stored as versioned YAML templates:

```
cortex/prompts/
├── versions/
│   └── v1/
│       ├── briefing.yaml         # Daily briefing generation
│       ├── recommendation.yaml   # Recommendation generation
│       ├── evaluation.yaml       # AI-as-Judge scoring
│       ├── pattern_match.yaml    # Pattern retrieval
│       └── bridge_context.yaml   # Context queries
├── base.py                       # PromptTemplate class
├── registry.py                   # Template loading and caching
└── ab_testing.py                 # A/B testing framework
```

**Template Structure:**
```yaml
name: briefing_generation
version: "1.0.0"
description: "Generate daily briefing from project context"
template: |
  You are Cortex, an AI assistant helping with software development.

  Current date: {date}
  Projects: {projects}
  Recent activity: {activity}

  Generate a concise briefing...
variables:
  - date
  - projects
  - activity
metadata:
  author: "cortex-team"
  usage_count: 0
  avg_quality_score: null
```

---

## Safety Module Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SAFETY MODULE                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  intelligence/safety/                                                    │
│  ├── __init__.py           # Public API exports                         │
│  ├── injection_detector.py # 28 detection patterns                      │
│  ├── validators.py         # Input/Output validation                    │
│  ├── guardrails.py         # Query templates                            │
│  └── README.md             # Usage documentation                        │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    INJECTION DETECTOR                               │ │
│  │                                                                     │ │
│  │  Severity Levels:                                                   │ │
│  │                                                                     │ │
│  │  CRITICAL (4 patterns)                                              │ │
│  │  • "ignore all previous instructions"                               │ │
│  │  • "disregard your rules"                                           │ │
│  │  • "forget everything"                                              │ │
│  │  • "new instructions:"                                              │ │
│  │                                                                     │ │
│  │  HIGH (9 patterns)                                                  │ │
│  │  • "you are now a different AI"                                     │ │
│  │  • "reveal your prompt"                                             │ │
│  │  • "pretend you are"                                                │ │
│  │  • ...                                                              │ │
│  │                                                                     │ │
│  │  MEDIUM (13 patterns)                                               │ │
│  │  • "developer mode"                                                 │ │
│  │  • "without restrictions"                                           │ │
│  │  • Special tokens: [INST], <|im_start|>                            │ │
│  │  • ...                                                              │ │
│  │                                                                     │ │
│  │  LOW (2 patterns)                                                   │ │
│  │  • "override mode"                                                  │ │
│  │  • "change your behavior"                                           │ │
│  │                                                                     │ │
│  │  Performance: <0.5ms per query (compiled regex)                     │ │
│  │  False Positive Rate: 0% on legitimate queries                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  Security logs: ~/.cortex/security.log (JSONL format)                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Quality Dimensions

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATA QUALITY FRAMEWORK                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      SIX DIMENSIONS                                │  │
│  │                                                                    │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │  │
│  │  │COMPLETENESS │ │ CONSISTENCY │ │  ACCURACY   │                 │  │
│  │  │             │ │             │ │             │                 │  │
│  │  │ Required    │ │ No contra-  │ │ Factually   │                 │  │
│  │  │ fields      │ │ dictions    │ │ correct     │                 │  │
│  │  │ present     │ │             │ │             │                 │  │
│  │  │             │ │             │ │             │                 │  │
│  │  │ Score: 100% │ │ Score: 100% │ │ Score: 100% │                 │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                 │  │
│  │                                                                    │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │  │
│  │  │ TIMELINESS  │ │ UNIQUENESS  │ │  VALIDITY   │                 │  │
│  │  │             │ │             │ │             │                 │  │
│  │  │ Data        │ │ No          │ │ Format/     │                 │  │
│  │  │ freshness   │ │ duplicates  │ │ schema      │                 │  │
│  │  │             │ │             │ │ valid       │                 │  │
│  │  │             │ │             │ │             │                 │  │
│  │  │ Score: 15%  │ │ Score: 91%  │ │ Score: 100% │                 │  │
│  │  │ (ADDRESSED) │ │             │ │             │                 │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                 │  │
│  │                                                                    │  │
│  │  Overall Quality: 86.4% (on 57 production outcomes)               │  │
│  │                                                                    │  │
│  │  Note: Timeliness issue (15%) addressed by Three-Tier Memory      │  │
│  │  which now prioritizes recent data with 1.5x weight               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File System Layout

```
~/.cortex/                          # User data directory
├── patterns/
│   ├── patterns.json               # Long-term patterns
│   └── embeddings.pkl              # Cached embeddings
├── working_memory.db               # SQLite working memory
├── outcomes.jsonl                  # Outcome log
├── implicit_feedback.jsonl         # Feedback signals
├── evaluations.jsonl               # AI-as-Judge scores
├── security.log                    # Injection attempts
└── logs/                           # Application logs
```

---

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| Bridge initialization | 6.8ms | 99.5% faster than 1s target |
| Portfolio stats query | <1ms | 99.1% faster than target |
| Hybrid retrieval (cached) | 0.05ms | First search ~100ms |
| Tiered memory query | <50ms | Weighted merge |
| Input validation | <1ms | Compiled regex |
| Injection detection | <0.5ms | 28 patterns |
| AI-as-Judge evaluation | <500ms | Claude Haiku |
| Quality assessment | ~1ms | Per item |

---

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Tiered Memory | 31 | 100% passing |
| Context Optimizer | 26 | 100% passing |
| Hybrid Retriever | 17 | 100% passing |
| Quality Judge | 23 | 100% passing |
| Implicit Feedback | 28 | 100% passing |
| Data Quality | 28 | 100% passing |
| Safety | 22 | 100% passing |
| Prompts | 32 | 100% passing |
| **Total** | **449** | **99.8%** |

---

## Integration Points

### VortexV2 (Weather Forecasting)
- Tracks 47 ensemble model experiments
- Provides pattern recommendations for GRIB processing
- Feeds validation outcomes into learning system

### Alpha Arena (Trading)
- Tracks 23 strategy experiments
- Provides recommendations for model competition
- Feeds trade outcomes into learning system

### Claude Code / CLI
- Universal bridge interface
- Plugin system for custom commands
- Daily briefing generation

---

## Configuration Reference

```python
# cortex/config.py

# Feature flags
prompt_versioning_enabled: bool = True
data_quality_enabled: bool = True
defensive_prompting_enabled: bool = True
quality_weighting_enabled: bool = True

# Memory settings
short_term_capacity: int = 50
working_memory_retention_days: int = 7

# Retrieval settings
hybrid_alpha: float = 0.5  # 0.0 = BM25 only, 1.0 = embeddings only

# Safety settings
max_query_length: int = 10000
min_confidence_threshold: float = 0.3
```

---

**See Also:**
- [README.md](../README.md) - Quick start and overview
- [API.md](API.md) - Bridge API reference
- [AI_ENGINEERING_IMPROVEMENTS_PRD.md](AI_ENGINEERING_IMPROVEMENTS_PRD.md) - Full implementation spec
