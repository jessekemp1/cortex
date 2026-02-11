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
cortex/synthetic/
  pupil_population.py      # Persona synthesis from aggregate constraints
  pupil_state.py           # Agent state schema and transitions
  pupil_events.py          # Daily event generation engine
  pupil_environment.py     # Scenario and macro signal model
  pupil_simulation.py      # Time stepping and state updates
  pupil_forecast.py        # Ensemble forecast and uncertainty
  pupil_validation.py      # Fidelity, privacy, coherence, calibration checks
  pupil_pipeline.py        # Orchestrates end-to-end run and artifacts
  tests/
    test_pupil_population.py
    test_pupil_events.py
    test_pupil_simulation.py
    test_pupil_forecast.py
    test_pupil_validation.py
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

Required columns:

- `agent_id`
- `segment`
- `province`
- `age_band`
- `income_band`
- `credit_band`
- `household_type`
- `digital_adoption`
- `risk_tolerance`
- `price_sensitivity`
- `churn_propensity`
- `initial_state`

### 5.2 Event Record (`events.csv`)

Required columns:

- `event_id`
- `agent_id`
- `timestamp`
- `domain` (finance, retail, mobility, health, media, work)
- `event_type`
- `amount` (nullable)
- `duration_minutes` (nullable)
- `channel`
- `region`
- `state_before`
- `state_after`

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
