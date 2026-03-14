# Implementation Plan: Motivational Quote App

## Overview
Build a personalized motivational quote engine on top of Cortex's persistent intelligence layer. The app learns users' goals, challenges, values, and patterns to deliver precision motivation tuned to their full-potential optimization journey.

Full spec written to: `MOTIVATIONAL_QUOTE_APP_SPEC.md`

---

## Implementation Steps (Phase 1 — Foundation)

### Step 1: Create data models (`cortex/motivation/models.py`)
- `UserMotivationProfile` — goals, values, tone preferences, challenges, energy patterns
- `Goal` with milestones, deadlines, blockers, status tracking
- `LifeDomain` enum (career, health, relationships, growth, finance, creativity, spirituality)
- `Challenge` with severity, domain linkage, coping strategies
- `Quote` with full taxonomy: themes, tone vector, philosophy, best-for-states
- `PotentialMap` and `DomainPotential` for growth tracking
- `GrowthTrajectory` with snapshots, patterns, inflection points

### Step 2: Build quote database layer (`cortex/motivation/quote_database.py`)
- In-memory quote store with YAML/JSON seed data
- Taxonomy-based filtering (theme, domain, tone, philosophy)
- Embedding index integration point for Cortex `SemanticMemory`
- Quote deduplication and quality validation

### Step 3: Create curated quote seed data (`cortex/motivation/data/quotes.yaml`)
- 500+ quotes organized by theme, domain, tone, philosophy
- Sources: classical philosophy, historical leaders, modern thought leaders, literature
- Full tagging per the `Quote` model taxonomy

### Step 4: Build profile manager (`cortex/motivation/profile_manager.py`)
- Profile creation from onboarding answers
- Goal CRUD operations
- Challenge logging and resolution
- Motivational state detection (momentum/plateau/crisis/breakthrough/drift)
- Integration with Cortex `GoalParser` for natural-language goal intake

### Step 5: Implement quote scoring engine (`cortex/motivation/quote_engine.py`)
- Multi-signal scoring: goal relevance, challenge match, tone fit, philosophy affinity, temporal fit, novelty, resonance prediction
- Repetition decay penalty
- Candidate ranking and selection
- Integration hooks for Cortex `SemanticMemory` and `EpisodicMemory`

### Step 6: Build delivery system (`cortex/motivation/delivery.py`)
- Quote formatting with author attribution and context
- Schedule-based delivery via Cortex `Scheduler`
- Morning briefing generation (leveraging `briefing.py` pattern)
- Challenge mode: curated multi-quote sequences

### Step 7: Implement feedback/learning loop (`cortex/motivation/learning.py`)
- Quote rating capture (1-5 + "this hit different")
- Implicit signal tracking (read time, save, share, skip)
- Resonance model updates from feedback
- Anti-pattern detection (quote types that consistently miss)
- Integration with Cortex `FeedbackLoop`

### Step 8: Build API layer (`cortex/motivation/api.py`)
- FastAPI endpoints for all operations (profile, goals, challenges, quotes, ratings, briefings, journal, check-ins, potential map, trajectory)
- Request/response schemas
- Rate limiting via existing Cortex patterns

### Step 9: Quote conversations (`cortex/motivation/conversations.py`)
- LLM-powered quote interpretation through user's personal context
- Model routing: Haiku for selection, Sonnet for conversations
- Context injection from user profile and current challenges

### Step 10: Tests
- Unit tests for scoring algorithm
- Integration tests for profile → quote → feedback loop
- Quote database validation (taxonomy completeness)
- API endpoint tests
- State detection accuracy tests

---

## Key Architectural Decisions

1. **Module location**: `cortex/motivation/` — new top-level package within cortex
2. **Cortex integration**: Deep integration with SemanticMemory, EpisodicMemory, GoalParser, Scheduler, FeedbackLoop
3. **Quote storage**: YAML seed data + in-memory index, upgradeable to embedded DB
4. **Model routing**: Haiku for quick scoring, Sonnet for conversations and briefings
5. **State detection**: Rule-based initially, upgradeable to ML-based pattern detection

## Files to Create

```
cortex/motivation/__init__.py
cortex/motivation/models.py
cortex/motivation/quote_database.py
cortex/motivation/quote_engine.py
cortex/motivation/profile_manager.py
cortex/motivation/delivery.py
cortex/motivation/learning.py
cortex/motivation/conversations.py
cortex/motivation/potential.py
cortex/motivation/api.py
cortex/motivation/data/quotes.yaml
tests/test_motivation_models.py
tests/test_quote_engine.py
tests/test_profile_manager.py
tests/test_motivation_api.py
MOTIVATIONAL_QUOTE_APP_SPEC.md  (already created)
```
