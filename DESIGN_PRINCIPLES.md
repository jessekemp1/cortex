# Cortex Design Principles

**Version**: 2.0
**Last Updated**: 2026-01-18
**Status**: Strategic Direction

---

## Core Mission

**Cortex provides deep portfolio intelligence that transforms how developers manage complex, multi-project portfolios.**

### Value Proposition

Transform a developer from managing 3-5 projects to **strategically coordinating 30+ projects** through compound AI-assisted intelligence.

---

## 🎯 Primary Design Principle: Depth Over Speed

**Strategic Decision (2026-01-18)**: Cortex is optimized for **Deep Portfolio Intelligence**, not rapid context switching.

### What This Means

| Priority | Optimization Target |
|----------|-------------------|
| **#1 PRIMARY** | Intelligence depth & quality |
| **#2 SECONDARY** | Code simplicity & maintainability |
| **#3 TERTIARY** | Startup performance |

### The Tradeoff

- ✅ **ACCEPT**: 2-5 second startup for comprehensive analysis
- ✅ **ACCEPT**: Higher memory usage for deeper context
- ✅ **ACCEPT**: Batch API latency for better/cheaper intelligence
- ❌ **REJECT**: Speed optimizations that sacrifice depth
- ❌ **REJECT**: Caching that creates stale intelligence
- ❌ **REJECT**: Shallow analysis to meet latency targets

---

## Architecture Philosophy

### 1. **Simplicity Over Optimization**

**Before**: 848 performance-related patterns across 129 files
**Target**: Eliminate 80% of optimization complexity

**Guidelines**:
- No caching unless data is immutable
- No lazy loading unless import cycles require it
- No async unless operations are truly independent
- No layers unless they serve distinct purposes
- No premature optimization - measure first

**Example**:
```python
# AVOID (over-optimized)
async def get_context_cached_lazy():
    if not self._lazy_init:
        await self._initialize_async()
    if cached := self.cache.get("context"):
        return cached
    context = await self._build_context()
    self.cache.set("context", context, ttl=3600)
    return context

# PREFER (simple, correct)
def get_context():
    git_data = analyze_git_history(days=90)
    patterns = find_patterns()
    specs = search_specs()
    return Context(git=git_data, patterns=patterns, specs=specs)
```

---

### 2. **Deep Analysis Over Fast Response**

**Before**: Shallow, cached context to meet <500ms target
**Target**: Comprehensive, fresh intelligence even if 5s startup

**What Deep Means**:
- ✅ Full git history analysis (30-90 days, not just 5 commits)
- ✅ Fresh health calculations (real-time trends, not 1-hour cache)
- ✅ Automatic spec search (top 5 relevant specs at startup)
- ✅ Cross-project pattern matching (semantic, not keyword)
- ✅ Proactive anomaly detection (uncommitted work, stale branches)
- ✅ Dependency graph analysis (understand project relationships)
- ✅ Code quality metrics (linting, complexity, coverage)

**Rationale**:
Users spend 30+ seconds asking questions to build context. A 5-second deep startup eliminates that overhead while providing superior intelligence.

---

### 3. **Batch API First**

**Before**: Synchronous API calls for immediate results
**Target**: Batch API for all analysis (50% cost reduction, better models)

**Guidelines**:
- Use Batch API for all heavy analysis
- Accept 2-5 second wait for batch completion
- Use best models (Opus 4) instead of fast models (Haiku)
- Optimize for quality and cost, not latency

**Cost Comparison**:
- Synchronous API: ~$X/day, fast but expensive
- Batch API: ~$X/20/day, slower but 50% cheaper + better quality

---

### 4. **Adaptive Latency**

**Implementation**: Provide both fast and deep modes, default to deep

```bash
# Fast mode (500ms): Minimal analysis for quick checks
cortex quick

# Deep mode (5s): Comprehensive analysis (DEFAULT)
cortex deep
cortex  # Same as 'cortex deep'

# Auto mode: Learn user preference over time
cortex auto
```

**Default Behavior**: Deep mode
- Session start → Deep analysis
- User can opt into fast mode if needed
- System learns when each mode is appropriate

---

## Compound Intelligence

### Learning Feedback Loop

**Core Insight**: Rich feedback creates faster learning

| Approach | Sessions to 85% Accuracy | Context per Session |
|----------|-------------------------|-------------------|
| **Shallow (fast)** | ~50 sessions | Low quality feedback |
| **Deep (slow)** | ~20 sessions | Rich quality feedback |

**Principle**: Slower startup with richer context → faster learning → better recommendations sooner

### What Gets Tracked

- Full git context (not just recent commits)
- Comprehensive project health (not cached scores)
- Semantic pattern matches (not keyword hits)
- Deep code analysis (not quick scans)

**Result**: Higher quality outcome data → better calibration → more accurate predictions

---

## Implementation Guidelines

### DO

✅ **Run fresh analysis** every session (even if slower)
✅ **Use Batch API** for heavy computation
✅ **Provide comprehensive context** upfront
✅ **Simplify code** by removing optimizations
✅ **Measure intelligence quality** not just speed
✅ **Default to deep mode** unless user opts out
✅ **Use best models** (Opus > Sonnet > Haiku)

### DON'T

❌ **Cache intelligence** that should be fresh
❌ **Optimize prematurely** without profiling
❌ **Sacrifice depth** to meet arbitrary latency targets
❌ **Add complexity** for marginal speed gains
❌ **Default to fast mode** to "feel snappy"
❌ **Use cheaper models** to reduce cost at quality expense

---

## Migration Strategy

### Phase 1: Document & Measure (Current)

- ✅ Document strategic decision (this file)
- ✅ Identify complexity to remove (141 files with perf patterns)
- ⏳ Measure current intelligence quality baseline
- ⏳ Profile actual slow operations (not assumptions)

### Phase 2: Implement Deep Mode (Week 1)

- [ ] Create `cortex deep` command with comprehensive analysis
- [ ] Remove unnecessary caching from deep mode
- [ ] Integrate Batch API for heavy operations
- [ ] Measure quality improvement vs current

### Phase 3: Simplify Architecture (Week 2-3)

- [ ] Remove health tracker cache (run fresh git analysis)
- [ ] Simplify session manager (no lazy loading)
- [ ] Consolidate layer architecture (reduce boundaries)
- [ ] Remove async where not needed

### Phase 4: Make Deep Default (Week 4)

- [ ] Switch default to deep mode
- [ ] Keep fast mode for explicit opt-in
- [ ] Add adaptive mode that learns preference
- [ ] Measure adoption and satisfaction

---

## Success Metrics

### Quality Metrics (Primary)

| Metric | Current | Target |
|--------|---------|--------|
| **Recommendation accuracy** | 65% | 85%+ |
| **Context completeness** | ~40% (5 commits) | ~90% (full history) |
| **Spec search relevance** | On-demand | Auto top-5 at startup |
| **Pattern match quality** | Keyword-based | Semantic embeddings |
| **Sessions to calibration** | ~50 | ~20 |

### Simplicity Metrics (Secondary)

| Metric | Current | Target |
|--------|---------|--------|
| **Performance-related files** | 141 | <30 |
| **Lines of code** | ~15,000 | ~5,000 (-67%) |
| **Cache management LOC** | ~500 | <50 |
| **TODO/FIXME comments** | 131 | <20 |
| **Time to debug issues** | 30-60 min | 5-10 min |

### Speed Metrics (Tertiary)

| Metric | Current | Acceptable |
|--------|---------|-----------|
| **Session startup** | 500ms | 2-5s |
| **Deep analysis** | N/A (not implemented) | <5s |
| **Fast mode** | 500ms | <1s |

---

## Rationale: Why Depth First?

### 1. **Portfolio Intelligence is the Core Value**

- Managing 30+ projects requires deep understanding, not fast switching
- Quality recommendations matter more than instant responses
- Compound learning requires rich feedback data

### 2. **Speed Created Complexity Tax**

- 848 perf patterns across 129 files = maintenance burden
- Caching creates staleness and bugs
- Async creates race conditions and harder debugging
- Layers create marshalling overhead

### 3. **Users Want Intelligence, Not Speed**

- Current: 500ms startup → 30s of Q&A to build context
- Alternative: 5s startup → immediate productive work
- Net time savings despite slower startup

### 4. **Batch API Economics**

- 50% cost reduction enables using best models (Opus 4)
- Better models → better intelligence → more value
- Cost savings pay for architectural simplification

### 5. **Faster Learning Convergence**

- Rich context → high-quality outcome data
- Better data → faster calibration
- Reach 85% accuracy in 20 sessions instead of 50

---

## References

- [5 Whys Analysis: <500ms Constraint](/.claude/analysis/5-whys-500ms-constraint.md)
- [Slow vs Fast Architecture Analysis](/.claude/analysis/slow-architecture-benefits.md)
- [Technical Reference](docs/TECHNICAL_REFERENCE.md)
- [Golden Spec Method](golden-spec-method/GOLDEN_SPEC_CORTEX_EDITION.md)

---

## Review & Updates

This document should be reviewed quarterly or when major architectural decisions arise.

**Last Review**: 2026-01-18
**Next Review**: 2026-04-18
**Owner**: Primary maintainer

---

**Status**: ✅ **ACTIVE STRATEGIC DIRECTION**

All new features and refactoring should align with these principles.
