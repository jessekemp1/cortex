# Orchestration Dashboard - Quick Start

## What It Shows

Real-time monitoring of Cortex batch task orchestration:

- **Queue Health**: Queued, active, and completed tasks
- **Active Tasks**: Real-time progress with phase indicators
- **Worker Pool**: Capacity utilization (5 workers max)
- **Alerts**: Blocked, slow, or failed tasks
- **Task Flow**: Sprint/wave organization and dependencies
- **Cost Tracking**: Daily spend and savings estimates

## Running

```bash
cd /Users/jesse.kemp/Dev/cortex

# Option 1: Direct
source venv/bin/activate
streamlit run dashboard/orchestration.py --server.port 8502

# Option 2: Background
source venv/bin/activate
streamlit run dashboard/orchestration.py --server.port 8502 --server.headless true &
```

Then open: http://localhost:8502

## Current Data

Based on test run:
- ✅ 39 tasks loaded from `~/.cortex/batch_queue.db`
- ✅ 59 batch API jobs from `~/.cortex/batches/`
- ✅ 4 sprints detected
- ✅ 4 waves detected
- ⚠️ 10 failed tasks (needs attention)

## Dashboard Layout

```
┌─────────────────────────────────────────────────┐
│ 📊 Queue Health | ⚡ Active Now | 💰 Cost      │
├─────────────────────────────────────────────────┤
│ 🚨 NEEDS ATTENTION (alerts)                     │
├────────────┬──────────────┬─────────────────────┤
│ 🔄 Active  │ 🤖 Workers   │ 🔀 Task Flow        │
│ Execution  │ Pool Status  │ (Sprints/Waves)     │
└────────────┴──────────────┴─────────────────────┘
```

## Key Features

1. **Auto-refresh**: Click 🔄 button to refresh data
2. **Progress tracking**: Live progress bars for running tasks
3. **Alert system**: Color-coded warnings (🔴 error, 🟡 warning, 🔵 info)
4. **Filtering**: Filter tasks by state, type in "All Tasks" tab
5. **Dependency viz**: Shows blocked tasks and dependency chains

## Integration

**Current (v1):**
- Reads: `~/.cortex/batch_queue.db` (BatchTaskQueue)
- Reads: `~/.cortex/batches/msgbatch_*_metadata.json`
- Uses: Task state, dependencies, sprint_id, wave_id

**Future (v2):**
- Will read: `~/.cortex/orchestration.db` (Worker 1's database)
- Enhanced: Real-time worker state, trace events, detailed metrics

## Files

- **Dashboard**: `dashboard/orchestration.py`
- **Docs**: `dashboard/ORCHESTRATION_DASHBOARD.md`
- **Queue Model**: `intelligence/process_monitor/batch_queue.py`
- **API Manager**: `batch/queue_manager.py`

## Troubleshooting

**Dashboard won't start:**
```bash
source venv/bin/activate
pip install streamlit pandas
```

**No data showing:**
- Check `~/.cortex/batch_queue.db` exists
- Run some batch tasks first
- Verify permissions on `.cortex` directory

**Port already in use:**
```bash
# Kill existing process
pkill -f "streamlit run"

# Or use different port
streamlit run dashboard/orchestration.py --server.port 8503
```

## Next Steps

1. Worker 1 will create `orchestration.db` with enhanced tracking
2. Dashboard will switch to reading from centralized database
3. Add real-time WebSocket updates
4. Add worker health monitoring
5. Add capacity planning recommendations
