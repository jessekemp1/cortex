# Golden Spec: Cortex Synthetic Data Engine
## Codename: SynthFinServ

---

## 1. Deep Understanding (The "Why")

### Problem
Canadian financial institutions (Big 5 banks, insurers, fintechs) face a structural conflict:
- **PIPEDA**, **Quebec Law 25**, and **OSFI guidelines** increasingly restrict use of real customer data for market research, model training, and competitive analysis
- Yet the demand for realistic, granular data to train ML models, test scenarios, and research markets has never been higher
- Current synthetic data solutions generate plausible-looking data with no feedback loop — they produce records that *look* right but nobody validates whether they *behave* right when used downstream

### Why Cortex Is Uniquely Positioned
Cortex already has the hard parts built:
- **Quality-weighted learning** (6-dimension framework) — not all data points are equal
- **Outcome flywheel** — generation improves from usage feedback, continuously
- **Hybrid retrieval** (BM25 + embeddings + RRF) — sources patterns from diverse, heterogeneous data
- **AI-as-Judge** (discrete 1-5 scoring) — automated quality validation
- **Tiered memory** (487x recency weighting) — reflects current market conditions

No competitor has this feedback loop. Traditional synthetic data is generate-and-forget.

### Outcome
Clear understanding that the moat is the **outcome flywheel** applied to synthetic data, not the generation itself.

---

## 2. Outcome Definition (The "What")

### Primary Outcomes
1. **Generate synthetic Canadian FinServ datasets** that pass statistical distribution tests against real market data (StatsCan, CMHC, BoC benchmarks)
2. **Quality-score every record** using Cortex's 6-dimension framework adapted for financial data
3. **Learn from usage outcomes** — when clients use the data and report results, the next batch improves
4. **Serve three high-impact use cases**:
   - Customer profile generation (demographics + financial behavior)
   - Transaction data generation (AML/KYC training focus)
   - Market scenario generation (competitive intelligence)

### Success Criteria
- Generated profiles match Canadian demographic distributions within 5% of StatsCan benchmarks
- Quality scores average >0.8 across all six dimensions
- Outcome flywheel demonstrates measurable improvement between generation cycles
- CLI-accessible: `python cortex/cli.py synthetic --type profiles --count 1000 --segment prime-mortgage`

---

## 3. Outcome Validation (The "Reality Check")

### Feasibility
- **Core infrastructure exists**: Quality framework, hybrid retriever, learning system, AI judge — all production-tested
- **Knowledge base buildable**: StatsCan data is public, OSFI parameters are published, bank product mixes are in annual reports
- **LLM generation proven**: Claude can generate constrained, schema-valid records when given distribution parameters
- **Canadian market concentrated**: Big 5 + Big 3 insurers = addressable with focused domain expertise

### Risks
- **Distribution fidelity**: LLM generation may drift from target distributions — mitigated by statistical constraint engine
- **Regulatory nuance**: Provincial variations (Quebec Law 25 vs. rest of Canada) — mitigated by region-aware constraints
- **Validation without real data**: Can't directly compare to real bank data — mitigated by using public aggregate benchmarks

### Dependencies
- Cortex quality framework (exists, production)
- Cortex learning system (exists, production)
- Anthropic API access (exists, configured)
- Canadian public data sources (free, accessible)

---

## 4. Solution Design (The "How")

### Architecture

```
cortex/synthetic/
├── __init__.py              # Module exports
├── GOLDEN_SPEC.md           # This document
├── schemas.py               # Dataclasses: Profile, Transaction, Scenario
├── knowledge_base.py        # Canadian FinServ distributions & constraints
├── generator.py             # Core LLM-based generation engine
├── profiles.py              # Customer profile generation
├── transactions.py          # Transaction data generation
├── scenarios.py             # Market scenario generation (future)
├── quality.py               # Quality validation adapted for synthetic FinServ data
├── constraints.py           # Statistical constraint engine
└── tests/
    ├── test_schemas.py
    ├── test_generator.py
    ├── test_profiles.py
    └── test_quality.py
```

### Integration Points
- **bridge.py**: New `generate_synthetic()` method (try/except import pattern)
- **cli.py**: New `cmd_synthetic()` command
- **config.py**: New `synthetic_enabled: bool` flag
- **learning.py**: Outcome logging for synthetic data usage

### Highest-Impact Use Cases (Build Order)

**UC1: Customer Profiles** (Foundation)
- Canadian demographic distribution (age, income, province, FSA)
- Financial product holdings (mortgage, TFSA, RRSP, credit cards)
- Credit profile (score ranges by segment)
- Behavioral signals (digital adoption, channel preference)

**UC2: Transaction Data** (Revenue — regulatory mandate)
- Normal transaction patterns by customer segment
- Suspicious transaction patterns (AML red flags)
- Cross-border transaction scenarios
- Temporal patterns (payroll cycles, seasonal spending)

**UC3: Market Scenarios** (Strategic — competitive intel)
- Rate environment scenarios (BoC policy changes)
- Competitive response simulations
- Customer migration patterns between institutions

---

## 5. Solution-Outcome Alignment

| Outcome | Component | Validation |
|---------|-----------|------------|
| Distribution fidelity | knowledge_base.py constraints | Chi-square test vs StatsCan |
| Quality scoring | quality.py (6 dimensions) | Average >0.8 across dimensions |
| Outcome flywheel | learning.py integration | Measurable improvement cycle-over-cycle |
| CLI accessible | cli.py cmd_synthetic() | `--type profiles --count N` works |
| Schema valid | schemas.py dataclasses | 100% schema validation pass rate |

---

## 6. Implementation Planning

### Phase 1: Minimum Evolvable Product (NOW)
- [ ] schemas.py — Profile, Transaction, GenerationRequest dataclasses
- [ ] knowledge_base.py — Canadian FinServ distributions (demographics, products, income)
- [ ] generator.py — Core generation engine (LLM + constraints)
- [ ] profiles.py — Customer profile generation
- [ ] quality.py — Adapted quality validator
- [ ] Wire into bridge.py + cli.py + config.py

### Phase 2: Transaction Engine
- [ ] transactions.py — Normal + suspicious pattern generation
- [ ] AML scenario templates
- [ ] Temporal pattern engine

### Phase 3: Market Scenarios
- [ ] scenarios.py — Competitive scenario generation
- [ ] Rate environment simulator
- [ ] Customer migration modeler

### Phase 4: Flywheel Maturity
- [ ] Client outcome ingestion API
- [ ] Distribution drift detection
- [ ] Automatic recalibration from outcomes

---

## 7. Success Verification

### Tests
- Schema validation: All generated records pass schema
- Distribution tests: Chi-square against known Canadian distributions
- Quality scores: Average >0.8 on 6 dimensions
- Integration: CLI generates, bridge queries, learning logs

### Demo
- Generate 100 synthetic Canadian banking customer profiles
- Show quality distribution (histogram of scores)
- Show demographic fidelity vs StatsCan benchmarks
- Run through outcome flywheel cycle
