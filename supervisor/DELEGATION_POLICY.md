# Supervisor Delegation Policy

## Overview

The Supervisor Delegator implements intelligent task routing to specialized AI agents. Instead of the supervisor handling all work directly, it delegates tasks to agents with specific expertise.

## Design Principles

### 1. Capability-Based Routing
Tasks are routed based on type matching:
- **Security tasks** → Security Analyst
- **Quality analysis** → Code Quality Agent
- **Testing tasks** → Test Engineer
- **Refactoring** → Refactoring Specialist
- **Research** → Research Agent

### 2. Load Balancing
When multiple agents can handle a task type, the delegator:
1. Checks each agent's current load
2. Filters to agents with available capacity
3. Selects the agent with lowest load percentage
4. Tracks assignment (increment on assign, decrement on complete)

### 3. Capacity Management
Each agent has a `max_concurrent` limit:
- Security Analyst: 2 (analysis is expensive)
- Code Quality: 4 (lighter workload)
- Test Engineer: 3 (balanced)
- Refactoring Specialist: 2 (needs focus)
- Research Agent: 3 (balanced)

When all capable agents are at capacity, tasks wait in queue.

### 4. Policy Enforcement
The `DelegationPolicy` explicitly defines:
- Which agents the supervisor can delegate to
- What task types each agent can handle
- Which task types require human approval
- Maximum batch size for delegations

This prevents "free-for-all" delegation and maintains control.

## Agent Capabilities

### Security Analyst
**Task Types:** security, vulnerability, audit, auth, encryption
**Max Concurrent:** 2
**Estimated Tokens:** 12,000
**Requires Approval:** Yes

Deep security analysis including:
- Vulnerability scanning
- Authentication/authorization review
- Security pattern detection
- Encryption implementation checks

### Code Quality
**Task Types:** pattern, quality, complexity, analysis, review
**Max Concurrent:** 4
**Estimated Tokens:** 8,000
**Requires Approval:** No

Code quality analysis:
- Anti-pattern detection
- Complexity metrics
- Code smell identification
- Best practice enforcement

### Test Engineer
**Task Types:** test, coverage, validation, qa, integration
**Max Concurrent:** 3
**Estimated Tokens:** 10,000
**Requires Approval:** No

Testing and validation:
- Test coverage analysis
- Test generation
- Integration test design
- Validation logic

### Refactoring Specialist
**Task Types:** refactor, cleanup, optimization, restructure
**Max Concurrent:** 2
**Estimated Tokens:** 15,000
**Requires Approval:** Yes

Refactoring work:
- Code restructuring
- Performance optimization
- Technical debt cleanup
- Architecture improvements

### Research Agent
**Task Types:** research, benchmarking, investigation, discovery
**Max Concurrent:** 3
**Estimated Tokens:** 10,000
**Requires Approval:** No

Research and investigation:
- Technology research
- Performance benchmarking
- Architecture investigation
- Best practice discovery

## Usage Example

```python
from supervisor.core import CortexSupervisor
from supervisor.delegator import DelegationPolicy
from supervisor.models import WorkItem, WorkItemPriority

# Initialize supervisor with default policy
supervisor = CortexSupervisor()

# Create work items
security_work = WorkItem(
    id="sec-001",
    source="github_alert",
    task_type="security",
    description="Review authentication flow for vulnerabilities",
    priority=WorkItemPriority.HIGH,
)

test_work = WorkItem(
    id="test-001",
    source="coverage_report",
    task_type="test",
    description="Add integration tests for payment API",
    priority=WorkItemPriority.MEDIUM,
)

# Route tasks (delegator handles internally)
security_routed = supervisor.delegator.route_task(security_work)
test_routed = supervisor.delegator.route_task(test_work)

# Check delegation status
stats = supervisor.get_delegation_summary()
print(f"Security Analyst load: {stats['agent_loads']['security_analyst']}")
print(f"Test Engineer load: {stats['agent_loads']['test_engineer']}")

# Complete task to free capacity
supervisor.delegator.complete_task("security_analyst")
```

## Custom Delegation Policies

You can create custom policies for specific needs:

```python
from supervisor.delegator import DelegationPolicy, AgentCapability

# Create custom policy with only test agents
custom_policy = DelegationPolicy(
    allowed_delegations={
        "test_specialist": AgentCapability(
            name="test_specialist",
            task_types={"test", "qa", "validation"},
            max_concurrent=5,
            estimated_tokens=8000,
        )
    },
    require_approval=set(),  # No approval needed
    max_batch_size=20,
)

# Use custom policy
supervisor = CortexSupervisor(delegation_policy=custom_policy)
```

## Integration with Supervisor Core

The delegator integrates seamlessly with `CortexSupervisor`:

1. **Initialization:** Delegator created with default or custom policy
2. **Task Discovery:** Supervisor discovers work items
3. **Routing:** Delegator routes tasks to capable agents
4. **Execution:** Tasks executed by AI batch or shell
5. **Completion:** Delegator updates agent load on completion
6. **Monitoring:** Delegation stats available via `get_delegation_summary()`

## Monitoring & Observability

### Check Agent Status
```python
# Get specific agent status
load = supervisor.delegator.get_agent_status("security_analyst")
print(f"Current tasks: {load.current_tasks}")
print(f"Available capacity: {load.available_capacity}")
print(f"Load percentage: {load.load_percentage * 100:.1f}%")
```

### Get Routing Statistics
```python
stats = supervisor.delegator.get_routing_stats()
# Returns:
# {
#   "total_agents": 5,
#   "available_agents": 3,
#   "busy_agents": 2,
#   "total_capacity": 14,
#   "total_used": 5,
#   "capacity_percentage": 35.7,
#   "agent_loads": { ... }
# }
```

### Reset Agent Load (Recovery)
```python
# If an agent crashes or needs reset
supervisor.delegator.reset_agent_load("security_analyst")
```

## Future Enhancements

### Phase 2: Dynamic Scaling
- Auto-adjust `max_concurrent` based on system load
- Spawn additional agents when queue builds up
- Scale down during low-load periods

### Phase 3: Learning & Optimization
- Track agent performance (accuracy, speed)
- Learn which agents handle which tasks best
- Optimize routing based on historical data

### Phase 4: Specialized Agents
- Domain-specific agents (VortexV2, Alpha Arena, etc.)
- Project-aware routing
- Context-sensitive delegation

## Testing

Run the full test suite:
```bash
pytest supervisor/test_delegator.py -v
pytest supervisor/test_integration_delegator.py -v
```

Tests cover:
- Capability matching
- Load balancing
- Capacity management
- Policy enforcement
- Integration with supervisor core
