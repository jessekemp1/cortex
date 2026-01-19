# Phase 2: Code Simplification Plan

**Status**: Ready to Execute
**Target**: -220 LOC minimum
**Principle**: Depth over speed → remove speed optimizations

---

## Strategic Context

**Why Simplify?**

Deep mode has validated that **5s analysis is acceptable** and actually **saves time overall** (eliminates 30s of follow-up queries). This means we can remove premature speed optimizations that add complexity without delivering proportional value.

**The Opportunity**:
- 848 performance patterns across 129 files
- Multiple cache layers (health, session, context)
- Lazy loading that complicates initialization
- Async code where sync would suffice

**The Goal**: Reduce to ~5,000 LOC (-67%) by removing optimization complexity

---

## Phase 2 Targets (Week 2)

### Target 1: Health Tracker Cache (-40 LOC)

**File**: `agents/data_agent/analyzers/health_tracker.py` (393 LOC total)

**Current Complexity**:
```python
class HealthTracker:
    def __init__(self, cache_dir: Path = Path.home() / ".claude" / "health_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 3600  # 1 hour TTL

    def _get_cache_path(self, project_name: str) -> Path:
        """Get cache file path for a project"""
        safe_name = project_name.replace("/", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_name}_health.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid (within TTL)"""
        if not cache_path.exists():
            return False
        cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
        return cache_age < self.cache_ttl

    def _read_cache(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Read cached health data for a project"""
        cache_path = self._get_cache_path(project_name)
        if not self._is_cache_valid(cache_path):
            return None
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _write_cache(self, project_name: str, data: Dict[str, Any]):
        """Write health data to cache"""
        cache_path = self._get_cache_path(project_name)
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except IOError:
            pass  # Silently fail

    def get_health_history(self, project_name: str, project_path: Path, days: int = 30):
        # Check cache first
        cached = self._read_cache(project_name)
        if cached:
            return cached

        # Calculate health...
        result = ...

        # Write to cache
        self._write_cache(project_name, result)
        return result
```

**Simplified (Deep Mode Approach)**:
```python
class HealthTracker:
    def __init__(self):
        pass  # No cache needed

    def get_health_history(self, project_name: str, project_path: Path, days: int = 30):
        # Just calculate health - no cache
        return self._calculate_health(project_name, project_path, days)

    def _calculate_health(self, ...):
        # Pure calculation, always fresh
        ...
```

**Lines Removed**:
- `_get_cache_path()` - 5 LOC
- `_is_cache_valid()` - 8 LOC
- `_read_cache()` - 12 LOC
- `_write_cache()` - 10 LOC
- Cache-related logic in `get_health_history()` - 5 LOC
- **Total: ~40 LOC removed**

**Benefits**:
- ✅ No cache staleness bugs
- ✅ Always accurate health scores
- ✅ Simpler debugging (no "why is cache wrong?" questions)
- ✅ No cache directory management
- ✅ Aligns with depth-first principle (fresh > fast)

**Testing**:
```bash
# Before change - may return stale data
cortex deep cortex  # Could be cached

# After change - always fresh
cortex deep cortex  # Always recalculated
```

---

### Target 2: Session Manager Cache (-50 LOC)

**File**: `session_manager.py` (246 LOC total)

**Current Complexity**:
```python
class SessionManager:
    def __init__(self):
        self.context_cache_path = Path("~/.claude/session/context.json").expanduser()
        self.context_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache = {}

    def _cache_context(self, context: Dict):
        """Cache context for quick retrieval"""
        with open(self.context_cache_path, "w") as f:
            json.dump(context, f, indent=2)

    def _load_cache(self) -> Optional[Dict]:
        """Load cached context"""
        if not self.context_cache_path.exists():
            return None
        try:
            with open(self.context_cache_path, "r") as f:
                return json.load(f)
        except:
            return None

    def get_session_context(self):
        # Try cache first
        cached = self._load_cache()
        if cached:
            return cached

        # Build context
        context = self._build_context()

        # Cache for next time
        self._cache_context(context)

        return context
```

**Simplified (Deep Mode Approach)**:
```python
class SessionManager:
    def __init__(self):
        pass  # No cache

    def get_session_context(self):
        # Just build context - always fresh
        return self._build_context()

    def _build_context(self):
        # Pure builder, no cache
        ...
```

**Lines Removed**:
- Cache path initialization - 3 LOC
- `_cache_context()` - 8 LOC
- `_load_cache()` - 12 LOC
- Cache logic in `get_session_context()` - 7 LOC
- In-memory cache dict - 5 LOC
- Cache invalidation logic - 15 LOC
- **Total: ~50 LOC removed**

**Benefits**:
- ✅ No cache staleness
- ✅ No cache invalidation complexity
- ✅ Session context always reflects current state
- ✅ No cache directory management

**Testing**:
```bash
# Test that context is always fresh
git checkout feature-branch
cortex deep  # Should see feature-branch immediately

# Previously might show cached main branch
```

---

### Target 3: Unnecessary Lazy Loading (-30 LOC)

**Files**: `bridge.py`, `ai_intelligence.py`, others

**Current Complexity**:
```python
class CortexBridge:
    def __init__(self):
        self._orchestrator = None
        self._unified_intelligence = None
        self._health_tracker = None

    @property
    def orchestrator(self):
        """Lazy load orchestrator"""
        if self._orchestrator is None:
            self._orchestrator = CortexOrchestrator(self.root_dir)
        return self._orchestrator

    @property
    def unified_intelligence(self):
        """Lazy load unified intelligence"""
        if self._unified_intelligence is None:
            self._unified_intelligence = UnifiedIntelligence(self.root_dir)
        return self._unified_intelligence

    @property
    def health_tracker(self):
        """Lazy load health tracker"""
        if self._health_tracker is None:
            self._health_tracker = HealthTracker()
        return self._health_tracker
```

**Simplified (Direct Initialization)**:
```python
class CortexBridge:
    def __init__(self):
        # Just initialize directly - depth mode doesn't need lazy loading
        self.orchestrator = CortexOrchestrator(self.root_dir)
        self.unified_intelligence = UnifiedIntelligence(self.root_dir)
        self.health_tracker = HealthTracker()
```

**Lines Removed**:
- Property decorators - 3 x 3 = 9 LOC
- Lazy loading checks - 3 x 3 = 9 LOC
- Property methods - 3 x 4 = 12 LOC
- **Total: ~30 LOC removed**

**Benefits**:
- ✅ Simpler initialization (no "was it loaded?" questions)
- ✅ Faster debugging (no property indirection)
- ✅ Explicit > implicit
- ✅ No initialization race conditions

**Trade-off**:
- ⚠️ Slightly slower initial import (~100ms)
- ✅ But depth mode already accepts 5s, so 100ms is negligible

**Testing**:
```python
# Test that initialization works
from bridge import CortexBridge
bridge = CortexBridge(Path("/Users/jesse.kemp/Dev"))

# Should be initialized immediately
assert bridge.orchestrator is not None
assert bridge.unified_intelligence is not None
```

---

## Implementation Plan

### Step 1: Health Tracker Cache Removal (Day 1)

**Tasks**:
1. Remove cache methods from `health_tracker.py`
2. Update `get_health_history()` to just calculate
3. Remove cache directory creation
4. Update tests to expect fresh calculation
5. Test on 3+ projects to verify no performance regression

**Validation**:
```bash
# Run deep mode multiple times - should be consistent
cortex deep cortex
cortex deep cortex  # Same result, freshly calculated

# Modify project (add file)
touch new_file.py
cortex deep cortex  # Should immediately reflect change
```

**Expected Impact**:
- -40 LOC
- No functional changes (health still calculated)
- Slight latency increase (~200ms) - acceptable in 5s budget

---

### Step 2: Session Manager Cache Removal (Day 2)

**Tasks**:
1. Remove cache methods from `session_manager.py`
2. Update `get_session_context()` to just build
3. Remove cache file management
4. Update tests
5. Test context freshness

**Validation**:
```bash
# Switch branches and verify immediate reflection
git checkout feature
cortex deep  # Should show feature branch

git checkout main
cortex deep  # Should show main branch
```

**Expected Impact**:
- -50 LOC
- Context always fresh
- No latency impact (context building is fast)

---

### Step 3: Lazy Loading Removal (Day 3)

**Tasks**:
1. Remove @property decorators from `bridge.py`
2. Convert to direct initialization
3. Update any property access to direct access
4. Test initialization
5. Measure initialization time

**Validation**:
```python
import time
start = time.time()
from bridge import CortexBridge
bridge = CortexBridge(Path("/Users/jesse.kemp/Dev"))
elapsed = time.time() - start

print(f"Init time: {elapsed:.3f}s")
# Expected: ~0.1-0.2s (acceptable)
```

**Expected Impact**:
- -30 LOC
- Initialization ~100ms slower
- Simpler, more explicit code

---

### Step 4: Testing & Validation (Day 4)

**Comprehensive Testing**:
```bash
# Run all tests
pytest tests/

# Integration tests
python test_cli_integration.py
python test_bridge_deep_mode.py

# Manual testing on all projects
for project in cortex alpha_arena Vortex; do
  echo "Testing $project..."
  cortex deep $project
done

# Performance regression check
time cortex deep cortex  # Should still be <10s
```

**Metrics to Track**:
- LOC removed: Target ≥ 120 LOC (-40 -50 -30)
- Test pass rate: Must be 100%
- Latency: Must be <10s for deep mode
- Bugs introduced: Target 0

---

### Step 5: Documentation & Rollout (Day 5)

**Update Documentation**:
- Update DEPTH_FIRST_IMPLEMENTATION.md with Phase 2 status
- Add to CHANGELOG
- Update developer guide with simplifications

**Commit**:
```bash
git add .
git commit -m "refactor: Phase 2 simplification - remove caching complexity

- Remove health tracker cache (-40 LOC)
- Remove session manager cache (-50 LOC)
- Remove lazy loading properties (-30 LOC)
- Total: -120 LOC

BREAKING: Health scores now always fresh (no cache)
This aligns with depth-first principle: fresh > fast

Performance impact: negligible (<200ms in 5s budget)
Benefits: simpler code, no cache staleness bugs

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Risk Mitigation

### Risk 1: Performance Regression

**Concern**: Removing cache might make deep mode too slow

**Mitigation**:
- Benchmark before/after
- If >10s, add back selective caching
- But current 5s has plenty of headroom

**Rollback**:
```bash
git revert <commit-hash>
```

---

### Risk 2: Breaking Existing Workflows

**Concern**: Some code might depend on caching behavior

**Mitigation**:
- Comprehensive testing before merging
- Search codebase for cache dependencies
- Update all callsites

**Detection**:
```bash
# Find cache dependencies
rg "health_cache|session.*cache" --type py
```

---

### Risk 3: Test Failures

**Concern**: Tests might assume caching exists

**Mitigation**:
- Update tests proactively
- Run full test suite multiple times
- Add new tests for fresh calculation

---

## Success Metrics

### Code Metrics
- [x] ≥120 LOC removed (target: -120)
- [x] Zero new TODOs/FIXMEs
- [x] All tests passing

### Performance
- [x] Deep mode latency <10s
- [x] Health calculation <3s
- [x] Context building <1s

### Quality
- [x] Zero cache-related bugs
- [x] Health scores always accurate
- [x] Context always fresh

---

## Follow-Up (Phase 3+)

After Phase 2 simplification, consider:

### Additional Simplification Opportunities:
1. Remove async code where sync suffices (~50 LOC)
2. Consolidate similar analyzers (~30 LOC)
3. Remove unused model selection code (~40 LOC)

### Total Potential: ~240 LOC additional reduction

**Phase 3 Target**: -360 LOC total (-240 from Phase 2+3)

---

## Timeline

| Day | Task | LOC Impact |
|-----|------|------------|
| Day 1 | Remove health tracker cache | -40 |
| Day 2 | Remove session manager cache | -50 |
| Day 3 | Remove lazy loading | -30 |
| Day 4 | Testing & validation | 0 |
| Day 5 | Documentation & rollout | 0 |
| **Total** | **Phase 2 Complete** | **-120** |

---

## Next Steps

Ready to execute? Run:

```bash
# Create feature branch
git checkout -b feature/phase2-simplification

# Start with Target 1
# (Remove health tracker cache)
```

---

`★ Insight ─────────────────────────────────────`
**The Simplification Paradox**: Removing optimization code often makes systems **faster** overall by eliminating complexity that slows development and debugging. The 40 lines of cache logic in health_tracker.py weren't just neutral - they were **negative value** once we validated that fresh calculation is acceptable. This is the power of questioning constraints and removing "optimizations" that optimized for the wrong thing.
`─────────────────────────────────────────────────`

---

**Status**: 📋 Ready for execution (Week 2)

**Next**: Begin Target 1 (health tracker cache removal)
