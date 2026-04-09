# Pupil v1 Technical Spec

**Product**: Pupil  
**Built On**: SynthFinServ generation, validation, and privacy layers  
**Version**: 1.0  
**Status**: Execution-ready v1 spec  
**Owner**: Cortex Product and Engineering  
**Last Updated**: 2026-02-07

---

## 1. Problem and Outcome

### 1.1 Problem

Market research provides sparse, static snapshots with limited variables and weak temporal resolution.  
Teams need dense, scenario-ready synthetic populations that produce behavioral event trails and forecast paths with uncertainty.

### 1.2 v1 Outcome

Pupil v1 produces four release artifacts:

1. `population.csv`
   - Synthetic cohort state for each agent
2. `events.csv`
   - Timestamped behavioral event trail
3. `forecast.json`
   - Scenario forecasts with quantile uncertainty
4. `validation_report.md`
   - Fidelity, privacy, coherence, and calibration status

If all four artifacts are not generated in one run, v1 is incomplete.

---

## 2. Scope

### 2.1 In Scope

- Synthetic population generation from aggregate constraints
- Rule/probability-based agent behavior simulation
- Daily event trail generation
- Scenario simulation and forward forecasts
- Confidence and uncertainty outputs
- Validation and release gating

### 2.2 Out of Scope

- Person-level social media ingestion
- LLM persona generation tied to real users
- Global country coverage
- UI/dashboard productization
- Real-time distributed serving at very high scale

---

## 3. Safety and Data Policy

Pupil v1 must comply with `PUPIL_SAFE_MODELING_STANDARD.md`.

### 3.1 Required Inputs

- Aggregate public benchmarks (StatsCan/CBA/OSFI/other public statistical releases)
- Public macro time series
- Optional consented first-party telemetry aggregated to cohort-time buckets

### 3.2 Prohibited Inputs

- Individual social media profiles
- Scraped user-level data
- Personal identifiers and re-identification keys

---

## 4. System Design

## 4.1 Modules

```
pupil/                          # Top-level package at repo root
  __init__.py                   # v1.0.0, Canadian FinServ tagline
  __main__.py                   # Demo runner (python -m pupil)
  schema.py                     # Agent dataclass (~98 variables), enums, TrailEvent
  population.py                 # Bayesian network population generator (15 layers)
  behavior.py                   # Life event generation + decision engine
  engine.py                     # SimulationEngine (time-stepping)
  environment.py                # Environment, WorldState, MarketEvent
  prediction.py                 # Predictor (Monte Carlo ensemble forecasts)
  trail.py                      # TrailGenerator (daily behavioral data trails)
  tests/
    __init__.py
```

### 4.2 Data Flow

1. Ingest aggregate constraints and macro signals
2. Generate synthetic agent population
3. Simulate daily events over configured horizon
4. Run scenario ensemble forward simulation
5. Compute uncertainty and calibration
6. Run validation gates
7. Export required artifacts

---

## 5. Schemas

### 5.1 Population Record (`population.csv`)

Required columns (subset of ~98 total agent variables):

- `id` -- unique agent identifier (PUP-XXXXXXXXXX)
- `province` -- Canadian province/territory code (StatsCan Census 2021)
- `segment` -- FinancialSegment (mass_market, mass_affluent, affluent, hnwi)
- `age` -- 18-95
- `gender` -- male, female, non_binary
- `ethnicity` -- StatsCan visible minority categories
- `education` -- includes college_trade (key Canadian category)
- `annual_income` -- CAD, pre-tax individual income
- `net_worth` -- CAD, total assets minus liabilities
- `credit_score` -- 300-900 (Equifax/TransUnion Canada scale)
- `risk_tolerance` -- 0-1
- `price_sensitivity` -- 0-1
- `investment_participation` -- bool (RRSP/TFSA)
- `life_satisfaction` -- 0-1
- Plus ~85 additional variables across health, social, consumer, digital, values, routine, media, shopping, transport, and lifestyle domains

### 5.2 Event Record (`trail_30days.csv`)

Required columns (from `TrailEvent` schema):

- `agent_id`
- `day` -- day number in simulation
- `hour` -- hour of day (0.0-24.0)
- `event_type` -- purchase, meal, social_media, media, exercise, commute, social, health, search, location
- `category` -- subcategory (e.g., groceries, streaming, cardio)
- `amount` -- financial amount in CAD (nullable)
- `duration_minutes` -- time spent (nullable)
- `location_type` -- home, work, store, restaurant, gym, outdoors, transit
- `channel` -- online, in_store, mobile, app
- `brand` -- brand/vendor if applicable
- `sentiment` -- -1 to 1

### 5.3 Forecast Record (`forecast.json`)

Required fields:

- `scenario_name`
- `horizon_days`
- `metrics`:
  - `metric_name`
  - `p10`
  - `p50`
  - `p90`
  - `mean`
  - `std`
- `calibration`:
  - `ece` (expected calibration error)
  - `coverage_80`
  - `coverage_90`
- `model_uncertainty` summary

---

## 6. Behavior and Learning

### 6.1 Agent Dynamics

Each agent contains:

- Static attributes from synthetic population generation
- Dynamic state variables updated each timestep
- Policy parameters for action probabilities
- Memory features derived from recent history

### 6.2 Event Generation

At each day:

1. Read environment signals
2. Update latent drivers (financial pressure, confidence, stress)
3. Sample domain-specific actions from constrained probability models
4. Emit events
5. Update agent state and memory

### 6.3 Self-Learning (v1-safe)

Learning is aggregate-only:

- Update transition probabilities from forecast error on aggregate targets
- No per-person retraining or identity-linked memory
- Keep bounded updates with rollback on drift failures

---

## 7. Validation and Quality Gates

v1 release requires passing all gates.

### 7.1 Fidelity Gates

- Distribution fidelity against benchmark constraints
- Cross-field consistency checks
- Temporal coherence checks (no invalid state transitions)

### 7.2 Privacy Gates

- DCR pass
- NNDR pass
- MIA pass
- Sparse cell risk check pass

### 7.3 Forecast Gates

- Uncertainty intervals generated for all required metrics
- Calibration report generated (`ece`, coverage)
- Scenario sensitivity behaves directionally as expected

---

## 8. Acceptance Criteria

1. Population
   - At least 1,000 agents
   - Required columns complete at 100 percent
2. Event trail
   - At least 90 days daily simulation
   - Mean events per agent per day > 5
3. Forecast
   - Baseline and one stress scenario
   - p10/p50/p90 provided for all core metrics
4. Validation
   - All privacy and fidelity gates pass
   - Calibration metrics reported
5. Reproducibility
   - Seeded run produces stable aggregate outputs within tolerance

---

## 9. Milestones

### Milestone A: Core Population and Events

- Implement `pupil_population.py`, `pupil_state.py`, `pupil_events.py`
- Generate `population.csv` and `events.csv`

### Milestone B: Simulation and Forecast

- Implement `pupil_environment.py`, `pupil_simulation.py`, `pupil_forecast.py`
- Generate `forecast.json` for baseline and stress

### Milestone C: Validation and Pipeline

- Implement `pupil_validation.py`, `pupil_pipeline.py`
- Generate `validation_report.md` and enforce release gate

---

## 10. Risks and Controls

1. **Narrative inflation**
   - Risk: claim behavior realism without validation
   - Control: block release without validation report
2. **Privacy overreach**
   - Risk: accidentally ingest person-level traces
   - Control: provenance audit and policy checks in pipeline
3. **Model drift**
   - Risk: self-learning destabilizes distributions
   - Control: bounded updates and rollback on failed gates
4. **False certainty**
   - Risk: single-point forecasts treated as certainty
   - Control: mandatory uncertainty and calibration outputs

---

## 11. Definition of Done

Pupil v1 is complete only when:

- All required modules exist
- Test suite for Pupil modules passes
- All four output artifacts are generated
- Safety and validation gates pass
- Runbook documents exact reproducible command

Anything less is a prototype, not v1.
