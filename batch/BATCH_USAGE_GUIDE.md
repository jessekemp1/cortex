# Cortex Batch API Usage Guide

**Goal: Move 40% of work to Batch API for 50% cost savings**

## Quick Start

### Submit a Batch Job

```bash
# From /path/to/cortex

# Code review
python batch/quick_batch.py review path/to/file.py

# Documentation
python batch/quick_batch.py docs path/to/module/

# Research question
python batch/quick_batch.py research "Should we use Redis for caching?"

# Security audit (whole codebase)
python batch/quick_batch.py security

# Pattern analysis
python batch/quick_batch.py patterns

# Test coverage gaps
python batch/quick_batch.py test-gaps path/to/tests/
```

### Check Status

```bash
python batch/quick_batch.py status
# or
python batch/dashboard.py
```

### Or Use Slash Commands

```
/batch-submit review src/api.py
/batch-submit research "Compare FastAPI vs Flask"
/batch-status
/batch-retrieve <batch_id>
/batch-orchestrate   # Fill overnight queue automatically
```

## When to Use Batch

**YES - Good for Batch (40% target):**
- Code reviews (PRs, file changes)
- Documentation generation
- Research questions
- Security audits
- Test coverage analysis
- Refactoring suggestions
- Architecture analysis
- Dependency audits

**NO - Keep Real-time:**
- Interactive debugging
- Urgent bug fixes
- Live coding sessions
- Quick questions needing immediate answers

## How It Works

1. **Submit** - Job goes to scheduler queue
2. **Schedule** - Jobs submit at 6 PM (or immediately if high priority)
3. **Process** - Anthropic Batch API processes overnight (50% cheaper)
4. **Results** - Available by morning in `/briefing` or via `/batch-retrieve`

## Architecture

```
User                Scheduler              Anthropic API
  |                    |                        |
  |-- quick_batch.py ->|                        |
  |                    |-- (at 6 PM) ---------->|
  |                    |                        |
  |                    |<-- (overnight) --------|
  |                    |                        |
  |<-- /briefing ------|                        |
```

## Cost Savings

| Operation | Real-time | Batch | Savings |
|-----------|-----------|-------|---------|
| Code review (15K tokens) | $0.68 | $0.34 | 50% |
| Research (5K tokens) | $0.23 | $0.11 | 50% |
| Security audit (30K tokens) | $1.35 | $0.68 | 50% |

*Estimated at Opus pricing: ~$45/M tokens average*

## Automation

Nightly automation is already configured:
- **10 PM**: Intelligent Orchestrator fills overnight queue
- **Overnight**: Batch API processes jobs
- **Morning**: Results in `/briefing`

To manually trigger overnight queue:
```bash
python batch/intelligent_orchestrator.py
# or
/batch-orchestrate
```

## Templates Available

| Template | Description | Default Priority |
|----------|-------------|------------------|
| review | Code review | normal |
| docs | Documentation | low |
| research | Research/analysis | normal |
| security | Security audit | high |
| patterns | Anti-pattern scan | normal |
| test-gaps | Test coverage | normal |

## Options

```bash
python batch/quick_batch.py <type> <target> [options]

Options:
  --priority {low,normal,high}  Job priority
  --deadline N                  Hours until needed (default: 24)
  --context "text"              Additional context
  --json                        Output as JSON
```

## Monitoring

### Dashboard
```bash
python batch/dashboard.py
```

Shows:
- API batch status
- Local queue status
- Performance metrics
- Cost savings
- Recommendations

### Optimization Report
```bash
python batch/usage_optimizer.py
```

Shows compliance with burn rate targets.

## Troubleshooting

### Jobs not submitting?
```bash
# Check daemon is running
launchctl list | grep cortex.batch

# Restart daemon
launchctl kickstart -k gui/$(id -u)/com.cortex.batch-daemon
```

### Can't find results?
```bash
# Check if batch completed
python batch/dashboard.py

# Retrieve specific batch
/batch-retrieve <batch_id>
```

### Low batch adoption?
Run `/batch-orchestrate` at end of day to auto-fill queue.

## Files

| File | Purpose |
|------|---------|
| `batch/quick_batch.py` | Easy one-command submission |
| `batch/dashboard.py` | Comprehensive status view |
| `batch/batch_scheduler.py` | Core scheduling logic |
| `batch/intelligent_orchestrator.py` | Auto queue filling |
| `batch/queue_manager.py` | API submission/polling |
| `batch/usage_optimizer.py` | Burn rate tracking |

## Target Metrics

- **Batch adoption**: 40% of work
- **Cost savings**: 50% on batch work
- **Daily sustainable**: 8.6 hours real-time
- **Weekly limit**: 60 hours total
