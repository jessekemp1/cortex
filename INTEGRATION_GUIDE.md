# Cortex-Local-Orchestrator Integration Guide

**Date**: December 8, 2025  
**Status**: Complete

---

## Overview

This guide documents the integration between Cortex (strategic orchestrator) and local-orchestrator (task execution system). The integration was built in 3 phases using coordination agent teams.

---

## Architecture

### Integration Flow

```
Cortex (Strategic Decisions)
    ↓
Integration Layer (Adapter)
    ↓
Local-Orchestrator (Task Execution)
    ↓
Execution History
    ↓
Learning & Feedback
    ↓
Cortex (Improved Recommendations)
```

### Components

1. **Integration Adapter** (`cortex/integration/local_orchestrator.py`)
   - Converts Cortex recommendations to local-orchestrator agents
   - Manages scheduling and registration

2. **History Analyzer** (`cortex/integration/history_analyzer.py`)
   - Analyzes execution history from local-orchestrator
   - Calculates success rates and metrics

3. **Feedback Loop** (`cortex/integration/feedback_loop.py`)
   - Bidirectional feedback between systems
   - Adjusts recommendations based on execution results

---

## Usage

### Schedule a Recommendation

```bash
# Schedule the current top recommendation
cortex schedule

# Schedule with custom cron schedule
cortex schedule --schedule "0 9 * * *"  # Daily at 9 AM

# Schedule recommendation for specific project
cortex schedule --project vortexv2
```

### Check Learning Metrics

```python
from cortex.integration.feedback_loop import FeedbackLoop

feedback = FeedbackLoop()
metrics = feedback.get_learning_metrics()
print(metrics)
```

---

## Agent Teams

The integration was built using 3 coordination agent teams:

### Phase 1: Fix Local-Orchestrator
- Fixed import isolation issues
- Verified agent registration
- Created import isolation utilities

### Phase 2: Add Integration Layer
- Created integration adapter
- Added `cortex schedule` command
- Implemented recommendation-to-agent conversion

### Phase 3: Enhanced Integration
- Added execution history analysis
- Implemented learning mechanisms
- Created bidirectional feedback loop

---

## Running All Phases

To run all integration phases:

```bash
python3 cortex/agents/integration/run_all_phases.py
```

This will:
1. Execute Phase 1 (fix local-orchestrator)
2. Execute Phase 2 (add integration layer)
3. Execute Phase 3 (enhanced integration)

---

## Testing

### Run Integration Tests

```bash
# Test integration components
pytest cortex/tests/test_integration_local_orchestrator.py

# Test learning and adaptation
pytest cortex/tests/test_integration_learning.py

# Test all phases
pytest cortex/tests/test_integration_phases.py
```

---

## Files Created

### Integration Modules
- `cortex/integration/__init__.py`
- `cortex/integration/local_orchestrator.py`
- `cortex/integration/history_analyzer.py`
- `cortex/integration/feedback_loop.py`
- `cortex/integration/metrics.py`

### Agent Teams
- `cortex/agents/integration/base_coordination_agent.py`
- `cortex/agents/integration/team_coordinator.py`
- `cortex/agents/integration/phase1_agent.py`
- `cortex/agents/integration/phase2_agent.py`
- `cortex/agents/integration/phase3_agent.py`
- `cortex/agents/integration/run_all_phases.py`

### Local-Orchestrator
- `local-orchestrator/utils/import_isolation.py`
- `local-orchestrator/agents/integration/phase1_agent.py`

### Tests
- `cortex/tests/test_integration_local_orchestrator.py`
- `cortex/tests/test_integration_learning.py`
- `cortex/tests/test_integration_phases.py`

---

## Success Criteria

### Phase 1
- ✅ Import isolation utility created
- ✅ Agent wrappers can load without conflicts
- ✅ Agent registration verified

### Phase 2
- ✅ Integration adapter functional
- ✅ `cortex schedule` command works
- ✅ Recommendations can be scheduled

### Phase 3
- ✅ Execution history analysis working
- ✅ Learning mechanisms active
- ✅ Feedback loop operational

---

## Next Steps

1. **Use the Integration**: Start scheduling recommendations
2. **Monitor Learning**: Check metrics to see how recommendations improve
3. **Extend**: Add more sophisticated learning algorithms
4. **Optimize**: Fine-tune priority adjustments based on results

---

## Troubleshooting

### Integration Not Available

If `cortex schedule` says integration not available:
1. Check that local-orchestrator is installed
2. Verify dependencies: `apscheduler`, `fastapi`, `uvicorn`
3. Check that local-orchestrator can be imported

### Learning Not Working

If learning metrics show as unavailable:
1. Verify execution history is being tracked
2. Check that `ExecutionHistory` class is accessible
3. Ensure local-orchestrator is running and recording executions

---

## References

- `local-orchestrator/PROJECT_ASSESSMENT.md` - Original assessment
- `cortex/README.md` - Updated with integration docs
- `local-orchestrator/HARSH_ASSESSMENT.md` - Phase 1 completion status
