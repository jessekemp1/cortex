# CortexDBx Technical Specification
## Outcome-Aware Intelligence Layer for Databricks

**Version:** 0.1.0-draft  
**Status:** Specification (Pre-Implementation)  
**Branch:** `feature/cortex-dbx`

---

## 1. Problem Statement

### 1.1 The Stateless System Problem

Modern data platforms execute tasks but do not learn from outcomes. Consider a Security Operations Center using Databricks:

1. Analyst runs query to investigate threat indicator
2. Query times out due to unoptimized join
3. Analyst rewrites query with filter pushdown - succeeds
4. **Next week**: Different analyst encounters same table, makes same mistake

The platform has no mechanism to capture: "Query pattern X on table Y fails; pattern Z succeeds."

### 1.2 What Databricks Provides (and Doesn't)

| Capability | Databricks Native | Gap |
|------------|-------------------|-----|
| Query execution | Spark SQL, Photon | No outcome tracking |
| AI inference | Mosaic AI Model Serving | Stateless per request |
| Data lineage | Unity Catalog | Tracks *what*, not *whether it worked* |
| Monitoring | System Tables | Raw events, no strategy calibration |

### 1.3 Target Problem Scope

CortexDBx addresses **operational decision optimization** - choosing between known strategies based on historical outcomes. It does NOT address:

- General-purpose RAG/knowledge retrieval
- Real-time ML model serving
- Data quality monitoring (DLT Expectations handles this)

---

## 2. Core Concepts

### 2.1 Outcome

The atomic unit of learning. An Outcome records:

```
Outcome {
  id: UUID
  context_hash: string        # Fingerprint of execution context
  strategy_id: string         # What approach was taken
  result: SUCCESS | FAILURE | PARTIAL
  confidence_delta: float     # How much this changed our belief
  timestamp: datetime
  metadata: map<string, any>  # Domain-specific details
}
```

**Key insight**: We don't store "logs" or "events." We store structured records that link *what was tried* to *what happened*.

### 2.2 Context

A fingerprint of the operational environment when a decision was made:

```
Context {
  context_hash: string        # SHA256 of normalized factors
  factors: [
    { key: "table_size_gb", value: "500" },
    { key: "join_type", value: "broadcast" },
    { key: "time_of_day", value: "business_hours" }
  ]
  domain: string              # e.g., "query_optimization", "security_response"
}
```

### 2.3 Strategy

A named approach to solving a class of problems:

```
Strategy {
  strategy_id: string         # e.g., "broadcast_join_under_1gb"
  description: string
  domain: string
  success_count: int
  failure_count: int
  confidence: float           # Bayesian posterior, updated on each outcome
}
```

### 2.4 Confidence Calibration

Confidence is **calibrated**, not asserted. The system uses Bayesian updating:

```
P(success | evidence) = P(evidence | success) * P(success) / P(evidence)
```

A strategy with 8 successes and 2 failures has confidence:
- Prior: 0.5 (no information)
- Posterior: ~0.80 (calibrated from outcomes)

A strategy never used has confidence: 0.5 (unknown)

---

## 3. Architecture

### 3.1 Component Overview

```
+------------------+     +------------------+     +------------------+
|   ABSORBER       |     |   GRAPH ENGINE   |     |   BROKER         |
|                  |     |                  |     |                  |
| - System Tables  |---->| - Context Match  |---->| - Genie Plugin   |
| - DLT Events     |     | - Outcome Store  |     | - IDE Extension  |
| - AI Gateway     |     | - Calibration    |     | - Webhook Alerts |
| - Manual SDK     |     |                  |     | - Dashboard App  |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        v                        v                        v
+---------------------------------------------------------------+
|                     DELTA LAKE (Unity Catalog)                |
|  cortex_outcomes | cortex_contexts | cortex_strategies        |
+---------------------------------------------------------------+
```

### 3.2 Absorber (Input Layer)

**Purpose**: Passive collection of outcome signals without user effort.

**Data Sources**:

| Source | Table/API | Signal Extracted |
|--------|-----------|------------------|
| Query History | `system.query.history` | Query success/failure, runtime, cost |
| DLT Pipelines | `system.lakeflow.pipeline_events` | Pipeline failures, data quality |
| AI Gateway | Mosaic AI Gateway logs | Agent responses, user feedback |
| Manual SDK | `cortex.log_outcome()` | Explicit user reports |

**Processing Model**:
- Batch: Databricks Job runs every 15 minutes, scans new events
- Stream: Optional DLT pipeline for sub-minute latency

### 3.3 Graph Engine (Core)

**Purpose**: Maintain the outcome-strategy-context relationships and compute calibrated confidence.

**Storage Schema** (Delta Tables):

```sql
-- cortex_outcomes
CREATE TABLE cortex_outcomes (
  outcome_id STRING,
  context_hash STRING,
  strategy_id STRING,
  result STRING,  -- 'SUCCESS', 'FAILURE', 'PARTIAL'
  confidence_prior DOUBLE,
  confidence_posterior DOUBLE,
  created_at TIMESTAMP,
  metadata MAP<STRING, STRING>
) USING DELTA
PARTITIONED BY (date(created_at));

-- cortex_contexts  
CREATE TABLE cortex_contexts (
  context_hash STRING,
  factors ARRAY<STRUCT<key STRING, value STRING>>,
  domain STRING,
  first_seen TIMESTAMP,
  last_seen TIMESTAMP
) USING DELTA;

-- cortex_strategies
CREATE TABLE cortex_strategies (
  strategy_id STRING,
  description STRING,
  domain STRING,
  success_count BIGINT,
  failure_count BIGINT,
  confidence DOUBLE,
  updated_at TIMESTAMP
) USING DELTA;
```

**Context Matching Algorithm**:

1. Incoming context factors are normalized and hashed
2. Exact match attempted first (O(1) lookup)
3. If no exact match, similarity search on factor vectors
4. Threshold: similarity > 0.85 counts as "same context"

### 3.4 Broker (Output Layer)

**Purpose**: Deliver intelligence at the right moment with appropriate confidence.

**Intervention Thresholds**:

| Confidence | Behavior | UX |
|------------|----------|-----|
| < 0.3 | Block/Warn | Red alert: "This pattern has 70%+ failure rate" |
| 0.3 - 0.7 | Suggest | Yellow note: "Consider alternative approach X" |
| > 0.7 | Recommend | Green tip: "Recommended based on N outcomes" |
| Unknown (0.5) | Silent | No intervention |

**Delivery Channels**:

1. **Databricks Genie Integration**: Register as Unity Catalog Function, callable by Genie
2. **IDE Extension**: VS Code / Databricks Notebook sidebar
3. **Webhook Alerts**: Slack, Teams, PagerDuty for high-severity patterns
4. **Dashboard App**: Databricks Apps (React) for exploration

---

## 4. Data Flow

### 4.1 Learning Flow (Write Path)

```
Event Source                    Absorber                Graph Engine
     |                              |                        |
     |-- system.query.history ----->|                        |
     |                              |-- parse query -------->|
     |                              |   extract context      |
     |                              |   identify strategy    |
     |                              |                        |
     |                              |<-- context_hash -------|
     |                              |                        |
     |                              |-- create outcome ----->|
     |                              |                        |-- update confidence
     |                              |                        |-- store outcome
```

### 4.2 Inference Flow (Read Path)

```
User Query                      Broker                  Graph Engine
     |                              |                        |
     |-- "SELECT * FROM big" ----->|                        |
     |                              |-- extract context ---->|
     |                              |                        |
     |                              |<-- similar contexts ---|
     |                              |<-- strategy rankings --|
     |                              |                        |
     |<-- "Warning: 80% fail" -----|                        |
```

---

## 5. API Specification

### 5.1 Python SDK

```python
from cortexdbx import CortexClient

# Initialize (uses current Databricks context)
cortex = CortexClient()

# Manual outcome logging
cortex.log_outcome(
    context={"table": "orders", "operation": "aggregate"},
    strategy="incremental_refresh",
    result="SUCCESS",
    metadata={"duration_ms": 1200}
)

# Query for recommendations
recommendations = cortex.get_recommendations(
    context={"table": "orders", "operation": "aggregate"},
    min_confidence=0.7
)
# Returns: [{"strategy": "incremental_refresh", "confidence": 0.85, "evidence_count": 42}]

# Direct confidence query
confidence = cortex.get_confidence(
    context={"table": "orders", "join_type": "broadcast"},
    strategy="broadcast_join"
)
# Returns: 0.78
```

### 5.2 SQL Functions (Unity Catalog)

```sql
-- Get recommendation for current context
SELECT cortex.recommend(
  named_struct('table', 'orders', 'operation', 'join')
) as recommendation;

-- Log outcome from SQL
SELECT cortex.log_outcome(
  named_struct('context_hash', 'abc123', 'strategy', 'broadcast_join', 'result', 'SUCCESS')
);
```

### 5.3 REST API (Model Serving Endpoint)

```
POST /serving-endpoints/cortex-broker/invocations
Content-Type: application/json

{
  "action": "recommend",
  "context": {
    "table": "orders",
    "query_type": "aggregate"
  }
}

Response:
{
  "recommendations": [
    {"strategy": "incremental_refresh", "confidence": 0.85, "evidence": 42}
  ],
  "warnings": []
}
```

---

## 6. Deployment Model

### 6.1 Infrastructure Components

| Component | Databricks Resource | Sizing |
|-----------|---------------------|--------|
| Absorber (Batch) | Scheduled Job | 1x small cluster, 15-min schedule |
| Absorber (Stream) | DLT Pipeline | Auto-scaling, optional |
| Graph Engine | Delta Tables | Unity Catalog managed |
| Broker (Sync) | Model Serving Endpoint | Serverless, auto-scale |
| Broker (Dashboard) | Databricks App | Single container |

### 6.2 Security Model

- **Data Access**: All data respects Unity Catalog ACLs
- **Row-Level**: Users only see outcomes from data they can access
- **Audit**: All Cortex queries logged to `system.access.audit`
- **Secrets**: No external credentials required (runs entirely within DBX)

### 6.3 Cost Model

Estimated overhead as percentage of total Databricks spend:

| Workload Size | Absorber Cost | Serving Cost | Total Overhead |
|---------------|---------------|--------------|----------------|
| Small (<$10k/mo) | ~$50/mo | ~$20/mo | <1% |
| Medium ($10-100k/mo) | ~$200/mo | ~$100/mo | <0.5% |
| Large (>$100k/mo) | ~$500/mo | ~$300/mo | <0.2% |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Metric | Target | Rationale |
|--------|--------|-----------|
| Recommendation latency (p99) | < 200ms | Interactive UX requirement |
| Outcome ingestion lag | < 15 minutes (batch) / < 1 minute (stream) | Timely learning |
| Context match accuracy | > 90% | Useful recommendations |

### 7.2 Scale

| Metric | Initial Target | Stretch |
|--------|----------------|---------|
| Outcomes stored | 10M | 1B |
| Unique contexts | 100K | 10M |
| Strategies | 1K | 100K |
| Concurrent queries | 100 | 10K |

### 7.3 Reliability

| Metric | Target |
|--------|--------|
| Availability | 99.9% (aligned with DBX SLA) |
| Data durability | Delta Lake guarantees |
| Recovery time | < 1 hour (restore from Delta checkpoints) |

---

## 8. Implementation Phases

### Phase 1: Foundation

**Goal**: Prove the outcome tracking concept works.

- [ ] Delta table schema deployed via Terraform/Pulumi
- [ ] Absorber job ingesting `system.query.history`
- [ ] Python SDK with `log_outcome()` and `get_confidence()`
- [ ] Basic CLI for querying outcomes
- [ ] Unit tests for confidence calibration math

**Exit Criteria**: 1000 outcomes logged, confidence scores validated against actual success rates.

### Phase 2: Intelligence

**Goal**: Deliver proactive recommendations.

- [ ] Context matching algorithm (exact + similarity)
- [ ] Broker Model Serving endpoint
- [ ] Genie integration (UC Function)
- [ ] VS Code extension (read-only display)
- [ ] Integration tests with mock query workloads

**Exit Criteria**: Recommendations surfaced in Genie with >70% user acceptance rate.

### Phase 3: Scale

**Goal**: Production-ready for enterprise workloads.

- [ ] DLT streaming absorber
- [ ] Dashboard App (React)
- [ ] Multi-domain support (security, cost, performance)
- [ ] Row-level security enforcement
- [ ] Performance optimization (caching, indexing)

**Exit Criteria**: Deployed at 3+ enterprise customers, <200ms p99 latency at scale.

---

## 9. Open Questions

| Question | Impact | Status |
|----------|--------|--------|
| Should context matching use embeddings or rule-based? | Accuracy vs. complexity | Needs prototyping |
| How to handle conflicting outcomes (same context, different results)? | Confidence reliability | Propose variance tracking |
| Integration with Databricks Assistant vs Genie? | UX consistency | Awaiting DBX roadmap |
| Cross-workspace outcome sharing? | Enterprise value vs. privacy | Requires UC federation |

---

## 10. Glossary

- **Outcome**: Structured record linking strategy + context + result
- **Context**: Fingerprint of operational environment
- **Strategy**: Named approach to a problem class
- **Confidence**: Bayesian posterior probability of success
- **Absorber**: Component that ingests outcome signals
- **Broker**: Component that delivers recommendations
- **Graph Engine**: Core storage and computation layer

---

## Appendix A: Confidence Calibration Math

Given:
- `n_success`: Count of successful outcomes for strategy S in context C
- `n_failure`: Count of failed outcomes
- `prior`: Initial belief (default 0.5)

Posterior confidence using Beta-Binomial model:

```
alpha = prior * 2 + n_success
beta = (1 - prior) * 2 + n_failure
confidence = alpha / (alpha + beta)
```

This produces well-calibrated confidence that:
- Starts at 0.5 with no evidence
- Moves toward 1.0 with consistent success
- Moves toward 0.0 with consistent failure
- Requires significant evidence to reach extreme values

---

## Appendix B: Example Outcome Record

```json
{
  "outcome_id": "550e8400-e29b-41d4-a716-446655440000",
  "context_hash": "a1b2c3d4e5f6",
  "strategy_id": "broadcast_join_under_1gb",
  "result": "SUCCESS",
  "confidence_prior": 0.72,
  "confidence_posterior": 0.75,
  "created_at": "2026-01-29T10:30:00Z",
  "metadata": {
    "query_id": "abc-123",
    "duration_ms": "1200",
    "cost_dbu": "0.05",
    "table": "orders",
    "join_size_mb": "800"
  }
}
```
