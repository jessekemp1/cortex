# Implementation Plan: NEXUS

## Overview

This document outlines a phased implementation plan for NEXUS, starting with MVP and progressing through increasingly capable versions.

**Philosophy**: Ship fast, learn fast. Each phase should deliver usable value, not just infrastructure.

---

## Phase 0: Foundation (Week 1)

### Goal
Set up project structure, core dependencies, and prove the concept works.

### Deliverables

```
nexus/
├── pyproject.toml           # Dependencies and config
├── README.md                 # Getting started
├── nexus/
│   ├── __init__.py
│   ├── cli.py               # Entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ontology.py      # Entity/relationship models
│   │   ├── store.py         # SQLite operations
│   │   └── vectors.py       # ChromaDB operations
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── llm.py           # LLM client abstraction
│   │   └── embeddings.py    # Embedding generation
│   └── config.py            # Configuration management
├── tests/
│   └── ...
└── examples/
    └── ...
```

### Tasks

| Task | Description | Effort |
|------|-------------|--------|
| Project setup | pyproject.toml, ruff, pytest, pre-commit | 2h |
| Entity models | Pydantic models for all entity types | 4h |
| SQLite store | CRUD for entities and relationships | 4h |
| ChromaDB integration | Embedding storage and search | 3h |
| LLM client | Claude API with fallback structure | 3h |
| Basic CLI | `nexus add`, `nexus search` commands | 4h |
| Proof of concept | End-to-end: add → embed → search → query | 4h |

### Success Criteria
- Can add an entity via CLI
- Entity is searchable via semantic search
- Can ask a question and get LLM-grounded response

---

## Phase 1: MVP - "Personal Ontology + AI Chat" (Weeks 2-4)

### Goal
A usable product that proves the core value proposition.

### User Journey

```
1. User runs `nexus init` → creates ~/.nexus directory
2. User runs `nexus import ~/Obsidian` → imports markdown vault
3. Entities extracted and indexed automatically
4. User runs `nexus ask "What do I know about X?"` → gets answer
5. User runs `nexus add "John is the CTO of Acme"` → adds entity
6. User runs `nexus graph` → sees relationship visualization
```

### Features

#### 1.1 Core Ontology Engine

```python
# Entity types supported
- Person (name, role, organization, relationship_strength)
- Project (name, status, domain)
- Decision (options, rationale, confidence, reversibility)
- Goal (target_date, success_criteria, status)
- Event (occurred_at, location, event_type)
- Note (content, note_type, source_file)
- Source (url, author, credibility)

# Relationship types
- works_with, works_on, owns
- made, resulted_in, toward
- references, related_to
```

#### 1.2 Obsidian Import

```python
class ObsidianImporter:
    def import_vault(self, vault_path: Path):
        # 1. Scan all markdown files
        # 2. Parse frontmatter and content
        # 3. Extract entities via LLM
        # 4. Create relationships from [[wikilinks]]
        # 5. Generate embeddings
        # 6. Store in database
```

#### 1.3 AI Query Interface

```python
class QueryEngine:
    async def ask(self, question: str) -> Response:
        # 1. Semantic search for relevant entities
        relevant = await self.vector_search(question, k=20)

        # 2. Graph expand to find connected entities
        expanded = await self.graph_expand(relevant, depth=1)

        # 3. Build context
        context = self.build_context(relevant + expanded)

        # 4. Query LLM
        response = await self.llm.query(question, context)

        # 5. Return with sources
        return Response(
            answer=response.text,
            sources=[e.id for e in relevant],
            confidence=response.confidence
        )
```

#### 1.4 CLI Interface

```bash
# Initialization
nexus init                    # Create ~/.nexus directory
nexus config                  # Configure API keys, paths

# Data management
nexus import <path>           # Import from Obsidian/markdown
nexus add "<natural language>" # Add entity via NL
nexus show <entity_id>        # Show entity details
nexus list [--type <type>]    # List entities
nexus link <e1> <e2> <type>   # Create relationship

# Querying
nexus search "<query>"        # Semantic search
nexus ask "<question>"        # AI-powered Q&A
nexus graph [--entity <id>]   # Terminal graph visualization

# Maintenance
nexus sync                    # Re-sync sources
nexus backup                  # Create backup
nexus export [--format json]  # Export data
```

### Implementation Tasks

| Week | Focus | Tasks |
|------|-------|-------|
| Week 2 | Import & Storage | Obsidian parser, entity extractor, batch import |
| Week 3 | Query Engine | Context builder, LLM integration, search refinement |
| Week 4 | CLI & Polish | Full CLI, error handling, documentation |

### Technical Decisions

**Entity Extraction Strategy**:
```python
# Batch extraction for efficiency
async def extract_entities_batch(notes: List[Note]) -> List[Entity]:
    # Group notes into batches of 5
    batches = chunk(notes, 5)

    all_entities = []
    for batch in batches:
        prompt = build_extraction_prompt(batch)
        result = await llm.extract(prompt)
        all_entities.extend(result.entities)

    return deduplicate(all_entities)
```

**Context Window Management**:
```python
def build_context(entities: List[Entity], max_tokens: int = 4000) -> str:
    context_parts = []
    token_count = 0

    # Sort by relevance score
    sorted_entities = sorted(entities, key=lambda e: e.relevance, reverse=True)

    for entity in sorted_entities:
        entity_text = entity.to_context_string()
        entity_tokens = count_tokens(entity_text)

        if token_count + entity_tokens > max_tokens:
            break

        context_parts.append(entity_text)
        token_count += entity_tokens

    return "\n\n".join(context_parts)
```

### Success Metrics
- Import 500+ notes from Obsidian vault
- 90%+ entity extraction accuracy
- Query response < 3 seconds
- User finds "forgotten" information in first session

---

## Phase 2: Decision Intelligence (Weeks 5-8)

### Goal
Transform from knowledge base to decision support system.

### Features

#### 2.1 Decision Tracking

```python
class DecisionCapture:
    async def capture_decision(self, description: str) -> Decision:
        # LLM extracts structured decision
        extracted = await self.llm.extract_decision(description)

        decision = Decision(
            name=extracted.name,
            options_considered=extracted.options,
            chosen_option=extracted.chosen,
            rationale=extracted.rationale,
            confidence_at_decision=extracted.confidence,
            reversibility=extracted.reversibility,
            time_horizon=extracted.time_horizon,
            stakes=extracted.stakes
        )

        # Link to related entities
        related = await self.find_related_entities(decision)
        for entity in related:
            self.link(decision, entity, RelationType.RELATED_TO)

        return decision
```

#### 2.2 Outcome Tracking

```python
class OutcomeTracker:
    async def track_outcome(self, decision_id: str, description: str):
        decision = await self.get_decision(decision_id)

        outcome = await self.llm.extract_outcome(description)

        outcome = Outcome(
            name=outcome.name,
            occurred_at=datetime.now(),
            expected=outcome.was_expected,
            valence=outcome.valence,  # positive/negative/neutral
            magnitude=outcome.magnitude,
            lessons=outcome.lessons
        )

        self.link(decision, outcome, RelationType.RESULTED_IN)

        # Update decision learning
        await self.update_decision_patterns(decision, outcome)
```

#### 2.3 Daily Briefing

```bash
$ nexus briefing

╭─────────────────────────────────────────────────────────────╮
│                    NEXUS Daily Briefing                     │
│                     January 18, 2026                        │
╰─────────────────────────────────────────────────────────────╯

📊 SUMMARY
You have 3 active projects and 2 decisions awaiting outcomes.
Yesterday you made a key decision on Alpha pricing strategy.

🎯 KEY ITEMS
1. [Project] Alpha MVP launch scheduled for tomorrow
2. [Decision] Awaiting outcome: Freemium pricing (decided Jan 12)
3. [Event] Investor call at 2pm with Sarah

🔄 DECISIONS TO REVISIT
• Tech stack choice (Jan 5) - Consider checking if FastAPI is
  performing as expected after 2 weeks

💡 PATTERNS NOTICED
• Your decisions this month show a bias toward technical quality
  over speed-to-market
• 3 of 4 recent positive outcomes involved John's input

❓ QUESTIONS TO CONSIDER
• Have you validated the freemium conversion assumption?
• Is the launch timeline still realistic given yesterday's scope add?
```

#### 2.4 Graph Visualization (Desktop)

```
Features:
- Interactive node/edge graph
- Filter by entity type
- Time-based filtering
- Highlight paths between entities
- Click to expand node details
- Search within graph
```

### Implementation Tasks

| Week | Focus | Tasks |
|------|-------|-------|
| Week 5 | Decision System | Decision model, capture workflow, CLI commands |
| Week 6 | Outcome System | Outcome tracking, decision-outcome linking |
| Week 7 | Briefing | Briefing generator, pattern detection v1 |
| Week 8 | Desktop UI v1 | Tauri setup, graph visualization, basic UI |

### Success Metrics
- 80%+ of significant decisions captured
- Daily briefing used 5+ days/week
- Users report better decision awareness

---

## Phase 3: Operational Intelligence (Weeks 9-14)

### Goal
Move from understanding to action.

### Features

#### 3.1 Multi-Source Sync

```python
# Calendar integration
class CalendarSync(SyncSource):
    async def sync(self):
        events = await self.calendar.get_events(
            start=self.last_sync,
            end=datetime.now() + timedelta(days=30)
        )
        for event in events:
            await self.create_or_update_entity(event)

# Git integration
class GitSync(SyncSource):
    async def sync(self):
        commits = await self.git.get_commits(since=self.last_sync)
        for commit in commits:
            # Link commits to projects
            project = await self.match_project(commit.repo)
            event = Event(
                name=f"Commit: {commit.message[:50]}",
                event_type="git_commit",
                properties={"sha": commit.sha, "repo": commit.repo}
            )
            self.link(event, project, RelationType.CONTRIBUTES_TO)
```

#### 3.2 Pattern Analysis

```python
class PatternAnalyzer:
    async def analyze_decision_patterns(self) -> List[Pattern]:
        decisions = await self.get_all_decisions()
        outcomes = await self.get_all_outcomes()

        patterns = []

        # Time-based patterns
        patterns.extend(await self.analyze_temporal_patterns(decisions))
        # e.g., "Decisions made on Mondays have better outcomes"

        # Person-based patterns
        patterns.extend(await self.analyze_person_patterns(decisions, outcomes))
        # e.g., "Decisions involving John tend to succeed"

        # Domain-based patterns
        patterns.extend(await self.analyze_domain_patterns(decisions, outcomes))
        # e.g., "Technical decisions have 80% positive outcomes"

        # Confidence calibration
        patterns.extend(await self.analyze_calibration(decisions, outcomes))
        # e.g., "You're overconfident - 90% confidence = 70% success"

        return patterns
```

#### 3.3 Proactive Insights

```python
class ProactiveEngine:
    async def generate_insights(self) -> List[Insight]:
        insights = []

        # Check for stale decisions
        stale = await self.find_decisions_needing_review()
        for decision in stale:
            insights.append(Insight(
                type="decision_review",
                message=f"Decision '{decision.name}' was made {decision.age_days} days ago. Worth revisiting?",
                priority="medium",
                action_url=f"/decision/{decision.id}"
            ))

        # Check for missing outcomes
        pending = await self.find_decisions_without_outcomes()
        for decision in pending:
            insights.append(Insight(
                type="outcome_needed",
                message=f"What happened with '{decision.name}'?",
                priority="high"
            ))

        # Surface relevant past experience
        context = await self.get_current_context()
        similar = await self.find_similar_situations(context)
        if similar:
            insights.append(Insight(
                type="relevant_experience",
                message=f"This situation is similar to {similar.name}. That resulted in: {similar.outcome}",
                priority="high"
            ))

        return insights
```

#### 3.4 Mobile Companion (PWA)

```
Features:
- Quick capture (voice → entity)
- View briefing
- Log outcomes on the go
- Push notifications for insights
- Offline support
```

### Implementation Tasks

| Week | Focus | Tasks |
|------|-------|-------|
| Week 9 | Calendar Sync | Google Calendar integration, event entity mapping |
| Week 10 | Git Sync | Repository scanning, commit → project linking |
| Week 11 | Pattern Analysis | Pattern detection algorithms, confidence calibration |
| Week 12 | Proactive Insights | Insight generation, notification system |
| Week 13-14 | Mobile PWA | React PWA, voice capture, offline sync |

### Success Metrics
- 3+ integrations actively syncing
- Users receive 2+ useful proactive insights/week
- Mobile used for 30%+ of quick captures

---

## Phase 4: Adaptive Intelligence (Weeks 15-20)

### Goal
System learns and adapts to individual user patterns.

### Features

#### 4.1 Personalized Learning

```python
class AdaptiveLearner:
    async def learn_from_interaction(self, interaction: Interaction):
        # What entities did user click/expand?
        # What questions did user ask?
        # What decisions had good outcomes?
        # What patterns did user find valuable?

        await self.update_relevance_model(interaction)
        await self.update_prediction_model(interaction)
        await self.update_briefing_preferences(interaction)
```

#### 4.2 Hypothesis Mode

```python
class HypothesisWorkspace:
    async def create_hypothesis(self, statement: str) -> Hypothesis:
        # Parse hypothesis
        hypothesis = await self.llm.parse_hypothesis(statement)

        # Find supporting evidence
        supporting = await self.find_supporting_evidence(hypothesis)

        # Find contradicting evidence
        contradicting = await self.find_contradicting_evidence(hypothesis)

        # Generate alternatives
        alternatives = await self.generate_alternatives(hypothesis)

        return Hypothesis(
            statement=statement,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            alternative_hypotheses=alternatives,
            confidence_score=self.calculate_confidence(supporting, contradicting)
        )
```

#### 4.3 Small Team Features

```python
class TeamWorkspace:
    members: List[User]
    shared_ontology: Ontology
    private_spaces: Dict[User, Ontology]

    async def share_entity(self, entity: Entity, with_team: bool):
        if with_team:
            await self.shared_ontology.add(entity)
        else:
            await self.private_spaces[current_user].add(entity)

    async def get_combined_view(self, user: User) -> List[Entity]:
        # Combine shared + private
        shared = await self.shared_ontology.list()
        private = await self.private_spaces[user].list()
        return merge_with_priority(private, shared)
```

#### 4.4 Plugin System

```python
class PluginSystem:
    plugins: List[Plugin]

    async def register_plugin(self, plugin: Plugin):
        # Validate plugin
        if not plugin.is_valid():
            raise InvalidPluginError()

        # Grant permissions
        permissions = await self.request_permissions(plugin.required_permissions)

        # Register hooks
        for hook in plugin.hooks:
            self.event_bus.register(hook.event, hook.handler)

        self.plugins.append(plugin)

# Example plugin: Readwise integration
class ReadwisePlugin(Plugin):
    name = "readwise"
    required_permissions = ["create_entity", "create_relationship"]

    async def on_sync(self):
        highlights = await self.readwise.get_highlights(since=self.last_sync)
        for highlight in highlights:
            source = await self.create_source(highlight.book)
            note = await self.create_note(highlight.text, source)
```

### Implementation Tasks

| Week | Focus | Tasks |
|------|-------|-------|
| Week 15 | Learning System | Interaction tracking, model updates |
| Week 16 | Hypothesis Mode | Evidence finding, alternative generation |
| Week 17 | Team Features | Shared ontologies, permission model |
| Week 18 | Plugin System | Plugin architecture, first plugins |
| Week 19-20 | Polish & Launch | Bug fixes, documentation, launch prep |

### Success Metrics
- System recommendations improve over time (measured by user feedback)
- Hypothesis mode used for 50%+ of complex decisions
- 3+ community plugins available

---

## Resource Requirements

### Development Team (Ideal)

| Role | Allocation | Focus |
|------|------------|-------|
| Backend Engineer | 1 FTE | Core engine, AI integration |
| Frontend Engineer | 0.5 FTE | Desktop UI, mobile PWA |
| Product/Design | 0.25 FTE | UX, testing, feedback |

### Solo Builder Approach

If building solo, adjust timeline:
- Phase 0-1: 6-8 weeks (instead of 4)
- Phase 2: 8 weeks (instead of 4)
- Phase 3: 10 weeks (instead of 6)
- Phase 4: Defer until user feedback demands it

### Infrastructure Costs (Monthly)

| Service | Cost | Notes |
|---------|------|-------|
| Claude API | ~$20 | Based on 1000 queries/month |
| OpenAI Embeddings | ~$1 | 10K entities |
| Domain/hosting | ~$10 | For landing page |
| **Total** | **~$31** | |

---

## Risk Mitigation Timeline

| Risk | Phase | Mitigation |
|------|-------|------------|
| Entity extraction quality | Phase 1 | Validate on real vault before shipping |
| LLM latency | Phase 1 | Implement response caching early |
| User doesn't adopt | Phase 1 | Focus on one "wow" moment (finding forgotten info) |
| Context costs scale | Phase 2 | Implement smart context selection |
| Pattern detection accuracy | Phase 3 | Start simple, improve with data |
| Team complexity | Phase 4 | Validate demand before building |

---

## Milestones & Checkpoints

| Milestone | Target | Validation |
|-----------|--------|------------|
| **M0: Proof of Concept** | Week 1 | Add, search, query works end-to-end |
| **M1: MVP Launch** | Week 4 | 5 beta users using daily |
| **M2: Decision Intelligence** | Week 8 | Users tracking 80%+ decisions |
| **M3: Multi-Source** | Week 14 | 3+ integrations, proactive insights |
| **M4: v1.0 Launch** | Week 20 | Public launch, community forming |

---

## Next Steps

1. **Immediately**: Set up project repository and dependencies
2. **This week**: Implement entity models and SQLite store
3. **Next week**: Build Obsidian importer and test on real vault
4. **Week 3**: AI query interface and first usable CLI
5. **Week 4**: Polish and recruit beta users

---

## Appendix: File Structure (Final)

```
nexus/
├── pyproject.toml
├── README.md
├── LICENSE
├── nexus/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── add.py
│   │   │   ├── ask.py
│   │   │   ├── briefing.py
│   │   │   ├── decision.py
│   │   │   ├── export.py
│   │   │   ├── graph.py
│   │   │   ├── import_.py
│   │   │   ├── list.py
│   │   │   ├── search.py
│   │   │   └── sync.py
│   │   └── ui/
│   │       ├── __init__.py
│   │       └── components.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ontology/
│   │   │   ├── __init__.py
│   │   │   ├── entities.py
│   │   │   ├── relationships.py
│   │   │   └── schema.py
│   │   ├── store/
│   │   │   ├── __init__.py
│   │   │   ├── sqlite.py
│   │   │   └── vectors.py
│   │   └── sync/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── obsidian.py
│   │       ├── calendar.py
│   │       └── git.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── claude.py
│   │   │   └── local.py
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── openai.py
│   │   │   └── local.py
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── entities.py
│   │   │   └── decisions.py
│   │   ├── query/
│   │   │   ├── __init__.py
│   │   │   ├── context.py
│   │   │   └── engine.py
│   │   └── intelligence/
│   │       ├── __init__.py
│   │       ├── briefing.py
│   │       ├── patterns.py
│   │       └── proactive.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   └── utils/
│       ├── __init__.py
│       ├── tokens.py
│       └── cache.py
├── desktop/
│   ├── src/
│   │   └── ... (Tauri + React)
│   └── package.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_ontology.py
│   ├── test_store.py
│   ├── test_sync.py
│   ├── test_ai.py
│   └── fixtures/
│       └── ...
├── docs/
│   ├── getting-started.md
│   ├── architecture.md
│   ├── api-reference.md
│   └── plugins.md
└── examples/
    ├── basic_usage.py
    └── custom_entity_type.py
```
