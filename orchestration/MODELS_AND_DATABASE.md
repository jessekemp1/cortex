# Orchestration Models and Database

## Overview

This document describes the core data models and database schema for the Cortex orchestration system. These components provide the foundation for managing long-running agent workflows with dependency tracking, capacity management, and audit logging.

## Files Created

### 1. `/Users/jesse.kemp/Dev/cortex/orchestration/models.py`

Comprehensive data models that unify concepts from multiple existing systems:
- `batch/orchestrator.py` (JobState, APIJob, LocalJob)
- `intelligence/process_monitor/batch_queue.py` (BatchTask)
- `batch/intelligent_orchestrator.py` (BatchWorkItem)
- `orchestration/task.py` (Task, TaskPhase)

#### Key Models

**ExecutionBackend (Enum)**
Determines how and where a task is executed:
- `LOCAL_SYNC`: Immediate local shell execution (foreground)
- `LOCAL_BATCH`: Scheduled local execution (background queue)
- `API_BATCH`: Anthropic Batch API (overnight processing)
- `API_REALTIME`: Anthropic Messages API (immediate processing)

**WorkerRole (Enum)**
Agent roles in the orchestration system:
- `SUPERVISOR`: Delegates and monitors
- `INVESTIGATOR`: Analyzes and researches
- `PLANNER`: Designs solutions
- `IMPLEMENTER`: Writes code
- `TESTER`: Validates quality
- `REVIEWER`: Code review

**ValidationCriteria (Dataclass)**
Defines test requirements and success patterns for task validation:
- Test requirements (unit, integration, e2e)
- Test coverage targets (min_coverage_percent)
- Required test commands
- Success/failure regex patterns
- Required files to exist after completion
- Performance requirements (max_execution_seconds)
- Custom validation logic

**WorkerState (Dataclass)**
Tracks state and capacity of an agent/worker:
- Identity (worker_id, role)
- Capacity tracking (max_concurrent_tasks, current_task_count)
- Availability status
- Performance metrics (tasks completed/failed, average duration)
- Current load (assigned_task_ids)
- Specialization tags for routing
- Methods: `assign_task()`, `complete_task()`, `mark_unavailable()`, `mark_available()`

**TraceEvent (Dataclass)**
Audit trail entry for orchestration decisions and events:
- Event identity (event_id, event_type, timestamp)
- Context (task_id, worker_id)
- Event data (message, details dict)
- Metadata (phase, backend)

**TraceEventType (Enum)**
Types of trace events:
- Task lifecycle: `TASK_CREATED`, `TASK_SCHEDULED`, `TASK_STARTED`, `TASK_PHASE_CHANGED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_RETRIED`
- Dependency: `TASK_BLOCKED`, `TASK_UNBLOCKED`
- Worker: `WORKER_ASSIGNED`, `WORKER_CAPACITY_CHANGED`
- System: `BACKEND_SELECTED`, `VALIDATION_RUN`, `DECISION_MADE`, `ERROR_OCCURRED`

#### Helper Functions

- `create_task_event()`: Create trace event for task action
- `create_worker_event()`: Create trace event for worker action
- `create_decision_event()`: Create trace event for routing/scheduling decision

### 2. `/Users/jesse.kemp/Dev/cortex/orchestration/database.py`

SQLite database for orchestration system with persistent storage for tasks, workers, trace events, and validation criteria.

#### Database Schema

**tasks table**
Stores all task information:
- Core: id, title, description, priority, deadline
- Workflow: phase, status
- Dependencies: blocked_by (JSON array), blocks (JSON array)
- Execution: prompt, context (JSON), files_affected (JSON)
- Tokens: estimated/actual input/output tokens
- Execution context: execution_mode, execution_backend, batch_id, assigned_agent
- Results: result, error, validation_passed
- Metadata: created_at, started_at, completed_at, tags (JSON), source, project

**validation_criteria table**
Stores validation requirements for tasks:
- task_id (foreign key)
- Test flags: requires_unit_tests, requires_integration_tests, requires_e2e_tests
- Coverage: min_coverage_percent
- Commands: test_commands (JSON array)
- Patterns: success_patterns (JSON array), failure_patterns (JSON array)
- Files: required_files (JSON array)
- Performance: max_execution_seconds
- Custom: custom_validator

**worker_states table**
Stores worker capacity and performance:
- Identity: worker_id, role
- Capacity: max_concurrent_tasks, current_task_count, is_available, unavailable_reason
- Metrics: total_tasks_completed, total_tasks_failed, average_task_duration_minutes
- Current state: assigned_task_ids (JSON array), specialties (JSON array)
- Timestamps: last_task_started_at, last_task_completed_at, created_at, updated_at

**trace_events table**
Audit log for all orchestration events:
- Event: event_id, event_type, timestamp
- Context: task_id, worker_id
- Data: message, details (JSON)
- Metadata: phase, backend

#### Indexes

Performance indexes on:
- Tasks: status, phase, priority, deadline, created_at, execution_backend, assigned_agent, source, project
- Workers: role, is_available
- Trace events: timestamp, task_id, worker_id, event_type

#### Key Methods

**Task Operations**
- `create_task(task, validation)`: Create task with optional validation criteria
- `get_task(task_id)`: Retrieve task by ID
- `get_validation_criteria(task_id)`: Get validation criteria for task
- `update_task(task)`: Update task
- `update_task_phase(task_id, phase)`: Update task phase
- `update_task_execution_backend(task_id, backend)`: Update execution backend
- `get_ready_tasks(limit)`: Get tasks ready to execute (not blocked, PENDING status)
- `get_blocked_tasks()`: Get tasks blocked by dependencies
- `get_running_tasks()`: Get currently running tasks
- `get_completed_task_ids()`: Get set of completed task IDs
- `unblock_dependent_tasks(completed_task_id)`: Unblock tasks that depend on completed task
- `get_tasks_by_status(status, limit)`: Filter tasks by status
- `get_tasks_by_phase(phase, limit)`: Filter tasks by phase

**Worker Operations**
- `create_worker(worker)`: Create worker
- `get_worker(worker_id)`: Get worker by ID
- `update_worker(worker)`: Update worker state
- `get_available_workers(role)`: Get available workers, optionally filtered by role

**Trace Event Operations**
- `add_trace_event(event)`: Add trace event to audit log
- `get_trace_events(task_id, worker_id, event_type, limit)`: Query trace events with filters

**Migration**
- `migrate_from_batch_queue(batch_queue_db_path)`: Migrate tasks from existing batch_queue.db

**Statistics**
- `get_stats()`: Get database statistics (task counts, worker counts, event counts)

#### Database Features

- WAL mode for concurrent access
- Foreign keys enabled
- Automatic schema creation
- Proper boolean conversion (SQLite INTEGER 0/1 to Python bool)
- JSON serialization for complex fields
- Comprehensive error handling

### 3. `/Users/jesse.kemp/Dev/cortex/orchestration/test_database.py`

Comprehensive test suite verifying:
- Database creation and initialization
- Task CRUD operations with validation criteria
- Dependency tracking and unblocking
- Worker state management and capacity tracking
- Trace event logging and retrieval
- Migration from existing batch_queue.db

**Test Results**: All 6 tests passing
- Database creation
- Task operations (create, retrieve, update, validation)
- Dependency tracking (blocked/unblocked tasks)
- Worker operations (capacity, assignments, metrics)
- Trace events (logging, retrieval)
- Migration (39 tasks migrated from batch_queue.db)

### 4. Updated `/Users/jesse.kemp/Dev/cortex/orchestration/__init__.py`

Added exports for new models and database:
- `ExecutionBackend`
- `WorkerRole`
- `WorkerState`
- `TraceEvent`
- `TraceEventType`
- `ValidationCriteria`
- `OrchestrationDatabase`
- `create_task_event()`
- `create_worker_event()`
- `create_decision_event()`

## Design Decisions

### 1. Unified Task Model
Rather than creating separate task types for different backends, we use a single `Task` model with an `execution_backend` field. This simplifies the codebase and allows tasks to be rerouted if needed.

### 2. Separate Validation Criteria
Validation criteria is stored in a separate table with a foreign key to tasks. This:
- Keeps the tasks table lean
- Allows optional validation (most tasks won't have detailed criteria)
- Makes it easy to query tasks without loading validation data

### 3. JSON for Complex Fields
Arrays and dictionaries (blocked_by, blocks, context, tags, etc.) are stored as JSON strings. This:
- Maintains SQLite compatibility (no array types)
- Allows flexible schema evolution
- Simplifies queries (no join tables needed)

### 4. Boolean Storage
SQLite stores booleans as INTEGER (0/1). The database layer handles conversion:
- Python bool → SQLite INTEGER when writing
- SQLite INTEGER → Python bool when reading

### 5. Trace Events
Comprehensive audit logging through TraceEvent provides:
- Debugging capability (what happened and when)
- Analysis of orchestration decisions
- Performance insights (duration tracking)
- Compliance/accountability

### 6. Worker State
WorkerState tracks agent capacity for intelligent delegation:
- Prevents overloading agents
- Enables load balancing
- Tracks performance metrics
- Supports specialization-based routing

## Integration Points

### For Worker 2 (Dashboard)
The dashboard can read from the orchestration database to display:
```python
from orchestration import OrchestrationDatabase

db = OrchestrationDatabase()
stats = db.get_stats()
ready_tasks = db.get_ready_tasks(limit=20)
running_tasks = db.get_running_tasks()
workers = db.get_available_workers()
recent_events = db.get_trace_events(limit=50)
```

### For Worker 3 (Optimizer)
The optimizer uses the Task model and database queries:
```python
from orchestration import OrchestrationDatabase, TaskPriority

db = OrchestrationDatabase()

# Find high-priority tasks ready to run
ready = db.get_ready_tasks(limit=100)
high_priority = [t for t in ready if t.priority == TaskPriority.A]

# Check capacity
workers = db.get_available_workers()
available_capacity = sum(w.max_concurrent_tasks - w.current_task_count for w in workers)
```

### For Worker 4 (Supervisor)
The supervisor uses WorkerState for delegation:
```python
from orchestration import OrchestrationDatabase, WorkerRole, create_worker_event

db = OrchestrationDatabase()

# Find best worker for task
implementers = db.get_available_workers(role=WorkerRole.IMPLEMENTER)
best_worker = min(implementers, key=lambda w: w.current_task_count)

# Assign task
best_worker.assign_task(task.id)
db.update_worker(best_worker)

# Log decision
event = create_worker_event(
    TraceEventType.WORKER_ASSIGNED,
    best_worker,
    f"Assigned task {task.id} to {best_worker.worker_id}",
    task_id=task.id,
)
db.add_trace_event(event)
```

## Database Location

Default: `~/.cortex/orchestration.db`

Can be overridden:
```python
from pathlib import Path
db = OrchestrationDatabase(db_path=Path("/custom/path/orchestration.db"))
```

## Migration from Existing Systems

The database includes migration logic for `batch_queue.db`:
```python
from pathlib import Path
from orchestration import OrchestrationDatabase

db = OrchestrationDatabase()
batch_queue_path = Path.home() / ".cortex" / "batch_queue.db"
migrated_count = db.migrate_from_batch_queue(batch_queue_path)
print(f"Migrated {migrated_count} tasks")
```

Migration maps:
- BatchTask → Task
- Old priority (immediate/high/normal/low) → New priority (A/B/C)
- Old TaskState → New TaskPhase + TaskStatus
- Command stored in context dict

## Next Steps

1. **Worker 2 (Dashboard)**: Use database queries to populate Streamlit dashboard
2. **Worker 3 (Optimizer)**: Implement adaptive batch queue optimization using Task queries
3. **Worker 4 (Supervisor)**: Implement delegation logic using WorkerState
4. **Integration**: Connect to existing batch/orchestrator.py and intelligent_orchestrator.py

## Testing

Run tests:
```bash
PYTHONPATH=/path/to/cortex:$PYTHONPATH python orchestration/test_database.py
```

Expected output: **All 6 tests passing**
