# Advanced Usage

**Advanced features and customization options**

This guide covers advanced features and customization options for Cortex.

---

## Table of Contents

1. [Custom Integrations](#custom-integrations)
2. [Performance Optimization](#performance-optimization)
3. [Custom Analyzers](#custom-analyzers)
4. [Workflow Automation](#workflow-automation)
5. [Configuration Tuning](#configuration-tuning)

---

## Custom Integrations

### MCP Server Integration

**Purpose**: Enable AI agents to access Cortex via Model Context Protocol

**Configuration**: `~/.cursor/mcp.json`
```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["/path/to/cortex/mcp_server.py"]
    }
  }
}
```

**Usage**:
```python
# AI agents can now access Cortex resources
# Resource: cortex://context?query=...
# Tools: inject_recommendation, trigger_action
```

---

### Session Hooks

**Purpose**: Automatic context injection on session start

**Setup**:
```bash
# Create hooks directory
mkdir -p ~/.claude/hooks

# Create session start hook
cat > ~/.claude/hooks/SessionStart.compact.sh <<'EOF'
#!/bin/bash
cd ~/Dev/cortex
python3 bridge.py session-context 2>/dev/null
EOF

# Make executable
chmod +x ~/.claude/hooks/SessionStart.compact.sh
```

**Result**: Automatic context injection on every Claude Code session

---

### Custom Automation Scripts

**Example: Daily Metrics Report**:
```python
#!/usr/bin/env python3
"""Generate daily metrics report"""

from cortex.bridge import CortexBridge
from metrics_tracker import MetricsTracker
from datetime import datetime

def daily_report():
    bridge = CortexBridge()
    tracker = MetricsTracker()

    # Get metrics
    dashboard = tracker.get_dashboard(days=1)

    # Generate report
    report = f"""
Daily Metrics Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Velocity:
  Improvement: {dashboard.get('velocity', {}).get('improvement_pct', 0):.1f}%
  Time Saved: {dashboard.get('velocity', {}).get('total_saved_minutes', 0):.0f} minutes

Mistake Prevention:
  Prevention Rate: {dashboard.get('mistakes', {}).get('prevention_rate', 0):.1f}%
  Mistakes Prevented: {dashboard.get('mistakes', {}).get('prevented_count', 0)}

ROI:
  Ratio: {dashboard.get('roi', {}).get('ratio', 0):.2f}x
  Net Benefit: {dashboard.get('roi', {}).get('net_minutes', 0):.0f} minutes
"""

    print(report)

    # Optionally email or save to file
    # with open('daily_report.txt', 'w') as f:
    #     f.write(report)

if __name__ == "__main__":
    daily_report()
```

---

## Performance Optimization

### Caching Strategies

**Session Context Caching**:
```python
from intelligence.session_manager import SessionManager

# Session context cached for 1 hour by default
sm = SessionManager()
context = sm.load_session_context(max_age_hours=1)  # Use cached if <1 hour old
```

**Portfolio Stats Caching**:
```python
from portfolio_memory import PortfolioMemory

# Stats are cached in memory
pm = PortfolioMemory()
stats = pm.get_stats()  # Fast, cached
```

### Lazy Initialization

**Components initialize only when needed**:
```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()  # Fast initialization, components loaded lazily

# Components initialized on first use
if bridge.spec_kb:  # Only initialized if needed
    results = bridge.search_specs("query")
```

---

## Custom Analyzers

### Creating Custom Analyzers

**Example: Custom Dependency Analyzer**:
```python
from cortex.agents.data_agent.analyzers.dependency_mapper import DependencyMapper

class CustomDependencyAnalyzer(DependencyMapper):
    def analyze_custom_metric(self, project_path):
        """Custom analysis logic"""
        # Your custom analysis
        return {"custom_metric": "value"}

# Use custom analyzer
analyzer = CustomDependencyAnalyzer(project_path)
custom_result = analyzer.analyze_custom_metric(project_path)
```

---

## Workflow Automation

### Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Track current metrics
python bridge.py track --project $(basename $(pwd))

# Check for critical alerts
alerts=$(python bridge.py alerts --project $(basename $(pwd)) --severity critical)

if [ -n "$alerts" ]; then
    echo "⚠️  Critical alerts detected!"
    echo "$alerts"
    echo ""
    echo "Continue with commit? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

### Scheduled Tasks

**Using cron**:
```bash
# Daily metrics tracking
0 0 * * * cd /path/to/cortex && python bridge.py track --project all

# Weekly portfolio analysis
0 0 * * 0 cd /path/to/cortex && python portfolio_analyzer.py
```

---

## Configuration Tuning

### Performance Tuning

**Adjust cache TTL**:
```yaml
# ~/.cortex/config.yaml
cache_ttl_seconds: 3600  # 1 hour (default)
max_cache_size_mb: 100   # Maximum cache size
```

### Feature Toggles

**Disable optional features**:
```yaml
# ~/.cortex/config.yaml
learning_enabled: false      # Disable learning system
spec_kb_enabled: false       # Disable spec knowledge base
session_intelligence: true   # Enable session intelligence
```

---

## Advanced API Usage

### Batch Operations

**Process multiple projects**:
```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

projects = ["cortex", "VortexV2", "AlphaArena"]

# Analyze all projects
for project in projects:
    health = bridge.get_dependency_health(project)
    print(f"{project}: {health['total_score']}/100")
```

### Error Recovery

**Robust error handling**:
```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

def safe_get_stats():
    """Get stats with error recovery"""
    try:
        stats = bridge.get_portfolio_stats()
        if "error" in stats:
            # Fallback to cached stats
            return get_cached_stats()
        return stats
    except Exception as e:
        # Log error and return default
        print(f"Error: {e}")
        return {"total_projects": 0, "error": str(e)}
```

---

## Next Steps

- [Best Practices](best_practices.md) - Optimization tips
- [API Documentation](../API.md) - Complete API reference
- [Developer Guide](../developer/setup.md) - Development setup

---

**Version**: 1.0  
**Last Updated**: 2025-12-24
