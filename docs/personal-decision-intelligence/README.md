# NEXUS: Personal Decision Intelligence Platform

> Democratizing enterprise-grade decision intelligence for solo AI builders

## Research Initiative

This directory contains comprehensive research and planning documents for building **NEXUS** — a personal decision intelligence platform that brings Palantir/Databricks-class capabilities to individual builders.

## Documents

| Document | Description |
|----------|-------------|
| [RESEARCH_SYNTHESIS.md](./RESEARCH_SYNTHESIS.md) | Deep dive into Palantir Gotham, Foundry, and Databricks with transferable patterns |
| [PRD.md](./PRD.md) | Product Requirements Document with user stories and feature prioritization |
| [DESIGN_SPEC.md](./DESIGN_SPEC.md) | Technical architecture, data models, and system design |
| [RECOMMENDATIONS.md](./RECOMMENDATIONS.md) | Build vs. buy decisions and technology stack recommendations |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Phased implementation roadmap from MVP to v1.0 |

## Core Thesis

The same capabilities that give governments situational awareness and enterprises operational excellence can be reimagined for individuals—with AI as the great equalizer that makes "enterprise-grade" decision intelligence accessible at personal scale.

## Key Concepts Extracted

### From Palantir Gotham
- **Link Analysis**: Visual network exploration of connected entities
- **Entity Resolution**: Unify the same thing across data sources
- **Timeline Analysis**: Temporal view of events and decisions
- **Pattern Detection**: Find similarities across records
- **Provenance Tracking**: Know where information came from

### From Palantir Foundry
- **The Ontology**: Semantic layer mapping digital assets to real-world entities
- **Object-Centric Modeling**: Everything is an object with properties and relationships
- **Pipeline Orchestration**: Data flows from sources to insights
- **Workshop/Actions**: Operational applications on top of data

### From Databricks
- **Lakehouse Architecture**: Unified storage with ACID transactions
- **Time Travel**: Query any point in history
- **Unity Catalog**: Single governance model for all assets
- **Notebook-First**: Exploratory and operational in same environment

## Target Audience

**Primary**: Solo AI builders and technical founders
- Managing multiple domains (product, code, customers, finances, strategy)
- Information scattered across 15+ tools
- Making 50+ consequential micro-decisions daily
- No executive assistant, data team, or analysts

**What they need**:
- Make better decisions faster
- Build institutional memory (even as team of one)
- See connections they're missing
- Learn from their own patterns
- Spend less time searching, more time doing

## Proposed Solution: NEXUS

**NEXUS** (Network of EXperience, Understanding, and Synthesis) is a local-first personal decision intelligence platform featuring:

1. **Semantic Layer (Ontology)**: Unified model of the user's world
2. **Data Layer**: Multi-source integration with versioning
3. **Intelligence Layer**: AI-powered analysis and pattern recognition
4. **Action Layer**: Decision support and operational workflows

### Core Entity Types
- Person, Project, Decision, Goal, Event, Note, Resource, Source

### Key Features (MVP)
- Obsidian/Markdown import with entity extraction
- Natural language queries ("What do I know about X?")
- Decision tracking with outcome linking
- Daily briefings with pattern insights
- Graph visualization of relationships
- Local-first with privacy by default

## Technology Stack (Recommended)

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Entity Store | SQLite |
| Vector Store | ChromaDB |
| LLM | Claude API (+ Ollama fallback) |
| Embeddings | OpenAI (+ local fallback) |
| Desktop UI | Tauri + React |
| CLI | Textual |

## Implementation Timeline

| Phase | Duration | Goal |
|-------|----------|------|
| Phase 0: Foundation | Week 1 | Project setup, proof of concept |
| Phase 1: MVP | Weeks 2-4 | Obsidian import, AI chat, basic CLI |
| Phase 2: Decision Intelligence | Weeks 5-8 | Decision tracking, briefings, graph UI |
| Phase 3: Operational | Weeks 9-14 | Multi-source sync, patterns, mobile |
| Phase 4: Adaptive | Weeks 15-20 | Learning, teams, plugins, launch |

## Research Status

**Completed**: 2026-01-18

- [x] Palantir Gotham architecture analysis
- [x] Palantir Foundry ontology deep dive
- [x] Databricks lakehouse patterns
- [x] Solo builder needs assessment
- [x] Decision intelligence frameworks (OODA, etc.)
- [x] Product requirements document
- [x] Technical design specification
- [x] Build/buy/integrate recommendations
- [x] Phased implementation plan

## Next Steps

1. **Create repository**: Set up `nexus` project with dependencies
2. **Build entity models**: Pydantic models for ontology
3. **Implement storage**: SQLite + ChromaDB integration
4. **Obsidian import**: Parse and extract entities from markdown
5. **Query engine**: Context builder + LLM integration
6. **MVP CLI**: First usable version

---

*Generated as part of Personal Decision Intelligence Research Initiative*
*Inspired by: Palantir Gotham, Palantir Foundry, Databricks, and the needs of solo AI builders*
