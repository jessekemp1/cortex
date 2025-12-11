# Converx - Strategic Orchestrator

**Converx** is a thin orchestration layer that combines existing tools to answer: **"What should I do next?"**

## Quick Start

```bash
# Get next action
python -m converx.cli next

# Get next action for specific project
python -m converx.cli next vortexv2

# Get next action with context
python -m converx.cli next --with-context

# JSON output
python -m converx.cli next --json

# Show current state
python -m converx.cli status
```

## What It Does

Converx orchestrates existing tools to provide a unified strategist interface:

- **Project Activity**: Uses `ai_intelligence.py` to scan git repositories
- **Goals**: Uses `goal_parser.py` to extract goals from `ACTION_PLAN.md`
- **Recommendations**: Uses `recommendation_engine.py` to generate strategic recommendations
- **Context**: Uses `context_intelligence.py` to predict needed context

## Installation

No installation required! Converx uses existing tools in your repository.

**Requirements**:
- Python 3.10+
- Existing tools: `ai_intelligence.py`, `goal_parser.py`, `recommendation_engine.py`, `context_intelligence.py`

## Usage

### Get Next Action

```bash
python -m converx.cli next
```

Returns the top priority next action with:
- Current state summary (projects, goals, blockers)
- Next action with rationale
- Alternative actions
- Optional context predictions

### Project-Specific Recommendations

```bash
python -m converx.cli next vortexv2
```

Filters recommendations to focus on a specific project.

### Include Context

```bash
python -m converx.cli next --with-context
```

Includes context predictions from `context_intelligence.py`.

### JSON Output

```bash
python -m converx.cli next --json
```

Outputs structured JSON for programmatic use.

### Show Status

```bash
python -m converx.cli status
```

Shows current state summary without recommendations.

## Output Format

Example output:

```
╔══════════════════════════════════════════════════════╗
║              CONVERX - STRATEGIC NEXT ACTION             ║
╚══════════════════════════════════════════════════════╝

📊 CURRENT STATE
────────────────
Active Projects: 3 (3+ commits in 7d)
Priority A Goals: 2
Goals: 1 in progress, 2 pending
Blockers: 1
  • VortexV2: Missing .env file

🎯 NEXT ACTION
────────────────
[HIGH PRIORITY] Complete Block 1.2: Sensor Data Preprocessing

Why: Priority A goal from ACTION_PLAN.md. Blocks VortexV2 MVP 
completion (currently 60% complete). High commercial value (⭐⭐⭐⭐⭐).

Effort: 4-6 hours
Impact: High
Confidence: 90%

Next Steps:
  • Migrate sensor preprocessing from Vortex
  • Add outlier detection, quality scoring
  • Create API endpoint for sensor data ingestion

Related Projects: VortexV2
Related Goals: vortexv2-mvp-completion

────────────────────────────────────────────────────────────
💡 ALTERNATIVE ACTIONS
────────────────────────────────────────────────────────────
2. 🟡 [MEDIUM] Configure environment for keto-tracker
   Quick fix can unblock progress.
```

## Architecture

Converx is a thin orchestration layer:

```
┌─────────────────────────────────────────────────────────┐
│                    converx CLI                          │
│  (converx next [PROJECT])                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ConverxOrchestrator                        │
│  - Calls ai_intelligence.py (project activity)          │
│  - Calls goal_parser.py (goals)                        │
│  - Calls recommendation_engine.py (recommendations)      │
│  - Calls context_intelligence.py (context)             │
│  - Formats output as strategist response               │
└─────────────────────────────────────────────────────────┘
```

## Integration

Converx integrates with existing tools:

- **ai_intelligence.py**: Project activity tracking
- **goal_parser.py**: Goal extraction from ACTION_PLAN.md
- **recommendation_engine.py**: Strategic recommendations
- **context_intelligence.py**: Context prediction
- **personal-ai-dataset**: Knowledge search (via context_intelligence)

## Error Handling

Converx gracefully handles missing tools:

- If a tool is unavailable, it continues with available tools
- Warnings are printed to stderr
- Output still provides value with partial data

## Performance

- **Startup**: <1 second
- **Execution**: <5 seconds (including all tool calls)
- **Memory**: <50MB

## Troubleshooting

### "No recommendations available"

**Possible causes**:
- ACTION_PLAN.md not found or empty
- No active projects detected
- recommendation_engine.py unavailable

**Solutions**:
- Check ACTION_PLAN.md exists and has goals
- Run `python ai_intelligence.py` to verify project scanning
- Verify recommendation_engine.py is in repository root

### "Warning: Could not scan projects"

**Possible causes**:
- Git not installed
- No git repositories in root directory
- Permission issues

**Solutions**:
- Verify git is installed: `git --version`
- Check root directory has git repos
- Verify read permissions

### Import errors

**Possible causes**:
- Missing dependencies
- Python path issues

**Solutions**:
- Ensure all tools are in repository root
- Run from repository root: `cd /Users/jesse.kemp/Dev`

## Development

### File Structure

```
converx/
├── __init__.py          # Package initialization
├── cli.py                # CLI entry point
├── orchestrator.py       # Core orchestration logic
├── formatter.py          # Output formatting
├── README.md             # This file
└── tests/                # Test files
```

### Running Tests

```bash
cd /Users/jesse.kemp/Dev
python -m pytest converx/tests/
```

## Future Enhancements

Post-MVP features (only if MVP proves useful):

- Virtual twin simulation
- Strategic projections (optimistic/likely/conservative)
- Multi-domain Life Weather Map
- Route & waypoint tracking
- Reflection & learning system

## License

Part of the Dev monorepo. See repository root for license.

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review existing tool documentation
3. Check ACTION_PLAN.md for goal structure

