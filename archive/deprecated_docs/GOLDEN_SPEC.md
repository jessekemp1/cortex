# Cortex: Golden Specification

*Complete Engineering Documentation*

**Version:** 1.0.0
**Last Updated:** January 2026
**Status:** Production

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Core Architecture](#3-core-architecture)
4. [Universal Bridge API](#4-universal-bridge-api)
5. [Memory Systems](#5-memory-systems)
6. [Learning System](#6-learning-system)
7. [Batch Processing](#7-batch-processing)
8. [CLI Reference](#8-cli-reference)
9. [MCP Server](#9-mcp-server)
10. [Work Absorber](#10-work-absorber)
11. [Integration Guide](#11-integration-guide)
12. [Performance Characteristics](#12-performance-characteristics)
13. [Security Model](#13-security-model)
14. [Appendices](#appendices)

---

## 1. Executive Summary

### What is Cortex?

Cortex is a **meta-intelligence layer** for AI-assisted development. It sits above individual AI tools (Claude Code, Cursor, Copilot) and provides:

- **Memory**: What happened before, across projects and sessions
- **Context**: What's relevant right now, from a portfolio of work
- **Learning**: What worked last time, from tracked outcomes
- **Strategy**: What should happen next, via smart recommendations
- **Coordination**: How multiple AI agents work together

### The Core Insight

> "AI tools are individually brilliant but collectively amnesiac."

Every AI session starts fresh. There's no learning from outcomes, no awareness of parallel work, no strategic prioritization. Cortex fills this gap by providing the meta-layer that transforms stateless AI tools into a compound intelligence system.

### Key Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| Recommendation Accuracy | 85%+ | Tracked via feedback loop |
| Context Retrieval | <200ms | P95 for knowledge base queries |
| Batch Cost Savings | 50% | Via Anthropic Batch API |
| Portfolio Coverage | 5+ projects | Simultaneous awareness |
| Learning Convergence | ~50 outcomes | Confidence calibration stabilizes |

---

## 2. System Overview

### Design Philosophy

Cortex follows three guiding principles:

1. **Transparency over Magic**: Every recommendation explains its rationale. Every decision is traceable. Users should understand why Cortex suggests what it suggests.

2. **Compound Intelligence**: Each session should make the next one better. Outcomes feed back into recommendations. Patterns emerge from accumulated data.

3. **Universal Integration**: Any AI tool should be able to connect. The Bridge API is protocol-agnostic. MCP, REST, and CLI all use the same underlying intelligence.

### Architecture Principles

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CORTEX ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│    │ Claude Code │  │   Cursor    │  │   Other AI  │   CLIENTS     │
│    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│           │                │                │                       │
│           └────────────────┼────────────────┘                       │
│                            │                                        │
│                    ┌───────▼───────┐                                │
│                    │  BRIDGE API   │  Universal Interface           │
│                    │  (CortexBridge)│                               │
│                    └───────┬───────┘                                │
│                            │                                        │
│    ┌───────────────────────┼───────────────────────┐               │
│    │                       │                       │                │
│    ▼                       ▼                       ▼                │
│ ┌──────────────┐   ┌──────────────┐   ┌──────────────┐             │
│ │ LAYER 1      │   │ LAYER 2      │   │ LAYER 3      │             │
│ │ Project      │   │ Memory &     │   │ Warnings &   │             │
│ │ Analysis     │   │ Context      │   │ Metrics      │             │
│ └──────────────┘   └──────────────┘   └──────────────┘             │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            ▼                                        │
│                    ┌──────────────┐                                 │
│                    │ LAYER 4      │                                 │
│                    │ Smart        │                                 │
│                    │ Recommendations│                               │
│                    └──────────────┘                                 │
│                            │                                        │
│                    ┌───────▼───────┐                                │
│                    │   LEARNING    │  Feedback → Calibration        │
│                    │   SYSTEM      │                                │
│                    └───────────────┘                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
cortex/
├── cli.py                    # Main CLI (2100+ lines, 20+ commands)
├── bridge.py                 # Universal Bridge API (2200+ lines)
├── orchestrator.py           # Core orchestrator (545 lines)
├── learning.py               # Learning system (322 lines)
├── briefing.py               # Daily briefing generator
├── scheduler.py              # Cron-style scheduling
├── formatter.py              # Output formatting
├── feedback.py               # Feedback logging
├── mcp_server.py             # MCP protocol server
├── work_absorber.py          # Work detection and plan correlation
├── golden_spec_validator.py  # Spec compliance validation
├── spec_generator.py         # New spec generation
├── batch/                    # Batch API integration
│   ├── batch_config.py       # Feature flags
│   ├── batch_fallback.py     # Fallback handlers
│   └── tests/
├── integration/              # External integrations
│   ├── git_tracker.py        # Git state tracking
│   ├── git_sync.py           # Git synchronization
│   ├── feedback_loop.py      # Bidirectional feedback
│   └── history_analyzer.py   # Execution history
├── intelligence/             # AI intelligence modules
│   └── process_monitor.py    # System resource monitoring
├── agents/                   # Multi-agent coordination
│   └── integration/
│       ├── team_coordinator.py
│       └── base_coordination_agent.py
├── skills/                   # Skill-based capabilities
└── docs/                     # Documentation
```

---

## 3. Core Architecture

### 3.1 Layer 1: Project Analysis

**Purpose**: Understand the current state of all projects in the portfolio.

**Implementation**: `orchestrator.py` - `CortexOrchestrator`

```python
class CortexOrchestrator:
    """Core orchestrator combining project scanning, goal parsing,
    and recommendation generation."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.project_scanner = ProjectScanner(root_dir)
        self.goal_parser = GoalParser()
        self.recommendation_engine = RecommendationEngine()
        self.context_intelligence = ContextIntelligence()
```

**Data Collected**:
- Git activity (commits, branches, PRs)
- Project structure (files, dependencies)
- Goal files (ACTION_PLAN.md, GOLDEN_SPEC.md)
- Recent changes (last 7/30 days)

**Key Metrics**:
- `total_projects`: All detected projects
- `active_projects`: 3+ commits in 7 days
- `recent_projects`: Any commits in 7 days
- `dormant_projects`: Only commits in 30 days

### 3.2 Layer 2: Memory & Context

**Purpose**: Provide relevant context from accumulated knowledge.

**Components**:

1. **Portfolio Memory**: Project-level patterns and history
2. **Session Memory**: Current session context
3. **Spec Knowledge Base**: Accumulated specifications and decisions
4. **Execution History**: What was tried and what happened

**Context Retrieval** (from `bridge.py`):

```python
def get_context(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve context items relevant to query.

    Sources:
    - Portfolio memory (project patterns)
    - Session memory (current work)
    - Spec knowledge base (decisions)
    - Execution history (outcomes)

    Returns:
        List of context items with relevance scores
    """
```

### 3.3 Layer 3: Warnings & Metrics

**Purpose**: Track progress and identify issues.

**Implementation**: `metrics_tracker.py`

**Four Core Metrics**:

| Metric | Description | Target |
|--------|-------------|--------|
| **Velocity** | Work items completed per week | Stable or improving |
| **Mistakes** | Failed attempts / corrections | Decreasing |
| **Calibration** | Prediction accuracy | >80% |
| **ROI** | Value delivered / time spent | Positive trend |

**Warning Types**:

1. **Blockers**: Issues preventing progress
2. **Staleness**: Work not touched in >7 days
3. **Drift**: Actual work differs from plan
4. **Dependencies**: Waiting on external factors

### 3.4 Layer 4: Smart Recommendations

**Purpose**: Generate actionable next steps.

**Implementation**: `recommendation_engine.py`

**Recommendation Structure**:

```python
@dataclass
class Recommendation:
    id: str                      # Unique identifier
    type: str                    # next_action, blocker, quick_win, etc.
    priority: str                # high, medium, low
    title: str                   # Brief description
    description: str             # Detailed actions
    rationale: str               # Why this recommendation
    estimated_effort: str        # Time estimate
    estimated_impact: str        # Expected outcome
    prerequisites: List[str]     # What must be true first
    related_goals: List[str]     # Connected goals
    related_projects: List[str]  # Connected projects
    confidence: float            # 0.0 to 1.0
```

**Recommendation Types**:

| Type | Trigger | Example |
|------|---------|---------|
| `next_action` | Highest priority work | "Complete authentication module" |
| `blocker` | Blocked goal detected | "Resolve API dependency before continuing" |
| `quick_win` | Low effort, high value | "Fix typo in production config" |
| `context_switch` | Current work stalled | "Switch to VortexV2 while waiting on review" |
| `maintenance` | Tech debt detected | "Update deprecated dependencies" |

---

## 4. Universal Bridge API

### Overview

The Bridge API (`bridge.py`, 2200+ lines) is the central nervous system of Cortex. It provides a single interface for any AI agent to interact with Cortex intelligence.

### Core Interface

```python
class CortexBridge:
    """Universal interface for AI agent integration.

    Design: Single entry point for all intelligence operations.
    Pattern: Facade over multiple specialized systems.
    """

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path("~/Dev")
        self.orchestrator = CortexOrchestrator(root_dir)
        self.learning = LearningSystem()
        self.portfolio_memory = PortfolioMemory()
        self.batch_manager = BatchManager()
```

### Method Categories

#### Context Methods

```python
# Get relevant context for a query
context = bridge.get_context("authentication flow", limit=10)

# Get session-specific context
session_ctx = bridge.get_session_context(session_id="abc123")

# Get project-specific context
project_ctx = bridge.get_project_context(project="VortexV2")
```

#### Recommendation Methods

```python
# Get next recommended action
recommendation = bridge.get_recommendation(project="VortexV2")

# Get multiple recommendations
recommendations = bridge.get_recommendations(limit=5)

# Inject external recommendation
bridge.inject_recommendation(
    title="Optimize database queries",
    rationale="Current queries average 200ms",
    priority="high",
    related_project="VortexV2"
)
```

#### Execution Methods

```python
# Record execution start
bridge.start_execution(recommendation_id="rec_123")

# Record execution outcome
bridge.record_outcome(
    recommendation_id="rec_123",
    outcome="success",  # success, partial, failed
    notes="Completed in 30 minutes"
)

# Trigger automated action
result = bridge.trigger_action(
    agent_id="test_runner",
    payload={"project": "VortexV2", "suite": "unit"}
)
```

#### Intelligence Methods

```python
# Get learning metrics
metrics = bridge.get_learning_metrics()

# Get confidence calibration
calibration = bridge.get_confidence_calibration()

# Get pattern insights
patterns = bridge.get_outcome_patterns()
```

#### Portfolio Methods

```python
# Get portfolio overview
portfolio = bridge.get_portfolio_status()

# Get project health
health = bridge.get_project_health(project="VortexV2")

# Get cross-project dependencies
deps = bridge.get_project_dependencies()
```

#### Batch Methods

```python
# Submit batch research request
batch_id = bridge.submit_batch_research(
    queries=["How to optimize React renders?", "Redis caching patterns"],
    callback_url="http://localhost:8000/callback"
)

# Check batch status
status = bridge.get_batch_status(batch_id)

# Get batch results
results = bridge.get_batch_results(batch_id)
```

#### Planning Methods

```python
# Create execution plan
plan = bridge.create_plan(
    goal="Implement user authentication",
    constraints=["Use existing auth library", "Timeline: 2 days"]
)

# Validate plan against spec
validation = bridge.validate_plan_against_spec(plan, spec_path="AUTH_SPEC.md")
```

### Return Types

All Bridge methods return structured data:

```python
# Success response
{
    "success": True,
    "data": {...},
    "metadata": {
        "timestamp": "2026-01-01T10:00:00Z",
        "latency_ms": 45
    }
}

# Error response
{
    "success": False,
    "error": {
        "code": "CONTEXT_NOT_FOUND",
        "message": "No context available for query",
        "recoverable": True
    }
}
```

---

## 5. Memory Systems

### 5.1 Portfolio Memory

**Purpose**: Long-term memory across all projects.

**Storage**: `~/.claude/portfolio/`

**Data Model**:

```python
@dataclass
class ProjectMemory:
    project_name: str
    first_seen: datetime
    last_activity: datetime
    total_sessions: int
    successful_patterns: List[Pattern]
    failed_patterns: List[Pattern]
    common_contexts: List[str]
    key_decisions: List[Decision]
```

**Persistence**:

```
~/.claude/portfolio/
├── memory.json           # Portfolio-level memory
├── metrics.json          # Tracked metrics over time
├── outcomes.json         # Historical outcomes
└── projects/
    ├── vortexv2.json     # Project-specific memory
    └── alpha_arena.json
```

### 5.2 Session Memory

**Purpose**: Context within a single work session.

**Lifecycle**: Created on session start, persisted on session end.

**Data Model**:

```python
@dataclass
class SessionMemory:
    session_id: str
    started_at: datetime
    project_focus: Optional[str]
    goals_pursued: List[str]
    recommendations_shown: List[str]
    recommendations_followed: List[str]
    outcomes_recorded: List[Outcome]
    context_queries: List[str]
```

### 5.3 Spec Knowledge Base

**Purpose**: Accumulated decisions and specifications.

**Sources**:
- `*_SPEC.md` files
- `GOLDEN_SPEC.md` files
- `ARCHITECTURE.md` files
- `ACTION_PLAN.md` files

**Indexing**: Full-text search with section extraction.

### 5.4 Feedback Memory

**Purpose**: Track what was recommended and what happened.

**Storage**: `~/.claude/portfolio/outcomes.json`

**Schema**:

```python
@dataclass
class OutcomeRecord:
    recommendation_id: str
    recommendation_type: str
    recommendation_title: str
    priority: str
    confidence: float
    followed: bool
    outcome: str  # success, partial, failed, unknown
    notes: Optional[str]
    timestamp: datetime
    context: Dict[str, Any]
```

---

## 6. Learning System

### Overview

The Learning System (`learning.py`, 322 lines) tracks recommendation outcomes and adjusts future recommendations based on historical performance.

### Core Class

```python
class LearningSystem:
    """Learn from recommendation outcomes.

    Capabilities:
    - Track outcome success rates by recommendation type
    - Calibrate confidence based on historical accuracy
    - Identify patterns in successful vs failed recommendations
    - Adjust priority based on past performance
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".claude/portfolio/outcomes.json"
        self.outcomes: List[OutcomeRecord] = self._load_outcomes()
```

### Learning Metrics

```python
@dataclass
class LearningMetrics:
    total_outcomes: int
    followed_count: int
    success_rate: float        # Successful / Followed
    partial_rate: float        # Partial success / Followed
    failed_rate: float         # Failed / Followed
    recommendation_accuracy: float  # How often recommendations were followed
    confidence_calibration: Dict[str, float]  # By confidence bucket
    outcome_patterns: Dict[str, PatternStats]  # By recommendation type
```

### Confidence Calibration

The system tracks how well confidence scores predict success:

```python
def get_confidence_calibration(self) -> Dict[str, float]:
    """Return success rate by confidence bucket.

    Example output:
    {
        "0.9-1.0": 0.92,  # 92% success for high-confidence recs
        "0.8-0.9": 0.85,
        "0.7-0.8": 0.71,
        "0.6-0.7": 0.58,
        "0.5-0.6": 0.45,
        "0.0-0.5": 0.31
    }
    """
```

**Interpretation**: If 0.8-0.9 confidence recommendations succeed 85% of the time, the system is well-calibrated. If they succeed only 50%, confidence scores are inflated.

### Historical Adjustment

```python
def adjust_confidence_based_on_history(
    self,
    recommendation: Recommendation
) -> float:
    """Adjust confidence based on historical performance.

    Factors:
    - Success rate for this recommendation type
    - Success rate for this project
    - Time of day / day of week patterns
    - Similar past recommendations

    Returns:
        Adjusted confidence score
    """
```

### Outcome Patterns

```python
def get_outcome_patterns(self) -> Dict[str, PatternStats]:
    """Identify patterns in outcomes by recommendation type.

    Returns:
        {
            "next_action": {
                "total": 45,
                "followed": 40,
                "success_rate": 0.85,
                "avg_confidence": 0.78,
                "common_projects": ["VortexV2", "Cortex"]
            },
            "quick_win": {
                "total": 20,
                "followed": 18,
                "success_rate": 0.94,
                "avg_confidence": 0.82,
                "common_projects": ["Cortex"]
            }
        }
    """
```

---

## 7. Batch Processing

### Overview

Cortex integrates with the Anthropic Batch API for cost-effective processing of non-urgent requests.

**Cost Savings**: 50% reduction compared to standard API calls
**Turnaround**: Up to 24 hours for batch completion

### Configuration

```python
# batch/batch_config.py

class BatchConfig:
    """Batch API configuration with feature flags."""

    @classmethod
    def is_batch_enabled(cls, feature: str) -> bool:
        """Check if batch is enabled for a feature.

        Features: research, recommendations, learning, decisions

        Environment variables:
        - CORTEX_BATCH_RESEARCH_ENABLED=true
        - CORTEX_BATCH_RECOMMENDATIONS_ENABLED=true
        """
        env_var = f"CORTEX_BATCH_{feature.upper()}_ENABLED"
        return os.getenv(env_var, "false").lower() == "true"
```

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CORTEX_BATCH_MAX_REQUESTS` | 10,000 | Max requests per batch |
| `CORTEX_BATCH_TIMEOUT_MINUTES` | 1440 (24h) | Max wait time |
| `CORTEX_BATCH_RETRY_ATTEMPTS` | 3 | Retries on failure |
| `CORTEX_BATCH_FALLBACK_ON_ERROR` | true | Fall back to sequential |
| `CORTEX_BATCH_POLL_INTERVAL` | 5 | Status check interval (seconds) |
| `CORTEX_BATCH_CACHE_HOURS` | 24 | Cache batch results |

### Usage Example

```python
# Submit batch research
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Submit batch (requires CORTEX_BATCH_RESEARCH_ENABLED=true)
batch_id = bridge.submit_batch_research(
    queries=[
        "Best practices for FastAPI middleware",
        "Optimizing PostgreSQL queries for time-series",
        "React state management patterns 2025"
    ]
)

# Check status
status = bridge.get_batch_status(batch_id)
# Returns: {"status": "processing", "progress": "2/3", "eta_minutes": 15}

# Get results when complete
results = bridge.get_batch_results(batch_id)
```

### Fallback Behavior

When batch processing fails:

1. **Retry**: Attempt up to `CORTEX_BATCH_RETRY_ATTEMPTS` times
2. **Fallback**: If `CORTEX_BATCH_FALLBACK_ON_ERROR=true`, process sequentially
3. **Cache**: Cache results for `CORTEX_BATCH_CACHE_HOURS` to prevent re-processing

---

## 8. CLI Reference

### Installation

```bash
# Add to shell profile
alias cortex='python3 /path/to/cortex/cli.py'

# Or create symlink
ln -s /path/to/cortex/cli.py /usr/local/bin/cortex
```

### Command Overview

| Command | Description |
|---------|-------------|
| `cortex next` | Get next recommended action |
| `cortex status` | Show portfolio status |
| `cortex health` | Show system health |
| `cortex briefing` | Generate daily briefing |
| `cortex execute` | Execute a recommendation |
| `cortex feedback` | Log outcome feedback |
| `cortex learn` | Show learning metrics |
| `cortex git` | Show Git/GitHub status |
| `cortex sync` | Synchronize Git state |
| `cortex check` | Validate spec compliance |
| `cortex draft` | Generate new spec |
| `cortex batch` | Batch task management |
| `cortex work` | Work absorber commands |
| `cortex process` | System monitoring |
| `cortex skill` | Execute skills |
| `cortex dashboard` | Show symbiosis dashboard |
| `cortex notify` | Send notifications |
| `cortex schedule` | Schedule recommendations |

### Detailed Command Reference

#### `cortex next`

Get next recommended action.

```bash
cortex next                    # Get top recommendation
cortex next vortexv2           # Filter by project
cortex next --with-context     # Include context predictions
cortex next --json             # JSON output
cortex next --limit 5          # Show 5 alternatives
```

**Output**:
```
╔══════════════════════════════════════════════════════════════════╗
║                    CORTEX - NEXT ACTION                          ║
╚══════════════════════════════════════════════════════════════════╝

🎯 PRIMARY RECOMMENDATION

[HIGH] Complete ensemble weight optimization
Type: next_action | Confidence: 0.85

Rationale:
  Ensemble system is ready for weight tuning based on 45-day validation.

Estimated Effort: 2-3 hours
Impact: +5-10% forecast accuracy

Related:
  Projects: VortexV2
  Goals: Improve forecast accuracy to 90%+
```

#### `cortex briefing`

Generate comprehensive daily briefing.

```bash
cortex briefing                # Text format
cortex briefing --format=json  # JSON output
cortex briefing --no-color     # Plain text
```

**Output**:
```
╔══════════════════════════════════════════════════════════════════╗
║              CORTEX DAILY BRIEFING - January 1, 2026             ║
╚══════════════════════════════════════════════════════════════════╝

📊 PORTFOLIO PULSE

Active Projects: 5
  VortexV2:     8 commits (↑ active)
  Cortex:       4 commits (stable)
  Alpha Arena:  2 commits (stable)

Goals In Progress: 3
Blockers: 1

🎯 PRIORITY ACTIONS

1. [HIGH] Fix ECMWF data loading timeout
   Blocking forecast generation for European regions

2. [MEDIUM] Complete API documentation
   Needed before external beta launch

📈 PATTERNS & INSIGHTS

Most productive hours: 9-11 AM, 2-4 PM
Common context switches: VortexV2 ↔ Cortex
Success rate this week: 87%
```

#### `cortex learn`

Show learning metrics and patterns.

```bash
cortex learn
```

**Output**:
```
╔══════════════════════════════════════════════════════════════════╗
║                 CORTEX - LEARNING METRICS                        ║
╚══════════════════════════════════════════════════════════════════╝

📊 OVERALL METRICS
────────────────
Total Outcomes: 127
Followed Recommendations: 98
Success Rate: 87.8%
Partial Success: 8.2%
Failed: 4.1%
Recommendation Accuracy: 77.2%

🎯 CONFIDENCE CALIBRATION
────────────────
How well do confidence scores predict success?

  0.9-1.0: ████████████████████ 94%
  0.8-0.9: █████████████████░░░ 86%
  0.7-0.8: ██████████████░░░░░░ 72%
  0.6-0.7: ██████████░░░░░░░░░░ 55%
  0.5-0.6: ██████░░░░░░░░░░░░░░ 38%

📈 OUTCOME PATTERNS BY TYPE
────────────────
  next_action
    Total: 45, Followed: 40
    Success Rate: 85%
    Avg Confidence: 0.78

  quick_win
    Total: 20, Followed: 18
    Success Rate: 94%
    Avg Confidence: 0.82
```

#### `cortex work`

Work absorber commands for tracking actual work vs plans.

```bash
cortex work absorb             # Run absorption cycle
cortex work status             # Show absorber status
cortex work items              # List work items
cortex work items --status orphaned  # Show unplanned work
cortex work drift              # Show plan drift
cortex work drift --resolve ID # Resolve drift
cortex work report             # Generate report
```

#### `cortex batch`

Batch task scheduling and execution.

```bash
cortex batch add "pytest tests/" --type test --priority high
cortex batch list
cortex batch status
cortex batch schedule          # Schedule pending tasks
cortex batch run               # Execute scheduled tasks
cortex batch cancel TASK_ID
cortex batch logs TASK_ID
cortex batch daemon start      # Start background daemon
cortex batch daemon stop
cortex batch daemon status
```

---

## 9. MCP Server

### Overview

The MCP (Model Context Protocol) Server enables integration with Cursor, Claude Code, and other MCP-compatible tools.

**Protocol**: JSON-RPC 2.0 over Stdio
**Implementation**: `mcp_server.py`

### Starting the Server

```bash
# Direct execution
python3 cortex/mcp_server.py

# Via Cursor/Claude Code configuration
# Add to MCP server config
```

### Capabilities

#### Resources

```json
{
  "uriTemplate": "cortex://context/{query}",
  "name": "Cortex Context",
  "description": "Get context from Cortex Brain",
  "mimeType": "application/json"
}
```

**Example**:
```
cortex://context/authentication%20flow
```

Returns relevant context items from portfolio memory, specs, and history.

#### Tools

**inject_recommendation**

```json
{
  "name": "inject_recommendation",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "rationale": {"type": "string"},
      "priority": {"type": "string", "enum": ["high", "medium", "low"]},
      "related_project": {"type": "string"}
    },
    "required": ["title", "rationale"]
  }
}
```

**trigger_action**

```json
{
  "name": "trigger_action",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id": {"type": "string"},
      "payload": {"type": "object"}
    },
    "required": ["agent_id"]
  }
}
```

### Request/Response Format

**Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "inject_recommendation",
    "arguments": {
      "title": "Optimize database queries",
      "rationale": "Current queries average 200ms",
      "priority": "high"
    }
  }
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"success\": true}"
      }
    ]
  }
}
```

---

## 10. Work Absorber

### Overview

The Work Absorber (`work_absorber.py`) detects actual work being done and correlates it with existing plans to identify drift.

### Core Concept

> "Plans are hypotheses. Work is evidence."

The Work Absorber:
1. **Detects** work signals (git commits, file changes, etc.)
2. **Absorbs** signals into work items
3. **Correlates** work items with plan steps
4. **Identifies** drift when work doesn't match plans

### Work Signals

| Signal Type | Source | Description |
|-------------|--------|-------------|
| `git_commit` | Git history | Commits with messages |
| `file_change` | File system | New/modified files |
| `test_run` | Test results | Test execution outcomes |
| `build` | Build system | Build success/failure |
| `deploy` | Deployment | Deployment events |

### Work Items

```python
@dataclass
class WorkItem:
    id: str
    project: str
    title: str
    status: WorkStatus  # detected, absorbed, correlated, orphaned
    signal_count: int
    files_touched: List[str]
    scope: Optional[str]
    plan_step_id: Optional[str]
    correlation_confidence: float
    first_seen: datetime
    last_activity: datetime
```

### Drift Detection

When work doesn't match plans, drift is detected:

```python
@dataclass
class PlanDrift:
    id: str
    drift_type: DriftType  # unplanned_work, missing_work, scope_creep
    severity: str  # info, warning, critical
    project: str
    description: str
    suggested_action: str
```

**Drift Types**:

| Type | Description | Example |
|------|-------------|---------|
| `unplanned_work` | Work with no matching plan step | "Found 15 commits for 'refactor auth' but no auth refactor in plan" |
| `missing_work` | Plan step with no work signals | "Plan step 'Setup CI/CD' has no associated work in 14 days" |
| `scope_creep` | Work exceeding plan scope | "Auth implementation touched 25 files vs planned 8" |

### CLI Usage

```bash
# Run absorption cycle
cortex work absorb
cortex work absorb --project VortexV2
cortex work absorb --since 7d

# View status
cortex work status

# List work items
cortex work items
cortex work items --status orphaned
cortex work items --project VortexV2

# View and resolve drift
cortex work drift
cortex work drift --resolve drift_123 --notes "Intentional scope expansion"

# Generate report
cortex work report --days 30
```

---

## 11. Integration Guide

### 11.1 Claude Code Integration

**Via MCP**:

Add to Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python3",
      "args": ["/path/to/cortex/mcp_server.py"]
    }
  }
}
```

**Via Hooks**:

```bash
# In .claude/hooks/
cat > session_start.sh << 'EOF'
#!/bin/bash
python3 /path/to/cortex/cli.py briefing --format=json
EOF
chmod +x session_start.sh
```

### 11.2 Project Integration

**Golden Spec Validation**:

Each project can have a `GOLDEN_SPEC.md` following the 7-phase methodology:

1. Deep Understanding
2. Outcome Definition
3. Outcome Validation
4. Solution Design
5. Solution-Outcome Alignment
6. Implementation Planning
7. Success Verification

Validate with:
```bash
cortex check MyProject
```

**ACTION_PLAN.md Structure**:

```markdown
# ACTION_PLAN

## Goals

### A. Critical (P0)
- [ ] Goal 1 description

### B. Important (P1)
- [ ] Goal 2 description

### C. Nice to Have (P2)
- [ ] Goal 3 description

## Blockers
- Blocker 1 description
```

### 11.3 Python Integration

```python
from cortex.bridge import CortexBridge

# Initialize
bridge = CortexBridge(root_dir=Path("/path/to/workspace"))

# Get recommendations
recommendation = bridge.get_recommendation()
print(f"Next: {recommendation.title}")

# Record outcome
bridge.record_outcome(
    recommendation_id=recommendation.id,
    outcome="success",
    notes="Completed as expected"
)

# Query context
context = bridge.get_context("how does authentication work")
for item in context:
    print(f"- {item['title']}: {item['content'][:100]}...")
```

---

## 12. Performance Characteristics

### Latency Targets

| Operation | Target | Actual P95 |
|-----------|--------|------------|
| `get_recommendation()` | <500ms | 280ms |
| `get_context()` | <200ms | 120ms |
| `record_outcome()` | <100ms | 45ms |
| `briefing` generation | <2s | 1.4s |
| Portfolio scan | <10s | 6.2s |

### Memory Usage

| Component | Typical | Maximum |
|-----------|---------|---------|
| CLI process | 80MB | 200MB |
| MCP server | 60MB | 150MB |
| Portfolio memory | 5MB | 50MB |

### Scalability

| Metric | Tested | Limit |
|--------|--------|-------|
| Projects | 20 | 100+ |
| Outcomes | 500 | 10,000+ |
| Session history | 1 year | Unlimited (with pruning) |
| Concurrent sessions | 5 | 20 |

### Optimization Strategies

1. **Lazy Loading**: Project data loaded on-demand
2. **Caching**: Context queries cached for 5 minutes
3. **Incremental Updates**: Portfolio scan detects changes
4. **Batch Processing**: Non-urgent work batched for 50% cost savings

---

## 13. Security Model

### Data Storage

All data stored locally:
- `~/.claude/portfolio/` - Portfolio memory
- `<project>/.cortex/` - Project-specific data
- No cloud sync by default

### Secrets Handling

- API keys via environment variables only
- Never logged or stored in memory files
- Spec files scanned for accidental secret commits

### Access Control

- File system permissions apply
- No authentication layer (single-user design)
- MCP server binds to localhost only

### Audit Trail

All operations logged:
```
~/.claude/portfolio/audit.log
```

Format:
```
2026-01-01T10:00:00Z INFO recommendation_shown id=rec_123 confidence=0.85
2026-01-01T10:05:00Z INFO outcome_recorded id=rec_123 outcome=success
```

---

## Appendices

### A. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CORTEX_ROOT_DIR` | `~/Dev` | Workspace root |
| `CORTEX_BATCH_*_ENABLED` | `false` | Batch feature flags |
| `CORTEX_LOG_LEVEL` | `INFO` | Logging verbosity |
| `ANTHROPIC_API_KEY` | - | Required for batch API |

### B. File Formats

**outcomes.json**:
```json
{
  "outcomes": [
    {
      "recommendation_id": "rec_123",
      "recommendation_type": "next_action",
      "recommendation_title": "Complete auth module",
      "priority": "high",
      "confidence": 0.85,
      "followed": true,
      "outcome": "success",
      "notes": "Completed in 2 hours",
      "timestamp": "2026-01-01T10:00:00Z",
      "context": {
        "project": "VortexV2",
        "session_id": "session_abc"
      }
    }
  ]
}
```

**metrics.json**:
```json
{
  "velocity": {
    "weekly": [12, 15, 14, 18, 16],
    "trend": "stable"
  },
  "calibration": {
    "0.9-1.0": 0.92,
    "0.8-0.9": 0.85
  },
  "by_project": {
    "VortexV2": {"outcomes": 45, "success_rate": 0.87},
    "Cortex": {"outcomes": 32, "success_rate": 0.91}
  }
}
```

### C. Error Codes

| Code | Meaning | Recovery |
|------|---------|----------|
| `CONTEXT_NOT_FOUND` | No context for query | Broaden query |
| `PROJECT_NOT_FOUND` | Unknown project | Check project name |
| `BATCH_TIMEOUT` | Batch processing timeout | Wait and retry |
| `OUTCOME_INVALID` | Invalid outcome value | Use: success/partial/failed |
| `CONFIG_MISSING` | Required config not set | Set environment variable |

### D. Glossary

| Term | Definition |
|------|------------|
| **Bridge** | Universal API for AI agent integration |
| **Briefing** | Daily summary of portfolio state and priorities |
| **Calibration** | Accuracy of confidence scores |
| **Drift** | Deviation between planned and actual work |
| **Golden Spec** | Comprehensive project specification document |
| **MCP** | Model Context Protocol (AI tool integration standard) |
| **Outcome** | Result of following a recommendation |
| **Portfolio** | Collection of tracked projects |
| **Recommendation** | Suggested next action with rationale |
| **Work Absorber** | System for detecting and correlating actual work |

---

*This specification is maintained alongside the Cortex codebase. For the latest version, see `cortex/docs/GOLDEN_SPEC.md`.*
