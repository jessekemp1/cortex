# Cortex Architecture

**System**: Strategic AI Orchestrator and Workspace Intelligence Hub
**Domain**: Infrastructure / Developer Productivity
**Last Updated**: 2025-12-23

---

## System Overview

Cortex is the central intelligence layer for the AI-first workspace. It provides project discovery, metadata consumption, strategic recommendations, daily briefings, and a universal bridge for AI agents to access workspace intelligence.

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI-First Workspace                          │
│  (Projects with .claude/project.yaml + ARCHITECTURE.md)         │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ProjectMetadataReader                          │
│  - Scans workspace for .claude/project.yaml                    │
│  - Caches metadata with 5-minute TTL                           │
│  - Filters by domain, status, tech stack                       │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Cortex CLI                                 │
│  - projects: List all discovered projects                      │
│  - project-info: Show rich metadata                            │
│  - sync-portfolio: Update central index                        │
│  - briefing: Generate daily briefing                           │
│  - next: Get strategic recommendation                          │
│  - status: Show workspace health                               │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Core Components                              │
├─────────────────────────────────────────────────────────────────┤
│  AI Intelligence  │  Recommendation   │  Context         │  │
│  (scanning)       │  Engine           │  Intelligence    │  │
│                   │                   │                  │  │
│  Portfolio        │  Session          │  Learning        │  │
│  Memory           │  Manager          │  System          │  │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CortexBridge (Universal Interface)           │
│  - get_context()                                                │
│  - get_recommendations()                                        │
│  - trigger_action()                                             │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 AI Agent Consumers                              │
│  Claude Code  │  Cursor  │  Custom Scripts  │  Hooks           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Project Metadata Layer (`project_metadata.py`)

#### ProjectMetadataReader
- **Purpose**: Discover and read `.claude/project.yaml` files across workspace
- **Key Method**: `scan_workspace()` - Recursively finds all project.yaml files
- **Caching**: 5-minute TTL to balance freshness and performance
- **Filtering**: By domain, status, tech stack, related projects

**Data Model**:
```python
@dataclass
class ProjectMetadata:
    name: str
    domain: str           # weather, infrastructure, audio, health
    status: str           # production, development, experimental
    priority: str         # high, medium, low
    path: Path
    description: str
    tech_stack: Dict[str, List[str]]  # primary, secondary
    entry_points: Dict[str, str]      # api, ui, cli, etc.
    key_directories: List[str]
    related_projects: List[Dict]
    common_tasks: List[CommonTask]
    ai_hints: List[str]
    known_issues: List[str]
    environment: Dict[str, List[str]]  # required, optional
```

**Design Decision**: YAML for metadata (not JSON)
- Rationale: Human-readable, supports multi-line strings, comments
- Trade-off: Requires PyYAML dependency
- Benefit: Easy to hand-edit, git-friendly

### 2. CLI Layer (`cli.py`)

#### Command Structure (argparse)
```
cortex
  ├── projects [--domain DOMAIN] [--status STATUS]
  ├── project-info PROJECT_NAME
  ├── sync-portfolio
  ├── briefing [--json]
  ├── next [PROJECT] [--with-context] [--limit N]
  ├── status
  ├── health
  └── feedback [--stats]
```

**Key Commands**:

**`projects`**: Lists all discovered projects
- Implementation: `ProjectMetadataReader.scan_workspace()`
- Output: Rich-formatted table grouped by domain
- Performance: <1 second for 20+ projects

**`project-info`**: Shows detailed metadata for one project
- Implementation: `ProjectMetadataReader.load(project_path)`
- Output: Description, tech stack, entry points, tasks, AI hints
- Performance: <100ms (cached)

**`sync-portfolio`**: Updates central portfolio index
- Implementation: Merges .claude/project.yaml data with `~/.claude/portfolio/project_index.json`
- Backward compatible: Preserves legacy entries without project.yaml
- Performance: <2 seconds for full workspace scan

**`briefing`**: Generates daily strategic briefing
- Implementation: `BriefingGenerator.generate_daily_briefing()`
- Scans: Git commits (24h), goals, blockers, patterns
- Output: Portfolio pulse, priority actions, waiting items
- Performance: 15-30 seconds (git operations)

**`next`**: Strategic recommendation for next action
- Implementation: `CortexOrchestrator.get_next_action()`
- Uses: AI Intelligence + Recommendation Engine + Context Intelligence
- Output: Prioritized recommendations with confidence scores
- Performance: 10-15 seconds

### 3. AI Intelligence (`ai_intelligence.py`)

#### ProjectScanner
- **Purpose**: Analyze git repositories for activity and patterns
- **Metrics**: Commits (24h, 7d), active projects, dormant projects
- **Key Method**: `scan_projects()` - Parallel git analysis

**Activity Classification**:
- **Active**: 3+ commits in last 7 days
- **Recent**: 1-2 commits in last 7 days
- **Dormant**: Only commits in 7-30 day window
- **Stale**: No commits in 30+ days

**Design Decision**: Git-based activity tracking
- Rationale: Git is universal, accurate, no external dependencies
- Trade-off: Slower than file modification times
- Benefit: Reflects actual development work, not just file edits

### 4. Recommendation Engine (`recommendation_engine.py`)

#### RecommendationEngine
- **Purpose**: Generate strategic recommendations from project state
- **Input**: Project activity, goals, blockers, historical patterns
- **Output**: Prioritized recommendations with confidence scores

**Recommendation Types**:
1. **Goal-Based**: Actions from `ACTION_PLAN.md` goals
2. **Blocker Resolution**: Address identified blockers
3. **Activity-Based**: Continue active work
4. **Maintenance**: Update stale projects
5. **Exploration**: Investigate new areas

**Confidence Scoring**:
- 0.9+: High confidence (clear goal, recent activity)
- 0.7-0.9: Medium confidence (active project, some uncertainty)
- <0.7: Low confidence (stale project, exploratory)

**Design Decision**: Multi-factor confidence scoring
- Rationale: Combines recency, clarity, historical success
- Trade-off: More complex than simple priority
- Benefit: Better recommendations over time

### 5. Context Intelligence (`context_intelligence.py`)

#### ContextIntelligence
- **Purpose**: Predict and inject relevant context for tasks
- **Key Method**: `predict_context(task)` - Returns file paths, docs, hints
- **Uses**: Project metadata, git history, file analysis

**Context Types**:
- **Files**: Relevant source files for task
- **Documentation**: Related README, ARCHITECTURE, docs
- **Dependencies**: Required libraries, tools
- **Hints**: AI hints from project.yaml

### 6. Universal Bridge (`bridge.py`)

#### CortexBridge
- **Purpose**: Unified interface for ALL AI agents
- **Consumers**: Claude Code, Cursor, custom scripts, hooks

**Core Methods**:

```python
class CortexBridge:
    def get_context(query: str, limit: int = 5) -> List[Dict]
        """Get relevant context from KB and project history."""

    def get_recommendations(project: str = None, limit: int = 3) -> List[Dict]
        """Get strategic recommendations."""

    def trigger_action(action_name: str, params: Dict = None) -> Dict
        """Trigger automated action via local-orchestrator."""

    def read_project_metadata(project_name: str) -> ProjectMetadata
        """Read .claude/project.yaml for project."""
```

**Design Decision**: Universal bridge (not per-agent adapters)
- Rationale: Single interface easier to maintain, test, extend
- Replaces: Separate adapters for Antigravity, Cursor, Claude Code
- Benefit: Any AI agent can use same methods

### 7. Portfolio Memory (`portfolio_memory.py`)

#### PortfolioMemory
- **Purpose**: Maintain central index of all projects (migrated + legacy)
- **Storage**: `~/.claude/portfolio/project_index.json`
- **Format**:
```json
{
  "projects": [
    {
      "name": "VortexV2",
      "domain": "weather",
      "path": "/Users/jesse.kemp/Dev/Vortex/VortexV2",
      "status": "production",
      "priority": "high",
      "has_metadata": true,
      "last_updated": "2025-12-23T10:30:00"
    }
  ]
}
```

**Merge Strategy**:
- New projects from .claude/project.yaml: Always add/update
- Legacy projects (no project.yaml): Preserve in index
- Conflict resolution: .claude/project.yaml wins

### 8. Session Manager (`session_manager.py`)

#### SessionManager
- **Purpose**: Track active sessions and inject context
- **Integration**: `.claude/hooks/project_context.py` hook
- **Key Method**: `get_session_context(project_path)` - Returns rich context

**Context Injection**:
When user runs `claude` in project directory:
1. Hook detects project directory
2. SessionManager finds .claude/project.yaml
3. Injects: description, common tasks, AI hints, entry points
4. Result: AI agent starts with full project context

### 9. Learning System (`learning.py`)

#### LearningSystem
- **Purpose**: Adapt recommendations based on execution history
- **Data Source**: local-orchestrator execution logs
- **Key Method**: `update_confidence(recommendation, outcome)`

**Learning Loop**:
1. Cortex generates recommendation → local-orchestrator
2. local-orchestrator executes action → logs result
3. LearningSystem reads result → updates confidence
4. Future recommendations adjusted by historical success rate

**Metrics Tracked**:
- Success rates per action type
- Average execution duration
- Failure patterns (error types, frequency)
- Recommendation-to-execution conversion rate

### 10. Briefing Generator (`briefing.py`)

#### BriefingGenerator
- **Purpose**: Generate daily strategic briefing
- **Output**: Portfolio pulse, priority actions, patterns, waiting items

**Briefing Structure**:
```
╔══════════════════════════════════════════════════════╗
║              DAILY BRIEFING - 2025-12-23             ║
╚══════════════════════════════════════════════════════╝

📊 PORTFOLIO PULSE
  Active Projects (3): VortexV2, cortex, dj-copilot
  Recent Commits (24h): 12
  Total Commits (7d): 47

🎯 PRIORITY ACTIONS (3)
  1. VortexV2: Run validation analysis (confidence: 0.92)
  2. cortex: Complete project migrations (confidence: 0.85)
  3. dj-copilot: Fix failing tests (confidence: 0.78)

📈 PATTERNS NOTICED
  - High activity in infrastructure domain (cortex, local-orchestrator)
  - VortexV2 validation work ongoing (12 commits)
  - Audio projects stable (dj-copilot, windfield)

⏳ WAITING ON
  - VortexV2: NCAR GDEX data download (manual)
  - cortex: Batch API results for morning briefing
```

---

## Data Flow

### Project Discovery Flow

1. **User runs `cortex projects`**
2. **ProjectMetadataReader.scan_workspace()**
   - Recursively search for `.claude/project.yaml` files
   - `workspace.rglob(".claude/project.yaml")`
3. **For each project.yaml found:**
   - Parse YAML → ProjectMetadata object
   - Cache in memory (5-minute TTL)
4. **Filter and group projects:**
   - By domain (weather, infrastructure, etc.)
   - By status (production, development)
5. **Format output with rich library**
6. **Return results to user** (<1 second)

### Recommendation Flow

1. **User runs `cortex next vortexv2`**
2. **CortexOrchestrator.get_next_action(project_filter='vortexv2')**
3. **Parallel data gathering:**
   - AI Intelligence scans git activity
   - Goal Parser reads ACTION_PLAN.md
   - Context Intelligence predicts needed files
4. **RecommendationEngine generates candidates:**
   - Goal-based recommendations
   - Blocker resolution actions
   - Activity-based continuations
5. **LearningSystem adjusts confidence:**
   - Based on historical success rates
   - Recent execution patterns
6. **Sort by confidence, return top N**
7. **User receives prioritized recommendations** (10-15 seconds)

### Context Injection Flow

1. **User runs `claude` in project directory**
2. **`.claude/hooks/project_context.py` executes**
3. **SessionManager.get_session_context(cwd)**
4. **ProjectMetadataReader.load(project_path)**
5. **Extract context:**
   - Description
   - Common tasks with steps
   - AI hints
   - Entry points
   - Known issues
6. **Inject into AI session startup**
7. **AI agent starts with full project knowledge**

---

## Key Design Decisions

### 1. YAML for Metadata (Not JSON)

**Rationale**: Human-readable, supports multi-line strings, comments
**Trade-off**: Requires PyYAML dependency
**Benefit**:
- Easy to hand-edit
- Git-friendly diffs
- Comments for documentation
- Multi-line descriptions

### 2. File-Based Discovery (Not Database)

**Rationale**: `.claude/project.yaml` files live with projects
**Trade-off**: Slower than database lookup (but <1 sec)
**Benefit**:
- No central database to maintain
- Projects self-describing
- Works offline
- Git-versioned metadata

### 3. 5-Minute Cache TTL

**Rationale**: Balance between freshness and performance
**Trade-off**: Metadata changes not instant
**Benefit**:
- Fast repeated queries
- Reduces file I/O
- Good enough for developer workflow

### 4. Universal Bridge (Not Per-Agent Adapters)

**Rationale**: Single interface easier to maintain
**Trade-off**: Less specialized per agent
**Benefit**:
- One test suite
- Faster to add new agents
- Consistent behavior

### 5. Git-Based Activity Tracking

**Rationale**: Git is universal, accurate
**Trade-off**: Slower than file modification times
**Benefit**:
- Reflects actual work (not just file edits)
- No additional instrumentation needed
- Works across all projects

### 6. Confidence-Weighted Recommendations

**Rationale**: Better than simple priority levels
**Trade-off**: More complex scoring logic
**Benefit**:
- Adapts to user patterns
- Clear signal of certainty
- Improves over time with learning

---

## Extension Points

### Adding New CLI Commands

1. Create command handler in `cli.py`:
```python
def cmd_new_command(args):
    """Handler for new command."""
    # Implementation
    pass
```

2. Add subparser:
```python
parser_new = subparsers.add_parser('new-command', help='...')
parser_new.add_argument('--option', help='...')
parser_new.set_defaults(func=cmd_new_command)
```

### Adding New Intelligence Sources

1. Create module in `intelligence/` directory
2. Implement standard interface:
```python
class NewIntelligence:
    def query(self, query: str) -> List[Dict]:
        # Return relevant results
        pass
```
3. Register in `UnifiedIntelligence`

### Adding New Recommendation Types

1. Extend `RecommendationEngine` in `recommendation_engine.py`
2. Add new method:
```python
def _generate_new_type_recommendations(self, state: Dict) -> List[Recommendation]:
    # Generate recommendations
    pass
```
3. Call in `generate_recommendations()`

### Adding New Skills

1. Create Python module in `skills/` directory
2. Implement skill interface:
```python
def skill_name(params: Dict) -> Dict:
    """Skill implementation."""
    return {"status": "success", "result": ...}
```
3. Skills auto-discovered by skill loader

---

## Performance Characteristics

### Command Performance

| Command | Execution Time | Notes |
|---------|---------------|-------|
| `cortex projects` | <1 second | Cached after first run |
| `cortex project-info` | <100ms | Cached metadata |
| `cortex sync-portfolio` | 1-2 seconds | Full workspace scan |
| `cortex briefing` | 15-30 seconds | Git operations |
| `cortex next` | 10-15 seconds | AI analysis |
| `cortex status` | 5-10 seconds | Activity scan |

### Scalability

| Metric | Current | Tested | Limit |
|--------|---------|--------|-------|
| Projects in workspace | 6 | 20 | ~100 |
| Cache size | ~1 MB | ~10 MB | Memory |
| Portfolio index size | 15 KB | 150 KB | Filesystem |

**Bottlenecks**:
- Git operations (briefing, activity scan)
- File I/O for project.yaml scanning
- No bottlenecks for <50 projects

---

## Testing Strategy

### Unit Tests (`tests/unit/`)
- ProjectMetadataReader parsing
- CLI argument parsing
- Recommendation engine logic
- Cache behavior

### Integration Tests (`tests/integration/`)
- Full workspace scanning
- Portfolio sync with real projects
- CLI command execution
- Bridge interface

### E2E Tests (`tests/e2e/`)
- Complete briefing generation
- Recommendation → execution flow
- Learning system adaptation

---

## Deployment

### Development

```bash
# Install in development mode
cd /Users/jesse.kemp/Dev/cortex
pip install -e .

# Run CLI directly
python cli.py projects
```

### Production

```bash
# Install as package
pip install /Users/jesse.kemp/Dev/cortex

# Use installed command
cortex projects
```

### System Integration

**Context Injection Hook**:
```bash
# Symlink hook to .claude/hooks/
ln -s /Users/jesse.kemp/Dev/cortex/.claude/hooks/project_context.py \
      ~/.claude/hooks/project_context.py
```

**Shell Alias**:
```bash
# Add to ~/.zshrc or ~/.bashrc
alias cortex="python /Users/jesse.kemp/Dev/cortex/cli.py"
```

---

## Integration with Local-Orchestrator

### Bidirectional Flow

```
Cortex (Strategic Intelligence)
    ↓ Recommendations
local-orchestrator (Execution Engine)
    ↓ Results
Cortex Learning System
    ↓ Updated Confidence
Future Recommendations
```

**Recommendation → Agent**:
1. Cortex generates recommendation
2. User accepts: `cortex schedule`
3. Integration adapter converts to local-orchestrator agent
4. Agent scheduled and executed

**Execution → Learning**:
1. local-orchestrator executes agent
2. Logs result to `storage/execution_history/`
3. Cortex LearningSystem reads logs
4. Updates confidence scores for action types

---

## Future Enhancements

### V2 Intelligence Layer
- Semantic search across all project documentation
- Cross-project dependency analysis
- Automated migration suggestions
- Real-time activity streaming

### V3 Advanced Recommendations
- Time-of-day patterns (when you usually work on X)
- Context switching detection (just left meeting → likely to work on Y)
- Deadline awareness (integrate with calendar)
- Team collaboration patterns

### V4 Multi-Workspace Support
- Support multiple workspace roots
- Sync across machines
- Cloud backup of portfolio index
- Team sharing of project metadata

---

## References

- Project Metadata Format: `.claude/project.yaml` specification
- CLI Design: `cli.py` implementation
- Bridge Interface: `bridge.py` API documentation
- Learning System: `learning.py` algorithm details

---

**Version**: 1.0
**Last Updated**: 2025-12-23
**Status**: Production (V1 Infrastructure Complete)
