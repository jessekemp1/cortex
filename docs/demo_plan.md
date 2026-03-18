# Cortex Demo Plan — Senior Developer Audience

## Demo Philosophy

Lead with what's real. Show data, not slides. Let the system speak.
A senior dev will spot fake metrics in 30 seconds. The paper has been
cleaned — the demo should match the paper's new honesty.

## Pre-Demo Checklist

```
□ Bridge API running (:8765)          launchctl list | grep cortex.bridge
□ Cortex tests pass                   cd Dev && pytest cortex/tests/ -x -q
□ MCP server responsive               curl -s localhost:8765/health
□ Web chat accessible                 open http://127.0.0.1:8765/chat
□ portfolio_status.py works           python3 scripts/portfolio_status.py
□ Fresh terminal, no stale state
```

## Demo Script (25 minutes)

### 1. The Problem (2 min)
**What to say**: "Every Claude Code session starts from zero. I work on 6 projects.
Cortex remembers what worked, what failed, and what matters — across all of them."

**Show**: `python3 scripts/portfolio_status.py`
- Real 6-project dashboard, real test counts, real commit data
- "This is live data, not a screenshot."

### 2. Memory Architecture (5 min)
**What to say**: "Three tiers: short-term (in-memory, 50 items), working (SQLite, 7-day),
long-term (permanent, indexed). Items promote based on access patterns and outcome data."

**Show**:
```bash
# Show the bridge has real data
curl -s localhost:8765/service-health | python3 -m json.tool

# Show memory tiers in action
python -c "
from cortex.bridge import CortexBridge
b = CortexBridge()
ctx = b.get_context('GRIB coordinate conventions', limit=5, project='vortex')
for item in ctx[:3]:
    print(f'{item.get(\"source\", \"?\")}: {str(item.get(\"content\", \"\"))[:100]}')
"
```
**Key point**: "This retrieved 3 relevant patterns from 841 indexed items. The retrieval
benchmark shows 80% recall@10 and 0.643 MRR — honest numbers, room to improve."

### 3. Anti-Pattern Database (3 min)
**What to say**: "The most practically useful feature. Cortex stores behavioral
anti-patterns — not syntax errors, but patterns that caused real failures."

**Show**: Read from CLAUDE.md the mock patch namespace gotcha:
```
Mock patch namespace: from X import Y at module level binds Y in the importing
module. Must patch importing_module.Y, not X.Y. This cost 2 sessions before
we codified it.
```
**Key point**: "12 anti-patterns, each with: pattern, symptom, fix, detection method.
This is the highest-ROI feature — preventing known failures before they happen."

### 4. AST Meta-Testing (3 min) — THE NOVEL CONTRIBUTION
**What to say**: "Tests that test the tests. We scan the entire suite with Python's
ast module to enforce assertion quality."

**Show**:
```bash
cd Dev && pytest cortex/tests/test_assertion_quality.py -v
```
**Key point**: "1.8% trivial assertion rate, enforced automatically. Three checks:
no trivial-only files, integration tests have behavioral calls, no empty bodies.
I haven't seen anyone else do this. It catches the most common test inflation pattern."

### 5. Orchestration Pipeline (4 min)
**What to say**: "Intake discovers work from GOALS.md and taskboard. Router picks
model tier by complexity. Dispatcher executes. Collector logs outcomes for learning."

**Show**:
```bash
# Show the real supervisor state
curl -s localhost:8765/intelligence/recommendations | python3 -m json.tool
```
**Be honest**: "The router has dispatched 13 unique work items. That's enough to
validate the pipeline, not enough for learned threshold adjustment. The infrastructure
is real, the learning data is still accumulating."

### 6. CRA — Continuous Research Agent (3 min)
**What to say**: "Scans frontier sources, scores discoveries against 7 capability
vectors, generates adoption proposals."

**Show**:
```bash
ls -la ~/.cortex/research/cra/
wc -l ~/.cortex/research/cra/discoveries.jsonl
wc -l ~/.cortex/research/cra/assessments.jsonl
# Show a real assessment
tail -1 ~/.cortex/research/cra/assessments.jsonl | python3 -m json.tool
```
**Key point**: "39 discoveries, 31 assessments. Each scored on disruption risk,
adoption effort, expected impact against MY specific capability vectors. Not 'here's
a trending repo' — 'here's how this threatens or enhances YOUR architecture.'"

### 7. Web Chat Gateway (2 min)
**What to say**: "Built in one session. Telegram bot + web UI, both backed by the
same Bridge API. The web chat uses WebSocket + JetBrains Mono for perfect ASCII rendering."

**Show**: Open http://127.0.0.1:8765/chat, type `/briefing`
- Real data flows through
- Show the quick-command buttons

### 8. Honest Limitations (3 min) — CRITICAL
**What to say**: "Here's what doesn't work yet."

**List**:
- Implicit feedback: 39 entries in 14 weeks. Not at learning scale.
- Model routing: 13 dispatched items. Static heuristics, not learned.
- Outcome data: ~60 human outcomes out of 657 total. Rest is test fixtures and automated pipelines.
- The context benchmark (21.2% dedup) was synthetic. We caught this, rewrote the paper, and now lead with the retrieval benchmark instead.
- Cross-project pattern transfer: works in theory, limited evidence.

**Key point**: "The architecture is sound. The data needs to accumulate. We're honest
about where we are."

## Demo Anti-Patterns (DO NOT)

- Don't show the context benchmark (synthetic, caveated in paper)
- Don't claim "learns from outcomes" without qualifying sample size
- Don't run tests that take >30 seconds (pick fast subsets)
- Don't show the ICLR pitch (separate from the paper)
- Don't apologize for small numbers — frame as "early data, real infrastructure"

## What Will Impress a Senior Dev

1. **The test suite is real** — 1,291 tests in Cortex, 7,500+ across portfolio
2. **AST meta-testing is novel** — they've never seen this
3. **The anti-pattern database is practical** — they've felt this pain
4. **The CRA pipeline is ambitious** — 63K discoveries scored against personal vectors
5. **The honesty** — showing limitations builds more trust than hiding them

## Fallback Plans

| If this breaks... | Do this instead |
|---|---|
| Bridge API down | Show code: `cat cortex/bridge.py \| head -50` |
| Web chat won't load | Use curl: `curl localhost:8765/intelligence/recommendations` |
| Tests fail | Show structure: `find cortex/tests -name "*.py" \| wc -l` |
| Portfolio status fails | Show git log: `git log --oneline -10` |

## Post-Demo Questions to Prepare For

1. **"How is this different from Mem0?"** → Same tier as storage; different tier as intelligence. Mem0 stores memories. Cortex learns what works from outcomes. Retrieval is outcome-weighted.
2. **"Why not just use a longer context window?"** → 1M tokens helps single sessions. Doesn't help across sessions, doesn't learn, doesn't route by complexity, doesn't detect anti-patterns.
3. **"What's the adoption path?"** → `pip install cortex-intelligence`, configure `~/.cortex/config.yaml`, MCP server integrates with Claude Code in one line.
4. **"Would you submit this to a venue?"** → AST meta-testing and anti-pattern database are publishable. Full system is a strong workshop paper with honest scale disclosure.
