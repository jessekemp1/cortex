# Pupil Safe Modeling Standard

**Product**: Pupil (built on SynthFinServ trust layer)  
**Version**: 1.0  
**Status**: Required for all Pupil releases  
**Owner**: Cortex Product and Engineering  
**Last Updated**: 2026-02-07

---

## 1. Purpose

This standard defines mandatory safety, privacy, legal, and governance constraints for Pupil.
Pupil simulates synthetic agents and behavioral event trails. It must never be built from real people or identifiable personal traces.

This document is not guidance. It is a release gate.

---

## 2. Non-Negotiable Rules

1. **No person-level social media ingestion**
   - No scraping of Instagram, Facebook, TikTok, X, LinkedIn, Reddit, or similar platforms at account level.
   - No ingestion of user handles, profile text, posts, comments, media, friend graphs, or inferred identity clusters.

2. **No unauthorized personal data use**
   - No use of private datasets without explicit legal basis and documented consent.
   - No repurposing personal data beyond original allowed use.

3. **No identity reconstruction**
   - No persistent person-level identifiers in training, simulation, output, or logs.
   - No linkage keys that allow mapping synthetic agents to real individuals.

4. **Only aggregate or consented inputs**
   - Allowed data classes:
     - Public aggregate statistics
     - Licensed aggregate panels
     - Consented first-party telemetry aggregated to cohorts
     - Regulatory and macroeconomic public datasets

5. **Minimum cohort protection**
   - Any cohort-based feature must satisfy minimum cohort size thresholds.
   - Sparse cohort cells must be suppressed or merged.

---

## 3. Allowed vs Prohibited Data Inputs

### 3.1 Allowed Inputs

- Census and labor statistics (national/provincial/state/regional aggregate)
- Public economic indicators (rates, inflation, unemployment, housing, retail indices)
- Public survey summaries and benchmark tables
- Aggregate trend features from media/social platforms (region-time topic index, region-time sentiment index)
- Institution-internal consented telemetry aggregated by cohort and time bucket

### 3.2 Prohibited Inputs

- User-level social media data, including "public profile" records
- Individual browsing or app activity tied to a person
- PII or quasi-identifiers used for person-level modeling
- Raw person-level data acquired through scraping or unauthorized export
- Any dataset that requires violation of platform terms

---

## 4. Privacy and Governance Controls

### 4.1 Required Controls

- Data provenance manifest for every source
- Legal basis and license check for each source
- Cohort-level aggregation enforcement before modeling
- k-anonymity style minimum cell size checks
- Sparse-cell suppression and generalization rules
- Export controls with policy checks

### 4.2 Required Privacy Evaluation

Every production candidate release must pass:

- DCR threshold checks
- NNDR threshold checks
- MIA threshold checks
- Re-identification risk review for output schemas

If any check fails, release is blocked.

---

## 5. Modeling Guardrails

1. **Population-first modeling**
   - Generate synthetic personas from statistical distributions and constraints.
   - Never initialize agents from observed individuals.

2. **Behavior modeling from aggregate signals**
   - Learn transition probabilities from aggregate outcomes.
   - Use latent factors for behavior calibration.

3. **Uncertainty is mandatory**
   - Each forecast output must include uncertainty intervals.
   - Calibration quality must be reported alongside point estimates.

4. **No unverifiable claims**
   - Do not claim "real-world predictive accuracy" without held-out real aggregate validation.
   - Do not claim "privacy guarantee" without passing defined privacy metrics.

---

## 6. Release Gate Checklist

All boxes must be true:

- [ ] No prohibited inputs detected by provenance audit
- [ ] All sources have legal and license approval
- [ ] Cohort aggregation and sparse-cell suppression verified
- [ ] DCR, NNDR, and MIA checks passed
- [ ] Distribution fidelity checks passed
- [ ] Temporal coherence checks passed
- [ ] Forecast uncertainty and calibration report generated
- [ ] Policy attestation signed by technical owner

---

## 7. Enforcement

- Violations of Section 2 block deployment.
- Violations are treated as product integrity incidents.
- Emergency overrides require explicit written approval by engineering and product owners and must include postmortem documentation.

---

## 8. Scope

This standard applies to:

- Data ingestion
- Feature generation
- Agent initialization
- Simulation runtime
- Output exports
- API endpoints
- Observability and logs

Any new Pupil module must reference this standard before merge.
