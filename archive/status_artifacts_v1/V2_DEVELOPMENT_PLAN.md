# Cortex V2 Development Plan

**Goal:** Build enhanced Cortex without breaking current version
**Approach:** New `cortex_v2/` directory, parallel development, feature flags for migration

---

## Architecture: V2 Alongside V1

```
cortex/
├── cli.py                    # V1 (unchanged)
├── bridge.py                 # V1 (unchanged)
├── ...                       # V1 files (unchanged)
│
├── v2/                       # NEW: V2 implementation
│   ├── __init__.py
│   ├── cli.py                # V2 CLI (cortex2 command)
│   ├── bridge.py             # V2 Bridge with new features
│   ├── memory/
│   │   ├── graph.py          # Graph relationships
│   │   ├── types.py          # Memory type separation
│   │   └── store.py          # Unified storage layer
│   ├── learning/
│   │   ├── outcomes.py       # Automated outcome detection
│   │   ├── skills.py         # Skill extraction
│   │   └── calibration.py    # ML-based confidence
│   └── integrations/
│       ├── git_hooks.py      # Git hook integration
│       └── ci_webhooks.py    # CI/CD webhooks
│
├── data/
│   ├── v1/                   # V1 data (unchanged)
│   └── v2/                   # V2 data (new format)
│       ├── graph.db          # SQLite for graph
│       ├── memories.json     # Typed memories
│       └── skills.json       # Extracted skills
```

---

## Feature Plan

### Tier 1: Must Have (Weeks 1-4)

| # | Feature | Description | Effort |
|---|---------|-------------|--------|
| 1 | Graph relationships | Connect patterns, projects, outcomes | 2 weeks |
| 2 | Automated outcome detection | Git hooks + CI webhooks | 2 weeks |
| 3 | Memory type separation | Patterns, incidents, skills, decisions | 1 week |

### Tier 2: Should Have (Weeks 5-8)

| # | Feature | Description | Effort |
|---|---------|-------------|--------|
| 4 | Skill extraction | Auto-extract skills from successful outcomes | 2 weeks |
| 5 | Temporal decay | Stale patterns fade in relevance | 1 week |
| 6 | ML confidence calibration | Replace averaging with real ML | 2 weeks |

### Tier 3: Nice to Have (Weeks 9-12)

| # | Feature | Description | Effort |
|---|---------|-------------|--------|
| 7 | Vector embeddings | Semantic search with ChromaDB | 2 weeks |
| 8 | Simple agent delegation | "Research this" capability | 3 weeks |

---

## Tier 1 Detailed Plans

### Feature 1: Graph Relationships

**Problem:** Current JSON storage has no relationships. Can't discover "Project A uses same pattern as Project B."

**Solution:** SQLite-based graph with simple schema.

**Schema:**
```sql
-- Nodes
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- pattern, project, outcome, skill
    name TEXT NOT NULL,
    data JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Edges (relationships)
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    from_id TEXT REFERENCES nodes(id),
    to_id TEXT REFERENCES nodes(id),
    relation TEXT NOT NULL,  -- uses, similar_to, validates, caused_by
    weight REAL DEFAULT 1.0,
    data JSON,
    created_at TIMESTAMP
);

-- Indexes for fast traversal
CREATE INDEX idx_edges_from ON edges(from_id);
CREATE INDEX idx_edges_to ON edges(to_id);
CREATE INDEX idx_edges_relation ON edges(relation);
CREATE INDEX idx_nodes_type ON nodes(type);
```

**Relationships to support:**
```
project --uses--> pattern
pattern --similar_to--> pattern
outcome --validates--> pattern
outcome --caused_by--> pattern
skill --extracted_from--> outcome
project --depends_on--> project
```

**API:**
```python
class GraphMemory:
    def add_node(self, type: str, name: str, data: dict) -> str
    def add_edge(self, from_id: str, to_id: str, relation: str, weight: float = 1.0)
    def get_related(self, node_id: str, relation: str = None, depth: int = 1) -> List[Node]
    def find_path(self, from_id: str, to_id: str) -> List[Edge]
    def query(self, node_type: str, filters: dict) -> List[Node]
```

**Files to create:**
- `v2/memory/graph.py` - GraphMemory class
- `v2/memory/models.py` - Node, Edge dataclasses
- `v2/tests/test_graph.py` - Unit tests

**Success criteria:**
- Query "patterns used by VortexV2" returns results in <10ms
- Find similar patterns across projects
- Graph traversal depth 3 in <50ms

---

### Feature 2: Automated Outcome Detection

**Problem:** Manual outcome logging has <30% compliance. Learning system is starved.

**Solution:** Git hooks + CI webhook receiver.

**Git Hook (post-commit):**
```bash
#!/bin/bash
# .git/hooks/post-commit

# Extract commit info
COMMIT_MSG=$(git log -1 --pretty=%B)
COMMIT_HASH=$(git rev-parse HEAD)
BRANCH=$(git branch --show-current)
FILES_CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD | wc -l)

# Detect outcome signals
if echo "$COMMIT_MSG" | grep -qiE "(fix|resolve|close|complete)"; then
    OUTCOME_TYPE="success"
elif echo "$COMMIT_MSG" | grep -qiE "(revert|rollback|broken|fail)"; then
    OUTCOME_TYPE="failure"
elif echo "$COMMIT_MSG" | grep -qiE "(wip|progress|partial)"; then
    OUTCOME_TYPE="in_progress"
else
    OUTCOME_TYPE="unknown"
fi

# Report to Cortex V2
python3 -c "
from cortex.v2.learning.outcomes import OutcomeDetector
detector = OutcomeDetector()
detector.record_git_outcome(
    commit_hash='$COMMIT_HASH',
    message='$COMMIT_MSG',
    branch='$BRANCH',
    files_changed=$FILES_CHANGED,
    detected_outcome='$OUTCOME_TYPE'
)
"
```

**CI Webhook Receiver:**
```python
# v2/integrations/ci_webhooks.py

from fastapi import FastAPI, Request
from cortex.v2.learning.outcomes import OutcomeDetector

app = FastAPI()
detector = OutcomeDetector()

@app.post("/webhook/github-actions")
async def github_actions_webhook(request: Request):
    payload = await request.json()

    if payload.get("action") == "completed":
        workflow = payload["workflow_run"]
        detector.record_ci_outcome(
            repo=workflow["repository"]["full_name"],
            workflow=workflow["name"],
            conclusion=workflow["conclusion"],  # success, failure, cancelled
            commit=workflow["head_sha"],
            branch=workflow["head_branch"],
            duration=workflow["run_duration_ms"]
        )

    return {"status": "ok"}

@app.post("/webhook/pytest")
async def pytest_webhook(request: Request):
    payload = await request.json()

    detector.record_test_outcome(
        project=payload["project"],
        passed=payload["passed"],
        failed=payload["failed"],
        skipped=payload["skipped"],
        duration=payload["duration"],
        commit=payload.get("commit")
    )

    return {"status": "ok"}
```

**Outcome Detector:**
```python
# v2/learning/outcomes.py

@dataclass
class DetectedOutcome:
    id: str
    source: str  # git, ci, test, manual
    outcome_type: str  # success, failure, partial, unknown
    confidence: float  # 0-1, how sure are we
    project: str
    context: dict
    timestamp: datetime

class OutcomeDetector:
    def record_git_outcome(self, commit_hash: str, message: str, ...) -> DetectedOutcome
    def record_ci_outcome(self, repo: str, conclusion: str, ...) -> DetectedOutcome
    def record_test_outcome(self, passed: int, failed: int, ...) -> DetectedOutcome
    def correlate_to_pattern(self, outcome: DetectedOutcome) -> Optional[str]
    def get_recent_outcomes(self, project: str = None, days: int = 7) -> List[DetectedOutcome]
```

**Files to create:**
- `v2/learning/outcomes.py` - OutcomeDetector class
- `v2/integrations/ci_webhooks.py` - Webhook receiver
- `v2/integrations/git_hooks.py` - Hook installer
- `scripts/install_hooks.sh` - Hook installation script

**Success criteria:**
- 80%+ of commits auto-detected
- CI outcomes captured within 1 minute
- Correlation to patterns >60% accuracy

---

### Feature 3: Memory Type Separation

**Problem:** All memories in one flat JSON. "How do I..." queries return random facts.

**Solution:** Separate storage by memory type with specialized retrieval.

**Memory Types:**
```python
# v2/memory/types.py

class MemoryType(Enum):
    PATTERN = "pattern"      # Reusable solutions
    INCIDENT = "incident"    # What went wrong
    SKILL = "skill"          # Step-by-step procedures
    DECISION = "decision"    # Why we chose X over Y
    FACT = "fact"            # General knowledge

@dataclass
class TypedMemory:
    id: str
    type: MemoryType
    title: str
    content: str
    projects: List[str]
    tags: List[str]
    confidence: float
    created_at: datetime
    last_used: datetime
    use_count: int

@dataclass
class Pattern(TypedMemory):
    problem: str
    solution: str
    context: str  # When to use
    anti_patterns: List[str]  # When NOT to use
    outcomes: List[str]  # Linked outcome IDs

@dataclass
class Incident(TypedMemory):
    what_happened: str
    root_cause: str
    resolution: str
    prevention: str
    severity: str  # critical, major, minor

@dataclass
class Skill(TypedMemory):
    steps: List[str]
    prerequisites: List[str]
    estimated_time: str
    difficulty: str  # easy, medium, hard

@dataclass
class Decision(TypedMemory):
    question: str
    chosen_option: str
    alternatives: List[str]
    rationale: str
    outcome: str  # How it turned out
```

**Type-Aware Retrieval:**
```python
# v2/memory/store.py

class TypedMemoryStore:
    def __init__(self, data_dir: Path):
        self.patterns = self._load("patterns.json")
        self.incidents = self._load("incidents.json")
        self.skills = self._load("skills.json")
        self.decisions = self._load("decisions.json")

    def query(self,
              query: str,
              types: List[MemoryType] = None,
              projects: List[str] = None,
              min_confidence: float = 0.5) -> List[TypedMemory]:
        """Smart retrieval based on query intent."""

        # Detect query intent
        if query.lower().startswith(("how do i", "how to", "steps to")):
            types = types or [MemoryType.SKILL, MemoryType.PATTERN]
        elif query.lower().startswith(("why did", "what caused", "why is")):
            types = types or [MemoryType.INCIDENT, MemoryType.DECISION]
        elif query.lower().startswith(("what is", "explain")):
            types = types or [MemoryType.FACT, MemoryType.DECISION]
        else:
            types = types or list(MemoryType)

        # Search appropriate stores
        results = []
        for mem_type in types:
            store = self._get_store(mem_type)
            results.extend(self._search(store, query, projects, min_confidence))

        return sorted(results, key=lambda x: x.confidence, reverse=True)
```

**Files to create:**
- `v2/memory/types.py` - Memory type definitions
- `v2/memory/store.py` - TypedMemoryStore class
- `v2/tests/test_memory_types.py` - Unit tests

**Success criteria:**
- "How do I..." queries return skills/patterns 90%+ of time
- "What went wrong..." queries return incidents 90%+ of time
- Retrieval precision improves from 30% to 70%+

---

## Implementation Schedule

### Week 1-2: Graph Relationships (Feature 1)

**Week 1:**
- Day 1-2: Set up v2/ directory structure, SQLite schema
- Day 3-4: Implement GraphMemory class
- Day 5: Unit tests, edge cases

**Week 2:**
- Day 1-2: Migration script (V1 JSON → V2 graph)
- Day 3-4: Query optimization, indexing
- Day 5: Integration with V2 bridge

### Week 3-4: Automated Outcomes (Feature 2)

**Week 3:**
- Day 1-2: OutcomeDetector class
- Day 3-4: Git hook implementation
- Day 5: Hook installer script

**Week 4:**
- Day 1-2: CI webhook receiver (FastAPI)
- Day 3-4: Pattern correlation logic
- Day 5: End-to-end testing

### Week 5: Memory Types (Feature 3)

**Week 5:**
- Day 1: Memory type definitions
- Day 2-3: TypedMemoryStore implementation
- Day 4: Intent detection for queries
- Day 5: Migration from V1 format

---

## Migration Strategy

### Phase 1: Parallel Operation
- V1 continues working unchanged
- V2 runs separately with `cortex2` command
- Data stored in separate locations

### Phase 2: Data Sync
- V2 reads V1 data (backward compatible)
- New data written to V2 format
- V1 still works, V2 has more features

### Phase 3: Cutover
- V2 becomes default `cortex` command
- V1 available as `cortex-legacy`
- Migration script for remaining users

---

## Testing Strategy

### Unit Tests
```
v2/tests/
├── test_graph.py           # Graph memory operations
├── test_outcomes.py        # Outcome detection
├── test_memory_types.py    # Type separation
└── test_integration.py     # End-to-end
```

### Integration Tests
- Git hook triggers outcome detection
- CI webhook records properly
- Graph queries return correct results

### Performance Tests
- Graph query <10ms for 1000 nodes
- Outcome detection <100ms per commit
- Memory retrieval <50ms

---

## Success Metrics

| Metric | V1 Baseline | V2 Target |
|--------|-------------|-----------|
| Outcome logging rate | 30% | 80%+ (automated) |
| Pattern discovery accuracy | 30% | 70%+ (graph + types) |
| Cross-project matching | Manual only | Automatic |
| Learning system data | 127 outcomes | 500+ (automated) |
| Query intent accuracy | N/A | 90%+ |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| V2 breaks V1 | Separate directories, no shared code |
| Data migration fails | Keep V1 data untouched, copy-only migration |
| Performance regression | Benchmarks before/after each feature |
| Scope creep | Strict Tier 1 focus, defer Tier 2-3 |

---

## Tier 1 Status: COMPLETE ✅

All Tier 1 features implemented and tested:

| Feature | Status | Tests |
|---------|--------|-------|
| 1. Graph Relationships | ✅ Complete | 5/5 passing |
| 2. Automated Outcome Detection | ✅ Complete | 10/10 passing |
| 3. Memory Type Separation | ✅ Complete | 10/10 passing |
| V2 Bridge Integration | ✅ Complete | 10/10 passing |

---

## Tier 2 Detailed Plans

### Feature 4: Skill Extraction from Outcomes

**Problem:** Developers repeat the same multi-step processes. We detect "fix deployed successfully" but don't capture HOW.

**Solution:** Extract step-by-step skills from successful outcome sequences.

**Detection Signals:**
```python
# What indicates a learnable skill sequence:
1. Git commits with "step 1", "part 1", sequential patterns
2. Multiple commits within 30min touching same files
3. Commits ending with "complete", "done", "ship"
4. CI passing after a sequence of related changes
```

**Skill Extractor:**
```python
# v2/learning/skills.py

@dataclass
class ExtractedSkill:
    id: str
    title: str  # Auto-generated from commit messages
    steps: List[str]  # Extracted from commit sequence
    source_commits: List[str]
    source_outcomes: List[str]
    project: str
    confidence: float
    duration_minutes: int  # Time from first to last commit
    files_touched: List[str]
    created_at: datetime

class SkillExtractor:
    def __init__(self, outcomes: OutcomeDetector, graph: GraphMemory):
        self.outcomes = outcomes
        self.graph = graph

    def extract_from_recent(self, days: int = 7) -> List[ExtractedSkill]:
        """Find skill-like sequences in recent outcomes."""
        # Group outcomes by project + time window
        # Look for sequential patterns
        # Extract steps from commit messages
        # Create Skill memories

    def detect_sequence(self, outcomes: List[DetectedOutcome]) -> Optional[List[str]]:
        """Detect if outcomes form a skill sequence."""
        # Check for:
        # - Sequential numbering (step 1, step 2)
        # - Time proximity (<30min between commits)
        # - File overlap (same files touched)
        # - Success at end

    def generate_skill_title(self, commits: List[str]) -> str:
        """Generate skill title from commit messages."""
        # Extract common theme
        # E.g., ["Add user model", "Add user API", "Add user tests"]
        #    -> "Implement User Feature"

    def merge_similar_skills(self, skills: List[ExtractedSkill]) -> List[ExtractedSkill]:
        """Merge similar skills to avoid duplicates."""
        # Compare file patterns, step similarity
        # Keep highest confidence version
```

**Sequence Detection Algorithm:**
```python
def detect_skill_sequences(outcomes: List[DetectedOutcome]) -> List[SkillSequence]:
    sequences = []

    # Sort by timestamp
    sorted_outcomes = sorted(outcomes, key=lambda o: o.timestamp)

    # Sliding window approach
    current_sequence = []

    for outcome in sorted_outcomes:
        if not current_sequence:
            current_sequence = [outcome]
            continue

        last = current_sequence[-1]
        time_gap = (outcome.timestamp - last.timestamp).total_seconds() / 60

        # Check if this continues the sequence
        if (time_gap < 30 and  # Within 30 minutes
            outcome.project == last.project and  # Same project
            _files_overlap(outcome, last)):  # Related files
            current_sequence.append(outcome)
        else:
            # End current sequence, start new
            if len(current_sequence) >= 3 and _ends_with_success(current_sequence):
                sequences.append(SkillSequence(current_sequence))
            current_sequence = [outcome]

    return sequences
```

**Files to create:**
- `v2/learning/skills.py` - SkillExtractor class
- `v2/tests/test_skills.py` - Unit tests

**Success criteria:**
- Extract 5+ skills from 30 days of outcomes
- 70%+ of extracted skills are actually useful
- No duplicate skills (similarity threshold)

---

### Feature 5: Temporal Decay

**Problem:** Old patterns have same weight as recent ones. A 2-year-old "use jQuery" pattern shouldn't rank equally with recent "use React" pattern.

**Solution:** Time-based relevance decay with configurable half-life.

**Decay Model:**
```python
# v2/memory/decay.py

import math
from datetime import datetime, timedelta

class TemporalDecay:
    """Time-based relevance decay for memories."""

    # Half-life in days (relevance drops 50% after this time)
    DEFAULT_HALF_LIVES = {
        "pattern": 180,    # 6 months - patterns stay relevant longer
        "incident": 90,    # 3 months - incidents fade faster
        "skill": 365,      # 1 year - skills stay relevant
        "decision": 730,   # 2 years - decisions are semi-permanent
        "fact": 365,       # 1 year - facts may become outdated
    }

    def __init__(self, half_lives: dict = None):
        self.half_lives = half_lives or self.DEFAULT_HALF_LIVES

    def calculate_decay(
        self,
        memory_type: str,
        created_at: datetime,
        last_used: datetime = None,
        use_count: int = 0
    ) -> float:
        """Calculate decay factor (0-1) for a memory.

        Returns:
            float: 1.0 = fully relevant, 0.0 = completely decayed
        """
        now = datetime.utcnow()
        half_life = self.half_lives.get(memory_type, 180)

        # Use last_used if available, otherwise created_at
        reference_time = last_used or created_at
        days_old = (now - reference_time).days

        # Exponential decay: relevance = 0.5 ^ (days / half_life)
        base_decay = math.pow(0.5, days_old / half_life)

        # Boost for frequently used memories
        # Each use adds ~10% back to relevance (diminishing)
        use_boost = min(0.3, use_count * 0.03)

        # Final relevance
        return min(1.0, base_decay + use_boost)

    def apply_decay(self, memories: List[TypedMemory]) -> List[TypedMemory]:
        """Apply decay to a list of memories."""
        for memory in memories:
            decay_factor = self.calculate_decay(
                memory_type=memory.__class__.__name__.lower(),
                created_at=memory.created_at,
                last_used=memory.last_used,
                use_count=memory.use_count
            )
            # Multiply confidence by decay factor
            memory.effective_confidence = memory.confidence * decay_factor

        return sorted(memories, key=lambda m: m.effective_confidence, reverse=True)

    def get_stale_memories(
        self,
        memories: List[TypedMemory],
        threshold: float = 0.1
    ) -> List[TypedMemory]:
        """Find memories that have decayed below threshold."""
        stale = []
        for memory in memories:
            decay = self.calculate_decay(
                memory_type=memory.__class__.__name__.lower(),
                created_at=memory.created_at,
                last_used=memory.last_used,
                use_count=memory.use_count
            )
            if decay < threshold:
                stale.append(memory)
        return stale
```

**Integration with Store:**
```python
# Updated TypedMemoryStore.query()
def query(self, query: str, ..., apply_decay: bool = True) -> List[TypedMemory]:
    results = self._search(...)

    if apply_decay:
        decay = TemporalDecay()
        results = decay.apply_decay(results)

    return results
```

**Files to create:**
- `v2/memory/decay.py` - TemporalDecay class
- `v2/tests/test_decay.py` - Unit tests

**Success criteria:**
- 1-year-old unused pattern has ~25% relevance
- Recently used pattern stays at 90%+ relevance
- Stale memory detection identifies genuinely outdated content

---

### Feature 6: ML Confidence Calibration

**Problem:** Current confidence is simple averaging. A pattern with 3 successes / 1 failure = 75%. But is that better than 30 successes / 10 failures?

**Solution:** Bayesian confidence with outcome weighting.

**Calibration Model:**
```python
# v2/learning/calibration.py

from dataclasses import dataclass
from typing import List, Optional
import math

@dataclass
class OutcomeStats:
    successes: int = 0
    failures: int = 0
    partial: int = 0
    total: int = 0

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.5  # Prior: assume 50% if no data
        return self.successes / self.total

class ConfidenceCalibrator:
    """Bayesian confidence calibration based on outcomes."""

    # Prior parameters (Beta distribution)
    PRIOR_ALPHA = 2  # Equivalent to 2 successes
    PRIOR_BETA = 2   # Equivalent to 2 failures
    # This gives a prior of ~50% with moderate certainty

    def __init__(self, graph: GraphMemory, outcomes: OutcomeDetector):
        self.graph = graph
        self.outcomes = outcomes

    def calculate_confidence(
        self,
        pattern_id: str,
        project: Optional[str] = None
    ) -> float:
        """Calculate calibrated confidence for a pattern.

        Uses Bayesian updating with Beta-Binomial model.
        """
        # Get outcomes linked to this pattern
        stats = self._get_outcome_stats(pattern_id, project)

        # Bayesian posterior mean: (alpha + successes) / (alpha + beta + total)
        alpha = self.PRIOR_ALPHA + stats.successes
        beta = self.PRIOR_BETA + stats.failures + (stats.partial * 0.5)

        posterior_mean = alpha / (alpha + beta)

        # Confidence interval width (uncertainty)
        # Narrower interval = more certain
        n = stats.total + self.PRIOR_ALPHA + self.PRIOR_BETA
        std_dev = math.sqrt(alpha * beta / (n * n * (n + 1)))

        # Adjust confidence based on certainty
        # More data = more trust in the estimate
        certainty_factor = min(1.0, stats.total / 10)  # Caps at 10 outcomes

        # Blend toward prior for low data
        final_confidence = (
            posterior_mean * certainty_factor +
            0.5 * (1 - certainty_factor)  # Prior mean
        )

        return round(final_confidence, 3)

    def _get_outcome_stats(
        self,
        pattern_id: str,
        project: Optional[str] = None
    ) -> OutcomeStats:
        """Get outcome statistics for a pattern."""
        # Find outcomes linked via graph
        edges = self.graph.get_edges(
            to_id=pattern_id,
            relation=RelationType.VALIDATES
        )

        stats = OutcomeStats()
        for edge in edges:
            outcome_node = self.graph.get_node(edge.from_id)
            if not outcome_node or outcome_node.type != MemoryType.OUTCOME:
                continue

            outcome_data = outcome_node.data
            outcome_type = outcome_data.get("outcome_type", "unknown")

            # Filter by project if specified
            if project and outcome_data.get("project") != project:
                continue

            stats.total += 1
            if outcome_type == "success":
                stats.successes += 1
            elif outcome_type == "failure":
                stats.failures += 1
            elif outcome_type == "partial":
                stats.partial += 1

        return stats

    def recalibrate_all(self, project: Optional[str] = None) -> dict:
        """Recalibrate confidence for all patterns.

        Returns:
            Dict with pattern_id -> new_confidence
        """
        patterns = self.graph.find_nodes(type=MemoryType.PATTERN)
        updates = {}

        for pattern in patterns:
            new_confidence = self.calculate_confidence(pattern.id, project)
            old_confidence = pattern.data.get("confidence", 0.5)

            if abs(new_confidence - old_confidence) > 0.01:
                updates[pattern.id] = {
                    "old": old_confidence,
                    "new": new_confidence,
                    "delta": new_confidence - old_confidence
                }
                # Update in graph
                pattern.data["confidence"] = new_confidence
                self.graph.update_node(pattern.id, data=pattern.data)

        return updates

    def get_confidence_report(self) -> dict:
        """Generate report on confidence distribution."""
        patterns = self.graph.find_nodes(type=MemoryType.PATTERN)

        report = {
            "total_patterns": len(patterns),
            "high_confidence": 0,    # > 0.7
            "medium_confidence": 0,  # 0.4 - 0.7
            "low_confidence": 0,     # < 0.4
            "needs_data": 0,         # < 5 outcomes
            "patterns": []
        }

        for pattern in patterns:
            stats = self._get_outcome_stats(pattern.id)
            confidence = self.calculate_confidence(pattern.id)

            if stats.total < 5:
                report["needs_data"] += 1
            elif confidence > 0.7:
                report["high_confidence"] += 1
            elif confidence > 0.4:
                report["medium_confidence"] += 1
            else:
                report["low_confidence"] += 1

            report["patterns"].append({
                "id": pattern.id,
                "name": pattern.name,
                "confidence": confidence,
                "outcomes": stats.total,
                "success_rate": stats.success_rate
            })

        return report
```

**Files to create:**
- `v2/learning/calibration.py` - ConfidenceCalibrator class
- `v2/tests/test_calibration.py` - Unit tests

**Success criteria:**
- 3/1 success ratio gives ~70% confidence
- 30/10 success ratio gives ~75% confidence (more certain)
- New patterns start at 50% (prior)
- Confidence updates automatically when outcomes recorded

---

## Tier 2 Implementation Schedule

### Week 1: Skill Extraction (Feature 4)
- Day 1-2: SkillExtractor class with sequence detection
- Day 3-4: Integration with OutcomeDetector
- Day 5: Tests and edge cases

### Week 2: Temporal Decay (Feature 5)
- Day 1-2: TemporalDecay class
- Day 3: Integration with TypedMemoryStore
- Day 4-5: Tests and tuning half-lives

### Week 3: ML Confidence (Feature 6)
- Day 1-2: ConfidenceCalibrator class
- Day 3: Graph integration for outcome linking
- Day 4-5: Recalibration logic and reporting

### Week 4: Integration & Testing
- Day 1-2: E2E tests for all Tier 2 features
- Day 3-4: Bridge API updates
- Day 5: Documentation

---

## Tier 2 Files to Create

```
v2/learning/
├── skills.py           # Feature 4: Skill extraction
├── calibration.py      # Feature 6: ML confidence

v2/memory/
├── decay.py            # Feature 5: Temporal decay

v2/tests/
├── test_skills.py
├── test_decay.py
├── test_calibration.py
```

---

## Next Steps

1. ~~Create v2/ directory structure~~ ✅
2. ~~Implement Feature 1: Graph Relationships~~ ✅
3. ~~Implement Feature 2: Automated Outcomes~~ ✅
4. ~~Implement Feature 3: Memory Types~~ ✅
5. ~~E2E Testing~~ ✅
6. **Implement Feature 4: Skill Extraction** ⬅️ NEXT
7. **Implement Feature 5: Temporal Decay**
8. **Implement Feature 6: ML Confidence**

Ready to start building.
