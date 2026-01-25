# Cortex Orchestration System

Core task queue infrastructure for managing long-running agent workflows with intelligent routing between realtime and batch execution.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Task Scheduler                         │
│  Routes tasks based on priority + deadline constraints     │
└──────────────┬────────────────────────────────┬─────────────┘
               │                                │
       ┌───────▼────────┐              ┌────────▼────────┐
       │   Realtime     │              │     Batch       │
       │   Execution    │              │   Execution     │
       │                │              │                 │
       │  - Priority A  │              │  - Priority C   │
       │  - Urgent B    │              │  - Delayed B    │
       │  - <2h deadline│              │  - No deadline  │
       └────────────────┘              └─────────────────┘
               │                                │
               │                                │
       ┌───────▼────────────────────────────────▼─────────┐
       │             Task Queue (SQLite)                  │
       │  - Priority ordering (A > B > C)                 │
       │  - Dependency tracking (blocked_by/blocks)       │
       │  - Persistent storage for crash recovery        │
       │  - Phase transitions (queued → ... → completed) │
       └──────────────────────────────────────────────────┘
```

## Components

### 1. Task (`task.py`)

Dataclass representing a single unit of work with:

- **Priority Levels**:
  - `A` (critical): Always realtime, immediate execution
  - `B` (important): Batch-eligible if deadline > 4 hours
  - `C` (background): Batch-only, overnight processing

- **Workflow Phases**:
  ```
  queued → investigating → planning → implementing → testing → completed/failed
  ```

- **Dependency Management**:
  - `blocked_by`: Tasks that must complete first
  - `blocks`: Tasks that depend on this one

- **Cost Estimation**:
  - Auto-calculates token estimates from description length
  - Tracks actual usage vs estimates

### 2. TaskQueue (`task_queue.py`)

Priority-based queue with SQLite persistence:

- **Features**:
  - FIFO within priority levels
  - Dependency-aware dequeuing (won't return blocked tasks)
  - Crash recovery via SQLite persistence
  - Efficient queries with indexes

- **Operations**:
  ```python
  queue = TaskQueue()

  # Add task
  queue.enqueue(task)

  # Get next ready task
  task = queue.dequeue(priority=TaskPriority.A)

  # Check what's ready
  ready = queue.get_ready_tasks(limit=10)

  # Mark complete (unblocks dependencies)
  queue.complete_task(task_id, result="Success")
  ```

### 3. TaskScheduler (`scheduler.py`)

Routes tasks between batch and realtime based on priority and deadline:

- **Routing Rules**:
  1. **Urgent override**: Deadline < 2h → always realtime
  2. **Priority A**: Always realtime (critical work)
  3. **Priority C**: Always batch (background work)
  4. **Priority B**: Batch if deadline > 4h, else realtime

- **Usage**:
  ```python
  scheduler = TaskScheduler()

  # Schedule and enqueue
  decision = scheduler.enqueue_and_schedule(task)
  print(f"Routed to: {decision.execution_mode}")
  print(f"Reason: {decision.reason}")

  # Get next realtime task
  task = scheduler.get_next_realtime_task()

  # Get batch tasks for submission
  batch_tasks = scheduler.get_next_batch_tasks(limit=10)

  # Re-evaluate as deadlines approach
  stats = scheduler.rebalance_queue()
  ```

## CLI Usage

```bash
# Add a critical task (routes to realtime)
python orchestration/cli.py add \
  --title "Fix production bug" \
  --description "Login endpoint returning 500" \
  --priority A

# Add an important task with deadline (batch-eligible)
python orchestration/cli.py add \
  --title "Refactor authentication" \
  --description "Clean up auth code" \
  --priority B \
  --deadline-hours 24

# Add background task (always batch)
python orchestration/cli.py add \
  --title "Generate API docs" \
  --description "Update API documentation" \
  --priority C \
  --source "docs" \
  --project "VortexV2"

# List ready tasks
python orchestration/cli.py list

# Show statistics
python orchestration/cli.py stats

# Get next task for execution
python orchestration/cli.py next --mode realtime
python orchestration/cli.py next --mode batch
```

## Example: Creating Tasks

```python
from datetime import datetime, timedelta
from orchestration import Task, TaskPriority, TaskScheduler

# Critical task - immediate realtime
critical_task = Task(
    id="critical-1",
    title="Fix production outage",
    description="Database connection pool exhausted",
    priority=TaskPriority.A,
)

# Important task with tight deadline - realtime
urgent_task = Task(
    id="urgent-1",
    title="Prepare demo for meeting",
    description="Create demo environment for client meeting",
    priority=TaskPriority.B,
    deadline=datetime.now() + timedelta(hours=2),
)

# Important task with relaxed deadline - batch
batch_eligible = Task(
    id="batch-1",
    title="Security audit",
    description="Scan codebase for vulnerabilities",
    priority=TaskPriority.B,
    deadline=datetime.now() + timedelta(hours=24),
)

# Background task - always batch
background = Task(
    id="background-1",
    title="Update dependencies",
    description="Check for outdated npm packages",
    priority=TaskPriority.C,
)

# Schedule all tasks
scheduler = TaskScheduler()

for task in [critical_task, urgent_task, batch_eligible, background]:
    decision = scheduler.enqueue_and_schedule(task)
    print(f"{task.title}: {decision.execution_mode}")

# Output:
# Fix production outage: realtime
# Prepare demo for meeting: realtime
# Security audit: batch
# Update dependencies: batch
```

## Example: Dependency Management

```python
from orchestration import Task, TaskPriority, TaskQueue

# Create dependent tasks
setup = Task(
    id="setup-1",
    title="Setup test environment",
    description="Create test database and fixtures",
    priority=TaskPriority.B,
)

test = Task(
    id="test-1",
    title="Run integration tests",
    description="Execute full test suite",
    priority=TaskPriority.B,
    blocked_by=["setup-1"],  # Can't run until setup completes
)

# Link dependency
setup.blocks = ["test-1"]

queue = TaskQueue()
queue.enqueue(setup)
queue.enqueue(test)

# Only setup is ready
ready = queue.get_ready_tasks()
assert len(ready) == 1
assert ready[0].id == "setup-1"

# Complete setup
queue.complete_task("setup-1")

# Now test is ready
ready = queue.get_ready_tasks()
assert len(ready) == 1
assert ready[0].id == "test-1"
```

## Integration with Existing Batch System

The orchestration system is designed to integrate with the existing batch infrastructure:

```python
from orchestration import TaskScheduler
from batch.batch_scheduler import BatchScheduler

# Get tasks scheduled for batch
task_scheduler = TaskScheduler()
batch_tasks = task_scheduler.get_next_batch_tasks(limit=10)

# Convert to batch API format
batch_scheduler = BatchScheduler()

for task in batch_tasks:
    batch_scheduler.schedule_task(
        title=task.title,
        description=task.description,
        prompt=task.prompt or task.description,
        priority=task.priority.value,
        deadline_hours=int(task.hours_until_deadline or 48),
    )
```

## Database Schema

Tasks are stored in SQLite with the following schema:

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL,
    deadline TEXT,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    -- ... additional fields
);

CREATE TABLE task_dependencies (
    task_id TEXT NOT NULL,
    blocks_task_id TEXT NOT NULL,
    PRIMARY KEY (task_id, blocks_task_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (blocks_task_id) REFERENCES tasks(id)
);
```

Default location: `~/.cortex/queue/tasks.db`

## Testing

```bash
# Run all tests
pytest orchestration/test_queue_system.py -v

# Run specific test class
pytest orchestration/test_queue_system.py::TestScheduler -v

# Run with coverage
pytest orchestration/test_queue_system.py --cov=orchestration
```

## Cost Savings

Batch routing provides significant cost savings:

- **50% cost reduction** for batch vs realtime (Anthropic Batch API)
- Automatic routing maximizes batch usage while respecting deadlines
- Cost estimation built-in:
  ```python
  savings = scheduler.estimate_batch_cost_savings()
  print(f"Potential savings: ${savings['savings_usd']:.2f}")
  ```

## Next Steps

This module provides the foundation for:

1. **Supervisor Agent**: Manages task execution, delegates to workers
2. **Worker Agents**: Execute individual tasks (investigate, plan, implement, test)
3. **Batch Integration**: Submit batch tasks to Anthropic Batch API
4. **Realtime Integration**: Route urgent tasks to interactive agents

See parent `cortex/` directory for integration points.

## File Reference

- `orchestration/task.py:1` - Task dataclass and enums
- `orchestration/task_queue.py:1` - Priority queue with SQLite persistence
- `orchestration/scheduler.py:1` - Batch vs realtime routing logic
- `orchestration/cli.py:1` - Command-line interface
- `orchestration/test_queue_system.py:1` - Comprehensive test suite
