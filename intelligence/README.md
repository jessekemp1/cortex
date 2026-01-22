# Cortex Intelligence System

## Overview

The Cortex Intelligence System provides layered, progressive intelligence for development workflows. This is the foundation for making Cortex recommendations more specific, actionable, and context-aware.

## Architecture

```
Layer 1: Deep Project Analysis (✅ COMPLETE)
├── Tech stack detection (languages, frameworks, databases)
├── Test coverage estimation
├── Critical file identification
└── Quality tooling detection (linters, formatters)

Layer 2: Pattern Memory (✅ COMPLETE)
├── Index successful solutions from git history
├── Cross-project pattern recognition
└── "We solved this before in project X"

Layer 3: Warning System (✅ COMPLETE)
├── Monitor metrics and track trends
├── Alert on degradation
└── Proactive issue detection

Layer 3.5: Process Monitor (✅ COMPLETE)
├── OS process monitoring with psutil
├── AI tool & dev service tracking
├── Waste detection & capacity forecasting
└── Real-time resource intelligence

Layer 4: Smart Recommendations (✅ COMPLETE)
├── Use layers 1-3 for context
├── Generate specific, actionable recommendations
└── Replace generic "continue momentum"

Layer 5: Planning & Context Injection (✅ COMPLETE)
├── Context synthesis for Claude Code
├── Execution planning and tracking
└── Sub-500ms context delivery
```

## Layer 1: Deep Project Analysis

### What It Does

Analyzes project structure to provide contextual intelligence:

- **Tech Stack Detection**: Identifies languages (Python, JS/TS, Go, Rust), frameworks (FastAPI, React, Next.js), and databases (PostgreSQL, Redis, MongoDB)
- **Test Coverage**: Estimates coverage from test file counts or reads actual coverage reports
- **Quality Tools**: Detects linters and formatters
- **Warnings**: Flags low coverage, missing linters, or missing tests

### How It Works

The project profiler (`intelligence/analysis/project_profiler.py`) scans project files to build a comprehensive profile:

1. **Tech Stack**: Reads `requirements.txt`, `package.json`, `go.mod`, etc.
2. **Test Coverage**: Counts test files vs source files, or parses coverage reports
3. **Critical Files**: Identifies important files (main.py, config.py) and frequently changed files from git history
4. **Warnings**: Generates actionable warnings based on detected issues

### Usage

#### Quick Mode (for context injection)

```python
from intelligence.analysis.project_profiler import profile_project

# Quick mode: skips expensive operations (git log, file counting)
# Fast enough for per-prompt context injection
profile = profile_project(Path("/path/to/project"), quick=True)
```

**Quick mode output:**
```
Project: cortex (Python/FastAPI)
Branch: main
⚠️  No linter configured for Python
```

#### Full Mode (for deep analysis)

```python
# Full mode: includes critical files, test coverage counting
profile = profile_project(Path("/path/to/project"), quick=False)
```

**Full mode output:**
```
=== Project Profile: cortex ===

Tech Stack: Python/FastAPI
  Languages: Python
  Frameworks: FastAPI

Test coverage: ~34% (estimated)
  Test files: 41
  Source files: 72

Quality Tools:
  Linter: ✗
  Formatter: ✗

⚠️  Warnings:
  • Test coverage: 34% (target: 70%)
  • No linter configured for Python

Critical Files (10):
  • config.py - Configuration
  • orchestrator.py - Core orchestrator
  • bridge.py - API bridge
  ...
```

### Integration with inject_context.py

The enhanced `inject_context.py` hook now uses Layer 1 intelligence:

```python
def get_enhanced_context() -> str:
    """Get enhanced context with tech stack and warnings."""
    profile = profile_project(Path.cwd(), quick=True)

    # Returns: "Project: X (Python/FastAPI) | Branch: main | ⚠️  Warning"
    return profile.to_context_str()
```

This provides **context-aware intelligence** on every prompt without significant performance impact.

## Performance

### Quick Mode Benchmarks

- **cortex**: ~200ms
- **alpha_arena**: ~150ms
- **VortexV2**: ~300ms

Quick mode is fast enough for per-prompt context injection (< 500ms target).

### Full Mode Benchmarks

- **cortex**: ~2-3 seconds
- **VortexV2**: ~5-8 seconds (larger git history)

Full mode is suitable for on-demand analysis (slash commands, deep reports).

## Configuration

### Tech Stack Detection

The profiler detects tech stacks from standard project files:

- **Python**: `requirements.txt`, `pyproject.toml`, `.python-version`
- **JavaScript/TypeScript**: `package.json`
- **Go**: `go.mod`
- **Rust**: `Cargo.toml`

### Framework Detection

- **Python**: FastAPI, Flask, Django, Streamlit
- **JavaScript**: React, Vue, Next.js, Express, React Native

### Database Detection

- **Python**: Detects psycopg2 (PostgreSQL), pymongo (MongoDB), redis, mysql, sqlite
- **JavaScript**: Detects pg/postgres, mongodb, redis, mysql

### Quality Tools

- **Linters**: `.pylintrc`, `.flake8`, `pyproject.toml` (ruff/black), `.eslintrc`
- **Formatters**: `.prettierrc`, `pyproject.toml` (black)

## Warnings

The profiler generates warnings for:

1. **Low test coverage** (< 50%)
2. **No linter configured**
3. **No test files detected**

Warnings are prioritized and shown in context injection (most important first).

## Current Status

All 5 layers are now **COMPLETE** and operational:

### Layer 2: Pattern Memory ✅
- Indexes successful patterns from git commit messages
- Keyword-based similarity search
- Cross-project pattern reuse
- **Location**: `intelligence/memory/`

### Layer 3: Warning System ✅
- Monitors test coverage trends
- Tracks lint violation counts
- Alerts on metric degradation
- **Location**: `intelligence/monitoring/`

### Layer 3.5: Process Monitor ✅
- Real-time process monitoring with psutil
- Tracks CPU, memory, AI tools, dev services
- Detects resource waste and anomalies
- Provides capacity forecasting
- **Location**: `intelligence/process_monitor/`
- **CLI**: `cortex process status|waste|optimize|insights`

### Layer 4: Smart Recommendations ✅
- Uses all layers for context-aware recommendations
- Generates specific, actionable steps
- Alert-driven and goal-driven recommendations
- **Location**: `intelligence/recommendations/`

### Layer 5: Planning & Context Injection ✅
- Synthesizes intelligence for Claude Code
- Sub-500ms context delivery
- Execution planning and tracking
- **Location**: `intelligence/planning/`, `intelligence/context_injector.py`

## Files

```
cortex/intelligence/
├── README.md (this file)
├── __init__.py
└── analysis/
    ├── __init__.py
    └── project_profiler.py (Layer 1 implementation)
```

## Examples

### Example 1: Detect Missing Linter

```bash
cd ~/Dev/alpha_arena
python3 -m intelligence.analysis.project_profiler .
```

**Output:**
```
⚠️  Warnings:
  • No linter configured for Python
```

### Example 2: Tech Stack for Context

```bash
echo "test" | .claude/hooks/inject_context.py
```

**Output:**
```xml
<cortex_context>Project: alpha_arena (Python/Streamlit) | Branch: main | ⚠️  No linter configured for Python</cortex_context>
```

### Example 3: Full Project Analysis

```bash
cd ~/Dev/cortex
python3 intelligence/analysis/project_profiler.py .
```

**Output:**
```
=== Project Profile: cortex ===

Tech Stack: Python/FastAPI
  Languages: Python
  Frameworks: FastAPI

Test coverage: ~34% (estimated)
  Test files: 41
  Source files: 72

⚠️  Warnings:
  • Test coverage: 34% (target: 70%)
  • No linter configured for Python

Critical Files (10):
  • config.py - Configuration
  • orchestrator.py - Core orchestrator
```

## Testing

To test the profiler:

```bash
# Test on a specific project
python3 ~/Dev/cortex/intelligence/analysis/project_profiler.py /path/to/project

# Test quick mode (for context injection)
cd /path/to/project
echo "test" | python3 ~/Dev/.claude/hooks/inject_context.py
```
