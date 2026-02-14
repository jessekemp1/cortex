# Paper: Counterfactual Learning Ledger

## Abstract
Counterfactual Learning quantifies opportunity cost from ignored recommendations by comparing recommended vs chosen actions and estimated value delta.

## Problem
Recommendation systems improve slowly when only followed actions are measured.

## Method
- Log each recommendation and the chosen action.
- Estimate missed value when recommendations are not followed.
- Track follow-rate and missed-value trends.

## Engineering Status
- Implemented: `cortex/intelligence/counterfactual_learning.py`
- Tested: `cortex/tests/test_counterfactual_learning.py`

## Evaluation Plan
- Weekly retrospective on top missed-value events.
- Target: downward missed-value trend over 12 weeks.

## Risks
- Estimated values may be noisy; mitigated with confidence buckets.
