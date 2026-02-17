# Cortex Conductor: Product Requirements Document

**Status**: V1 Shipped (142/142 tests, 0.29s)
**Owner**: Jesse Kemp
**Last Updated**: 2026-02-17

---

## 1. Overview

The Cortex Conductor is a multi-provider AI model router that lives in `cortex/conductor/`. It routes AI requests to the optimal provider and model based on use case, cost, and capability, then tracks all spending against a configurable daily budget.

**Problem**: Running all AI workloads through Anthropic is expensive. Many tasks (classification, pattern extraction, documentation) don't need frontier models. Routing these to cheaper providers (Groq, DeepSeek, MiniMax) saves ~39% on monthly API costs with no quality loss for the routed use cases.

**Solution**: A routing layer with 6 providers, 11 models, 11 use cases, automatic fallback, and JSONL-based cost tracking.

### Providers

| Provider | Models | API Style | Key Env Var |
|----------|--------|-----------|-------------|
| Groq | Llama 3.1 8B, GPT-OSS 20B | OpenAI-compatible | `GROQ_API_KEY` |
| xAI | Grok 3 Fast, Grok Code Fast 1 | OpenAI-compatible | `XAI_API_KEY` |
| MiniMax | MiniMax M1 80k | OpenAI-compatible | `MINIMAX_API_KEY` |
| DeepSeek | DeepSeek V3.2 | OpenAI-compatible | `DEEPSEEK_API_KEY` (fallback: `OPENAI_API_KEY`) |
| OpenAI | GPT-5, GPT-5 Nano | OpenAI native | `OPENAI_API_KEY` |
| Anthropic | Opus 4.6, Sonnet 4.5, Haiku 4.5 | Messages API | `ANTHROPIC_API_KEY` |

### Current State

- **Core routing**: `router.py`, `models.py`, `registry.py` -- 62 tests
- **Provider clients**: `groq`, `xai`, `minimax`, `openai`, `anthropic` -- 52 tests
- **Cost tracker**: JSONL tracking, budget enforcement, savings calculation -- 28 tests
- **Live tested**: Groq working, Anthropic fallback working, xAI needs credits
- **Total**: 142/142 tests in 0.29s

---

## 2. Architecture

### Module Structure

```
cortex/conductor/
    __init__.py          # Public API: route(), call(), get_costs(), get_savings(), get_budget_remaining()
    router.py            # ConductorRouter + UseCaseClassifier + routing tables
    models.py            # Data classes: ModelSpec, ProviderConfig, RoutingRequest, RoutingDecision
    registry.py          # Provider registry (6 providers, 11 models, pricing, context limits)
    cost_tracker.py      # CostTracker: JSONL append-only log, budget enforcement, savings calc
    providers/
        __init__.py      # Re-exports all provider classes
        base.py          # BaseProvider ABC, ChatMessage, CompletionResponse, ProviderError
        groq_provider.py
        xai_provider.py
        minimax_provider.py
        openai_provider.py       # Also used for DeepSeek (base_url override)
        anthropic_provider.py    # Uses Messages API, NOT OpenAI-compatible
    tests/
        test_router.py
        test_providers.py
        test_cost_tracker.py
```

### Public API

```python
from cortex.conductor import route, call, get_costs, get_savings, get_budget_remaining

# 1. Get routing recommendation (no API call)
decision = route("classify this request", use_case="classification")
# -> RoutingDecision(provider="groq", model_id="llama-3.1-8b-instant", ...)

# 2. Route AND execute (makes the API call, tracks cost)
response = call("What category is this?", use_case="classification")
# -> CompletionResponse(content="...", cost_usd=0.0001, ...)

# 3. Check daily spending by provider
costs = get_costs()
# -> {"groq": 0.05, "anthropic": 1.20, "total": 1.25}

# 4. Savings vs Anthropic-only baseline
savings = get_savings()
# -> {"actual_spend": 2.50, "anthropic_equivalent": 4.10, "savings_pct": 39.0, ...}

# 5. Remaining daily budget
remaining = get_budget_remaining()
# -> 17.50
```

### Data Flow

```
call("prompt", use_case="classification")
  |
  v
route() -> RoutingDecision(provider="groq", model="llama-3.1-8b-instant", fallback="openai/gpt-5-nano")
  |
  v
_create_provider("groq") -> GroqProvider(api_key=env.GROQ_API_KEY)
  |
  v
provider.complete(messages, model, max_tokens, temperature)
  |
  +-- SUCCESS -> CostTracker.record(provider, model, tokens, cost, latency) -> return CompletionResponse
  |
  +-- FAILURE -> _create_provider("openai") -> retry with fallback model -> record cost -> return
  |
  +-- BOTH FAIL -> raise ProviderError with context from both failures
```

### Key Design Decisions

- **DeepSeek reuses OpenAIProvider** with `base_url="https://api.deepseek.com"` -- no separate client needed.
- **Anthropic uses Messages API** (not OpenAI format): system messages as top-level param, `x-api-key` header, content blocks response format.
- **API keys loaded from `cortex/.env`** at module import time via `_load_dotenv()` -- daemon-compatible, does not rely on direnv or shell activation.
- **Module-level singletons** for CostTracker and ConductorRouter, lazy-initialized on first use.
- **Thread-safe cost recording** via `threading.Lock` on JSONL writes.

---

## 3. Routing Table

### Competition Matrix

| Use Case | Primary Provider | Primary Model | Fallback Provider | Fallback Model |
|----------|-----------------|---------------|-------------------|----------------|
| `architecture` | anthropic | `claude-opus-4-6` | openai | `gpt-5` |
| `interactive_coding` | anthropic | `claude-sonnet-4-5-20250929` | xai | `grok-code-fast-1` |
| `classification` | groq | `llama-3.1-8b-instant` | openai | `gpt-5-nano` |
| `long_context` | xai | `grok-3-fast` | minimax | `MiniMax-M1-80k` |
| `research` | xai | `grok-3-fast` | deepseek | `deepseek-chat` |
| `quick_qa` | groq | `openai/gpt-oss-20b` | anthropic | `claude-haiku-4-5-20251001` |
| `code_review` | minimax | `MiniMax-M1-80k` | anthropic | `claude-sonnet-4-5-20250929` |
| `test_generation` | minimax | `MiniMax-M1-80k` | xai | `grok-code-fast-1` |
| `documentation` | deepseek | `deepseek-chat` | deepseek | `deepseek-chat` |
| `security_audit` | anthropic | `claude-opus-4-6` | openai | `gpt-5` |
| `pattern_learning` | deepseek | `deepseek-chat` | groq | `llama-3.1-8b-instant` |

### Model Registry (11 models, 6 providers)

| Provider | Model ID | Display Name | Input $/MTok | Output $/MTok | Context | Speed |
|----------|----------|-------------|-------------|--------------|---------|-------|
| groq | `llama-3.1-8b-instant` | Groq Llama 8B | $0.05 | $0.08 | 131K | fast |
| groq | `openai/gpt-oss-20b` | Groq GPT-OSS 20B | $0.075 | $0.30 | 131K | fast |
| xai | `grok-3-fast` | Grok 4.1 Fast | $0.20 | $0.50 | 2M | fast |
| xai | `grok-code-fast-1` | Grok Code Fast 1 | $0.20 | $1.50 | 131K | fast |
| minimax | `MiniMax-M1-80k` | MiniMax M2.5 | $0.30 | $1.20 | 1M | medium |
| anthropic | `claude-opus-4-6` | Opus 4.6 | $15.00 | $75.00 | 200K | slow |
| anthropic | `claude-sonnet-4-5-20250929` | Sonnet 4.5 | $3.00 | $15.00 | 200K | fast |
| anthropic | `claude-haiku-4-5-20251001` | Haiku 4.5 | $1.00 | $5.00 | 200K | fast |
| openai | `gpt-5` | GPT-5 | $2.50 | $20.00 | 400K | medium |
| openai | `gpt-5-nano` | GPT-5 Nano | $0.10 | $0.80 | 128K | fast |
| deepseek | `deepseek-chat` | DeepSeek V3.2 | $0.28 | $0.42 | 128K | medium |

### Routing Overrides

1. **Context override**: If `context_tokens > 200,000`, the router forces `long_context` regardless of explicit `use_case`. This ensures the request goes to a provider with sufficient context window (xAI Grok at 2M, or MiniMax at 1M).

2. **Context capacity upgrade**: If the selected primary model cannot handle the input tokens, the router searches the entire registry for the cheapest model with sufficient context and upgrades.

3. **Batch routing**: Batch-eligible requests have a separate routing table (currently same providers, reserved for future batch-discount optimization).

4. **Keyword classification**: When no explicit `use_case` is provided, the `UseCaseClassifier` matches task descriptions against keyword sets to infer the use case. Confidence ranges from 0.3 (no match, defaults to `quick_qa`) to 0.95 (3+ keyword hits in one category).

---

## 4. Acceptance Criteria

### P0 -- Must Pass (Ship Blockers)

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `route()` returns correct provider+model for each of 11 use cases | `test_router.py::TestRoutingTable` -- one test per use case asserting provider and model_id |
| 2 | `call()` executes through primary provider and returns `CompletionResponse` | `test_providers.py` -- mocked HTTP for each provider, verify response fields |
| 3 | On primary failure, `call()` falls back to secondary provider automatically | `__init__.py:391-435` fallback logic -- primary raises `ProviderError`, fallback succeeds |
| 4 | All costs tracked in JSONL with provider, model, tokens, cost_usd, latency | `test_cost_tracker.py::test_record_and_load` -- verify JSONL entry fields |
| 5 | `get_costs()` returns accurate daily spending per provider | `test_cost_tracker.py::test_daily_spend` -- record N entries, assert per-provider totals |
| 6 | `get_savings()` correctly calculates savings vs Anthropic-only baseline | `test_cost_tracker.py::test_savings_report` -- record cheap-provider calls, verify savings_pct > 0 |
| 7 | API keys loaded from `cortex/.env` (daemon-compatible, not relying on direnv) | `__init__.py:30-45` -- `_load_dotenv()` reads `cortex/.env` at import time |
| 8 | Budget enforcement: `get_budget_remaining()` reflects actual spend | `test_cost_tracker.py::test_budget_remaining` -- record $5, assert remaining = budget - 5 |
| 9 | 142/142 unit tests pass | `pytest cortex/conductor/tests/ -v` -- 0 failures, 0 errors |

### P1 -- Should Pass (Quality Gates)

| # | Criterion | Verification |
|---|-----------|--------------|
| 10 | Batch pipeline costs tracked in CostTracker alongside interactive costs | `cortex/batch/` pipeline calls `CostTracker.record()` with `use_case` tag |
| 11 | `/budget` command shows unified view (interactive + batch spending) | Slash command reads from same JSONL, displays by-provider and by-use-case |
| 12 | Daily/hourly cost sync -- no data loss between sessions | JSONL is append-only on disk; no in-memory buffer that could be lost |
| 13 | Delegation flow: conductor -> provider -> cost tracking verified end-to-end | Integration test: `call()` -> verify JSONL has matching entry |
| 14 | Cost data persists across process restarts (JSONL file-based) | JSONL at `~/.cortex/conductor/costs.jsonl` -- survives process exit |

### P2 -- Nice to Have

| # | Criterion | Verification |
|---|-----------|--------------|
| 15 | Per-use-case cost breakdown in savings report | `get_savings()` already returns `by_use_case` dict |
| 16 | Hourly spend rate for budget pacing | Compute from JSONL timestamps: `total_last_hour / 1 * hours_remaining` |
| 17 | Provider health monitoring (track failure rates) | Count `ProviderError` occurrences per provider in JSONL or separate log |

---

## 5. Budget and Limits

### Daily Budget

- **Default**: $20.00 (configurable via `CostTracker(daily_budget=...)`)
- **Reset**: Midnight UTC (budget is date-scoped via JSONL timestamp filtering)
- **Enforcement**: `check_budget(estimated_cost)` returns `False` if the next call would exceed the daily limit
- **Remaining**: `get_budget_remaining()` = `daily_budget - today's total spend`

### Cost Log Format

Append-only JSONL at `~/.cortex/conductor/costs.jsonl`. One record per API call:

```json
{
  "timestamp": "2026-02-17T14:30:00Z",
  "provider": "groq",
  "model": "llama-3.1-8b-instant",
  "input_tokens": 1500,
  "output_tokens": 200,
  "cost_usd": 0.000091,
  "use_case": "classification",
  "latency_ms": 142.5
}
```

### Savings Baseline

For each `use_case`, the savings report calculates what the same tokens would cost on the equivalent Anthropic model:

| Use Case | Anthropic Baseline Model | Input $/MTok | Output $/MTok |
|----------|------------------------|-------------|--------------|
| `classification` | Haiku | $1.00 | $5.00 |
| `quick_qa` | Haiku | $1.00 | $5.00 |
| `documentation` | Haiku | $1.00 | $5.00 |
| `pattern_learning` | Haiku (batch) | $0.50 | $2.50 |
| `interactive_coding` | Sonnet | $3.00 | $15.00 |
| `code_review` | Sonnet | $3.00 | $15.00 |
| `long_context` | Sonnet | $3.00 | $15.00 |
| `research` | Sonnet | $3.00 | $15.00 |
| `test_generation` | Sonnet | $3.00 | $15.00 |
| `architecture` | Opus | $15.00 | $75.00 |
| `security_audit` | Opus | $15.00 | $75.00 |

Savings = `anthropic_equivalent - actual_spend`. Target: ~39% savings on monthly spend.

### Monthly Summary

`get_monthly_summary()` provides:
- `by_provider`: total spend per provider for current month
- `by_use_case`: total spend per use case
- `by_day`: daily spend totals
- `total_calls`: number of API calls
- `total_spend`: aggregate USD

---

## 6. Integration Points

### Cortex Batch Pipeline (`cortex/batch/`)

Batch jobs (nightly analysis, bulk classification) route through the conductor. The batch processor calls `call()` with appropriate `use_case` tags so costs are tracked in the same JSONL. Batch jobs that use Anthropic's Batch API (50% discount) should NOT be rerouted -- the conductor only handles interactive and non-batch-API requests.

### `/budget` Slash Command

Unified spending dashboard that reads from `~/.cortex/conductor/costs.jsonl`:

```
Budget Status (2026-02-17)
    Daily Budget:   $20.00
    Spent Today:    $2.47
    Remaining:      $17.53
    By Provider:    groq $0.12 | deepseek $0.35 | anthropic $2.00
    Savings Today:  $1.85 (43% vs Anthropic-only)
```

### `/briefing` Slash Command

Daily briefing includes a cost summary section pulled from `get_costs()` and `get_savings()`.

### Session Hook

On session start, if `get_budget_remaining() < daily_budget * 0.2` (under 20% remaining), display a budget warning.

### API Key Loading

Keys are loaded from `cortex/.env` via `_load_dotenv()` at module import time. This supports:
- Interactive sessions (direnv may also be active, but `.env` load is the primary path)
- Daemon processes (launchd jobs, cron, batch processor) that don't inherit shell environment
- The function does NOT overwrite keys already in `os.environ`, so explicit env vars take precedence

---

## 7. Non-Goals (Explicit)

These are deliberately out of scope for V1:

1. **NOT replacing Anthropic Batch API for batch jobs.** The Batch API gives a 50% discount on Anthropic models. Conductor routes interactive requests to cheaper providers; it does not compete with Anthropic's own batch pricing.

2. **NOT implementing provider health checks in V1.** Provider failure rates are not tracked or monitored. If a provider is down, the fallback path handles it. Systematic health monitoring is P2.

3. **NOT supporting streaming responses in V1.** All provider calls are synchronous (full response returned). Streaming would require async clients and SSE handling across 5 different API formats.

4. **NOT adding new providers without explicit user approval.** The provider registry is manually curated. Adding a provider requires: new client module, pricing data, routing table entry, and test coverage.

5. **NOT doing real-time model quality comparison.** The routing table is based on a one-time competition matrix. Dynamic quality scoring (like Vortex's field-selective ensemble) is a future enhancement.

6. **NOT routing Claude Code's own requests.** The conductor routes programmatic AI calls from Cortex subsystems (batch, intelligence, pattern learning). Claude Code sessions go directly through Anthropic.

---

## Appendix A: Test Breakdown

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_router.py` | 62 | Routing table correctness, keyword classification, context overrides, batch routing, edge cases |
| `test_providers.py` | 52 | Provider instantiation, API key handling, request formatting, response parsing, error handling (all 5 providers) |
| `test_cost_tracker.py` | 28 | Record/load, daily spend, budget enforcement, savings calculation, monthly summary, thread safety |
| **Total** | **142** | **0.29s runtime** |

## Appendix B: Provider API Differences

| Feature | Groq/xAI/MiniMax/OpenAI/DeepSeek | Anthropic |
|---------|----------------------------------|-----------|
| Auth Header | `Authorization: Bearer <key>` | `x-api-key: <key>` |
| System Message | In `messages` array with `role: "system"` | Top-level `system` parameter |
| Response Content | `choices[0].message.content` (string) | `content[]` array of typed blocks |
| Token Fields | `prompt_tokens`, `completion_tokens` | `input_tokens`, `output_tokens` |
| Timeout | 60s | 120s (Opus is slower) |
