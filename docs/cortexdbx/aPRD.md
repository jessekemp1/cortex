# CortexDBx: Abbreviated Product Requirements Document (aPRD)

**Version:** 1.0  
**Date:** 2026-01-29  
**Status:** Draft  
**Product Branch:** `feature/cortex-dbx`  

---

## 1. Vision and Positioning

CortexDBx is an add-on **Intelligence Layer** for the Databricks Data Intelligence Platform. It observes operational outcomes (query costs, failures, pipeline results), stores them in a structured Outcome Graph, calibrates confidence per strategy, and surfaces proactive, battle-tested recommendations. It turns the platform from a reactive tool ("here is your data") into a proactive partner ("here is what worked last time"). V1 is Databricks-only and focused on **query cost and failure guardrails**; pipeline reliability and optional IDE/CI collectors follow in later phases.

---

## 2. Primary Persona and Job-to-Be-Done

**Primary:** Platform Engineer / SQL power user (or Databricks admin / SRE).

**Job-to-be-done:** "I need to reduce runaway query cost and repeated failures without manually reviewing every query or pipeline run. I want the system to tell me which patterns are risky and what has worked before, with evidence and confidence."

**Secondary personas:** Security analysts (SOC) and business operators who need outcome-ranked recommendations in their domains; included in later phases.

---

## 3. MVP Scope (Tight)

- **Ingest:** Read system tables (e.g. `system.query.history`) and optionally Delta Live Table events; persist raw or normalized signals to Delta in Unity Catalog.
- **Outcome Graph:** Build and maintain contexts, strategies, outcomes, and (context, strategy) edges in Delta tables; update success probability per edge (e.g. Beta-Binomial).
- **Anti-pattern detection:** Identify top costly/failing query patterns and produce recommended rewrites or mitigations (e.g. add predicate, use smaller warehouse).
- **Outcome Logging SDK:** Simple Python API (e.g. `cortex.log_outcome(context, strategy, outcome)`) for notebooks/jobs to report success or failure explicitly.
- **Dashboard:** Databricks App (React or Streamlit) showing top anti-patterns, recommendations, and confidence with evidence links.
- **Alerting:** Webhooks (Slack/Teams/PagerDuty or similar) for critical anti-patterns or threshold breaches.
- **Agent tool (if contract available):** Endpoint callable by Mosaic AI agents to retrieve historical context and recommendations for a given query or context.

---

## 4. Non-Goals (V1)

- **Pre-execution enforcement:** No "block query before it runs" in the SQL editor without an editor plugin; v1 is post-execution analysis and proactive alerts.
- **Fully autonomous remediation:** No automatic query rewrite or pipeline change; all interventions are advisory or human-approved.
- **Cross-workspace global learning:** Learning and data are scoped to a single workspace (or explicitly defined multi-workspace design).
- **OS / IDE / CI telemetry:** No hooks into OS, IDE, or CI outside Databricks in v1.

---

## 5. Functional Requirements

| ID | Requirement | Priority | Description |
|----|-------------|----------|-------------|
| FR-01 | Unity Catalog integration | P0 | All CortexDBx state (signals, contexts, strategies, outcomes, recommendations) stored in UC; governance and lineage via UC. |
| FR-02 | Outcome Logging API | P0 | Python SDK (e.g. `cortex.log_outcome(...)`) for explicit success/failure logging from notebooks or jobs. |
| FR-03 | Signal ingestion from system tables | P0 | Job(s) that read query history (and optionally DLT events) and write to Cortex Delta tables. |
| FR-04 | Outcome Graph (Delta) | P0 | Tables for contexts, strategies, outcomes, context_strategy_edges; calibration updates success probability per edge. |
| FR-05 | Dashboard (Databricks App) | P1 | App showing top anti-patterns, costly/failing patterns, recommendations with confidence and evidence. |
| FR-06 | Alert webhooks | P1 | Configurable webhooks for critical anti-patterns or cost/failure thresholds. |
| FR-07 | Mosaic AI Agent skill / tool | P1 | Tool or endpoint that agents can call (e.g. `get_historical_context(query)`) returning recommendations; depends on Genie/agent extension points. |
| FR-08 | Feedback loop | P2 | UI or API for users to thumbs-up/thumbs-down a recommendation; updates feedback table and can influence calibration. |

---

## 6. Non-Functional Requirements

| ID | Area | Requirement |
|----|------|-------------|
| NFR-01 | Latency | Per-surface SLOs only: dashboard load within 2–5 s; agent tool P95 as documented (e.g. 500ms–2s when cached). No single "200ms" promise for all paths. |
| NFR-02 | Scalability | Outcome Graph in Delta; design for 10M+ outcome rows via partitioning and compaction; no SQLite/JSONL as primary store at scale. |
| NFR-03 | Privacy / visibility | Recommendations and evidence respect UC and row-level visibility; users see only patterns they are allowed to see; aggregation (e.g. k-min) where needed. |
| NFR-04 | Cost | Cortex overhead (jobs, storage, app, optional serving) target &lt; 5% of customer Databricks compute spend; monitor and document. |
| NFR-05 | Audit | Writes to outcome/recommendation tables and reads of recommendations logged; retention and format per security spec. |

---

## 7. Success Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Adoption | % of active Databricks users in scope who use Cortex (dashboard or SDK) at least weekly | Track by workspace. |
| Outcome accuracy | Among recommendations with confidence &gt; 85%, % that lead to success (or user confirm) | Calibration quality. |
| Cost savings | $ or % reduction in avoidable query cost (e.g. prevented full scans, OOMs) | Estimate from prevented failures and rewrites. |
| Failure reduction | Fewer repeated failures for same/similar patterns; MTTR reduction for incidents tied to known patterns | Compare before/after Cortex. |
| Calibration | Brier score, precision-at-high-confidence | Improve over time. |

---

## 8. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Cold start | High | Medium | Start with system-table ingestion only; document "first 1–2 weeks low value" and use synthetic or historical replay for demos. |
| Privacy / leakage | Medium | High | Strict UC and row-level filtering; aggregate before showing patterns where needed; security review. |
| False positives (noisy alerts) | High | Medium | Confidence thresholds and k-min evidence; allow users to dismiss and feedback; tune thresholds. |
| Compute cost of Cortex | Medium | Medium | Batch ingestion; limit real-time path; target &lt; 5% overhead; cost alerts. |
| Genie/agent API unavailable or limited | Medium | Low | Agent tool is P1; ship dashboard and webhooks first; add agent integration when contract is clear. |

---

## 9. Milestones (4–6 Week Increments)

| Milestone | Scope | Outcome |
|-----------|--------|---------|
| M1 | Observer + Delta schema + Outcome Logging SDK | Raw signals and outcomes writable; minimal graph (contexts, strategies, outcomes, edges). |
| M2 | Calibration job + anti-pattern detection | Success probability per (context, strategy); top N costly/failing patterns and recommended strategies. |
| M3 | Dashboard (Databricks App) | Users can view top anti-patterns, recommendations, and evidence. |
| M4 | Alerts + optional agent tool | Webhooks for critical patterns; agent tool if API available. |
| M5 | Feedback loop + calibration metrics | Thumbs up/down and Brier/precision tracking; iterate on thresholds. |

---

## 10. Approvals

- [ ] Product Management  
- [ ] Engineering Lead  
- [ ] Security / Compliance  

---

## References

- [CortexDBx Technical Paper](TECHNICAL_PAPER.md)
- [CortexDBx Audit](AUDIT.md)
- [Architecture and Data Model](spec/ARCHITECTURE_AND_DATA_MODEL.md)
- [Interfaces and Integrations](spec/INTERFACES.md)
- [Security and Governance](spec/SECURITY_GOVERNANCE.md)
