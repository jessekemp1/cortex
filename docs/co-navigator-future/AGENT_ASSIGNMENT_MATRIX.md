# Agent Assignment Matrix (Max-Scale)

## Operating Model
- 8 parallel agents + 1 integrator + 1 validation lead.
- Ownership by file domain, no overlap without explicit contract.

## Pods
1. Pod A (Core Loop): `co_navigator.py`, `task_router.py`
2. Pod B (Execution): `quick_batch.py`, queue integrations
3. Pod C (Runtime/API): `runtime/api.py`, status contracts
4. Pod D (Briefing UX): `plugins/briefing/plugin.py`
5. Pod E (Learning): `counterfactual_learning.py`, `outcome_logger.py`
6. Pod F (Planning Intelligence): `decision_twin.py`, planning integrations
7. Pod G (Portfolio): `portfolio_allocator.py`, goal-alignment logic
8. Pod H (Trust/Safety): `trust_governor.py`, guardrail policy

## Wave Plan
1. Wave 1 (parallel): A+B+C+D (integration backbone)
2. Wave 2 (parallel): E+F+G (intelligence modules)
3. Wave 3 (parallel): H + cross-cutting hardening

## Integration Contracts
1. `RoutedAction` schema is shared boundary.
2. All pods must emit JSON-serializable payloads.
3. API/briefing fields are contract-tested before merge.

## Quality Gates per Pod
1. Unit tests mandatory.
2. Contract tests mandatory for boundary changes.
3. Rollback notes required in PR summary.
4. No branch switching or destructive git operations.

## Throughput Controls
1. Batch PRs by pod; max 2 concurrent open PRs per pod.
2. Integrator merges only green tests + contract compliance.
3. Daily sync: blockers, dependency changes, contract drift.
