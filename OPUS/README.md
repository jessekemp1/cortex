# Converx OPUS - Strategic Intelligence Platform

**The Operating System for Human-AI Symbiosis**

Converx is a personal cognitive OS that bridges human intuition with AI precision, transforming all your signals (code, docs, markets, health, habits, goals) into clear strategies, forecasts, and next best actions.

---

## Quick Start

```bash
# From the OPUS directory
cd /Users/jesse.kemp/Dev/converx/OPUS

# Get next action
python -m cli next

# Get next action for specific project
python -m cli next vortexv2

# Get current status
python -m cli status

# With context from knowledge base
python -m cli next --with-context

# JSON output for programmatic use
python -m cli next --json
```

---

## What Converx Does

### The Problem
You make decisions based on incomplete information, optimistic estimates, and yesterday's priorities.

### The Solution
Converx synthesizes your goals, current state, and environmental changes into clear strategic recommendations.

### The Transformation
```
BEFORE                          AFTER
------                          -----
Wake up -> Check inputs         Wake up -> Check strategic position
React to urgent                 Act on important
Feel busy                       Feel directed
End day exhausted               End day accomplished
Wonder if it mattered           Know exactly what moved
```

---

## Core Concepts

### Status Map
Your life as interconnected domains (Work, Health, Finance, Learning), each with:
- **State**: Key variables (workload, energy, runway)
- **Status**: Qualitative summary (Calm, Pressure, Storm)
- **Horizons**: Nowcast (24-72h), Short-term (weeks), Long-term (quarters)

### Routes & Waypoints
Not task lists - strategic routes:
- **Goal**: Desired state across domains
- **Route**: Ordered waypoints toward the goal
- **Waypoint**: Entry/exit conditions, dependencies

### Forecast Range
Every route evaluated in three trajectories:
- **Optimistic**: Best reasonable case
- **Likely**: Central trajectory
- **Conservative**: Safe, slower path

### Virtual Twin
A model of how your system evolves - simulate outcomes before committing.

---

## File Structure

```
OPUS/
  cli.py                # CLI entry point
  orchestrator.py       # Core orchestration
  formatter.py          # Output formatting
  __init__.py           # Package init
  converx               # Entry script
  OPUS_DESIGN.md        # Unified design document
  README.md             # This file

  docs/                 # Documentation
    DESIGN_SPEC.md      # Technical specification
    USE_CASES.md        # Persona-based use cases
    SUCCESS_METRICS.md  # Metrics framework
    FUTURE_ARCHAEOLOGY.md  # 10-year evolution
    MARKETING_MANIFESTO.md # Why it matters
    STRATEGIC_RAMP_UP_PLAN.md # Implementation guide
    FUTURE_VISION.md    # Long-term vision

  tests/                # Test suite
    test_orchestrator.py
    test_formatter.py
    test_e2e_situational.py

  strategy/             # Phase 1-2 (planned)
  knowledge/            # Phase 3 (planned)
  twin/                 # Phase 5 (planned)
  playbooks/            # Phase 4 (planned)
  memory/               # Phase 1+ (planned)
```

---

## Current Status

### Phase 0 - COMPLETE
- [x] `converx next` - Prioritized next action
- [x] `converx status` - Current state summary
- [x] Project filtering
- [x] Context integration
- [x] JSON output
- [x] 10 tests passing

### Roadmap
| Phase | Focus | Effort |
|-------|-------|--------|
| **1** | Status Map + Forecast Range | 2-3h / ~50K tokens |
| **2** | Routes & Multi-Domain | 4-6h / ~100K tokens |
| **3** | Integrations | 6-8h / ~150K tokens |
| **4** | Playbooks & Executor | 4-6h / ~100K tokens |
| **5** | Virtual Twin + Learning | 8-12h / ~200K tokens |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [OPUS_DESIGN.md](OPUS_DESIGN.md) | Full architecture |
| [docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md) | Technical spec + tests |
| [docs/USE_CASES.md](docs/USE_CASES.md) | Persona examples |
| [docs/SUCCESS_METRICS.md](docs/SUCCESS_METRICS.md) | Metrics framework |
| [docs/FUTURE_ARCHAEOLOGY.md](docs/FUTURE_ARCHAEOLOGY.md) | 10-year evolution |

---

## The Five Dimensions of Winning

1. **Clarity**: Know exactly what matters and why
2. **Velocity**: Maximum sustainable speed
3. **Sustainability**: Win without breaking
4. **Learning**: Get wiser, not just busier
5. **Freedom**: More options, more runway, more capability

---

## Success Metrics

### Weekly
- 30+ min/day saved on decisions
- 70%+ recommendations actionable
- 80%+ effort estimate accuracy

### Monthly
- 25%+ decision quality improvement
- 80%+ forecast accuracy
- Balanced domains (all >0.6)

### Yearly
- 50%+ capability growth
- 25%+ freedom increase
- Zero burnout, sustainable pace

---

## Multi-Model Collaboration

This implementation synthesizes contributions from:
- **Claude**: Technical architecture, test cases, success engine
- **Grok**: Military-strategic terminology, truth-seeking, future archaeology
- **Cross-model**: Use cases, metrics, marketing vision

---

## The Invitation

Use Converx for one week. Just `python -m cli next` each morning.

At the end, you'll know:
- What you actually accomplished
- How accurate your intuitions are
- What patterns are helping or hurting

**The system doesn't demand. It offers. The choice is yours.**

---

*"The system that helps you see clearly is more valuable than the system that helps you do more."*
