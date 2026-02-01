# CortexDBx: Interfaces and Integrations (Spec Starter)

**Purpose:** Spec starter for Observer inputs, Broker outputs, and external integrations. Expand with exact APIs, payloads, and auth.

---

## 1. Observer Inputs (Signal Sources)

| Source | Type | Format / Access | v1 |
|-------|------|-----------------|-----|
| System Tables (e.g. `system.query.history`) | Databricks System Table | SQL from job; columns: query_id, query_text, status, cost, duration, user, warehouse, etc. | Yes |
| Delta Live Tables events | DLT event log / system tables | Pipeline run id, status, failure reason, data quality metrics. | Optional |
| Outcome Logging SDK | Python API from notebook/job | `cortex.log_outcome(context, strategy, outcome)`; payload written to Cortex Delta (e.g. signals_raw or outcomes). | Yes |
| Mosaic AI Gateway logs | Logs / API (if available) | Agent interactions, feedback; TBD by Databricks. | No (V2) |
| Git webhooks | External | Code change events; TBD. | No (V2) |

**Contract for SDK:** To be specified: `log_outcome(context: dict | str, strategy: str | dict, outcome: str, evidence: dict | None)`. Context and strategy can be resolved to existing context_id/strategy_id or create new; outcome is success/failure/partial.

---

## 2. Broker Outputs (Intervention Surfaces)

| Surface | Type | Consumer | v1 |
|---------|------|----------|-----|
| Dashboard (Databricks App) | React or Streamlit | User in browser; reads Cortex schema (read-only). | Yes |
| Webhooks | HTTP POST to customer URL | Slack/Teams/PagerDuty or custom; payload: e.g. anti-pattern summary, top recommendations, link to dashboard. | Yes |
| Agent tool | HTTP or serverless call | Mosaic AI agent; input: e.g. query text or context fingerprint; output: list of recommendations with confidence and evidence. | If API available |
| IDE / SQL editor plugin | Extension (future) | Pre-execution warning; out of scope for v1. | No |

**Dashboard contract:** App loads top N anti-patterns, top costly/failing patterns, and recommended strategies with confidence and sample evidence (query_id, job_run_id). Filtering by user/warehouse/date; respect UC visibility.

**Webhook payload (starter):** `{ "event": "critical_anti_pattern", "pattern_summary": "...", "recommendations": [...], "dashboard_url": "..." }`. Exact schema TBD.

**Agent tool contract (starter):** Request: `{ "query_text"?: string, "context_fingerprint"?: string }`. Response: `{ "recommendations": [ { "strategy_id", "confidence", "evidence_summary" } ] }`. Auth and exact schema TBD when Genie/agent extension points are known.

---

## 3. External Dependencies

- **Databricks workspace:** System Tables, UC, Jobs, App, optional Model Serving / serverless.
- **Customer webhook URLs:** Configured per workspace (e.g. in Cortex config or secret); no outbound auth in v1 beyond URL.
- **Mosaic AI / Genie:** Agent tool depends on extension points; document when available.

---

## 4. Next Steps for Full Spec

- [ ] SDK Python API signature and default catalog/schema.
- [ ] Dashboard API (if backend API is used) or direct SQL from app.
- [ ] Webhook payload schema and retry policy.
- [ ] Agent tool OpenAPI or equivalent when contract is fixed.
