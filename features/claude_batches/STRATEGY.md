# Strategy: Claude Batches for Agent Teams ("The Night Shift")

**Goal**: Maximize throughput and minimize cost by offloading non-urgent agent tasks to the Anthropic Message Batches API.

## Core Concept
- **Standard Agents**: Run synchronously (High cost, instant).
- **"Night Shift" Agents**: Run asynchronously (50% cost, 24h SLA).

## Proposed Architecture

### 1. The Queue System
We add a `BatchQueue` to the `local-orchestrator`.
- Agents don't call `anthropic.messages.create` directly.
- They call `orchestrator.enqueue_batch(prompt, callback_id)`.

### 2. The Batch Processor (System Agent)
A specialized agent `system_batch_processor` that runs every hour.
- **Aggregates**: Pulls pending items from `BatchQueue`.
- **Formats**: Creates the `.jsonl` file required by Anthropic.
- **Submits**: `client.messages.batches.create(...)`
- **Tracks**: Stores the `batch_id` in `BatchTracker` DB.

### 3. The Result Handler (System Agent)
A specialized agent `system_batch_handler` that runs every 15 minutes.
- **Polls**: Checks status of tracked batches.
- **Downloads**: When `status="ended"`, downloads results.
- **Dispatches**: Triggers the original callbacks/agents with the results.

## Use Cases for "Symbiosis"
1.  **Massive Refactors**: "Rename this variable in these 500 files." -> Batch it.
2.  **Deep Research**: "Read these 50 PDF papers and summarize." -> Batch it.
3.  **Test Generation**: "Write unit tests for this entire module." -> Batch it.

## Implementation Steps
1.  **Database**: Add `batch_queue` and `batch_tracking` tables to `local-orchestrator`.
2.  **API Client**: Update `learning` or `ai_intelligence` module to support Batch API.
3.  **Agents**: Create `BatchProcessor` and `ResultHandler` system agents.
