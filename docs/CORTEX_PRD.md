# Cortex Product Requirements Document

**Version:** 1.0
**Last Updated:** 2026-02-01
**Status:** Production (95% - Validation Phase)

---

## Problem Statement

Developers managing multiple projects (10-30+) face compounding friction:

1. **Context loss** - Switching between projects erases mental context
2. **Pattern blindness** - Solutions from Project A aren't applied to Project B
3. **Priority drift** - Unclear what to work on when everything seems urgent
4. **Repeated mistakes** - Same errors occur across projects without learning
5. **Stale work** - Validated improvements sit undeployed

These problems compound: a developer with 30 projects spends more time remembering context than doing productive work.

---

## Solution

Cortex provides **portfolio-wide memory and pattern recognition** that enables better development decisions through accumulated learning.

**Core insight:** Intelligence compounds. Every pattern saved, lesson learned, and outcome tracked makes future recommendations more valuable.

---

## User Personas

### Primary: Solo Developer with Multiple Projects

**Profile:**
- Maintains 10-30 active projects
- Works across multiple languages/frameworks
- Context switches 5-10 times per day
- Has limited time for each project

**Pain Points:**
- Forgets what was working last session
- Repeats research already done in other projects
- Prioritizes based on urgency, not impact
- Validates improvements but forgets to deploy

**Goal:** Spend time on high-impact work, not remembering context

### Secondary: Team Lead Coordinating Portfolio

**Profile:**
- Oversees 5-10 related projects
- Needs visibility into project health
- Makes resource allocation decisions

**Pain Points:**
- No unified view of portfolio health
- Hard to identify which projects need attention
- Patterns solved by one team not shared

**Goal:** Portfolio-level visibility and intelligent routing

---

## Core Features

### 1. Portfolio Intelligence (P0 - Complete)

**What:** Query patterns, lessons, and context across all projects

**Value:**
- "We solved authentication the same way in 3 projects - use that pattern"
- "VortexV2 had this exact migration issue - here's what worked"

**Commands:**
```bash
python bridge.py portfolio stats
python bridge.py portfolio patterns
python bridge.py portfolio lessons
python bridge.py intelligence "query" --project NAME
```

**Metrics:**
- 10 projects indexed
- 23 patterns tracked
- 14 lessons learned
- Query time: 125ms-4s

---

### 2. Session Context (P0 - Complete)

**What:** Git-based understanding of current work state

**Value:**
- Instant resume after context switch
- "You were working on authentication in the feature/auth branch with uncommitted changes"

**Commands:**
```bash
python bridge.py session-context
```

**Metrics:**
- Derived from git in <1s
- Includes branch, commits, uncommitted work

---

### 3. Task Orchestration (P0 - Complete)

**What:** Priority-based queue with intelligent routing

**Value:**
- Critical work happens immediately
- Background work batches overnight (50% cost savings)
- Dependencies tracked, blocked tasks don't execute

**Commands:**
```bash
python orchestration/cli.py add --title "Fix bug" --priority A
python orchestration/cli.py list
python orchestration/cli.py next --mode realtime
```

**Metrics:**
- 3 priority levels (A/B/C)
- Automatic batch routing for B/C tasks
- SQLite persistence for crash recovery

---

### 4. Health Monitoring (P1 - Complete)

**What:** Track project activity and detect anomalies

**Value:**
- "VortexV2 has no commits in 7 days - stale?"
- "Alpha Arena has 26 active projects - context switching risk"

**Commands:**
```bash
python bridge.py health summary --days 7
python bridge.py health project NAME
```

**Metrics:**
- 7 anomaly types detected
- 3 anti-patterns monitored
- Dashboard at localhost:8502

---

### 5. Recommendations (P1 - Complete)

**What:** Suggest next action based on all context

**Value:**
- "Deploy validated improvement to VortexV2" (not generic "continue momentum")
- Context-aware, specific, actionable

**Commands:**
```bash
python bridge.py recommendations --project NAME
python cli.py next
```

---

## Success Metrics

### Primary (Weekly Review)

| Metric | Target | Current |
|--------|--------|---------|
| **Query response time** | <5s | 125ms-4s |
| **Portfolio coverage** | 10+ projects | 10 |
| **Pattern reuse** | 5+ patterns applied/month | Tracking |
| **Batch utilization** | >50% overnight | 0% (action needed) |

### Secondary (Monthly Review)

| Metric | Target | Current |
|--------|--------|---------|
| **Context switch time** | <30s to resume | Not measured |
| **Repeated mistakes** | 0/month | Not measured |
| **Validated-undeployed code** | 0 | 0 (good) |
| **Active projects** | <10 | 26 (action needed) |

### Validation Period Metrics (Jan 31 - Feb 7)

| Metric | Target | Status |
|--------|--------|--------|
| **Dashboard uptime** | 99% | Running |
| **Anomaly detection** | Functional | Verified |
| **No critical bugs** | 0 | Tracking |

---

## Non-Goals

Cortex deliberately does NOT:

1. **Execute code** - It recommends, you decide and execute
2. **Replace version control** - Uses git, doesn't replace it
3. **Auto-deploy** - Flags validated work, human deploys
4. **Real-time collaboration** - Single-developer focus
5. **Project management** - Not Jira, just intelligent routing
6. **Full IDE integration** - CLI-first, not a plugin
7. **AI code generation** - Context and recommendations, not code

---

## Design Principles

### 1. Depth Over Speed

Cortex optimizes for **intelligence quality**, not response time.

- Accept 2-5s startup for comprehensive analysis
- Use best models (Opus) not fastest (Haiku)
- Fresh analysis beats stale cache

### 2. Evidence-Based

Only track what's measured, only recommend what's validated.

- Patterns from actual git history
- Lessons from real failures
- Health from real commits

### 3. Graceful Degradation

Every feature has a fallback.

- No chromadb? Keyword search
- No psutil? Skip process monitor
- No network? Use cached data

### 4. User-First Output

Every output enables action.

- Commands, not explanations
- Specific files, not vague areas
- Priority, not everything at once

---

## Constraints

### Technical

- Python 3.11+
- Git required for session context
- SQLite for persistence (no external DB)
- Anthropic API for AI features

### Operational

- Max 500 lines per doc (force prioritization)
- Sub-5s response for all commands
- Graceful degradation for optional features

### Resource

- Single developer maintenance
- No dedicated infrastructure team
- Cost-conscious batch routing

---

## Roadmap

### Now (Validation Phase - Ends Feb 7)

- [x] Dashboard deployed
- [ ] Reduce active projects: 26 -> 10
- [ ] Queue overnight batch jobs
- [ ] Daily anomaly monitoring
- [ ] Validation report Feb 7

### Next (Post-Validation)

- [ ] MCP Server integration
- [ ] Real embeddings (replace hash-based)
- [ ] Claude Agent SDK integration

### Future

- [ ] Multi-developer support
- [ ] Team patterns sharing
- [ ] Integration with external tools

---

## Risks

### Technical

| Risk | Mitigation |
|------|------------|
| Chromadb unavailable | Fallback to keyword search |
| API rate limits | Batch routing, caching |
| Large git histories | Limit to 90 days |

### Operational

| Risk | Mitigation |
|------|------------|
| Context switching overhead | Reduce to 10 active projects |
| Stale recommendations | Fresh analysis, no long-term cache |
| Over-engineering | Max 500 lines per doc |

---

## Appendix: 5-Why Analysis

**Why 1:** Why does Cortex provide recommendations?
> Because developers need to know what to work on next

**Why 2:** Why don't developers already know?
> Because managing 30 projects creates cognitive overload

**Why 3:** Why is there cognitive overload?
> Because context from each project is lost on switch

**Why 4:** Why is context lost?
> Because there's no persistent memory across projects

**Why 5:** Why isn't there persistent memory?
> **Core Problem:** Development tools are project-scoped, not portfolio-scoped

**Solution:** Cortex provides portfolio-scoped memory that persists across context switches.
