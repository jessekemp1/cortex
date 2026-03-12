# Cortex Strategic Roadmap

**Created:** 2026-03-12
**Author:** Jesse Kemp + Claude
**Horizon:** 6 months (Mar — Sep 2026)
**Review:** Bi-weekly

---

## Part 1: Paths Forward (Goal-Aligned Assessment)

### Current Position (Honest)

```
┌─────────────────────────────────────────────────────────────────┐
│ CORTEX COMPETITIVE POSITION — MARCH 2026                        │
├────────────────┬──────────┬──────────┬──────────┬──────────────┤
│                │ Cortex   │ Mem0     │ Letta    │ claude-mem   │
│                │          │ (49.5K★) │ (21.5K★) │ (34.2K★)    │
├────────────────┼──────────┼──────────┼──────────┼──────────────┤
│ Memory Store   │ File+SQL │ Graph+Vec│ Virtual  │ File-based   │
│ Retrieval      │ BM25+Emb │ Vec+Graph│ OS-style │ Keyword      │
│ Outcome Learn  │ ★ NEW    │ None     │ None     │ None         │
│ Task Routing   │ ★ UNIQUE │ None     │ None     │ None         │
│ Goal Parsing   │ ★ UNIQUE │ None     │ None     │ None         │
│ Anti-Patterns  │ ★ UNIQUE │ None     │ None     │ None         │
│ MCP Native     │ Yes      │ No       │ No       │ Yes          │
│ Multi-tenant   │ No       │ Yes      │ Yes      │ No           │
│ Community      │ ~0       │ 49,500   │ 21,500   │ 34,200       │
│ Production Use │ 18mo/1dev│ Many orgs│ Many orgs│ Many devs    │
│ Benchmarks     │ Internal │ LongMem  │ Academic │ None         │
└────────────────┴──────────┴──────────┴──────────┴──────────────┘
```

**Cortex's real moat (3 things nobody else has):**
1. **Task orchestration + memory in one system** — Mem0 is memory-only, LangGraph is orchestration-only
2. **Anti-pattern primitives** — failure mode + trigger + prevention + project context = memory type that doesn't exist in any competitor or paper
3. **Goal-to-task pipeline** — parses GOALS.md into prioritized work, routes to optimal model tier, learns from outcomes

**Cortex's real weaknesses (unflinching):**
1. **Zero community** — all competitors have 15K-50K stars. Cortex has 0 users besides Jesse
2. **Single-developer validation** — 18 months of one person's data. Not generalizable
3. **Learning loop was broken for 4 days** — only 2 implicit outcomes had been derived before fix
4. **No external benchmarks** — internal metrics (21.2% dedup, 0.94 PQS) mean nothing without comparison baselines
5. **Retrieval is mediocre** — BM25+embedding is table stakes. Mem0 and Supermemory have graph memory, temporal reasoning, contradiction handling

### Path Assessment Against Goals

| Path | Goal Alignment | Market Fit | Effort | Verdict |
|------|---------------|------------|--------|---------|
| **A: OSS launch as-is** | P1 (Goal 5) | Niche but honest | 2 days | DO — ship what works |
| **B: Compete on retrieval** | Low | Red ocean vs Mem0/Supermemory | 3+ months | SKIP — can't win here |
| **C: Double down on orchestration** | P1 (Goal 5+9) | Unique position | 1 month | DO — this is the moat |
| **D: Integrate Mem0 for storage** | Medium | Leverage their infra | 2 weeks | CONSIDER — replace our weak layer with their strong one |
| **E: Auto-research agent** | P1 (Goal 9) | Novel, high-value | 3 weeks | DO — compounds everything |
| **F: Multi-tenant SaaS** | Low | Premature | 2+ months | SKIP — no users yet |

**Recommended sequence:** A → C → E → D (ship → strengthen moat → build compounding → upgrade infrastructure)

---

## Part 2: Self-Adapting System Design

### The Core Problem

Cortex currently learns from *user interactions* (implicit feedback, model outcomes). It does NOT learn from *the field* — new papers, new tools, new capabilities, competitor features. This is a manual process (Jesse reads papers, implements ideas).

**Target state:** Cortex should have an autonomous research loop that:
1. Discovers relevant advances (papers, repos, tools, MCP servers)
2. Assesses applicability to Cortex's architecture
3. Proposes integration plans (with effort/impact estimates)
4. Tracks which innovations were adopted and their outcomes

### Architecture: Cortex Research Agent (CRA)

```
┌─────────────────────────────────────────────────────────────┐
│                  CORTEX RESEARCH AGENT (CRA)                │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│  │ Discovery│──→│ Analysis │──→│ Proposal │               │
│  │ Agent    │   │ Agent    │   │ Agent    │               │
│  └──────────┘   └──────────┘   └──────────┘               │
│       │              │              │                       │
│  Scans:         Evaluates:     Produces:                    │
│  - arxiv RSS    - Relevance    - Integration spec           │
│  - GitHub       - Effort       - Risk assessment            │
│  - HN/Reddit    - Impact       - Priority vs backlog        │
│  - MCP registry - Disruption   - Code sketch                │
│                   risk                                      │
│                                                             │
│  ┌──────────────────────────────────────────┐               │
│  │          Knowledge Base                   │               │
│  │  ~/.cortex/research/                      │               │
│  │  ├── discoveries.jsonl  (raw findings)    │               │
│  │  ├── assessments.jsonl  (scored items)    │               │
│  │  ├── proposals/         (integration plans│)              │
│  │  ├── adopted.jsonl      (what we shipped) │               │
│  │  └── dismissed.jsonl    (what we skipped) │               │
│  └──────────────────────────────────────────┘               │
│                                                             │
│  Feedback loop:                                             │
│  adopted.jsonl outcome data → refine discovery priorities   │
└─────────────────────────────────────────────────────────────┘
```

### Discovery Agent

**Sources (ranked by signal-to-noise):**

| Source | Method | Frequency | Signal Quality |
|--------|--------|-----------|---------------|
| arxiv cs.AI, cs.CL, cs.SE | RSS + semantic filter | Daily | High (but noisy) |
| GitHub Trending (agent, memory, MCP) | API scrape | Weekly | Medium |
| Anthropic changelog/blog | Web fetch | Weekly | Very high |
| Papers With Code (agent-memory) | API | Weekly | High |
| HN front page (filtered) | API | Daily | Low (but early signal) |
| MCP server registry | API | Weekly | High for integrations |

**Semantic filter:** Each discovery is scored against Cortex's capability map:

```python
CAPABILITY_VECTORS = {
    "memory_retrieval": "BM25 embedding hybrid search pattern matching",
    "outcome_learning": "implicit feedback outcome routing model selection",
    "task_orchestration": "work discovery routing dispatch model tier",
    "anti_patterns": "failure prevention pattern memory recurring bugs",
    "context_optimization": "token budget lost-in-middle attention reordering",
    "goal_tracking": "GOALS.md parsing work items priority scheduling",
}

def score_relevance(discovery_text: str) -> Dict[str, float]:
    """Score discovery against each capability vector."""
    # Embedding cosine similarity against each vector
    # Returns {"memory_retrieval": 0.72, "outcome_learning": 0.85, ...}
```

### Analysis Agent

For each high-relevance discovery (score > 0.6 on any capability):

```python
@dataclass
class ResearchAssessment:
    discovery_id: str
    title: str
    source: str  # paper URL, repo URL

    # Impact assessment
    relevance_scores: Dict[str, float]  # per-capability
    disruption_risk: float  # 0-1: how much does this threaten our approach?
    adoption_effort: str  # "trivial" | "small" | "medium" | "large" | "rewrite"
    expected_impact: str  # "incremental" | "significant" | "transformative"

    # Integration sketch
    affected_modules: List[str]  # e.g. ["intelligence/memory/hybrid_retriever.py"]
    integration_approach: str  # 1-paragraph plan
    risks: List[str]

    # Decision
    recommendation: str  # "adopt" | "monitor" | "dismiss"
    reasoning: str
```

**Key heuristics:**
- If `disruption_risk > 0.7` AND `adoption_effort <= "medium"` → **ADOPT urgently**
- If `disruption_risk > 0.7` AND `adoption_effort > "medium"` → **MONITOR + plan**
- If `expected_impact == "transformative"` → **Always assess**, regardless of effort
- If provider-native (Anthropic ships memory API) → **ADAPT immediately**

### Proposal Agent

Generates integration plans in Golden Spec format:

```markdown
## Research Integration: [Title]

**Source:** [paper/repo URL]
**Assessed:** [date]
**Recommendation:** ADOPT / MONITOR / DISMISS

### What It Is
[2-3 sentences]

### Why It Matters for Cortex
[Specific capability it improves/threatens]

### Integration Plan
1. [Step with affected file]
2. [Step with affected file]

### Risk Assessment
- [Risk 1]
- [Risk 2]

### Success Criteria
- [Measurable outcome]

### Effort: [S/M/L]
```

### Execution: How CRA Runs

**Option A: Batch API (Recommended — 50% cost savings)**
```
cortex research scan          # Discovery agent (haiku tier, daily)
cortex research assess        # Analysis agent (sonnet tier, weekly)
cortex research propose       # Proposal agent (opus tier, on-demand)
cortex research digest        # Human-readable weekly summary
```

CRA jobs go into the existing batch queue (`~/.cortex/batch/`), benefiting from the overnight dispatch window (2-6 AM UTC).

**Option B: Claude Code Cowork Integration**
If Anthropic's cowork feature supports data passing between sessions:
- CRA runs as a cowork participant
- Shares discoveries via MCP resources (`cortex://research/latest`)
- Main development session can query `cortex_research_status` tool
- Proposals surface in daily briefing

**Option C: Standalone daemon**
```python
# cortex/engines/research_agent.py
class CortexResearchAgent:
    def __init__(self):
        self.discovery = DiscoveryEngine(sources=SOURCES)
        self.analyzer = AnalysisEngine(capability_map=CAPABILITY_VECTORS)
        self.proposer = ProposalEngine()

    async def daily_scan(self):
        discoveries = await self.discovery.scan()
        for d in discoveries:
            if d.relevance > 0.6:
                assessment = await self.analyzer.assess(d)
                if assessment.recommendation == "adopt":
                    proposal = await self.proposer.generate(assessment)
                    self.notify(proposal)

    async def weekly_digest(self) -> str:
        """Generate human-readable research digest."""
        assessments = self.load_recent_assessments(days=7)
        return format_digest(assessments)
```

### Adaptation Mechanism: The "Evolve" Loop

Beyond just discovering papers, Cortex needs to evolve its own capabilities:

```
┌─────────────────────────────────────────────────────┐
│                 THE EVOLVE LOOP                      │
│                                                      │
│  1. DISCOVER  ───→  New capability identified        │
│       ↓                                              │
│  2. ASSESS    ───→  Scored against current arch      │
│       ↓                                              │
│  3. PROTOTYPE ───→  Minimal integration (branch)     │
│       ↓                                              │
│  4. VALIDATE  ───→  A/B test vs current behavior     │
│       ↓                                              │
│  5. SHIP      ───→  If validates > current, deploy   │
│       ↓                                              │
│  6. LEARN     ───→  Track adoption outcome           │
│       └─────────────────────→ feeds back to (1)      │
└─────────────────────────────────────────────────────┘
```

**Critical insight from the research:** The paper "Adaptive Memory Admission Control" (arXiv 2603.04549) shows that deciding **what NOT to adopt** is as important as what to adopt. CRA needs a `dismissed.jsonl` with reasoning, so it doesn't re-evaluate the same things.

---

## Part 3: Competitive Strategy + Research Integration

### Where to Compete (and Where Not To)

```
┌─────────────────────────────────────────────────────────────────┐
│              COMPETITIVE STRATEGY MAP                            │
│                                                                  │
│  DON'T COMPETE                    COMPETE HERE                   │
│  (commodity layer)                (intelligence layer)           │
│                                                                  │
│  ┌──────────────┐                ┌──────────────────────────┐   │
│  │ Vector store │                │ Outcome-aware retrieval  │   │
│  │ Basic RAG    │                │ Anti-pattern primitives  │   │
│  │ Session state│                │ Task orchestration+memory│   │
│  │ MCP transport│                │ Goal-to-task pipeline    │   │
│  │ Embedding gen│                │ Model tier routing       │   │
│  └──────────────┘                │ Implicit feedback loop   │   │
│     ↓                            │ Auto-research evolution  │   │
│  USE: Mem0, LangGraph,           └──────────────────────────┘   │
│  native provider memory             ↓                           │
│                                   BUILD: This is the moat       │
└─────────────────────────────────────────────────────────────────┘
```

### 6-Month Roadmap (Phased)

#### Phase 1: Ship + Validate (Mar 12 — Mar 28) — CURRENT

| Item | Priority | Status | Dependency |
|------|----------|--------|------------|
| OSS launch (subtree, DOI, HN) | P0 | 80% done | None |
| Learning pipeline verified (outcomes flowing) | P0 | Just fixed | None |
| **Conversation history ingestion** | P0 | ✅ SHIPPED | None |
| External benchmark (AMA-Bench or LongMemEval) | P1 | Not started | OSS launch |
| First 3 beta users with feedback | P1 | Not started | OSS launch |
| **Batch API deep conversation analysis** | P2 | Not started | Conversation ingestion validated |

**Success criteria:** 5+ GitHub stars from non-Jesse users. 1 external person runs `cortex status` successfully.

#### Phase 2: Strengthen the Moat (Apr 1 — Apr 30)

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| **Trajectory-informed memory** | P1 | 2 weeks | High — learn from HOW tasks were solved, not just outcomes |
| **Graph memory for anti-patterns** | P2 | 1 week | Medium — causal links between anti-patterns, projects, failures |
| **Memory admission control** | P2 | 1 week | Medium — decide what NOT to remember (paper 2603.04549) |
| **CLI decomposition** | P2 | 1 week | Medium — cli.py is 5K lines, blocks contributions |

**Key research to integrate:**
- "Trajectory-Informed Memory Generation" (arXiv 2603.10600) — +14.3pp on AppWorld
- "Adaptive Memory Admission Control" (arXiv 2603.04549) — 5-factor admission scoring
- "AutoSkill" (arXiv 2603.01145) — extract reusable skills from interaction traces

**Trajectory memory design sketch:**
```python
# New module: intelligence/memory/trajectory_memory.py
@dataclass
class TrajectoryPattern:
    """Learned from a successful task execution."""
    task_type: str           # "debug", "implement", "refactor"
    decision_points: List[DecisionPoint]  # where the agent chose
    outcome: str             # success/partial/failed
    key_actions: List[str]   # what actually worked
    anti_actions: List[str]  # what was tried and failed

    # Attribution
    source_session: str
    confidence: float
    reuse_count: int = 0

class TrajectoryMemory:
    """Learn from HOW tasks were solved, not just WHAT was discussed."""

    def extract_from_session(self, session_log: List[dict]) -> List[TrajectoryPattern]:
        """Analyze a completed session → extract reusable patterns."""
        # 1. Identify decision points (tool choices, file selections)
        # 2. Attribute outcomes to specific decisions
        # 3. Extract generalizable patterns
        pass

    def suggest_approach(self, task: WorkItem) -> Optional[TrajectoryPattern]:
        """Given a new task, suggest approach based on similar past trajectories."""
        # Semantic search over trajectory patterns
        # Rank by outcome quality + similarity
        pass
```

#### Phase 3: Auto-Research Agent (May 1 — May 21)

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| **Discovery engine** (arxiv, GitHub, MCP registry) | P1 | 1 week | Foundation for everything |
| **Analysis engine** (relevance scoring, disruption detection) | P1 | 1 week | Filter signal from noise |
| **Proposal engine** (integration specs) | P2 | 3 days | Actionable output |
| **Weekly research digest** (in `cortex briefing`) | P1 | 2 days | User-facing value |
| **Batch API integration** (overnight research scans) | P2 | 2 days | Cost-efficient |

**Cowork integration assessment:**

Anthropic's cowork feature (if available) would enable:
```
┌──────────────────┐     ┌──────────────────┐
│ Main Dev Session │     │ Research Agent    │
│ (Claude Code)    │────→│ (Cowork session) │
│                  │     │                  │
│ "What's new in   │     │ Scans arxiv,     │
│  agent memory?"  │     │ GitHub, MCP      │
│                  │←────│                  │
│ Gets structured  │     │ Returns scored   │
│ research digest  │     │ discoveries      │
└──────────────────┘     └──────────────────┘
```

**Without cowork (fallback):** CRA writes to `~/.cortex/research/` and results surface through existing MCP tools:
```
cortex_intelligence("what research is relevant to my current task?")
  → includes recent CRA discoveries in context
```

**Data bridge pattern (works with or without cowork):**
```python
# cortex/engines/research_agent.py
RESEARCH_DIR = Path.home() / ".cortex" / "research"

class CRABridge:
    """Bridge between CRA output and Cortex intelligence layer."""

    def get_relevant_discoveries(self, task_context: str) -> List[Discovery]:
        """Query CRA knowledge base for task-relevant research."""
        discoveries = self._load_recent(days=30)
        return self._rank_by_relevance(discoveries, task_context)

    def surface_in_briefing(self) -> str:
        """Add research section to daily briefing."""
        week = self._load_recent(days=7)
        adopt = [d for d in week if d.recommendation == "adopt"]
        monitor = [d for d in week if d.recommendation == "monitor"]
        return self._format_briefing_section(adopt, monitor)
```

#### Phase 4: Infrastructure Upgrade (Jun 1 — Jun 30)

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| **Mem0 integration** (replace file-based with graph memory) | P2 | 2 weeks | Leverage 49K-star infra |
| **AMA-Bench evaluation** (arXiv 2602.22769) | P1 | 1 week | External credibility |
| **Provider memory detection** (if Anthropic ships native) | P1 | 1 week | Existential adaptation |
| **Multi-user support** (team memory sharing) | P3 | 2 weeks | Growth path |

**Mem0 integration design:**
```python
# Don't replace everything — layer Mem0 under Cortex's intelligence
# Mem0 handles: storage, embedding, graph relationships
# Cortex handles: outcome learning, task routing, anti-patterns, goals

from mem0 import Memory

class CortexMemoryBackend:
    """Pluggable backend: file-based (default) or Mem0."""

    def __init__(self, backend="file"):
        if backend == "mem0":
            self.store = Memory()  # Mem0's graph + vector store
        else:
            self.store = FileMemoryStore()  # Current implementation

    # Cortex-specific operations layer on top
    def store_anti_pattern(self, pattern: AntiPattern):
        """Anti-pattern is a Cortex concept — stored via any backend."""
        self.store.add(
            messages=[{"role": "system", "content": pattern.serialize()}],
            metadata={"type": "anti_pattern", "project": pattern.project},
            user_id=self.user_id,
        )
```

#### Phase 5: Compounding (Jul — Sep 2026)

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| **Causal retrieval** (retrieve by cause, not similarity) | P2 | 3 weeks | Next-gen retrieval |
| **Learned forgetting** (graceful memory degradation) | P3 | 2 weeks | Long-term health |
| **Cross-repo transfer** (memory sharing across repos) | P2 | 2 weeks | Portfolio value |
| **CRA self-improvement** (research agent learns what to scan) | P3 | 1 week | Meta-learning |

---

### Research Papers to Track (Priority Queue)

| Paper | ArXiv | Why It Matters | When to Integrate |
|-------|-------|---------------|-------------------|
| Trajectory-Informed Memory | 2603.10600 | +14.3pp improvement. Directly maps to Cortex's interaction capture | Phase 2 (April) |
| Adaptive Memory Admission | 2603.04549 | 5-factor admission scoring. Cortex stores everything — needs curation | Phase 2 (April) |
| AutoSkill | 2603.01145 | Skills from traces = anti-patterns generalized | Phase 2 (April) |
| AMA-Bench | 2602.22769 | First real benchmark for agent memory | Phase 4 (June) |
| RetroAgent | 2603.08561 | Dual intrinsic feedback without external reward | Phase 3 (May) |
| Memory Survey (5 mechanisms) | 2603.07670 | Taxonomy to validate our architecture decisions | Read immediately |
| TA-Mem | 2603.09297 | Agent autonomously explores memory via tools | Phase 5 (Jul+) |

---

### Disruption Scenarios (What Could Kill Cortex)

| Scenario | Probability | Impact | Cortex Response |
|----------|------------|--------|-----------------|
| **Anthropic ships native memory API** | 60% by Sep 2026 | HIGH — commoditizes basic memory | Pivot to orchestration layer ON TOP of native memory. Anti-patterns + routing remain unique |
| **Mem0 adds task orchestration** | 20% | HIGH — direct competitor | Ship faster. 49K stars + orchestration = game over for us |
| **Context windows reach 10M tokens** | 40% by Dec 2026 | MEDIUM — reduces need for memory | Memory still needed for curation, not just storage. 10M tokens of noise < 1K tokens of curated context |
| **Claude Code gets built-in learning** | 30% by Sep 2026 | VERY HIGH — our exact use case | Pivot to cross-tool layer (not Claude-specific) |

**Hedging strategy:** Every Cortex feature should work with ANY LLM agent, not just Claude Code. MCP is the right abstraction layer. If any provider ships native memory, Cortex becomes the intelligence layer on top.

---

### Metrics That Matter (Not Vanity)

```
┌─────────────────────────────────────────────────────────┐
│  CORTEX NORTH STAR METRICS                              │
│                                                          │
│  Adoption:                                               │
│  ├── GitHub stars (target: 100 by Jun, 500 by Sep)      │
│  ├── pip installs / week (target: 50 by Jun)            │
│  └── Issues filed by non-Jesse users (target: 10 by Jun)│
│                                                          │
│  Quality:                                                │
│  ├── AMA-Bench score (baseline TBD)                     │
│  ├── Anti-pattern recurrence rate (target: <5%)         │
│  └── Model routing accuracy (target: >80% optimal)      │
│                                                          │
│  Learning:                                               │
│  ├── Implicit outcomes derived / week (target: 50+)     │
│  ├── Outcome→retrieval boost measured improvement        │
│  └── CRA discoveries adopted / month (target: 2-3)      │
│                                                          │
│  Compounding:                                            │
│  ├── Time-to-productive-session (should decrease)        │
│  └── Repeated mistakes (anti-pattern hits, should → 0)  │
│                                                          │
│  Research Agent:                                         │
│  ├── Discoveries scanned / week                         │
│  ├── Assessments generated / week                       │
│  └── Proposals adopted → outcome (did it actually help?)│
└─────────────────────────────────────────────────────────┘
```

---

### Implementation Priority (Next 2 Weeks)

```
Week of Mar 12-14 (SHIP WEEK):
  ├── [x] Outcome-aware retrieval wired (done today)
  ├── [ ] git subtree push → standalone repo
  ├── [ ] Zenodo DOI
  ├── [ ] Show HN post
  └── [ ] Share with beta users

Week of Mar 17-21 (RESEARCH AGENT FOUNDATION):
  ├── [ ] Read survey paper (2603.07670) — inform all decisions
  ├── [ ] Prototype CRA discovery engine (arxiv RSS + semantic filter)
  ├── [ ] Wire CRA output into cortex briefing
  ├── [ ] Design trajectory memory data model
  └── [ ] CLI decomposition (cli.py → commands/)
```

---

### Decision Log

| Date | Decision | Reasoning |
|------|----------|-----------|
| 2026-03-12 | Don't compete on retrieval quality | Mem0/Supermemory have 50K+ stars and dedicated teams. Our BM25+embedding is adequate. Compete on intelligence layer instead |
| 2026-03-12 | Build auto-research agent before Mem0 integration | CRA compounds everything — helps us discover what to integrate and when. Mem0 integration is a point improvement |
| 2026-03-12 | MCP as primary interface (not Claude-specific) | Provider-native memory is coming. MCP abstracts across providers. Reduces lock-in risk |
| 2026-03-12 | Batch API for research scans | 50% cost savings. Research is not latency-sensitive. Fits existing overnight dispatch infrastructure |

---

## Appendix: CRA Technical Specification

### Module Structure

```
cortex/
├── engines/
│   └── research_agent/
│       ├── __init__.py
│       ├── discovery.py      # Source scanning (arxiv, GitHub, MCP)
│       ├── analysis.py       # Relevance scoring, disruption detection
│       ├── proposal.py       # Integration plan generation
│       ├── bridge.py         # CRA ↔ Cortex intelligence bridge
│       └── sources/
│           ├── arxiv.py      # arxiv RSS + API
│           ├── github.py     # Trending repos + topic search
│           ├── mcp_registry.py  # MCP server discovery
│           └── hacker_news.py   # HN API filtered search
```

### Data Models

```python
@dataclass
class Discovery:
    id: str
    source: str          # "arxiv", "github", "mcp", "hn"
    title: str
    url: str
    summary: str         # 2-3 sentence summary
    discovered_at: datetime
    relevance_scores: Dict[str, float]  # per-capability
    raw_metadata: dict

@dataclass
class Assessment:
    discovery_id: str
    disruption_risk: float       # 0-1
    adoption_effort: str         # trivial/small/medium/large/rewrite
    expected_impact: str         # incremental/significant/transformative
    affected_modules: List[str]
    integration_approach: str    # 1-paragraph
    risks: List[str]
    recommendation: str          # adopt/monitor/dismiss
    reasoning: str
    assessed_at: datetime

@dataclass
class Proposal:
    assessment_id: str
    title: str
    spec: str                    # Golden Spec format markdown
    estimated_effort_days: int
    success_criteria: List[str]
    created_at: datetime
    status: str                  # draft/approved/implementing/shipped/abandoned
    outcome: Optional[str]       # measured result after shipping
```

### Batch Integration

```python
# In supervisor/intake.py — add research tasks to work discovery
def discover_from_research() -> List[WorkItem]:
    """Surface CRA proposals as potential work items."""
    proposals = CRABridge().get_pending_proposals()
    items = []
    for p in proposals:
        if p.status == "approved":
            items.append(WorkItem(
                title=f"Research integration: {p.title}",
                source="cra",
                priority=WorkItemPriority.MEDIUM,
                estimated_complexity=p.estimated_effort_days,
            ))
    return items
```

### Cowork / Data Sharing Protocol

```python
# If cowork is available, CRA exposes MCP resources:
@mcp.resource("cortex://research/discoveries")
def get_recent_discoveries():
    """Last 7 days of CRA discoveries, scored and sorted."""
    return CRABridge().get_relevant_discoveries(days=7)

@mcp.resource("cortex://research/proposals")
def get_pending_proposals():
    """Integration proposals awaiting approval."""
    return CRABridge().get_pending_proposals()

@mcp.tool("cortex_research_assess")
def assess_topic(topic: str) -> str:
    """On-demand: assess a specific technology/paper for Cortex relevance."""
    discovery = Discovery(title=topic, source="manual", ...)
    assessment = AnalysisEngine().assess(discovery)
    return assessment.to_json()
```

### Without Cowork (File-Based Fallback)

```
~/.cortex/research/
├── discoveries.jsonl       # Append-only discovery log
├── assessments.jsonl       # Scored assessments
├── proposals/
│   ├── 2026-03-15_trajectory_memory.md
│   └── 2026-03-22_mem0_integration.md
├── adopted.jsonl           # Shipped integrations + outcomes
├── dismissed.jsonl         # Rejected with reasoning
└── digest_cache.json       # Weekly digest cache
```

CRA runs via batch queue (overnight), writes to these files. `cortex briefing` reads them. No cowork dependency required.
