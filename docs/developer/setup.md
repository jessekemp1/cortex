# Developer Setup Guide

**Development environment setup for Cortex contributors**

This guide helps developers set up their environment to contribute to Cortex.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Environment Setup](#development-environment-setup)
3. [Code Structure](#code-structure)
4. [Running Tests](#running-tests)
5. [Code Style Guidelines](#code-style-guidelines)
6. [Git Workflow](#git-workflow)

---

## Prerequisites

### Required

- **Python**: 3.9+ (3.11+ recommended)
- **Git**: 2.0+
- **pip**: Latest version

### Recommended

- **IDE**: VS Code, PyCharm, or Cursor
- **Python Tools**: `ruff` (linting/formatting), `pytest` (testing)

---

## Development Environment Setup

### Step 1: Clone Repository

```bash
# Navigate to workspace
cd /Users/jesse.kemp/Dev

# Clone or navigate to cortex
cd cortex
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### Step 3: Install Dependencies

```bash
# Install development dependencies
pip install -r requirements.txt

# Install cortex in development mode
pip install -e .

# Install development tools
pip install pytest pytest-cov ruff mypy
```

### Step 4: Verify Setup

```bash
# Run tests
pytest tests/ -v

# Run enterprise-grade tests
python test_enterprise_grade.py

# Check code style
ruff check .
```

---

## Code Structure

### Directory Structure

```
cortex/
├── __init__.py              # Package initialization
├── bridge.py                # CortexBridge class (intelligence backing)
├── mcp_server.py            # MCP server — primary interface, in-process
├── cli/                     # CLI package (commands/ + dispatcher)
├── portfolio_memory.py      # Portfolio memory
├── metrics_tracker.py       # Metrics tracking
├── orchestrator.py          # Core orchestration
├── intelligence/            # Intelligence modules
│   ├── session_manager.py  # Session intelligence
│   ├── spec_knowledge_base.py # Spec knowledge base
│   └── unified_intelligence.py # Unified intelligence
├── agents/                  # Agent modules
│   └── data_agent/          # Data agent
│       ├── analyzers/      # Analyzers (dependency, health, etc.)
│       └── cli.py          # Data agent CLI
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md     # Architecture docs
│   ├── API.md              # API reference
│   └── user_guide/         # User guides
├── tests/                   # Test files
│   └── test_*.py           # Test modules
└── test_enterprise_grade.py # Enterprise-grade tests
```

### Key Modules

**Bridge API** (`bridge.py`):
- Unified interface to all Cortex modules
- Error handling and validation
- Multiple output formats

**Portfolio Memory** (`portfolio_memory.py`):
- Cross-project patterns and lessons
- Project metadata
- Health tracking

**Session Manager** (`intelligence/session_manager.py`):
- Git-based context generation
- Goal inference
- Focus detection

**Spec Knowledge Base** (`intelligence/spec_knowledge_base.py`):
- Semantic search
- Spec indexing
- Embedding-based similarity

---

## Running Tests

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_portfolio_memory.py -v

# Run with coverage
pytest tests/ --cov=cortex --cov-report=html
```

### Enterprise-Grade Tests

```bash
# Run enterprise-grade assessment
python test_enterprise_grade.py

# Expected: 15/15 tests pass (100%)
```

### E2E Tests

```bash
# Run E2E validation
python e2e_validation.py

# Expected: 9/9 tests pass
```

---

## Code Style Guidelines

### Python Style

**Follow PEP 8** with these guidelines:

- **Line Length**: 100 characters (soft limit)
- **Indentation**: 4 spaces
- **Imports**: Grouped (stdlib, third-party, local)
- **Docstrings**: Google style

**Example**:
```python
"""Module docstring."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from cortex.portfolio_memory import PortfolioMemory


def get_portfolio_stats(include_health: bool = True) -> Dict[str, Any]:
    """
    Get portfolio statistics.

    Args:
        include_health: Include health summary (default: True)

    Returns:
        Dict with stats about projects, patterns, lessons, and health
    """
    # Implementation
    pass
```

### Linting and Formatting

**Use Ruff** (faster than black+flake8):

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .
```

### Type Hints

**Use type hints** for all function signatures:

```python
from typing import Dict, List, Optional, Any

def get_stats(include_health: bool = True) -> Dict[str, Any]:
    """Get statistics."""
    pass
```

---

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Refactoring

### Commit Messages

**Follow conventional commits**:

```
feat(bridge): add search_specs method
fix(portfolio): fix project health calculation
docs(api): update API documentation
refactor(session): simplify context generation
```

### Pull Request Process

1. **Create branch**: `git checkout -b feature/new-feature`
2. **Make changes**: Implement feature
3. **Run tests**: `pytest tests/ && python test_enterprise_grade.py`
4. **Check style**: `ruff check .`
5. **Commit**: `git commit -m "feat(module): description"`
6. **Push**: `git push origin feature/new-feature`
7. **Create PR**: With description and test results

---

## Development Tools

### Recommended VS Code Extensions

- **Python**: Python language support
- **Ruff**: Linting and formatting
- **Pytest**: Test discovery and running
- **GitLens**: Git integration

### Recommended Cursor Extensions

- **Python**: Python language support
- **Ruff**: Linting and formatting
- **Error Lens**: Inline error display

---

## Debugging

### Debug Mode

```bash
# Enable debug logging
export CORTEX_DEBUG=1

# Run with verbose output
cortex status --verbose
```

### Python Debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use breakpoint() (Python 3.7+)
breakpoint()
```

---

## Next Steps

- [Architecture Deep Dive](architecture_deep_dive.md) - Internal design
- [Extension Points](extension_points.md) - Extending Cortex
- [Testing Guide](../testing_guide.md) - Writing tests
- [Contributing Guide](../CONTRIBUTING.md) - Contribution guidelines

---

**Version**: 1.0  
**Last Updated**: 2025-12-24
