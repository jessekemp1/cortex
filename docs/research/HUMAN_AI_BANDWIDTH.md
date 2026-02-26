# Research Project: Human-AI Bandwidth Optimization

**Status**: Foundation — Evolved into [Exponential Collaboration](./EXPONENTIAL_COLLAB.md)
**Created**: 2026-01-15
**Owner**: Jesse + Claude (collaborative)
**Cortex Integration**: Yes - feeds into learning system
**Evolution**: This v1 research established the conceptual framework (bandwidth model, trust accumulator, creativity amplifier). The v2 research ([EXPONENTIAL_COLLAB.md](./EXPONENTIAL_COLLAB.md)) builds on these foundations with production implementation, iTerm orchestration, workstream engines, and exponential idea augmentation.

---

## Executive Summary

The bottleneck in human-AI collaboration isn't intelligence—it's **bandwidth**. This research project explores how to maximize the productive signal between human and AI collaborators, building verified trust, augmenting creativity, and reducing toil.

**Core Thesis**: We can 10x our collaborative output by optimizing the interface layer between human intuition and AI capability.

---

## Problem Statement

### Current State
- Each AI session starts cold (context loss)
- Trust is rebuilt from scratch every conversation
- Ideas scatter across tools (Claude Code, Chat, Cursor, notes)
- Manual context injection is tedious and incomplete
- No systematic measurement of collaboration quality

### Desired State
- Persistent context that compounds across sessions
- Trust earned and remembered (calibrated confidence)
- Ideas flow seamlessly between human and AI minds
- Context is automatically rich and relevant
- Measurable improvement in collaboration bandwidth

### Key Questions
1. How do we compress context without losing signal?
2. How do we build trust that persists across sessions?
3. How do we augment ideas rather than just execute tasks?
4. How do we reduce toil while increasing output quality?

---

## Conceptual Framework

### The Bandwidth Model

```
Human Mind ←→ [Interface Layer] ←→ AI Mind
              ↑
              The bottleneck is HERE
```

**Bandwidth** = (Useful Information Transferred) / (Total Interaction Cost)

Components:
- **Signal Quality**: How much of what's transferred is actually useful
- **Transfer Speed**: How quickly context can be established
- **Compression Ratio**: How much meaning per token
- **Error Rate**: Misunderstandings, corrections needed
- **Latency**: Time from thought to productive output

### The Trust Accumulator

```
Trust = f(predictions, outcomes, time)

Trust_new = Trust_prev × decay + (outcome_accuracy × recency_weight)
```

Trust should:
- Accumulate over successful interactions
- Decay slowly when not reinforced
- Be specific to domains/tasks
- Enable increasingly autonomous operation

### The Creativity Amplifier

```
Human Seed → AI Expansion → Human Curation → AI Refinement → ...
     ↑                                              │
     └──────────────── Feedback Loop ──────────────┘
```

The goal: Each cycle adds novelty and value, not just volume.

---

## Experiments

### Experiment 1: Context Compression

**Hypothesis**: Structured context formats transfer more information per token than narrative formats.

**Method**:
1. Create identical context in 3 formats:
   - Narrative (prose description)
   - Structured (JSON/YAML with schema)
   - Hybrid (structured skeleton + narrative annotations)
2. Start fresh sessions with each format
3. Measure: Time to first useful output, error rate, human satisfaction

**Metrics**:
- `time_to_productive`: Minutes until first valuable output
- `correction_rate`: Corrections per 100 interactions
- `satisfaction_score`: 1-10 human rating

**Implementation**:
```python
# cortex/intelligence/experiments/context_compression.py
class ContextCompressionExperiment:
    formats = ['narrative', 'structured', 'hybrid']

    def run_trial(self, context_payload, format_type):
        # Inject context
        # Measure outputs
        # Record metrics
```

### Experiment 2: Trust Calibration

**Hypothesis**: Tracking prediction accuracy over time enables calibrated AI confidence.

**Method**:
1. AI makes predictions with confidence levels (0.0-1.0)
2. Human records actual outcomes
3. Build calibration curve: predicted confidence vs actual accuracy
4. Use curve to adjust future confidence displays

**Metrics**:
- `calibration_error`: Mean (confidence - actual_accuracy)²
- `override_rate`: Human corrections per 100 suggestions
- `autonomy_level`: Percentage of actions taken without confirmation

**Integration with Cortex**:
```python
# Extend cortex/learning.py
def record_prediction(prediction_id, confidence, domain):
    """Record AI prediction for calibration tracking"""

def record_outcome(prediction_id, was_correct):
    """Record actual outcome"""

def get_calibrated_confidence(raw_confidence, domain):
    """Adjust confidence based on historical calibration"""
```

### Experiment 3: Handoff Protocol

**Hypothesis**: Structured session handoffs reduce context loss by >50%.

**Method**:
1. Define handoff schema (what MUST be captured)
2. Test handoff completeness across:
   - Same tool, new session
   - Different tool (Claude Code → Chat)
   - Different model (Opus → Sonnet)
3. Measure context retention

**Handoff Schema v1**:
```yaml
session_handoff:
  timestamp: ISO8601
  project: string
  workstream: enum[planning, building, testing, shipping]

  context:
    active_task: string
    blockers: list[string]
    decisions_made: list[{decision, rationale}]
    open_questions: list[string]

  artifacts:
    files_modified: list[path]
    files_created: list[path]
    tests_status: {passed, failed, skipped}

  continuity:
    next_action: string
    suggested_prompt: string
    confidence: float
```

### Experiment 4: Idea Augmentation Loop

**Hypothesis**: Structured brainstorm protocols generate more novel ideas than freeform.

**Method**:
1. Human provides seed idea
2. AI expands using specific protocols:
   - Divergent (generate alternatives)
   - Convergent (synthesize and refine)
   - Adversarial (challenge assumptions)
   - Analogical (find parallels)
3. Human curates and rates
4. Iterate

**Metrics**:
- `novelty_score`: Ideas human hadn't considered (self-report)
- `implementation_rate`: Ideas that became real features
- `iteration_depth`: Useful cycles before diminishing returns

---

## Implementation Roadmap

### Phase 1: Instrumentation (Week 1-2)
- [ ] Add session telemetry to Cortex
- [ ] Create handoff schema and capture tool
- [ ] Build prediction/outcome tracking
- [ ] Instrument iTerm profiles for workstream tracking

### Phase 2: Baseline Measurement (Week 3-4)
- [ ] Run each experiment once with current workflow
- [ ] Establish baseline metrics
- [ ] Identify lowest-hanging fruit

### Phase 3: Intervention Testing (Week 5-8)
- [ ] Test context compression formats
- [ ] Implement trust calibration
- [ ] Deploy handoff protocol
- [ ] Run idea augmentation sessions

### Phase 4: Integration (Week 9-12)
- [ ] Integrate winning approaches into Cortex
- [ ] Automate context generation
- [ ] Build trust dashboard
- [ ] Create augmentation workflows

---

## Workstream Integration with iTerm

### The 5+ Workstream Model

```
┌─────────────────────────────────────────────────────────────────┐
│  COMMAND CENTER (iTerm)                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ PLAN    │ │ BUILD   │ │ TEST    │ │ SHIP    │ │ CONNECT │   │
│  │ ─────── │ │ ─────── │ │ ─────── │ │ ─────── │ │ ─────── │   │
│  │ Opus    │ │ Sonnet  │ │ Sonnet  │ │ Sonnet  │ │ Opus    │   │
│  │ Claude  │ │ Claude  │ │ Claude  │ │ Claude  │ │ Claude  │   │
│  │ Chat    │ │ Cursor  │ │ Watch   │ │ CI/CD   │ │ Chat    │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│       │           │           │           │           │         │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                              │                                  │
│                    ┌─────────▼─────────┐                        │
│                    │      CORTEX       │                        │
│                    │   Memory Layer    │                        │
│                    │   Trust Tracker   │                        │
│                    │   Context Engine  │                        │
│                    └───────────────────┘                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Model Selection by Workstream

| Workstream | Primary Model | Rationale |
|------------|--------------|-----------|
| **PLAN** | Opus | Complex reasoning, architecture decisions |
| **BUILD** | Sonnet | Fast iteration, routine implementation |
| **TEST** | Sonnet | Quick verification, fix cycles |
| **SHIP** | Sonnet | Procedural tasks, deployments |
| **CONNECT** | Opus | Customer empathy, value articulation |

### iTerm Profile Strategy

**Per-Project Profiles**:
- `VortexV2-Build`, `VortexV2-Test`
- `AlphaArena-Build`, `AlphaArena-Test`
- `Cortex-Build`, `Cortex-Research`
- `DJ-CoPilot-Build`
- `Kempion-Build`

**Cross-Cutting Profiles**:
- `Planning-Opus` (any project, strategic work)
- `Research-Opus` (exploration, learning)
- `Ship-Mode` (deployment focus)

---

## Success Criteria

### Quantitative
- 50% reduction in `time_to_productive` for new sessions
- `calibration_error` < 0.1 (well-calibrated confidence)
- `override_rate` < 10% (trust established)
- 3x increase in `novelty_score` for brainstorms

### Qualitative
- Sessions feel like continuation, not restart
- AI suggestions match human intuition more often
- Creative work is energizing, not draining
- Trust is earned and visible

---

## Integration Points

### Cortex Learning System
- Predictions and outcomes feed into `learning.py`
- Context compression findings inform `context_intelligence.py`
- Handoff data enriches `session_manager.py`

### iTerm Automation
- Profile triggers capture workstream context
- Window arrangements saved per project phase
- Python API scripts for state persistence

### Cross-Tool Flow
- Claude Code ↔ Claude Chat handoffs
- Cursor ↔ Claude Code context sharing
- All tools → Cortex memory layer

---

## Open Questions

1. **Storage**: Where should session transcripts live? Local vs cloud?
2. **Privacy**: How much context is safe to persist?
3. **Decay**: How should old context be pruned?
4. **Multi-human**: Could this scale to team collaboration?
5. **Metrics**: What's the North Star metric for "bandwidth"?

---

## Next Actions

1. **Immediate**: Set up iTerm profiles for all workstreams
2. **This Week**: Implement handoff schema capture in Cortex
3. **This Month**: Run baseline experiments for all 4 areas
4. **This Quarter**: Integrate findings into production workflow

---

## References

- Cortex Technical Reference: `cortex/docs/TECHNICAL_REFERENCE.md`
- Session Manager: `cortex/session_manager.py`
- Learning System: `cortex/learning.py`
- Context Intelligence: `cortex/context_intelligence.py`

---

*This document is a living research artifact. Update as experiments yield insights.*
