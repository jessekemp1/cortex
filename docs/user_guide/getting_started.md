# Cortex Layers 3-4: Getting Started Guide

**Quick start guide for using the Cortex Intelligence Stack (Layers 3-4).**

Welcome to the Cortex Warning System and Smart Recommendations! This guide will help you get started with tracking project metrics, generating alerts, and receiving intelligent recommendations.

---

## Table of Contents

- [Quick Start (CLI)](#quick-start-cli)
- [Quick Start (Python API)](#quick-start-python-api)
- [Tracking Metrics](#tracking-metrics)
- [Viewing Alerts](#viewing-alerts)
- [Generating Recommendations](#generating-recommendations)
- [Configuration](#configuration)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Quick Start (CLI)

The fastest way to get started is using the CLI commands:

### Track Your Project Metrics

```bash
# Track coverage, violations, and commits for a project
cd /path/to/your/project
venv/bin/python cli.py track --project myproject
```

**Output:**
```
Tracking metrics for: myproject
✓ Tracking complete

Metrics updated:
  Test Coverage Estimate: 75.3%
  Violations: 12
  Commits (24h): 5
```

### View Metrics

```bash
# View tracked metrics for the last 7 days
venv/bin/python cli.py metrics myproject
```

**Output:**
```
Metrics for: myproject
Period: Last 7 days

COVERAGE
────────────────────────────────────────────────────────────
  Current: 75.30
  Updated: 2025-12-23 14:30:15
  Min: 72.10 | Max: 76.50 | Avg: 74.80
```

### Check Alerts

```bash
# Check for any alerts
venv/bin/python cli.py alerts --project myproject
```

**Output:**
```
Found 2 alert(s):

🔴 [CRITICAL] myproject: Test coverage dropped 5.2%
   Test coverage decreased from 76.5% to 71.3% over the last 7 days.
   Details: change: -5.2%
   Time: 2025-12-23 14:30

⚠️  [WARNING] myproject: Lint violations increased by 8
   Lint violations increased from 4 to 12 over the last 7 days.
   Time: 2025-12-23 14:30
```

---

## Quick Start (Python API)

### Track Metrics

```python
from intelligence.monitoring.metric_tracker import MetricTracker

# Initialize tracker
tracker = MetricTracker()

# Track coverage
tracker.track_coverage("myproject", 85.5, metadata={"test_files": 50})

# Track violations
tracker.track_violations("myproject", 12, linter="flake8")

# Track commits
tracker.track_commits("myproject", 15, timeframe="24h")
```

### Generate Alerts

```python
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
from intelligence.monitoring.alert_generator import AlertGenerator

# Initialize components
analyzer = TrendAnalyzer(tracker)
alert_gen = AlertGenerator(analyzer)

# Generate alerts
alerts = alert_gen.generate_alerts("myproject", days=7)

# Display alerts
for alert in alerts:
    print(alert.format_detailed())
```

### Use RecommendationEngine

```python
from recommendation_engine import RecommendationEngine

# Initialize engine (simplest API)
engine = RecommendationEngine()

# Get project health
health = engine.get_project_health("myproject")
print(f"Coverage: {health['coverage']['current']:.1f}%")
print(f"Total alerts: {health['alerts']['total']}")

# Get active alerts
alerts = engine.get_active_alerts("myproject")

# Generate recommendations
recs = engine.generate_recommendations(limit=5)
for rec in recs:
    print(f"- {rec.title}")
```

---

## Tracking Metrics

### Coverage Tracking

Track test coverage over time to identify degradation:

```python
from intelligence.monitoring.metric_tracker import MetricTracker

tracker = MetricTracker()

# Track coverage with metadata
tracker.track_coverage(
    project="myproject",
    coverage_pct=85.5,
    metadata={
        "test_files": 50,
        "total_files": 100,
        "framework": "pytest"
    }
)
```

### Violation Tracking

Track linting violations:

```python
# Track violations from flake8
tracker.track_violations(
    project="myproject",
    count=12,
    linter="flake8",
    metadata={"severity": "E501,E701"}
)

# Track violations from pylint
tracker.track_violations(
    project="myproject",
    count=5,
    linter="pylint",
    metadata={"severity": "C0301"}
)
```

### Commit Activity Tracking

Track commit frequency:

```python
# Track daily commits
tracker.track_commits(
    project="myproject",
    count=15,
    timeframe="24h",
    metadata={"branch": "main"}
)

# Track weekly commits
tracker.track_commits(
    project="myproject",
    count=45,
    timeframe="7d",
    metadata={"branch": "main"}
)
```

### Automated Tracking

Set up automated tracking in your CI/CD:

**Example: GitHub Actions**

```yaml
# .github/workflows/track-metrics.yml
name: Track Metrics

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * *'  # Daily

jobs:
  track:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Track metrics
        run: |
          python cli.py track --project ${{ github.repository }}
```

---

## Viewing Alerts

### CLI Alerts

```bash
# All alerts
venv/bin/python cli.py alerts --project myproject

# Only critical alerts
venv/bin/python cli.py alerts --project myproject --severity critical
```

### Python API Alerts

```python
from intelligence.monitoring.alert_generator import AlertGenerator, AlertSeverity

alert_gen = AlertGenerator(trend_analyzer)
alerts = alert_gen.generate_alerts("myproject", days=7)

# Filter by severity
critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]

# Get most critical
most_critical = alert_gen.get_most_critical_alert("myproject")
if most_critical:
    print(f"🔴 {most_critical.title}")
```

### Alert Formatting

```python
# Compact format (for context injection)
print(alert.format_compact())
# Output: 🔴 Coverage dropped 5%

# Detailed format (for CLI)
print(alert.format_detailed())
# Output:
# 🔴 [CRITICAL] myproject: Test coverage dropped 5.2%
#    Test coverage decreased from 76.5% to 71.3% over the last 7 days.
#    Details: change: -5.2%
#    Time: 2025-12-23 14:30
```

---

## Generating Recommendations

### Basic Recommendations

```python
from recommendation_engine import RecommendationEngine

engine = RecommendationEngine()

# Generate up to 10 recommendations
recs = engine.generate_recommendations(limit=10)

for rec in recs:
    print(f"\nTitle: {rec.title}")
    print(f"Priority: {rec.priority}")
    print(f"Type: {rec.type}")
```

### With Tasks and Goals

```python
from recommendation_engine import Task, Goal

# Define current tasks
tasks = [
    Task(id="1", title="Fix authentication bug", status="blocked", metadata=None),
    Task(id="2", title="Add tests", status="in_progress", metadata=None)
]

# Define goals
goals = [
    Goal(
        id="1",
        name="Reach 90% coverage",
        target_value=90.0,
        current_value=75.0,
        metric_type="coverage"
    )
]

# Generate recommendations
recs = engine.generate_recommendations(
    tasks=tasks,
    goals=goals,
    limit=10
)
```

### With Context

```python
# Add custom context
context = {
    "recent_changes": ["auth.py", "models.py"],
    "last_build": "failed",
    "branch": "feature/new-auth"
}

recs = engine.generate_recommendations(
    tasks=tasks,
    goals=goals,
    context=context,
    limit=5
)
```

---

## Configuration

### Database Location

By default, metrics are stored in `~/.cortex/metrics.db`. To use a custom location:

```python
from pathlib import Path
from intelligence.monitoring.metric_tracker import MetricTracker

tracker = MetricTracker(db_path=Path("/custom/path/metrics.db"))
```

### Retention Period

Adjust how long metrics are retained:

```python
# Keep metrics for 180 days
tracker = MetricTracker(retention_days=180)

# Clean up old metrics manually
deleted_count = tracker.cleanup_old_metrics(days=90)
print(f"Deleted {deleted_count} old metrics")
```

### Alert Thresholds

Customize alert thresholds:

```python
from intelligence.monitoring.alert_generator import AlertGenerator, AlertRules

# Modify thresholds
AlertRules.COVERAGE_CRITICAL_DROP = -10.0  # 10% drop is critical
AlertRules.COVERAGE_WARNING_DROP = -5.0     # 5% drop is warning

alert_gen = AlertGenerator(trend_analyzer)
```

---

## Common Workflows

### Workflow 1: Daily Health Check

```python
from recommendation_engine import RecommendationEngine

def daily_health_check(project):
    engine = RecommendationEngine()

    # Get health
    health = engine.get_project_health(project, days=7)

    # Check alerts
    if health['alerts']['critical'] > 0:
        print(f"⚠️  {health['alerts']['critical']} critical alerts!")

        # Get details
        alerts = engine.get_active_alerts(project)
        for alert in alerts:
            if alert.severity.value == "critical":
                print(f"  - {alert.title}")

    # Generate recommendations
    recs = engine.generate_recommendations(limit=3)
    if recs:
        print("\nTop recommendations:")
        for i, rec in enumerate(recs, 1):
            print(f"{i}. {rec.title}")

# Run daily
daily_health_check("myproject")
```

### Workflow 2: Pre-Commit Check

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Track current metrics
python cli.py track --project myproject

# Check for critical alerts
alerts=$(python cli.py alerts --project myproject --severity critical)

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

### Workflow 3: Weekly Report

```python
from datetime import datetime
from recommendation_engine import RecommendationEngine

def weekly_report(project):
    engine = RecommendationEngine()
    health = engine.get_project_health(project, days=7)

    report = f"""
    Weekly Report for {project}
    Generated: {datetime.now().strftime('%Y-%m-%d')}

    Coverage:
      Current: {health['coverage']['current']:.1f}%
      Trend: {health['coverage']['trend']}
      Change: {health['coverage']['delta']:+.1f}%

    Violations:
      Current: {health['violations']['current']}
      Trend: {health['violations']['trend']}
      Change: {health['violations']['delta']:+d}

    Activity:
      Commits: {health['activity']['commits']}
      Trend: {health['activity']['trend']}

    Alerts:
      Total: {health['alerts']['total']}
      Critical: {health['alerts']['critical']}
      Warning: {health['alerts']['warning']}
    """

    print(report)
    return report

# Email or slack the report
weekly_report("myproject")
```

---

## Troubleshooting

### Issue: "No metrics found"

**Solution:** Track some metrics first:

```python
tracker = MetricTracker()
tracker.track_coverage("myproject", 75.0)
```

### Issue: "Database locked"

**Solution:** Close existing tracker connections:

```python
tracker.close()
```

Or use the singleton:

```python
from intelligence.monitoring.metric_tracker import get_tracker
tracker = get_tracker()
```

### Issue: "No alerts generated"

**Possible reasons:**
1. Not enough metrics (need at least 2 data points)
2. Metrics are stable (no degradation)
3. Changes below alert thresholds

**Debug:**

```python
# Check metrics exist
metrics = tracker.get_metrics("myproject", MetricType.COVERAGE, days=7)
print(f"Found {len(metrics)} metrics")

# Check trend
trend = analyzer.analyze_coverage_trend("myproject", days=7)
print(f"Delta: {trend.delta}, Alert level: {trend.alert_level}")
```

### Issue: "ImportError: No module named 'intelligence'"

**Solution:** Ensure you're running from the correct directory:

```bash
cd /path/to/cortex
venv/bin/python your_script.py
```

Or add to path:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

---

## Next Steps

1. **Set up automated tracking** in your CI/CD pipeline
2. **Configure alert thresholds** for your project
3. **Review the [API Reference](../api/layers_3_4.md)** for advanced usage
4. **Check [integration tests](../../tests/test_layer3_4_integration.py)** for more examples

---

## Support

- **Documentation:** [API Reference](../api/layers_3_4.md)
- **Examples:** [Integration Tests](../../tests/test_layer3_4_integration.py)
- **Status:** [INTEGRATION_COMPLETE.md](../../INTEGRATION_COMPLETE.md)

---

**Happy tracking!** 🚀
