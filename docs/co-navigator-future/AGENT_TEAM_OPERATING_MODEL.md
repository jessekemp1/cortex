# Agent Team Operating Model (Scale-Out)

## Objective
Maximize parallel throughput without quality collapse or context loss.

## Team Topology
1. Architecture Lane (explorer agents): design constraints and integration points.
2. Build Lane (worker agents): isolated module ownership and tests.
3. Validation Lane (explorer + worker): benchmarks, regressions, safety checks.
4. Narrative Lane (explorer): PRD/spec/marketing artifacts from accepted evidence.

## Ownership Rules
1. Each worker owns explicit files only.
2. Shared contracts updated by one designated integrator.
3. No branch switching by workers.
4. Every worker ships tests with changes.

## Cadence
1. 2-hour cycles: plan -> build -> verify -> integrate.
2. End-of-cycle synthesis: risks, blockers, next highest-EV task.

## Quality Controls
1. Contract tests for integration boundaries.
2. Trust/focus gates checked every cycle.
3. Auto-backup of docs and plans (non-blocking hook).

## Scale Pattern
1. Start with 3-agent pods.
2. Expand to 6-8 agents only with strict file ownership.
3. Keep one human integrator as final arbiter.
