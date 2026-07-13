Show HN: Cortex – persistent memory and task routing for LLM dev agents

Six months ago I noticed a pattern: every morning I'd open a new Claude session
and spend the first ten minutes re-explaining my codebase, my preferences, which
patterns to avoid, and what I was in the middle of. The agent would do good work,
then the session ended and everything was gone. The next session was a blank
slate. I was the one providing continuity, not the system.

Cortex is my attempt to fix that. It's a local-first intelligence layer that
gives LLM agents persistent memory across sessions, structured task context, and
automatic model routing. It runs as an MCP server, so Claude Desktop and Claude
Code both pick it up without any glue code.

The memory architecture has three tiers. Working memory holds the current session
state. Episodic memory records what happened in past sessions — decisions made,
problems solved, outcomes. Semantic memory uses a BM25 + embedding hybrid index
so retrieval is fast even across months of history. At query time the system
merges all three and deduplicates before returning context. In practice that
deduplication pass removes about 21% of tokens that would otherwise be redundant
noise in the prompt.

The part I'm most pleased with is the anti-pattern database. When I finish a
debugging session where the agent went down a wrong path, I can record that
mistake with enough context that the system can surface it when a similar
situation comes up later. It's not just "remember this happened" — it's "here's
why this approach fails and what to do instead." That prevention context is
stored as a separate field and boosted in retrieval.

Task routing tries to match query complexity to model tier. Short, low-complexity
prompts auto-downgrade to Haiku. Richer tasks go to Sonnet. Anything that
requires extended reasoning gets flagged for Opus. The routing quality score on
my test set is 0.94. Combined with Anthropic's Batch API for eligible work, this
produces about a 50% reduction in API spend compared to routing everything to the
largest model.

The system has 1,855 tests passing on a fresh clone across unit, integration,
and end-to-end suites. The architecture is covered in a 9-page preprint [1] if
you want the full technical treatment.

There are two direct comparisons worth being honest about. Mem0 (49K stars) is
the established player in agent memory — it's general-purpose and has a large
ecosystem. Cortex is narrower: it's built specifically for a solo developer or
small team running LLM agents across a multi-project portfolio over months or
years. If you're building a product that needs memory for thousands of users,
Mem0 is probably the right choice. Supermemory (17K stars) has excellent
retrieval benchmarks; Cortex trades some retrieval benchmark performance for task
orchestration primitives that Supermemory doesn't have. Neither comparison is a
clean win — it depends on the use case.

What Cortex doesn't do: it doesn't sync to the cloud, it doesn't work with
OpenAI or Gemini natively (though the MCP interface is provider-agnostic at the
protocol level), and it's not a hosted service. Everything lives in ~/.cortex/
and nothing leaves your machine unless you configure an external backend.

It's Apache 2.0. The repo is at https://github.com/jessekemp1/cortex.

[1] https://github.com/jessekemp1/cortex/blob/main/docs/cortex_paper.pdf

The feedback I'd most value from this audience: (1) If you've tried to build or
use agent memory systems before, where did the friction actually come from? My
assumption was session amnesia, but I'm curious whether the retrieval quality,
the context window cost, or the tooling integration were bigger pain points for
you. (2) The anti-pattern database is the feature I have the least external
signal on — does that concept resonate, or does it sound like too much manual
overhead to maintain?
