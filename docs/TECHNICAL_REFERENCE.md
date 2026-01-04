# Cortex V2 Prime: Technical Reference

**Version**: 2.0-draft
**Status**: Architectural Specification
**Last Updated**: 2026-01-02

---

## 1. System Architecture: The 3-Engine Active Model

### 1.1 Overview

Cortex V2 Prime operates as an **Active Context Operating System** through three engines:

```
+-------------------------------------------------------------+
|                    CORTEX V2 PRIME                          |
+-------------------------------------------------------------+
|                                                             |
|  +-------------+  +-------------+  +-------------+          |
|  |  ENGINE A   |  |  ENGINE B   |  |  ENGINE C   |          |
|  |  Absorber   |->|  Synthesis  |->|   Broker    |          |
|  |   (Input)   |  | (Processing)|  |  (Output)   |          |
|  +-------------+  +-------------+  +-------------+          |
|        ^                |                 |                 |
|   [Environment]   [Context Graph]   [Interventions]         |
|                                                             |
+-------------------------------------------------------------+
```

**Key Transformation from V1:**
- V1: Passive CLI waiting for `cortex next`
- V2 Prime: Active system emitting `InterventionEvents` proactively

### 1.2 Engine A: The Context Absorber

**Role**: Passive ingestion of environmental signals.

**Components**:

| Component | Purpose | Status |
|-----------|---------|--------|
| FileWatcher | Monitor filesystem events | PLANNED |
| ShellListener | Capture terminal history/exit codes | PLANNED |
| IDEBridge | Receive cursor position/active file via MCP | PARTIAL (MCP exists) |
| GitTracker | Track repository state | FUNCTIONAL |

**Signal Types**:
- File creation/modification/deletion
- Command execution and exit codes
- IDE focus changes
- Git commits/branch switches

**V1 Legacy**: Current implementation relies on manual Git scans. V2 Prime upgrades to real-time event streaming.

### 1.3 Engine B: The Synthesis Core

**Role**: Converting raw signals into structured context.

**Architecture**: Hierarchical Context Graph

```
+----------------------------------------------------------+
|                   CONTEXT GRAPH                           |
+----------------------------------------------------------+
|                                                           |
|   [Goals] <--relates_to--> [Projects]                     |
|      |                          |                         |
|   implements                 contains                     |
|      v                          v                         |
|   [Patterns] <---causes---> [Errors]                      |
|      |                          |                         |
|   used_in                   occurs_in                     |
|      v                          v                         |
|   [Files] <-----blocks-----> [Dependencies]               |
|                                                           |
+----------------------------------------------------------+
```

**Node Types**:
| Type | Description | Storage |
|------|-------------|---------|
| Goal | User objective from GOALS.md | portfolio/goals.json |
| Project | Repository with metadata | portfolio/project_index.json |
| Pattern | Successful approach | portfolio/patterns.json |
| Lesson | Mistake and prevention | portfolio/lessons.json |
| Error | Known failure mode | portfolio/errors.json |
| File | Source file with context | Dynamic |
| Dependency | External/internal dependency | Dynamic |

**Edge Types**:
| Edge | Meaning | Example |
|------|---------|---------|
| relates_to | Conceptual relationship | Goal relates_to Project |
| implements | Realizes a concept | Pattern implements Goal |
| blocks | Prevents progress | Dependency blocks Goal |
| causes | Causal relationship | Error causes Pattern (anti-pattern) |
| contains | Hierarchical containment | Project contains Files |

**V1 Legacy**: Current implementation uses isolated spec search. V2 Prime upgrades to graph-based context synthesis.

### 1.4 Engine C: The Action Broker

**Role**: Proactive intervention based on synthesized context.

**Intervention Events**:

| Event Type | Trigger | Action |
|------------|---------|--------|
| ERROR_PATTERN_DETECTED | Known error signature in logs | Surface lesson + suggested fix |
| WORK_DRIFT | Activity diverges from active plan | Alert + suggested realignment |
| BLOCKER_IDENTIFIED | Dependency blocks progress | Surface alternatives + escalation |
| CONTEXT_SWITCH | User switches project | Inject relevant context |
| RECOMMENDATION_AVAILABLE | High-confidence action ready | Proactive suggestion |

**Intervention Schema**:
```json
{
  "event_type": "ERROR_PATTERN_DETECTED",
  "timestamp": "2026-01-02T10:30:00Z",
  "severity": "high",
  "context": {
    "pattern_id": "pattern:grib_index_check",
    "lesson_id": "lesson:always_check_grib_index",
    "relevant_files": ["src/data/grib_loader.py"]
  },
  "suggested_action": {
    "title": "Add index validation before GRIB download",
    "rationale": "This pattern has caused issues in VortexV2",
    "confidence": 0.87
  }
}
```

**V1 Legacy**: Current implementation waits for `cortex next`. V2 Prime emits proactive interventions.

---

## 2. Data Structures

### 2.1 Project Schema

```json
{
  "name": "string",
  "path": "absolute_path",
  "priority": "tier1 | tier2 | tier3",
  "tech_stack": ["string"],
  "domain": "string",
  "status": "active | dormant | archived",
  "common_patterns": ["pattern_id"],
  "common_issues": ["lesson_id"],
  "activity_commits_7d": "number",
  "related_projects": ["project_name"],
  "health_score": "0-100",
  "last_activity": "ISO8601"
}
```

### 2.2 Pattern Schema

```json
{
  "id": "pattern:unique_id",
  "name": "string",
  "category": "string",
  "description": "string",
  "context": "when to apply",
  "implementation": {
    "stage1": "string",
    "stage2": "string"
  },
  "success_metrics": {
    "metric_name": "value"
  },
  "lessons_learned": ["string"],
  "projects": ["project_name"],
  "usage_count": "number",
  "success_rate": "0.0-1.0"
}
```

### 2.3 Lesson Schema

```json
{
  "id": "lesson:unique_id",
  "title": "string",
  "category": "string",
  "mistake": "what went wrong",
  "prevention": "how to avoid",
  "detection": "how to detect early",
  "projects": ["project_name"],
  "frequency": "number",
  "first_seen": "ISO8601",
  "last_seen": "ISO8601",
  "severity": "critical | high | medium | low"
}
```

### 2.4 Outcome Schema (Learning System)

```json
{
  "id": "outcome:unique_id",
  "recommendation_id": "rec:unique_id",
  "recommendation_type": "string",
  "recommendation_title": "string",
  "confidence": "0.0-1.0",
  "followed": "boolean",
  "outcome": "success | partial | failed",
  "notes": "string",
  "timestamp": "ISO8601",
  "context": {
    "project": "string",
    "session_id": "string"
  }
}
```

### 2.5 Signal Schema (V2 Prime)

```json
{
  "id": "signal:unique_id",
  "type": "file_created | file_modified | command_executed | git_commit | ide_focus",
  "timestamp": "ISO8601",
  "source": "file_watcher | shell_listener | ide_bridge | git_tracker",
  "payload": {
    "path": "string",
    "project": "string",
    "details": {}
  },
  "processed": "boolean",
  "absorbed_into": "work_item_id | null"
}
```

### 2.6 Intervention Schema (V2 Prime)

```json
{
  "id": "intervention:unique_id",
  "type": "error_pattern_detected | work_drift | blocker_identified | context_switch | recommendation_available",
  "severity": "critical | high | medium | low | info",
  "title": "string",
  "description": "string",
  "context": {
    "pattern_id": "string",
    "lesson_id": "string",
    "relevant_files": ["string"]
  },
  "suggested_action": {
    "title": "string",
    "rationale": "string",
    "confidence": "0.0-1.0"
  },
  "timestamp": "ISO8601",
  "acknowledged": "boolean",
  "suppressed_until": "ISO8601 | null"
}
```

---

## 3. Bridge API

### 3.1 Interface Definition

```python
class CortexBridge:
    """Universal interface for AI agent integration."""
    
    # V1 Context Methods
    def get_context(query: str, limit: int = 5, project: str = None) -> List[Dict]
    def get_session_context(format: str = "structured") -> Dict
    def get_project_context(project: str) -> Dict
    
    # V1 Recommendation Methods
    def get_recommendation(project: str = None) -> Recommendation
    def get_recommendations(limit: int = 5) -> List[Recommendation]
    def inject_recommendation(title: str, rationale: str, **kwargs) -> bool
    
    # V1 Execution Methods
    def start_execution(recommendation_id: str) -> bool
    def record_outcome(recommendation_id: str, outcome: str, notes: str = "") -> bool
    
    # V1 Intelligence Methods
    def query_intelligence(request: str, project: str, query_type: str) -> Dict
    def get_learning_metrics() -> LearningMetrics
    def get_confidence_calibration() -> Dict
    
    # V1 Portfolio Methods
    def get_portfolio_status() -> Dict
    def get_project_health(project: str) -> Dict
    
    # V2 Prime: Graph Methods (NEW)
    def query_graph(node_type: str, filters: Dict) -> List[Node]
    def get_related_nodes(node_id: str, edge_type: str) -> List[Node]
    def add_edge(source_id: str, target_id: str, edge_type: str) -> bool
    
    # V2 Prime: Intervention Methods (NEW)
    def get_pending_interventions() -> List[Intervention]
    def acknowledge_intervention(intervention_id: str) -> bool
    def suppress_intervention(intervention_id: str, duration: str) -> bool
    
    # V2 Prime: IAP Methods (NEW)
    def handle_iap_message(message_dict: Dict) -> Dict
```

### 3.2 Response Format

```json
{
  "success": true,
  "data": { },
  "metadata": {
    "timestamp": "ISO8601",
    "latency_ms": 45,
    "source_engine": "synthesis | broker | absorber"
  }
}
```

---

## 4. Inter-Agent Protocol (IAP)

### 4.1 Protocol Overview

Cortex-IAP/1.0 enables structured communication between AI agents and Cortex.

### 4.2 Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| handoff | Agent -> Agent | Transfer work context between agents |
| intervention | Cortex -> Agent | Proactive notification |
| query | Agent -> Cortex | Request context/recommendation |
| response | Cortex -> Agent | Answer to query |
| ack | Agent -> Cortex | Acknowledge intervention |

### 4.3 Message Schema

```json
{
  "protocol": "Cortex-IAP/1.0",
  "message_id": "msg:unique_id",
  "timestamp": "ISO8601",
  "message_type": "handoff | intervention | query | response | ack",
  "source_agent": {
    "id": "agent_id",
    "role": "researcher | implementer | reviewer | orchestrator",
    "capabilities": ["code_generation", "file_editing", "testing"]
  },
  "target_agent": {
    "id": "agent_id | cortex",
    "role": "string"
  },
  "context_snapshot": {
    "active_goal_id": "goal:unique_id",
    "active_project": "project_name",
    "relevant_files": ["path/to/file"],
    "memory_refs": ["pattern:id", "lesson:id"]
  },
  "payload": {
    "instruction": "string",
    "constraints": ["string"],
    "expected_output": "string",
    "timeout_seconds": 300
  }
}
```

### 4.4 Handoff Example

```json
{
  "protocol": "Cortex-IAP/1.0",
  "message_id": "msg:handoff-001",
  "timestamp": "2026-01-02T10:30:00Z",
  "message_type": "handoff",
  "source_agent": {
    "id": "researcher-01",
    "role": "researcher",
    "capabilities": ["web_search", "documentation_analysis"]
  },
  "target_agent": {
    "id": "coder-01",
    "role": "implementer"
  },
  "context_snapshot": {
    "active_goal_id": "goal:implement-auth",
    "active_project": "cortex",
    "relevant_files": ["src/auth.py", "src/middleware.py"],
    "memory_refs": ["pattern:auth_middleware", "lesson:jwt_timeout"]
  },
  "payload": {
    "instruction": "Implement JWT validation based on the attached pattern.",
    "constraints": ["No external auth libraries", "Max latency 50ms"],
    "expected_output": "Modified auth.py with JWT validation",
    "timeout_seconds": 1800
  }
}
```

### 4.5 Intervention Example

```json
{
  "protocol": "Cortex-IAP/1.0",
  "message_id": "msg:intervention-042",
  "timestamp": "2026-01-02T10:35:00Z",
  "message_type": "intervention",
  "source_agent": {
    "id": "cortex",
    "role": "orchestrator"
  },
  "target_agent": {
    "id": "coder-01",
    "role": "implementer"
  },
  "context_snapshot": {
    "active_goal_id": "goal:implement-auth",
    "active_project": "cortex",
    "relevant_files": ["src/auth.py"],
    "memory_refs": ["lesson:jwt_timeout"]
  },
  "payload": {
    "intervention_type": "ERROR_PATTERN_DETECTED",
    "severity": "high",
    "instruction": "JWT timeout not configured. This caused issues in VortexV2.",
    "suggested_fix": "Add timeout parameter to jwt.decode()",
    "constraints": []
  }
}
```

---

## 5. Security & Storage

### 5.1 Filesystem Layout

```
~/.claude/
  portfolio/
    project_index.json    # Project registry
    patterns.json         # Pattern library
    lessons.json          # Lessons learned
    goals.json            # Active goals
    outcomes.json         # Outcome history
    metrics.json          # Performance metrics
  specs/
    index.json            # Spec index
    embeddings/           # Vector embeddings (ChromaDB)
  session/
    context.json          # Cached session context
  graph/
    nodes.json            # Graph nodes (V2 Prime)
    edges.json            # Graph edges (V2 Prime)

~/.cortex/
  config.json             # Configuration
  outcomes.jsonl          # Outcome log (append-only)
  interventions.json      # Pending interventions (V2 Prime)
  logs/
    cortex.log            # Application logs
```

### 5.2 Security Model

| Principle | Implementation |
|-----------|----------------|
| Local-First | All data stored in user home directory |
| No Telemetry | No external network calls except optional APIs |
| Secret Protection | API keys via environment variables only |
| Path Safety | All paths resolved and validated |
| Audit Trail | All operations logged |

---

## 6. Migration Path: V1 -> V2 Prime

### 6.1 Phase 1: Foundation (Current)
- V1 infrastructure operational
- Bridge API functional
- Learning system collecting data

### 6.2 Phase 2: Absorber (Q1 2026)
- Implement FileWatcher
- Implement ShellListener
- Upgrade IDEBridge (MCP enhancement)

### 6.3 Phase 3: Synthesis Graph (Q2 2026)
- Implement graph data structure
- Migrate patterns/lessons to nodes
- Add edge relationships

### 6.4 Phase 4: Action Broker (Q3 2026)
- Implement intervention events
- Add proactive notification
- Integrate IAP

### 6.5 Phase 5: Full Active Context (Q4 2026)
- Real-time context synthesis
- Multi-agent orchestration
- Autonomous intervention

---

## Appendix A: V1 Legacy Reference

The following V1 components are preserved for reference:

| V1 Component | V2 Prime Mapping |
|--------------|------------------|
| 5-Layer Stack | 3-Engine Model |
| Layer 1: Project Analysis | Engine A: Absorber |
| Layer 2: Pattern Memory | Engine B: Synthesis (Graph) |
| Layer 3: Warnings | Engine C: Broker (Interventions) |
| Layer 4: Recommendations | Engine C: Broker (Suggestions) |
| Layer 5: Execution | Engine C: Broker (Actions) |
| CortexOrchestrator | Synthesis Core |
| RecommendationEngine | Action Broker |
| PortfolioMemory | Context Graph |

---

## Appendix B: Module Structure

```
cortex/
  __init__.py
  bridge.py              # Universal Bridge API (V1 + V2)
  cli.py                 # Command-line interface
  orchestrator.py        # Core orchestrator (V1)
  learning.py            # Learning system
  mcp_server.py          # MCP integration
  
  engines/               # V2 Prime (NEW)
    __init__.py
    absorber.py          # Engine A: Context Absorber
    synthesis.py         # Engine B: Synthesis Core
    broker.py            # Engine C: Action Broker
  
  protocols/             # V2 Prime (NEW)
    __init__.py
    iap.py               # Inter-Agent Protocol handler
  
  intelligence/          # Existing
    models.py
    unified_intelligence.py
    spec_knowledge_base.py
    session_manager.py
    planning.py
  
  work_absorber/         # Existing (V2 Prime foundation)
    __init__.py
    work_absorber.py
    plan_sync.py
  
  agents/                # Existing
    data_agent/
    research_agent/
```

---

**Document Status**: Draft
**Replaces**: GOLDEN_SPEC.md, TECHNICAL_SPECIFICATION.md, ARCHITECTURE.md, DESIGN.md
**Last Updated**: 2026-01-02
