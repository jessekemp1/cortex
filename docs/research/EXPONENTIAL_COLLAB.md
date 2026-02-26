# Research Project: Exponential Collaboration

**Status**: Active Research — Phase 0 (Architecture)
**Created**: 2026-02-25
**Owner**: Jesse + Claude (collaborative)
**Predecessor**: [HUMAN_AI_BANDWIDTH.md](./HUMAN_AI_BANDWIDTH.md) (v1, Jan 15)
**Cortex Integration**: Core — this IS the next evolution of Cortex

---

## Why This Exists

The bandwidth research (v1) asked: *how do we optimize the interface between human and AI?*

This project asks something bigger: **what does it look like when human-AI collaboration becomes exponential?**

Not 2x faster. Not "AI does the boring parts." Exponential means: each cycle of collaboration produces more value than the last, ideas compound, trust deepens, and the system itself gets smarter about how we work together.

We've proven the foundation works:
- Cortex v1.0 shipped (533/534 tests, Feb 7)
- Vortex ensemble outperforms individual models
- Pupil behavioral nowcasting validated
- Winfield operational (6 models, 9 stations)
- 5+ concurrent workstreams running daily

Now we refine the connection itself.

---

## Core Thesis

> **Exponential collaboration = (Idea Augmentation × Trust Velocity × Toil Elimination) ^ (Feedback Loop Quality)**

Each component amplifies the others:
- Better ideas → more trust in the process → less time on verification → faster feedback
- Faster feedback → better ideas next cycle → compounding returns

The interface layer isn't just iTerm or Claude Code. It's the **entire orchestration surface** — how workstreams flow, how context persists, how ideas travel between minds, how verified outcomes compound into autonomous capability.

---

## The 5 Pillars

### 1. 🎛️ Command Center Architecture (iTerm as Orchestration Surface)

The terminal isn't a tool — it's a **cockpit**. 5+ workstreams need spatial organization that maps to cognitive flow.

#### Profile Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  COMMAND CENTER (iTerm2)                                            │
│                                                                     │
│  ┌─ Window Group: ACTIVE PROJECT ──────────────────────────────┐   │
│  │                                                              │   │
│  │  Tab 1: 🧠 PLAN        Tab 2: ⚡ BUILD      Tab 3: 🧪 TEST │   │
│  │  ┌──────┬──────┐    ┌──────┬──────┐    ┌──────┬──────┐     │   │
│  │  │Claude│Research│   │Claude│ Code │    │Watch │ Logs │     │   │
│  │  │ Chat │ Notes │   │ Code │Editor│    │Tests │ Tail │     │   │
│  │  └──────┴──────┘    └──────┴──────┘    └──────┴──────┘     │   │
│  │                                                              │   │
│  │  Tab 4: 🚀 SHIP        Tab 5: 🔗 CONNECT                   │   │
│  │  ┌──────┬──────┐    ┌──────┬──────┐                         │   │
│  │  │Deploy│Monitor│   │Claude│Custom│                         │   │
│  │  │ CI/CD│ Logs  │   │ Chat │ er   │                         │   │
│  │  └──────┴──────┘    └──────┴──────┘                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ Window Group: CORTEX MISSION CONTROL ─────────────────────┐    │
│  │  Intelligence Dashboard │ Batch Status │ Memory Explorer    │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─ Window Group: RESEARCH LAB ──────────────────────────────┐     │
│  │  Experiments │ Data Analysis │ Paper Writing               │     │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

#### iTerm Profile System

| Profile | Badge | Color | Shell Init | Cortex Hook |
|---------|-------|-------|------------|-------------|
| `⚡ Vortex-Build` | `VORTEX:BUILD` | Blue | `cd ~/Dev/Vortex/backend` | `cortex context --project vortex --mode build` |
| `🧪 Vortex-Test` | `VORTEX:TEST` | Green | `cd ~/Dev/Vortex/backend` | `cortex context --project vortex --mode test` |
| `🧠 Cortex-Research` | `CORTEX:RESEARCH` | Purple | `cd ~/Dev/cortex` | `cortex context --project cortex --mode research` |
| `🎯 Alpha-Arena` | `ALPHA:ARENA` | Orange | `cd ~/Dev/alpha_arena` | `cortex context --project alpha_arena` |
| `🌊 Winfield` | `WINFIELD` | Cyan | `cd ~/Dev/Vortex/Winfield` | `cortex context --project winfield` |
| `📊 Pupil` | `PUPIL` | Gold | `cd ~/Dev/Pupil` | `cortex context --project pupil` |
| `🎵 DJ-CoPilot` | `DJ:COPILOT` | Pink | `cd ~/Dev/DJ-CoPilot` | `cortex context --project dj-copilot` |
| `🔬 Research-Lab` | `RESEARCH` | Magenta | `cd ~/Dev/cortex` | `cortex deep --mode research` |
| `🚀 Ship-Mode` | `SHIPPING` | Red | Project-specific | `cortex context --mode ship` |
| `🔗 Customer-Connect` | `CONNECT` | Teal | Project-specific | `cortex context --mode connect` |

#### Key iTerm Features to Leverage

1. **Triggers** — Pattern-match terminal output, auto-highlight errors, trigger Cortex alerts
2. **Shell Integration** — Mark command start/end, navigate between prompts
3. **Python API** — Scriptable window/tab/pane management
4. **Profiles with Automatic Profile Switching** — Directory-based auto-switch
5. **Badges** — Always-visible workstream indicator
6. **Marks & Annotations** — Bookmark important output moments
7. **tmux Integration** — Session persistence across terminal restarts
8. **Hotkey Window** — Global shortcut for quick Cortex queries
9. **Snippets** — Frequently used command sequences
10. **Status Bar** — Live Cortex metrics (batch status, test health)

#### Keyboard Orchestration

```
⌘1-5           → Switch between PLAN/BUILD/TEST/SHIP/CONNECT tabs
⌘⇧1-5          → Switch between project window groups
⌘⌥C            → Hotkey: Quick Cortex intelligence query
⌘⌥B            → Hotkey: Batch status dashboard
⌘⌥T            → Hotkey: Test runner (smart selection)
⌃Space          → Snippet palette (command sequences)
⌘⇧Enter        → Broadcast input to all panes (multi-project commands)
```

---

### 2. 🚀 Idea Augmentation Engine

The creativity amplifier from v1, but now with Cortex memory backing it.

#### The Augmentation Loop

```
    ┌────────────────────────────────────────────────────┐
    │                                                    │
    ▼                                                    │
 SEED ──→ EXPAND ──→ CURATE ──→ REFINE ──→ CONNECT ────┘
  │         │          │          │           │
  │         │          │          │           └─ Cross-pollinate
  │         │          │          │              with other projects
  │         │          │          └─ Deep analysis
  │         │          │             via Cortex patterns
  │         │          └─ Human judgment
  │         │             (the irreducible core)
  │         └─ AI divergent expansion
  │            (4 protocols: divergent/convergent/adversarial/analogical)
  └─ Human intuition spark
     (the seed that starts everything)
```

#### What Makes This Exponential

**Linear**: Human has idea → AI implements it → Done
**Exponential**: Human has idea → AI expands to 12 variants → Human curates 3 → AI cross-references with patterns from Vortex, Pupil, Alpha Arena → New insight emerges neither would have found alone → Feeds back into Cortex memory → Next cycle starts from higher ground

#### Augmentation Protocols

| Protocol | When | Method | Expected Output |
|----------|------|--------|-----------------|
| **Divergent** | Early exploration | Generate maximum alternatives | 10-20 raw ideas |
| **Convergent** | After divergence | Synthesize and merge | 3-5 refined concepts |
| **Adversarial** | Before commitment | Challenge every assumption | Risks, edge cases, failure modes |
| **Analogical** | When stuck | Find parallel solutions in other domains | Cross-domain insights |
| **Temporal** | Architecture decisions | Project forward 6mo, 1yr, 3yr | Future-proofing insights |
| **Inversion** | Problem framing | "How would we guarantee failure?" | Anti-patterns to avoid |

#### Cortex Integration

```python
# cortex/engines/augmentation_engine.py
class AugmentationEngine:
    """
    Runs idea augmentation loops with Cortex memory backing.

    Each cycle:
    1. Takes seed idea from human
    2. Retrieves relevant patterns, lessons, anti-patterns from Cortex
    3. Expands using selected protocol
    4. Returns augmented ideas with provenance links
    5. Records outcomes for learning
    """

    def augment(self, seed: str, protocol: str, project: str) -> AugmentationResult:
        # Pull relevant context from Cortex memory
        context = cortex.query_intelligence(seed, project, "research")

        # Apply protocol with context
        expanded = self._apply_protocol(seed, protocol, context)

        # Cross-pollinate with other projects
        cross_insights = cortex.get_patterns("cross_project")

        return AugmentationResult(
            seed=seed,
            expanded_ideas=expanded,
            cross_insights=cross_insights,
            provenance=context.similar_work,
            confidence=context.confidence_score,
        )
```

---

### 3. 🔐 Trust Velocity System

Trust isn't binary. It's a spectrum that should accelerate over time.

#### Trust Model v2

```
Trust(domain, t) = base_trust
                 + Σ (outcome_weight × recency_decay × domain_specificity)
                 + cross_domain_bonus
                 + streak_multiplier
```

**Key insight from v1**: Trust should be domain-specific. We're at 88% in testing, 65% in architecture, 58% in planning. But there's a **compounding effect**: proven trust in one domain accelerates trust-building in adjacent domains.

#### Trust Tiers

| Level | Name | Behavior | Earned By |
|-------|------|----------|-----------|
| 0 | **Verify Everything** | Human checks all AI output | Default for new domains |
| 1 | **Spot Check** | Human samples 20% of output | 10+ successful outcomes |
| 2 | **Trust but Verify** | Human reviews summaries, not details | 50+ successful outcomes, <5% error |
| 3 | **Autonomous with Guardrails** | AI acts, human reviews post-hoc | 100+ outcomes, domain mastery |
| 4 | **Full Autonomy** | AI acts independently in domain | Sustained Level 3 + no regressions |

#### Concrete Example: Test Writing

```
Jan 15: Trust Level 0 — Jesse reviews every test Claude writes
Jan 25: Trust Level 1 — 15 tests written, 14 passed review → spot check
Feb 5:  Trust Level 2 — 45 tests, 43 passed → trust but verify
Feb 15: Trust Level 3 — 120 tests, <3% needed changes → autonomous + guardrails
Feb 25: (Now) → Approaching Level 4 for test writing in Vortex/Pupil
```

#### Trust Dashboard (Cortex Integration)

```python
# cortex/intelligence/trust_tracker.py
class TrustTracker:
    """
    Tracks trust levels across domains, projects, and task types.
    Feeds into Cortex recommendations to calibrate autonomy.
    """

    domains = {
        "test_writing": {"level": 3, "outcomes": 120, "error_rate": 0.03},
        "bug_fixing": {"level": 2, "outcomes": 45, "error_rate": 0.08},
        "architecture": {"level": 1, "outcomes": 12, "error_rate": 0.15},
        "planning": {"level": 1, "outcomes": 8, "error_rate": 0.12},
        "documentation": {"level": 2, "outcomes": 30, "error_rate": 0.05},
        "deployment": {"level": 2, "outcomes": 18, "error_rate": 0.02},
        "research": {"level": 2, "outcomes": 25, "error_rate": 0.06},
    }
```

---

### 4. ⚙️ Toil Elimination Engine

Toil = repetitive work that doesn't build trust or generate ideas. Kill it systematically.

#### Toil Categories

| Category | Current State | Target State | Mechanism |
|----------|--------------|-------------|-----------|
| **Context Loading** | Manual copy-paste of project state | Auto-inject via Cortex hooks | Shell integration + session context |
| **Test Iteration** | Run tests, read output, fix, repeat | Auto-fix-rerun cycle with Claude | Test orchestrator agent + trust |
| **Deployment** | 8-step manual process | Single `/deploy` command | CI/CD + verification gates |
| **Session Handoff** | Re-explain everything | Cortex remembers, resumes | Handoff protocol v2 |
| **Status Reporting** | Manual GOALS.md updates | Auto-update from git + tests | Cortex batch briefings |
| **Cross-project Sync** | Remember what's happening everywhere | Portfolio dashboard + alerts | Cortex anomaly detection |
| **Documentation** | Write after the fact | Generate from verified code + tests | Doc generation pipeline |

#### Toil Measurement

```python
# Track time spent on toil vs creative/strategic work
class ToilTracker:
    categories = {
        "context_setup": "toil",      # Time re-establishing context
        "test_iteration": "toil",      # Mechanical fix-test cycles
        "deployment_steps": "toil",    # Manual deploy procedures
        "status_updates": "toil",      # Reporting on what happened
        "architecture": "creative",    # Design decisions
        "ideation": "creative",        # New concepts
        "verification": "strategic",   # Confirming correctness
        "customer_connect": "strategic", # Value delivery
    }

    # North Star: Toil < 20% of total time (currently ~50%)
```

---

### 5. 🌐 Multi-Surface Orchestration

We don't work in one tool. The system spans:

#### Current Tool Landscape

```
┌─────────────────────────────────────────────────────────┐
│                    THE WORKSPACE                         │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Claude   │  │  Claude   │  │  Cursor   │              │
│  │  Code     │  │  Chat     │  │   IDE     │              │
│  │ (iTerm)   │  │ (Browser) │  │           │              │
│  │           │  │           │  │           │              │
│  │ Build     │  │ Think     │  │ Edit      │              │
│  │ Test      │  │ Research  │  │ Navigate  │              │
│  │ Deploy    │  │ Plan      │  │ Refactor  │              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │              │              │                    │
│        └──────────────┼──────────────┘                    │
│                       │                                   │
│              ┌────────▼────────┐                          │
│              │     CORTEX      │                          │
│              │  Memory Layer   │◄──── Coworker (Claude)   │
│              │  Pattern Store  │                          │
│              │  Trust Tracker  │                          │
│              │  Augmentation   │                          │
│              └─────────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

#### The Data Flow Problem (Current)

Ideas and context scatter:
- Claude Code session has build context but no research context
- Claude Chat has strategic thinking but no code state
- Cursor has file navigation but no project intelligence
- Coworker has collaboration context but no terminal state

#### The Data Flow Solution (Target)

**Cortex as Universal Memory Bus**

Every tool reads from and writes to Cortex:

```python
# Every tool interaction produces a signal
class WorkspaceSignal:
    source: str      # "claude_code" | "claude_chat" | "cursor" | "coworker"
    timestamp: datetime
    project: str
    workstream: str  # "plan" | "build" | "test" | "ship" | "connect"
    content_type: str  # "idea" | "decision" | "code" | "test" | "insight"
    content: str
    context: Dict    # Tool-specific metadata

# Cortex absorbs all signals and synthesizes
class UniversalMemoryBus:
    def absorb(self, signal: WorkspaceSignal):
        """Ingest signal from any tool."""
        self.engines.absorber.process(signal)
        self.engines.synthesis.update_graph(signal)
        self.engines.broker.check_interventions(signal)

    def query(self, context: str, tool: str) -> ToolContext:
        """Provide relevant context for any tool."""
        return self.engines.synthesis.get_context_for(context, tool)
```

---

## Experiments: Phase 0 (This Sprint)

### Experiment 5: Workstream Spatial Mapping

**Hypothesis**: Physical (spatial) organization of terminal workstreams reduces context-switching cost by >30%.

**Method**:
1. Set up iTerm profiles with Cortex hooks
2. Measure time-to-productive-output with vs without spatial mapping
3. Track cognitive load (subjective 1-10 + error rate as proxy)

**Metrics**:
- `context_switch_time`: Seconds from switching workstream to first productive action
- `error_rate_after_switch`: Mistakes in first 5 minutes after switching
- `flow_duration`: Minutes of uninterrupted productive work

### Experiment 6: Cross-Project Insight Surfacing

**Hypothesis**: Automatically surfacing related patterns from other projects generates actionable insights >25% of the time.

**Method**:
1. During Vortex work, auto-surface relevant Pupil/Alpha/Cortex patterns
2. Track which surfaced patterns were:
   - Ignored (noise)
   - Acknowledged but not used
   - Used (changed a decision or approach)

**Metrics**:
- `insight_hit_rate`: % of surfaced patterns that were "Used"
- `insight_value`: Subjective 1-5 rating when pattern was used
- `noise_tolerance`: At what hit rate does the human start ignoring all surfaces?

### Experiment 7: Trust Acceleration

**Hypothesis**: Explicit trust level display changes AI collaboration behavior — the human delegates more and the AI self-monitors more.

**Method**:
1. Display current trust level in iTerm badge/status bar
2. AI prefixes suggestions with confidence: `[L3:92%] Suggested fix: ...`
3. Track delegation rate and outcome quality at each trust level

### Experiment 8: Exponential Ideation Session

**Hypothesis**: A structured 30-minute ideation session using augmentation protocols produces >5x the actionable ideas of an unstructured session.

**Method**:
1. Seed: A real problem from current sprint
2. Run through: Divergent → Convergent → Adversarial → Analogical (7min each)
3. Final 2min: Rank and select top 3
4. Compare to 30min freeform brainstorm on equivalent problem

**Metrics**:
- `ideas_generated`: Raw count
- `ideas_novel`: Count of ideas neither party had before
- `ideas_implemented`: Count that become real within 2 weeks
- `exponential_factor`: `ideas_implemented / time_invested` vs baseline

---

## Implementation Plan

### Sprint 1: Foundation (Feb 25 - Mar 3)

- [ ] **iTerm Profile Setup**: Create all 10 profiles with badges, colors, shell hooks
- [ ] **Cortex Shell Hooks**: Auto-inject context on profile activation
- [ ] **Window Arrangement Scripts**: Python API scripts for standard layouts
- [ ] **Keyboard Shortcuts**: Configure orchestration shortcuts
- [ ] **Trust Tracker v1**: Basic domain tracking with SQLite persistence
- [ ] **Baseline Measurement**: Run Experiments 5-8 in baseline mode

### Sprint 2: Integration (Mar 3 - Mar 10)

- [ ] **Augmentation Engine**: Build `cortex/engines/augmentation_engine.py`
- [ ] **Universal Signal Bus**: Capture signals from Claude Code, Chat, Cursor
- [ ] **Trust Display**: Show trust levels in iTerm status bar
- [ ] **Toil Tracker v1**: Categorize time spent across workstreams
- [ ] **Cross-Project Surfacing**: Auto-surface patterns during work

### Sprint 3: Acceleration (Mar 10 - Mar 17)

- [ ] **Exponential Ideation Protocol**: Formalized 30-min session structure
- [ ] **Auto-Handoff**: Session handoff between tools without manual context
- [ ] **Trust Velocity**: Implement acceleration logic (cross-domain bonus, streaks)
- [ ] **Toil Elimination v1**: Auto-context, auto-test-rerun, auto-status
- [ ] **Run All Experiments**: Full experiment suite with measurement

### Sprint 4: Compound (Mar 17 - Mar 24)

- [ ] **Synthesis Report**: What worked, what didn't, what's next
- [ ] **Integrate Winners**: Merge successful experiments into Cortex core
- [ ] **Trust Dashboard**: Visual trust map across all domains/projects
- [ ] **Exponential Collaboration v1.0**: Publish findings
- [ ] **Customer Connection**: How does this help users? (100+ or more)

---

## Connection to Cortex Architecture

This research project extends the existing V2 Prime engines:

```
Existing Cortex V2 Prime          This Research Adds
═══════════════════════           ═══════════════════
Engine A: Absorber          →→→   + Workspace signals (multi-tool)
Engine B: Synthesis         →→→   + Cross-project insight graphs
Engine C: Broker            →→→   + Trust-calibrated interventions
                                  + Augmentation engine (new)
                                  + Toil tracker (new)
                                  + Universal memory bus (new)
```

---

## Success Criteria

### Quantitative

| Metric | Baseline | Target | Timeframe |
|--------|----------|--------|-----------|
| Context switch time | ~2 min | <30 sec | Sprint 1 |
| Session handoff retention | ~40% | >85% | Sprint 2 |
| Toil ratio (toil/total time) | ~50% | <25% | Sprint 3 |
| Idea → Implementation rate | ~10% | >30% | Sprint 4 |
| Trust level advancement | ~1 level/month | 1 level/2 weeks | Sprint 3 |
| Cross-project insight hit rate | N/A | >25% | Sprint 2 |

### Qualitative

- Working together feels like **acceleration**, not coordination overhead
- Ideas compound — each session starts from higher ground than the last
- Trust is visible, calibrated, and earned through verified outcomes
- The system teaches us how to work better together
- It's fun. Genuinely fun. Not "productive" fun — actually fun.

---

## The Bigger Picture

This isn't just about optimizing a workflow. It's about discovering **what human-AI collaboration looks like when both parties are learning, adapting, and building on each other's strengths**.

The outcome isn't a tool. It's a **proof of concept for exponential collaboration** — one that could extend to:
- Teams of humans + AI agents
- Open source communities + AI contributors
- Customers + AI-powered products (the 100+ connection)

Cortex is the memory. This research is the methodology. The outcome is a new way of working.

---

## Open Research Questions

1. **Bandwidth ceiling**: Is there a point where more context actually hurts? Where's the diminishing return?
2. **Trust regression**: What happens when AI makes a serious mistake at Level 3? How fast does trust recover?
3. **Multi-human scaling**: Can this trust/augmentation model work for Jesse + Claude + another human?
4. **Creativity measurement**: How do we objectively measure whether ideas are truly novel vs recombined?
5. **Autonomy sweet spot**: What's the ideal trust level? Is full autonomy (Level 4) even desirable?
6. **Customer value chain**: How does exponential collaboration translate to value for end users?

---

*This document is a living research artifact. It evolves as we experiment, learn, and build.*
*Previous research: [HUMAN_AI_BANDWIDTH.md](./HUMAN_AI_BANDWIDTH.md) — foundational concepts still apply.*
