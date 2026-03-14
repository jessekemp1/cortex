# Cortex Research Directives

> This file is the CRA equivalent of Karpathy's `program.md` in autoresearch.
> Humans edit this file to steer the research agent's autonomous behavior.
> The CRA agent reads this file, proposes integrations, and validates them
> against a single scalar metric (`adoption_outcome_score`).

## Current Research Priorities (March 2026)

### Priority 1: Existential Threat Monitoring

Monitor these developments continuously. If any crosses the "disruption" threshold,
CRA should produce an URGENT assessment and propose an adaptation plan:

1. **Anthropic native memory API** — If Claude gets built-in persistent memory,
   Cortex must pivot to intelligence layer on top. Watch: Anthropic changelog,
   developer docs, SDK releases.
2. **Mem0 adds orchestration** — If Mem0 (49.5K stars) ships task routing or
   anti-pattern primitives, our moat narrows to zero. Watch: mem0ai/mem0 releases,
   their blog, their Discord.
3. **Claude Code built-in learning** — If Claude Code ships cross-session memory
   natively, our core use case is commoditized. Watch: Claude Code changelog,
   Anthropic blog.

### Priority 2: Capability Amplification

Research that directly strengthens Cortex's moat (orchestration + intelligence):

1. **Trajectory memory** — Learn from HOW tasks were solved, not just outcomes.
   Key paper: arXiv 2603.10600 (+14.3pp on AppWorld). Also: MACLA (2512.18950).
2. **Memory admission control** — Decide what NOT to remember. Key paper:
   arXiv 2603.04549 (5-factor admission scoring).
3. **Causal retrieval** — Retrieve by cause, not similarity. Explore graph-based
   approaches (MAGMA, A-Mem).
4. **Auto-skill extraction** — Extract reusable skills from interaction traces.
   Key paper: AutoSkill (2603.01145).

### Priority 3: Infrastructure Evolution

Lower priority — only pursue if adoption_outcome_score > 0.7:

1. **Mem0 as storage backend** — Replace file-based storage with Mem0's graph+vector.
   Only if their API is stable and we can layer intelligence on top.
2. **MCP server ecosystem** — New MCP servers that could extend Cortex's reach.
3. **Benchmark evaluation** — AMA-Bench (2602.22769) for external credibility.

## Constraints

- **One metric per experiment**: `adoption_outcome_score` only. Do not optimize
  for multiple objectives simultaneously.
- **Tests must pass**: No integration that breaks existing tests. Ever.
- **Moat-preserving**: Never adopt something that commoditizes our unique layers
  (anti-patterns, outcome learning, goal pipeline). Only adopt things that
  strengthen or extend them.
- **Minimal changes**: Prefer small, surgical integrations over large rewrites.
  Karpathy's insight: the agent that ran 126 experiments overnight beat the one
  that tried 3 ambitious rewrites.

## Evaluation Protocol

When the CRA proposes an integration:

1. Create a branch
2. Implement the minimal viable integration
3. Run `pytest cortex/tests/ -v`
4. Compute `adoption_outcome_score`:
   - `test_pass_rate` (0-1): fraction of tests passing
   - `capability_score_delta` (0-1): improvement in the target capability
   - `disruption_addressed` (0 or 1): does this address a Priority 1 threat?
   - Score = `0.5 * test_pass + 0.3 * capability_delta + 0.2 * disruption`
5. If score > current baseline: **keep**
6. If score <= current baseline: **discard**, log reasoning to `dismissed.jsonl`

## Anti-Directives (What NOT to Research)

- Basic RAG improvements (Mem0/Supermemory own this space)
- Vector store engines (commodity layer)
- Multi-tenant SaaS patterns (premature — no users yet)
- UI/dashboard frameworks (not our problem space)
- General LLM benchmarks (only agent-memory-specific benchmarks matter)

## Scan Schedule

- **Daily**: arxiv cs.AI, cs.CL, cs.SE (semantic filter against capability vectors)
- **Weekly**: GitHub trending (agent, memory, MCP), Anthropic changelog, Mem0 releases
- **On-demand**: When human adds a new paper/repo to Priority 2 list above

---

*Last updated: 2026-03-14 by Jesse Kemp*
*Inspired by: [karpathy/autoresearch](https://github.com/karpathy/autoresearch) program.md pattern*
