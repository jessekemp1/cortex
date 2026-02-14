# Co-Navigator Design Spec (2026-2028)

## Loop Architecture
Sense -> Forecast -> Route -> Execute -> Validate -> Learn

## Extended Architecture (High-Impact Modules)

1. `DecisionTwinEngine`
- Inputs: candidate plan scenarios, task-level impact/focus/risk.
- Output: ranked scenarios with utility and rationale.
- File: `cortex/intelligence/decision_twin.py`

2. `CounterfactualLedger`
- Inputs: recommended action, chosen action, expected/actual value.
- Output: follow-rate, missed-value estimates, project-level summaries.
- File: `cortex/intelligence/counterfactual_learning.py`

3. `PortfolioAllocator`
- Inputs: per-project risk/opportunity/strategic signals.
- Output: daily attention allocation constrained by min/max budgets.
- File: `cortex/intelligence/portfolio_allocator.py`

4. `TrustGovernor` (planned)
- Inputs: calibration curves, guardrail incidents, outcome quality.
- Output: autonomy level transitions with explicit reasons.

5. `PreMortemEngine` (planned)
- Inputs: initiatives, dependencies, risk priors.
- Output: failure narratives + mitigation task routes.

6. `MemoryDistiller` (planned)
- Inputs: noisy event streams and outcomes.
- Output: compact reusable strategy primitives and anti-pattern suppressors.

## Core Components
1. Sense Layer: normalize state snapshot (queue, churn, failures, focus mode).
2. Forecast Layer: create blocker/opportunity hypotheses with horizon + evidence.
3. Routing Layer: merge manual scoring with Q-router.
4. Execution Layer: bounded queue submission with dedupe and budget caps.
5. Validation Layer: prediction vs outcome logging + calibration updates.

## Integration Points
- `cortex/intelligence/task_router.py`
- `cortex/intelligence/outcome_logger.py`
- `cortex/batch/quick_batch.py`
- `cortex/plugins/briefing/plugin.py`
- `cortex/runtime/api.py`

## Data Contracts
- `ForecastHypothesis {id, category, horizon_hours, confidence, evidence}`
- `RoutedAction {action, expected_value, confidence, rationale}`
- `ScenarioScore {utility_score, shipped_impact, focus_cost, risk}`
- `CounterfactualEntry {recommended_action, chosen_action, expected_value, actual_value}`
- `Allocation {project, hours, share, score}`

## Safety and Governance
1. No high-impact autonomous actions without evidence trace.
2. Focus window interruption cap.
3. Data-quality gate before forecast emission.
4. Immediate rollback on trust gate failure.
5. Autonomy transitions only through Trust Governor policy.

## Research-to-Product Bridge
1. Causal Routing -> confidence-adjusted action effects.
2. Energy-Aware Planning -> context-aware focus-cost model.
3. Strategic Horizon Model -> tri-horizon plan optimizer.
4. Human-AI Contract Layer -> enforceable policy schema.
5. Narrative Intelligence -> generated strategy brief artifacts.
