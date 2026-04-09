# Research Prompt: Synthetic Echo — Schema-Driven Synthetic Data for Tokenized Databricks Environments

**Origin**: Field observation — Canadian FinServ customer on Databricks
**Cortex Project**: Pupil (synthetic population engine)
**Priority**: HIGH — direct product-market signal
**Date**: 2026-04-08

---

## Problem Statement

A Canadian financial services company runs Databricks with full column-level tokenization in production. This is correct security posture — PII, account numbers, transaction details are all tokenized, Unity Catalog enforces access controls, and compliance is satisfied.

**But tokenization creates a usability wall.** Developers, analysts, and data scientists cannot:
- Build or test new pipelines against realistic data (tokenized values destroy statistical properties)
- Prototype ML features (correlations between tokenized columns are meaningless)
- Validate business logic (can't tell if a join produces sensible results when both sides are tokens)
- Demo or prove value to stakeholders (dashboards of hashed strings don't tell a story)

The current workarounds are bad:
- Requesting access escalation to clear-text data (defeats the security model)
- Manually crafting test fixtures (doesn't scale, doesn't reflect real distributions)
- Using production snapshots with partial masking (leaks structure, violates policy)

## Core Research Question

**Can we generate "synthetic echo" datasets that preserve the statistical shape, correlations, and business logic of tokenized production data — using only the schema metadata and aggregate statistics that are visible *without* de-tokenizing?**

This is NOT traditional synthetic data generation (which typically requires access to the real data to learn distributions). This is **schema-first, metadata-driven generation** where the generator never sees clear-text values.

## What Pupil Already Solves

Pupil's architecture is a proof-of-concept for this exact approach:

1. **Schema-driven generation**: 98-variable Bayesian network generates from schema + published aggregate statistics — never from person-level data
2. **Cross-variable correlation preservation**: 15-layer conditional sampling ensures education-income, age-career, credit-income correlations are realistic
3. **10-layer validation**: Fidelity (chi-squared vs reference), discriminator (XGBoost AUC 0.52), privacy (DCR, NNDR, MIA), TSTR (train-synthetic-test-real)
4. **Canadian FinServ calibration**: Already tuned to StatsCan Census 2021, LFS, SHS — the same regulatory and demographic context
5. **Behavioral trails**: 50 events/agent/day with Canadian brands, CAD amounts — realistic transactional patterns

## Research Tasks (Delegate via Conductor)

### Task 1: Schema Inference from Tokenized Metadata (Sonnet)
**Question**: What metadata is available in a Databricks Unity Catalog environment WITHOUT access to clear-text data?
- Column names, data types, nullability, primary/foreign keys
- Table-level statistics (row counts, column cardinality, null rates)
- Unity Catalog tags, classifications, lineage metadata
- Information schema views available at each privilege level
- Delta Lake transaction log metadata (schema evolution, partition stats)

**Output**: Catalog of available metadata signals ranked by usefulness for synthetic generation.

### Task 2: Tokenization-Aware Distribution Recovery (Sonnet)
**Question**: What statistical properties survive tokenization, and which must be inferred?
- Format-preserving encryption (FPE) vs. random tokenization — what leaks?
- Cardinality preservation: if a tokenized column has 47 distinct values, the real column has ~47
- Null patterns: tokenization preserves null/not-null — this is a correlation signal
- Join topology: foreign key relationships are preserved (tokenized FK still joins)
- Temporal ordering: if tokenization is deterministic, sort order is preserved
- Column-level statistics in Delta Lake: min/max (useless if tokenized), count, null_count, distinct_count (useful)

**Output**: Matrix of {tokenization method} × {statistical property} → {preserved / destroyed / partially recoverable}

### Task 3: Pupil Adaptation Architecture (Opus — planning only)
**Question**: How should Pupil be extended to accept an arbitrary customer schema (not just the hardcoded 98-variable Canadian population schema)?
- Schema ingestion: parse Unity Catalog metadata → infer variable types, ranges, relationships
- Distribution priors: map column semantics to known distributions (income → lognormal, age → bounded normal, category → multinomial)
- Correlation graph: infer from foreign keys, co-occurrence patterns, domain knowledge
- Calibration sources: customer-provided aggregate reports, industry benchmarks, public regulatory filings
- Generation: adapt the 15-layer Bayesian network to arbitrary DAG structure
- Validation: which of the 10 layers generalize? (L1 quality, L4 risk, L5 discriminator, L7 privacy all generalize; L2 fidelity needs customer-specific reference)

**Output**: Architecture spec for "Pupil Schema Adapter" — the module that bridges customer metadata → Pupil generation pipeline.

### Task 4: Databricks Integration Design (Sonnet)
**Question**: How does synthetic echo data get delivered back into the Databricks environment?
- Unity Catalog synthetic schema: `catalog.synthetic.*` mirroring `catalog.production.*`
- Access controls: synthetic data available at lower privilege tier than production
- Freshness: how often does the echo need to regenerate? (schema changes, new tables, distribution drift)
- Delta Lake format: write synthetic data as Delta tables for native Spark consumption
- Lineage: tag synthetic tables with provenance (generation method, calibration sources, validation scores)
- Notebooks: template notebooks that demonstrate synthetic ↔ production swap

**Output**: Integration architecture for Databricks deployment.

### Task 5: Tiered Access Model — "Levels of Clear" (Sonnet)
**Question**: How do users graduate from synthetic → partially clear → fully clear data?
- **Level 0 — Synthetic Echo**: Fully synthetic, statistically faithful, zero privacy risk. Available to all authenticated users. Use case: prototyping, testing, demos.
- **Level 1 — Synthetic + Real Aggregates**: Synthetic records, but aggregate statistics (means, distributions, counts) from real data overlaid as reference. Use case: validation, calibration.
- **Level 2 — Anonymized Sample**: Real data with k-anonymity / differential privacy applied. Requires data steward approval. Use case: model training, feature engineering.
- **Level 3 — Clear Text**: Full production data. Requires compliance approval + audit logging. Use case: production deployment, regulatory reporting.
- Map each level to Unity Catalog row/column access policies
- Define the "proof of value" gate: what must a user demonstrate at Level N to unlock Level N+1?

**Output**: Tiered access framework with Unity Catalog policy templates.

### Task 6: Validation & Trust — Proving the Echo is Faithful (Haiku — literature scan)
**Question**: What published methods exist for validating synthetic data quality WITHOUT access to the original data?
- TSTR (Train-Synthetic-Test-Real) — but requires real test set
- Discriminator tests — requires real sample
- Can we validate against published benchmarks only? (Pupil's approach)
- Differential privacy guarantees as formal proof
- Industry precedent: banking regulators accepting synthetic data for stress testing (OSFI, OCC, EBA)

**Output**: Validation strategy that works within the tokenization constraint.

### Task 7: Competitive Landscape (Haiku — web scan)
**Question**: Who else is solving this? What's the state of the art?
- Gretel.ai, Mostly AI, Hazy, Tonic.ai, Synthesized — do any work from schema-only?
- Databricks-native solutions (Databricks Labs synthetic data generators)
- Academic: schema-driven generation, metadata-only synthesis
- Pricing models for synthetic data platforms in enterprise Databricks deployments

**Output**: Competitive matrix with Pupil's differentiation highlighted.

## Delegation Plan (Cost-Optimized)

| Task | Model | Reason | Est. Tokens |
|------|-------|--------|-------------|
| T1: Schema Inference | Sonnet | Structured technical research | ~8K |
| T2: Tokenization Properties | Sonnet | Requires reasoning about crypto properties | ~10K |
| T3: Pupil Architecture | Opus | Novel architecture design, core IP | ~15K |
| T4: Databricks Integration | Sonnet | Technical integration, well-defined space | ~8K |
| T5: Tiered Access Model | Sonnet | Policy design with clear precedent | ~8K |
| T6: Validation Methods | Haiku | Literature scan, low reasoning load | ~5K |
| T7: Competitive Landscape | Haiku | Web search + summarization | ~5K |
| **Total** | | | **~59K tokens** |

**Batch candidates (overnight, 50% discount)**: T6, T7 (non-blocking, research-only)
**Interactive (need results to inform T3)**: T1, T2
**Depends on T1+T2**: T3, T4, T5

## Success Criteria

1. A customer with tokenized Databricks tables can generate a synthetic echo dataset using ONLY Unity Catalog metadata — no clear-text access required
2. The synthetic echo passes at least 7/10 of Pupil's validation layers (L1, L3, L4, L5, L7 are mandatory)
3. The tiered access model maps cleanly to Unity Catalog policies
4. Total generation time < 5 minutes for a 100-table schema with 1M synthetic rows
5. At least one Canadian banking regulator (OSFI) has precedent for accepting synthetic data in comparable contexts

## Deliverable

**Research brief** (Cortex format) with:
- Architecture diagram: Customer Databricks → Schema Extractor → Pupil Adapter → Synthetic Echo → Unity Catalog
- Feasibility assessment per task (green/yellow/red)
- Recommended pilot scope (which tables, which customer team, what timeline)
- Go/no-go recommendation with confidence interval

---

*This prompt was refined from a field observation. The original insight: tokenization solves security but kills usability. Pupil's schema-first approach — generating from metadata and aggregate statistics, never from person-level data — is architecturally aligned with the constraint. The research question is whether this generalizes from Pupil's hardcoded Canadian FinServ schema to arbitrary customer schemas.*
