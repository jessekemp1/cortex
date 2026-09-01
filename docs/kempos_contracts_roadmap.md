# KempOS Reliability Contracts Roadmap

KempOS is a private reference workload that forces Cortex to become reliable enough for long-running personal/team intelligence without leaking private data into the OSS core.

This roadmap intentionally separates the reliability substrate from higher-level coaching features.

## Phase 0: Current Assumption

KempOS must operate reliably on Cortex. If it cannot, Cortex is not robust enough yet.

Cortex remains the generic engine. KempOS remains a private application layer.

## Phase 1: Minimal Reliable Substrate

Status: initial branch `refactor/kempos-contracts`.

Build:

- `namespaces.py`
- `events.py`
- `capabilities.py`
- `health.py`
- tests for each

Purpose:

- private state isolation
- append-only events
- explicit capability reporting
- namespace doctor checks

Definition of done:

```bash
pytest tests/test_namespaces.py tests/test_events.py tests/test_capabilities.py tests/test_namespace_doctor.py
```

Must pass without:

- Anthropic key
- ChromaDB
- MCP
- scheduler
- optional memory/intelligence modules
- network

## Phase 2: Bridge Integration

Build:

- `CortexBridge.capabilities()`
- `CortexBridge.require_capability(name)`
- `CortexBridge.append_event(namespace, event_type, payload, visibility="private")`
- `CortexBridge.list_events(namespace, event_type=None, limit=50)`
- `CortexBridge.doctor_namespace(namespace)`

Extend `inject_recommendation` with optional:

- `namespace="default"`
- `visibility="private"`

For non-default namespaces, write recommendations to:

```text
~/.cortex/namespaces/<namespace>/recommendations.json
```

Definition of done:

- existing bridge behavior remains backward compatible
- namespaced event/recommendation calls work through the bridge
- invalid namespaces are rejected
- tests use temp config dirs only

## Phase 3: KempOS Reference Workload Test

Add:

```text
tests/reference_workloads/test_kempos_contract.py
```

Scenario:

1. create namespace `kempos`
2. append daily evidence event
3. append weekly review event
4. inject next-action recommendation
5. run namespace doctor
6. inspect capability registry
7. assert all private paths are outside repo working tree

No real personal data. Fake payloads only.

Definition of done:

- reference workload passes locally with filesystem-only dependencies
- no network
- no LLM key
- no scheduler

## Phase 4: CLI Surface

Add commands only after Python contracts are stable.

Target commands:

```bash
cortex capabilities
cortex namespace doctor kempos
cortex event append --namespace kempos --type evidence --payload sample.json
cortex event list --namespace kempos --type evidence
```

Definition of done:

- CLI returns JSON with `--json`
- errors are explicit
- no silent fallbacks

## Phase 5: Scheduler Contract

Build scheduler after the event/recommendation substrate is stable.

Target API:

```python
scheduler.register(namespace, job)
scheduler.status(namespace)
scheduler.run_due(namespace=None)
scheduler.history(namespace)
```

Definition of done:

- daily/weekly/monthly KempOS jobs can be registered
- job history writes to namespace-local logs or global metrics with namespace field
- missed jobs are visible
- failures are explicit

## Phase 6: KempOS Private App MVP

Private repo or server folder, not Cortex OSS.

Build:

- daily capture command
- weekly review generator
- monthly CEO review generator
- experiment tracker
- deterministic pattern rules
- Cortex bridge adapter

Definition of done:

- KempOS stores evidence through Cortex events
- weekly review references actual evidence only
- no evidence means coach asks for evidence instead of hallucinating
- personal data remains private

## Phase 7: Pattern Intelligence

Only after 4+ weeks of evidence.

Build:

- repeated avoidance detection
- visible-signal trends
- shipment trends
- health consistency correlations
- experiment result summaries

Definition of done:

- pattern reports cite source events/reviews
- deterministic rules first
- LLM synthesis optional and clearly marked

## Phase 8: Dashboard / Reports

Build after the evidence model stabilizes.

Outputs:

- weekly compound score
- monthly trend report
- active experiments
- role scorecards
- privacy-scrubbed public artifacts if desired

Definition of done:

- dashboard is read-only first
- no private data leaves the server by default
- exports are explicitly scrubbed

## Non-Negotiables

- No private KempOS content in Cortex OSS.
- No silent success on write failures.
- All private data paths must be namespace-scoped.
- Every new reliability contract needs tests.
- Filesystem-only MVP first. Clever later.
