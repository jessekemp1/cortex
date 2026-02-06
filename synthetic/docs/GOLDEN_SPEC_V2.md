# Golden Spec v2: Cortex Synthetic Data Engine

## Codename: SynthFinServ
## Version: 2.0 — 7-Layer Feedback Flywheel Architecture

| Field              | Value                                    |
|--------------------|------------------------------------------|
| **Product**        | Cortex SynthFinServ                      |
| **Version**        | v2.0                                     |
| **Spec Version**   | Golden Spec v2 (supersedes GOLDEN_SPEC.md) |
| **Status**         | Phase 1 COMPLETE, Phase 2 IN PROGRESS    |
| **Owner**          | Jesse Kemp                               |
| **Last Updated**   | 2026-02-05                               |

---

## Table of Contents

1. [Deep Understanding (The "Why")](#1-deep-understanding-the-why)
2. [Outcome Definition (The "What")](#2-outcome-definition-the-what)
3. [Outcome Validation (The "Reality Check")](#3-outcome-validation-the-reality-check)
4. [Solution Design (The "How")](#4-solution-design-the-how)
5. [Solution-Outcome Alignment](#5-solution-outcome-alignment)
6. [Implementation Planning](#6-implementation-planning)
7. [Success Verification](#7-success-verification)

---

## 1. Deep Understanding (The "Why")

### 1.1 The Regulatory Pressure Cooker

Canadian financial institutions operate under layered, tightening regulatory
constraints that make real customer data increasingly toxic to handle:

**Federal (PIPEDA)**
- Personal Information Protection and Electronic Documents Act governs all
  federally regulated financial institutions. Consent requirements for secondary
  data use (model training, market research) are strict and getting stricter.
- The 2024 proposed Consumer Privacy Protection Act (CPPA) would add
  algorithmic transparency requirements, making synthetic data even more critical
  for ML development.

**Provincial (Quebec Law 25)**
- Effective September 2024, Quebec Law 25 (modernization of the Act respecting
  the protection of personal information in the private sector) imposes:
  - Mandatory Privacy Impact Assessments for any project involving personal
    information
  - De-identification requirements that exceed federal standards
  - Right to data portability (synthetic data enables compliant testing of
    portability systems without exposing real customer records)
  - Administrative monetary penalties up to $25M CAD or 4% of global turnover
- Quebec accounts for 22.8% of the Canadian banking population. Any institution
  operating in Quebec (i.e., all Big 5 banks) must comply.

**OSFI B-20 Stress Testing**
- OSFI Guideline B-20 requires stress-test scenarios for residential mortgage
  underwriting. The qualifying rate floor (currently 5.25% or contract+2%,
  whichever is greater) means institutions need to model borrower behavior
  under stress conditions.
- Synthetic data enables repeatable stress-test scenario generation without
  accessing real mortgage portfolios.

**FINTRAC AML/KYC Mandates**
- Proceeds of Crime (Money Laundering) and Terrorist Financing Act requires
  suspicious transaction reporting above $10,000 CAD (cash) and electronic
  funds transfer reporting.
- AML model validation requires labeled suspicious-transaction datasets.
  Real STR data is classified; synthetic data with calibrated risk patterns
  is the only legal way to train and validate AML detection models externally.

### 1.2 Market Landscape

**Demand Side: Who Needs Synthetic FinServ Data**

| Segment            | Count | Primary Use Case                       | Urgency   |
|--------------------|-------|----------------------------------------|-----------|
| Big 5 Banks        | 5     | AML model validation, stress testing   | Mandatory |
| Big 3 Insurers     | 3     | Claims modeling, fraud detection       | High      |
| Credit Unions      | ~200  | Member analytics (pooled)              | Medium    |
| Fintechs           | ~800  | Product development, compliance testing| High      |
| Regulators (OSFI)  | 1     | Supervisory model validation           | Growing   |

**Market Size**
- Canadian FinServ IT spend: ~$15B CAD/year (IDC Canada 2025)
- Synthetic data tools subset: growing 30%+ annually (Gartner 2025 estimate)
- AML/KYC compliance spend alone: ~$1.2B CAD/year across Big 5 banks
- Addressable market for calibrated synthetic FinServ data: $50M-$200M CAD
  within 3 years (conservative)

**Supply Side: Competitor Landscape**

| Competitor    | Approach              | Feedback Loop | Canadian Focus | AML Support |
|---------------|-----------------------|---------------|----------------|-------------|
| Mostly AI     | CTGAN / Conditional   | None          | No             | Generic     |
| Gretel.ai     | Neural network synth  | None          | No             | Generic     |
| SDV (MIT)     | Statistical modeling  | None          | No             | None        |
| Hazy          | Differential privacy  | None          | No             | Limited     |
| Tonic.ai      | Schema-based masking  | None          | No             | None        |
| **SynthFinServ** | **KB-calibrated + 7-layer flywheel** | **Automated** | **Native** | **FINTRAC-aligned** |

Every competitor follows the same pattern: generate-and-forget. They produce
synthetic data that is statistically plausible at generation time, but nobody
validates whether it behaves correctly when used downstream. There is no
mechanism to learn from outcomes and improve.

### 1.3 Why Cortex Is Uniquely Positioned

Cortex already has the hard parts built and production-tested:

```
  Existing Cortex Infrastructure (Production)
  ============================================
  Quality Framework -----> 6-dimension scoring (completeness, consistency,
  |                        accuracy, timeliness, uniqueness, validity)
  |
  Learning System -------> Outcome flywheel with recency weighting (487x)
  |                        Generation improves from usage feedback
  |
  Hybrid Retriever ------> BM25 + embeddings + RRF fusion
  |                        Sources patterns from heterogeneous data
  |
  AI-as-Judge -----------> Discrete 1-5 scoring, automated quality validation
  |
  Tiered Memory ---------> Reflects current market conditions
  |
  Bridge API ------------> generate_synthetic() method already wired
```

The moat is not generation (commodity). The moat is the **outcome flywheel**
applied to synthetic data -- generation that learns from its own usage and
self-corrects without human intervention.

### 1.4 Highest-Urgency Use Case: AML/KYC Compliance Testing

AML compliance testing is the entry point because it is:

1. **Regulatory mandate** -- institutions must validate AML models but cannot
   share real STR data externally
2. **Well-scoped** -- FINTRAC defines the suspicious patterns; we encode them
3. **Measurable** -- AML rule engines provide binary pass/fail feedback that
   feeds the flywheel directly
4. **High-value** -- AML fines in Canada range from $1M-$500K per violation;
   institutions will pay for better testing data

### 1.5 Phase 1 Outcome

Clear understanding that the competitive moat is the **7-layer automated
feedback flywheel** applied to synthetic data, not the generation engine itself.
Every layer feeds corrections back into the generator without human intervention.

---

## 2. Outcome Definition (The "What")

### 2.1 Primary Outcomes

**O1: Generate synthetic Canadian FinServ datasets calibrated to public
statistical benchmarks**
- Customer profiles match StatsCan/CBA demographic distributions within 5%
  per-dimension deviation
- 9 distribution constraints enforced: province, age, income, segment, credit
  score, product penetration, products-per-customer, digital adoption, primary
  channel

**O2: Generate synthetic transactions with FINTRAC-compliant AML risk patterns**
- Normal transaction distributions by type, amount, frequency
- 7 suspicious-activity patterns: structuring, rapid movement, geographic risk,
  unusual volume, round amounts, dormant reactivation, third-party deposits
- Configurable risk profile (low/medium/high) controls suspicious transaction
  prevalence

**O3: Quality-score every record across 6 weighted dimensions**
- Completeness, consistency, accuracy, timeliness, uniqueness, validity
- Per-record quality score (0.0--1.0) with configurable minimum threshold
- Batch-level distribution fidelity assessment (sample vs. benchmark)

**O4: 7-layer automated feedback flywheel**
- Each layer independently detects quality degradation and routes corrections
  back to the generator
- No human intervention required for quality maintenance
- Measurable improvement between generation cycles (quality score trend)

**O5: Risk model feedback loop**
- AML rule engine validates synthetic fraud patterns
- Adversarial loop: generator tries to produce undetectable fraud; rule engine
  validates; failures feed back as training signal
- TSTR (Train-on-Synthetic, Test-on-Real) utility for downstream task
  benchmarking

**O6: Bridge API and CLI access**
- `python cortex/bridge.py generate_synthetic --type profiles --count 1000`
- `python cortex/cli.py synthetic --type profiles --segment prime-mortgage`
- Programmatic: `bridge.generate_synthetic(data_type="profiles", count=1000)`

**O7: Output formats**
- JSONL (default, streaming-friendly)
- JSON (batch, human-readable)
- CSV (spreadsheet/BI tool compatibility)

### 2.2 Success Criteria (Quantified)

| Criterion                            | Target            | Measurement              |
|--------------------------------------|-------------------|--------------------------|
| StatsCan distribution fidelity       | < 5% max deviation | KS test per dimension    |
| Average quality score (profiles)     | > 0.85            | 6-dimension weighted avg |
| Average quality score (transactions) | > 0.80            | 6-dimension weighted avg |
| AML pattern detection rate           | > 90%             | Rule engine pass-through |
| Flywheel improvement per cycle       | > 2% quality gain | Cycle-over-cycle delta   |
| Discriminator accuracy (synth vs real)| < 65% (closer to random) | XGBoost AUC   |
| Generation throughput                | 1000 profiles/sec | Wall-clock time          |
| Privacy (DCR)                        | > 0.05            | Distance to closest record|
| Privacy (NNDR)                       | > 0.5             | Nearest-neighbor ratio   |

---

## 3. Outcome Validation (The "Reality Check")

### 3.1 What Already Exists (Production-Tested)

| Component           | Status    | Evidence                                         |
|---------------------|-----------|--------------------------------------------------|
| schemas.py          | COMPLETE  | CustomerProfile, Transaction, GenerationRequest   |
| knowledge_base.py   | COMPLETE  | 9 constraints, regulatory params, segment ranges  |
| generator.py        | COMPLETE  | Statistical sampling + correlated field generation |
| quality.py          | COMPLETE  | 6-dimension validator, batch distribution check    |
| demo_synthetic.py   | COMPLETE  | Interactive demo, 6 showcase scenarios             |
| test_generator.py   | COMPLETE  | 23/23 tests passing                               |
| bridge.py           | COMPLETE  | generate_synthetic() method wired                  |
| __init__.py         | COMPLETE  | v0.1.0, all exports defined                       |

**MEP (Minimum Evolvable Product) Validation:**
- Generates 100 profiles in < 0.1 seconds (pure statistical, no LLM call)
- 9 distribution constraints calibrated to StatsCan Census 2021 data
- Quality scores average 0.87 across 6 dimensions on test runs
- Output written to JSONL/JSON/CSV at `~/.cortex/synthetic/`
- Outcome logging to `generation_outcomes.jsonl` for flywheel tracking

### 3.2 Canadian Data Sources (All Public, Free)

| Source                             | Data                          | Access    |
|------------------------------------|-------------------------------|-----------|
| Statistics Canada Census 2021      | Demographics, income, geography| Open data |
| CMHC Housing Market Reports       | Mortgage rates, housing stats  | Published |
| Bank of Canada Interest Rates     | Policy rate, qualifying rate   | Published |
| OSFI Guideline B-20               | Stress test parameters         | Published |
| Big 5 Annual Reports (2024)       | Product mix, segment breakdown | Published |
| CBA Financial Statistics           | Product penetration, digital   | Published |
| Equifax Canada Credit Trends      | Credit score distributions     | Published |
| FINTRAC Guidance                   | AML thresholds, red flags      | Published |
| CRA Tax Statistics                 | Income distributions by FSA    | Open data |

### 3.3 Risks and Mitigations

**Risk 1: Distribution Fidelity for Complex Multivariate Correlations**
- *Problem:* Individual marginal distributions may be correct, but joint
  distributions (e.g., age x income x province x products) could be unrealistic.
- *Severity:* High -- unrealistic correlations undermine downstream model
  training.
- *Mitigation:* constraints.py implements statistical tests (KS, chi-squared,
  JSD) on joint distributions, not just marginals. Flywheel Layer 2 detects
  drift and triggers recalibration.
- *Fallback:* Manual correlation matrices derived from Big 5 annual report
  segment-level disclosures.

**Risk 2: Model Collapse from Recursive Self-Training**
- *Problem:* If the flywheel trains on its own synthetic output (recursive
  feedback), distributions could collapse to a narrow mode.
- *Severity:* Critical -- model collapse is irreversible without intervention.
- *Mitigation:* The knowledge base is the immutable anchor. Every flywheel
  cycle validates against the original StatsCan/CBA benchmarks, not against
  previous synthetic output. Tail-distribution monitoring (Layer 2) catches
  mode collapse early.
- *Fallback:* Hard reset to knowledge base if tail-distribution deviation
  exceeds 15%.

**Risk 3: Privacy Leakage Through Memorization**
- *Problem:* If the knowledge base or generator memorizes specific real
  individuals from aggregate statistics, synthetic records could be
  re-identifiable.
- *Severity:* Medium -- the generator uses statistical distributions, not
  individual records, but edge cases exist.
- *Mitigation:* privacy.py implements DCR (Distance to Closest Record), NNDR
  (Nearest Neighbor Distance Ratio), and MIA (Membership Inference Attack)
  resistance. Records too close to any real data point are rejected.

**Risk 4: Regulatory Drift**
- *Problem:* Canadian regulatory parameters change (e.g., OSFI qualifying rate
  adjustments, new FINTRAC thresholds).
- *Severity:* Low -- parameters are explicit in knowledge_base.py, easy to
  update.
- *Mitigation:* Regulatory parameters are isolated in a single method
  (`_load_regulatory_parameters`). Quarterly review cadence.

### 3.4 Dependencies

| Dependency                        | Status      | Risk  |
|-----------------------------------|-------------|-------|
| Cortex quality framework          | Production  | None  |
| Cortex learning system            | Production  | None  |
| Python 3.11+                      | Available   | None  |
| scipy (statistical tests)         | pip install | None  |
| scikit-learn (discriminator)      | pip install | None  |
| xgboost (discriminator)           | pip install | Low   |
| shap (feedback explanations)      | pip install | Low   |

---

## 4. Solution Design (The "How")

### 4.1 System Architecture

```
                        CORTEX SYNTHFINSERV v2 — SYSTEM ARCHITECTURE
 ==================================================================================

                                  CLI / Bridge API
                                       |
                                       v
                          +------------------------+
                          |    GenerationRequest    |
                          |  type, count, segment,  |
                          |  province, risk_profile |
                          +------------------------+
                                       |
                                       v
  +-------------+            +------------------+
  | Knowledge   |----------->|    generator.py   |
  | Base (9     |  constrain |  Statistical      |
  | constraints)|            |  sampling +       |
  +-------------+            |  correlated       |
        ^                    |  field generation  |
        |                    +------------------+
        |                            |
        | anchor                     | raw records
        |                            v
        |                    +------------------+
        |                    |   quality.py      |
        |                    |   6-dimension     |
        |                    |   per-record      |
        |                    |   scoring         |
        |                    +------------------+
        |                            |
        |                            | scored records
        |                            v
  +-----+------+            +==================+
  | Knowledge  |<===========|   flywheel.py     |
  | Base       | corrections|   7-Layer         |
  | (immutable |            |   Feedback        |
  |  anchor)   |            |   Orchestrator    |
  +------------+            +==================+
                                     |
                      +--------------+--------------+
                      |              |              |
                      v              v              v
              +-------------+ +-----------+ +------------+
              | constraints | | discrim.  | | risk_      |
              | .py         | | .py       | | validator  |
              | KS, chi-sq, | | XGBoost + | | .py        |
              | JSD tests   | | SHAP      | | AML rule   |
              +-------------+ +-----------+ | engine     |
                      |              |       +------------+
                      v              v              |
              +-------------+ +-----------+        v
              | tstr.py     | | privacy   | +-----------+
              | Train-Synth | | .py       | | Adversar. |
              | Test-Real   | | DCR, NNDR | | loop      |
              +-------------+ | MIA       | +-----------+
                              +-----------+
                                     |
                                     v
                            +------------------+
                            | GenerationResult  |
                            | records, quality, |
                            | flywheel_id       |
                            +------------------+
                                     |
                                     v
                            JSONL / JSON / CSV
                            ~/.cortex/synthetic/
```

### 4.2 The 7-Layer Feedback Flywheel

The flywheel is the core differentiator. Each layer operates independently,
detects a specific class of quality degradation, and routes corrections back
to the generator. The layers execute sequentially on every generation batch.

```
  THE 7-LAYER FEEDBACK FLYWHEEL
  ==============================

  Layer 1: Quality Gate (quality.py)
  |  Per-record 6-dimension scoring. Records below threshold are rejected.
  |  FEEDBACK: Rejection rate trends -> adjust generation parameters
  |
  v
  Layer 2: Statistical Fidelity (constraints.py)
  |  Batch-level distribution tests (KS, chi-squared, JSD) against
  |  knowledge base benchmarks. Detects marginal AND joint drift.
  |  FEEDBACK: Deviation vectors -> recalibrate sampling weights
  |
  v
  Layer 3: Cross-Field Consistency (quality.py + constraints.py)
  |  Validates multivariate relationships (income~segment, credit~age,
  |  digital_adoption~age, tenure~age). Uses conditional distributions.
  |  FEEDBACK: Inconsistency patterns -> adjust correlation matrices
  |
  v
  Layer 4: Risk Model Validation (risk_validator.py)
  |  AML rule engine pass-through: validates that suspicious transactions
  |  trigger expected FINTRAC rules and normal transactions do not.
  |  FEEDBACK: False positive/negative rates -> tune risk pattern params
  |
  v
  Layer 5: Discriminator Feedback (discriminator.py)
  |  XGBoost classifier tries to distinguish synthetic from real aggregate
  |  stats. SHAP values identify which features are most distinguishable.
  |  FEEDBACK: Top SHAP features -> targeted distribution refinement
  |
  v
  Layer 6: Downstream Task Validation (tstr.py)
  |  Train-on-Synthetic, Test-on-Real: trains a model on synthetic data
  |  and evaluates on held-out real aggregate benchmarks.
  |  FEEDBACK: Task performance delta -> prioritize generation improvements
  |
  v
  Layer 7: Privacy Audit (privacy.py)
  |  DCR, NNDR, and MIA resistance checks. Ensures no synthetic record
  |  is too close to a real individual.
  |  FEEDBACK: Privacy violations -> increase noise in affected dimensions
  |
  v
  [All 7 layers report to flywheel.py orchestrator]
  [Orchestrator aggregates feedback, prioritizes corrections, triggers
   next generation cycle with updated parameters]
```

**Anti-Collapse Safeguard:** The knowledge base is the immutable anchor. No
flywheel layer can modify the knowledge base constraints. Layers can only adjust
generation parameters (sampling weights, correlation matrices, noise levels)
within bounds defined by the knowledge base. If any dimension deviates more
than 15% from its knowledge base anchor, the flywheel triggers a hard reset
for that dimension.

### 4.3 Module Structure

```
cortex/synthetic/
|-- __init__.py                  # v0.1.0, module exports
|-- schemas.py                   # CustomerProfile, Transaction, GenerationRequest,
|                                # GenerationResult dataclasses
|-- knowledge_base.py            # 9 Canadian FinServ distribution constraints
|                                # + regulatory parameters (OSFI, FINTRAC, CMHC)
|-- generator.py                 # Statistical sampling + correlated field generation
|                                # Hybrid: statistical primary, LLM enrichment optional
|-- quality.py                   # 6-dimension quality validator (per-record + batch)
|-- constraints.py               # NEW: Statistical constraint engine
|                                #   - Kolmogorov-Smirnov test (continuous)
|                                #   - Chi-squared test (categorical)
|                                #   - Jensen-Shannon divergence (all distributions)
|                                #   - Joint distribution validation
|-- discriminator.py             # NEW: Synthetic vs. real discriminator
|                                #   - XGBoost binary classifier
|                                #   - SHAP feature importance feedback
|                                #   - Target: AUC < 0.65 (near-random)
|-- risk_validator.py            # NEW: AML rule engine validation
|                                #   - FINTRAC threshold checks
|                                #   - Suspicious pattern detection rules
|                                #   - Adversarial generation loop
|                                #   - False positive/negative rate tracking
|-- tstr.py                      # NEW: Train-on-Synthetic, Test-on-Real utility
|                                #   - Downstream task benchmarking
|                                #   - Performance delta measurement
|                                #   - Task: credit scoring, AML detection
|-- privacy.py                   # NEW: Privacy guarantee engine
|                                #   - DCR (Distance to Closest Record)
|                                #   - NNDR (Nearest Neighbor Distance Ratio)
|                                #   - MIA (Membership Inference Attack) resistance
|                                #   - Record-level privacy scoring
|-- flywheel.py                  # NEW: 7-layer orchestrator
|                                #   - Runs all layers sequentially
|                                #   - Aggregates feedback vectors
|                                #   - Prioritizes corrections by impact
|                                #   - Triggers recalibration or hard reset
|                                #   - Logs cycle metrics for trend analysis
|-- demo_synthetic.py            # Interactive demo (6 scenarios)
|-- docs/
|   |-- PRD.md                   # Product Requirements Document
|   |-- TECHNICAL_PAPER.md       # Academic-style technical paper
|   +-- GOLDEN_SPEC_V2.md        # This document
+-- tests/
    |-- test_generator.py        # 23 tests (PASSING)
    |-- test_constraints.py      # NEW: statistical test validation
    |-- test_discriminator.py    # NEW: discriminator accuracy bounds
    |-- test_risk_validator.py   # NEW: AML rule engine coverage
    +-- test_flywheel.py         # NEW: end-to-end flywheel cycle
```

### 4.4 Key Module Designs

#### 4.4.1 constraints.py -- Statistical Constraint Engine

```python
class StatisticalConstraintEngine:
    """
    Validates synthetic data distributions against knowledge base anchors
    using rigorous statistical tests.
    """

    def ks_test(self, synthetic: array, reference: array) -> KSResult:
        """Kolmogorov-Smirnov test for continuous distributions.
        Returns: statistic, p_value, passes (p > 0.05)"""

    def chi_squared_test(self, synthetic: dict, reference: dict) -> ChiSqResult:
        """Chi-squared goodness-of-fit for categorical distributions.
        Returns: statistic, p_value, passes"""

    def jsd(self, synthetic: dict, reference: dict) -> float:
        """Jensen-Shannon Divergence (symmetric, bounded [0,1]).
        Target: JSD < 0.05 for each dimension."""

    def validate_joint(self, synthetic_df, dimensions: list) -> JointResult:
        """Validate joint distributions across multiple dimensions.
        Uses chi-squared on cross-tabulations."""

    def compute_deviation_vector(self, synthetic_batch, kb) -> dict:
        """Returns per-dimension deviation from knowledge base.
        Used by flywheel to prioritize corrections."""
```

#### 4.4.2 risk_validator.py -- AML Rule Engine

```python
class AMLRuleEngine:
    """
    Validates synthetic transactions against FINTRAC reporting rules.
    Provides feedback for adversarial generation improvement.
    """

    # FINTRAC-aligned rules
    RULES = {
        "large_cash":        lambda t: t.amount >= 10000 and t.type == "deposit",
        "structuring":       lambda t: 9000 <= t.amount < 10000,
        "rapid_movement":    lambda t: t.in_out_delta_hours < 48,
        "geographic_risk":   lambda t: t.country_code in HIGH_RISK_JURISDICTIONS,
        "unusual_volume":    lambda t: t.amount > 3 * t.baseline_avg,
        "round_amounts":     lambda t: t.amount % 1000 == 0 and t.amount >= 5000,
        "dormant_reactivation": lambda t: t.days_since_last > 180,
    }

    def validate_batch(self, transactions) -> ValidationReport:
        """Run all rules against a batch. Returns detection rates."""

    def adversarial_loop(self, generator, n_rounds=5) -> LoopResult:
        """Generator tries to produce undetectable fraud patterns.
        Rule engine validates. Failures feed back to generator.
        Converges when detection rate > 90%."""
```

#### 4.4.3 discriminator.py -- XGBoost Discriminator + SHAP Feedback

```python
class SyntheticDiscriminator:
    """
    Trains XGBoost to distinguish synthetic from real aggregate statistics.
    SHAP values identify which features need the most improvement.

    Target: AUC < 0.65 (synthetic is indistinguishable from real).
    """

    def train(self, synthetic_stats: DataFrame, real_stats: DataFrame):
        """Train binary classifier. 'real' stats come from published
        aggregate benchmarks (StatsCan, CBA), not individual records."""

    def evaluate(self) -> DiscriminatorResult:
        """Returns AUC, accuracy, and top SHAP feature importances."""

    def get_feedback(self) -> dict:
        """Returns ranked list of features to improve, with direction
        (too high / too low / wrong shape) from SHAP analysis."""
```

#### 4.4.4 flywheel.py -- 7-Layer Orchestrator

```python
class SynthFlywheel:
    """
    Orchestrates the 7-layer feedback loop.
    Runs after every generation batch.
    """

    def __init__(self, kb, generator, quality, constraints,
                 discriminator, risk_validator, tstr, privacy):
        self.layers = [
            ("quality_gate",      quality),
            ("stat_fidelity",     constraints),
            ("cross_field",       quality),       # reused with joint mode
            ("risk_validation",   risk_validator),
            ("discriminator",     discriminator),
            ("downstream_task",   tstr),
            ("privacy_audit",     privacy),
        ]

    def run_cycle(self, batch, request) -> FlywheelReport:
        """Execute all 7 layers, aggregate feedback, return report."""

    def apply_corrections(self, feedback: dict) -> None:
        """Apply feedback to generator parameters.
        Bounded by knowledge base constraints (anti-collapse)."""

    def should_hard_reset(self, deviation_vector: dict) -> bool:
        """Returns True if any dimension > 15% from KB anchor."""
```

### 4.5 Integration Points

```
  INTEGRATION MAP
  ===============

  bridge.py                           config.py
  +----------------------------+      +------------------+
  | generate_synthetic()       |      | synthetic_enabled|
  |   data_type, count,        |      | : bool = True    |
  |   segment, province,       |      +------------------+
  |   risk_profile, format     |
  +----------------------------+
              |
              v
  generator.py --> flywheel.py --> quality.py
                                   constraints.py
                                   risk_validator.py
                                   discriminator.py
                                   tstr.py
                                   privacy.py
              |
              v
  CLI: python cortex/cli.py synthetic
       --type profiles|transactions
       --count N
       --segment mass_market|mass_affluent|affluent|...
       --province ON|QC|BC|AB|...
       --risk-profile low|medium|high
       --format jsonl|json|csv
       --flywheel (enable 7-layer feedback)
       --output /path/to/output
```

### 4.6 Data Flow: End-to-End Generation Cycle

```
  REQUEST                GENERATE              VALIDATE                FEEDBACK
  =======                ========              ========                ========

  User calls             generator.py          quality.py              flywheel.py
  bridge.generate_       samples from          scores each             runs 7 layers
  synthetic()            knowledge_base        record (6 dim)          on batch
       |                 distributions              |                       |
       |                      |                     |                       |
       v                      v                     v                       v
  GenerationRequest ---> Raw records ---------> Scored records -------> Corrections
       |                                            |                       |
       |                                            v                       v
       |                                      Filter by              Apply to next
       |                                      min_quality            generation
       |                                            |                cycle params
       |                                            v                       |
       |                                      GenerationResult              |
       |                                      + flywheel_id                 |
       |                                            |                       |
       +----<--- outcome_log ----<--- usage ---<----+----->--- output ----->+
                                      feedback
                                      (future:
                                      client API)
```

---

## 5. Solution-Outcome Alignment

### 5.1 Outcome-to-Component Mapping

| # | Outcome                                          | Primary Component    | Validation Method                          | Target                   |
|---|--------------------------------------------------|----------------------|--------------------------------------------|--------------------------|
| O1 | StatsCan-calibrated synthetic profiles           | generator.py + knowledge_base.py | KS test, chi-sq, JSD per dimension | < 5% max deviation       |
| O2 | FINTRAC-compliant AML risk patterns              | generator.py + risk_validator.py | AML rule engine pass-through       | > 90% detection rate     |
| O3 | 6-dimension quality scoring per record           | quality.py           | Unit tests, batch assessment               | avg > 0.85 (profiles)   |
| O4 | 7-layer automated feedback flywheel              | flywheel.py          | Cycle-over-cycle quality trend             | > 2% improvement/cycle  |
| O5 | Risk model feedback loop                         | risk_validator.py + flywheel.py | Adversarial loop convergence      | Converge in < 5 rounds  |
| O6 | Bridge API + CLI access                          | bridge.py + cli.py   | Integration tests                          | All commands functional  |
| O7 | JSONL, JSON, CSV output                          | generator.py         | Output format tests                        | Valid parse by pandas    |

### 5.2 Flywheel Layer-to-Outcome Mapping

| Layer | Name                  | Outcomes Served | Failure Mode Detected                |
|-------|-----------------------|-----------------|--------------------------------------|
| 1     | Quality Gate          | O3              | Per-record quality degradation       |
| 2     | Statistical Fidelity  | O1              | Marginal/joint distribution drift    |
| 3     | Cross-Field Consistency| O1, O3         | Unrealistic multivariate combos      |
| 4     | Risk Model Validation | O2, O5          | AML pattern false pos/neg            |
| 5     | Discriminator Feedback| O1              | Synthetic detectability              |
| 6     | Downstream Task       | O1, O2          | Synthetic data utility gap           |
| 7     | Privacy Audit         | (privacy)       | Re-identification risk               |

### 5.3 Coverage Analysis

Every outcome is covered by at least one flywheel layer. Every flywheel layer
feeds back into at least one outcome. There are no orphaned components.

```
  COVERAGE MATRIX (X = primary, o = secondary)
  =============================================

              O1   O2   O3   O4   O5   O6   O7
  Layer 1      o         X    o
  Layer 2      X              o
  Layer 3      X         o    o
  Layer 4           X              X
  Layer 5      X              o
  Layer 6      o    o              o
  Layer 7                     o

  generator         X    X              X         X
  knowledge_base    X    o
  quality           o         X
  bridge/cli                            o    X    X
```

---

## 6. Implementation Planning

### 6.1 Phase Overview

```
  IMPLEMENTATION ROADMAP
  ======================

  Phase 1 (DONE)          Phase 2 (NEXT)         Phase 3              Phase 4
  MEP Foundation          Risk + Fidelity        Discriminator +      Privacy +
                                                 TSTR                 Enterprise
  +-----------------+     +-----------------+    +-----------------+  +----------------+
  | schemas.py      |     | constraints.py  |    | discriminator.py|  | privacy.py     |
  | knowledge_base  |     | risk_validator  |    | tstr.py         |  | API endpoints  |
  | generator.py    |     | adversarial loop|    | SHAP feedback   |  | Client outcome |
  | quality.py      |     | flywheel.py     |    | Downstream task |  | ingestion      |
  | demo_synthetic  |     | (layers 1-4)    |    | benchmarks      |  | Enterprise     |
  | test_generator  |     | test_constraints|    | (layers 5-6)    |  | auth + billing |
  | bridge.py wire  |     | test_risk_valid.|    | test_discrim.   |  | (layer 7)      |
  +-----------------+     | test_flywheel   |    +-----------------+  +----------------+
                          +-----------------+
  23/23 tests             Dependencies:          Dependencies:        Dependencies:
  100 profiles <0.1s      scipy, numpy           xgboost, shap,       FastAPI,
  9 constraints                                  scikit-learn         auth middleware
```

### 6.2 Phase 1: MEP Foundation (COMPLETE)

**Status:** Done. All components production-tested.

| Component         | File                    | Tests | Status   |
|-------------------|-------------------------|-------|----------|
| Data schemas      | schemas.py              | 3/3   | COMPLETE |
| Knowledge base    | knowledge_base.py       | 8/8   | COMPLETE |
| Generator engine  | generator.py            | 7/7   | COMPLETE |
| Quality validator | quality.py              | 5/5   | COMPLETE |
| Bridge integration| bridge.py               | Wired | COMPLETE |
| Interactive demo  | demo_synthetic.py       | --    | COMPLETE |

**Deliverables:**
- [x] CustomerProfile, Transaction, GenerationRequest, GenerationResult schemas
- [x] 9 distribution constraints from public Canadian sources
- [x] Statistical sampling with correlated field generation
- [x] 6-dimension per-record quality scoring
- [x] Batch distribution fidelity assessment
- [x] AML risk flag generation (7 suspicious patterns)
- [x] JSONL/JSON/CSV output
- [x] Outcome logging for flywheel tracking
- [x] 23/23 tests passing

### 6.3 Phase 2: Risk Model + Statistical Fidelity (NEXT)

**Goal:** Close the feedback loop. Move from generate-and-forget to
generate-validate-correct. Implement flywheel layers 1-4.

| Component                | File                | Depends On          |
|--------------------------|---------------------|---------------------|
| Statistical constraint engine | constraints.py | scipy, knowledge_base.py |
| AML rule engine          | risk_validator.py   | schemas.py, knowledge_base.py |
| Adversarial generation loop | risk_validator.py| generator.py        |
| Flywheel orchestrator (L1-4) | flywheel.py    | All above           |
| Constraint tests         | test_constraints.py | constraints.py      |
| Risk validator tests     | test_risk_validator.py | risk_validator.py |
| Flywheel integration tests | test_flywheel.py | flywheel.py         |

**constraints.py Deliverables:**
- [ ] KS test for continuous dimensions (income, credit score, age, tenure)
- [ ] Chi-squared test for categorical dimensions (province, segment, products)
- [ ] JSD for all distributions (unified metric)
- [ ] Joint distribution validation (cross-tabulation chi-squared)
- [ ] Deviation vector computation (per-dimension feedback for flywheel)
- [ ] Anti-collapse bounds checking (15% hard reset threshold)

**risk_validator.py Deliverables:**
- [ ] FINTRAC rule implementation (7 rules matching knowledge_base.py red flags)
- [ ] Batch validation with detection rate reporting
- [ ] Adversarial loop (generator vs. rule engine, converge in 5 rounds)
- [ ] False positive/negative rate tracking
- [ ] Rule coverage report (which patterns are well-represented)

**flywheel.py Deliverables (Layers 1-4):**
- [ ] Layer execution pipeline (sequential, fault-tolerant)
- [ ] Feedback aggregation (weighted by layer confidence)
- [ ] Correction application (bounded by knowledge base)
- [ ] Cycle logging (metrics for trend analysis)
- [ ] Hard reset trigger (any dimension > 15% deviation)

**Test Targets:**
- [ ] test_constraints.py: 15+ tests (KS, chi-sq, JSD, joint, bounds)
- [ ] test_risk_validator.py: 12+ tests (each rule, adversarial loop, rates)
- [ ] test_flywheel.py: 10+ tests (cycle execution, feedback, reset)

### 6.4 Phase 3: Discriminator + TSTR

**Goal:** Add external validation layers. Can a classifier tell synthetic from
real? Does synthetic data perform comparably in downstream tasks?

| Component                | File                | Depends On               |
|--------------------------|---------------------|--------------------------|
| XGBoost discriminator    | discriminator.py    | xgboost, scikit-learn    |
| SHAP feedback extraction | discriminator.py    | shap                     |
| TSTR utility             | tstr.py             | scikit-learn             |
| Flywheel layers 5-6      | flywheel.py update  | discriminator.py, tstr.py|
| Discriminator tests      | test_discriminator.py | discriminator.py       |

**discriminator.py Deliverables:**
- [ ] XGBoost binary classifier (synthetic=1, real_aggregate=0)
- [ ] Train/eval split with cross-validation
- [ ] AUC, accuracy, precision, recall reporting
- [ ] SHAP value extraction per feature
- [ ] Ranked feedback: which features are most distinguishable
- [ ] Direction feedback: each feature too high / too low / wrong shape

**tstr.py Deliverables:**
- [ ] TSTR framework for arbitrary downstream tasks
- [ ] Built-in task: credit score prediction (synthetic train -> real test)
- [ ] Built-in task: AML detection (synthetic train -> rule engine test)
- [ ] Performance delta reporting (synthetic vs. real training performance)

**Test Targets:**
- [ ] test_discriminator.py: 8+ tests (training, eval, SHAP, feedback)

### 6.5 Phase 4: Privacy + Enterprise

**Goal:** Production hardening. Privacy guarantees, API endpoints, client
outcome ingestion for closing the external feedback loop.

| Component                | File                | Depends On              |
|--------------------------|---------------------|-------------------------|
| Privacy engine           | privacy.py          | scipy, scikit-learn     |
| Flywheel layer 7         | flywheel.py update  | privacy.py              |
| API endpoints            | (FastAPI routes)    | bridge.py               |
| Client outcome ingestion | (API route)         | flywheel.py             |
| Enterprise auth          | (middleware)        | TBD                     |

**privacy.py Deliverables:**
- [ ] DCR: Distance to Closest Record (target > 0.05)
- [ ] NNDR: Nearest Neighbor Distance Ratio (target > 0.5)
- [ ] MIA: Membership Inference Attack simulation
- [ ] Per-record privacy score
- [ ] Batch privacy report
- [ ] Noise injection calibration (increase noise for low-privacy dimensions)

**API Deliverables:**
- [ ] POST /api/v1/synthetic/generate (async generation)
- [ ] GET /api/v1/synthetic/status/{flywheel_id} (generation status)
- [ ] GET /api/v1/synthetic/download/{flywheel_id} (retrieve output)
- [ ] POST /api/v1/synthetic/feedback/{flywheel_id} (client outcome)
- [ ] GET /api/v1/synthetic/quality/report (quality trends)

---

## 7. Success Verification

### 7.1 Test Suite

| Test File               | Test Count | Coverage                              |
|-------------------------|------------|---------------------------------------|
| test_generator.py       | 23         | Schemas, KB, generator, quality       |
| test_constraints.py     | 15+        | KS, chi-sq, JSD, joint, bounds        |
| test_risk_validator.py  | 12+        | 7 AML rules, adversarial, rates       |
| test_discriminator.py   | 8+         | Train, eval, SHAP, feedback           |
| test_flywheel.py        | 10+        | Cycle, feedback, reset, logging       |
| **Total**               | **68+**    |                                       |

**Test Commands:**
```bash
# All synthetic tests
pytest cortex/synthetic/tests/ -v

# By module
pytest cortex/synthetic/tests/test_generator.py -v
pytest cortex/synthetic/tests/test_constraints.py -v
pytest cortex/synthetic/tests/test_risk_validator.py -v
pytest cortex/synthetic/tests/test_discriminator.py -v
pytest cortex/synthetic/tests/test_flywheel.py -v

# With coverage
pytest cortex/synthetic/tests/ -v --cov=cortex/synthetic --cov-report=term-missing
```

### 7.2 Benchmark Suite

| Benchmark                     | Method                    | Target              | Frequency    |
|-------------------------------|---------------------------|---------------------|--------------|
| Generation throughput         | Wall-clock, 1000 profiles | < 1 second          | Every commit |
| Distribution fidelity (KS)   | KS test per dimension     | p > 0.05 all dims   | Every batch  |
| Distribution fidelity (JSD)  | JSD per dimension         | JSD < 0.05 all dims | Every batch  |
| Quality score average         | 6-dim weighted mean       | > 0.85 profiles     | Every batch  |
| AML detection rate            | Rule engine coverage      | > 90%               | Every batch  |
| Discriminator AUC             | XGBoost 5-fold CV         | < 0.65              | Weekly       |
| TSTR delta                    | Synthetic vs. real train  | < 5% accuracy gap   | Weekly       |
| Privacy DCR                   | Min distance to real      | > 0.05              | Every batch  |
| Privacy NNDR                  | Nearest-neighbor ratio    | > 0.5               | Every batch  |
| Flywheel convergence          | Cycles to stable quality  | < 5 cycles          | On demand    |

### 7.3 Demo Scenarios

The demo suite (`demo_synthetic.py`) validates end-to-end functionality:

| Demo | Scenario                              | Validates                           |
|------|---------------------------------------|-------------------------------------|
| 1    | Generate 100 mixed-segment profiles   | Core generation, quality scoring    |
| 2    | Generate 50 mass-affluent ON profiles | Segment + province targeting        |
| 3    | Distribution fidelity vs StatsCan     | Batch-level statistical tests       |
| 4    | 200 transactions with high risk       | AML pattern generation              |
| 5    | Knowledge base inspection             | Constraint loading, regulatory params|
| 6    | Outcome flywheel log                  | Outcome tracking, flywheel readiness|
| 7    | (NEW) Flywheel cycle demonstration    | 7-layer feedback in action          |
| 8    | (NEW) Adversarial AML loop            | Risk validator convergence          |

### 7.4 Acceptance Criteria by Phase

**Phase 1 (DONE):**
- [x] 23/23 tests passing
- [x] 100 profiles generated in < 0.1 seconds
- [x] 9 distribution constraints loaded and validated
- [x] Quality scores average > 0.85
- [x] JSONL/JSON/CSV output functional
- [x] bridge.py integration working
- [x] Outcome logging to generation_outcomes.jsonl

**Phase 2 (IN PROGRESS):**
- [ ] constraints.py passes all statistical test validations
- [ ] risk_validator.py achieves > 90% AML detection rate
- [ ] Adversarial loop converges in < 5 rounds
- [ ] flywheel.py executes layers 1-4 without error
- [ ] Cycle-over-cycle quality improvement > 2%
- [ ] 37+ new tests passing (constraints + risk + flywheel)
- [ ] No dimension deviates > 15% from KB anchor after flywheel cycle

**Phase 3:**
- [ ] Discriminator AUC < 0.65 (synthetic near-indistinguishable)
- [ ] SHAP feedback identifies top 3 features for improvement
- [ ] TSTR accuracy gap < 5% on credit scoring task
- [ ] TSTR accuracy gap < 5% on AML detection task
- [ ] 8+ new tests passing

**Phase 4:**
- [ ] DCR > 0.05 on all generated batches
- [ ] NNDR > 0.5 on all generated batches
- [ ] MIA attack success rate < 55% (near random)
- [ ] API endpoints functional with auth
- [ ] Client outcome ingestion working end-to-end
- [ ] 68+ total tests passing

### 7.5 What Gets Deployed

Per Cortex convention: if it validates, it deploys. No orphaned validated code.

| Phase | Validates                          | Deploys To                        |
|-------|------------------------------------|-----------------------------------|
| 1     | MEP generation + quality           | bridge.py, CLI, ~/.cortex/synthetic/ |
| 2     | Flywheel layers 1-4                | flywheel.py auto-runs on generate |
| 3     | Discriminator + TSTR               | flywheel.py layers 5-6 added     |
| 4     | Privacy + API                      | FastAPI endpoints, layer 7 added |

**Deployment verification:** After each phase, run `pytest cortex/synthetic/tests/ -v`
and confirm all tests green before merging to main.

---

## Appendix A: Knowledge Base Constraint Summary

| #  | Constraint               | Dimension           | Source                          | Year |
|----|--------------------------|---------------------|---------------------------------|------|
| 1  | Province distribution    | province            | StatsCan Census 2021            | 2021 |
| 2  | Age distribution (18+)   | age                 | StatsCan Census 2021            | 2021 |
| 3  | Income distribution      | annual_income       | StatsCan Table 11-10-0239-01    | 2022 |
| 4  | Segment distribution     | segment             | Big 5 Annual Reports aggregate  | 2024 |
| 5  | Credit score distribution| credit_score        | Equifax Canada Credit Trends    | 2024 |
| 6  | Product penetration      | products_held       | CBA Financial Statistics        | 2024 |
| 7  | Products per customer    | products_per_household | Big 5 Cross-Sell Metrics     | 2024 |
| 8  | Digital adoption         | digital_adoption    | CBA Digital Banking Survey      | 2024 |
| 9  | Primary channel          | primary_channel     | CBA Digital Banking Survey      | 2024 |

## Appendix B: AML Risk Pattern Definitions

| Pattern              | FINTRAC Basis                    | Synthetic Implementation              |
|----------------------|----------------------------------|---------------------------------------|
| Structuring          | Multiple txns < $10K threshold   | Amount range: $9,000--$9,999          |
| Rapid Movement       | In-and-out within 24-48 hours    | Deposit + withdrawal, delta < 48h     |
| Geographic Risk      | High-risk jurisdiction txns      | Wire to IR, KP, SY, MM, AF           |
| Unusual Volume       | 3x+ baseline transaction volume  | Amount > 3x segment average           |
| Round Amounts        | Repeated exact round transfers   | Amount in {5K, 10K, 15K, 20K, 25K, 50K} |
| Dormant Reactivation | Inactive > 6 months, then active | days_since_last > 180                 |
| Third-Party Deposits | Deposits from unrelated parties  | Mismatched profile_id counterparty    |

## Appendix C: Quality Dimension Weights

| Dimension    | Weight | Rationale                                            |
|--------------|--------|------------------------------------------------------|
| Completeness | 0.15   | All fields populated                                 |
| Consistency  | 0.25   | Cross-field coherence is critical for financial data |
| Accuracy     | 0.25   | Values within realistic Canadian market ranges       |
| Timeliness   | 0.05   | Synthetic data is always fresh (low discriminative)  |
| Uniqueness   | 0.15   | No duplicate records                                 |
| Validity     | 0.15   | Schema compliance, enum validation                   |

**Weighted overall score:** `sum(dimension_score * weight)`

## Appendix D: Glossary

| Term   | Definition                                                          |
|--------|---------------------------------------------------------------------|
| CBA    | Canadian Bankers Association                                        |
| CMHC   | Canada Mortgage and Housing Corporation                             |
| CPPA   | Consumer Privacy Protection Act (proposed federal)                  |
| DCR    | Distance to Closest Record (privacy metric)                        |
| FSA    | Forward Sortation Area (first 3 characters of Canadian postal code) |
| GDS    | Gross Debt Service ratio                                            |
| JSD    | Jensen-Shannon Divergence                                           |
| KS     | Kolmogorov-Smirnov (statistical test)                               |
| MEP    | Minimum Evolvable Product                                           |
| MIA    | Membership Inference Attack                                         |
| NNDR   | Nearest Neighbor Distance Ratio (privacy metric)                    |
| OSFI   | Office of the Superintendent of Financial Institutions              |
| PIPEDA | Personal Information Protection and Electronic Documents Act        |
| SHAP   | SHapley Additive exPlanations                                       |
| STR    | Suspicious Transaction Report                                       |
| TDS    | Total Debt Service ratio                                            |
| TSTR   | Train on Synthetic, Test on Real                                    |

---

*This Golden Spec supersedes `cortex/synthetic/GOLDEN_SPEC.md` (v1). The v1 spec
remains as historical reference. All new development follows v2.*

*Spec authored per Cortex Golden Spec convention: 7 phases, dependencies only
(no time estimates), outcomes mapped to components, validation at every layer.*
