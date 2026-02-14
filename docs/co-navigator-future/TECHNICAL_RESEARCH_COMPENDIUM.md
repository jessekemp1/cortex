# Technical Research Compendium

## Purpose
Convert frontier concepts into testable technical programs and engineering specs.

## Part I: High-Impact Pull-Ins

### 1. Decision Twin Engine
- Hypothesis: simulation-based weekly planning beats static prioritization.
- Method: generate candidate plans, score utility by impact/focus/risk.
- Experiment: compare twin-selected plan vs manual plan over 8 weeks.
- Success: statistically significant lift in shipped-impact per focus-hour.

### 2. Counterfactual Learning
- Hypothesis: measuring missed value accelerates strategy adaptation.
- Method: ledger of recommended vs chosen actions with expected/actual value.
- Experiment: weekly review of top missed-value cases.
- Success: missed-value trend declines and follow-rate improves.

### 3. Portfolio Allocator
- Hypothesis: constrained dynamic allocation outperforms fixed project splits.
- Method: weighted score from risk, opportunity, strategic alignment.
- Experiment: daily rebalance with cap/min constraints.
- Success: higher portfolio throughput and lower drift.

### 4. Trust Governor
- Hypothesis: policy-driven autonomy transitions reduce trust incidents.
- Method: reliability curves + guardrail event thresholds.
- Experiment: staged autonomy with automatic promote/downgrade.
- Success: no severe trust incidents during autonomy expansion.

### 5. Pre-Mortem Forecasting
- Hypothesis: pre-mortem narratives reduce preventable blockers.
- Method: generate likely failure paths and mitigation tasks before execution.
- Experiment: compare blocker rates with/without pre-mortem flow.
- Success: reduction in high-severity preventable incidents.

### 6. Compounding Memory Distiller
- Hypothesis: distilled strategy memory improves transfer and lowers noise.
- Method: weekly compression pipeline from raw events -> reusable primitives.
- Experiment: A/B team-of-one operations with/without distiller output.
- Success: lower anti-pattern recurrence and faster decision cycles.

## Part II: Innovation Research Tracks

### 1. Causal Routing
- Problem: correlation-based ranking confounds action quality.
- Approach: causal effect estimation from interventions/outcomes.
- Deliverable: causal-adjusted action ranker with uncertainty bounds.

### 2. Energy-Aware Planning
- Problem: same task has different quality/cost by cognitive state.
- Approach: infer energy mode and adapt route selection.
- Deliverable: energy-tagged schedule with expected quality uplift.

### 3. Strategic Horizon Model
- Problem: urgent work cannibalizes compounding work.
- Approach: tri-horizon objective (24h/7d/30d) with constrained optimization.
- Deliverable: horizon-balanced daily plan generator.

### 4. Human-AI Contract Layer
- Problem: trust decays when authority boundaries are unclear.
- Approach: explicit machine-action contract, rationale obligations, veto flow.
- Deliverable: enforceable policy spec + runtime checks.

### 5. Narrative Intelligence
- Problem: strategy becomes fragmented across metrics and tasks.
- Approach: generate living narrative artifacts grounded in outcomes.
- Deliverable: weekly strategy narrative with risk/learning updates.

## Engineering Readiness Matrix
1. Ready now: Decision Twin, Counterfactual, Allocator (v1 implemented).
2. Next build: Trust Governor, Pre-Mortem, Memory Distiller.
3. Research-first: Causal Routing, Energy-Aware, Strategic Horizon, Contract Layer, Narrative Intelligence.
