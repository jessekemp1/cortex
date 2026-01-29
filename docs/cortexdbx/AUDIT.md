# CortexDBx: Audit of Source Papers

**Purpose:** Extract contradictions, missing definitions, feasibility gaps, and rewrite requirements from the six Cortex/CortexDBx source papers. Informs the Technical Paper and aPRD rewrite.

**Sources:** cortex-dbx-prd, cortex-manifesto-v3, cortex-dbx-use-cases, cortex-databricks-enterprise, cortex-architecture-v2, cortex-vs-palantir-assessment.

---

## 1. Contradictions

| Area | Source A | Source B | Resolution for rewrite |
|------|----------|----------|------------------------|
| **Platform boundary** | Manifesto: Observer hooks "OS kernel, IDE language server, CI/CD pipeline." | CortexDBx PRD: "Runs entirely within the customer's Databricks environment." | Define Databricks-only MVP; IDE/CI as V2 optional collectors. |
| **Engine naming** | Manifesto: "Observer, Orientation Core, Intervenor." | PRD / Architecture: "Absorber, Synthesis Core, Broker." | Standardize on Observer / Orientation Core / Broker in CortexDBx docs. |
| **Intervention timing** | PRD: "Warn me before I run a query that is likely to fail." | No implementation path for "before" (requires editor/plugin). | Separate pre-execution (plugin) from post-execution (system tables) interventions; v1 is post-execution + dashboard. |
| **Storage** | PRD: "Unity Catalog Volumes (for the Outcome Graph SQLite/JSONL)." | Same doc: "cortex_graph (Delta Table or Graph structure in UC Volume)." | Commit to Delta tables as source of truth; graph as derived view. |

---

## 2. Missing Definitions

| Concept | Current state | Required for rewrite |
|---------|----------------|----------------------|
| **Outcome Graph** | Referenced but no schema. | Minimum tables: signals_raw, contexts, strategies, outcomes, context_strategy_edges, recommendations, feedback. |
| **Context** | "Recurring contexts" (e.g. "High CPU + specific SQL join type") not formalized. | Context fingerprint: deterministic hash or structured key from signal attributes (query shape, table set, user/warehouse, etc.). |
| **Strategy** | "Strategy" and "Action" used interchangeably. | Strategy = actionable recommendation or pattern (e.g. "add predicate," "use smaller warehouse"); link to outcome. |
| **Confidence / P(Success)** | "Bayesian inference," "edge weight P" mentioned; no update rule. | Specify Beta-Binomial (or conjugate prior) per (context, strategy) edge; decay or time-windowing for drift. |
| **Evidence** | "Traceability" mentioned, not specified. | Evidence = reference to system table row (query_id, job_run_id), DLT event id, or SDK log id. |
| **ACL / visibility** | "Users only see patterns from data they have access to." | Design: row-level filtering via UC/securable objects; aggregation thresholds (e.g. k-min) for restricted data. |

---

## 3. Feasibility Gaps

| Claim | Issue | Rewrite action |
|-------|--------|-----------------|
| **"Real-time recommendations < 200ms"** | Unrealistic for cold cluster, model serving, and UC checks in workspace. | Define per-surface SLOs (dashboard, webhook, agent tool); allow batch/near-real-time tiers; document fallbacks. |
| **"10M+ outcome nodes without degradation"** | SQLite/JSONL in UC Volume is not suitable for this scale or concurrency. | Delta-based schema; partitioning and compaction; graph as query/view over tables. |
| **"Genie Plugin" / "Inject context into Genie responses"** | Depends on Genie extension points not specified in papers. | Describe as integration target with explicit contract (e.g. tool or context API); mark as P1/post-MVP if API unknown. |
| **"Before the query executes"** | Requires SQL editor plugin or query interception; not specified. | Non-goal for v1; document as future "pre-execution" surface. |
| **"Git provider webhooks"** | Adds external dependency and deployment complexity. | Optional V2 signal source; not in MVP. |

---

## 4. Governance and Security (Under-specified)

| Requirement | Gap | Rewrite action |
|-------------|-----|----------------|
| **Unity Catalog integration** | "Read/write all state to UC" stated; how outcomes respect table ACLs is not defined. | Specify catalog/schema ownership; which tables are securable; how recommendation visibility is filtered by user/group. |
| **Audit** | Not mentioned. | Require audit log for outcome writes and recommendation reads; retention and format. |
| **Tenant / workspace boundary** | Single-tenant per workspace assumed but not stated. | State scope: one workspace (or explicitly multi-workspace) and data isolation. |
| **High-impact interventions** | "Block/Warn" in manifesto; no safety gate. | Human-in-the-loop for any automated block or change; warn-only default for v1. |

---

## 5. Scope and Use Cases

| Issue | Detail | Rewrite action |
|-------|--------|----------------|
| **50 use cases** | Use-case doc spans many verticals; not buildable as single scope. | Pick 1-2 wedges: (1) query cost/failure guardrails, (2) DLT pipeline reliability; reference others as future expansion. |
| **Palantir comparison** | "Palantir AIP does not learn from outcomes" asserted without citation. | Phrase differentiation as "we optimize operational strategies via outcome telemetry"; avoid unverifiable competitor claims. |

---

## 6. Rewrite Requirements (Checklist for Paper and aPRD)

- [ ] Single platform boundary: Databricks-only for v1; IDE/CI optional later.
- [ ] One MVP wedge: query cost guardrails (and optionally DLT reliability).
- [ ] Concrete data model: Delta tables listed with purpose; evidence and traceability.
- [ ] Confidence: Beta-Binomial (or equivalent) with decay/time-window; calibration metrics (e.g. Brier, precision-at-high-confidence).
- [ ] Per-surface SLOs and fallbacks; no single "200ms" for all.
- [ ] Governance: UC storage, ACL-aware visibility, audit, human-in-the-loop for high-impact actions.
- [ ] Non-goals: no pre-execution enforcement in v1, no self-healing automation in v1, no OS/IDE telemetry in v1.
- [ ] Competitive positioning without unverifiable claims.
