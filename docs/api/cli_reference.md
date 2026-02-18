# Cortex CLI Reference

**Complete command-line interface reference**

This document provides a complete reference for all Cortex CLI commands.

---

## Table of Contents

1. [Main CLI Commands](#main-cli-commands)
2. [Bridge CLI Commands](#bridge-cli-commands)
3. [Data Agent CLI Commands](#data-agent-cli-commands)
4. [Common Workflows](#common-workflows)

---

## Main CLI Commands

### `cortex next [PROJECT]`

Get next recommended action.

**Options**:
- `PROJECT`: Optional project name filter
- `--with-context`: Include context predictions
- `--json`: Output JSON format
- `--limit N`: Number of alternative actions (default: 3)

**Examples**:
```bash
# Get next action
cortex next

# Get next action for specific project
cortex next vortexv2

# Get next action with context
cortex next --with-context

# Get next action in JSON format
cortex next --json
```

---

### `cortex status`

Show current state summary.

**Examples**:
```bash
# Show current state
cortex status
```

**Output**: Current projects, goals, blockers, system health

---

### `cortex health`

Show system health check.

**Examples**:
```bash
# Check system health
cortex health
```

**Output**: System health status, component availability

---

### `cortex feedback [OPTIONS]`

Log feedback for recommendations.

**Options**:
- `--action-title TITLE`: Title of the action/recommendation
- `--action-id ID`: ID of the action
- `--useful yes|no`: Was it useful?
- `--notes NOTES`: Optional notes
- `--outcome OUTCOME`: What actually happened?
- `--stats [recent]`: Show feedback statistics
- `--log NOTE`: Quick log entry

**Examples**:
```bash
# Log feedback
cortex feedback --action-title "Implement feature X" --useful yes --notes "Worked well"

# Show feedback statistics
cortex feedback --stats

# Show recent feedback
cortex feedback --stats recent

# Quick log entry
cortex feedback --log "Completed task Y"
```

---

### `cortex briefing`

Generate daily briefing.

**Examples**:
```bash
# Generate daily briefing
cortex briefing
```

**Output**: Daily summary of projects, goals, metrics

---

### `cortex schedule [OPTIONS]`

Schedule a recommendation as an automated agent.

**Options**:
- `--schedule CRON`: Custom cron schedule (default: immediate)
- `--project PROJECT`: Project name

**Examples**:
```bash
# Schedule current recommendation
cortex schedule

# Schedule with custom cron
cortex schedule --schedule "0 9 * * *"  # Daily at 9 AM

# Schedule for specific project
cortex schedule --project vortexv2
```

---

### `cortex execute [OPTIONS]`

Execute a scheduled agent.

**Options**:
- `--agent-id ID`: Agent identifier
- `--context JSON`: Context payload

**Examples**:
```bash
# Execute agent
cortex execute --agent-id agent_123
```

---

### `cortex learn`

Show learning metrics and patterns.

**Examples**:
```bash
# Show learning metrics
cortex learn
```

**Output**: Learning metrics, patterns, recommendations

---

### `cortex dashboard`

Show Symbiosis Engine Dashboard.

**Examples**:
```bash
# Show dashboard
cortex dashboard
```

**Output**: Unified dashboard with metrics, health, recommendations

---

### `cortex check [PROJECT]`

Check project compliance with Golden Spec.

**Options**:
- `PROJECT`: Optional project name (default: all projects)

**Examples**:
```bash
# Check all projects
cortex check

# Check specific project
cortex check vortexv2
```

**Output**: Compliance scores, phase status, recommendations

---

### `cortex draft INTENT [--project PROJECT]`

Draft a new Golden Spec from intent.

**Options**:
- `INTENT`: The intent or goal of the project
- `--project PROJECT`: Project name (optional, defaults to current dir)

**Examples**:
```bash
# Draft spec for current directory
cortex draft "Build weather forecast validation system"

# Draft spec for specific project
cortex draft "Build trading system" --project alpha_arena
```

---

## Bridge CLI Commands

### `python bridge.py context QUERY [--project PROJECT]`

Get context for a query.

**Options**:
- `QUERY`: Natural language query
- `--project PROJECT`: Optional project filter

**Examples**:
```bash
# Get context
python bridge.py context "GRIB data processing"

# Get context for specific project
python bridge.py context "API rate limiting" --project cortex
```

---

### `python bridge.py portfolio stats`

Get portfolio statistics.

**Examples**:
```bash
# Get portfolio stats
python bridge.py portfolio stats
```

**Output**: Project counts, tech stacks, patterns, lessons

---

### `python bridge.py portfolio patterns [--type TYPE]`

Get cross-project patterns.

**Options**:
- `--type TYPE`: Optional pattern type filter

**Examples**:
```bash
# Get all patterns
python bridge.py portfolio patterns

# Get patterns by type
python bridge.py portfolio patterns --type async_fastapi
```

---

### `python bridge.py portfolio lessons [--project PROJECT] [--pattern PATTERN]`

Get lessons learned.

**Options**:
- `--project PROJECT`: Filter by project
- `--pattern PATTERN`: Filter by pattern

**Examples**:
```bash
# Get all lessons
python bridge.py portfolio lessons

# Get lessons for project
python bridge.py portfolio lessons --project VortexV2

# Get lessons for pattern
python bridge.py portfolio lessons --pattern data_processing
```

---

### `python bridge.py portfolio project NAME`

Get project context.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Get project context
python bridge.py portfolio project VortexV2
```

---

### `python bridge.py intelligence REQUEST --project PROJECT [--type TYPE]`

Query unified intelligence system.

**Options**:
- `REQUEST`: User request string
- `--project PROJECT`: Project name (required)
- `--type TYPE`: Query type (spec/impl/analysis/research, default: spec)

**Examples**:
```bash
# Query intelligence
python bridge.py intelligence "implement API rate limiting" --project cortex --type impl
```

---

### `python bridge.py similar-work DOMAIN --project PROJECT [--limit N]`

Find similar work.

**Options**:
- `DOMAIN`: Domain/topic
- `--project PROJECT`: Project name (required)
- `--limit N`: Maximum results (default: 5)

**Examples**:
```bash
# Find similar work
python bridge.py similar-work "ensemble forecasting" --project VortexV2 --limit 5
```

---

### `python bridge.py session-context [--format FORMAT] [--max-chars N]`

Get session context.

**Options**:
- `--format FORMAT`: Output format (json/terminal/compact, default: json)
- `--max-chars N`: Max characters for compact format (default: 450)

**Examples**:
```bash
# Get session context (JSON)
python bridge.py session-context

# Get session context (terminal)
python bridge.py session-context --format terminal

# Get session context (compact)
python bridge.py session-context --format compact --max-chars 450
```

---

### `python bridge.py index-spec PATH --project PROJECT [--domain DOMAIN]`

Index a specification file.

**Options**:
- `PATH`: Path to spec file
- `--project PROJECT`: Project name (required)
- `--domain DOMAIN`: Optional domain tag

**Examples**:
```bash
# Index a spec
python bridge.py index-spec docs/ARCHITECTURE.md --project cortex --domain architecture
```

---

### `python bridge.py health summary [--days N]`

Get portfolio health summary.

**Options**:
- `--days N`: Days to analyze (default: 7)

**Examples**:
```bash
# Get health summary
python bridge.py health summary

# Get health summary for 30 days
python bridge.py health summary --days 30
```

---

### `python bridge.py health project NAME [--days N]`

Get detailed project health.

**Options**:
- `NAME`: Project name
- `--days N`: Days to analyze (default: 7)

**Examples**:
```bash
# Get project health
python bridge.py health project cortex --days 30
```

---

### `python bridge.py health compare PROJECT1 PROJECT2 [--days N]`

Compare two projects.

**Options**:
- `PROJECT1`: First project name
- `PROJECT2`: Second project name
- `--days N`: Days to analyze (default: 7)

**Examples**:
```bash
# Compare projects
python bridge.py health compare cortex VortexV2 --days 30
```

---

### `python bridge.py health trends NAME`

Get health trends for project.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Get health trends
python bridge.py health trends cortex
```

---

### `python bridge.py plan create PROJECT [--title TITLE]`

Create a plan from recommendations.

**Options**:
- `PROJECT`: Project name
- `--title TITLE`: Optional plan title

**Examples**:
```bash
# Create plan
python bridge.py plan create cortex --title "Implement API rate limiting"
```

---

### `python bridge.py plan list [--status STATUS]`

List all plans.

**Options**:
- `--status STATUS`: Filter by status (draft/active/completed/cancelled)

**Examples**:
```bash
# List all plans
python bridge.py plan list

# List active plans
python bridge.py plan list --status active
```

---

### `python bridge.py plan show PLAN_ID [--format FORMAT]`

Show plan details.

**Options**:
- `PLAN_ID`: Plan identifier
- `--format FORMAT`: Output format (json/markdown, default: markdown)

**Examples**:
```bash
# Show plan (markdown)
python bridge.py plan show plan_123

# Show plan (JSON)
python bridge.py plan show plan_123 --format json
```

---

### `python bridge.py plan start PLAN_ID`

Start plan execution.

**Options**:
- `PLAN_ID`: Plan identifier

**Examples**:
```bash
# Start plan
python bridge.py plan start plan_123
```

---

### `python bridge.py plan complete STEP_ID [--notes NOTES]`

Complete a plan step.

**Options**:
- `STEP_ID`: Step identifier
- `--notes NOTES`: Optional completion notes

**Examples**:
```bash
# Complete step
python bridge.py plan complete step_456 --notes "Implemented rate limiter"
```

---

### `python bridge.py plan progress`

Show active plan progress.

**Examples**:
```bash
# Show progress
python bridge.py plan progress
```

---

### `python bridge.py profile PROJECT`

Analyze project structure and tech stack.

**Options**:
- `PROJECT`: Project name

**Examples**:
```bash
# Analyze project
python bridge.py profile cortex
```

---

### `python bridge.py patterns PROJECT TASK [--limit N]`

Find similar work from other projects.

**Options**:
- `PROJECT`: Current project name
- `TASK`: Task description
- `--limit N`: Maximum results (default: 5)

**Examples**:
```bash
# Find patterns
python bridge.py patterns cortex "implement rate limiting" --limit 5
```

---

## Data Agent CLI Commands

### `python -m cortex.agents.data_agent.cli summary [DAYS]`

Portfolio health summary.

**Options**:
- `DAYS`: Days to analyze (default: 7)

**Examples**:
```bash
# Get summary
python -m cortex.agents.data_agent.cli summary

# Get summary for 30 days
python -m cortex.agents.data_agent.cli summary 30
```

---

### `python -m cortex.agents.data_agent.cli project NAME [DAYS]`

Project analysis.

**Options**:
- `NAME`: Project name
- `DAYS`: Days to analyze (default: 7)

**Examples**:
```bash
# Analyze project
python -m cortex.agents.data_agent.cli project cortex 30
```

---

### `python -m cortex.agents.data_agent.cli compare PROJ1 PROJ2 [DAYS]`

Compare projects.

**Options**:
- `PROJ1`: First project name
- `PROJ2`: Second project name
- `DAYS`: Days to analyze (default: 7)

**Examples**:
```bash
# Compare projects
python -m cortex.agents.data_agent.cli compare cortex VortexV2 30
```

---

### `python -m cortex.agents.data_agent.cli trends NAME`

Health trends for project.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Get trends
python -m cortex.agents.data_agent.cli trends cortex
```

---

### `python -m cortex.agents.data_agent.cli deps NAME`

Dependency analysis.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Analyze dependencies
python -m cortex.agents.data_agent.cli deps cortex
```

---

### `python -m cortex.agents.data_agent.cli deps-health NAME`

Dependency health check.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Check dependency health
python -m cortex.agents.data_agent.cli deps-health cortex
```

---

### `python -m cortex.agents.data_agent.cli deps-circular NAME`

Find circular dependencies.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Find circular dependencies
python -m cortex.agents.data_agent.cli deps-circular cortex
```

---

### `python -m cortex.agents.data_agent.cli deps-graph NAME [FORMAT]`

Export dependency graph.

**Options**:
- `NAME`: Project name
- `FORMAT`: Output format (ascii/dot/mermaid, default: ascii)

**Examples**:
```bash
# Export graph (ASCII)
python -m cortex.agents.data_agent.cli deps-graph cortex

# Export graph (Mermaid)
python -m cortex.agents.data_agent.cli deps-graph cortex mermaid

# Export graph (DOT)
python -m cortex.agents.data_agent.cli deps-graph cortex dot
```

---

### `python -m cortex.agents.data_agent.cli deps-package NAME`

Get package dependencies.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Get package dependencies
python -m cortex.agents.data_agent.cli deps-package cortex
```

---

### `python -m cortex.agents.data_agent.cli deps-compare NAME`

Compare declared vs actual dependencies.

**Options**:
- `NAME`: Project name

**Examples**:
```bash
# Compare dependencies
python -m cortex.agents.data_agent.cli deps-compare cortex
```

---

### `python -m cortex.agents.data_agent.cli deps-portfolio [PROJECT]`

Portfolio-wide dependency analysis.

**Options**:
- `PROJECT`: Optional project filter

**Examples**:
```bash
# Analyze portfolio
python -m cortex.agents.data_agent.cli deps-portfolio

# Analyze specific project
python -m cortex.agents.data_agent.cli deps-portfolio cortex
```

---

## Common Workflows

### Daily Workflow

```bash
# Morning briefing
cortex status
cortex briefing
python bridge.py portfolio stats

# Before coding
python bridge.py intelligence "your task" --project yourproject --type impl

# After task
cortex feedback --action-title "Task X" --useful yes
```

---

### Project Analysis Workflow

```bash
# Get project context
python bridge.py portfolio project cortex

# Analyze dependencies
python -m cortex.agents.data_agent.cli deps cortex
python -m cortex.agents.data_agent.cli deps-health cortex

# Check health
python bridge.py health project cortex --days 30
```

---

### Spec Indexing Workflow

```bash
# Index single spec
python bridge.py index-spec docs/ARCHITECTURE.md --project cortex

# Index all specs (programmatic)
python3 -c "
from intelligence.spec_knowledge_base import SpecKnowledgeBase
kb = SpecKnowledgeBase()
count = kb.index_project('/path/to/project', 'ProjectName')
print(f'Indexed {count} specs')
"
```

---

### Planning Workflow

```bash
# Create plan
python bridge.py plan create cortex --title "Implement feature"

# List plans
python bridge.py plan list --status active

# Start plan
python bridge.py plan start plan_123

# Complete step
python bridge.py plan complete step_456 --notes "Done"

# Check progress
python bridge.py plan progress
```

---

## Output Formats

### JSON Format

Most commands support JSON output:

```bash
# JSON output
cortex next --json
python bridge.py portfolio stats  # Default JSON
```

### Terminal Format

Some commands support terminal format:

```bash
# Terminal format
python bridge.py session-context --format terminal
```

### Compact Format

Session context supports compact format for hooks:

```bash
# Compact format (<450 chars)
python bridge.py session-context --format compact --max-chars 450
```

---

## Error Handling

All commands return appropriate exit codes:
- `0`: Success
- `1`: Error

Error messages are printed to stderr.

---

## References

- [API Documentation](../API.md) - Python API reference
- [User Guide](../user_guide/getting_started.md) - Getting started
- [Examples](../user_guide/examples.md) - Usage examples

---

**Version**: 1.0  
**Last Updated**: 2025-12-24
