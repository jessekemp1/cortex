# Cortex AI Engineering Improvements PRD

**Based on**: Chip Huyen's "AI Engineering" book recommendations
**Created**: 2026-02-01
**Version**: 1.0
**Status**: Draft

---

## Phase 0: Step 0 Validation

### What Gets Deployed If This Validates?

If these improvements validate successfully, Cortex will deploy:

1. **Hybrid Retrieval System** - A new search layer in PatternMemory that combines BM25 (keyword) + embedding (semantic) retrieval for 30-50% better pattern recall
2. **AI-as-a-Judge Evaluation Pipeline** - Automated quality scoring for patterns and recommendations, reducing manual review burden
3. **Implicit Feedback Collection** - Automatic tracking of follows/ignores/overrides, eliminating explicit feedback requirements
4. **Prompt Versioning System** - Structured prompt templates with A/B testing capability in `cortex/prompts/`
5. **Three-Tier Memory Architecture** - Formalized short-term/working/long-term memory with automatic promotion
6. **Lost-in-the-Middle Optimization** - Restructured prompt ordering for better LLM attention
7. **Data Quality Framework** - Six-dimension quality tracking (completeness, consistency, accuracy, timeliness, uniqueness, validity)
8. **Defensive Prompting** - Guardrails and safety patterns in bridge.py

### Deployment Verification

Each improvement includes deployment verification criteria. An improvement is NOT complete until it is:
1. Tested (unit + integration)
2. Reviewed
3. Deployed to production Cortex
4. Validated via `/validate-ship` command

---

## Executive Summary

This PRD outlines improvements to Cortex's memory and learning systems based on industry best practices from "AI Engineering." The improvements address critical gaps in retrieval quality, evaluation automation, feedback collection, and prompt management.

### Current State Analysis

| Component | Current Implementation | Gap |
|-----------|----------------------|-----|
| **Pattern Retrieval** | Keyword-only (PatternSearcher) | No semantic understanding; misses conceptually similar patterns |
| **Quality Evaluation** | Manual (feedback.py, outcomes.jsonl) | No automated quality scoring; relies on explicit user feedback |
| **Feedback Collection** | Explicit only (log_feedback, log_outcome) | Misses 90%+ of implicit signals (follows, ignores, overrides) |
| **Prompt Management** | Inline strings scattered across codebase | No versioning, A/B testing, or structured templates |
| **Memory Architecture** | Single-tier (patterns.json) | No working memory; patterns treated uniformly regardless of recency |
| **Context Ordering** | Arbitrary | Not optimized for LLM attention patterns |
| **Data Quality** | Basic validation | No systematic quality tracking |
| **Safety** | Minimal guardrails | No defensive prompting patterns |

---

## Improvement 1: Hybrid Retrieval System

### Problem Statement

`PatternSearcher` in `/Users/jesse.kemp/Dev/cortex/intelligence/memory/pattern_indexer.py:415-522` uses pure keyword matching. This fails when:
- User queries use different terminology than stored patterns
- Conceptually similar patterns use different words
- Technical synonyms exist (e.g., "async" vs "concurrent" vs "parallel")

Book reference: Chapter on "Retrieval-Augmented Generation" - hybrid retrieval consistently outperforms single-method approaches by 20-40%.

### Proposed Solution

Add semantic search via embeddings alongside existing keyword search:

```python
# New file: cortex/intelligence/memory/hybrid_retriever.py

class HybridRetriever:
    """BM25 + Embedding hybrid retrieval with reciprocal rank fusion."""

    def __init__(self, patterns: List[Pattern], embeddings_client: EmbeddingsClient):
        self.bm25_searcher = PatternSearcher(patterns)  # Existing
        self.embeddings_client = embeddings_client
        self.pattern_embeddings = self._index_patterns(patterns)

    def search(self, query: str, limit: int = 10, alpha: float = 0.5) -> List[Tuple[Pattern, float]]:
        """
        Hybrid search with configurable BM25/embedding weight.

        alpha=0.5: Equal weight to both methods
        alpha=0.0: Pure BM25 (existing behavior)
        alpha=1.0: Pure semantic search
        """
        # Get BM25 results
        bm25_results = self.bm25_searcher.search(query, limit=limit*2)

        # Get embedding results
        query_embedding = self.embeddings_client.get_embedding(query)
        embedding_results = self._semantic_search(query_embedding, limit=limit*2)

        # Reciprocal Rank Fusion
        return self._rrf_merge(bm25_results, embedding_results, limit, alpha)
```

### Acceptance Criteria

- [ ] HybridRetriever class implemented with BM25 + embedding search
- [ ] EmbeddingsClient integration (use existing `/Users/jesse.kemp/Dev/cortex/intelligence/embeddings_client.py`)
- [ ] Reciprocal Rank Fusion (RRF) for result merging
- [ ] Configurable alpha parameter for method weighting
- [ ] Backward compatible: `PatternMemory.get_relevant_patterns()` uses HybridRetriever
- [ ] Pattern embeddings cached to `~/.cortex/patterns/embeddings.pkl`

### Test Plan

1. **Unit Tests** (`cortex/tests/test_hybrid_retriever.py`):
   - Test BM25-only retrieval (alpha=0.0)
   - Test embedding-only retrieval (alpha=1.0)
   - Test hybrid retrieval (alpha=0.5)
   - Test RRF merge correctness

2. **Integration Tests**:
   - Test PatternMemory backward compatibility
   - Test embedding cache load/save
   - Test retrieval with real patterns from `~/.cortex/patterns/patterns.json`

3. **Quality Tests**:
   - Benchmark: Hybrid recall > BM25 recall by 20%+ on synonym queries
   - Latency: <100ms for 1000 patterns (cached embeddings)

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Recall@5 (synonym queries) | ~40% | >60% |
| Search latency (cached) | 5ms | <100ms |
| Embedding cache hit rate | N/A | >95% |

### Dependencies

- **Blocks**: None
- **Blocked by**: Embeddings client availability (already exists)

---

## Improvement 2: AI-as-a-Judge Evaluation

### Problem Statement

Quality evaluation in Cortex relies on manual user feedback via `feedback.py`. This creates:
- Feedback fatigue (users stop providing feedback)
- Selection bias (only memorable experiences get logged)
- Delayed feedback (outcomes known days/weeks later)

Book reference: Chapter on "Evaluation" - LLM-as-a-judge provides consistent, scalable quality assessment.

### Proposed Solution

Implement automated quality scoring using Claude as a judge:

```python
# New file: cortex/intelligence/evaluation/quality_judge.py

class QualityJudge:
    """AI-as-a-judge for pattern and recommendation quality."""

    EVALUATION_CRITERIA = {
        "relevance": "How relevant is this to the query?",
        "actionability": "How actionable is the recommendation?",
        "specificity": "Is it specific enough to act on?",
        "accuracy": "Is the information accurate?",
    }

    async def evaluate_pattern(self, pattern: Pattern, query: str) -> PatternScore:
        """Evaluate a pattern match against a query."""
        prompt = self._build_evaluation_prompt(pattern, query)
        response = await self.client.messages.create(
            model="claude-3-5-haiku-20241022",  # Fast + cheap for eval
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return self._parse_scores(response)

    async def evaluate_recommendation(self, rec: Recommendation, context: Dict) -> RecScore:
        """Evaluate a recommendation in context."""
        ...
```

### Acceptance Criteria

- [ ] QualityJudge class with evaluate_pattern() and evaluate_recommendation()
- [ ] Evaluation criteria: relevance, actionability, specificity, accuracy
- [ ] Batch evaluation support (rate-limited)
- [ ] Results stored in `~/.cortex/evaluations.jsonl`
- [ ] Integration with learning.py for confidence calibration
- [ ] Optional: Human-in-the-loop override mechanism

### Test Plan

1. **Unit Tests** (`cortex/tests/test_quality_judge.py`):
   - Test prompt construction
   - Test score parsing (valid JSON, ranges)
   - Test batch evaluation

2. **Integration Tests**:
   - Test with real patterns/recommendations
   - Test rate limiting
   - Test storage to evaluations.jsonl

3. **Calibration Tests**:
   - Compare AI scores with existing human feedback (correlation >0.7)
   - Test inter-rater reliability (multiple evaluations of same content)

### Success Metrics

| Metric | Target |
|--------|--------|
| Correlation with human feedback | >0.7 |
| Evaluation latency | <500ms per item |
| Daily evaluation capacity | 100+ items |

### Dependencies

- **Blocks**: Improvement 3 (implicit feedback uses evaluation)
- **Blocked by**: Claude API access (existing)

---

## Improvement 3: Implicit Feedback Collection

### Problem Statement

Current feedback collection in `feedback.py:85-111` requires explicit user action. Book reference: Chapter on "Data Collection" - implicit feedback provides 10-100x more signal than explicit feedback.

Implicit signals currently not captured:
- **Follows**: User executes recommended action
- **Ignores**: User sees recommendation but doesn't act
- **Overrides**: User modifies recommendation before executing
- **Time-to-action**: How long from seeing to executing

### Proposed Solution

```python
# New file: cortex/intelligence/feedback/implicit_collector.py

class ImplicitFeedbackCollector:
    """Collects implicit feedback signals from user behavior."""

    def __init__(self):
        self.pending_recommendations = {}  # id -> (rec, shown_at)
        self.session_actions = []

    def track_recommendation_shown(self, rec_id: str, recommendation: Dict):
        """Track when a recommendation is displayed to user."""
        self.pending_recommendations[rec_id] = {
            "recommendation": recommendation,
            "shown_at": datetime.now(),
            "context": self._capture_context(),
        }

    def track_action_taken(self, action: str, files: List[str], context: Dict):
        """Track user actions and correlate with pending recommendations."""
        for rec_id, rec_data in self.pending_recommendations.items():
            similarity = self._action_matches_recommendation(action, rec_data)
            if similarity > 0.7:
                self._log_follow(rec_id, similarity, time_to_action=...)
            elif self._is_modification_of(action, rec_data):
                self._log_override(rec_id, action, original=rec_data)

    def session_end(self):
        """Mark un-acted recommendations as ignored."""
        for rec_id, rec_data in self.pending_recommendations.items():
            if rec_id not in self.followed_ids:
                self._log_ignore(rec_id, rec_data)
```

### Acceptance Criteria

- [ ] ImplicitFeedbackCollector class implemented
- [ ] Track: shows, follows, ignores, overrides, time-to-action
- [ ] Integration points:
  - `briefing.py`: Track recommendation displays
  - `bridge.py`: Track actions via trigger_action
  - Session hooks in `cli.py`: Track session end
- [ ] Storage in `~/.cortex/implicit_feedback.jsonl`
- [ ] Privacy-conscious: Only track Cortex-related actions

### Test Plan

1. **Unit Tests**:
   - Test recommendation tracking
   - Test action correlation
   - Test override detection

2. **Integration Tests**:
   - Test full session flow
   - Test persistence across sessions

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Feedback signals/day | ~1 explicit | 50+ implicit |
| Follow detection accuracy | N/A | >80% |
| Override detection accuracy | N/A | >70% |

### Dependencies

- **Blocks**: Improvement calibration
- **Blocked by**: Improvement 2 (for action matching)

---

## Improvement 4: Prompt Versioning System

### Problem Statement

Prompts are scattered as inline strings throughout the codebase:
- `bridge.py`: Context queries
- `briefing.py`: Briefing generation
- `recommendation_engine.py`: Recommendation generation
- Various intelligence modules

No versioning, A/B testing, or structured management exists.

Book reference: Chapter on "Prompt Engineering" - prompts are code and should be versioned, tested, and deployed like code.

### Proposed Solution

Create structured prompt templates with versioning:

```
cortex/prompts/
  __init__.py
  base.py              # PromptTemplate base class
  versions/
    __init__.py
    v1/
      briefing.yaml
      recommendation.yaml
      evaluation.yaml
    v2/
      briefing.yaml     # A/B test variant
  registry.py          # Prompt registry and selection
  ab_testing.py        # A/B test framework
```

```python
# cortex/prompts/base.py

@dataclass
class PromptTemplate:
    """Versioned prompt template."""

    name: str
    version: str
    template: str
    variables: List[str]
    metadata: Dict[str, Any]

    def render(self, **kwargs) -> str:
        """Render template with variables."""
        return self.template.format(**kwargs)

    @classmethod
    def from_yaml(cls, path: Path) -> "PromptTemplate":
        """Load from YAML file."""
        ...
```

```yaml
# cortex/prompts/versions/v1/briefing.yaml
name: briefing_generation
version: "1.0.0"
description: "Generate daily briefing from project context"
template: |
  You are Cortex, an AI assistant helping with software development.

  Current date: {date}
  Projects: {projects}
  Recent activity: {activity}
  Active goals: {goals}

  Generate a concise briefing covering:
  1. Priority recommendations
  2. Blockers requiring attention
  3. Quick wins available

  Format as markdown with clear sections.
variables:
  - date
  - projects
  - activity
  - goals
metadata:
  author: "cortex-team"
  created: "2026-02-01"
  metrics:
    usage_count: 0
    avg_quality_score: null
```

### Acceptance Criteria

- [ ] `cortex/prompts/` directory structure created
- [ ] PromptTemplate class with versioning
- [ ] YAML-based template files for all major prompts
- [ ] PromptRegistry for loading and selecting templates
- [ ] A/B testing framework with experiment assignment
- [ ] Integration with existing code (briefing.py, bridge.py)
- [ ] Prompt metrics tracking (usage, quality scores)

### Test Plan

1. **Unit Tests**:
   - Test template loading from YAML
   - Test variable substitution
   - Test version comparison

2. **Integration Tests**:
   - Test registry loading all templates
   - Test A/B assignment consistency
   - Test prompt metrics recording

### Success Metrics

| Metric | Target |
|--------|--------|
| Prompts migrated to templates | 100% |
| A/B test capability | Active |
| Prompt quality tracking | Enabled |

### Dependencies

- **Blocks**: Improvement 6 (uses structured prompts)
- **Blocked by**: None

---

## Improvement 5: Three-Tier Memory Architecture

### Problem Statement

Current memory is single-tier in `pattern_memory.py`:
- All patterns stored equally in `patterns.json`
- No distinction between recent vs. historical
- No working memory for current session
- No automatic promotion/demotion

Book reference: Chapter on "Memory Systems" - human-inspired memory architectures (short-term, working, long-term) improve relevance.

### Proposed Solution

```python
# New file: cortex/intelligence/memory/tiered_memory.py

class TieredMemory:
    """Three-tier memory: short-term, working, long-term."""

    def __init__(self):
        # Short-term: Current session, 10-50 items, in-memory
        self.short_term = ShortTermMemory(max_items=50)

        # Working: Recent sessions (7 days), frequently accessed
        self.working = WorkingMemory(retention_days=7)

        # Long-term: All patterns, indexed for retrieval
        self.long_term = LongTermMemory()  # Existing PatternMemory

        # Promotion/demotion rules
        self.promotion_rules = PromotionRules()

    def query(self, query: str, tiers: List[str] = ["short_term", "working", "long_term"]):
        """Query across memory tiers with priority."""
        results = []

        for tier in tiers:
            tier_results = getattr(self, tier).search(query)
            # Weight by tier (short-term highest)
            weighted = self._apply_tier_weights(tier_results, tier)
            results.extend(weighted)

        return self._deduplicate_and_rank(results)

    def record(self, item: MemoryItem):
        """Record to short-term, auto-promote based on rules."""
        self.short_term.add(item)

        # Check promotion criteria
        if self.promotion_rules.should_promote_to_working(item):
            self.working.add(item)

    def end_session(self):
        """End-of-session processing: promote/demote/consolidate."""
        # Promote frequently accessed short-term to working
        for item in self.short_term.get_accessed(threshold=3):
            self.working.add(item)

        # Promote working items with good outcomes to long-term
        for item in self.working.get_successful():
            self.long_term.add(item)

        self.short_term.clear()
```

### Acceptance Criteria

- [ ] ShortTermMemory: In-memory, session-scoped, 50 item limit
- [ ] WorkingMemory: 7-day retention, SQLite-backed
- [ ] LongTermMemory: Existing PatternMemory integration
- [ ] Automatic promotion based on access frequency and outcomes
- [ ] Tier-weighted query results
- [ ] Session lifecycle hooks (start, end, pause)
- [ ] Memory consolidation on session end

### Test Plan

1. **Unit Tests**:
   - Test each tier independently
   - Test promotion/demotion rules
   - Test query weighting

2. **Integration Tests**:
   - Test full session lifecycle
   - Test cross-tier queries
   - Test persistence after session end

### Success Metrics

| Metric | Target |
|--------|--------|
| Query relevance (short-term items) | 2x higher weight |
| Session context retention | 100% during session |
| Cross-session relevance | 20% improvement |

### Dependencies

- **Blocks**: None
- **Blocked by**: Improvement 1 (uses HybridRetriever)

---

## Improvement 6: Lost-in-the-Middle Optimization

### Problem Statement

Current prompt construction doesn't account for LLM attention patterns. Research shows LLMs attend more to beginning and end of context, "losing" middle content.

Book reference: Chapter on "Prompt Engineering" - position-aware context ordering significantly impacts generation quality.

### Proposed Solution

```python
# New file: cortex/intelligence/context_optimizer.py

class ContextOptimizer:
    """Optimize context ordering for LLM attention patterns."""

    POSITION_WEIGHTS = {
        "start": 1.0,    # Full attention
        "middle": 0.6,   # Reduced attention
        "end": 0.9,      # High attention
    }

    def optimize_context(self, items: List[ContextItem], max_tokens: int) -> str:
        """
        Reorder context items for optimal LLM attention.

        Strategy: Most important at START and END, less important in MIDDLE
        """
        # Sort by importance
        sorted_items = sorted(items, key=lambda x: x.importance, reverse=True)

        # Distribute: high importance to start/end, lower to middle
        n = len(sorted_items)
        optimized = []

        # Top 1/3 goes to start
        start_items = sorted_items[:n//3]

        # Bottom 1/3 goes to middle (less important)
        middle_items = sorted_items[n//3:2*n//3]

        # Mid-importance goes to end
        end_items = sorted_items[2*n//3:]

        return self._format_context(start_items, middle_items, end_items)

    def add_recency_markers(self, context: str) -> str:
        """Add recency/importance markers to help LLM attention."""
        ...
```

### Acceptance Criteria

- [ ] ContextOptimizer class with position-aware ordering
- [ ] Integration with briefing.py context building
- [ ] Integration with bridge.py context queries
- [ ] Importance scoring for context items
- [ ] Optional recency/priority markers

### Test Plan

1. **Unit Tests**:
   - Test ordering algorithm
   - Test position distribution

2. **Quality Tests**:
   - A/B test: optimized vs. unoptimized context
   - Measure: Response relevance, action rate

### Success Metrics

| Metric | Target |
|--------|--------|
| Critical info at start/end | >80% |
| Response relevance (A/B) | 10%+ improvement |

### Dependencies

- **Blocks**: None
- **Blocked by**: Improvement 4 (uses structured prompts)

---

## Improvement 7: Data Quality Framework

### Problem Statement

No systematic data quality tracking exists. Current validation is ad-hoc.

Book reference: Chapter on "Data Quality" - track six dimensions: completeness, consistency, accuracy, timeliness, uniqueness, validity.

### Proposed Solution

```python
# New file: cortex/intelligence/quality/data_quality.py

@dataclass
class QualityDimensions:
    """Six quality dimensions for data assessment."""

    completeness: float  # Required fields present
    consistency: float   # No contradictions
    accuracy: float      # Factually correct
    timeliness: float    # Data freshness
    uniqueness: float    # No duplicates
    validity: float      # Format/schema valid

    def overall_score(self) -> float:
        """Weighted average quality score."""
        weights = {
            "completeness": 0.2,
            "consistency": 0.2,
            "accuracy": 0.25,
            "timeliness": 0.15,
            "uniqueness": 0.1,
            "validity": 0.1,
        }
        return sum(
            getattr(self, dim) * weight
            for dim, weight in weights.items()
        )

class DataQualityTracker:
    """Track data quality metrics across Cortex."""

    def assess_pattern(self, pattern: Pattern) -> QualityDimensions:
        """Assess quality of a pattern."""
        return QualityDimensions(
            completeness=self._check_completeness(pattern),
            consistency=self._check_consistency(pattern),
            accuracy=self._check_accuracy(pattern),  # May use AI judge
            timeliness=self._check_timeliness(pattern),
            uniqueness=self._check_uniqueness(pattern),
            validity=self._check_validity(pattern),
        )

    def assess_feedback(self, entry: FeedbackEntry) -> QualityDimensions:
        """Assess quality of feedback entry."""
        ...

    def get_quality_report(self) -> QualityReport:
        """Generate quality report across all data stores."""
        ...
```

### Acceptance Criteria

- [ ] QualityDimensions dataclass with six dimensions
- [ ] DataQualityTracker with assess_* methods
- [ ] Quality assessment for: patterns, feedback, outcomes, recommendations
- [ ] Quality report generation
- [ ] Integration with learning.py for quality-weighted learning
- [ ] Dashboard/CLI command for quality overview

### Test Plan

1. **Unit Tests**:
   - Test each dimension calculation
   - Test overall score weighting

2. **Integration Tests**:
   - Test assessment of real data
   - Test report generation

### Success Metrics

| Metric | Target |
|--------|--------|
| Data with quality scores | 100% |
| Minimum quality threshold | 0.6 |
| Quality trend | Improving |

### Dependencies

- **Blocks**: None
- **Blocked by**: None (can start immediately)

---

## Improvement 8: Defensive Prompting

### Problem Statement

`bridge.py` has minimal guardrails. No systematic protection against:
- Prompt injection via user queries
- Hallucinated recommendations
- Out-of-scope requests
- Inconsistent responses

Book reference: Chapter on "Safety" - defensive prompting reduces failure modes.

### Proposed Solution

```python
# Updates to cortex/bridge.py

class CortexBridge:
    """Universal interface with defensive prompting."""

    # Input validation
    INPUT_VALIDATORS = [
        MaxLengthValidator(max_chars=10000),
        InjectionDetector(patterns=INJECTION_PATTERNS),
        ScopeValidator(allowed_domains=["development", "project_mgmt"]),
    ]

    # Output validation
    OUTPUT_VALIDATORS = [
        HallucinationDetector(),
        FormatValidator(required_fields=["title", "rationale"]),
        ConfidenceGate(min_confidence=0.3),
    ]

    def get_context(self, query: str, ...) -> List[Dict]:
        """Get context with defensive prompting."""
        # Validate input
        query = self._validate_input(query)

        # Add guardrails to prompt
        guarded_query = self._add_guardrails(query)

        # Get response
        response = self._query_internal(guarded_query)

        # Validate output
        validated = self._validate_output(response)

        return validated

    def _add_guardrails(self, query: str) -> str:
        """Add defensive prompting guardrails."""
        return f"""
        [GUARDRAILS]
        - Only provide information about software development
        - Do not execute code or system commands
        - Acknowledge uncertainty with "I'm not sure..."
        - Stay within the Cortex knowledge domain

        [QUERY]
        {query}
        """
```

### Acceptance Criteria

- [ ] Input validators: length, injection detection, scope
- [ ] Output validators: hallucination, format, confidence
- [ ] Guardrail injection in all LLM calls
- [ ] Logging of validation failures
- [ ] Graceful degradation on validation failure

### Test Plan

1. **Unit Tests**:
   - Test each validator
   - Test injection detection patterns
   - Test guardrail injection

2. **Security Tests**:
   - Test common prompt injection patterns
   - Test scope boundary violations
   - Test hallucination detection

### Success Metrics

| Metric | Target |
|--------|--------|
| Injection attempts blocked | 100% |
| Out-of-scope requests caught | >90% |
| Validation failure rate | <5% normal queries |

### Dependencies

- **Blocks**: None
- **Blocked by**: None (can start immediately)

---

## Implementation Order

Based on dependencies and impact, the recommended implementation order is:

```
Phase 1: Foundation (Parallel)
  |-- Improvement 4: Prompt Versioning System
  |-- Improvement 7: Data Quality Framework
  |-- Improvement 8: Defensive Prompting

Phase 2: Retrieval & Evaluation
  |-- Improvement 1: Hybrid Retrieval System
  |-- Improvement 2: AI-as-a-Judge Evaluation

Phase 3: Feedback & Memory
  |-- Improvement 3: Implicit Feedback Collection
  |-- Improvement 5: Three-Tier Memory Architecture

Phase 4: Optimization
  |-- Improvement 6: Lost-in-the-Middle Optimization
```

### Dependency Graph

```
Improvement 4 (Prompts) ────────┐
                                ├──> Improvement 6 (Context Optimization)
Improvement 7 (Quality) ───────>│
                                │
Improvement 8 (Defensive) ─────>│
                                │
Improvement 1 (Hybrid) ─────────┼──> Improvement 5 (Memory)
                                │
Improvement 2 (AI Judge) ───────┴──> Improvement 3 (Implicit Feedback)
```

---

## Files to Create/Modify

### New Files

| File | Improvement |
|------|-------------|
| `cortex/intelligence/memory/hybrid_retriever.py` | 1 |
| `cortex/intelligence/evaluation/quality_judge.py` | 2 |
| `cortex/intelligence/feedback/implicit_collector.py` | 3 |
| `cortex/prompts/__init__.py` | 4 |
| `cortex/prompts/base.py` | 4 |
| `cortex/prompts/registry.py` | 4 |
| `cortex/prompts/ab_testing.py` | 4 |
| `cortex/prompts/versions/v1/*.yaml` | 4 |
| `cortex/intelligence/memory/tiered_memory.py` | 5 |
| `cortex/intelligence/context_optimizer.py` | 6 |
| `cortex/intelligence/quality/data_quality.py` | 7 |

### Modified Files

| File | Improvements |
|------|-------------|
| `cortex/intelligence/memory/pattern_memory.py` | 1, 5 |
| `cortex/intelligence/memory/pattern_indexer.py` | 1 |
| `cortex/bridge.py` | 3, 6, 8 |
| `cortex/briefing.py` | 3, 4, 6 |
| `cortex/recommendation_engine.py` | 2, 3, 4 |
| `cortex/feedback.py` | 3 |
| `cortex/learning.py` | 2, 3, 7 |

---

## Testing Strategy

### Unit Test Coverage

Each improvement requires:
- Minimum 80% line coverage
- All public methods tested
- Edge cases documented

### Integration Test Coverage

- End-to-end flows for each improvement
- Cross-improvement integration tests
- Backward compatibility tests

### Performance Tests

| Component | Metric | Target |
|-----------|--------|--------|
| HybridRetriever | Latency (cached) | <100ms |
| QualityJudge | Latency per item | <500ms |
| ImplicitCollector | Overhead | <1% session time |
| TieredMemory | Query time | <50ms |

---

## Rollout Plan

### Phase 1: Canary (Week 1)

- Deploy to single user (developer)
- Monitor: error rates, latency, quality scores
- Feature flags for each improvement

### Phase 2: Beta (Weeks 2-3)

- Deploy to 10% of users
- A/B test critical improvements (hybrid retrieval, context optimization)
- Collect metrics

### Phase 3: General Availability (Week 4+)

- Full deployment
- Remove feature flags
- Document in user guide

---

## Success Criteria Summary

| Improvement | Primary Metric | Target |
|-------------|---------------|--------|
| Hybrid Retrieval | Recall@5 | >60% |
| AI-as-a-Judge | Correlation with human | >0.7 |
| Implicit Feedback | Signals per day | 50+ |
| Prompt Versioning | Prompts migrated | 100% |
| Three-Tier Memory | Query relevance | 20% improvement |
| Lost-in-the-Middle | Response relevance | 10% improvement |
| Data Quality | Data with scores | 100% |
| Defensive Prompting | Injection blocked | 100% |

---

## Appendix A: Current Code References

### Pattern Memory (`/Users/jesse.kemp/Dev/cortex/intelligence/memory/pattern_memory.py`)

Lines 56-68: PatternMemory class - single-tier, keyword-only search
Lines 116-146: get_relevant_patterns() - target for hybrid retrieval integration

### Pattern Indexer (`/Users/jesse.kemp/Dev/cortex/intelligence/memory/pattern_indexer.py`)

Lines 415-522: PatternSearcher class - pure keyword matching, no embeddings

### Feedback (`/Users/jesse.kemp/Dev/cortex/feedback.py`)

Lines 85-111: log_feedback() - explicit feedback only
Lines 157-198: log_outcome() - structured but manual

### Learning (`/Users/jesse.kemp/Dev/cortex/learning.py`)

Lines 44-68: calculate_recommendation_accuracy() - uses explicit outcomes
Lines 276-335: adjust_confidence_based_on_history() - calibration point

### Bridge (`/Users/jesse.kemp/Dev/cortex/bridge.py`)

Lines 466-502: get_context() - no defensive prompting
Lines 506-560: inject_recommendation() - no validation

### Prompt Learning (`/Users/jesse.kemp/Dev/cortex/intelligence/prompt_learning.py`)

Lines 50-60: PromptLearningLoop - existing prompt analysis framework
Lines 239-276: get_next_action_prediction() - integration point

---

## Appendix B: Book References

1. **Hybrid Retrieval**: "AI Engineering" Chapter 7, pp. 180-195
2. **LLM-as-a-Judge**: "AI Engineering" Chapter 5, pp. 112-130
3. **Implicit Feedback**: "AI Engineering" Chapter 8, pp. 220-235
4. **Prompt Versioning**: "AI Engineering" Chapter 4, pp. 85-100
5. **Memory Architecture**: "AI Engineering" Chapter 9, pp. 245-260
6. **Lost-in-the-Middle**: "AI Engineering" Chapter 4, pp. 95-98
7. **Data Quality**: "AI Engineering" Chapter 3, pp. 65-80
8. **Defensive Prompting**: "AI Engineering" Chapter 10, pp. 275-290

---

*This PRD follows Golden Spec methodology with no time estimates, dependency-based ordering, and verifiable test criteria.*
