# Cortex v1: Core Documentation
## The Intelligence Layer for Compounding Operational Wisdom

**Version:** 1.0  
**Status:** Canonical Reference  
**Last Updated:** 2026-01-29

---

## 1. What Cortex Is

Cortex is an **Intelligence Layer** that sits between humans and AI execution tools. It tracks outcomes, calibrates confidence, and learns which recommendations actually work.

```
+---------------------------+
|     Human Decision        |
+------------+--------------+
             |
             v
+---------------------------+
|    Cortex Intelligence    |  <-- Tracks outcomes, calibrates confidence
|    Layer                  |      Surfaces proven recommendations
+------------+--------------+
             |
             v
+---------------------------+
|    Execution Layer        |  <-- Claude, Cursor, Databricks, etc.
+------------+--------------+
             |
             v
+---------------------------+
|    Domain Systems         |  <-- Your actual applications
+---------------------------+
```

### What Cortex Does

1. **Observes** decisions and their outcomes passively
2. **Records** structured outcome data (context + strategy + result)
3. **Calibrates** confidence scores based on historical success rates
4. **Surfaces** recommendations when similar contexts arise
5. **Learns** from feedback to improve over time

### What Cortex Does NOT Do

- Replace execution tools (use Claude, Cursor, Databricks for execution)
- Provide general-purpose chat (use ChatGPT, Claude for conversation)
- Store raw documents (use Obsidian, Notion for notes)
- Monitor infrastructure (use Datadog, Grafana for metrics)

---

## 2. Core Concepts

### 2.1 The Outcome

The atomic unit of learning. Every outcome captures:

```python
@dataclass
class Outcome:
    id: str                    # Unique identifier
    context_hash: str          # Fingerprint of the situation
    strategy_id: str           # What approach was taken
    result: str                # SUCCESS | FAILURE | PARTIAL
    confidence_prior: float    # Confidence before this outcome
    confidence_posterior: float # Confidence after this outcome
    timestamp: datetime
    evidence: Dict[str, Any]   # Links to source data
    notes: Optional[str]       # Human annotations
```

### 2.2 The Context

A fingerprint of the operational environment:

```python
@dataclass  
class Context:
    context_hash: str          # SHA256 of normalized factors
    factors: List[Dict]        # Key-value pairs describing situation
    domain: str                # query_optimization, security, etc.
    first_seen: datetime
    last_seen: datetime
```

### 2.3 The Strategy

A named approach to solving a class of problems:

```python
@dataclass
class Strategy:
    strategy_id: str           # Unique identifier
    name: str                  # Human-readable name
    description: str           # What this approach does
    domain: str                # Which problem domain
    success_count: int         # Times this worked
    failure_count: int         # Times this failed
    confidence: float          # Current calibrated confidence
```

### 2.4 Confidence Calibration

Confidence is Bayesian, not asserted:

```python
def update_confidence(prior_alpha: float, prior_beta: float,
                      successes: int, failures: int) -> float:
    """
    Beta-Binomial model for confidence calibration.

    Returns: P(success) = (alpha + successes) / (alpha + beta + successes + failures)
    """
    posterior_alpha = prior_alpha + successes
    posterior_beta = prior_beta + failures
    return posterior_alpha / (posterior_alpha + posterior_beta)
```

**Confidence buckets:**
- **High (0.8-1.0)**: Target 85%+ actual success rate
- **Medium (0.5-0.8)**: Target 60-70% actual success rate  
- **Low (0.0-0.5)**: Experimental, may fail

---

## 3. Architecture

### 3.1 Three-Engine Pipeline

```
+------------------+     +------------------+     +------------------+
|    OBSERVER      |     |  ORIENTATION     |     |     BROKER       |
|                  |     |     CORE         |     |                  |
| - File changes   |---->| - Context match  |---->| - Recommendations|
| - Shell output   |     | - Outcome store  |     | - Alerts         |
| - Git events     |     | - Calibration    |     | - Dashboard      |
| - Explicit SDK   |     |                  |     | - Agent tools    |
+------------------+     +------------------+     +------------------+
```

**Observer** (Engine A): Passive signal collection
- Watches file system, shell commands, git operations
- Ingests system tables, logs, events
- Requires zero user effort to capture data

**Orientation Core** (Engine B): Context and learning
- Maps signals to contexts and strategies
- Stores outcomes with evidence
- Updates confidence via Bayesian calibration

**Broker** (Engine C): Intervention delivery
- Surfaces recommendations at decision points
- Respects confidence thresholds (silent when unknown)
- Delivers via appropriate channel (CLI, dashboard, webhook)

### 3.2 Storage

**Local Cortex** (personal/dev):
```
~/.cortex/
├── outcomes.jsonl       # Append-only outcome log
├── contexts.json        # Known context fingerprints
├── strategies.json      # Strategy definitions
├── calibration.json     # Confidence state
└── config.yaml          # User configuration
```

**Enterprise Cortex** (CortexDBx):
```
cortex_catalog.cortex_schema/
├── signals_raw          # Delta table: raw events
├── contexts             # Delta table: context entities
├── strategies           # Delta table: strategy entities  
├── outcomes             # Delta table: outcome events
├── context_strategy_edges # Delta table: calibrated edges
├── recommendations      # Delta table: generated recs
└── feedback             # Delta table: user feedback
```

---

## 4. The Learning Loop

### 4.1 Flow

```
1. SIGNAL          2. CONTEXT         3. STRATEGY        4. OUTCOME
   Raw event   -->    Fingerprint  -->   Approach    -->   Result
                                                              |
                                                              v
5. CALIBRATION     6. RECOMMENDATION    7. FEEDBACK
   Update P(s)  <--   Surface rec    <--   User rates
```

### 4.2 Implementation

```python
class CortexEngine:
    def observe(self, signal: Dict) -> None:
        """Ingest raw signal, extract context."""
        context = self.extract_context(signal)
        self.store_signal(signal, context)

    def record_outcome(self, context_hash: str, strategy_id: str,
                       result: str, evidence: Dict) -> None:
        """Record outcome and update calibration."""
        outcome = Outcome(
            id=uuid4(),
            context_hash=context_hash,
            strategy_id=strategy_id,
            result=result,
            evidence=evidence,
            timestamp=datetime.now()
        )
        self.store_outcome(outcome)
        self.update_calibration(context_hash, strategy_id, result)

    def recommend(self, context: Dict) -> List[Recommendation]:
        """Get recommendations for current context."""
        context_hash = self.fingerprint(context)
        similar_contexts = self.find_similar(context_hash)
        strategies = self.get_strategies_for_contexts(similar_contexts)
        return self.rank_by_confidence(strategies)

    def intervene(self, context: Dict) -> Optional[Intervention]:
        """Decide whether/how to intervene."""
        recommendations = self.recommend(context)

        if not recommendations:
            return None  # No data, stay silent

        top = recommendations[0]

        if top.confidence < 0.3:
            return Warning(f"High failure risk: {top.strategy}")
        elif top.confidence > 0.8:
            return Recommendation(f"Recommended: {top.strategy}")
        else:
            return None  # Uncertain, stay silent
```

---

## 5. Deployment Variants

### 5.1 Personal Cortex (Local)

For individual developers:

```bash
# Install
pip install cortex-intelligence

# Initialize
cortex init

# Start observer
cortex observe --background

# Get recommendations
cortex recommend "deploying to production"

# Log outcome
cortex log-outcome --context "deploy_prod" --strategy "blue_green" --result success
```

**Storage:** Local filesystem (`~/.cortex/`)
**Compute:** Local Python process
**Interface:** CLI + optional dashboard

### 5.2 Team Cortex (Shared)

For small teams:

```bash
# Initialize with shared storage
cortex init --storage postgres://team-db/cortex

# All team members observe to same store
cortex observe --background --team-mode

# Recommendations draw from team-wide outcomes
cortex recommend "handling customer escalation"
```

**Storage:** PostgreSQL or SQLite (shared)
**Compute:** Local or containerized
**Interface:** CLI + shared dashboard

### 5.3 Enterprise Cortex (CortexDBx)

For organizations on Databricks:

**Storage:** Delta Lake in Unity Catalog
**Compute:** Databricks Jobs, Model Serving
**Interface:** Databricks Apps, webhooks, agent tools

See: `CortexDBx-MVP-Implementation.md`

---

## 6. Current State

### 6.1 What Exists

| Component | Status | Location |
|-----------|--------|----------|
| Observer (file/shell/git) | Implemented | `cortex/engines/absorber.py` |
| Synthesis Core | Implemented | `cortex/engines/synthesis.py` |
| Broker | Implemented | `cortex/engines/broker.py` |
| Learning System | Implemented | `cortex/learning.py` |
| CLI | Implemented | `cortex/cli.py` |
| Dashboard | Implemented | `cortex/dashboard/` |
| 54 Slash Commands | Implemented | `.claude/commands/` |

### 6.2 Technical Debt

| Issue | Impact | Priority |
|-------|--------|----------|
| `cli.py` is 3,857 lines | Hard to maintain | Medium |
| 134 hardcoded paths | Blocks portability | High |
| No multi-user support | Blocks team use | Medium |

### 6.3 What's Validated

- Outcome tracking works and accumulates data
- Confidence calibration improves recommendations over time
- Anti-pattern detection catches real problems (context switching, validated-not-shipped)
- Portfolio memory surfaces cross-project patterns

### 6.4 What's Unvalidated

- Compounding effect at scale (need 100+ outcomes)
- Cross-team learning (single-user only so far)
- Enterprise deployment (CortexDBx is spec, not implementation)

---

## 7. Iteration Roadmap

### Phase 1: Stabilization (Current)

**Goal:** Solidify local Cortex for single-user production use.

- [ ] Refactor `cli.py` into modules (<500 lines each)
- [ ] Replace hardcoded paths with config
- [ ] Add comprehensive tests for learning system
- [ ] Document all slash commands
- [ ] Achieve 100+ logged outcomes for calibration validation

**Exit Criteria:** Single-user Cortex runs reliably with validated calibration.

### Phase 2: Team Support

**Goal:** Enable small team usage with shared learning.

- [ ] Shared storage backend (PostgreSQL or SQLite server)
- [ ] User attribution on outcomes
- [ ] Team-wide recommendation aggregation
- [ ] Access controls (who can see what)
- [ ] Team dashboard

**Exit Criteria:** 3-5 person team using shared Cortex productively.

### Phase 3: Enterprise (CortexDBx)

**Goal:** Production deployment on Databricks.

- [ ] Delta table schema deployed
- [ ] Observer jobs for system tables
- [ ] Python SDK for outcome logging
- [ ] Databricks App dashboard
- [ ] Agent tool integration

**Exit Criteria:** Deployed at 1+ enterprise customer with validated ROI.

### Phase 4: Intelligence Scaling

**Goal:** Advanced learning and cross-domain intelligence.

- [ ] Automated experiment suggestion
- [ ] Cross-domain pattern transfer
- [ ] Self-healing workflows (with human approval)
- [ ] Public API for intelligence queries

**Exit Criteria:** System demonstrably improves decision quality at scale.

---

## 8. Design Principles

### 8.1 Passive Over Active

Learn by watching, not by asking. The only sustainable knowledge capture is automatic.

### 8.2 Calibrated Over Confident

Say "I don't know" when you don't know. Overconfident wrong recommendations destroy trust.

### 8.3 Narrow Over Broad

Solve specific problems deeply. Don't try to be "intelligence for everything."

### 8.4 Evidence Over Assertion

Every recommendation must cite evidence. "Based on 47 outcomes" is actionable. "I think" is not.

### 8.5 Compound Over Execute

Optimize for learning, not for doing. Execution tools are commoditized. Intelligence is not.

---

## 9. File Reference

### Core Engine

```
cortex/
├── engines/
│   ├── absorber.py         # Signal capture
│   ├── synthesis.py        # Context graph
│   └── broker.py           # Intervention delivery
├── learning.py             # Outcome tracking, calibration
├── feedback.py             # Outcome logging
├── recommendation_engine.py # Strategy ranking
└── portfolio_memory.py     # Cross-project intelligence
```

### Integration

```
cortex/
├── integration/
│   ├── feedback_loop.py    # Learning integration
│   └── local_orchestrator.py # Local execution
├── intelligence/
│   ├── unified_intelligence.py # Aggregate sources
│   └── monitoring/         # Anomaly detection
└── cli.py                  # Command-line interface
```

### Commands

```
.claude/commands/           # 54 slash commands
├── investigate.md          # Research only
├── plan.md                 # Design with DoD
├── implement.md            # TDD execution
├── review.md               # Code review
├── cortex-feedback.md      # Log outcomes
└── ...
```

---

## 10. Getting Started

### For Developers (Local)

```bash
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate

# Run daily scan
./daily_scan.sh

# Launch dashboard
./launch_dashboard.sh

# Log an outcome
python -m cortex.cli feedback --outcome success --notes "Fixed the bug"
```

### For Architects (Documentation)

```
docs/
├── v1/
│   ├── CORTEX_CORE.md      # This document
│   └── CORTEXDBX_MVP.md    # Enterprise implementation
├── cortexdbx/
│   ├── aPRD.md             # Product requirements
│   ├── TECHNICAL_PAPER.md  # Technical specification
│   └── spec/               # Detailed specs
└── user_guide/             # End-user documentation
```

### For Builders (Implementation)

See `CortexDBx-MVP-Implementation.md` for the enterprise build guide with synthetic data and agent teams.

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **Outcome** | Structured record: context + strategy + result |
| **Context** | Fingerprint of operational environment |
| **Strategy** | Named approach to a problem class |
| **Confidence** | Bayesian probability of success |
| **Observer** | Component that ingests signals |
| **Orientation Core** | Component that stores and calibrates |
| **Broker** | Component that delivers recommendations |
| **Calibration** | Updating confidence based on evidence |
| **Intelligence Layer** | Architecture pattern: learning between human and execution |
