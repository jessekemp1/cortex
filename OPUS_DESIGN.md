# Converx - Strategist-First Life OS with Virtual Twin

## Opus Design Document

**Version**: 2.0  
**Created**: December 4, 2025  
**Updated**: December 5, 2025  
**Status**: Phase 0 (MVP) Complete - Phased Implementation Active

---

## Current Implementation Status

```
FULL VISION ─────────────────────────────────────────────── Phase 5
    Virtual Twin + Monte Carlo + Learned Models
                                        │
Phase 4 ────────────────────────────────┤ Playbooks & Executor
                                        │
Phase 3 ────────────────────────────────┤ Deep Integrations
                                        │
Phase 2 ────────────────────────────────┤ Multi-Domain + Routes
                                        │
Phase 1 ────────────────────────────────┤ Weather Map + Scenarios
                                        │
Phase 0 (MVP) ══════════════════════════╧═══ YOU ARE HERE
    Orchestrator + CLI + Basic Recommendations
```

**Phase 0 Complete**: Working MVP with `converx next` and `converx status`

---

## 1. Purpose and North Star

**Converx** is a **personal cognitive OS + strategist**: a local-first, semi-autonomous intelligence that continuously turns all your signals (code, docs, markets, health, habits, goals) into **clear strategies, forecasts, and next best actions**.

### Core Principles

- **Strategist-first**: coding/building and complex project execution are the primary initial domain.
- **Life OS-aware**: designed from day one for finance, health/energy, learning, and personal growth.
- **Virtual twin-driven**: maintains a structured model of "you + your system" and runs simulations to compare routes and estimate outcome probabilities.
- **Semi-autonomous**: proposes and can execute bounded playbooks under explicit policies and approvals.

### What Makes Converx Different

| Traditional AI Assistant | Converx |
|--------------------------|---------|
| Tasks and to-dos | Routes with waypoints |
| Q&A responses | Strategist loop with forecasts |
| Single answer | Scenario bands (optimistic/likely/conservative) |
| Context retrieval | Virtual twin simulation |
| Reactive assistance | Semi-autonomous with policies |
| Chat interface | Strategic reasoning engine |

---

## 2. Core Concepts

### 2.1 Strategic Domain Assessment

A structured, evolving picture of your life as a set of **domains**:

**Domains**: `Work/Code`, `Finance`, `Health/Energy`, `Learning`, `Relationships`, etc.

For each domain:

- **State**: key variables (e.g., workload, cognitive load, runway, volatility, sleep quality, stress, training volume)
- **Operational Status**: qualitative summary (critical/optimal readiness) - inspired by Vortex
- **Operational Horizons**:
  - **Current Assessment**: current state and next 24-72 hours
  - **Short-term strategic projection**: 1-4 weeks (sprint horizon)
  - **Long-term strategic position**: quarters/years (trajectory)

This is the substrate the strategist reasons over.

### 2.2 Mission Goals, Tactical Routes, and Operational Waypoints

Instead of flat task lists, Converx models **tactical routes**:

**Mission Goal**: desired state in a domain (or across domains)
- Example: "Ship Converx MVP in 3 weeks while maintaining sleep >= 7h and runway > 6 months."

**Tactical Route**: an ordered sequence of **operational waypoints**

**Operational Waypoint**: Each waypoint has:
- Description and intent
- Entry conditions (what needs to be true to start)
- Exit conditions (what makes it complete)
- Risk notes and dependencies on other domains

Converx navigates by picking and updating routes, not just enumerating tasks.

### 2.3 Scenarios and Strategic Projection Bands

Every route is evaluated in **strategic projection bands**:

- **Optimistic**: best reasonable case
- **Most likely**: central trajectory
- **Conservative**: safe, slower or more robust path

Each scenario is tied to conditions:
- "Optimistic if: uninterrupted 20 focused hours/week + no major external surprises."
- "Conservative if: we limit weekly load to protect energy and focus on minimal viable scope."

This is the human-readable analogue of ensemble forecasting in Vortex.

### 2.4 Virtual Twin

The **virtual twin** is a simplified model of how your system evolves over time:

**State model**:
- Encodes the Strategic Domain Assessment variables and constraints (time, capital, energy, risk tolerance)

**Transition model**:
- Rules/heuristics that approximate how actions (e.g., "push 60-hour week", "cut scope", "start new project", "increase cardio") tend to change each state variable
- Initially: hand-crafted + AI-assisted rules, later calibrated by your data

**Observation model**:
- Maps real-world data (repo status, commits, test history, P&L, health tracker metrics, calendar, logs) back into the twin to keep it aligned

Converx uses the twin to run **forward simulations** of routes and to compare options.

---

## 3. Architecture

### 3.1 System Overview

```
+------------------------------------------------------------------+
|                    CONVERX STRATEGIST                             |
+------------------------------------------------------------------+
|  STRATEGIC DOMAIN ASSESSMENT                                                 |
|  +------------+  +------------+  +------------+  +------------+  |
|  | Work/Code  |  | Finance    |  | Health     |  | Learning   |  |
|  | state,     |  | state,     |  | state,     |  | state,     |  |
|  | weather,   |  | weather,   |  | weather,   |  | weather,   |  |
|  | horizons   |  | horizons   |  | horizons   |  | horizons   |  |
|  +------------+  +------------+  +------------+  +------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|  COGNITIVE ENGINE (Multi-Agent Graph)                             |
|                                                                   |
|  [Strategist] --> [Researcher] --> [Simulator] --> [Synthesizer] |
|       |               |                |                |         |
|   owns goals      web/repo         virtual twin     narratives   |
|   routes          search           simulations      coaching     |
|   scenarios                                                       |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|  VIRTUAL TWIN                                                     |
|  - State model (variables: focus hours, energy, risk, runway)    |
|  - Transition model (how actions change state)                    |
|  - Observation model (real data -> twin alignment)                |
|  - Forward simulation of candidate routes                         |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|  OUTPUT: Strategy + Next Best Action                              |
|  - Current nowcast (where you are)                                |
|  - Recommended next waypoint                                      |
|  - Which scenario you're tracking (and why)                       |
|  - Forecast bands for each route option                           |
+------------------------------------------------------------------+
```

### 3.2 Cognitive Engine: Graph-Structured Multi-Agent Workflows

Converx uses a small, explicit **reasoning graph**, not opaque chains:

**Strategist**:
- Central node that owns goals, routes, scenarios, and the Strategic Domain Assessment
- Decides which routes to propose, update, or abandon

**Researcher**:
- Pulls in relevant information from:
  - Web search
  - Codebases and local docs
  - Later: personal-ai-dataset, Alpha Arena, Keto, StratOS, etc.

**Simulator**:
- Runs candidate routes through the virtual twin under different scenarios and horizons
- Produces distributions and qualitative likelihoods

**Synthesizer/Coach**:
- Turns raw outputs into narratives and guidance:
  - "If you choose Route A, here's your likely next month across work/finance/health."
- Provides reflection prompts and growth-oriented framing

**Executor (later)**:
- Runs bounded playbooks (tests, analyses, simulations, small refactors, data pulls) under policy constraints

Each user request or system event triggers a **predefined graph** (e.g., "plan project route" or "evaluate decision"), so it's inspectable and debuggable.

---

## 4. Knowledge Layer: Unified Personal + Web Intelligence

All knowledge is accessed through a **unified knowledge substrate**:

### Sources (connectors)

- Web search (default external oracle)
- Code repositories and product docs
- `personal-ai-dataset` (later)
- Alpha Arena / financial-aggregator outputs (finance)
- Keto / health trackers (health and energy)
- StratOS artifacts (goals, strategies, decisions)

### Common Interface

```python
search(query, filters) -> List[TypedSnippet]
# Returns snippets annotated with: domain(s), project, time, source, confidence

retrieve(resource_id) -> Artifact
# Fetch full underlying artifact if needed
```

### Optional Embeddings/Graph (later)

- Provide richer linking between entities
- "This research paper impacts Project X and Health Protocol Y"

**MVP**: implement only **WebSource** and a simple **Repo/Docs source**, but design the abstraction so others snap in cleanly.

---

## 5. Action & Autonomy Layer: Policy-Driven Playbooks

Converx can not only advise but also **take actions**, constrained by explicit policies:

### Playbooks

Declarative action templates:
- "Analyze repo and summarize risks"
- "Run tests and update project route based on results"
- "Simulate a portfolio strategy in Alpha Arena (paper-only)"
- "Aggregate last week's sleep + workload and adjust health-related guidance"

Each playbook specifies:
- Inputs, outputs
- Side effects (if any)
- Required approvals

### Policy Engine (Autonomy Ladder)

**Advisor mode**: propose; everything is manual

**Semi-autonomous mode**:
- Grant limited scopes per domain (allowed commands, data sources, frequencies)
- Critical actions (real trades, destructive file ops, major schedule changes) always require explicit confirmation

**MVP**: 1-2 playbooks focused on coding/project analysis, structured as a reusable layer.

---

## 6. Learning & Personalization

Converx improves as it observes you:

### Interaction & Outcome Log

For each decision, strategy, and playbook execution, log:
- Context (state, routes, scenarios)
- Recommendation(s) and what you chose
- Actual outcomes where observable
- Your feedback (thumbs, comments)

### Reflection Jobs

Strategist periodically reviews logs to:
- Compare **predicted vs actual** outcomes
- Adjust virtual twin parameters and routing heuristics
- Update default behaviors (e.g., prefer shorter sprints, less parallelism, or more conservative financial moves based on your pattern)

### Preferences & Constraints

Structured settings for:
- Risk tolerances per domain
- Preferred working patterns
- Privacy boundaries (what data Converx is allowed to see)

Feed directly into Strategist and Policy Engine.

---

## 7. Primary Surfaces and Integrations

Initial focus is **local-first, dev-centric**, with clean paths to full Life OS:

### Early Surfaces

- CLI / local HTTP endpoint for conversational access
- Integration points in:
  - Editor/terminal (e.g., ask: "What's my next best action for Converx?")
  - StratOS (Converx as the intelligence layer; StratOS as strategic board and visualization)

### Later Surfaces

- Minimal web UI for:
  - Chat with Converx
  - Viewing the Strategic Domain Assessment
  - Inspecting routes, scenarios, and simulation results
- Mobile-friendly view focused on "today's conditions" and suggested moves

---

## 8. Phased Implementation Roadmap

### Phase 0: Foundation MVP (COMPLETE)

**Status**: Done (2-3 hours)

**What Was Built**:
- `converx next` - Returns prioritized next action
- `converx status` - Shows current state summary
- `converx next PROJECT` - Project-specific filtering
- `--with-context` - Context predictions
- `--json` - Machine-readable output

**Architecture**:
- Orchestrates existing tools: ai_intelligence, goal_parser, recommendation_engine, context_intelligence
- Graceful degradation if tools missing
- ~800 lines, 11 tests passing

**Validates**: Core concept - unified strategist interface provides value

---

### Phase 1: Strategic Domain Assessment (2-3 hours)

**Goal**: Add strategic framing to recommendations

**Features**:
- **Current Assessment**: Current state with operational readiness metaphor (critical/optimal)
- **Strategic Projection Bands**: Optimistic/Likely/Conservative for each recommendation
- **Waypoint Tracking**: Mark actions as complete, track progress

**New Commands**:
```bash
converx operational_status              # Show Strategic Domain Assessment (Work/Code domain)
converx complete WAYPOINT_ID # Mark waypoint complete
```

**Files to Add**:
- `strategy/operational_status.py` - Operational status state and metaphors
- `strategy/strategic_projection.py` - Strategic projection band calculation

---

### Phase 2: Tactical Routes & Multi-Domain (4-6 hours)

**Goal**: Move from flat recommendations to route-based planning

**Features**:
- **Tactical Routes**: Ordered sequences of waypoints toward goals
- **Entry/Exit Conditions**: What needs to be true to start/complete
- **Multi-Domain**: Add Finance, Health domains (structure only)
- **Cross-Domain Visibility**: See how Work affects Health, etc.

**New Commands**:
```bash
converx route "Ship VortexV2"   # Create/view route to goal
converx forecast ROUTE_ID       # Show scenario bands for route
converx domains                 # Show all domain operational readiness
```

**Files to Add**:
- `strategy/model.py` - Mission goal, Tactical route, Operational waypoint dataclasses
- `strategy/domains.py` - Multi-domain operational readiness map

---

### Phase 3: Deep Integrations (6-8 hours)

**Goal**: Connect to real data sources across domains

**Connectors**:
- `personal-ai-dataset` - Knowledge base search
- `Alpha Arena` - Financial signals, portfolio status
- `Google Fit / Pixel Watch` - Health metrics (steps, HR, sleep)
- `financial-aggregator` - Account balances
- `GitHub` - Repo status, issues, PRs
- `StratOS` - Strategic visualization

**Files to Add**:
- `knowledge/personal_ai.py` - personal-ai-dataset connector
- `knowledge/alpha_arena.py` - Alpha Arena connector
- `knowledge/google_fit.py` - Health data connector
- `knowledge/github.py` - GitHub connector

---

### Phase 4: Playbooks & Executor (4-6 hours)

**Goal**: Semi-autonomous execution with policies

**Features**:
- **Playbooks**: Declarative action templates
- **Policy Engine**: Autonomy ladder (advisor -> semi-auto)
- **Approval Workflows**: Critical actions require confirmation
- **Bounded Execution**: Run tests, analyses, data pulls

**Example Playbooks**:
- "Analyze repo and summarize risks"
- "Run tests and update route based on results"
- "Aggregate health data and adjust recommendations"

**Files to Add**:
- `playbooks/base.py` - Playbook interface
- `playbooks/executor.py` - Execution engine
- `playbooks/policies.py` - Policy definitions

---

### Phase 5: Virtual Twin + Advanced Learning (8-12 hours)

**Goal**: Predictive simulation and learned optimization

**Features**:
- **State Model**: Variables for focus, energy, burnout, runway
- **Transition Model**: How actions change state (initially rules, later learned)
- **Forward Simulation**: Predict outcomes for candidate routes
- **Predicted vs Actual**: Track accuracy, calibrate twin
- **Monte Carlo**: Probabilistic scenario planning

**Files to Add**:
- `twin/state.py` - State model
- `twin/transitions.py` - Transition rules
- `twin/simulation.py` - Forward simulation
- `memory/reflection.py` - Predicted vs actual tracking

---

### Feature Preservation Matrix

All features from the original vision mapped to phases:

| Feature | Phase | Status |
|---------|-------|--------|
| CLI interface | 0 | DONE |
| Next action recommendations | 0 | DONE |
| Project filtering | 0 | DONE |
| Context predictions | 0 | DONE |
| JSON output | 0 | DONE |
| Current Assessment (operational readiness metaphor) | 1 | Planned |
| Strategic Projection Bands | 1 | Planned |
| Waypoint tracking | 1 | Planned |
| Tactical routes with waypoints | 2 | Planned |
| Entry/exit conditions | 2 | Planned |
| Multi-domain operational readiness map | 2 | Planned |
| personal-ai-dataset integration | 3 | Planned |
| Alpha Arena integration | 3 | Planned |
| Google Fit integration | 3 | Planned |
| GitHub integration | 3 | Planned |
| StratOS integration | 3 | Planned |
| Playbooks | 4 | Planned |
| Policy engine | 4 | Planned |
| Semi-autonomous execution | 4 | Planned |
| Virtual twin state model | 5 | Planned |
| Forward simulation | 5 | Planned |
| Learned transitions | 5 | Planned |
| Monte Carlo scenarios | 5 | Planned |
| Reflection/calibration | 5 | Planned |

---

## 9. File Structure

### Current (Phase 0 - MVP)
```
converx/
  __init__.py               # Package init
  cli.py                    # CLI entry point (DONE)
  orchestrator.py           # Core orchestration (DONE)
  formatter.py              # Output formatting (DONE)
  converx                   # Entry point script (DONE)
  README.md                 # Documentation (DONE)
  tests/
    test_orchestrator.py    # Unit tests (DONE)
    test_formatter.py       # Formatter tests (DONE)
```

### Target (Full Vision)
```
converx/
  cli.py                    # Entry point (Phase 0)
  orchestrator.py           # Core orchestration (Phase 0)
  formatter.py              # Output formatting (Phase 0)
  
  strategy/                 # Phase 1-2
    model.py                # Mission goal, Tactical route, Operational waypoint, Scenario
    operational_status.py          # Operational status state and metaphors
    strategic_projection.py            # Strategic projection band calculation
    domains.py              # Multi-domain support
  
  agents/                   # Phase 2-3
    researcher.py           # Web + repo search
    simulator.py            # Virtual twin simulations
    synthesizer.py          # Narrative output, coaching
  
  twin/                     # Phase 5
    state.py                # State model (variables)
    transitions.py          # How actions change state
    simulation.py           # Forward simulation engine
  
  knowledge/                # Phase 3
    base.py                 # Common interface
    personal_ai.py          # personal-ai-dataset connector
    alpha_arena.py          # Alpha Arena connector
    google_fit.py           # Health data connector
    github.py               # GitHub connector
  
  memory/                   # Phase 1+
    store.py                # Strategy snapshots, decisions
    reflection.py           # Predicted vs actual analysis
  
  playbooks/                # Phase 4
    base.py                 # Playbook interface
    executor.py             # Execution engine
    policies.py             # Policy definitions
```

---

## 10. Next Implementation: Phase 1

**Prerequisite**: Validate Phase 0 MVP with daily usage (1 week)

### Phase 1 Block 1 - Strategic Domain Assessment (1-2h)

- Create `strategy/operational_status.py`
- Define operational readiness states: critical, optimal, storm
- Map project activity to operational readiness metaphors
- Update `converx status` to show operational readiness

### Phase 1 Block 2 - Strategic Projection Bands (1-2h)

- Create `strategy/strategic_projection.py`
- Add optimistic/likely/conservative bands to recommendations
- Calculate bands based on:
  - Project momentum (commits, activity)
  - Blockers and risks
  - Historical patterns (if available)
- Update formatter to show strategic projection bands

### Phase 1 Block 3 - Waypoint Tracking (1h)

- Add `converx complete WAYPOINT_ID` command
- Store completion status in JSON file
- Show progress on routes (x/y complete)
- Update recommendations based on completed waypoints

---

## 11. Example Interactions

### Phase 0 (Current MVP)

```bash
$ converx next

+==============================================================+
|              CONVERX - STRATEGIC NEXT ACTION                  |
+==============================================================+

CURRENT STATE
------------------------------------------------------------
Active Projects: 3 (VortexV2, alpha_arena, converx)
Priority A Goals: 2 pending, 1 in progress
Blockers: 1 (VortexV2: Missing sensor preprocessing)

NEXT ACTION
------------------------------------------------------------
[HIGH PRIORITY] Complete Block 1.2: Sensor Data Preprocessing

Why: Priority A goal from ACTION_PLAN.md. Blocks VortexV2 MVP 
completion (currently 60% complete).

Effort: 4-6 hours
Impact: High

Next Steps:
  - Migrate sensor preprocessing from Vortex
  - Add outlier detection, quality scoring
  - Verification: pytest tests/unit/test_sensor_preprocessing.py

ALTERNATIVE ACTIONS
------------------------------------------------------------
2. [MEDIUM] Configure environment for keto-tracker
3. [MEDIUM] Alpha Arena - Trading Engine Hardening
```

### Phase 1 (Strategic Domain Assessment + Scenarios) - Future

```bash
$ converx operational_status

STRATEGIC DOMAIN ASSESSMENT - Work/Code
------------------------------------------------------------
Operational Readiness: Optimal (deadline approaching)
Current Assessment: 3 active projects, 2 blockers identified

STRATEGIC PROJECTION BANDS for "Complete VortexV2 MVP":
  Optimistic:    10 days (if 25h focused/week, no blockers)
  Most Likely:   14 days (if 18h focused/week)  <-- tracking
  Conservative:  21 days (if interruptions occur)
```

### Phase 2 (Tactical Routes) - Future

```bash
$ converx route "Ship VortexV2 MVP"

ROUTE: Ship VortexV2 MVP
------------------------------------------------------------
Progress: 3/6 waypoints complete (50%)

  [x] Block 1.1: Project Setup
  [x] Block 1.2: Sensor Preprocessing  
  [x] Block 1.3: Data Ingestion API
  [>] Block 1.4: ML Model Integration (in progress)
  [ ] Block 1.5: Scoring System
  [ ] Block 1.6: Integration Tests

NEXT WAYPOINT: Block 1.4 - ML Model Integration
  Entry: Data pipeline working, test data available
  Exit: Models return predictions via API
  Estimated: 4-6 hours
```

---

## 12. Success Criteria (Per Phase)

### Phase 0 Success (ACHIEVED)
- [x] `converx next` returns actionable next step
- [x] Output more useful than running tools separately
- [x] Project filtering works
- [x] Executes in <5 seconds
- [x] 11 tests passing

### Phase 1 Success
- [ ] Operational readiness metaphor helps frame current state
- [ ] Strategic projection bands (opt/likely/cons) improve decision confidence
- [ ] Can mark waypoints complete and track progress
- [ ] Used daily for 1 week with positive feedback

### Phase 2 Success
- [ ] Tactical routes with waypoints improve project planning
- [ ] Entry/exit conditions clarify what's needed
- [ ] Multi-domain visibility useful (even if minimal data)
- [ ] Can forecast route completion with scenario bands

### Phase 3 Success
- [ ] At least 3 integrations providing real data
- [ ] Cross-domain insights emerge (e.g., work impacts health)
- [ ] Knowledge base search improves recommendations

### Phase 4 Success
- [ ] At least 2 playbooks executing reliably
- [ ] Policy engine prevents unwanted actions
- [ ] Semi-autonomous mode saves significant time

### Phase 5 Success (Full Vision)
- [ ] Virtual twin predicts outcomes with 70%+ accuracy
- [ ] Learned from 30+ days of historical data
- [ ] Monte Carlo scenarios provide actionable insights
- [ ] Productizable for other advanced AI users

---

## 13. Estimated Effort (Phased)

| Phase | Effort | Outcome | Status |
|-------|--------|---------|--------|
| Phase 0 | 2-3 hours | MVP: CLI + Orchestrator | DONE |
| Phase 1 | 2-3 hours | Strategic Domain Assessment + Scenarios | Next |
| Phase 2 | 4-6 hours | Tactical Routes + Multi-Domain | Planned |
| Phase 3 | 6-8 hours | Deep Integrations | Planned |
| Phase 4 | 4-6 hours | Playbooks + Executor | Planned |
| Phase 5 | 8-12 hours | Virtual Twin + Learning | Planned |
| **Full Vision** | **26-38 hours** | **Complete Life OS** | - |

**Incremental Value**: Each phase delivers standalone value. Stop at any phase.

---

## 14. Validation Gates

Before proceeding to next phase, validate current phase provides value:

### Phase 0 -> Phase 1 Gate
- [ ] Used `converx next` daily for 1 week
- [ ] Recommendations were actionable 70%+ of time
- [ ] Identified need for scenario/weather framing

### Phase 1 -> Phase 2 Gate
- [ ] Operational readiness metaphor helps decision-making
- [ ] Strategic projection bands improve confidence in choices
- [ ] Need for route-based planning identified

### Phase 2 -> Phase 3 Gate
- [ ] Tactical routes with waypoints improve project tracking
- [ ] Multi-domain visibility is useful
- [ ] Ready to connect real data sources

### Phase 3 -> Phase 4 Gate
- [ ] Integrations provide actionable insights
- [ ] Want automated actions, not just recommendations
- [ ] Policies and approvals needed for safety

### Phase 4 -> Phase 5 Gate
- [ ] Playbooks executing reliably
- [ ] Need predictive simulation for decisions
- [ ] Enough historical data to train twin

---

**This design captures**: strategist-first focus, Strategic Domain Assessment, tactical routes/waypoints, strategic projection bands, Vortex-inspired forecasting, and a virtual twin capable of running simulations to estimate outcome probabilities - while keeping the MVP core small, testable, and extensible.

