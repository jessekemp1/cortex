# Design Specification: NEXUS
## Personal Decision Intelligence Platform

**Version**: 1.0
**Date**: 2026-01-18
**Status**: Draft

---

## 1. System Overview

NEXUS is a local-first personal decision intelligence platform that provides:
1. **Semantic Layer** (Ontology): Unified model of the user's world
2. **Data Layer**: Multi-source integration with versioning
3. **Intelligence Layer**: AI-powered analysis and pattern recognition
4. **Action Layer**: Decision support and operational workflows

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   Chat   │  │  Graph   │  │ Timeline │  │Dashboard │  │  Canvas  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                        INTELLIGENCE LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   AI Agent   │  │   Briefing   │  │   Pattern    │                  │
│  │   (Claude)   │  │   Generator  │  │   Detector   │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
├─────────────────────────────────────────────────────────────────────────┤
│                         SEMANTIC LAYER (ONTOLOGY)                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Entity Types │ Relationships │ Actions │ Functions │ Schemas    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                            DATA LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Entity     │  │   Vector     │  │   Sync       │                  │
│  │   Store      │  │   Store      │  │   Engine     │                  │
│  │  (SQLite)    │  │  (ChromaDB)  │  │              │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
├─────────────────────────────────────────────────────────────────────────┤
│                         INTEGRATION LAYER                               │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│  │Obsidian│  │Calendar│  │ GitHub │  │ Manual │  │  API   │           │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Model (Ontology)

### 2.1 Core Entity Types

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CORE ONTOLOGY                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐      works_on       ┌──────────┐                        │
│   │  PERSON  │─────────────────────│ PROJECT  │                        │
│   └──────────┘                     └──────────┘                        │
│        │                                │                              │
│        │ made                           │ has_goal                     │
│        │                                │                              │
│        ▼                                ▼                              │
│   ┌──────────┐      toward         ┌──────────┐                        │
│   │ DECISION │─────────────────────│   GOAL   │                        │
│   └──────────┘                     └──────────┘                        │
│        │                                │                              │
│        │ resulted_in                    │ measured_by                  │
│        │                                │                              │
│        ▼                                ▼                              │
│   ┌──────────┐      informs        ┌──────────┐                        │
│   │ OUTCOME  │─────────────────────│  METRIC  │                        │
│   └──────────┘                     └──────────┘                        │
│                                                                         │
│   ┌──────────┐                     ┌──────────┐                        │
│   │  EVENT   │                     │ RESOURCE │                        │
│   └──────────┘                     └──────────┘                        │
│                                                                         │
│   ┌──────────┐      references     ┌──────────┐                        │
│   │   NOTE   │─────────────────────│  SOURCE  │                        │
│   └──────────┘                     └──────────┘                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Entity Schemas

```python
# Core Entity Base
class Entity:
    id: UUID
    type: EntityType
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    source: Source  # Where this entity came from
    confidence: float  # How certain we are (0-1)
    embedding: Vector  # Semantic embedding
    properties: Dict[str, Any]  # Flexible properties
    tags: List[str]

# Person Entity
class Person(Entity):
    type = EntityType.PERSON
    email: Optional[str]
    organization: Optional[str]
    role: Optional[str]
    last_contact: Optional[datetime]
    relationship_strength: float  # 0-1

# Project Entity
class Project(Entity):
    type = EntityType.PROJECT
    status: ProjectStatus  # active, paused, completed, abandoned
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    domain: Optional[str]  # e.g., "product", "investment", "research"

# Decision Entity
class Decision(Entity):
    type = EntityType.DECISION
    decided_at: datetime
    options_considered: List[str]
    rationale: str
    confidence_at_decision: float  # How confident was I?
    reversibility: str  # "easily_reversible", "hard_to_reverse", "irreversible"
    time_horizon: str  # "immediate", "short_term", "long_term"
    stakes: str  # "low", "medium", "high"

# Outcome Entity
class Outcome(Entity):
    type = EntityType.OUTCOME
    occurred_at: datetime
    expected: bool  # Was this expected?
    valence: str  # "positive", "negative", "neutral"
    magnitude: str  # "minor", "moderate", "major"
    lessons: Optional[str]

# Goal Entity
class Goal(Entity):
    type = EntityType.GOAL
    target_date: Optional[datetime]
    status: GoalStatus  # not_started, in_progress, achieved, abandoned
    success_criteria: List[str]

# Event Entity
class Event(Entity):
    type = EntityType.EVENT
    occurred_at: datetime
    ended_at: Optional[datetime]
    location: Optional[str]
    event_type: str  # "meeting", "milestone", "observation", etc.

# Note Entity
class Note(Entity):
    type = EntityType.NOTE
    content: str
    note_type: str  # "fleeting", "literature", "permanent"
    source_file: Optional[str]  # For synced notes

# Resource Entity
class Resource(Entity):
    type = EntityType.RESOURCE
    resource_type: str  # "money", "time", "tool", "credential"
    quantity: Optional[float]
    unit: Optional[str]

# Source Entity
class Source(Entity):
    type = EntityType.SOURCE
    source_type: str  # "article", "book", "conversation", "observation"
    url: Optional[str]
    author: Optional[str]
    accessed_at: datetime
    credibility: float  # 0-1
```

### 2.3 Relationship Types

```python
class Relationship:
    id: UUID
    source_id: UUID
    target_id: UUID
    type: RelationshipType
    created_at: datetime
    confidence: float
    properties: Dict[str, Any]

class RelationshipType(Enum):
    # Person relationships
    WORKS_WITH = "works_with"
    REPORTS_TO = "reports_to"
    INTRODUCED_BY = "introduced_by"

    # Project relationships
    WORKS_ON = "works_on"
    OWNS = "owns"
    CONTRIBUTES_TO = "contributes_to"
    DEPENDS_ON = "depends_on"

    # Decision relationships
    MADE = "made"  # Person -> Decision
    RESULTED_IN = "resulted_in"  # Decision -> Outcome
    INFORMED_BY = "informed_by"  # Decision -> Note/Source
    IMPACTS = "impacts"  # Decision -> Goal/Project

    # Goal relationships
    TOWARD = "toward"  # Decision/Action -> Goal
    MEASURED_BY = "measured_by"  # Goal -> Metric
    SUPPORTS = "supports"  # Goal -> Goal

    # Generic relationships
    REFERENCES = "references"
    RELATED_TO = "related_to"
    CAUSED = "caused"
    FOLLOWED = "followed"  # Temporal sequence
```

---

## 3. Storage Architecture

### 3.1 Entity Store (SQLite)

```sql
-- Core entities table
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    source_id TEXT,
    confidence REAL DEFAULT 1.0,
    properties JSON,
    tags JSON,
    deleted_at TIMESTAMP  -- Soft delete
);

-- Relationships table
CREATE TABLE relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES entities(id),
    target_id TEXT NOT NULL REFERENCES entities(id),
    type TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    confidence REAL DEFAULT 1.0,
    properties JSON,
    UNIQUE(source_id, target_id, type)
);

-- Entity history (time travel)
CREATE TABLE entity_versions (
    version_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    version_at TIMESTAMP NOT NULL,
    data JSON NOT NULL,
    change_type TEXT  -- "created", "updated", "deleted"
);

-- Sync tracking
CREATE TABLE sync_state (
    source TEXT PRIMARY KEY,
    last_sync TIMESTAMP,
    state JSON
);

-- Indexes
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_created ON entities(created_at);
CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);
CREATE INDEX idx_versions_entity ON entity_versions(entity_id);
```

### 3.2 Vector Store (ChromaDB)

```python
# Collection structure
collection = chroma_client.create_collection(
    name="nexus_entities",
    metadata={"hnsw:space": "cosine"}
)

# Document structure
{
    "id": entity.id,
    "embedding": embed(entity.to_text()),  # Generated by embedding model
    "metadata": {
        "type": entity.type,
        "name": entity.name,
        "created_at": entity.created_at.isoformat(),
        "tags": entity.tags
    },
    "document": entity.to_searchable_text()  # Concatenated text representation
}
```

### 3.3 File Structure

```
~/.nexus/
├── config.yaml           # User configuration
├── nexus.db              # SQLite database
├── chroma/               # Vector store
│   └── ...
├── cache/                # LLM response cache
│   └── ...
├── exports/              # Exported data
│   └── ...
├── logs/                 # Application logs
│   └── ...
└── backups/              # Automatic backups
    └── ...
```

---

## 4. Intelligence Layer

### 4.1 AI Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI AGENT                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    CONTEXT BUILDER                       │   │
│  │  • Retrieves relevant entities via semantic search       │   │
│  │  • Fetches connected entities via graph traversal        │   │
│  │  • Applies temporal filtering (recent > old)             │   │
│  │  • Respects context window limits                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    PROMPT COMPOSER                       │   │
│  │  • System prompt with ontology schema                    │   │
│  │  • Injected context (relevant entities)                  │   │
│  │  • User query                                            │   │
│  │  • Output format instructions                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      LLM CALL                            │   │
│  │  • Claude API (primary)                                  │   │
│  │  • Local model fallback (Ollama)                         │   │
│  │  • Response caching                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   RESPONSE PROCESSOR                     │   │
│  │  • Parse structured output                               │   │
│  │  • Extract entity references                             │   │
│  │  • Identify suggested actions                            │   │
│  │  • Track confidence/uncertainty                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Query Pipeline

```python
class QueryPipeline:
    async def process(self, query: str) -> Response:
        # 1. Classify query intent
        intent = await self.classify_intent(query)

        # 2. Retrieve relevant context
        if intent.needs_semantic_search:
            semantic_results = await self.vector_search(query, k=20)

        if intent.needs_graph_traversal:
            graph_results = await self.graph_query(intent.entities)

        if intent.needs_temporal:
            temporal_results = await self.temporal_query(intent.time_range)

        # 3. Rank and select context
        context = self.rank_and_select(
            semantic_results + graph_results + temporal_results,
            max_tokens=4000
        )

        # 4. Compose prompt
        prompt = self.compose_prompt(query, context, intent)

        # 5. Call LLM
        response = await self.llm.generate(prompt)

        # 6. Post-process
        return self.process_response(response, context)
```

### 4.3 Briefing Generator

```python
class BriefingGenerator:
    async def generate_daily_briefing(self) -> Briefing:
        today = datetime.now().date()

        # Gather inputs
        recent_decisions = await self.get_recent_decisions(days=7)
        upcoming_events = await self.get_upcoming_events(days=3)
        active_projects = await self.get_active_projects()
        pending_outcomes = await self.get_decisions_awaiting_outcomes()
        recent_patterns = await self.detect_recent_patterns()

        # Generate briefing via LLM
        briefing = await self.compose_briefing(
            decisions=recent_decisions,
            events=upcoming_events,
            projects=active_projects,
            pending=pending_outcomes,
            patterns=recent_patterns
        )

        return briefing

class Briefing:
    date: datetime
    summary: str  # 2-3 sentence overview
    key_items: List[BriefingItem]
    decisions_to_revisit: List[Decision]
    upcoming_focus: List[str]
    patterns_noticed: List[str]
    questions_to_consider: List[str]
```

### 4.4 Pattern Detection

```python
class PatternDetector:
    async def detect_patterns(self) -> List[Pattern]:
        patterns = []

        # Decision patterns
        decision_patterns = await self.analyze_decisions()
        # e.g., "You tend to make technology choices quickly but people choices slowly"

        # Temporal patterns
        temporal_patterns = await self.analyze_temporal()
        # e.g., "Your most productive days are Tuesdays"

        # Relationship patterns
        relationship_patterns = await self.analyze_relationships()
        # e.g., "Projects with John tend to succeed more often"

        # Outcome patterns
        outcome_patterns = await self.analyze_outcomes()
        # e.g., "Decisions made under time pressure have 30% worse outcomes"

        return patterns

class Pattern:
    description: str
    evidence: List[Entity]
    confidence: float
    actionable: bool
    suggestion: Optional[str]
```

---

## 5. Integration Layer

### 5.1 Sync Architecture

```python
class SyncEngine:
    sources: List[SyncSource]

    async def sync_all(self):
        for source in self.sources:
            try:
                changes = await source.get_changes()
                for change in changes:
                    await self.process_change(source, change)
                await source.update_sync_state()
            except SyncError as e:
                log.error(f"Sync failed for {source.name}: {e}")

class SyncSource(ABC):
    name: str

    @abstractmethod
    async def get_changes(self) -> List[Change]:
        """Get changes since last sync"""
        pass

    @abstractmethod
    async def apply_change(self, change: Change):
        """Apply a change from NEXUS to the source"""
        pass
```

### 5.2 Obsidian Integration

```python
class ObsidianSync(SyncSource):
    name = "obsidian"
    vault_path: Path

    async def get_changes(self) -> List[Change]:
        changes = []

        # Scan vault for changed files
        for md_file in self.vault_path.rglob("*.md"):
            if self.is_changed(md_file):
                note = await self.parse_note(md_file)
                entities = await self.extract_entities(note)
                changes.append(Change(
                    type="note_update",
                    source_file=md_file,
                    note=note,
                    entities=entities
                ))

        return changes

    async def extract_entities(self, note: Note) -> List[Entity]:
        """Use LLM to extract entities from note content"""
        prompt = f"""
        Extract entities from this note:
        {note.content}

        Entity types: Person, Project, Decision, Goal, Event
        Return as JSON.
        """
        return await self.llm.extract(prompt)
```

### 5.3 Calendar Integration

```python
class CalendarSync(SyncSource):
    name = "calendar"
    calendar_client: CalendarClient

    async def get_changes(self) -> List[Change]:
        events = await self.calendar_client.get_events(
            start=self.last_sync,
            end=datetime.now() + timedelta(days=30)
        )

        changes = []
        for event in events:
            entity = Event(
                name=event.title,
                occurred_at=event.start,
                ended_at=event.end,
                location=event.location,
                properties={
                    "calendar_id": event.id,
                    "attendees": event.attendees
                }
            )
            changes.append(Change(type="event", entity=entity))

        return changes
```

---

## 6. User Interface

### 6.1 Primary Interface: Chat

```
┌─────────────────────────────────────────────────────────────────┐
│  NEXUS                                            [≡] [?] [⚙]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 👤 What decisions have I made about the Alpha project   │   │
│  │    this month?                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🤖 You've made 3 decisions about Alpha in January:       │   │
│  │                                                          │   │
│  │ 1. **Tech stack choice** (Jan 5)                        │   │
│  │    → Chose Python + FastAPI over Node.js                │   │
│  │    → Rationale: ML integration, team familiarity        │   │
│  │    → Status: Awaiting outcome                           │   │
│  │    [View Decision] [Track Outcome]                      │   │
│  │                                                          │   │
│  │ 2. **Pricing model** (Jan 12)                           │   │
│  │    → Chose freemium over paid-only                      │   │
│  │    → Rationale: Market validation > immediate revenue   │   │
│  │    → Status: Outcome tracked (positive)                 │   │
│  │    [View Decision] [See Outcome]                        │   │
│  │                                                          │   │
│  │ 3. **Hiring first engineer** (Jan 15)                   │   │
│  │    → Decided to wait until funding                      │   │
│  │    → Rationale: Preserve runway                         │   │
│  │    → Status: Active                                     │   │
│  │    [View Decision] [Revisit]                            │   │
│  │                                                          │   │
│  │ ---                                                      │   │
│  │ 💡 Pattern noticed: Your Alpha decisions tend to        │   │
│  │    prioritize technical quality over speed.             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [Type a message...]                           [↵ Send]  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Graph View

```
┌─────────────────────────────────────────────────────────────────┐
│  NEXUS > Graph                            [Search] [Filter] [+] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│            ┌──────────┐                                        │
│            │  Sarah   │                                        │
│            │  (CEO)   │                                        │
│            └────┬─────┘                                        │
│                 │ introduced_by                                │
│                 │                                              │
│  ┌──────────┐   │   ┌──────────────┐      ┌──────────┐        │
│  │  John    │───┼───│    ALPHA     │──────│ Decision │        │
│  │(Engineer)│   │   │   PROJECT    │      │(Tech stk)│        │
│  └──────────┘   │   └──────────────┘      └──────────┘        │
│       │         │          │                    │              │
│       │         │          │                    │              │
│  works_on       │     has_goal             resulted_in        │
│       │         │          │                    │              │
│       ▼         │          ▼                    ▼              │
│  ┌──────────┐   │   ┌──────────┐         ┌──────────┐         │
│  │   MVP    │───┘   │  Launch  │         │ Outcome  │         │
│  │ Feature  │       │  by Q2   │         │(pending) │         │
│  └──────────┘       └──────────┘         └──────────┘         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Selected: ALPHA PROJECT                                        │
│  Created: Dec 2025 | Status: Active | 12 connected entities    │
│  [Open] [Edit] [Add Connection] [Timeline View]                │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Timeline View

```
┌─────────────────────────────────────────────────────────────────┐
│  NEXUS > Timeline                    [Jan 2026 ▼] [All Types ▼] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Jan 18 (Today)                                                 │
│  ─────────────                                                  │
│  │ 10:00  📅 Meeting: Weekly sync with John                    │
│  │ 14:00  📝 Note: Pricing research findings                   │
│  │                                                              │
│  Jan 17 (Yesterday)                                             │
│  ─────────────────                                              │
│  │ 09:00  📅 Meeting: Investor call                            │
│  │ 11:30  🎯 Decision: Delay hiring until funding              │
│  │ 15:00  💡 Outcome: Freemium launch - 100 signups            │
│  │                                                              │
│  Jan 15                                                         │
│  ──────                                                         │
│  │ All day  🚀 Event: Beta launch                              │
│  │                                                              │
│  Jan 12                                                         │
│  ──────                                                         │
│  │ 10:00  🎯 Decision: Freemium pricing model                  │
│  │                                                              │
│  Jan 5                                                          │
│  ─────                                                          │
│  │ 14:00  🎯 Decision: Python + FastAPI tech stack             │
│  │                                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. API Design

### 7.1 Core Operations

```python
# Entity Operations
nexus.entity.create(type, name, properties)
nexus.entity.get(id)
nexus.entity.update(id, properties)
nexus.entity.delete(id)
nexus.entity.list(type=None, filters=None)

# Relationship Operations
nexus.relationship.create(source_id, target_id, type)
nexus.relationship.get(id)
nexus.relationship.delete(id)
nexus.relationship.list(entity_id=None)

# Query Operations
nexus.query.semantic(query_text, k=10)
nexus.query.graph(start_id, relationship_types, depth)
nexus.query.temporal(start_date, end_date, types)
nexus.query.natural_language(question)

# Intelligence Operations
nexus.intelligence.briefing(date=None)
nexus.intelligence.patterns()
nexus.intelligence.ask(question)
nexus.intelligence.suggest_connections(entity_id)

# Sync Operations
nexus.sync.trigger(source=None)
nexus.sync.status()
nexus.sync.configure(source, config)

# Export Operations
nexus.export.json(path)
nexus.export.markdown(path)
nexus.export.graph(path, format="graphml")
```

### 7.2 CLI Interface

```bash
# Entity management
nexus add "John Smith is an engineer at Acme Corp"
nexus search "engineers I know"
nexus show <entity_id>
nexus link <entity1> --to <entity2> --as "works_with"

# Queries
nexus ask "What decisions have I made about Alpha?"
nexus briefing  # Today's briefing
nexus timeline --last 7d

# Sync
nexus sync  # Sync all sources
nexus sync --source obsidian

# Management
nexus status
nexus backup
nexus export --format json
```

---

## 8. Security Model

### 8.1 Data Protection

```yaml
# Security configuration
encryption:
  at_rest: true
  algorithm: AES-256-GCM
  key_derivation: argon2id

llm:
  # What gets sent to LLM
  send_entity_names: true
  send_entity_content: true
  send_relationships: true
  # What doesn't
  send_raw_files: false
  send_credentials: false

  # Context limits
  max_context_entities: 50
  max_tokens_per_entity: 500

backup:
  automatic: true
  frequency: daily
  retention: 30  # days
  location: ~/.nexus/backups
```

### 8.2 Privacy Principles

1. **Local-First**: All data stored locally by default
2. **Minimal API Exposure**: Only send necessary context to LLM
3. **No Telemetry**: No usage data sent without explicit consent
4. **Full Export**: User can export all data at any time
5. **Audit Trail**: Log of all external API calls

---

## 9. Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Entity creation | < 100ms | Including embedding generation |
| Semantic search | < 500ms | Top 20 results |
| Graph traversal (depth 2) | < 200ms | With caching |
| LLM query | < 5s | Dependent on API |
| Full sync | < 60s | For 1000 entities |
| Startup time | < 2s | Cold start |

---

## 10. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | ML ecosystem, productivity |
| Entity Store | SQLite | Zero-config, embedded, powerful |
| Vector Store | ChromaDB | Local, embedded, Python-native |
| Embeddings | OpenAI/Local | High quality, fallback available |
| LLM | Claude API | Best reasoning, fallback to local |
| UI (Terminal) | Textual | Rich TUI, Python-native |
| UI (Desktop) | Tauri + React | Native feel, web tech |
| Sync | Watchdog + async | File watching, async processing |

---

## Appendix A: Entity Extraction Prompt

```
You are an entity extraction system for a personal knowledge base.

Given the following text, extract entities and relationships.

Entity types:
- Person: A human being (name, role, organization)
- Project: A discrete endeavor with goals
- Decision: A choice made between alternatives
- Goal: A desired outcome
- Event: Something that happened at a point in time
- Resource: Money, time, tools, credentials
- Note: A piece of captured knowledge
- Source: Where information came from

Relationship types:
- works_with, works_on, owns
- made (person -> decision)
- toward (decision -> goal)
- resulted_in (decision -> outcome)
- references, related_to

Return JSON:
{
  "entities": [{"type": "...", "name": "...", "properties": {...}}],
  "relationships": [{"source": "...", "target": "...", "type": "..."}]
}

Text:
{input_text}
```

---

## Appendix B: Briefing Prompt

```
You are generating a daily intelligence briefing for a solo builder.

Context:
- Recent decisions: {decisions}
- Upcoming events: {events}
- Active projects: {projects}
- Pending outcomes: {pending}
- Detected patterns: {patterns}

Generate a briefing with:
1. Summary (2-3 sentences on what matters today)
2. Key items (3-5 most important things)
3. Decisions to revisit (any past decisions worth reconsidering)
4. Focus recommendations (what to prioritize)
5. Patterns noticed (behavioral insights)
6. Questions to consider (thought-provoking prompts)

Be concise, actionable, and insightful. Avoid generic advice.
```
