# Wave manifest — Cortex curation P1

The tasks form a mostly-linear dependency chain (write path feeds read path feeds regression gate),
so parallelism is limited — that's honest, not a slicing failure: Changes 2→3→4 edit an overlapping
concern (the decision entry schema, then its consumers) and must be sequenced.

```
WAVE 1 (parallel):
  - task-01: importance scoring module | files: intelligence/memory/importance.py, tests/test_importance_scoring.py | depends: none

WAVE 2 (sequential):
  - task-02: annotate importance on write | files: mcp_handlers.py, tests/test_learning.py | depends: 01

WAVE 3 (parallel):
  - task-03: explicit supersession on write | files: mcp_handlers.py, mcp_server.py, api/routes/decisions.py, tests/test_supersession.py | depends: 02
  - task-05: backfill existing history | files: scripts/memory_maintenance.py | depends: 02
    (03 and 05 are parallel: 05 only reads the importance helper + writes its own subcommand; 03 edits
     the writer's supersedes path. They touch disjoint code — mcp_handlers additive supersedes param vs
     a new script subcommand. If an edit conflict surfaces in mcp_handlers, serialize 05 after 03.)

WAVE 4 (sequential):
  - task-04: read-side skip + down-weight | files: intelligence/memory/hybrid_retriever.py, tests/test_hybrid_retriever.py | depends: 03

WAVE 5 (sequential):
  - task-06: full-suite + recall-benchmark regression gate | files: tests/test_retrieval_benchmark.py | depends: 04, 05
```

Shippable unit = Waves 1-4 (write + read = the working feature). Wave 5 is the gate. Backfill (05)
can ship in the same PR or immediately after.
