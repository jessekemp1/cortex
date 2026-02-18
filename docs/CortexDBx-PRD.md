# CortexDBx Product Requirements Document
## Outcome-Aware Intelligence Layer for Databricks

**Version:** 0.1.0  
**Status:** Draft  
**Branch:** `feature/cortex-dbx`

---

## 1. Overview

### 1.1 What is CortexDBx?

CortexDBx is an add-on layer for Databricks that tracks operational outcomes and surfaces calibrated recommendations. It answers: "Given this situation, what approach has historically worked?"

### 1.2 What CortexDBx is NOT

- **Not a chatbot**: No conversational interface, no "ask me anything"
- **Not RAG**: Does not retrieve documents or general knowledge
- **Not monitoring**: Does not replace Databricks System Tables or Lakehouse Monitoring
- **Not MLOps**: Does not manage model lifecycle or feature stores

### 1.3 One-Sentence Value Proposition

> CortexDBx prevents teams from repeating mistakes by surfacing "this worked before" recommendations with calibrated confidence scores.

---

## 2. Problem

### 2.1 The Repeated Mistake Problem

Organizations using Databricks experience knowledge loss through:

1. **Staff turnover**: Senior engineer leaves, their "tribal knowledge" leaves too
2. **Session isolation**: AI assistants (Genie, Mosaic) reset context each session
3. **Siloed teams**: Team A solves a problem, Team B hits the same problem next month
4. **No feedback loop**: Query runs, succeeds or fails, but no system records which approach worked

### 2.2 Concrete Example

**Scenario**: Query optimization in a data engineering team

| Day | Event | What Should Happen | What Actually Happens |
|-----|-------|--------------------|-----------------------|
| Monday | Analyst A runs slow query | - | Query takes 45 minutes |
| Monday | Analyst A discovers broadcast join fixes it | - | Query takes 2 minutes |
| Tuesday | Analyst B faces same table | System warns: "broadcast join worked for this table" | Analyst B runs slow query, wastes 45 minutes |

**Cost of problem**: Hours of compute waste, engineer frustration, repeated work.

### 2.3 Why Databricks Doesn't Solve This

| Databricks Feature | What It Does | What It Doesn't Do |
|--------------------|--------------|---------------------|
| System Tables | Records query history | Doesn't track which approaches succeeded |
| Unity Catalog | Tracks data lineage | Doesn't track operational outcomes |
| Mosaic AI | Executes AI tasks | Resets context each request |
| Genie | Answers questions about data | Doesn't learn from past answers |

---

## 3. Users

### 3.1 Primary Users

| User | Job Function | Pain Point | CortexDBx Value |
|------|--------------|------------|-----------------|
| Data Engineer | Build pipelines | Debugging recurring failures | "This error pattern was fixed by X last time" |
| Platform Admin | Manage costs | Runaway query costs | "Query pattern Y typically costs $Z, recommend optimization" |
| Analytics Engineer | Write queries | Performance issues | "For this table, approach A has 85% success rate" |

### 3.2 Secondary Users

| User | Job Function | CortexDBx Value |
|------|--------------|-----------------|
| Security Analyst | Investigate threats | "Playbook X had 90% success for this threat type" |
| ML Engineer | Train models | "Configuration Y caused OOM 80% of the time" |

### 3.3 Non-Users

CortexDBx is NOT designed for:
- Business analysts who only consume dashboards
- Executives who need high-level summaries
- External customers/end-users

---

## 4. Requirements

### 4.1 Functional Requirements

#### P0 (Must Have for Launch)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-01 | **Outcome logging SDK** | Python SDK allows `cortex.log_outcome(context, strategy, result)` |
| FR-02 | **Query history ingestion** | System auto-ingests `system.query.history` failures/successes |
| FR-03 | **Confidence calculation** | System computes calibrated confidence using Bayesian updating |
| FR-04 | **Recommendation API** | `cortex.recommend(context)` returns ranked strategies with confidence |
| FR-05 | **Unity Catalog storage** | All data stored in UC-governed Delta tables |

#### P1 (Required for Adoption)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-06 | **Genie integration** | Cortex recommendations appear in Genie responses |
| FR-07 | **Webhook alerts** | High-confidence warnings sent to Slack/Teams |
| FR-08 | **Context similarity** | System finds similar (not just exact) contexts |
| FR-09 | **Multi-domain support** | Separate outcome tracking for query/security/cost domains |

#### P2 (Nice to Have)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-10 | **Dashboard UI** | React app shows outcome history and strategy rankings |
| FR-11 | **VS Code extension** | IDE sidebar displays relevant recommendations |
| FR-12 | **DLT streaming ingest** | Sub-minute outcome ingestion via DLT |
| FR-13 | **Cross-workspace sharing** | Outcomes shareable across workspaces (with UC governance) |

### 4.2 Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| **Latency** | Recommendation API p99 | < 200ms |
| **Scale** | Outcomes stored | 10M initial, 1B stretch |
| **Availability** | Uptime | 99.9% (Databricks SLA) |
| **Security** | Data access | Respects Unity Catalog ACLs |
| **Cost** | Overhead | < 5% of customer DBX spend |

---

## 5. User Stories

### 5.1 Core Flow: Learning from Mistakes

```
AS A data engineer
WHEN my query fails
I WANT the system to record what happened
SO THAT future queries can avoid the same mistake
```

**Scenario**:
1. Engineer runs query that OOMs
2. CortexDBx absorber detects failure in `system.query.history`
3. CortexDBx extracts context (table, query pattern, cluster size)
4. CortexDBx records outcome: context C + strategy S = FAILURE
5. Next time someone queries context C, CortexDBx warns: "Strategy S failed here"

### 5.2 Core Flow: Getting Recommendations

```
AS A data engineer
WHEN I'm about to run an expensive query
I WANT to know what approach worked before
SO THAT I don't waste compute on failed patterns
```

**Scenario**:
1. Engineer opens query editor with large table
2. CortexDBx (via Genie or IDE extension) detects context
3. CortexDBx queries outcome history for similar contexts
4. CortexDBx surfaces: "Broadcast join has 85% success rate (N=42)"
5. Engineer uses recommended approach, succeeds

### 5.3 Core Flow: Manual Outcome Logging

```
AS A platform admin
WHEN I resolve an incident using a specific approach
I WANT to record what worked
SO THAT the next person facing this incident knows
```

**Scenario**:
1. Admin resolves cost spike by terminating runaway job
2. Admin calls `cortex.log_outcome(context="cost_spike_job_type_X", strategy="terminate_and_resize", result="SUCCESS")`
3. Next cost spike of type X: CortexDBx recommends "terminate_and_resize" with confidence score

---

## 6. Success Metrics

### 6.1 Leading Indicators (Adoption)

| Metric | Definition | Target (90 days) |
|--------|------------|------------------|
| SDK installs | pip installs of cortexdbx | 100+ |
| Outcomes logged | Total outcome records | 10,000+ |
| Active users | Users who logged or queried outcomes | 50+ |
| Workspaces deployed | Distinct DBX workspaces with CortexDBx | 10+ |

### 6.2 Lagging Indicators (Value)

| Metric | Definition | Target (180 days) |
|--------|------------|-------------------|
| Recommendation acceptance | % of recommendations followed by users | > 60% |
| Calibration accuracy | Correlation between confidence and actual success | > 0.8 |
| Repeat failure reduction | % decrease in same-context failures | > 30% |
| Compute savings | $ saved from avoided failed queries | Track, no target |

### 6.3 Anti-Metrics (What We Don't Optimize)

| Anti-Metric | Why We Avoid It |
|-------------|-----------------|
| Recommendations shown | Gaming this leads to alert fatigue |
| AI tokens consumed | Efficiency matters more than volume |
| Features shipped | Quality over quantity |

---

## 7. Design Principles

### 7.1 Passive Over Active

**Principle**: Learn by watching, not by asking.

- BAD: "Please describe what you did and whether it worked"
- GOOD: Watch exit codes, query status, test results automatically

**Rationale**: Engineers won't maintain manual logs. The only sustainable knowledge capture is automatic.

### 7.2 Calibrated Over Confident

**Principle**: Say "I don't know" when you don't know.

- BAD: "This will definitely work" (hallucinated confidence)
- GOOD: "80% confidence based on 15 prior outcomes" or "No data for this context"

**Rationale**: Overconfident wrong recommendations destroy trust faster than silence.

### 7.3 Targeted Over Comprehensive

**Principle**: Solve specific problems deeply, not all problems shallowly.

- BAD: "Intelligence layer for everything"
- GOOD: "Outcome tracking for query optimization, security playbooks, cost governance"

**Rationale**: Focused products win. "Do one thing well" is not optional.

### 7.4 Zero-Migration

**Principle**: Work with existing data infrastructure, don't require moving data.

- BAD: "Ingest your data into our platform"
- GOOD: "Sit on top of your existing Delta tables"

**Rationale**: Data migration is the #1 blocker for enterprise adoption.

---

## 8. Competitive Positioning

### 8.1 vs. Databricks Native

| Capability | Databricks | CortexDBx |
|------------|------------|-----------|
| Query history | Records events | Tracks outcomes |
| AI assistant | Answers questions | Learns from answers |
| Monitoring | Shows metrics | Recommends actions |

**Position**: CortexDBx adds "operational memory" that Databricks doesn't have.

### 8.2 vs. Palantir AIP

| Capability | Palantir AIP | CortexDBx |
|------------|--------------|-----------|
| Data model | Rigid ontology | Flexible context graph |
| Setup time | Months | Hours |
| Learning | Manual optimization | Automatic calibration |
| Deployment | Full platform | Lightweight add-on |

**Position**: CortexDBx is the "agile learning layer" for teams who can't wait for enterprise integration.

### 8.3 vs. Knowledge Management (Wikis, Notion)

| Capability | Wikis/Notion | CortexDBx |
|------------|--------------|-----------|
| Input method | Manual documentation | Automatic ingestion |
| Freshness | Stale immediately | Updated with each outcome |
| Discoverability | Search-based | Proactive push |

**Position**: CortexDBx captures knowledge as a byproduct of work, not as extra work.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Low outcome volume** | High | High | Seed with synthetic outcomes, focus on high-traffic use cases |
| **Poor context matching** | Medium | High | Start with exact match only, add similarity later |
| **Alert fatigue** | Medium | Medium | Conservative thresholds, user-configurable |
| **Databricks API changes** | Low | Medium | Abstract ingestion layer, version pin |
| **Privacy concerns** | Medium | High | Strict UC ACL enforcement, no cross-tenant data |

---

## 10. Out of Scope (Explicit Non-Goals)

The following are explicitly NOT in scope for CortexDBx:

1. **General-purpose AI chat**: Not building another Genie competitor
2. **Data quality monitoring**: DLT Expectations and Lakehouse Monitoring exist
3. **MLOps/Feature Store**: MLflow and Feature Engineering exist
4. **Real-time alerting**: PagerDuty/OpsGenie integrations are delivery, not core
5. **Multi-cloud support**: Databricks-only initially, no Snowflake/BigQuery

---

## 11. Dependencies

### 11.1 Databricks Platform Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Unity Catalog | GA | Storage governance |
| System Tables | GA | Query history ingestion |
| Model Serving | GA | Broker API endpoint |
| Databricks Apps | GA | Dashboard hosting |
| Mosaic AI Gateway | Preview | AI interaction logging |

### 11.2 External Dependencies

| Dependency | Purpose | Risk |
|------------|---------|------|
| None | - | CortexDBx runs entirely within customer's Databricks environment |

---

## 12. Implementation Phases

### Phase 1: Foundation

**Scope**:
- Delta table schema for outcomes/contexts/strategies
- Absorber job for `system.query.history`
- Python SDK with `log_outcome()` and `recommend()`
- Unit tests for confidence math

**Exit Criteria**:
- 1000+ outcomes logged in test environment
- Confidence scores correlate with actual success rates (r > 0.7)

### Phase 2: Intelligence

**Scope**:
- Context similarity matching
- Broker Model Serving endpoint
- Genie UC Function integration
- Basic VS Code extension (read-only)

**Exit Criteria**:
- Recommendations surfaced in Genie
- >60% recommendation acceptance rate

### Phase 3: Scale

**Scope**:
- DLT streaming absorber
- React Dashboard App
- Multi-domain support
- Performance optimization

**Exit Criteria**:
- <200ms p99 latency at 10M outcomes
- Deployed at 3+ customer environments

---

## 13. Open Questions

| Question | Owner | Due |
|----------|-------|-----|
| Which domains to prioritize (query/security/cost)? | Product | Before Phase 1 |
| Exact vs. similarity matching in Phase 1? | Engineering | Before Phase 1 |
| Genie vs. Assistant integration path? | Engineering | Before Phase 2 |
| Pricing model for commercial release? | Business | Before Phase 3 |

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **Outcome** | Structured record: context + strategy + result |
| **Context** | Fingerprint of operational environment |
| **Strategy** | Named approach to solving a problem class |
| **Confidence** | Bayesian probability of success, calibrated from outcomes |
| **Absorber** | Component that ingests outcome signals |
| **Broker** | Component that delivers recommendations |
| **Calibration** | Process of updating confidence based on new evidence |
