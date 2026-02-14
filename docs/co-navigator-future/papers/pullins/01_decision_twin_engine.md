# Paper: Decision Twin Engine

## Abstract
Decision Twin simulates alternative weekly execution plans and ranks them by expected shipped impact adjusted for focus cost and risk.

## Problem
Manual weekly planning lacks scenario comparison and systematically underestimates focus fragmentation cost.

## Method
- Represent plan candidates as task sets with impact, effort, focus cost, risk.
- Compute utility: weighted impact minus focus/risk/effort penalties.
- Select highest utility scenario.

## Engineering Status
- Implemented: `cortex/intelligence/decision_twin.py`
- Tested: `cortex/tests/test_decision_twin.py`

## Evaluation Plan
- 8-week A/B: manual planning vs twin-ranked planning.
- Metrics: shipped impact per focus hour, blocked-task incidence.

## Risks
- Biased scoring weights; mitigated by weekly recalibration.
