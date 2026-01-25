# Batch Architecture Analysis
**Date:** 2026-01-21
**Issue:** Intelligent orchestrator jobs sitting in wrong queue
**Root Cause:** Two separate batch systems with overlapping names

---

## The Two Batch Systems

### System 1: ProcessMonitor BatchTaskQueue (Older - Dec 2025)
**Purpose:** Local shell command execution and task management
**Location:** `intelligence/process_monitor/batch_queue.py`
**Storage:** SQLite database at `~/.cortex/batch_queue.db`
**Used By:**
- ProcessMonitor daemon (`intelligence/process_monitor/daemon.py`)
- BatchExecutor (`intelligence/process_monitor/batch_executor.py`)
- Supervisor health monitoring (`supervisor/core.py`, `supervisor/health.py`)
- V2a sprint orchestrator (`batch/v2a_sprint_orchestrator.py`)
- Cortex runtime API (`runtime/api.py`)

**Execution Model:**
- Tasks are **shell commands** executed locally via `subprocess.run()`
- Examples: `pytest tests/`, `python scripts/analyze.py`, bash scripts
- Supports dependency chains, waves, sprints
- Has executor that runs commands in background threads
- Max 3 concurrent local tasks by default

**CLI Interface:**
```bash
python cli.py batch add "pytest tests/" --type test --priority high
python cli.py batch list
python cli.py batch status
```

**Key Features:**
- ✅ Dependency management (tasks can wait for other tasks)
- ✅ Wave/sprint organization
- ✅ Local execution with output capture
- ✅ Retry logic for failed commands
- ✅ Deeply integrated with ProcessMonitor
- ❌ NOT for Anthropic Batch API

---

### System 2: BatchQueueManager (Newer - Jan 21, 2026 - TODAY!)
**Purpose:** Anthropic Batch API job submission and management
**Location:** `batch/queue_manager.py`
**Storage:** JSON file at `~/.cortex/batches/remediation_queue.json`
**Used By:**
- queue_manager.py itself (standalone daemon, PID 87433 running right now!)
- **SHOULD be used by:** intelligent_orchestrator.py (but isn't!)

**Execution Model:**
- Tasks are **LLM prompts** submitted to Anthropic Batch API
- Examples: "Analyze code quality", "Generate documentation", "Security audit"
- Converts job definitions into BatchRequest objects
- Submits to Claude API as message batches
- Max 5 concurrent API batches

**CLI Interface:**
```bash
# Currently: None! (Should have cortex batch-api add/list/status)
# Actually controlled via:
python batch/queue_manager.py --status-only
python batch/queue_manager.py  # Run daemon
```

**Key Features:**
- ✅ Automatic submission when API capacity available
- ✅ Priority-based job ordering
- ✅ Dependency support (job chains)
- ✅ Daemon running 24/7 checking every 5 minutes
- ✅ Cost optimization (50% cheaper overnight)
- ❌ NOT integrated with CLI
- ❌ NOT discoverable to other systems

---

## The Collision (Jan 21, 2026)

### What Happened
1. **intelligent_orchestrator.py** generates 5 analysis jobs:
   - Test Coverage Gap Analysis
   - Code Quality Analysis
   - Dependency Version Audit
   - Documentation Completeness Audit
   - Performance Bottleneck Detection

2. **Submission attempt** calls:
   ```python
   subprocess.run([
       "python", "cli.py", "batch", "add",
       job.description, "--priority", job.priority
   ])
   ```

3. **Wrong system activated:**
   - CLI's `batch add` routes to `ProcessMonitor.batch_queue.add_task()`
   - ProcessMonitor tries to execute descriptions as shell commands
   - Commands fail with exit code 127 (command not found)
   - Example: Tries to run `"Test Coverage Gap Analysis"` as a bash command!

4. **Right system ignored:**
   - queue_manager daemon running (PID 87433, iteration #182)
   - Monitoring `remediation_queue.json` every 5 minutes
   - Queue is EMPTY (0 jobs pending)
   - Has 5 API slots available
   - **Sitting idle while work piles up in wrong queue**

---

## Architecture Issues

### Issue 1: Naming Collision
Both systems use "batch" terminology but mean completely different things:
- ProcessMonitor: "batch" = group of local shell tasks
- BatchQueueManager: "batch" = Anthropic Batch API job

### Issue 2: No Bridge
intelligent_orchestrator needs to submit to Anthropic API but no clear path exists:
- ❌ Can't use `cortex batch add` (goes to ProcessMonitor)
- ❌ No `cortex batch-api add` command
- ❌ Must write directly to remediation_queue.json

### Issue 3: Two Different Job Formats
**ProcessMonitor expects:**
```python
{
  "command": "pytest tests/",
  "task_type": "test",
  "priority": "high"
}
```

**BatchQueueManager expects:**
```json
{
  "id": "job_123",
  "description": "Analyze code quality",
  "priority": "HIGH",
  "tasks": [
    {
      "task_id": "task_1",
      "title": "...",
      "prompt": "...",
      "files_affected": [...]
    }
  ]
}
```

### Issue 4: Discoverability
- ProcessMonitor batch queue: Integrated into CLI, documented, easy to use
- BatchQueueManager: Standalone daemon, no CLI, must know file paths

---

## Current State

### ProcessMonitor Batch Queue
```
Status: ✅ Active
Location: ~/.cortex/batch_queue.db
CLI: python cli.py batch {add,list,status}
Tasks: 20+ (mostly failed orchestrator jobs)
Running: via ProcessMonitor daemon
Health: ✅ Working as designed
```

### BatchQueueManager
```
Status: ✅ Active (PID 87433)
Location: ~/.cortex/batches/remediation_queue.json
CLI: ❌ None
Tasks: 0 (empty queue)
Running: Standalone daemon, checking every 5min
Health: ✅ Working but starved of work
```

### Intelligent Orchestrator
```
Status: ❌ Broken integration
Generated Jobs: 5 analysis tasks
Submission: Attempted via wrong queue (ProcessMonitor)
Current State: Jobs failed in ProcessMonitor, never reached API
Next Steps: Need proper integration with BatchQueueManager
```

---

## Usage Patterns Identified

### Local Execution (ProcessMonitor)
✅ **Appropriate for:**
- Running pytest test suites
- Executing build scripts
- Running linters/formatters
- Data processing scripts
- Git operations
- File system operations

❌ **NOT appropriate for:**
- LLM-based analysis
- Code review generation
- Documentation generation
- Research tasks
- Anything requiring Claude API

### API Batch Jobs (BatchQueueManager)
✅ **Appropriate for:**
- Code quality analysis
- Security audits
- Documentation generation
- Test coverage analysis
- Research synthesis
- Pattern detection
- Architecture reviews

❌ **NOT appropriate for:**
- Running actual tests
- Building code
- File operations
- System commands

---

## Dependencies Map

```
┌─────────────────────────────────────────────────┐
│         ProcessMonitor BatchTaskQueue           │
│                (Local Execution)                │
└─────────────────────────────────────────────────┘
           ▲           ▲           ▲
           │           │           │
      ┌────┴───┐  ┌───┴────┐  ┌───┴────┐
      │ CLI    │  │Supervisor│  │V2a     │
      │        │  │          │  │Sprint  │
      └────────┘  └──────────┘  └────────┘


┌─────────────────────────────────────────────────┐
│          BatchQueueManager (Anthropic API)      │
│                                                 │
└─────────────────────────────────────────────────┘
           ▲
           │
      ┌────┴─────────────┐
      │ queue_manager.py │
      │ (standalone)     │
      └──────────────────┘


┌─────────────────────────────────────────────────┐
│      intelligent_orchestrator.py                │
│                                                 │
│  ❌ Calls: CLI batch add (ProcessMonitor)      │
│  ✅ Should: Write to remediation_queue.json    │
└─────────────────────────────────────────────────┘
```

---

## Analysis Complete

**Architectural Split Reason:**
Two legitimately different use cases that were built independently:
1. Local task execution (Dec 2025) - mature, integrated
2. API batch orchestration (Jan 21, 2026) - new, standalone

**Why They Don't Talk:**
- Built on different dates by different patterns
- ProcessMonitor system came first, established patterns
- BatchQueueManager built as new capability, not integrated
- intelligent_orchestrator assumed "batch" meant ProcessMonitor

**Impact:**
- ❌ Overnight batch jobs not running (0.8% utilization instead of 40%+)
- ❌ Cost optimization not happening (should save 50% on analysis)
- ❌ Manual `/batch-orchestrate` required instead of automated
- ❌ Work sitting in failed queue instead of processing

**Next:** Design unified orchestration that routes to correct system
