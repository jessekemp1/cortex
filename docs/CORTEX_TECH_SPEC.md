# Cortex Technical Specification

**Version:** 1.0
**Last Updated:** 2026-02-01
**Status:** Production

---

## Overview

Cortex is a portfolio intelligence platform that provides memory and pattern recognition across multiple development projects. It aggregates context from git history, indexed specifications, and project metadata to generate actionable recommendations.

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              bridge.py                  │
                    │         (Universal CLI Entry)           │
                    └───────────────┬─────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Portfolio   │         │    Unified      │         │  Orchestration  │
│    Memory     │         │  Intelligence   │         │     System      │
│               │         │                 │         │                 │
│ - patterns    │         │ - spec search   │         │ - task queue    │
│ - lessons     │         │ - session ctx   │         │ - scheduling    │
│ - project idx │         │ - predictions   │         │ - batch routing │
└───────────────┘         └─────────────────┘         └─────────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │         Data Storage          │
                    │  ~/.cortex/  ~/.claude/       │
                    └───────────────────────────────┘
```

---

## Core Components

### 1. CortexBridge (`bridge.py`)

Universal interface for all Cortex operations.

**Location:** `/Users/jesse.kemp/Dev/cortex/bridge.py`
**Lines:** ~3500

**Responsibilities:**
- CLI argument parsing and command routing
- Initialization of sub-systems (lazy loading)
- Unified output formatting (JSON/terminal)

**Key Methods:**
```python
class CortexBridge:
    def __init__(self, root_dir: Path = Path("/Users/jesse.kemp/Dev"))
    def read_context(self, project: str) -> Dict
    def query_intelligence(self, request: str, project: str) -> IntelligenceResult
    def get_portfolio_stats(self) -> Dict
```

**CLI Commands:**
| Command | Description |
|---------|-------------|
| `portfolio stats` | Project counts, technologies, patterns |
| `intelligence <query>` | Query all intelligence sources |
| `similar-work <query>` | Semantic search across specs |
| `session-context` | Current session from git |
| `health summary` | Project health metrics |
| `recommendations` | Get next action suggestions |

---

### 2. PortfolioMemory (`portfolio_memory.py`)

Cross-project pattern and lesson storage.

**Location:** `/Users/jesse.kemp/Dev/cortex/portfolio_memory.py`
**Lines:** ~700

**Data Source:** `~/.claude/portfolio/project_index.json`

**Key Methods:**
```python
class PortfolioMemory:
    def get_stats(self, include_health: bool = True) -> Dict
    def get_patterns(self, project: str = None) -> List[Pattern]
    def get_lessons(self, project: str = None) -> List[Lesson]
    def get_project_context(self, project: str) -> ProjectContext
```

**Data Model - project_index.json:**
```json
{
  "meta": {
    "last_updated": "2026-02-01T12:00:00",
    "total_projects": 10
  },
  "projects": {
    "vortex": {
      "priority": "tier1",
      "tech_stack": ["python", "fastapi"],
      "patterns": ["validation-first"],
      "activity_commits_7d": 15
    }
  }
}
```

---

### 3. UnifiedIntelligence (`intelligence/unified_intelligence.py`)

Aggregates context from multiple sources in parallel.

**Location:** `/Users/jesse.kemp/Dev/cortex/intelligence/unified_intelligence.py`
**Lines:** ~1200

**Sources Queried:**
1. SpecKnowledgeBase - Semantic similarity search
2. SessionManager - Git-based session context
3. PortfolioMemory - Patterns and lessons
4. ContextIntelligence - Predictions

**Performance:** 125ms - 4s depending on sources

**Key Methods:**
```python
class UnifiedIntelligence:
    def query(
        self,
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
        use_cache: bool = True,
        parallel: bool = True
    ) -> IntelligenceResult
```

**IntelligenceResult Model:**
```python
@dataclass
class IntelligenceResult:
    query_timestamp: datetime
    query_type: IntelligenceQueryType
    similar_work: List[SimilarWork]
    applicable_patterns: List[Pattern]
    lessons: List[Lesson]
    warnings: List[Warning]
    recommendations: List[Recommendation]
    project_context: Optional[ProjectContext]
    session_context: Optional[SessionContext]
    sources_queried: List[str]
    query_duration_ms: float
```

---

### 4. Orchestration System (`orchestration/`)

Task queue with priority scheduling and batch routing.

**Location:** `/Users/jesse.kemp/Dev/cortex/orchestration/`

**Files:**
| File | Purpose |
|------|---------|
| `task.py` | Task dataclass, priority enum |
| `task_queue.py` | SQLite-backed priority queue |
| `scheduler.py` | Batch vs realtime routing |
| `database.py` | Persistence layer |

**Task Priority Levels:**
- `A` (critical): Always realtime execution
- `B` (important): Batch if deadline > 4h
- `C` (background): Always batch

**Key Operations:**
```python
scheduler = TaskScheduler()
decision = scheduler.enqueue_and_schedule(task)
next_task = scheduler.get_next_realtime_task()
batch_tasks = scheduler.get_next_batch_tasks(limit=10)
```

**Storage:** `~/.cortex/queue/tasks.db` (SQLite)

---

### 5. Intelligence Layers (`intelligence/`)

Five-layer progressive intelligence system.

**Layer Summary:**
| Layer | Component | Status |
|-------|-----------|--------|
| 1 | Project Profiler | Complete |
| 2 | Pattern Memory | Complete |
| 3 | Warning System | Complete |
| 3.5 | Process Monitor | Complete |
| 4 | Recommendations | Complete |
| 5 | Context Injection | Complete |

**Performance Targets:**
- Quick mode: <500ms (for per-prompt injection)
- Deep mode: 2-5s (for analysis commands)

---

## API Surface

### CLI Interface

All commands via `python bridge.py`:

```bash
# Portfolio operations
python bridge.py portfolio stats
python bridge.py portfolio patterns [--project NAME]
python bridge.py portfolio lessons

# Intelligence queries
python bridge.py intelligence "query" --project NAME
python bridge.py similar-work "query" --project NAME

# Session context
python bridge.py session-context [--format terminal|json]

# Health monitoring
python bridge.py health summary --days 7
python bridge.py health project NAME

# Recommendations
python bridge.py recommendations --project NAME
```

### Python API

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Get portfolio statistics
stats = bridge.get_portfolio_stats()

# Query intelligence
result = bridge.query_intelligence(
    request="implement authentication",
    project="vortex"
)

# Get session context
context = bridge.get_session_context()
```

---

## Data Models

### Core Types

```python
# intelligence/models.py

class IntelligenceQueryType(Enum):
    SPEC = "spec"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    RESEARCH = "research"

@dataclass
class Pattern:
    name: str
    description: str
    projects: List[str]
    reference: str
    confidence_score: float
    relevance_score: float

@dataclass
class Lesson:
    title: str
    description: str
    projects: List[str]
    severity: str
    learned_date: datetime

@dataclass
class SimilarWork:
    title: str
    project: str
    similarity_score: float
    file_path: str
    excerpt: str
```

### Orchestration Types

```python
# orchestration/task.py

class TaskPriority(Enum):
    A = "A"  # Critical
    B = "B"  # Important
    C = "C"  # Background

class TaskPhase(Enum):
    QUEUED = "queued"
    INVESTIGATING = "investigating"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Task:
    id: str
    title: str
    description: str
    priority: TaskPriority
    phase: TaskPhase
    deadline: Optional[datetime]
    blocked_by: List[str]
    blocks: List[str]
```

---

## Integration Points

### 1. Claude Code Integration

Cortex provides context via `.claude/instructions.md`:
```
Location: ~/Dev/.claude/instructions.md
Purpose: Auto-loaded for all ~/Dev work
Content: Portfolio patterns, lessons, commands
```

### 2. Git Integration

Session context derived from:
- Current branch name
- Recent commits (7 days)
- Uncommitted changes
- Active project detection

### 3. Batch API Integration

Tasks route to Anthropic Batch API:
```python
# 50% cost reduction for batch-eligible tasks
scheduler.get_next_batch_tasks(limit=10)
```

### 4. Dashboard

Streamlit dashboard at `http://localhost:8502`:
- Real-time status monitoring
- Anomaly detection alerts
- Project health trends

---

## Storage Locations

| Path | Purpose |
|------|---------|
| `~/.cortex/` | Runtime data, queue, cache |
| `~/.cortex/queue/tasks.db` | Task queue (SQLite) |
| `~/.cortex/latest_scan.json` | Most recent scan results |
| `~/.claude/portfolio/` | Portfolio index, patterns |
| `~/.claude/specs/` | Indexed specifications |
| `~/.claude/session/` | Session context |

---

## Dependencies

**Core:**
```
anthropic>=0.18.0
pydantic>=2.0
structlog>=24.0
```

**Intelligence:**
```
chromadb>=0.4.0  # Vector similarity (optional)
psutil>=5.9.0    # Process monitoring
```

**Storage:**
```
sqlite3 (builtin)
```

**Installation:**
```bash
pip install -r requirements-lock.txt
```

---

## Configuration

Environment variables (`.env`):
```bash
ANTHROPIC_API_KEY=sk-...
MODEL_NAME=claude-3-5-sonnet-20241022
MAX_TOKENS=4096
CORTEX_ROOT=/Users/jesse.kemp/Dev/cortex
```

---

## Testing

```bash
# Full test suite
pytest tests/ -v

# Specific components
pytest tests/test_orchestrator.py -v
pytest tests/integration/ -v

# Coverage
pytest --cov=. --cov-report=html
```

**Test Count:** 35+ test files across unit, integration, e2e

---

## Performance Characteristics

| Operation | Target | Actual |
|-----------|--------|--------|
| Portfolio stats | <500ms | ~300ms |
| Intelligence query | <5s | 125ms-4s |
| Session context | <1s | ~500ms |
| Task enqueue | <100ms | ~50ms |
| Deep analysis | <5s | 2-5s |

---

## Known Limitations

1. **Similarity search** requires chromadb; falls back to keyword matching
2. **Process monitor** requires psutil; gracefully degrades if missing
3. **Batch routing** assumes Anthropic API availability
4. **Git operations** required for session context

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `bridge.py` | 3500 | Universal CLI |
| `cli.py` | 4000 | Full CLI interface |
| `orchestrator.py` | 500 | Combines subsystems |
| `portfolio_memory.py` | 700 | Portfolio patterns/lessons |
| `intelligence/unified_intelligence.py` | 1200 | Source aggregation |
| `orchestration/task_queue.py` | 500 | Priority queue |
| `orchestration/scheduler.py` | 350 | Batch routing |
