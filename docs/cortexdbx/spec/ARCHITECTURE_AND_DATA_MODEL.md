# CortexDBx: Architecture and Data Model (Spec Starter)

**Purpose:** Spec starter for implementation. Expand with concrete DDL, partitioning, and job DAGs.

---

## 1. Logical Architecture

- **Observer:** Jobs (scheduled or triggered) read from Databricks System Tables and DLT events; optionally ingest SDK log payloads. Write to Delta tables in Unity Catalog.
- **Orientation Core:** Jobs (or DLT) derive context fingerprints from signals, match or create contexts and strategies, append outcomes, and update `context_strategy_edges` (e.g. Beta params or success/failure counts). Graph is derived from these tables.
- **Broker:** Databricks App (dashboard), webhook notifier, and optional serving endpoint read from the graph tables (and recommendations table) to serve UI, alerts, and agent tool responses.

Data flows one way: Signals -> raw/normalized tables -> contexts/strategies/outcomes -> edges -> recommendations (optional). No SQLite or JSONL as primary store.

---

## 2. Data Model (Minimum Viable)

**Catalog/schema:** e.g. `cortex_<catalog>.<schema>`; all tables securable via UC.

| Table | Description | Key columns (to be fully specified in DDL) |
|-------|-------------|--------------------------------------------|
| `signals_raw` | Raw or normalized events from Observer | event_type, payload (JSON or struct), source (query_id, job_run_id, etc.), timestamp; partition by date. |
| `contexts` | Context entities | context_id, fingerprint_hash, attributes (query_shape, table_set, warehouse_id, etc.), first_seen, last_seen. |
| `strategies` | Strategy entities | strategy_id, name, description, category. |
| `outcomes` | Outcome events | outcome_id, context_id, strategy_id, result (success/failure/partial), evidence (query_id, job_run_id, etc.), actor, timestamp. |
| `context_strategy_edges` | Per (context, strategy) stats | context_id, strategy_id, success_count, failure_count, alpha, beta (if Beta), last_updated. |
| `recommendations` | Generated recommendations | recommendation_id, context_id, strategy_id, confidence, surface, created_at; optional TTL. |
| `feedback` | User/system feedback on recommendations | recommendation_id, rating (thumbs_up/down or override), timestamp. |

**Evidence:** Every outcome row should reference at least one of: `query_id` (system.query), `job_run_id`, DLT event id, or SDK log id for lineage and audit.

**Graph view:** Implemented as queries or views over `contexts`, `strategies`, `outcomes`, `context_strategy_edges`; no separate graph DB in v1.

---

## 3. Job / Pipeline DAG (Starter)

- **Job 1 – Ingest:** Read `system.query.history` (and optionally DLT events); normalize and append to `signals_raw` (and any domain-specific tables). Schedule: e.g. hourly.
- **Job 2 – Context + outcomes:** From `signals_raw` (or query history directly), compute context fingerprints; upsert `contexts`; create or link `strategies`; append `outcomes` with evidence. Schedule: same as or after Ingest.
- **Job 3 – Calibration:** Recompute `context_strategy_edges` from `outcomes` (Beta-Binomial or equivalent); optional decay/window. Schedule: after Context + outcomes.
- **Job 4 – Recommendations (optional):** Generate `recommendations` from edges above a confidence threshold; optional TTL. Can be part of Calibration or separate.

---

## 4. Deployment Layout

- **Repos / notebooks:** Observer and Orientation Core jobs as Databricks Jobs (notebooks or Python tasks); config for catalog/schema and table names.
- **Delta tables:** Created in UC with retention and optional liquid clustering (e.g. by context_id, strategy_id where useful).
- **App:** Databricks App (React or Streamlit) in same workspace; reads from Cortex schema (read-only for app identity).
- **Serving (optional):** Serverless function or Model Serving endpoint for agent tool; reads from Cortex schema and optionally caches hot edges.

---

## 5. Next Steps for Full Spec

- [ ] DDL for each table (types, constraints, partitioning).
- [ ] Exact context fingerprint algorithm (e.g. hash of normalized query + table set + warehouse).
- [ ] Calibration formula (Beta prior values, decay or window policy).
- [ ] Retention and compaction policy for `signals_raw` and `outcomes`.
