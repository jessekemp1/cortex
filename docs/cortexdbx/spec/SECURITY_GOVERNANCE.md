# CortexDBx: Security and Governance (Spec Starter)

**Purpose:** Spec starter for UC integration, visibility, audit, and safety. Expand with exact permissions and retention.

---

## 1. Unity Catalog Integration

- **Location:** All CortexDBx tables live in a single UC catalog/schema (e.g. `cortex_<catalog>.<schema>`).
- **Ownership:** Schema and tables owned by a principal that runs Cortex jobs (e.g. service principal or group). App and optional serving endpoint use a read-only principal (or read + write only to `feedback` if applicable).
- **Permissions:** Standard UC grants; no cross-catalog access required for v1 unless Cortex aggregates from other catalogs (then minimal read-only to those objects). Jobs need read on System Tables and DLT events per Databricks docs; read/write on Cortex schema.

---

## 2. Visibility and Row-Level Filtering

- **Principle:** Callers (dashboard user, agent, webhook recipient) must only see recommendations and evidence they are allowed to see.
- **Implementation (starter):** (1) All queries from dashboard and agent tool run as the caller identity (or a dedicated Cortex app identity with no extra privileges). (2) Filter recommendation and outcome rows by visibility: e.g. only show patterns where the caller has SELECT on the underlying tables referenced in evidence, or (3) aggregate so that no single query_id or PII is exposed (e.g. show only query shape and counts with k-min aggregation). Exact policy TBD (e.g. by table ACL, by tag, or by explicit Cortex "visibility" column).
- **Sensitive data:** Do not log full query text in recommendations if it contains PII; use fingerprint or redacted form. Document redaction rules.

---

## 3. Audit

- **Scope:** Log (1) writes to Cortex tables (outcomes, recommendations, feedback) and (2) reads of recommendations (by user/surface) where applicable.
- **Format:** Use Delta table with columns such as: timestamp, principal, action (insert/update/read), table, resource_id (e.g. outcome_id, recommendation_id). Retention TBD (e.g. 90 days); store in same or dedicated audit schema.
- **Access:** Audit table readable only by admins or compliance; not by general app users.

---

## 4. Human-in-the-Loop and Safety

- **V1 policy:** No fully automated "block" or "change" of user queries or pipelines. All interventions are advisory: dashboard, alerts, and agent suggestions. If automated remediation is added later, require explicit opt-in and human approval for high-impact actions.
- **High-impact definition (starter):** Any action that modifies production data or cancels/rewrites a running job. Document and refine with product/security.

---

## 5. Tenant and Workspace Scope

- **V1:** Single-workspace scope. Cortex data and learning are isolated to the workspace where Cortex is deployed. No cross-workspace sharing unless explicitly designed (e.g. read-only replica for reporting).
- **Multi-workspace:** If required later, define data isolation and aggregation rules explicitly.

---

## 6. Next Steps for Full Spec

- [ ] Exact UC grants per job identity, app identity, and serving endpoint.
- [ ] Row-level filtering implementation (views, dynamic filters, or UC row filters).
- [ ] Audit table DDL and retention policy.
- [ ] Redaction and k-min aggregation rules for recommendations and evidence.
