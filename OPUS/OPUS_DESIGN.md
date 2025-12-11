# Converx OPUS - Unified Design Document

**Version**: 3.0 (Synthesized from Claude, Grok, and multi-model collaboration)
**Date**: January 2025
**Status**: Phase 0 (MVP) Complete - Full Vision Documented

---

## Design Philosophy

This document synthesizes work from multiple AI models into a unified vision:
- **Claude**: Technical architecture, detailed test cases, success engine
- **Grok**: Military-strategic terminology, truth-seeking framework, future archaeology
- **Cross-model**: Use cases, metrics, marketing manifesto

**Core Principle**: Build from truth, not from features. Reverse-engineer from maximum potential.

---

## 1. The Core Truth

**What Converx IS**: A personal cognitive OS + strategist that bridges human intuition with AI precision.

**What Converx IS NOT**: A task manager, chat interface, or productivity tool.

**The Fundamental Problem**: You make decisions based on incomplete information, optimistic estimates, and yesterday's priorities. Converx changes this.

**The Transformation**:
```
BEFORE: Hoping → AFTER: Knowing
BEFORE: Reactive → AFTER: Strategic
BEFORE: Siloed → AFTER: Integrated
BEFORE: Generic AI → AFTER: Personal Intelligence
```

---

## 2. Architecture Overview

```
+======================================================================+
|                    CONVERX STRATEGIC INTELLIGENCE                     |
+======================================================================+
|                                                                       |
|  +-----------------------+  +-----------------------+                 |
|  | LIFE WEATHER MAP      |  | VIRTUAL TWIN          |                 |
|  | (Domain Assessment)   |  | (Simulation Engine)   |                 |
|  +-----------------------+  +-----------------------+                 |
|           |                          |                                |
|           v                          v                                |
|  +----------------------------------------------------------+        |
|  |              COGNITIVE ENGINE (Multi-Agent Graph)         |        |
|  |                                                           |        |
|  |  [Strategist] -> [Researcher] -> [Simulator] -> [Coach]  |        |
|  |       |              |               |             |      |        |
|  |   owns goals     web/repo        twin sims      narrative |        |
|  |   routes         search          forecasts      guidance  |        |
|  +----------------------------------------------------------+        |
|                              |                                        |
|                              v                                        |
|  +----------------------------------------------------------+        |
|  |              KNOWLEDGE SUBSTRATE                          |        |
|  |  personal-ai-dataset | GitHub | Alpha Arena | Health      |        |
|  +----------------------------------------------------------+        |
|                              |                                        |
|                              v                                        |
|  +----------------------------------------------------------+        |
|  |              OUTPUT: Strategy + Next Best Action          |        |
|  |  - Current nowcast (where you are)                        |        |
|  |  - Recommended action (what to do)                        |        |
|  |  - Scenario bands (what might happen)                     |        |
|  |  - Cross-domain impacts (what else changes)               |        |
|  +----------------------------------------------------------+        |
|                                                                       |
+======================================================================+
```

---

## 3. Core Concepts

### 3.1 Status Map

A structured view of your life as interconnected domains:

**Domains**: Work/Code, Finance, Health/Energy, Learning, Relationships

**For each domain**:
- **State**: Key variables (workload, runway, energy, stress)
- **Weather**: Qualitative summary (Calm, Moderate Pressure, High Pressure, Storm)
- **Horizons**:
  - Nowcast: Current + next 24-72 hours
  - Short-term: 1-4 weeks (sprint horizon)
  - Long-term: Quarters/years (trajectory)

### 3.2 Routes & Waypoints

Instead of flat task lists, Converx models **routes**:

- **Goal**: Desired state in a domain (or across domains)
- **Route**: Ordered sequence of waypoints toward the goal
- **Waypoint**: Each step with:
  - Description and intent
  - Entry conditions (what must be true to start)
  - Exit conditions (what makes it complete)
  - Dependencies and cross-domain impacts

### 3.3 Forecast Range

Every route is evaluated in three scenarios:

- **Optimistic**: Best reasonable case (conditions: high focus, no blockers)
- **Likely**: Central trajectory (conditions: normal pace, some interruptions)
- **Conservative**: Safe, slower path (conditions: significant blockers)

Each scenario tied to explicit conditions - not guesses, but structured forecasts.

### 3.4 Virtual Twin

A simplified model of how your system evolves:

- **State Model**: Variables (focus hours, energy, burnout risk, runway)
- **Transition Model**: How actions change state (initially rules, later learned)
- **Observation Model**: Maps real data back to keep twin aligned
- **Forward Simulation**: Predict outcomes for candidate routes

---

## 4. Cognitive Engine

### Multi-Agent Graph Architecture

Not opaque chains - explicit, inspectable reasoning:

**Strategist**:
- Central node owning goals, routes, scenarios
- Decides which routes to propose, update, or abandon

**Researcher**:
- Pulls information from web, codebases, knowledge bases
- Integrations: personal-ai-dataset, GitHub, Alpha Arena

**Simulator**:
- Runs routes through Virtual Twin under different scenarios
- Produces distributions and qualitative likelihoods

**Synthesizer/Coach**:
- Turns raw outputs into narratives and guidance
- Provides reflection prompts and growth framing

**Executor** (later):
- Runs bounded playbooks under policy constraints
- Semi-autonomous execution with approvals

---

## 5. Knowledge Layer

### Unified Personal + Web Intelligence

All knowledge accessed through common interface:

```python
search(query, filters) -> List[TypedSnippet]
# Returns snippets with: domain, project, time, source, confidence

retrieve(resource_id) -> Artifact
# Fetch full underlying artifact
```

### Connectors

| Connector | Domain | Phase | Status |
|-----------|--------|-------|--------|
| Web Search | All | 0 | Ready |
| Repo/Docs | Work/Code | 0 | Ready |
| personal-ai-dataset | All | 3 | Planned |
| GitHub | Work/Code | 3 | Planned |
| Alpha Arena | Finance | 3 | Planned |
| Google Fit | Health | 3 | Planned |

---

## 6. Action & Autonomy Layer

### Playbooks

Declarative action templates:
- "Analyze repo and summarize risks"
- "Run tests and update route based on results"
- "Aggregate health data and adjust recommendations"

Each specifies: inputs, outputs, side effects, required approvals

### Policy Engine (Autonomy Ladder)

**Advisor Mode**: Propose only; everything manual
**Semi-Autonomous Mode**: Execute within granted scopes
**Critical Actions**: Always require explicit confirmation

---

## 7. Learning & Personalization

### What Gets Logged
- Context (state, routes, scenarios)
- Recommendation(s) and what you chose
- Actual outcomes where observable
- Your feedback (thumbs, comments)

### Reflection Jobs
- Compare predicted vs actual outcomes
- Adjust Virtual Twin parameters
- Extract personal heuristics ("multiply estimates by 1.4")
- Update default behaviors

### Preferences & Constraints
- Risk tolerances per domain
- Preferred working patterns
- Privacy boundaries

---

## 8. The Success Engine

### Three Feedback Loops

```
LOOP 1: CALIBRATION (Tactical)
Predict -> Act -> Observe -> Compare -> Adjust
Frequency: Daily/Weekly
Output: Accurate self-knowledge

LOOP 2: ALIGNMENT (Strategic)
Goal -> Route -> Actions -> Outcome -> Was it worth it?
Frequency: Weekly/Monthly
Output: Wisdom about what matters

LOOP 3: SUSTAINABILITY (Existential)
Work <-> Health <-> Finance <-> Relationships <-> Purpose
Frequency: Monthly/Quarterly
Output: Life that actually works
```

### Truth-Seeking Mechanisms

1. **Forced Uncertainty**: Scenario bands make uncertainty visible
2. **Retrospective Honesty**: Weekly reflection surfaces patterns
3. **Cross-Source Aggregation**: Show conflicting evidence
4. **Weather Doesn't Lie**: The metaphor cuts through self-deception

### Wisdom Accumulation

- **Decision Log**: Every significant decision with context and outcome
- **Pattern Library**: "When X happens, you tend to do Y, leading to Z"
- **Personal Heuristics**: "No complex work after 8pm"

---

## 9. The Five Dimensions of Winning

### Dimension 1: Clarity
Know exactly what matters, why, and when.
*"The anxiety of 'am I working on the right thing?' dissolves."*

### Dimension 2: Velocity
Move at maximum sustainable speed - not faster (burnout), not slower (waste).
*"The guilt of 'I should be doing more' fades."*

### Dimension 3: Sustainability
Win without breaking. Cross-domain impacts visible before sacrifice.
*"You can push hard when it matters because you're not always depleted."*

### Dimension 4: Learning
Get wiser, not just busier. Every outcome feeds back.
*"You start recognizing patterns before they fully emerge."*

### Dimension 5: Freedom
The ultimate outcome: more options, more runway, more capability.
*"The scarcity mentality fades. Decisions from abundance, not fear."*

---

## 10. The Evolution Path

### Phase 0: Foundation (COMPLETE)
- CLI interface: `converx next`, `converx status`
- Core orchestration working
- **Effort**: 2-3h / ~50K tokens

### Phase 1: Status Map + Forecast Range
- Domain status (calm/pressure/storm)
- Forecast range (optimistic/likely/conservative)
- Waypoint tracking
- **Effort**: 2-3h / ~50K tokens

### Phase 2: Routes & Multi-Domain
- Route planning with waypoints
- Entry/exit conditions
- Cross-domain visibility
- **Effort**: 4-6h / ~100K tokens

### Phase 3: Integrations
- personal-ai-dataset, GitHub, Alpha Arena, Health
- Unified knowledge layer
- **Effort**: 6-8h / ~150K tokens

### Phase 4: Playbooks & Executor
- Semi-autonomous playbook execution
- Policy engine
- **Effort**: 4-6h / ~100K tokens

### Phase 5: Virtual Twin + Learning
- State/transition models
- Forward simulation
- Learned optimization
- **Effort**: 8-12h / ~200K tokens

### Future (2030+)
- Phase 6: Network coordination
- Phase 7: Sub-self agents
- Phase 8: Truth engine
- Phase 9: Full symbiosis

---

## 11. Implementation Status

### Current (Phase 0)

```
converx/OPUS/
  cli.py                    # CLI entry point
  orchestrator.py           # Core orchestration
  formatter.py              # Output formatting
  tests/                    # 10 tests passing
```

### Target (Full Vision)

```
converx/OPUS/
  cli.py                    # CLI
  orchestrator.py           # Orchestration
  formatter.py              # Formatting
  
  strategy/                 # Phase 1-2
    model.py                # Goals, Routes, Waypoints
    status_map.py           # Domain status
    forecast.py             # Forecast range calculation
    domains.py              # Multi-domain support
  
  knowledge/                # Phase 3
    base.py                 # Connector interface
    personal_ai.py          # personal-ai-dataset
    github.py               # GitHub
    alpha_arena.py          # Finance
    health.py               # Health data
  
  twin/                     # Phase 5
    state.py                # State model
    transitions.py          # Transition rules
    simulation.py           # Forward simulation
  
  playbooks/                # Phase 4
    base.py                 # Playbook interface
    executor.py             # Execution engine
    policies.py             # Policy definitions
  
  memory/                   # Phase 1+
    store.py                # Snapshots
    reflection.py           # Predicted vs actual
```

---

## 12. Success Criteria

### Phase 0 (COMPLETE)
- [x] `converx next` returns actionable recommendation
- [x] More useful than running tools separately
- [x] Project filtering works
- [x] <5 seconds execution
- [x] 10 tests passing

### Phase 1
- [ ] Status map improves situational awareness
- [ ] Forecast range increases decision confidence
- [ ] Waypoint tracking in daily use

### Phase 5 (Full Vision)
- [ ] Virtual Twin predicts with 70%+ accuracy
- [ ] Calibrated from 30+ days of data
- [ ] Monte Carlo provides actionable insights
- [ ] Calibration score > 0.7

---

## 13. The Invitation

**Right now, you make decisions based on**:
- Gut feeling
- Incomplete information
- Optimistic estimates
- Yesterday's priorities

**What if you could make decisions based on**:
- Empirical patterns from YOUR history
- Complete context across domains
- Calibrated predictions with confidence
- Strategic priorities updated by reality

**That's the difference between hoping and knowing.**

Use Converx for one week. Just `converx next` each morning.

At the end, you'll know:
- What you actually accomplished
- How accurate your intuitions are
- What patterns are helping or hurting

**The system doesn't demand. It offers. The choice is yours.**

---

## Document References

| Document | Purpose |
|----------|---------|
| `OPUS_DESIGN.md` | This unified design document |
| `DESIGN_SPEC.md` | Technical specification with test cases |
| `USE_CASES.md` | Persona-based use cases |
| `SUCCESS_METRICS.md` | Measurement framework |
| `FUTURE_ARCHAEOLOGY.md` | 10-year evolution path |
| `MARKETING_MANIFESTO.md` | Why Converx matters |
| `STRATEGIC_RAMP_UP_PLAN.md` | Phased implementation guide |

---

*"The system that helps you see clearly is more valuable than the system that helps you do more. Clarity creates leverage. Leverage creates freedom. Freedom creates the space to do what actually matters."*

**Last Updated**: January 2025

