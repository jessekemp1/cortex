# Cortex Planning Module - Layer 5

**Version:** 1.0
**Date:** 2025-12-24
**Status:** Production Ready

---

## Overview

The Planning Module (Layer 5) converts recommendations into actionable execution plans with task breakdown, dependency management, progress tracking, and time estimation.

### Key Features

- **Plan Generation**: Automatically convert recommendations into structured plans
- **Step Management**: Break down complex tasks into manageable steps
- **Dependency Tracking**: Ensure steps execute in the correct order
- **Progress Monitoring**: Track plan execution and completion
- **Time Estimation**: Estimate effort and completion dates
- **Persistence**: Save and load plans from disk
- **CLI Integration**: Full command-line interface for planning
- **Markdown Export**: Generate human-readable plan documents

---

## Architecture

```
Layer 5: Planning
├── models.py          # Data models (Plan, PlanStep, enums)
├── planner.py         # Plan creation and optimization
├── plan_executor.py   # Execution tracking and state management
└── __init__.py        # Public API

Integration Points:
├── RecommendationEngine  # Convert recommendations to plans
└── CortexBridge         # CLI access to planning
```

---

## Data Models

### Plan

Represents a complete execution plan.

**Attributes:**
- `id` (str): Unique plan identifier
- `title` (str): Plan title
- `description` (str): Plan description
- `priority` (PlanPriority): CRITICAL, HIGH, MEDIUM, or LOW
- `status` (PlanStatus): DRAFT, ACTIVE, COMPLETED, CANCELLED, or BLOCKED
- `steps` (List[PlanStep]): List of plan steps
- `estimated_total_time` (int): Total estimated time in minutes
- `actual_total_time` (int): Actual time taken
- `tags` (List[str]): Categorization tags
- `created_at`, `started_at`, `completed_at`: Timestamps

**Methods:**
- `add_step(step)`: Add a step to the plan
- `start()`: Mark plan as active
- `complete()`: Mark plan as completed
- `get_next_step()`: Get next executable step
- `get_progress()`: Get progress statistics
- `to_dict()`: Convert to dictionary
- `to_markdown()`: Export to markdown

### PlanStep

Represents a single step in a plan.

**Attributes:**
- `id` (str): Unique step identifier
- `title` (str): Brief step description
- `description` (str): Detailed description
- `status` (StepStatus): PENDING, IN_PROGRESS, COMPLETED, SKIPPED, or BLOCKED
- `estimated_time` (int): Estimated time in minutes
- `actual_time` (int): Actual time taken
- `dependencies` (List[str]): IDs of prerequisite steps
- `files` (List[str]): Files to modify/create
- `validation` (str): Validation criteria
- `notes` (str): Additional notes

**Methods:**
- `start()`: Mark step as in progress
- `complete()`: Mark step as completed
- `skip(reason)`: Skip this step
- `block(reason)`: Block this step
- `can_start(completed_steps)`: Check if dependencies are met

---

## Core Components

### Planner

Creates execution plans from recommendations.

```python
from intelligence.planning import Planner, PlanPriority

planner = Planner()

# Create plan from recommendations
plan = planner.create_plan_from_recommendations(
    recommendations=[rec1, rec2],
    title="Q1 Improvements",
    priority=PlanPriority.HIGH
)

# Create custom plan
plan = planner.create_custom_plan(
    title="Migrate to Python 3.12",
    description="Upgrade Python version",
    steps_config=[
        {
            "title": "Update requirements.txt",
            "description": "Update Python version constraint",
            "estimated_time": 15
        },
        {
            "title": "Test migration",
            "description": "Run test suite with Python 3.12",
            "estimated_time": 60,
            "dependencies": ["step-1"]
        }
    ],
    priority=PlanPriority.HIGH
)

# Add validation criteria
planner.add_validation_criteria(plan, {
    "step-1": "All tests pass",
    "step-2": "No deprecation warnings"
})

# Optimize step order
planner.optimize_plan_order(plan)
```

### PlanExecutor

Manages plan execution and state.

```python
from intelligence.planning import PlanExecutor

executor = PlanExecutor()

# Save plan
executor.save_plan(plan)

# Load plan
plan = executor.load_plan("plan-20251224-abc123")

# Start execution
executor.start_plan(plan)

# Get next step
next_step = executor.get_next_step()
print(f"Next: {next_step.title}")

# Start a step
executor.start_step(next_step.id)

# Complete a step
executor.complete_step(next_step.id, notes="All tests passed")

# Get progress
progress = executor.get_progress()
print(f"Progress: {progress['completion_pct']:.1f}%")

# List all plans
plans = executor.list_plans(status_filter=PlanStatus.ACTIVE)

# Export to markdown
markdown = executor.export_plan_markdown(plan.id)
```

---

## CLI Usage

### Create a Plan

```bash
# Create plan from recommendations
venv/bin/python bridge.py plan create cortex --title "Layer 3-4 Improvements"
```

**Output:**
```json
{
  "success": true,
  "plan_id": "plan-20251224-abc123",
  "title": "Layer 3-4 Improvements",
  "steps": 5,
  "estimated_time": 180,
  "message": "Plan created: plan-20251224-abc123"
}
```

### List Plans

```bash
# List all plans
venv/bin/python bridge.py plan list

# Filter by status
venv/bin/python bridge.py plan list --status active
```

### Show Plan Details

```bash
# Show as markdown (default)
venv/bin/python bridge.py plan show plan-20251224-abc123

# Show as JSON
venv/bin/python bridge.py plan show plan-20251224-abc123 --format json
```

### Start Plan Execution

```bash
venv/bin/python bridge.py plan start plan-20251224-abc123
```

**Output:**
```json
{
  "success": true,
  "plan_id": "plan-20251224-abc123",
  "status": "active",
  "next_step": {
    "id": "1.1",
    "title": "Improve test coverage",
    "description": "Add tests for edge cases"
  }
}
```

### Complete a Step

```bash
venv/bin/python bridge.py plan complete 1.1 --notes "Added 15 new test cases"
```

**Output:**
```json
{
  "success": true,
  "step_id": "1.1",
  "progress": {
    "total_steps": 5,
    "completed": 1,
    "completion_pct": 20.0
  },
  "next_step": {
    "id": "1.2",
    "title": "Refactor database code",
    "description": "Optimize connection pooling"
  },
  "completed": false
}
```

### Check Progress

```bash
venv/bin/python bridge.py plan progress
```

---

## Python API Usage

### Integration with RecommendationEngine

```python
from pathlib import Path
from recommendation_engine import RecommendationEngine
from intelligence.planning import PlanPriority

# Initialize engine
engine = RecommendationEngine(project_path=Path.cwd())

# Generate and create plan automatically
plan = engine.create_plan(
    title="Weekly Improvements",
    priority=PlanPriority.HIGH,
    auto_generate=True  # Auto-generate recommendations
)

# Start the plan
engine.start_plan(plan)

# Get next step
next_step = engine.get_next_step()
if next_step:
    print(f"Work on: {next_step.title}")

# Complete step
engine.complete_step(next_step.id, notes="Completed successfully")

# Check progress
progress = engine.get_plan_progress()
print(f"{progress['completed']}/{progress['total_steps']} steps done")
```

### Standalone Planning

```python
from intelligence.planning import Planner, PlanExecutor, PlanPriority
from recommendation_engine import Recommendation

# Create recommendations
recommendations = [
    Recommendation(
        type="coverage",
        title="Improve test coverage",
        description="Add tests for auth module",
        priority=85,
        confidence=0.9,
        steps=[
            "Review existing tests",
            "Identify gaps",
            "Write new tests"
        ]
    )
]

# Create plan
planner = Planner()
plan = planner.create_plan_from_recommendations(
    recommendations=recommendations,
    title="Q1 Testing Improvements",
    priority=PlanPriority.HIGH
)

# Execute plan
executor = PlanExecutor()
executor.save_plan(plan)
executor.start_plan(plan)

# Work through steps
while True:
    next_step = executor.get_next_step()
    if not next_step:
        break

    print(f"\n📋 {next_step.title}")
    print(f"📝 {next_step.description}")

    # Do the work...
    input("Press Enter when completed...")

    executor.start_step(next_step.id)
    executor.complete_step(next_step.id)

    progress = executor.get_progress()
    print(f"✅ Progress: {progress['completion_pct']:.1f}%")

print("\n🎉 Plan completed!")
```

---

## Storage

Plans are stored in `~/.cortex/plans/` as JSON files.

**File Structure:**
```
~/.cortex/plans/
├── plan-20251224-abc123.json
├── plan-20251224-def456.json
└── plan-20251223-ghi789.json
```

**Plan File Format:**
```json
{
  "id": "plan-20251224-abc123",
  "title": "Q1 Technical Improvements",
  "description": "...",
  "priority": 2,
  "status": "active",
  "steps": [
    {
      "id": "1.1",
      "title": "Step 1",
      "description": "...",
      "status": "completed",
      "estimated_time": 60,
      "actual_time": 55,
      "dependencies": [],
      "files": ["file.py"],
      "validation": "Tests pass",
      "notes": "Completed successfully"
    }
  ],
  "created_at": "2025-12-24T09:00:00",
  "started_at": "2025-12-24T09:15:00",
  "estimated_total_time": 180,
  "tags": ["testing", "quality"]
}
```

---

## Time Estimation

The planner uses heuristics to estimate time for steps:

| Keywords | Estimated Time |
|----------|----------------|
| refactor, migrate, redesign, rebuild | 120 minutes (2 hours) |
| implement, create, add, build | 60 minutes (1 hour) |
| update, modify, change, fix | 30 minutes |
| test, verify, validate | 15 minutes |
| Default | 45 minutes |

**Override Estimates:**
```python
step.estimated_time = 90  # Set custom estimate
```

**Calculate Completion Date:**
```python
completion_date = planner.estimate_completion_date(
    plan,
    hours_per_day=4
)
print(f"Expected completion: {completion_date}")
```

---

## Best Practices

1. **Break Down Large Tasks**: Split tasks > 2 hours into smaller steps
2. **Set Dependencies**: Use dependencies to enforce correct execution order
3. **Add Validation**: Define clear completion criteria for each step
4. **Track Notes**: Record important information when completing steps
5. **Update Estimates**: Adjust estimates based on actual time taken
6. **Export Plans**: Use markdown export for sharing and documentation
7. **Regular Progress Checks**: Monitor progress to identify blockers early

---

## Integration Examples

### With Alerts

```python
# Get alerts
alerts = engine.get_active_alerts("cortex")

# Convert to recommendations (handled internally)
recommendations = smart_generator.generate_alert_recommendations(alerts)

# Create plan
plan = planner.create_plan_from_recommendations(
    recommendations=recommendations,
    title="Alert Resolution Plan"
)
```

### With Goals

```python
from recommendation_engine import Goal

goals = [
    Goal(
        id="1",
        name="Reach 90% coverage",
        target_value=90.0,
        current_value=75.0,
        metric_type="coverage"
    )
]

# Generate goal-based recommendations
recommendations = engine.generate_recommendations(goals=goals)

# Create plan
plan = engine.create_plan(
    recommendations=recommendations,
    title="Coverage Improvement Plan"
)
```

---

## Performance

- **Plan Creation**: < 100ms
- **Step Execution**: < 10ms per operation
- **Plan Loading**: < 50ms
- **Progress Calculation**: < 5ms
- **Markdown Export**: < 20ms

---

## Future Enhancements

- [ ] Gantt chart visualization
- [ ] Team collaboration (assign steps to team members)
- [ ] Slack/email notifications on step completion
- [ ] Integration with calendar (schedule steps)
- [ ] Machine learning for better time estimates
- [ ] Plan templates
- [ ] Subtasks and nested plans
- [ ] Plan branching (if/else logic)

---

## See Also

- [Recommendation Engine API](api/layers_3_4.md)
- [User Guide](user_guide/getting_started.md)
- [Integration Tests](../tests/test_layer3_4_integration.py)

---

**Built with Claude Code**
**Date:** 2025-12-24
