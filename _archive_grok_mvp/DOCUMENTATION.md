# Converx Compiled Documentation

This file aggregates all documentation from DESIGN_SPEC.md, README.md, IMPLEMENTATION_COMPLETE.md, OPUS_DESIGN.md, and source code.

## Overview
Converx is a strategic orchestrator that answers \"What should I do next?\" by unifying project activity, goals, recommendations, and context into actionable insights. It's a thin layer over existing tools, designed as a \"cognitive exoskeleton\" for developers and strategists.

- **Core Value**: Turns reactive busyness into directed progress.
- **Tech Stack**: Python 3.10+ (stdlib only for MVP).
- **Dependencies**: None new; integrates with ai_intelligence.py, goal_parser.py, recommendation_engine.py, context_intelligence.py.
- **File Structure** (Current MVP):

\`\`\`bash
converx/
├── __init__.py          # Package initialization
├── cli.py                # CLI entry point
├── orchestrator.py       # Core orchestration logic
├── formatter.py          # Output formatting
├── converx               # Entry point script
├── README.md             # Usage documentation
├── IMPLEMENTATION_COMPLETE.md # Completion report
├── DESIGN_SPEC.md        # Full design spec
├── OPUS_DESIGN.md        # Vision document
└── tests/
    ├── test_orchestrator.py  # Orchestrator tests
    └── test_formatter.py     # Formatter tests
\`\`\`

## Usage Guide
Run from repo root (`/Users/jesse.kemp/Dev`):

\`\`\`bash
# Basic next action
python -m converx.cli next

# Project-specific
python -m converx.cli next vortexv2

# With context predictions
python -m converx.cli next --with-context

# JSON output
python -m converx.cli next --json

# Current state summary
python -m converx.cli status
\`\`\`

## Architecture
Converx is an orchestrator:

- **CLI** (`cli.py`): Handles commands, args (e.g., project filter, --with-context).
- **Orchestrator** (`orchestrator.py`): Calls tools, builds state, filters recommendations.
- **Formatter** (`formatter.py`): Renders text or JSON output.
- **Data Flow**: Scan projects → Parse goals → Generate recommendations → Predict context → Format.

Full Vision Expansion: Phases add weather maps, scenarios, routes, virtual twin, etc.

## Testing
- 11 tests passing in `tests/`.
- Run: `python -m pytest converx/tests/`.

## Roadmap
Phased build to full vision (26-38 hours total):
- Phase 0 (Done): CLI + Basic Orchestrator.
- Phase 1 (2-3h): Weather Map + Scenarios.
- Phase 2 (4-6h): Routes + Multi-Domain.
- Phase 3 (6-8h): Integrations (GitHub, Google Fit, etc.).
- Phase 4 (4-6h): Playbooks + Executor.
- Phase 5 (8-12h): Virtual Twin + Learning.

(Full details from original docs omitted for brevity; reference source files.)
