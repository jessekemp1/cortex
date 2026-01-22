# Cortex Batch System

Orchestrates long-running AI workloads using the Anthropic Batch API.

---

## Architecture

```
cortex/batch/
├── batch_api_client.py         ← Core API wrapper for Anthropic Batch API
├── queue_manager.py             ← Automatic queue processing and submission
├── queue.sh                     ← CLI helper script for queue management
├── queues/                      ← Queue definitions and templates
│   ├── queue_template.json      ← Template for creating new queues
│   └── remediation_queue.json   ← Active remediation queue definition
└── orchestrators/               ← High-level batch orchestration
    └── (future orchestrators)

~/.cortex/batches/               ← Runtime data (NOT in git)
├── active/
│   └── remediation_queue.json   ← Current queue state (runtime)
├── results/
│   └── msgbatch_*/              ← Batch results
└── logs/
    └── queue_manager.log        ← Queue manager logs
```

**Key Separation:**
- `cortex/batch/` = **Code** (versioned in git)
- `cortex/batch/queues/` = **Templates** (versioned in git)
- `~/.cortex/batches/` = **Runtime data** (NOT in git)

---

## Components

### Batch API Client (`batch_api_client.py`)

Low-level wrapper around Anthropic Batch API.

```python
from cortex.batch.batch_api_client import BatchAPIClient, BatchRequest

client = BatchAPIClient()

# Submit a batch
requests = [BatchRequest(custom_id="task1", params={...})]
batch_id = client.submit_batch(requests, description="My batch")

# Check status
status = client.get_batch_status(batch_id)

# Get results
results = client.poll_results(batch_id)
```

### Queue Manager (`queue_manager.py`)

Automatically monitors batch API capacity and submits queued jobs.

**Features:**
- Monitors active batch count
- Auto-submits when capacity available
- Respects job dependencies
- Updates queue state automatically
- Handles errors gracefully

**Usage:**

```python
from cortex.batch.queue_manager import BatchQueueManager

manager = BatchQueueManager(
    queue_file=Path("~/.cortex/batches/remediation_queue.json"),
    max_concurrent_batches=5,
    check_interval=300  # 5 minutes
)

# Run continuously
manager.run_continuous()

# Or process once
stats = manager.process_queue()
```

### CLI Helper (`queue.sh`)

Bash script for common queue operations.

```bash
# Start queue manager in background
cortex/batch/queue.sh start

# Check queue status
cortex/batch/queue.sh status

# View logs
cortex/batch/queue.sh logs

# Process queue once
cortex/batch/queue.sh process

# Stop queue manager
cortex/batch/queue.sh stop
```

---

## Queue Definition Format

Queue definitions are JSON files defining batched work.

```json
{
  "queue_version": "1.0",
  "priority_jobs": [
    {
      "id": "unique_job_id",
      "priority": "CRITICAL",  // CRITICAL | HIGH | MEDIUM | LOW
      "status": "queued",       // queued | submitted | completed
      "description": "Human readable description",
      "tasks": [
        {
          "task_id": "task_1",
          "title": "Short title",
          "context": "Background info for the task",
          "files_affected": ["path/to/file.py"],
          "prompt": "Full prompt for the LLM",
          "estimated_tokens": 2000
        }
      ],
      "estimated_total_tokens": 2000,
      "request_count": 1,
      "depends_on": ["other_job_id"]  // Optional dependencies
    }
  ],
  "queue_metadata": {
    "auto_submit": true,
    "check_interval_seconds": 300
  }
}
```

---

## Workflow

### 1. Create Queue Definition

```bash
# Start from template
cp cortex/batch/queues/queue_template.json cortex/batch/queues/my_queue.json

# Edit with your tasks
vim cortex/batch/queues/my_queue.json
```

### 2. Copy to Runtime Location

```bash
# Copy to runtime directory
cp cortex/batch/queues/my_queue.json ~/.cortex/batches/my_queue.json
```

### 3. Start Queue Manager

```bash
# Option 1: CLI helper (recommended)
cortex/batch/queue.sh start

# Option 2: Direct Python
export PYTHONPATH=/Users/jesse.kemp/Dev:$PYTHONPATH
export ANTHROPIC_API_KEY=$(security find-generic-password -s "anthropic-api-key" -w)
python3 cortex/batch/queue_manager.py --queue-file ~/.cortex/batches/my_queue.json
```

### 4. Monitor Progress

```bash
# Check status
cortex/batch/queue.sh status

# View live logs
cortex/batch/queue.sh logs
```

### 5. Retrieve Results

When jobs complete, results are stored in `~/.cortex/batches/results/msgbatch_*/`

```bash
# Using CLI (future)
cortex batch retrieve <batch_id>

# Manual
python3 -c "
from cortex.batch.batch_api_client import BatchAPIClient
client = BatchAPIClient()
results = client._retrieve_batch_results('msgbatch_...')
for r in results:
    print(r.custom_id, r.status)
"
```

---

## Integration with Cortex CLI

The queue system integrates with Cortex commands:

```bash
# Check queue status
cortex queue status

# List active batches
cortex batch status

# Start/stop queue manager
cortex queue start
cortex queue stop

# Submit new queue
cortex queue submit my_queue.json
```

*(Commands not yet implemented - see roadmap)*

---

## Examples

### Example 1: Code Remediation Queue

See `cortex/batch/queues/remediation_queue.json` for a real-world example of:
- Multi-task batch job
- Task dependencies
- Priority ordering
- Comprehensive prompts

### Example 2: Analysis Queue

```json
{
  "priority_jobs": [
    {
      "id": "security_analysis",
      "priority": "HIGH",
      "tasks": [
        {
          "task_id": "scan_secrets",
          "title": "Scan for hardcoded secrets",
          "prompt": "Scan all Python files for hardcoded API keys, passwords, tokens..."
        }
      ]
    }
  ]
}
```

---

## Roadmap

### Current Features
- ✅ Batch API client
- ✅ Queue manager with auto-submission
- ✅ CLI helper script
- ✅ Queue templates
- ✅ Dependency management

### Planned Features
- [ ] Integration with `cortex` CLI
- [ ] Web dashboard for monitoring
- [ ] Queue priority adjustment
- [ ] Retry logic for failed tasks
- [ ] Cost estimation and tracking
- [ ] Result processing pipelines
- [ ] Integration with portfolio memory (learn from batch results)

---

## Troubleshooting

### Queue manager not starting

```bash
# Check if already running
ps aux | grep queue_manager

# Check logs
tail -f ~/.cortex/batches/queue_manager.log

# Verify API key
echo $ANTHROPIC_API_KEY | cut -c1-20
```

### Jobs not submitting

1. Check batch capacity: `cortex/batch/queue.sh status`
2. Verify dependencies are completed
3. Check for errors in logs
4. Manually process: `cortex/batch/queue.sh process`

### Import errors

```bash
# Set PYTHONPATH
export PYTHONPATH=/Users/jesse.kemp/Dev:$PYTHONPATH

# Or use direnv (recommended)
cd /Users/jesse.kemp/Dev/cortex
# .envrc automatically sets PYTHONPATH
```

---

## Related Documentation

- [Cortex Analysis System](../analysis/README.md)
- [Portfolio Memory Integration](../intelligence/README.md)
- [Anthropic Batch API Docs](https://docs.anthropic.com/claude/reference/messages-batch)

---

**Last Updated:** 2026-01-20
