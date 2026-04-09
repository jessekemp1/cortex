# Synthetic Echo — Go/No-Go Research Brief

**Date**: 2026-04-08
**Project**: Pupil Echo — Schema-Driven Synthetic Data for Tokenized Databricks
**Customer**: Canadian FinServ company on Databricks with column-level tokenization
**Classification**: New Feature (Pupil extension module)

---

## Executive Summary

**Verdict: GO**
**Confidence: 78%**

Pupil Echo is feasible, architecturally clean, and competitively differentiated. Schema metadata (column names, types, nullability, cardinality, FK graph, semantic tags) is sufficient to generate statistically plausible synthetic data. The primary risk is distribution parameter accuracy for continuous columns — mitigated by CalibrationOverlay and industry benchmarks.

**Scope (revised 2026-04-08)**: Platform-agnostic. Echo accepts schema as dict/JSON and outputs pandas DataFrames. Databricks-specific integration (UC writer, tiered access, notebooks) deferred to future phase — design docs preserved.

---

## Feasibility Matrix

| Task | Finding | Status | Risk |
|---|---|---|---|
| **T1: UC Metadata** | USE CATALOG + USE SCHEMA gives column names, types, nullability, FK/PK, UC tags, comments. Delta log adds nullCount. | GREEN | Low — standard UC features |
| **T2: Tokenization Survival** | Cardinality, null rate, frequency distribution, rank correlation, FK graph all survive ALL tokenization methods. Min/max and sort order destroyed. | GREEN | Low — "safe signals" are sufficient |
| **T3: Architecture** | 7-pass distribution compiler, configurable DAG, token surrogates, 5 generalizable validation layers. Clean extension of Pupil — no core modifications. | GREEN | Medium — novel architecture, untested |
| **T4: Databricks Integration** | Separate `_synthetic` catalog, Spark/Connect write paths, table property provenance, schema-change-driven regeneration. | GREEN | Low — standard Databricks patterns |
| **T5: Tiered Access** | L0-L3 mapped to UC groups/grants. OSFI B-13 + PIPEDA aligned. Metric Views for L1, k-anon row filters for L2. | GREEN | Low — requires Premium tier verification |
| **T6: Validation** | No regulator has published synthetic data validation guidance. Reference-free methods: schema conformance, internal consistency, domain review. No TSTR/discriminator without real data. | YELLOW | Medium — regulatory frontier, no precedent to cite |
| **T7: Competitive** | Only Tonic Fabricate does schema-only. All others (Gretel, Mostly AI, Hazy, SDV) require real data training. Pupil Echo differentiates on UC-native extraction + frequency exploitation + validation suite. | GREEN | Low — clear differentiation |

**Overall: 6 GREEN, 1 YELLOW**

---

## Key Architectural Decisions

1. **Token surrogates as first-class output** — Echo doesn't fake values. Categorical columns output "tok_001", "tok_002" with correct frequency distribution. Remapping to real values requires separate clear-text access.

2. **Three-tier metadata access** — Echo quality scales with metadata access:
   - Level 0 (information_schema only): ~40-60% distribution confidence
   - Level 1 (+ Delta log stats): ~60-70%
   - Level 2 (+ tokenized SELECT for frequency profiles): ~80-90%

3. **CalibrationOverlay as escape hatch** — automatic inference can't recover mean/std for continuous columns. Customers provide industry benchmarks or aggregate reports to refine priors. This is honest about limits while being useful out of the box.

4. **Compile-then-execute** — GenerationPlan is a serializable, auditable artifact. Customers review and patch before generation runs.

5. **No simulation layer** — Echo generates static snapshots. Temporal data modeled as separate tables with date columns and FK relationships.

---

## Competitive Position

| Capability | Pupil Echo | Tonic Fabricate | Gretel/Mostly AI | dbldatagen |
|---|---|---|---|---|
| Schema-only (no real data) | YES | YES | NO | YES |
| UC-native metadata extraction | YES | NO (upload) | NO | YES |
| Frequency distribution exploitation | YES | NO | N/A | NO |
| Multi-table FK integrity | YES | YES | YES | YES |
| Statistical validation suite | 5-layer | Human review | Built-in | Schema only |
| Canadian FinServ calibration | YES (Pupil heritage) | NO | NO | NO |
| Regulatory alignment docs | OSFI B-13, PIPEDA | General | General | None |

**Moat**: UC-native + frequency exploitation + CalibrationOverlay + Canadian FinServ heritage from Pupil.

---

## Validation Strategy (Reference-Free)

Since Echo never touches real data, traditional validation (TSTR, discriminator) requires reference data the user may not have. The recommended stack:

1. **L1 — Schema Conformance**: Types, ranges, nullability, completeness (always available)
2. **L3 — Internal Consistency**: Cross-column correlations match FK graph expectations (always available)
3. **L4 — Risk / Impossibility**: Customer-configurable rules for impossible combinations (always available)
4. **L7 — Privacy**: DCR/NNDR/MIA pass by construction — formal proof artifact (always available)
5. **L5 — Discriminator**: XGBoost synthetic vs reference — ONLY when reference data provided (L1+ tiered access)

**Gap**: No published regulator precedent for accepting schema-only synthetic data. Recommend proactive engagement with customer's compliance team to establish acceptance criteria before building.

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Continuous column distributions too far from reality | Medium | Medium | CalibrationOverlay + industry benchmarks + progressive access levels |
| Customer uses column masking (RETURN NULL) that destroys cardinality | Low | High | Detect mask function type in UC metadata, flag to user |
| Databricks tier lacks Metric Views / row filters (Standard tier) | Low | Medium | Fall back to pre-aggregated Delta tables + explicit GRANT |
| Regulator questions synthetic data validity | Medium | High | Layer schema conformance + domain review + formal privacy proof |
| Tonic Fabricate adds UC-native extraction | Medium | Low | Echo's frequency exploitation + validation suite + Canadian calibration are durable differentiators |

---

## Recommended Pilot Scope

**Target**: 3-5 tables in one schema (e.g., `customers`, `accounts`, `transactions`, `products`, `regions`)
**Team**: Customer's data science team (L0 synthetic users)
**Deliverable**: EchoPipeline generates synthetic mirror, downstream notebook runs identically on synthetic vs production
**Duration**: 2-week sprint for Phase 1 (core MVP) + 1 week for validation + integration
**Success metric**: Data science team can build and test a feature pipeline end-to-end using only synthetic data

---

## Go/No-Go Recommendation

**GO** — with the following conditions:
1. Verify customer's Databricks tier supports Metric Views and row filter UDFs (Premium required for L1+L2)
2. Engage customer compliance team early on validation acceptance criteria
3. Ship Phase 1 (core MVP) first to validate the type→distribution mapping against their actual schema
4. CalibrationOverlay is required for production use — automatic inference alone is ~60-70% confidence

[Conf: 78% | Assumption: Customer uses deterministic tokenization (FPE or vault), preserving cardinality and FK integrity | Flips if: Random non-deterministic tokenization destroys FK joins AND customer refuses Delta log access AND no calibration data provided | 6mo: Pupil Echo as productizable module; CalibrationOverlay library grows per-industry]
