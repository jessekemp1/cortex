# Getting Started with Cortex

**Quick start guide for using Cortex Intelligence System**

Welcome to Cortex! This guide will help you get started with using Cortex as your digital brain and development hub.

---

## What is Cortex?

Cortex is a **meta-intelligence system** that creates compound learning across your entire project portfolio. It combines:

- **Portfolio Memory**: Cross-project patterns, lessons, and metadata
- **Session Intelligence**: Automatic git-based context generation
- **Spec Knowledge Base**: Semantic search across documentation
- **Metrics Tracking**: ROI measurement and performance analytics
- **Bridge API**: Unified access to all intelligence sources

**Status**: ✅ Enterprise-Grade (100% - 15/15 tests passing)

---

## Quick Start

### Step 1: Installation

```bash
# Navigate to cortex
cd /path/to/cortex

# Install (if not already installed)
pip install -e .

# Verify
cortex --help
```

See [Installation Guide](../INSTALLATION.md) for detailed setup.

### Step 2: First Commands

```bash
# Get your current session context
cortex status

# Get next recommended action
cortex next

# Check system health
cortex health
```

### Step 3: Basic Configuration

```bash
# Create config file (if needed)
python -c "from config import create_default_config; create_default_config()"

# Edit config
vim ~/.cortex/config.yaml
```

---

## Core Commands

### Session Context

```bash
# Get current session context
cortex status

# Get structured context (JSON)
python bridge.py session-context --format=structured
```

**What it shows**:
- Current project
- Git branch and recent commits
- Active goals
- Current focus

---

### Portfolio Intelligence

```bash
# Get portfolio statistics
python bridge.py portfolio stats

# Find cross-project patterns
python bridge.py portfolio patterns

# Get lessons learned
python bridge.py portfolio lessons

# Get project context
python bridge.py portfolio project VortexV2
```

**What it shows**:
- Total projects and activity
- Tech stack distribution
- Cross-project patterns
- Lessons learned

---

### Spec Search

```bash
# Search for similar work
python bridge.py intelligence similar-work "API rate limiting" --project cortex

# Index a spec file
python bridge.py index-spec /path/to/spec.md --project ProjectName
```

**What it shows**:
- Similar specifications across projects
- Relevance scores
- Key patterns and lessons

---

### Dependency Analysis

```bash
# Analyze project dependencies
python bridge.py deps cortex

# Check dependency health
python bridge.py deps-health cortex

# Find circular dependencies
python bridge.py deps-circular cortex

# Export dependency graph
python bridge.py deps-graph cortex mermaid
```

**What it shows**:
- Project dependencies
- Health scores
- Circular dependencies
- Visual dependency graphs

---

## Python API Usage

### Basic Usage

```python
from bridge import CortexBridge

# Initialize bridge
bridge = CortexBridge()

# Get session context
context = bridge.get_session_context()
print(f"Working on: {context['project']['name']}")

# Get portfolio stats
stats = bridge.get_portfolio_stats()
print(f"Total projects: {stats['total_projects']}")

# Search specs
results = bridge.search_specs("API rate limiting", project="cortex")
for result in results:
    print(f"Found: {result['spec_name']} (similarity: {result['similarity']})")
```

---

## Daily Workflow

### Morning Routine

```bash
# 1. Get session context
cortex status

# 2. Get portfolio overview
python bridge.py portfolio stats

# 3. Get daily briefing (if configured)
cortex briefing
```

### Before Coding

```bash
# Search for similar work
python bridge.py intelligence similar-work "your task" --project yourproject

# Check for applicable patterns
python bridge.py portfolio patterns
```

### After Task

```python
# Track metrics
from metrics_tracker import MetricsTracker

tracker = MetricsTracker()
tracker.record_velocity(
    task="Implemented feature X",
    time_without_cortex=60,  # Baseline estimate
    time_with_cortex=20,     # Actual time
    project="yourproject",
    notes="Used spec search to find existing pattern"
)
```

---

## Next Steps

1. **Read [Core Concepts](core_concepts.md)** - Understand Cortex components
2. **Try [Examples](examples.md)** - Real-world usage examples
3. **Learn [Advanced Usage](advanced_usage.md)** - Advanced features
4. **Follow [Best Practices](best_practices.md)** - Optimize your workflow

---

## Common Questions

### "How do I index my project specs?"

```bash
# Index a single spec
python bridge.py index-spec docs/ARCHITECTURE.md --project cortex

# Index all specs in a project (programmatic)
python3 -c "
from intelligence.spec_knowledge_base import SpecKnowledgeBase
kb = SpecKnowledgeBase()
count = kb.index_project('/path/to/project', 'ProjectName')
print(f'Indexed {count} specs')
"
```

### "How do I track my work?"

```python
from metrics_tracker import MetricsTracker

tracker = MetricsTracker()

# Track velocity
tracker.record_velocity(task="...", time_without_cortex=60, time_with_cortex=20, project="...")

# Track mistake prevention
tracker.record_mistake(mistake_type="...", was_prevented=True, project="...")

# Get dashboard
dashboard = tracker.get_dashboard(days=30)
print(dashboard)
```

### "How do I find similar work?"

```bash
# Via CLI
python bridge.py intelligence similar-work "your query" --project yourproject

# Via Python
from bridge import CortexBridge
bridge = CortexBridge()
results = bridge.search_specs("your query", project="yourproject")
```

---

## Troubleshooting

### "No projects found"

**Solution**: Ensure projects are in workspace and have `.git` directories or `.claude/project.yaml` files

### "Spec search returns no results"

**Solution**: Index specs first using `python bridge.py index-spec <file> --project <name>`

### "Portfolio memory not available"

**Solution**: Initialize portfolio memory: `python3 -c "from portfolio_memory import PortfolioMemory; PortfolioMemory()"`

See [Troubleshooting Guide](../TROUBLESHOOTING.md) for more solutions.

---

## Resources

- [Core Concepts](core_concepts.md) - Understanding Cortex
- [Examples](examples.md) - Usage examples
- [Advanced Usage](advanced_usage.md) - Advanced features
- [Best Practices](best_practices.md) - Optimization tips
- [API Documentation](../API.md) - Complete API reference
- [Architecture](../ARCHITECTURE.md) - System architecture

---

**Version**: 1.0  
**Last Updated**: 2025-12-24
