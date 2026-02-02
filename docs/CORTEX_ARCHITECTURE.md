# Cortex System Architecture

**Version:** 1.0
**Last Updated:** 2026-02-01

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐   │
│  │  CLI         │    │  Dashboard   │    │  Claude Code Integration     │   │
│  │  bridge.py   │    │  Streamlit   │    │  .claude/instructions.md     │   │
│  │  cli.py      │    │  :8502       │    │                              │   │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┬───────────────┘   │
└─────────┼───────────────────┼───────────────────────────┼───────────────────┘
          │                   │                           │
          └───────────────────┼───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                           INTELLIGENCE LAYER                                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      UnifiedIntelligence                               │ │
│  │              Parallel query aggregation (125ms-4s)                     │ │
│  └─────────────────────────────┬──────────────────────────────────────────┘ │
│                                │                                             │
│     ┌──────────────┬───────────┼───────────┬──────────────┐                 │
│     │              │           │           │              │                 │
│     ▼              ▼           ▼           ▼              ▼                 │
│  ┌──────┐    ┌──────────┐  ┌───────┐  ┌─────────┐  ┌───────────┐           │
│  │ Spec │    │ Session  │  │ Port- │  │ Context │  │ Recommend │           │
│  │  KB  │    │ Manager  │  │ folio │  │  Intel  │  │  Engine   │           │
│  └──────┘    └──────────┘  └───────┘  └─────────┘  └───────────┘           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                          TaskScheduler                                 │ │
│  │              Priority routing: realtime vs batch                       │ │
│  └─────────────────────────────┬──────────────────────────────────────────┘ │
│                                │                                             │
│           ┌────────────────────┼────────────────────┐                       │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│     ┌──────────┐        ┌──────────┐        ┌──────────────┐               │
│     │ TaskQueue│        │ Anomaly  │        │ Anti-Pattern │               │
│     │ (SQLite) │        │ Detector │        │   Detector   │               │
│     └──────────┘        └──────────┘        └──────────────┘               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                            DATA LAYER                                        │
│                                                                              │
│     ~/.cortex/                              ~/.claude/                       │
│     ├── queue/tasks.db                      ├── portfolio/project_index.json│
│     ├── latest_scan.json                    ├── specs/                      │
│     └── logs/                               └── session/context.json        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### User Interfaces

| Component | Responsibility |
|-----------|---------------|
| **bridge.py** | Universal CLI entry point, command routing, output formatting |
| **cli.py** | Extended CLI with status, briefing, next commands |
| **Dashboard** | Visual monitoring, health trends, anomaly alerts |
| **Claude Integration** | Context injection via .claude/instructions.md |

### Intelligence Layer

| Component | Responsibility |
|-----------|---------------|
| **UnifiedIntelligence** | Aggregates all sources in parallel, caching, result formatting |
| **SpecKnowledgeBase** | Semantic similarity search across 73+ indexed specs |
| **SessionManager** | Git-based session context (branch, commits, uncommitted) |
| **PortfolioMemory** | Cross-project patterns, lessons, project metadata |
| **ContextIntelligence** | Predictions and warnings based on current state |
| **RecommendationEngine** | Action suggestions based on all context |

### Orchestration Layer

| Component | Responsibility |
|-----------|---------------|
| **TaskScheduler** | Routes tasks to realtime or batch based on priority/deadline |
| **TaskQueue** | SQLite-backed priority queue with dependency tracking |
| **AnomalyDetector** | Monitors for 7 types of anomalies |
| **AntiPatternDetector** | Detects 3 anti-patterns (shipping gate, context switching, planning gap) |

### Data Layer

| Location | Contents |
|----------|----------|
| `~/.cortex/queue/tasks.db` | Persistent task queue |
| `~/.cortex/latest_scan.json` | Most recent scan results |
| `~/.claude/portfolio/` | Project index, patterns, lessons |
| `~/.claude/specs/` | Indexed specifications for search |
| `~/.claude/session/` | Current session context |

---

## Data Flow

### Query Flow

```
User Command
     │
     ▼
┌──────────┐
│ bridge.py│
└────┬─────┘
     │ parse command
     ▼
┌────────────────────┐
│ UnifiedIntelligence│
└────┬───────────────┘
     │ parallel queries
     ├────────────────────────────────────────────────┐
     │                    │                           │
     ▼                    ▼                           ▼
┌────────┐        ┌─────────────┐           ┌─────────────┐
│Spec KB │        │SessionMgr   │           │PortfolioMem│
│        │        │             │           │             │
│similarity│      │git log      │           │patterns     │
│search   │      │git status   │           │lessons      │
└────┬───┘        └──────┬──────┘           └──────┬──────┘
     │                   │                         │
     └───────────────────┴─────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  IntelligenceResult │
              │  - similar_work     │
              │  - patterns         │
              │  - lessons          │
              │  - recommendations  │
              └─────────────────────┘
                         │
                         ▼
                   JSON Output
```

### Task Flow

```
Task Created
     │
     ▼
┌────────────────┐
│ TaskScheduler  │
└────┬───────────┘
     │ evaluate priority + deadline
     │
     ├─────────────────────────────────────┐
     │                                     │
     ▼                                     ▼
┌──────────────┐                   ┌──────────────┐
│   REALTIME   │                   │    BATCH     │
│              │                   │              │
│ Priority A   │                   │ Priority C   │
│ Deadline <2h │                   │ Deadline >4h │
└──────┬───────┘                   └──────┬───────┘
       │                                  │
       ▼                                  ▼
┌──────────────┐                   ┌──────────────┐
│ Immediate    │                   │ Anthropic    │
│ Execution    │                   │ Batch API    │
│              │                   │ (50% cheaper)│
└──────────────┘                   └──────────────┘
```

---

## Design Decisions

### Why Parallel Query Aggregation?

**Decision:** Query all intelligence sources in parallel using ThreadPoolExecutor.

**Rationale:**
- Individual sources: 50-500ms each
- Sequential: 200-2000ms total
- Parallel: 125-500ms total (4x faster)

**Trade-off:** More complex error handling, but significant latency improvement.

### Why SQLite for Task Queue?

**Decision:** Use SQLite instead of Redis or PostgreSQL.

**Rationale:**
- Zero external dependencies
- Crash recovery built-in
- Works offline
- Single-user workload fits perfectly
- ACID guarantees for task state

**Trade-off:** Not suitable for multi-user, but that's a non-goal.

### Why Batch vs Realtime Routing?

**Decision:** Automatically route tasks to batch API based on priority/deadline.

**Rationale:**
- Batch API is 50% cheaper
- Background tasks can wait
- Deadline-aware prevents missed commitments

**Trade-off:** Added complexity in scheduler, but significant cost savings.

### Why Git-Based Session Context?

**Decision:** Derive session context from git state rather than explicit tracking.

**Rationale:**
- No extra user action required
- Already accurate (git is source of truth)
- Works across tools (not tied to one IDE)
- Resilient to crashes (git persists)

**Trade-off:** Requires git, but all target projects use git.

### Why Lazy Initialization?

**Decision:** Initialize sub-systems only when needed.

**Rationale:**
- Not all commands need all systems
- Faster startup for simple commands
- Graceful degradation if component fails

**Trade-off:** First access is slower, but overall experience is better.

### Why Portfolio-Scoped (Not Project-Scoped)?

**Decision:** Index and query across ALL projects, not just current.

**Rationale:**
- Core value is cross-project intelligence
- Patterns from Project A apply to Project B
- Reduces repeated work
- Enables portfolio health monitoring

**Trade-off:** More data to manage, but essential for value proposition.

---

## Failure Modes and Recovery

### Component Failure

| Component | Failure Mode | Recovery |
|-----------|--------------|----------|
| **SpecKnowledgeBase** | ChromaDB unavailable | Fall back to keyword search |
| **SessionManager** | Git not available | Return empty context |
| **PortfolioMemory** | Index file missing | Create empty index |
| **TaskQueue** | SQLite corrupted | Auto-create new DB |
| **Dashboard** | Streamlit crash | CLI still works |

### Data Corruption

| Location | Recovery |
|----------|----------|
| `tasks.db` | Re-create, tasks lost but can be re-added |
| `project_index.json` | Rebuild from git history |
| `specs/` | Re-index from source files |
| `session/` | Regenerate from git |

### API Failures

| API | Recovery |
|-----|----------|
| Anthropic API | Return cached results or skip AI features |
| Batch API | Queue locally, retry later |

---

## Performance Characteristics

### Response Times

| Operation | Target | Mechanism |
|-----------|--------|-----------|
| Portfolio stats | <500ms | Direct file read |
| Intelligence query | <5s | Parallel + 5min cache |
| Session context | <1s | Git commands |
| Task enqueue | <100ms | SQLite insert |
| Health check | <2s | Git log parsing |

### Memory Usage

| Component | Typical | Maximum |
|-----------|---------|---------|
| bridge.py | 50MB | 200MB |
| ChromaDB | 100MB | 500MB |
| TaskQueue | 5MB | 50MB |
| Dashboard | 100MB | 300MB |

### Storage

| Data | Growth Rate | Retention |
|------|-------------|-----------|
| Tasks | ~1MB/month | Prune completed after 30 days |
| Logs | ~10MB/month | Rotate weekly |
| Specs | ~50MB total | Permanent |
| Index | ~1MB total | Permanent |

---

## Security Considerations

### Data Sensitivity

| Data | Sensitivity | Protection |
|------|-------------|------------|
| API keys | High | .env file, not committed |
| Git history | Medium | Local only |
| Task content | Low | Local SQLite |
| Specs | Low | Read-only access |

### Access Control

- All data stored locally (~/.cortex, ~/.claude)
- No network exposure except optional dashboard
- Dashboard listens on localhost only
- No authentication (single-user system)

---

## Extension Points

### Adding a New Intelligence Source

```python
# 1. Create source class in intelligence/
class NewSource:
    def query(self, request: str) -> SourceResult:
        ...

# 2. Add to UnifiedIntelligence._query_sources()
futures["new_source"] = executor.submit(self._query_new_source, ...)

# 3. Handle result in aggregation
```

### Adding a New CLI Command

```python
# 1. Add subparser in bridge.py
subparsers.add_parser("new-command", ...)

# 2. Create handler function
def cmd_new_command(args):
    ...

# 3. Add to dispatch
commands = {"new-command": cmd_new_command, ...}
```

### Adding a New Anomaly Type

```python
# 1. Add to orchestration/anomaly_detector.py
class AnomalyType(Enum):
    ...
    NEW_ANOMALY = "new_anomaly"

# 2. Implement detection logic
def _detect_new_anomaly(self) -> Optional[Anomaly]:
    ...

# 3. Add to detection pipeline
```

---

## Module Dependencies

```
bridge.py
├── portfolio_memory.py
├── intelligence/
│   ├── unified_intelligence.py
│   │   ├── spec_knowledge_base.py
│   │   ├── session_manager.py
│   │   └── context_intelligence.py
│   ├── adaptive_latency.py
│   └── deep_analysis.py
├── orchestration/
│   ├── task_queue.py
│   ├── scheduler.py
│   └── database.py
├── orchestrator.py
│   ├── ai_intelligence.py
│   ├── goal_parser.py
│   └── recommendation_engine.py
└── cli.py
    ├── formatter.py
    ├── briefing.py
    └── feedback.py
```

---

## Deployment

### Local Development

```bash
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate
python bridge.py portfolio stats
```

### Dashboard

```bash
./launch_dashboard.sh
# or
streamlit run dashboard/app.py --server.port 8502
```

### Automation

```bash
# Daily scan at 8am
./install_automation.sh

# Manual scan
./daily_scan.sh
```
