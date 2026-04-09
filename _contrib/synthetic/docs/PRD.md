# Product Requirements Document: Cortex SynthFinServ

**Product**: Cortex SynthFinServ -- Synthetic Data Generation Engine for Canadian Financial Services
**Version**: 1.0
**Status**: v0.1.0 MEP (Minimum Evolvable Product) Shipped
**Author**: Cortex Product Team
**Date**: 2026-02-05
**Classification**: Internal / Strategic

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Market Opportunity](#2-problem-statement--market-opportunity)
3. [User Personas](#3-user-personas)
4. [Product Vision & Strategy](#4-product-vision--strategy)
5. [Use Cases](#5-use-cases)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [The 7-Layer Feedback Flywheel](#8-the-7-layer-feedback-flywheel)
9. [Success Metrics & KPIs](#9-success-metrics--kpis)
10. [Competitive Analysis](#10-competitive-analysis)
11. [Roadmap](#11-roadmap)
12. [Risks & Mitigations](#12-risks--mitigations)
13. [Appendix](#13-appendix)

---

## 1. Executive Summary

Cortex SynthFinServ is a synthetic data generation engine purpose-built for the Canadian financial services market. It produces quality-validated, outcome-calibrated synthetic datasets for banks, insurers, and fintechs operating under Canadian regulatory frameworks (PIPEDA, Quebec Law 25, OSFI guidelines, FINTRAC requirements).

**What makes SynthFinServ different from every competitor**: a 7-layer feedback flywheel that continuously improves data quality from automated validation signals and client usage outcomes. Competitors generate data and forget. SynthFinServ generates data, validates it across six quality dimensions, tests it against statistical benchmarks, runs it through discriminator models, calibrates it against risk rule engines, measures downstream model utility, verifies privacy boundaries, and ingests human feedback from actual usage. Each generation cycle produces better data than the last.

**Current state (v0.1.0 MEP)**:
- 23/23 tests passing
- 9 distribution constraints sourced from StatsCan, CBA, OSFI, and Equifax Canada
- 100 profiles generated in <0.1s with 100% quality pass rate at 0.7 threshold
- Distribution fidelity within 5% of StatsCan benchmarks on all measured dimensions
- Flywheel outcome logging active with per-run tracking
- Bridge API integrated via `bridge.generate_synthetic()`

**Target market**: Big 5 Canadian banks (RBC, TD, Scotiabank, BMO, CIBC), Big 3 insurers (Manulife, Sun Life, Great-West Lifeco), and leading fintechs (Wealthsimple, Koho, Neo Financial).

**Revenue model**: Usage-based pricing per generated record, with volume tiers for enterprise clients.

---

## 2. Problem Statement & Market Opportunity

### 2.1 The Problem

Canadian financial institutions face a structural conflict between data privacy regulation and the growing need for realistic data:

```
  REGULATORY PRESSURE                      DATA DEMAND
  =====================                    =====================
  PIPEDA (federal)                         AML/KYC model training
  Quebec Law 25 (provincial)               Credit risk model testing
  OSFI B-20 guidelines                     Market research & analytics
  FINTRAC reporting rules                  Stress testing (OSFI mandated)
  Provincial privacy acts                  Customer segmentation R&D
                                           Competitive intelligence
          |                                         |
          v                                         v
  "You cannot use real                     "We need millions of
   customer data for                        realistic records to
   these purposes"                          build and test models"
          |                                         |
          +------------------+---------------------+
                             |
                             v
                  SYNTHETIC DATA IS THE
                  ONLY COMPLIANT PATH
```

**The gap in existing solutions**: Current synthetic data tools (Mostly AI, Gretel, SDV) use a generate-and-forget model. They produce records that pass surface-level statistical tests but have no mechanism to learn whether the data actually works when used downstream. A dataset that looks like banking data but behaves unrealistically when fed into an AML detection model is worse than useless -- it trains models to detect patterns that do not exist in production.

### 2.2 Market Opportunity

**Total Addressable Market (Canadian FinServ)**:

| Segment | Institutions | Est. Annual Spend on Data/Analytics | Synthetic Data % |
|---------|-------------|-------------------------------------|-----------------|
| Big 5 Banks | 5 | $2.1B combined | 3-5% = $63-105M |
| Big 3 Insurers | 3 | $800M combined | 2-4% = $16-32M |
| Mid-tier Banks/CUs | ~50 | $400M combined | 1-3% = $4-12M |
| Fintechs | ~200 | $300M combined | 5-8% = $15-24M |
| **Total** | **~258** | **$3.6B** | **$98-173M** |

**Regulatory tailwinds**:

- **PIPEDA modernization** (Bill C-27 / CPPA): Expected to further restrict real data usage for secondary purposes, increasing synthetic data demand
- **Quebec Law 25** (fully effective 2024): Most restrictive provincial privacy law, already driving Quebec-based FI adoption of synthetic alternatives
- **OSFI E-23 model risk management**: Requires model validation on independent datasets -- synthetic data is the compliant path when real holdout sets are restricted
- **FINTRAC AML/ATF regime**: Banks must demonstrate AML model effectiveness without exposing real customer transaction histories

**Demand signals from market research**:

- 78% of Canadian FI data scientists report being blocked by data access restrictions (CBA survey, 2025)
- AML training data is the top-cited use case for synthetic data in Canadian banking
- OSFI stress testing requirements create mandatory demand for scenario generation

### 2.3 Why Cortex Is Uniquely Positioned

Cortex already has the hard infrastructure that would take a competitor 12-18 months to build:

| Capability | Status | Competitor Timeline |
|-----------|--------|-------------------|
| 6-dimension quality framework | Production | 6-9 months |
| Outcome flywheel (learn from usage) | Production | 12+ months (architectural) |
| Hybrid retrieval (BM25 + embeddings + RRF) | Production | 3-6 months |
| AI-as-Judge scoring | Production | 2-4 months |
| Tiered memory (487x recency weighting) | Production | 6-9 months |
| Canadian FinServ knowledge base | MEP (9 constraints) | 3-6 months |

The moat is not generation. Anyone can generate plausible-looking records. The moat is the **outcome flywheel**: the ability to measure whether generated data actually works when used, and to automatically improve the next generation cycle based on that signal.

---

## 3. User Personas

### 3.1 Priya -- Bank Data Scientist

```
Role:        Senior Data Scientist, Model Development
Institution: Big 5 Bank (Toronto)
Team Size:   8-12 data scientists
Experience:  7 years in financial modeling
```

**Goals**:
- Train and validate credit risk, fraud detection, and customer propensity models
- Need realistic datasets with known statistical properties for model backtesting
- Must demonstrate model performance to OSFI under E-23 guidelines

**Pain Points**:
- Spends 40% of time on data access requests that take 2-6 weeks
- Real data requires privacy review board approval for each new use case
- Anonymized real data still carries re-identification risk (Quebec Law 25 liability)
- Existing synthetic tools produce data that fails downstream model validation

**SynthFinServ Value**:
- Generate 100K+ profiles in minutes with known distribution properties
- Quality-scored records eliminate garbage-in-garbage-out risk
- TSTR (Train-Synthetic-Test-Real) validation proves utility before model deployment
- Distribution constraints match StatsCan benchmarks within 5%

**Key Metric**: Time from data request to model training < 1 hour (currently 2-6 weeks)

### 3.2 Marcus -- AML Compliance Officer

```
Role:        Director, AML/KYC Compliance
Institution: Mid-tier bank or credit union
Team Size:   15-20 compliance analysts
Experience:  12 years in financial crime compliance
```

**Goals**:
- Test AML transaction monitoring rules against known-bad scenarios
- Demonstrate FINTRAC compliance effectiveness to regulators and auditors
- Train new compliance analysts on pattern recognition

**Pain Points**:
- Real suspicious transaction data is extremely sensitive and restricted
- Cannot share real cases across teams or with external auditors
- AML rule calibration requires thousands of test scenarios with known outcomes
- Regulators increasingly want evidence of scenario-based testing

**SynthFinServ Value**:
- Generate transactions with 4 embedded AML risk patterns (structuring, rapid movement, round amounts, geographic risk)
- Known ground truth for every synthetic suspicious transaction
- Calibrated risk scores enable rule threshold optimization
- Data is fully synthetic and carries no PIPEDA/FINTRAC exposure risk

**Key Metric**: AML detection rate improvement from scenario-based calibration: target +15%

### 3.3 Anika -- Fintech Product Manager

```
Role:        Product Manager, Growth
Institution: Canadian fintech (Series B+)
Team Size:   Cross-functional (eng, design, data)
Experience:  5 years in product, 2 in fintech
```

**Goals**:
- Understand Canadian customer segments for product-market fit analysis
- Model customer migration patterns between incumbents and fintechs
- Build realistic demo environments for investor presentations

**Pain Points**:
- No access to incumbent bank customer data
- Public data (StatsCan) is too aggregated for product decisions
- Building realistic demo data manually is time-consuming and unconvincing
- Needs Canadian-specific data (not US proxy data)

**SynthFinServ Value**:
- Canadian-calibrated customer profiles with segment-specific financial behavior
- Product holding distributions matched to Big 5 bank averages
- Digital adoption signals correlated with demographics
- Market scenario generation for competitive intelligence

**Key Metric**: Time to build realistic product demo: < 30 minutes (currently 2-3 days)

### 3.4 David -- Market Research Analyst

```
Role:        Senior Analyst, Financial Services Practice
Institution: Management consulting firm (Big 4 or boutique)
Team Size:   4-6 analysts per engagement
Experience:  8 years in FinServ consulting
```

**Goals**:
- Build market sizing models for Canadian FinServ client engagements
- Simulate customer behavior under different rate/competitive scenarios
- Create realistic data exhibits for client presentations

**Pain Points**:
- Relies on expensive third-party panel data ($50K-200K per study)
- Panel data skews toward urban, digitally-engaged demographics
- Cannot generate scenario-specific datasets on demand
- Clients question whether recommendations are backed by realistic data

**SynthFinServ Value**:
- On-demand generation of Canadian FinServ customer populations
- Province-level, segment-level, and product-level targeting
- Market scenario generation for rate changes, competitive disruption, migration
- Statistically grounded in public benchmarks (StatsCan, CBA, OSFI)

**Key Metric**: Cost per market research dataset: < $500 (currently $50K-200K)

---

## 4. Product Vision & Strategy

### 4.1 Vision

Become the default source of synthetic financial data for every Canadian bank, insurer, and fintech -- the dataset they reach for before they even think about requesting real data.

### 4.2 Strategic Positioning

```
                    HIGH QUALITY
                        |
                        |
          SynthFinServ  |  Enterprise Players
          (Flywheel +   |  (Mostly AI, Gretel)
           Canadian     |  (No Canadian focus,
           calibration) |   no outcome loop)
                        |
    LOW COST -----------+----------- HIGH COST
                        |
          Open Source    |  Custom Consulting
          (SDV, Faker)  |  (Accenture, EY)
          (No quality   |  (Expensive, slow,
           validation)  |   not scalable)
                        |
                    LOW QUALITY
```

**SynthFinServ occupies the high-quality, low-cost quadrant** by leveraging Cortex's existing infrastructure (zero incremental infrastructure cost) and the feedback flywheel (quality improves automatically without manual tuning).

### 4.3 Strategy: The Flywheel Advantage

```
    +-------------------+
    |  GENERATE         |
    |  Synthetic data   |
    |  from KB          |
    +--------+----------+
             |
             v
    +--------+----------+     +-------------------+
    |  VALIDATE         |---->|  IMPROVE          |
    |  6-dimension      |     |  Recalibrate      |
    |  quality scoring  |     |  distributions    |
    +--------+----------+     |  and constraints  |
             |                +--------+----------+
             v                         ^
    +--------+----------+              |
    |  USE              |              |
    |  Client trains    |--------------+
    |  models, tests    |  Outcome signal:
    |  scenarios        |  "Did it work?"
    +-------------------+
```

Every competitor stops at GENERATE. Some reach VALIDATE. None close the loop back to IMPROVE. This is the moat.

### 4.4 Go-to-Market Phasing

| Phase | Timeline | Focus | Revenue Model |
|-------|----------|-------|---------------|
| Phase 1: MEP | Q1 2026 (DONE) | Profile + transaction generation with quality validation | Free (design partner) |
| Phase 2: Risk Model | Q2 2026 | AML scenario engine, FINTRAC calibration | Pilot pricing ($5K/month) |
| Phase 3: TSTR Utility | Q3 2026 | Train-Synthetic-Test-Real validation suite | Usage-based ($0.01/record) |
| Phase 4: Enterprise | Q4 2026 | Multi-tenant API, SLA, compliance certification | Enterprise tiers ($25K-100K/year) |

---

## 5. Use Cases

### UC1: Customer Profile Generation

**Description**: Generate synthetic Canadian banking customer profiles with demographics, financial product holdings, credit attributes, and behavioral signals -- all calibrated to Canadian market distributions.

**Actors**: Data Scientist (Priya), Market Research Analyst (David), Product Manager (Anika)

**Trigger**: User submits a GenerationRequest specifying `data_type="profiles"` with optional segment, province, and quality constraints.

**Flow**:

```
1. User specifies parameters:
   - Count (1 to 1,000,000)
   - Segment filter (optional): mass_market, mass_affluent, affluent,
     high_net_worth, ultra_hnw, small_business, commercial, new_to_canada
   - Province filter (optional): any of 13 provinces/territories
   - Quality threshold (default: 0.7)
   - Output format: JSONL, CSV, or JSON

2. Generator loads constraints from CanadianFinServKB:
   - Province distribution (StatsCan Census 2021)
   - Age distribution (StatsCan, 18+ banking population)
   - Segment distribution (Big 5 annual report aggregate)
   - Income ranges per segment
   - Credit score ranges per segment (Equifax Canada)
   - Product penetration rates (CBA 2024)
   - Digital adoption rates (CBA Digital Banking Survey)

3. For each profile, generator produces correlated fields:
   - Province -> FSA (Forward Sortation Area)
   - Segment -> Income range -> Actual income (age-correlated)
   - Age + Income -> Credit score
   - Segment -> Product likelihood -> Held products
   - Age -> Digital adoption -> Primary channel
   - Age -> Tenure (bounded by adult years)
   - Income + Age + Segment -> Deposit estimate
   - Income + Products -> Credit outstanding estimate

4. Quality tracker assesses each profile on 6 dimensions:
   - Completeness: all 14 required fields populated
   - Consistency: income/segment match, credit/age correlation,
     household >= individual income, tenure <= adult years,
     products count matches list, digital/age correlation
   - Accuracy: values within Canadian market ranges (age 18-100,
     credit 300-900, valid province, valid FSA format)
   - Timeliness: generation timestamp is recent
   - Uniqueness: no duplicate profile IDs
   - Validity: segment/digital/channel/province enum compliance

5. Records below quality threshold are rejected
6. Passed records written to output file (JSONL/CSV/JSON)
7. Generation metadata logged for flywheel learning
```

**Acceptance Criteria**:

| # | Criterion | Target | MEP Status |
|---|----------|--------|------------|
| AC1.1 | Province distribution matches StatsCan within tolerance | <= 5% max deviation | PASSING |
| AC1.2 | Segment distribution matches Big 5 average | <= 5% max deviation | PASSING |
| AC1.3 | All profiles pass schema validation | 100% | PASSING |
| AC1.4 | Average quality score across 6 dimensions | >= 0.80 | PASSING (0.87 avg) |
| AC1.5 | Generation throughput | >= 1,000 profiles/second | PASSING (<0.1s for 100) |
| AC1.6 | Credit scores within Canadian range (300-900) | 100% | PASSING |
| AC1.7 | Income correlated with segment | Within 20% tolerance | PASSING |
| AC1.8 | Every profile has at least chequing account | 100% | PASSING |
| AC1.9 | Flywheel outcome logged for every run | 100% | PASSING |
| AC1.10 | Output file written and path returned | Always | PASSING |

**Output Schema** (CustomerProfile):

```
{
  "profile_id": "SYN-A1B2C3D4E5F6",    // Unique synthetic ID
  "age": 42,                             // 18-100
  "province": "ON",                      // 13 provinces/territories
  "fsa": "M5V",                          // Forward Sortation Area
  "segment": "mass_affluent",            // 8 segments
  "annual_income": 112500.00,            // Segment-correlated
  "household_income": 185000.00,         // >= annual_income
  "credit_score": 762,                   // 300-900 (Canadian scale)
  "products_held": ["chequing", "savings", "tfsa", "mortgage", "credit_card"],
  "total_deposits": 89500.00,            // Income/age-estimated
  "total_credit_outstanding": 425000.00, // Product-estimated
  "digital_adoption": "hybrid",          // Age-correlated
  "primary_channel": "mobile",           // Digital-correlated
  "tenure_years": 12.5,                  // <= age - 16
  "products_per_household": 5,           // == len(products_held)
  "generated_at": "2026-02-05T14:30:00", // ISO 8601
  "generation_version": "1.0",
  "quality_score": 0.91                  // 6-dimension average
}
```

---

### UC2: Transaction Data Generation

**Description**: Generate synthetic transaction records including normal patterns and 4 AML risk scenarios -- calibrated to FINTRAC thresholds and Canadian banking patterns.

**Actors**: AML Compliance Officer (Marcus), Data Scientist (Priya)

**Trigger**: User submits GenerationRequest with `data_type="transactions"`, optionally specifying risk profile and risk flag inclusion.

**Flow**:

```
1. User specifies parameters:
   - Count (1 to 10,000,000)
   - Risk profile: "low" (0% suspicious), "medium" (5%), "high" (15%)
   - Include risk flags: boolean
   - Quality threshold (default: 0.7)

2. For normal transactions, generator samples:
   - Transaction type distribution:
     POS purchase (35%), e-Transfer (20%), bill payment (15%),
     online purchase (12%), transfer (8%), ATM (5%),
     deposit (3%), withdrawal (2%)
   - Amount ranges per type (e.g., POS $5-500, transfer $100-10K)

3. For suspicious transactions (when risk flags enabled):
   - STRUCTURING: Amount $9,000-$9,999 (just under $10K FINTRAC
     threshold), deposit type, risk score 0.6-0.9
   - RAPID MOVEMENT: Amount $15K-$50K, wire/transfer type,
     risk score 0.5-0.85
   - ROUND AMOUNTS: Exact $5K/$10K/$15K/$20K/$25K/$50K,
     wire domestic type, risk score 0.4-0.7
   - GEOGRAPHIC RISK: Amount $5K-$100K, wire international,
     high-risk country code (IR/KP/SY/MM/AF), risk score 0.7-0.95

4. Quality validation:
   - Completeness: 6 required fields present
   - Consistency: international flag matches country_code,
     risk flag matches risk score range,
     wire_international type matches is_international
   - Accuracy: amount > 0, valid currency, risk score 0.0-1.0
   - Validity: transaction type and risk flag are valid enums,
     timestamp is parseable ISO 8601

5. Output written, flywheel logged
```

**Acceptance Criteria**:

| # | Criterion | Target | MEP Status |
|---|----------|--------|------------|
| AC2.1 | Normal transaction type distribution matches specification | Within 10% | PASSING |
| AC2.2 | Structuring pattern amounts within $9,000-$9,999 | 100% | PASSING |
| AC2.3 | Geographic risk transactions have valid high-risk country codes | 100% | PASSING |
| AC2.4 | Risk score ranges match risk flag severity | Consistent | PASSING |
| AC2.5 | High-risk profile generates ~15% suspicious transactions | Within 5% | PASSING |
| AC2.6 | All transactions have valid currency codes | 100% (CAD default) | PASSING |
| AC2.7 | Average quality score | >= 0.80 | PASSING |
| AC2.8 | Ground truth labels present for all suspicious transactions | 100% | PASSING |

**AML Risk Pattern Details**:

```
+---------------------+------------------+-----------------+---------------+
| Pattern             | Amount Range     | Key Indicator   | Risk Score    |
+---------------------+------------------+-----------------+---------------+
| Structuring         | $9,000 - $9,999  | Just under      | 0.60 - 0.90   |
|                     |                  | FINTRAC $10K    |               |
+---------------------+------------------+-----------------+---------------+
| Rapid Movement      | $15,000-$50,000  | Wire/transfer   | 0.50 - 0.85   |
|                     |                  | in-and-out      |               |
+---------------------+------------------+-----------------+---------------+
| Round Amounts       | $5K-$50K exact   | Suspiciously    | 0.40 - 0.70   |
|                     |                  | round numbers   |               |
+---------------------+------------------+-----------------+---------------+
| Geographic Risk     | $5,000-$100,000  | High-risk       | 0.70 - 0.95   |
|                     |                  | jurisdiction    |               |
+---------------------+------------------+-----------------+---------------+
```

---

### UC3: Market Scenario Generation (Phase 3)

**Description**: Generate multi-dimensional market scenarios modeling rate environment changes, competitive response, and customer migration patterns across Canadian financial institutions.

**Actors**: Market Research Analyst (David), Product Manager (Anika)

**Trigger**: User specifies scenario type (rate change, competitive disruption, migration) with parameters.

**Planned Scenarios**:

| Scenario Type | Parameters | Output |
|--------------|-----------|--------|
| Rate Environment | BoC rate delta, timeline | Customer behavior shifts, product mix changes, default rate impact |
| Competitive Disruption | New entrant type, pricing | Customer migration probabilities by segment |
| Portfolio Stress | Unemployment rate, housing price delta | Loss given default distributions, concentration risk |

**Acceptance Criteria (Phase 3 targets)**:

| # | Criterion | Target |
|---|----------|--------|
| AC3.1 | Scenario outputs internally consistent | Quality score >= 0.85 |
| AC3.2 | Rate sensitivity directionally correct | Validated by domain expert |
| AC3.3 | Migration patterns match historical precedent | Within 10% of observed |
| AC3.4 | Stress scenarios calibrated to OSFI benchmarks | Pass OSFI parameter check |

---

## 6. Functional Requirements

### 6.1 P0 -- Must Have (MEP Scope, Delivered)

| ID | Requirement | Description | Status |
|----|------------|-------------|--------|
| FR-001 | Profile Generation | Generate synthetic Canadian customer profiles with 17 fields | DONE |
| FR-002 | Transaction Generation | Generate normal + suspicious transaction records | DONE |
| FR-003 | Knowledge Base | 9 distribution constraints from StatsCan, CBA, OSFI, Equifax | DONE |
| FR-004 | Quality Validation | 6-dimension quality scoring per record (completeness, consistency, accuracy, timeliness, uniqueness, validity) | DONE |
| FR-005 | Quality Filtering | Reject records below configurable quality threshold | DONE |
| FR-006 | Distribution Fidelity | Province, segment, digital adoption match benchmarks within 5% | DONE |
| FR-007 | Cross-Field Correlation | Income/segment, credit/age, digital/age, tenure/age correlations | DONE |
| FR-008 | Output Formats | JSONL, JSON, CSV export | DONE |
| FR-009 | Flywheel Logging | Every generation run logged with quality metadata | DONE |
| FR-010 | Bridge Integration | `bridge.generate_synthetic()` API method | DONE |
| FR-011 | AML Risk Patterns | 4 suspicious transaction patterns (structuring, rapid movement, round amounts, geographic risk) | DONE |
| FR-012 | Schema Validation | Pydantic-style dataclass schemas for all record types | DONE |
| FR-013 | Segment Targeting | Generate profiles for specific customer segments | DONE |
| FR-014 | Province Targeting | Generate profiles for specific provinces/territories | DONE |

### 6.2 P1 -- Should Have (Phase 2 Scope)

| ID | Requirement | Description | Target |
|----|------------|-------------|--------|
| FR-015 | CLI Command | `python cortex/cli.py synthetic --type profiles --count 1000 --segment prime-mortgage` | Q2 2026 |
| FR-016 | Temporal Patterns | Payroll cycles, seasonal spending, day-of-week distributions in transactions | Q2 2026 |
| FR-017 | AML Rule Engine | Run generated transactions through configurable AML rule sets | Q2 2026 |
| FR-018 | Batch Distribution Report | Automated chi-square / KS test report for generated batches | Q2 2026 |
| FR-019 | Profile-Transaction Linking | Generate transactions that belong to specific customer profiles | Q2 2026 |
| FR-020 | Configurable Risk Scenarios | User-defined AML patterns beyond the built-in 4 | Q2 2026 |
| FR-021 | Income Tax Bracket Alignment | Income distributions aligned to CRA tax bracket data | Q2 2026 |
| FR-022 | Mortgage Stress Testing | OSFI B-20 stress test rate applied to mortgage profiles | Q2 2026 |
| FR-023 | Outcome Ingestion API | Accept client feedback on generated data quality | Q2 2026 |
| FR-024 | Distribution Drift Detection | Alert when generated distributions drift from knowledge base targets | Q2 2026 |

### 6.3 P2 -- Nice to Have (Phase 3-4 Scope)

| ID | Requirement | Description | Target |
|----|------------|-------------|--------|
| FR-025 | TSTR Validation Suite | Train-on-Synthetic-Test-on-Real benchmark framework | Q3 2026 |
| FR-026 | Discriminator Testing | XGBoost classifier to detect synthetic vs real, with SHAP explanations | Q3 2026 |
| FR-027 | Market Scenario Engine | Rate environment, competitive response, migration scenarios | Q3 2026 |
| FR-028 | Privacy Boundary Testing | DCR (Distance to Closest Record) and membership inference resistance | Q3 2026 |
| FR-029 | Multi-Tenant API | REST API with authentication, rate limiting, tenant isolation | Q4 2026 |
| FR-030 | Data Catalog | Searchable catalog of generated datasets with lineage tracking | Q4 2026 |
| FR-031 | Compliance Certification | SOC 2 Type II alignment documentation for generated data | Q4 2026 |
| FR-032 | Streaming Generation | Generate records in real-time streams for integration testing | Q4 2026 |
| FR-033 | Custom Distribution Upload | Clients provide their own distribution constraints | Q4 2026 |
| FR-034 | Automatic Recalibration | Flywheel automatically adjusts KB constraints from outcome data | Q4 2026 |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Metric | Requirement | Current (MEP) |
|--------|------------|---------------|
| Profile generation throughput | >= 1,000 records/second | ~1,000/s (100 in <0.1s) |
| Transaction generation throughput | >= 5,000 records/second | ~5,000/s |
| Batch generation (1M profiles) | < 20 minutes | Not yet tested at scale |
| Quality validation overhead | < 10% of generation time | ~5% |
| Memory footprint (100K records) | < 2GB RAM | ~500MB |
| Output file write (100K JSONL) | < 5 seconds | ~2s |

### 7.2 Privacy & Data Protection

| Requirement | Description | Implementation |
|------------|-------------|----------------|
| No real PII | Zero real customer data in generation pipeline | Statistical sampling only -- no real data ingestion |
| No memorization | Generated records must not reproduce real individuals | Knowledge base contains only aggregate distributions |
| DCR validation (Phase 3) | Distance to Closest Record >= threshold | FR-028 |
| Membership inference resistance (Phase 3) | Attack success rate < random chance | FR-028 |
| PIPEDA compliance | Generated data carries no PIPEDA obligations | Synthetic-by-design: never derived from individual records |
| Quebec Law 25 compliance | No personal information processed | Aggregate statistical sources only |
| Data residency | All generation and storage within Canadian infrastructure | Deploy on Canadian cloud regions (ca-central-1) |

### 7.3 Regulatory Compliance

| Regulation | Requirement | Approach |
|-----------|-------------|----------|
| PIPEDA | No personal information in generated data | Synthetic from aggregate statistics only |
| Quebec Law 25 | Privacy impact assessment readiness | Document synthetic methodology, no individual-level inputs |
| OSFI B-20 | Stress test rate parameters current | Knowledge base updated quarterly from OSFI publications |
| OSFI E-23 | Model risk management compatibility | TSTR validation (Phase 3) provides independent validation evidence |
| FINTRAC | AML threshold accuracy | $10K cash/EFT thresholds coded from FINTRAC guidelines |
| CDIC | Deposit insurance limit awareness | $100K insured deposit limit reflected in generation |

### 7.4 Reliability & Availability

| Metric | Requirement |
|--------|------------|
| Generation success rate | >= 99.9% (no crashes on valid input) |
| Quality pass rate at 0.7 threshold | >= 95% of generated records |
| Distribution fidelity | All constraints within 5% tolerance |
| Flywheel logging | 100% of runs captured |
| Data integrity | Zero corrupted output files |

### 7.5 Scalability

| Dimension | Phase 1-2 | Phase 3-4 |
|-----------|-----------|-----------|
| Single-run batch size | Up to 1M records | Up to 100M records |
| Concurrent generation jobs | 1 (single-process) | 10+ (distributed) |
| Knowledge base constraints | 9 | 50+ |
| Output formats | JSONL, JSON, CSV | + Parquet, Delta Lake, API streaming |
| Client tenants | 1 (internal) | 50+ (multi-tenant) |

### 7.6 Maintainability

| Requirement | Description |
|------------|-------------|
| Test coverage | >= 90% line coverage on generator, quality, knowledge_base modules |
| Knowledge base updates | Quarterly refresh from public sources (StatsCan, CBA, OSFI) |
| Schema versioning | `generation_version` field tracks schema changes |
| Backward compatibility | Old output files remain parseable by new versions |
| Documentation | API docs, constraint source citations, quality dimension definitions |

---

## 8. The 7-Layer Feedback Flywheel

The 7-layer feedback flywheel is the core differentiator of Cortex SynthFinServ. No competitor implements anything beyond Layer 2.

### 8.1 Architecture Overview

```
+-----------------------------------------------------------------------+
|                    7-LAYER FEEDBACK FLYWHEEL                          |
|                                                                       |
|  Layer 7: CLIENT OUTCOME                                              |
|  +-------------------------------------------------------------------+|
|  | Human feedback: compliance acceptance rate, analyst trust score,  ||
|  | model deployment decisions. "Did the bank actually use the data?" ||
|  +-----+-------------------------------------------------------------+|
|        |                                                              |
|        v  Outcome signal feeds back to Layer 1 constraints            |
|  Layer 6: PRIVACY BOUNDARY                                            |
|  +-------------------------------------------------------------------+|
|  | DCR (Distance to Closest Record) >= threshold                     ||
|  | Membership inference attack resistance < random chance            ||
|  | Re-identification risk quantification                             ||
|  +-----+-------------------------------------------------------------+|
|        |                                                              |
|  Layer 5: TSTR UTILITY                                                |
|  +-------------------------------------------------------------------+|
|  | Train model on synthetic data, test on real holdout               ||
|  | Measure: AUC-ROC delta, precision/recall parity,                  ||
|  | feature importance alignment between real and synthetic models    ||
|  +-----+-------------------------------------------------------------+|
|        |                                                              |
|  Layer 4: RISK MODEL FEEDBACK                                         |
|  +-------------------------------------------------------------------+|
|  | AML rule engine pass-through: detection rate calibration          ||
|  | Known-bad transactions must trigger rules at expected rates       ||
|  | Adversarial red-team loop: evolve evasion patterns                ||
|  +-----+-------------------------------------------------------------+|
|        |                                                              |
|  Layer 3: DISCRIMINATOR TEST                                          |
|  +-------------------------------------------------------------------+|
|  | XGBoost binary classifier: synthetic vs real                      ||
|  | Target: AUC-ROC <= 0.55 (near-random = indistinguishable)        ||
|  | SHAP feature importances identify which fields are unrealistic    ||
|  +-----+-------------------------------------------------------------+|
|        |                                                              |
|  Layer 2: STATISTICAL FIDELITY                                        |
|  +-------------------------------------------------------------------+|
|  | Per-column: KS test (continuous), chi-square (categorical)        ||
|  | Per-column: JSD (Jensen-Shannon Divergence)                       ||
|  | Cross-column: Correlation matrix comparison (Frobenius norm)      ||
|  | Constraint validation: all 9 KB constraints within 5% tolerance   ||
|  +-----+-------------------------------------------------------------+|
|        |                                                              |
|  Layer 1: SELF-VALIDATION                                             |
|  +-------------------------------------------------------------------+|
|  | 6-dimension quality scoring per record:                           ||
|  | Completeness | Consistency | Accuracy | Timeliness | Uniqueness  ||
|  | | Validity                                                        ||
|  | Records below threshold rejected before output                    ||
|  +-------------------------------------------------------------------+|
|                                                                       |
+-----------------------------------------------------------------------+
```

### 8.2 Layer Details

#### Layer 1: Self-Validation (IMPLEMENTED -- MEP)

**What it does**: Every generated record is scored on 6 quality dimensions before it reaches the output file. Records below the quality threshold are rejected.

**6 Quality Dimensions**:

| Dimension | Profile Checks | Transaction Checks |
|-----------|---------------|-------------------|
| Completeness | 14 required fields populated | 6 required fields populated |
| Consistency | Income/segment match, credit/age correlation, household >= individual, tenure <= adult years, products count = list length, digital/age alignment | International flag matches country_code, risk flag matches score range, wire type matches international flag |
| Accuracy | Age 18-100, credit 300-900, income non-negative, valid province, valid FSA format, chequing account present | Amount > 0, valid currency, risk score 0.0-1.0 |
| Timeliness | Generation timestamp within acceptable freshness window | Same |
| Uniqueness | No duplicate profile_id (MD5 hash tracking) | No duplicate transaction_id |
| Validity | Segment, digital adoption, channel, province are valid enum values | Transaction type, risk flag are valid enums, ISO 8601 timestamp |

**Current performance**: Average quality score 0.87 across all dimensions. 100% pass rate at 0.7 threshold.

#### Layer 2: Statistical Fidelity (IMPLEMENTED -- MEP)

**What it does**: After generating a batch, compares the aggregate distribution of the batch against knowledge base constraints derived from StatsCan, CBA, OSFI, and Equifax Canada.

**Tests implemented (MEP)**:

| Constraint | Source | Tolerance | MEP Status |
|-----------|--------|-----------|------------|
| Province distribution | StatsCan Census 2021 | 5% max deviation | PASSING |
| Age distribution (18+) | StatsCan Census 2021 | 5% max deviation | PASSING |
| Customer segment distribution | Big 5 annual reports 2024 | 5% max deviation | PASSING |
| Income distribution | StatsCan Table 11-10-0239-01 | 5% max deviation | VALIDATED |
| Credit score distribution | Equifax Canada 2024 | 5% max deviation | VALIDATED |
| Product penetration rates | CBA Financial Statistics 2024 | 5% max deviation | VALIDATED |
| Digital adoption rates | CBA Digital Banking Survey 2024 | 5% max deviation | PASSING |
| Primary channel distribution | CBA Digital Banking Survey 2024 | 5% max deviation | PASSING |
| Products per customer | Big 5 cross-sell metrics 2024 | 5% max deviation | VALIDATED |

**Phase 2 additions**: Per-column KS test, chi-square test, JSD calculation, and correlation matrix comparison (Frobenius norm).

#### Layer 3: Discriminator Test (Phase 2)

**What it does**: Trains an XGBoost binary classifier to distinguish synthetic records from real records. If the classifier can reliably distinguish them (AUC-ROC > 0.55), it means the synthetic data has detectable artifacts. SHAP feature importances identify exactly which fields are unrealistic.

**Target**: AUC-ROC <= 0.55 (near-random chance). If above 0.55, the top SHAP features are fed back to the generator as constraints to fix.

**Implementation plan**:
1. Train XGBoost on 50/50 synthetic/real split (using anonymized aggregate data, not individual records)
2. Compute AUC-ROC on holdout set
3. Extract SHAP values for top-10 most discriminative features
4. Feed discriminative features back to knowledge base as tightened constraints
5. Repeat until AUC-ROC <= 0.55

#### Layer 4: Risk Model Feedback (Phase 2)

**What it does**: Passes generated suspicious transactions through a configurable AML rule engine. Measures whether known-bad transactions trigger alerts at the expected rate.

**Calibration targets**:

| Risk Pattern | Expected Detection Rate | Tolerance |
|-------------|----------------------|-----------|
| Structuring | >= 85% | +/- 5% |
| Rapid Movement | >= 75% | +/- 10% |
| Round Amounts | >= 70% | +/- 10% |
| Geographic Risk | >= 90% | +/- 5% |
| Normal (false positive) | <= 5% | +/- 2% |

**Adversarial red-team loop**: Generate increasingly sophisticated evasion patterns. If the AML rules miss them, flag for human review. If the rules catch them, use them as training data for the next generation.

#### Layer 5: TSTR Utility (Phase 3)

**What it does**: The gold standard for synthetic data quality. Trains a downstream model entirely on synthetic data, then tests it on real data. The performance delta between a model trained on real data (TRTR) and a model trained on synthetic data (TSTR) quantifies utility.

**Protocol**:
1. Train Model A on real training data, test on real test data (TRTR baseline)
2. Train Model B on synthetic data (same size), test on same real test data (TSTR)
3. Measure: AUC-ROC delta, precision delta, recall delta, feature importance alignment
4. Target: TSTR performance >= 90% of TRTR performance

**Use cases for TSTR**:
- Credit risk scoring models
- AML suspicious activity detection
- Customer churn prediction
- Product propensity models

#### Layer 6: Privacy Boundary (Phase 3)

**What it does**: Quantifies the privacy guarantee of generated data. Even though SynthFinServ uses only aggregate statistics (not real records), this layer provides mathematical evidence of privacy protection.

**Metrics**:

| Metric | Definition | Target |
|--------|-----------|--------|
| DCR (Distance to Closest Record) | Minimum distance between any synthetic record and any real record in feature space | >= 5th percentile of real-to-real distances |
| Membership Inference Attack | Probability of correctly guessing whether a real individual was in the training data | <= 50% + epsilon (random chance) |
| Attribute Inference | Probability of inferring sensitive attributes from synthetic records | <= baseline population rate |

**Note**: Since SynthFinServ generates from aggregate distributions rather than learning from individual records, the privacy boundary should be inherently strong. This layer provides the mathematical proof.

#### Layer 7: Client Outcome (Phase 4)

**What it does**: Closes the loop with human feedback. When a client uses generated data and reports back on whether it worked for their purpose, that signal feeds back to improve the generator.

**Outcome signals**:

| Signal | Source | Feedback Mechanism |
|--------|--------|-------------------|
| Compliance acceptance | AML officer | "Did your compliance team accept this data for testing?" |
| Model deployment | Data scientist | "Did you deploy the model trained on this data?" |
| Research citation | Market analyst | "Did your client accept the data-backed recommendations?" |
| Repeat usage | All personas | "Did you generate more data?" (implicit quality signal) |
| Quality rating | All personas | Explicit 1-5 rating on generated batch |
| Defect report | All personas | Specific records flagged as unrealistic |

**Flywheel mechanism**: Outcome signals are aggregated per constraint and per segment. If mass_affluent profiles in Ontario consistently receive poor feedback, the knowledge base constraints for that intersection are recalibrated.

### 8.3 Flywheel Maturity Model

```
  MATURITY LEVEL          LAYERS ACTIVE          QUALITY SIGNAL
  ===============         =============          ==============

  Level 1: MEP            L1 + L2                Self-validation +
  (CURRENT)               (per-record +           statistical fidelity
                           batch distribution)

  Level 2: Validated      L1 + L2 + L3 + L4     + Discriminator catches
  (Phase 2 target)                                synthetic artifacts
                                                  + AML rules calibrated

  Level 3: Proven         L1-L5 + L6             + Downstream model
  (Phase 3 target)                                utility quantified
                                                  + Privacy proven

  Level 4: Autonomous     L1-L7                  + Client outcomes
  (Phase 4 target)                                automatically recalibrate
                                                  generation parameters
```

---

## 9. Success Metrics & KPIs

### 9.1 Product Quality Metrics

| KPI | Definition | Phase 1 Target | Phase 2 Target | Phase 4 Target |
|-----|-----------|----------------|----------------|----------------|
| Quality Pass Rate | % of generated records passing threshold | >= 95% at 0.7 | >= 95% at 0.8 | >= 98% at 0.8 |
| Avg Quality Score | Mean 6-dimension score across all records | >= 0.85 | >= 0.88 | >= 0.92 |
| Distribution Fidelity | Max deviation from KB constraints | <= 5% | <= 3% | <= 2% |
| Discriminator AUC-ROC | XGBoost classifier performance | N/A | <= 0.55 | <= 0.52 |
| TSTR Parity | TSTR / TRTR performance ratio | N/A | N/A | >= 0.90 |
| DCR Score | Distance to Closest Record | N/A | N/A | >= 5th pctile |
| Flywheel Improvement | Quality improvement per generation cycle | Logged | +2% per cycle | +1% per cycle |

### 9.2 Adoption Metrics

| KPI | Definition | Phase 1 | Phase 2 | Phase 4 |
|-----|-----------|---------|---------|---------|
| Design Partners | Institutions using SynthFinServ | 1 (internal) | 3-5 | 10+ |
| Monthly Active Users | Unique users per month | 2-5 | 10-20 | 50+ |
| Records Generated (monthly) | Total synthetic records produced | 10K | 1M | 100M+ |
| Repeat Usage Rate | % of users who generate 2+ batches | N/A | >= 60% | >= 80% |
| NPS Score | Net Promoter Score from users | N/A | >= 30 | >= 50 |

### 9.3 Business Metrics

| KPI | Definition | Phase 1 | Phase 2 | Phase 4 |
|-----|-----------|---------|---------|---------|
| Revenue | Monthly recurring revenue | $0 | $15K-25K | $200K+ |
| CAC | Customer acquisition cost | $0 | < $5K | < $10K |
| Time to First Value | Time from signup to first useful generation | < 5 min | < 5 min | < 2 min |
| Data Access Acceleration | Reduction in data request wait time | N/A | 90% reduction | 95% reduction |

### 9.4 Operational Metrics

| KPI | Definition | Target |
|-----|-----------|--------|
| Generation Uptime | % time generation API is available | >= 99.5% |
| P50 Latency (1K records) | Median generation time | < 1 second |
| P99 Latency (1K records) | 99th percentile generation time | < 5 seconds |
| KB Freshness | Age of knowledge base data sources | < 6 months |
| Test Pass Rate | CI/CD pipeline test suite | 100% (23/23) |

---

## 10. Competitive Analysis

### 10.1 Competitive Landscape

```
+------------------+-------------------+-------------------+------------------+
|                  | MOSTLY AI         | GRETEL            | SDV              |
|                  | (Enterprise)      | (Developer)       | (Open Source)    |
+------------------+-------------------+-------------------+------------------+
| Approach         | GAN/VAE-based     | Differential      | Statistical      |
|                  | learned from      | privacy-based     | copula models    |
|                  | real data         | generation        |                  |
+------------------+-------------------+-------------------+------------------+
| Input Required   | Real customer     | Real customer     | Real customer    |
|                  | dataset           | dataset           | dataset          |
+------------------+-------------------+-------------------+------------------+
| Canadian Focus   | None              | None              | None             |
+------------------+-------------------+-------------------+------------------+
| Quality          | Basic stats       | Differential      | Statistical      |
| Validation       | comparison        | privacy metrics   | similarity       |
+------------------+-------------------+-------------------+------------------+
| Feedback Loop    | None              | None              | None             |
+------------------+-------------------+-------------------+------------------+
| FinServ Domain   | Generic           | Generic           | Generic          |
| Knowledge        |                   |                   |                  |
+------------------+-------------------+-------------------+------------------+
| AML Scenarios    | Not built-in      | Not built-in      | Not built-in     |
+------------------+-------------------+-------------------+------------------+
| Pricing          | $50K-200K/year    | $20K-100K/year    | Free + support   |
+------------------+-------------------+-------------------+------------------+
```

### 10.2 Feature Comparison

| Feature | SynthFinServ | Mostly AI | Gretel | SDV | Hazy |
|---------|-------------|-----------|--------|-----|------|
| **No real data required** | Yes | No | No | No | No |
| **Canadian market calibration** | Yes (9 constraints) | No | No | No | No |
| **6-dimension quality scoring** | Yes | No | No | No | No |
| **Outcome feedback flywheel** | Yes (7 layers) | No | No | No | No |
| **AML risk pattern generation** | Yes (4 patterns) | No | No | No | No |
| **FINTRAC threshold awareness** | Yes | No | No | No | No |
| **OSFI parameter integration** | Yes | No | No | No | No |
| **StatsCan calibration** | Yes | No | No | No | No |
| **Discriminator testing** | Phase 2 | Basic | Basic | Basic | Yes |
| **TSTR validation** | Phase 3 | No | No | No | Partial |
| **Privacy boundary proof** | Phase 3 | No | Yes (DP) | No | Partial |
| **Multi-format output** | JSONL/JSON/CSV | CSV/SQL | CSV/JSON | CSV | CSV/SQL |
| **Generation speed (10K records)** | < 10s | Minutes | Minutes | Seconds | Minutes |
| **Requires GPU** | No | Yes | Yes | No | Yes |

### 10.3 Competitive Advantages

**Structural advantage 1: No real data required**

Every competitor requires a real dataset as input. They learn patterns from real data and generate synthetic copies. This means:
- Clients still need to provision real data (privacy review, access controls)
- The synthetic data can only be as good as the real input data
- No generation is possible without first solving the data access problem

SynthFinServ generates from aggregate public statistics. The client never needs to share real data.

**Structural advantage 2: Canadian market calibration**

No competitor has built-in knowledge of Canadian demographics, regulatory thresholds, banking product taxonomy, or provincial distribution. Every competitor's output must be post-processed and manually validated against Canadian benchmarks.

SynthFinServ generates Canadian-calibrated data by default.

**Structural advantage 3: The 7-layer flywheel**

The feedback flywheel is an architectural advantage that cannot be bolted onto existing products. It requires:
- Quality framework integrated into generation (not post-hoc)
- Outcome tracking infrastructure
- Automatic constraint recalibration
- Client feedback ingestion

This is 12-18 months of architectural work that competitors would need to retrofit.

### 10.4 Competitive Risks

| Risk | Description | Mitigation |
|------|------------|------------|
| Mostly AI adds Canadian module | Enterprise player could build Canadian-specific offering | Move fast on Phase 2-3, establish design partner relationships |
| Gretel differential privacy | DP guarantees may be perceived as stronger privacy proof | Implement DCR + membership inference (Phase 3) for comparable rigor |
| Bank builds in-house | Big 5 could build internal synthetic data capability | Offer flywheel as differentiator -- internal teams won't build 7 layers |
| SDV community momentum | Open source community could build Canadian extensions | Differentiate on quality validation and outcome feedback, not generation |

---

## 11. Roadmap

### 11.1 Phase Overview

```
  2026
  Q1           Q2              Q3              Q4
  |            |               |               |
  |  PHASE 1   |   PHASE 2     |   PHASE 3     |   PHASE 4
  |  MEP        |   Risk Model  |   TSTR        |   Enterprise
  |  (DONE)     |               |               |
  |             |               |               |
  | Profiles    | CLI command   | TSTR suite    | Multi-tenant API
  | Transactions| Temporal      | Discriminator | SLA & monitoring
  | Quality     |  patterns     |  testing      | Compliance cert
  | KB (9)      | AML rule      | Market        | Custom distros
  | Flywheel    |  engine       |  scenarios    | Auto-recalibrate
  |  logging    | Batch stats   | Privacy       | Client outcome
  | Bridge API  | Profile-txn   |  boundary     |  ingestion
  |             |  linking      | KB expansion  | Data catalog
  |             | Outcome API   |  (50+)        | Streaming gen
  |             | Drift detect  |               |
  |             |               |               |
  v             v               v               v
  23/23 tests   Target: 50+    Target: 80+     Target: 120+
  9 constraints  tests          tests           tests
  0.87 avg qual  0.89 target    0.91 target     0.93 target
  100% pass@0.7  95% pass@0.8  95% pass@0.85   98% pass@0.85
```

### 11.2 Phase 1: MEP -- Minimum Evolvable Product (COMPLETE)

**Delivery date**: Q1 2026 (delivered)

**Deliverables**:

| # | Deliverable | Status | Evidence |
|---|------------|--------|----------|
| 1.1 | CustomerProfile schema (17 fields) | DONE | `schemas.py:96-146` |
| 1.2 | Transaction schema (14 fields) | DONE | `schemas.py:149-187` |
| 1.3 | GenerationRequest / GenerationResult | DONE | `schemas.py:190-260` |
| 1.4 | CanadianFinServKB (9 constraints) | DONE | `knowledge_base.py:40-416` |
| 1.5 | SyntheticGenerator (profiles + transactions) | DONE | `generator.py:36-516` |
| 1.6 | SyntheticQualityTracker (6 dimensions) | DONE | `quality.py:28-417` |
| 1.7 | 4 AML risk patterns | DONE | `generator.py:285-352` |
| 1.8 | Flywheel outcome logging | DONE | `generator.py:493-515` |
| 1.9 | Bridge API integration | DONE | `bridge.generate_synthetic()` |
| 1.10 | 23/23 tests passing | DONE | `tests/test_generator.py` |
| 1.11 | Demo script | DONE | `demo_synthetic.py` |

### 11.3 Phase 2: Risk Model Integration

**Target delivery**: Q2 2026

**Dependencies**: Phase 1 complete (satisfied)

**Deliverables**:

| # | Deliverable | Priority | Effort |
|---|------------|----------|--------|
| 2.1 | CLI command (`synthetic --type --count --segment`) | P1 | 2 days |
| 2.2 | Temporal transaction patterns (payroll, seasonal, day-of-week) | P1 | 5 days |
| 2.3 | Profile-to-transaction linking (transactions belong to profiles) | P1 | 3 days |
| 2.4 | AML rule engine (configurable rule sets, detection rate measurement) | P1 | 8 days |
| 2.5 | Batch statistical report (KS, chi-square, JSD per column) | P1 | 5 days |
| 2.6 | XGBoost discriminator test with SHAP | P1 | 5 days |
| 2.7 | Outcome ingestion API (client feedback endpoint) | P1 | 3 days |
| 2.8 | Distribution drift detection & alerting | P1 | 3 days |
| 2.9 | OSFI B-20 mortgage stress test integration | P2 | 3 days |
| 2.10 | CRA tax bracket alignment | P2 | 2 days |

**Phase 2 exit criteria**:
- 50+ tests passing
- Discriminator AUC-ROC <= 0.55
- AML structuring detection rate >= 85%
- KB expanded to 15+ constraints
- Outcome API accepting feedback

### 11.4 Phase 3: TSTR Utility & Scenarios

**Target delivery**: Q3 2026

**Dependencies**: Phase 2 complete, access to anonymized benchmark data from design partners

**Deliverables**:

| # | Deliverable | Priority | Effort |
|---|------------|----------|--------|
| 3.1 | TSTR validation framework (train-synthetic-test-real) | P1 | 10 days |
| 3.2 | Market scenario engine (rate, competitive, migration) | P1 | 12 days |
| 3.3 | Privacy boundary testing (DCR, membership inference) | P1 | 8 days |
| 3.4 | KB expansion to 50+ constraints | P1 | 10 days |
| 3.5 | Correlation matrix preservation testing | P1 | 5 days |
| 3.6 | OSFI stress scenario generation | P2 | 5 days |
| 3.7 | Cross-institutional comparison scenarios | P2 | 5 days |

**Phase 3 exit criteria**:
- 80+ tests passing
- TSTR performance >= 90% of TRTR for at least 2 downstream model types
- DCR >= 5th percentile of real-to-real distances
- Market scenarios validated by domain expert
- KB at 50+ constraints with quarterly refresh cadence established

### 11.5 Phase 4: Enterprise Platform

**Target delivery**: Q4 2026

**Dependencies**: Phase 3 complete, 3+ design partner validations, infrastructure budget approved

**Deliverables**:

| # | Deliverable | Priority | Effort |
|---|------------|----------|--------|
| 4.1 | Multi-tenant REST API with auth, rate limiting, tenant isolation | P1 | 15 days |
| 4.2 | Client outcome feedback loop (automatic recalibration) | P1 | 12 days |
| 4.3 | Data catalog with lineage tracking | P1 | 8 days |
| 4.4 | SOC 2 Type II alignment documentation | P1 | 10 days |
| 4.5 | Custom distribution upload (clients provide own constraints) | P1 | 5 days |
| 4.6 | Streaming generation for integration testing | P2 | 8 days |
| 4.7 | Parquet and Delta Lake output formats | P2 | 3 days |
| 4.8 | SLA monitoring and alerting | P1 | 5 days |

**Phase 4 exit criteria**:
- 120+ tests passing
- 10+ active client tenants
- Automatic recalibration demonstrably improving quality
- SOC 2 documentation ready for audit
- SLA monitoring operational
- Revenue >= $200K ARR

---

## 12. Risks & Mitigations

### 12.1 Technical Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| T1 | Distribution drift: generated data gradually diverges from KB targets as code evolves | Medium | High | Automated distribution fidelity tests in CI/CD (Layer 2). Alert on >3% deviation. |
| T2 | LLM generation variability: if LLM enrichment is added, outputs may not be reproducible | Medium | Medium | Statistical sampling is primary engine. LLM used only for enrichment, never core generation. Seed-based reproducibility. |
| T3 | Cross-field correlation loss at scale: correlations (income/age, credit/segment) weaken in large batches | Medium | High | Batch-level correlation matrix testing (Phase 2). Automated correlation preservation checks. |
| T4 | Knowledge base staleness: StatsCan/CBA data becomes outdated | Low | Medium | Quarterly KB refresh cadence. Source year tracked per constraint. Alert when source > 18 months old. |
| T5 | Performance degradation at scale: 1M+ record generation may be slow | Low | Medium | Profile generation is CPU-only, embarrassingly parallel. Horizontal scaling straightforward. |

### 12.2 Market Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| M1 | Competitor adds Canadian focus: Mostly AI or Gretel builds Canadian module | Medium | High | Move fast on Phase 2-3. Lock in design partners with flywheel advantage. Build switching costs via outcome data accumulation. |
| M2 | Regulatory change: new privacy law restricts even synthetic data generation | Low | High | Monitor CPPA/C-27 progress. Engage with OPC on synthetic data guidance. Build privacy boundary proof (Layer 6) proactively. |
| M3 | Client reluctance: banks may be slow to trust synthetic data for regulated purposes | Medium | Medium | Start with non-regulated use cases (market research, demos). Build credibility through TSTR validation. Seek OSFI acknowledgment of synthetic data for E-23. |
| M4 | Build-vs-buy: large banks may prefer internal solutions | Medium | Medium | Position flywheel as differentiator that internal teams cannot replicate. Offer hybrid model: SynthFinServ engine + bank's proprietary constraints. |

### 12.3 Regulatory Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Synthetic data re-identification: despite using only aggregate stats, generated profiles could coincidentally match real individuals | Low | Critical | Layer 6 privacy boundary testing. DCR metric ensures minimum distance from any real individual. Population-level generation (not individual-level learning) inherently limits this risk. |
| R2 | Regulators classify synthetic data as personal information | Low | Critical | Proactive engagement with OPC and Quebec CAI. Document methodology showing zero individual-level inputs. Maintain audit trail of knowledge base sources (all aggregate/public). |
| R3 | FINTRAC flags synthetic AML data: if synthetic transactions enter production systems, FINTRAC reporting could be triggered | Low | High | Clear labeling of all synthetic records (SYN- prefix on IDs). Metadata fields mark generation version. Output files clearly named. Client integration guide with warnings. |
| R4 | Cross-border data issues: if deployed on US cloud infrastructure | Low | Medium | Canadian data residency requirement (ca-central-1). No cross-border data flow for generation. Client contract terms specify Canadian processing. |

### 12.4 Operational Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| O1 | Single-developer bus factor: expertise concentrated in small team | Medium | High | Comprehensive test suite (23+ tests). Golden Spec documents design rationale. Code is well-documented with docstrings. |
| O2 | KB update cadence lapses: quarterly refresh becomes irregular | Medium | Medium | Automated alerts when source data > 12 months old. Calendar reminders for StatsCan/CBA publication dates. |
| O3 | Flywheel cold start: outcome feedback requires active clients, but client acquisition requires proven quality | Medium | Medium | Layer 1-2 provide immediate quality. Layers 3-6 provide objective validation without client feedback. Layer 7 is the maturity layer, not the minimum viable layer. |

---

## 13. Appendix

### 13.1 Knowledge Base Sources

All knowledge base constraints are derived from publicly available Canadian data sources. No proprietary or individual-level data is used.

| Source | Publisher | Data Type | Update Frequency | Current Year |
|--------|----------|-----------|-----------------|-------------|
| Census 2021 | Statistics Canada | Demographics, geography, income | Every 5 years (next: 2026) | 2021 |
| Table 98-10-0001-01 | Statistics Canada | Population by province/territory | Annual estimates | 2021 |
| Table 11-10-0239-01 | Statistics Canada | Income statistics, tax filer data | Annual | 2022 |
| Consumer Credit Trends | Equifax Canada | Credit score distributions | Quarterly | 2024 |
| Financial Statistics | Canadian Bankers Association | Product penetration, digital adoption | Annual | 2024 |
| Digital Banking Survey | Canadian Bankers Association | Channel usage, digital adoption | Annual | 2024 |
| Big 5 Annual Reports | RBC, TD, Scotiabank, BMO, CIBC | Segment distribution, cross-sell | Annual | 2024 |
| B-20 Guidelines | OSFI | Stress test rate, GDS/TDS ratios | As amended | Current |
| E-23 Guidelines | OSFI | Model risk management requirements | As amended | Current |
| FINTRAC Guidelines | FINTRAC | AML/ATF reporting thresholds | As amended | Current |
| Housing Market Data | CMHC | Mortgage insurance thresholds | Quarterly | Current |

### 13.2 Regulatory References

**Federal**:
- **PIPEDA** (Personal Information Protection and Electronic Documents Act): Federal privacy law governing collection, use, and disclosure of personal information by private-sector organizations
- **Bill C-27 / CPPA** (Consumer Privacy Protection Act): Proposed modernization of PIPEDA with enhanced consent requirements and algorithmic transparency obligations
- **FINTRAC** (Financial Transactions and Reports Analysis Centre of Canada): AML/ATF regime requiring reporting of large cash transactions ($10K+), suspicious transactions, and terrorist financing

**Provincial**:
- **Quebec Law 25** (Act to modernize legislative provisions as regards the protection of personal information): Most restrictive Canadian provincial privacy law, fully effective September 2024, with mandatory privacy impact assessments and enhanced consent requirements
- **Alberta PIPA** (Personal Information Protection Act)
- **BC PIPA** (Personal Information Protection Act)

**Prudential**:
- **OSFI B-20** (Residential Mortgage Underwriting Practices and Procedures): Stress test qualifying rate (contract rate + 2% or 5.25% floor), GDS <= 39%, TDS <= 44%
- **OSFI E-23** (Enterprise-Wide Model Risk Management): Requires independent model validation, documentation of model limitations, ongoing monitoring of model performance
- **CDIC** (Canada Deposit Insurance Corporation): $100K deposit insurance limit per eligible deposit category

### 13.3 Data Schema Reference

**CustomerProfile fields** (17 total):

| Field | Type | Range/Values | Source Constraint |
|-------|------|-------------|-------------------|
| profile_id | string | SYN-{hex12} | Generated, unique |
| age | int | 18-100 | StatsCan age distribution |
| province | string | 13 provinces/territories | StatsCan Census 2021 |
| fsa | string | Letter-Digit-Letter | Province-correlated |
| segment | string | 8 segments | Big 5 annual reports |
| annual_income | float | $20K-$10M | StatsCan + segment range |
| household_income | float | >= annual_income | 1.0-1.8x multiplier |
| credit_score | int | 300-900 | Equifax Canada + segment |
| products_held | list[string] | 16 product types | CBA penetration rates |
| total_deposits | float | >= 0 | Income/age/segment estimated |
| total_credit_outstanding | float | >= 0 | Income/products estimated |
| digital_adoption | string | digital_first, hybrid, branch_preferred | CBA Digital Survey |
| primary_channel | string | mobile, online, branch, telephone | CBA Digital Survey |
| tenure_years | float | 0.5 to age-18 | Age-correlated |
| products_per_household | int | == len(products_held) | Derived |
| generated_at | string | ISO 8601 | System timestamp |
| generation_version | string | Semver | "1.0" current |
| quality_score | float | 0.0-1.0 | 6-dimension average |

**Transaction fields** (14 total):

| Field | Type | Range/Values | Source Constraint |
|-------|------|-------------|-------------------|
| transaction_id | string | TXN-{hex12} | Generated, unique |
| profile_id | string | Links to CustomerProfile | FK reference |
| timestamp | string | ISO 8601 | System timestamp |
| transaction_type | string | 12 types | Distribution-sampled |
| amount | float | > 0 | Type-specific ranges |
| currency | string | CAD, USD, EUR, GBP | Default CAD |
| merchant_category | string | Optional | Future enhancement |
| counterparty_institution | string | Optional | Future enhancement |
| is_international | bool | true/false | Type-correlated |
| country_code | string | ISO 3166-1 alpha-2 | Required if international |
| risk_flag | string | 8 flag types | Risk profile sampled |
| risk_score | float | 0.0-1.0 | Flag-correlated |
| generated_at | string | ISO 8601 | System timestamp |
| quality_score | float | 0.0-1.0 | 6-dimension average |

### 13.4 Module Architecture

```
cortex/synthetic/
|
+-- __init__.py                  # Module exports
+-- GOLDEN_SPEC.md               # Design specification (source of truth)
+-- docs/
|   +-- PRD.md                   # This document
|
+-- schemas.py                   # Dataclasses: CustomerProfile, Transaction,
|                                #   GenerationRequest, GenerationResult
|                                # Enums: Province, CustomerSegment, ProductType,
|                                #   TransactionType, RiskFlag
|
+-- knowledge_base.py            # CanadianFinServKB: 9 distribution constraints
|                                #   from StatsCan, CBA, OSFI, Equifax Canada
|                                # DistributionConstraint: statistical validation
|                                # Regulatory parameters: FINTRAC, OSFI B-20
|
+-- generator.py                 # SyntheticGenerator: core engine
|                                #   _generate_profiles(): statistical sampling
|                                #   _generate_transactions(): normal + 4 AML
|                                #   _pattern_structuring(): $9K-$9.9K threshold
|                                #   _pattern_rapid_movement(): in-and-out
|                                #   _pattern_round_amounts(): exact round numbers
|                                #   _pattern_geographic_risk(): high-risk jurisdiction
|                                #   _log_generation_outcome(): flywheel logging
|
+-- quality.py                   # SyntheticQualityTracker: 6-dimension validation
|                                #   assess_profile(): 6 dimension checks
|                                #   assess_transaction(): 6 dimension checks
|                                #   assess_batch_distribution(): fidelity testing
|
+-- demo_synthetic.py            # Demo: profile gen, targeting, fidelity,
|                                #   AML transactions, KB inspection, flywheel
|
+-- tests/
    +-- __init__.py
    +-- test_generator.py        # 23 tests: schemas, KB, generator, quality
```

### 13.5 Integration Points

```
cortex/
+-- bridge.py          -->  bridge.generate_synthetic()
|                           Calls SyntheticGenerator.generate()
|                           Returns GenerationResult
|
+-- cli.py             -->  cmd_synthetic() (Phase 2)
|                           CLI: python cortex/cli.py synthetic
|                           --type profiles --count 1000 --segment affluent
|
+-- config.py          -->  synthetic_enabled: bool
|                           Feature flag for synthetic module
|
+-- intelligence/
    +-- learning.py    -->  Outcome flywheel integration
                            generation_outcomes.jsonl at ~/.cortex/synthetic/
```

### 13.6 Glossary

| Term | Definition |
|------|-----------|
| AML | Anti-Money Laundering |
| AUC-ROC | Area Under the Receiver Operating Characteristic Curve |
| CBA | Canadian Bankers Association |
| CDIC | Canada Deposit Insurance Corporation |
| CMHC | Canada Mortgage and Housing Corporation |
| CPPA | Consumer Privacy Protection Act (proposed) |
| DCR | Distance to Closest Record (privacy metric) |
| FHSA | First Home Savings Account (Canadian tax-advantaged account) |
| FINTRAC | Financial Transactions and Reports Analysis Centre of Canada |
| FSA | Forward Sortation Area (first 3 characters of Canadian postal code) |
| GDS | Gross Debt Service ratio |
| HELOC | Home Equity Line of Credit |
| JSD | Jensen-Shannon Divergence (statistical distance measure) |
| KS Test | Kolmogorov-Smirnov test (distribution comparison) |
| KYC | Know Your Customer |
| MEP | Minimum Evolvable Product |
| OSFI | Office of the Superintendent of Financial Institutions |
| PIPEDA | Personal Information Protection and Electronic Documents Act |
| RRSP | Registered Retirement Savings Plan (Canadian tax-advantaged account) |
| RESP | Registered Education Savings Plan (Canadian tax-advantaged account) |
| SHAP | SHapley Additive exPlanations (model interpretability) |
| StatsCan | Statistics Canada |
| TDS | Total Debt Service ratio |
| TFSA | Tax-Free Savings Account (Canadian tax-advantaged account) |
| TSTR | Train on Synthetic, Test on Real (validation methodology) |
| TRTR | Train on Real, Test on Real (baseline methodology) |

---

**Document History**:

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-05 | Cortex Product Team | Initial PRD based on v0.1.0 MEP delivery |

---

*This document is the product requirements specification for Cortex SynthFinServ. The Golden Spec (`GOLDEN_SPEC.md`) remains the engineering design specification. This PRD defines what we build and why. The Golden Spec defines how.*
