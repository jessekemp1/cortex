# Cortex Orchestration Dashboard

**Location:** `cortex/dashboard/orchestration.py`
**URL:** http://localhost:8502
**Status:** ✅ Working

## Overview

Real-time dashboard for monitoring batch task orchestration across the Cortex system.

## Features

### 1. Header Metrics (3-column layout)

**📊 Queue Health**
- Queued tasks count
- Active tasks count
- Completed today count

**⚡ Active Now**
- Current running task count
- Current phase/task type

**💰 Cost Today**
- Daily spend estimate
- Budget percentage used
- Savings vs interactive usage

### 2. Needs Attention Panel

Alerts for tasks requiring intervention:
- **Blocked tasks** (waiting on dependencies)
- **Slow tasks** (running > 2x estimated duration)
- **Failed tasks** (with error messages)

Color-coded by severity:
- 🔴 Error
- 🟡 Warning
- 🔵 Info

### 3. Three-Column Main View

**🔄 Active Execution (Left)**
- Real-time progress bars for running tasks
- Phase indicators (Initializing → Processing → Finalizing → Completing)
- Elapsed vs estimated time
- Recent completions list

**🤖 Agent Pool Status (Middle)**
- Worker capacity visualization (5 workers max)
- Worker status (ACTIVE/IDLE)
- Queue depth metrics
- Queue breakdown by priority

**🔀 Task Flow (Right)**
- Sprint progress tracking
- Wave progress tracking
- Dependency chain visualization
- Blocked task alerts

### 4. Detailed Tabs

**📋 All Tasks**
- Filterable task table
- Filter by state, type
- Configurable limit
- Shows: task_id, description, state, type, priority, created_at

**🔄 Batch API Jobs**
- Lists batch jobs from `~/.cortex/batches/`
- Shows metadata for each batch
- Status indicators (🔄 in_progress, ✅ ended, ⏳ validating, ❌ failed)

**📊 Statistics**
- Task state breakdown
- Task type distribution
- Average duration by type
- Success rate calculation

## Data Sources

### Primary Database
- `~/.cortex/batch_queue.db` (BatchTaskQueue from `intelligence/process_monitor/batch_queue.py`)
- Table: `batch_tasks`
- 39 tasks loaded (as of test)

### Batch API Data
- `~/.cortex/batches/msgbatch_*_metadata.json`
- 59 batch jobs loaded (as of test)

### Cost Tracking
- Estimates based on task metadata
- Token counts (input/output)
- Rough pricing: $3 per 1M input, $15 per 1M output

## Running the Dashboard

```bash
# From cortex directory
source venv/bin/activate
streamlit run dashboard/orchestration.py --server.port 8502
```

Or using the existing script pattern:
```bash
./run_with_venv.sh streamlit run dashboard/orchestration.py --server.port 8502
```

## Integration Points

### Current (v1)
- Reads from existing `batch_queue.db`
- Parses batch API metadata files
- Uses task state, dependencies, sprints, waves

### Future (v2 - Worker 1's orchestration.db)
- Will read from centralized orchestration database
- Enhanced worker state tracking
- Real-time trace events
- More detailed metrics

## Visual Design

- Dark theme with colored metrics
- Progress bars for running tasks
- Color-coded alerts (red/yellow/blue)
- Responsive 3-column layout
- Expandable detail views

## Task State Management

Supports all `BatchTask` states:
- `pending` - Created, not scheduled
- `scheduled` - Scheduled for future execution
- `running` - Currently executing
- `completed` - Successfully done
- `failed` - Execution failed
- `cancelled` - Manually cancelled

## Dependency Tracking

- Visualizes dependency chains
- Detects blocked tasks (dependencies not met)
- Shows sprint/wave organization
- Calculates progress percentages

## Performance Metrics

- Average duration by task type
- Success rate (completed vs failed)
- Queue depth trends
- Worker utilization

## Quick Reference

**Key Files:**
- `dashboard/orchestration.py` - Main dashboard
- `intelligence/process_monitor/batch_queue.py` - Task queue model
- `batch/queue_manager.py` - Batch API manager

**Key Functions:**
- `load_batch_queue_tasks()` - Loads from SQLite
- `analyze_task_states()` - Aggregates state metrics
- `detect_needs_attention()` - Finds alerts
- `get_running_tasks_with_progress()` - Calculates progress
- `estimate_daily_cost()` - Cost tracking

## Test Results

```
✅ Loaded 39 tasks from batch_queue.db
✅ Loaded 59 batch API jobs
✅ Task states: {'queued': 0, 'active': 0, 'completed_today': 0, 'failed': 10, 'cancelled': 17, 'total': 39}
✅ Cost metrics: spend=$0.00, savings=$0.00
```

Dashboard successfully running at http://localhost:8502
