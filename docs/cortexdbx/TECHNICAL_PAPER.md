# CortexDBx: The Intelligence Layer for the Databricks Data Intelligence Platform

**Technical Paper**

**Author:** Jesse Kemp  
**Date:** 2026-01-29  
**Version:** 1.0  
**Status:** Draft  

---

## Abstract

The Databricks Data Intelligence Platform excels at processing data (Lakehouse) and executing AI workloads (Mosaic AI) but does not natively persist **outcome-based learning**. Operational history—which queries failed, which strategies reduced cost, which pipeline changes fixed failures—is not systematically captured or reused. CortexDBx adds an outcome learning loop on top of Databricks: it ingests signals from system tables and pipelines, maps them to a typed Outcome Graph stored in Delta tables, calibrates strategy success probabilities, and surfaces recommendations through dashboards, alerts, and agent tools. This paper defines the system model, a Databricks-first architecture, a minimum-viable data model, learning and calibration mechanics, governance and safety, performance expectations, deployment layout, and limitations. V1 is scoped to **query cost and failure guardrails**; pipeline reliability and optional IDE/CI collectors follow in later phases.

---

## 1. Problem

Enterprises running on Databricks face an **amnesiac system**:

1. **Stateless AI:** Mosaic AI agents reset context between sessions. They do not remember that a given SQL pattern led to OOM or high cost last week.
2. **Institutional memory loss:** When experienced engineers leave, knowledge of what breaks pipelines and what fixes them is lost.
3. **Reactive analytics:** Dashboards and system tables show what already happened. They do not warn that a query or pipeline is likely to fail or overspend based on historical patterns.

The gap is not compute or data storage but **persistent operational memory**: a structured record of context, strategy, and outcome that compounds over time and drives proactive, calibrated recommendations.

---

## 2. Thesis

**Operational wisdom is a compound asset.** Value comes from optimizing for *probability of success* (and cost/failure avoidance) using historical outcomes, not from generating more tokens or more dashboards. CortexDBx implements this by:

- Treating every observable execution as a **signal** that can be linked to a **context** and a **strategy**.
- Storing **outcomes** (success / failure / partial) and updating **confidence** per (context, strategy) via Bayesian calibration.
- Delivering **interventions** through defined surfaces (dashboard, webhooks, agent tool) with human-in-the-loop gates for high-impact actions.

The system gets better with use: more outcomes improve calibration and recommendation quality.

---

## 3. System Model

High-level flow:

```
Signals -> Context fingerprints -> Strategy candidates -> Outcome logging
    -> Bayesian calibration -> Interventions
```

- **Signals:** Raw events from System Tables (e.g. query history), DLT events, model gateway logs (where available), and explicit SDK logging.
- **Context fingerprint:** A deterministic or structured key summarizing the situation (e.g. query shape, tables, warehouse, user) so similar situations map to the same or related contexts.
- **Strategy:** An actionable recommendation or pattern (e.g. "add date predicate," "use smaller warehouse," "retry with different config").
- **Outcome logging:** Each execution (or user feedback) produces an outcome record linked to context and strategy, with evidence (query_id, job_run_id, etc.).
- **Bayesian calibration:** Per (context, strategy), maintain a success probability (e.g. Beta-Binomial) and update it with each new outcome; support decay or time-windowing for concept drift.
- **Interventions:** Surfaces consume the calibrated graph to show warnings, recommendations, and alerts; high-impact actions require human approval in v1.

---

## 4. Architecture (Databricks-First)

CortexDBx runs entirely inside the customer Databricks environment. Three logical engines:

### 4.1 Observer (Signal Ingestion)

- **Sources (v1):**
  - **System Tables:** e.g. `system.query.history` (query text, status, cost, duration, user, warehouse).
  - **Delta Live Tables:** Pipeline run events, data quality metrics, failure reasons.
  - **Explicit SDK:** `cortex.log_outcome(context, strategy, outcome)` from notebooks/jobs for manual or scripted feedback.
- **Optional later:** Mosaic AI gateway logs, Git webhooks (V2).
- **Output:** Raw or normalized records written to Delta tables (e.g. `signals_raw` or domain-specific tables) in Unity Catalog.

### 4.2 Orientation Core (Outcome Graph)

- **Role:** Map signals to contexts and strategies; record outcomes; maintain and update confidence per (context, strategy).
- **Storage:** Delta tables in Unity Catalog (see Data Model). No SQLite/JSONL as primary store for scale; graph is a derived view or set of queries over these tables.
- **Components:**
  - **Pattern matcher / context builder:** Derive context fingerprints from signals (e.g. query fingerprint, table set, warehouse).
  - **Outcome tracker:** Persist outcome records with links to context and strategy and evidence (query_id, job_run_id, etc.).
  - **Confidence calibrator:** Update success probability per (context, strategy) using a conjugate prior (e.g. Beta-Binomial); optional decay or time-windowing.

### 4.3 Broker (Intervention Surfaces)

- **Dashboard (Databricks App):** React or Streamlit app showing top anti-patterns, costly/failing query patterns, and recommended strategies with confidence and sample evidence.
- **Alerts / webhooks:** Notify Slack/Teams/PagerDuty (or similar) for critical anti-patterns or threshold breaches.
- **Agent tool endpoint:** API or serverless function callable by Mosaic AI agents (e.g. "get historical context for this query") returning recommendations and confidence.
- **Pre-execution (future):** IDE or SQL editor plugin that can warn before running a query; out of scope for v1.

All recommendations respect governance: only expose evidence and patterns the caller is allowed to see (see Governance).

---

## 5. Data Model (Minimum Viable)

All tables live in Unity Catalog (e.g. `cortex_<catalog>.<schema>.*`). Suggested minimum set:

| Table | Purpose |
|-------|---------|
| `signals_raw` | Raw or normalized events from Observer (query history rows, DLT events, SDK logs). Partitioned by date. |
| `contexts` | Context entities: id, fingerprint/hash, attributes (e.g. query_shape, table_set, warehouse_id), first/last seen. |
| `strategies` | Strategy entities: id, name, description, category (e.g. rewrite, warehouse_change). |
| `outcomes` | Outcome events: id, context_id, strategy_id, result (success/failure/partial), evidence (query_id, job_run_id, etc.), actor, timestamp. |
| `context_strategy_edges` | Aggregated view or materialized stats per (context, strategy): success_count, failure_count, last_updated, optional Beta params (alpha, beta). |
| `recommendations` | Generated recommendations: id, context_id, strategy_id, confidence, surface, created_at; optional TTL. |
| `feedback` | User or system feedback on recommendations: recommendation_id, thumbs_up/down or outcome override, timestamp. |

**Evidence:** Every outcome should reference at least one of: system table row (e.g. `query_id`), `job_run_id`, DLT event id, or SDK log id. This enables lineage and audit.

**Graph view:** The "Outcome Graph" is not a separate store; it is derived from `contexts`, `strategies`, `outcomes`, and `context_strategy_edges` (and optionally `recommendations`). Queries or views can expose it for dashboard and API.

---

## 6. Learning and Calibration

- **Model:** For each (context, strategy), maintain a success probability. A simple approach is Beta-Binomial: treat each outcome as a Bernoulli trial, with conjugate prior Beta(alpha, beta). After n successes and m failures, posterior is Beta(alpha + n, beta + m); point estimate P(success) = (alpha + n) / (alpha + beta + n + m).
- **Decay / time-windowing:** To handle concept drift, either (a) apply exponential decay to older outcomes, or (b) only use outcomes in a rolling window (e.g. last 90 days). Exact policy is an implementation choice; document it in the spec.
- **Calibration metrics:** Track quality of confidence scores: e.g. **Brier score** (lower is better), **precision at high-confidence** (e.g. when system says >85% confidence, what fraction of recommendations actually succeed). Use to tune priors and decay.

---

## 7. Governance and Safety

- **Unity Catalog:** All CortexDBx tables are in UC. Use standard UC permissions; only authorized users/jobs can read/write Cortex schema. Recommendation APIs must run with a principal that has read access only to the tables the caller is allowed to see.
- **Visibility:** Recommendations and evidence must respect data boundaries. If a user must not see certain tables or query text, filter or aggregate: e.g. show only "query shape" and counts, or require k-min aggregation before showing patterns.
- **Audit:** Log writes to outcome and recommendation tables, and (where applicable) reads of recommendations by user/surface. Retention and format to be defined in security spec.
- **Human-in-the-loop:** In v1, no fully automated "block" or "change" of user queries or pipelines. Alerts and recommendations are advisory; any automated remediation (e.g. auto-retry with different params) is a later phase with explicit gates.

---

## 8. Performance and Reliability

- **Per-surface SLOs:** Do not promise a single "200ms" for all real-time recommendations. Define separate targets, e.g.:
  - **Dashboard:** Load of top N recommendations within 2–5 s (batch or cached).
  - **Agent tool:** P95 latency target (e.g. 500ms–2s) when serving from cache or precomputed edges; document cold-path behavior (e.g. first request after deploy).
  - **Webhooks:** Fire-and-forget; async delivery with retries.
- **Caching:** Cache hot (context, strategy) edges and top anti-patterns; refresh on a schedule or on new outcome batches.
- **Batch vs near-real-time:** v1 can rely on batch jobs (e.g. hourly) to ingest system tables and update the graph; near-real-time ingestion is an optimization. Document the chosen tier.

---

## 9. Deployment

- **Asset bundle:** Jobs (Observer ingestion, Orientation Core calibration), Delta tables (schema and retention), Databricks App (dashboard), and optionally a Model Serving or serverless endpoint for the agent tool. All in customer workspace.
- **Permissions:** Minimal privileges: job identity can read system tables and DLT events (as per Databricks docs), read/write Cortex schema; app and endpoint identities have read (and possibly write for feedback) as needed. No OS or out-of-workspace access in v1.

---

## 10. Limitations and Non-Goals (V1)

- **No pre-execution enforcement:** "Warn before I run a query" in the editor requires an IDE/editor plugin; not in v1. V1 is post-execution analysis, dashboard, and alerts plus agent tool.
- **No self-healing automation:** No automatic query rewrite or pipeline change without human approval in v1.
- **No OS or IDE telemetry:** No hooks into OS, IDE, or CI outside Databricks in v1; optional in V2.
- **Single-workspace scope:** Data and learning are scoped to one workspace (or explicitly defined multi-workspace design) unless otherwise specified.

---

## 11. Roadmap

- **V1:** Query cost and failure guardrails: ingest query history (and optionally DLT), build Outcome Graph in Delta, dashboard + alerts + Outcome Logging SDK; agent tool if contract available.
- **V1.5:** DLT/pipeline reliability: richer DLT signals, failure prediction, recommended fixes; still advisory.
- **V2:** Optional IDE/CI collectors; pre-execution plugin; optional self-healing with gates.

---

## References

- CortexDBx aPRD (this repo)
- CortexDBx Audit (AUDIT.md)
- Databricks System Tables, Delta Live Tables, Unity Catalog, and Databricks Apps documentation.
