# Cortex Execution Engine

## Overview

The Execution Engine closes the loop in the Cortex Intelligence Platform:

```
Signal Detection → Contract Generation → EXECUTION → Verification → Health Monitoring
```

## Architecture

### Core Components

1. **ContractExecutor** (`intelligence/executor.py`)
   - Parses TaskContracts into executable steps
   - Executes steps using bash, read, edit, write actions
   - Verifies success criteria (tests, metrics, benchmarks)
   - Reports results to health monitor

2. **ExecutionStep** (dataclass)
   - Represents single atomic action
   - Types: bash, read, edit, write
   - Tracks completion status and output

3. **ExecutionResult** (dataclass)
   - Captures execution outcome
   - Success/failure status
   - Verification results (tests, metrics)
   - Error messages and logs

## Workflow

### 1. Contract Parsing
```python
steps = await executor._parse_contract_to_steps(contract)
```

Uses Sonnet 4.5 to analyze contract requirements and generate actionable steps:
- Analyzes requirements, constraints, success criteria
- Generates sequential execution plan
- Determines action type (bash, read, edit, write)
- Fallback to requirement-based steps if AI parsing fails

### 2. Step Execution
```python
for step in steps:
    success = await executor._execute_step(step, contract)
```

Executes each step based on action type:

**Bash**: Run shell commands
- Determines working directory from contract context
- 5-minute timeout per command
- Captures stdout/stderr

**Read**: Load file contents
- Validates file exists
- Stores first 1000 chars for context

**Edit/Write**: File modifications (PLACEHOLDER)
- Currently safety-gated for MVP
- Logs intent without modifying files
- Requires explicit approval in production

### 3. Success Verification
```python
await executor._verify_success_criteria(contract, result)
```

Verifies all success criteria:

**Tests**:
- Extracts test commands from criteria
- Runs pytest or specified test suite
- 10-minute timeout
- Parses exit code for pass/fail

**Metrics**:
- Placeholder for metric verification
- Would integrate with dashboard_data.json
- Currently assumes pass for MVP

**Benchmarks**:
- Manual verification checklist
- Flags for human review
- Not auto-verified

### 4. Result Persistence
```python
executor._save_result(result)
```

Saves execution results to `~/.cortex/execution_results/`:
- Contract ID
- Status and success flag
- Step completion count
- Verification results
- Timestamps and duration
- Error messages

## Usage

### CLI Commands

**Execute a contract directly**:
```bash
# Interactive with dry run
cortex execute <contract_id>

# Skip dry run
cortex execute <contract_id> --no-dry-run
```

**Programmatic usage**:
```python
from intelligence.executor import ContractExecutor

executor = ContractExecutor()

# Dry run first
result = await executor.execute_contract(contract, dry_run=True)
print(f"Would execute {result.steps_total} steps")

# Real execution
result = await executor.execute_contract(contract, dry_run=False)

if result.success:
    print(f"✅ Success in {result.execution_time_seconds:.1f}s")
else:
    print(f"❌ Failed: {result.error_message}")
```

## Safety Features

### Risk-Based Execution

Only LOW and MEDIUM risk contracts execute automatically:
- **Low risk**: Tests, docs, analysis - no production impact
- **Medium risk**: Feature additions, refactors - tested and reversible
- **High/Critical**: Require explicit human approval

### Human Gates

Contracts specify mandatory approval points:
- `START`: Approve before beginning
- `REVIEW`: Approve before deployment
- `PRODUCTION`: Approve before production push

### File Modification Safety

For MVP, edit and write operations are **gated**:
- Logs intent without modifying files
- Returns success for planning purposes
- Actual modifications require:
  1. Human review of proposed changes
  2. Explicit approval
  3. Production-grade LLM code editing

### Execution Limits

- **Time limit**: 15 minutes per contract (5 min per command)
- **Retry limit**: 3 attempts (configurable in contract)
- **Cost limit**: $5-10 per contract (configurable)

## Integration

### Health Monitor Integration

Execution results update health metrics:
- Success rate (target: >85%)
- Cycle time (target: <4 hours)
- Active executors count
- Tasks completed/failed (24h)

### Batch Orchestrator Integration

Contracts can be queued for batch execution:
```python
orchestrator = BatchOrchestrator()
job_id = orchestrator.submit_job(job_data, auto_detect=True)
```

Execution engine can be invoked from:
- Direct CLI (`cortex execute`)
- Batch queue processing
- API endpoints (future)

## Testing

Run executor tests:
```bash
pytest intelligence/tests/test_executor.py -v
```

Test coverage:
- ✅ Contract parsing into steps
- ✅ Bash command execution
- ✅ File read operations
- ✅ Success verification
- ✅ Error handling
- ✅ Result persistence
- ✅ Dry run mode

## Metrics

Tracked per execution:
- `execution_time_seconds`: Total time
- `steps_completed/steps_total`: Progress
- `tests_passed`: Boolean
- `metrics_met`: Boolean
- `cost_usd`: API costs
- `attempts`: Retry count

## Future Enhancements

### Phase 2: Full File Editing
- LLM-powered code generation
- Syntax validation
- Git diff preview before applying
- Rollback on failure

### Phase 3: Advanced Verification
- Real-time metric collection
- Dashboard integration for metrics
- Benchmark automation
- Visual regression testing

### Phase 4: Parallel Execution
- Dependency graph analysis
- Parallel step execution where safe
- Resource pooling
- Load balancing

### Phase 5: Learning Loop
- Execution pattern recognition
- Failed execution analysis
- Success strategy extraction
- Contract refinement based on outcomes

## Troubleshooting

**Execution fails immediately**:
- Check contract requirements are clear
- Verify working directory is correct
- Ensure dependencies exist

**Tests fail during verification**:
- Review test output in result file
- Check test command extraction logic
- Verify test environment is set up

**Steps timeout**:
- Increase timeout in executor (default: 5 min)
- Break complex steps into smaller atomic steps
- Check for infinite loops in commands

**File operations don't work**:
- Edit/write are gated in MVP
- Use bash commands for file operations temporarily
- Or execute steps manually with approval

## Files

Core implementation:
- `intelligence/executor.py`: Main executor (650 lines)
- `intelligence/tests/test_executor.py`: Tests (350 lines)

Integration:
- `mvp/cli.py`: CLI commands
- `health/monitor.py`: Health tracking
- `batch/orchestrator.py`: Batch queue

Results:
- `~/.cortex/execution_results/`: Execution logs
- `~/.cortex/health_history/`: Health snapshots
