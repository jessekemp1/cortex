# Cortex Layers 3-4 API Reference

**Version:** 1.0
**Last Updated:** 2025-12-23

Complete API reference for the Cortex Intelligence Stack Layers 3-4:
- Layer 3: Warning System (MetricTracker, TrendAnalyzer, AlertGenerator)
- Layer 4: Smart Recommendations (FileSelector, SmartGenerator, RecommendationEngine)

---

## Table of Contents

- [Layer 3: Warning System](#layer-3-warning-system)
  - [MetricTracker](#metrictracker)
  - [TrendAnalyzer](#trendanalyzer)
  - [AlertGenerator](#alertgenerator)
- [Layer 4: Smart Recommendations](#layer-4-smart-recommendations)
  - [FileSelector](#fileselector)
  - [SmartRecommendationGenerator](#smartrecommendationgenerator)
  - [RecommendationEngine](#recommendationengine-top-level-api)
  - [AlertAdapter](#alertadapter)
- [Integration Examples](#integration-examples)

---

## Layer 3: Warning System

### MetricTracker

**Purpose:** Persistent metric tracking with SQLite storage.

**Import:**
```python
from intelligence.monitoring.metric_tracker import MetricTracker, MetricType
```

**Initialization:**
```python
tracker = MetricTracker(db_path=None, retention_days=90)
```

**Parameters:**
- `db_path` (Path, optional): Path to SQLite database. Defaults to `~/.cortex/metrics.db`
- `retention_days` (int): Number of days to retain metrics. Defaults to 90.

#### Methods

##### `track_coverage(project, coverage_pct, metadata=None, timestamp=None) → Metric`

Track test coverage for a project.

**Parameters:**
- `project` (str): Project name
- `coverage_pct` (float): Coverage percentage (0-100)
- `metadata` (dict, optional): Additional metadata
- `timestamp` (datetime, optional): Metric timestamp. Defaults to now.

**Returns:** `Metric` object

**Example:**
```python
tracker = MetricTracker()
metric = tracker.track_coverage(
    "my_project",
    85.5,
    metadata={"test_files": 50, "total_files": 100}
)
```

##### `track_violations(project, count, linter=None, metadata=None, timestamp=None) → Metric`

Track linter violations.

**Parameters:**
- `project` (str): Project name
- `count` (int): Number of violations (>= 0)
- `linter` (str, optional): Linter name (e.g., "flake8", "pylint")
- `metadata` (dict, optional): Additional metadata
- `timestamp` (datetime, optional): Metric timestamp

**Returns:** `Metric` object

**Example:**
```python
metric = tracker.track_violations(
    "my_project",
    12,
    linter="flake8",
    metadata={"severity": "warning"}
)
```

##### `track_commits(project, count, timeframe="24h", metadata=None, timestamp=None) → Metric`

Track commit activity.

**Parameters:**
- `project` (str): Project name
- `count` (int): Number of commits
- `timeframe` (str): Time period (e.g., "24h", "7d")
- `metadata` (dict, optional): Additional metadata
- `timestamp` (datetime, optional): Metric timestamp

**Returns:** `Metric` object

**Example:**
```python
metric = tracker.track_commits(
    "my_project",
    15,
    timeframe="24h",
    metadata={"branch": "main"}
)
```

##### `get_metrics(project, metric_type, days=7) → List[Metric]`

Retrieve metrics for a project.

**Parameters:**
- `project` (str): Project name
- `metric_type` (MetricType): Type of metric
- `days` (int): Number of days to retrieve

**Returns:** List of `Metric` objects, ordered by timestamp

**Example:**
```python
metrics = tracker.get_metrics(
    "my_project",
    MetricType.COVERAGE,
    days=30
)

for metric in metrics:
    print(f"{metric.timestamp}: {metric.metric_value}%")
```

##### `get_project_health(project, days=7) → Dict`

Get comprehensive health summary.

**Parameters:**
- `project` (str): Project name
- `days` (int): Number of days to analyze

**Returns:** Dict with health metrics and trends

**Example:**
```python
health = tracker.get_project_health("my_project", days=7)
print(f"Coverage: {health['coverage']['current']:.1f}%")
print(f"Alerts: {health['alerts']['total']}")
```

---

### TrendAnalyzer

**Purpose:** Analyze metric trends and detect anomalies.

**Import:**
```python
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
```

**Initialization:**
```python
analyzer = TrendAnalyzer(metric_tracker)
```

**Parameters:**
- `metric_tracker` (MetricTracker): MetricTracker instance

#### Methods

##### `analyze_coverage_trend(project, days=7) → Trend`

Analyze coverage trend using linear regression.

**Parameters:**
- `project` (str): Project name
- `days` (int): Number of days to analyze

**Returns:** `Trend` object with:
- `direction` (TrendDirection): IMPROVING, STABLE, or DEGRADING
- `delta` (float): Change in value
- `rate` (float): Change rate per day
- `alert_level` (AlertLevel): NONE, WARNING, or CRITICAL
- `start_value`, `end_value` (float): Trend values
- `confidence` (float): R² score (0-1)

**Example:**
```python
trend = analyzer.analyze_coverage_trend("my_project", days=7)

if trend.direction == TrendDirection.DEGRADING:
    print(f"Coverage dropped {abs(trend.delta):.1f}% over {days} days")
    print(f"Alert level: {trend.alert_level.value}")
```

##### `analyze_violation_trend(project, days=7) → Trend`

Analyze violation trend.

**Parameters:**
- `project` (str): Project name
- `days` (int): Number of days to analyze

**Returns:** `Trend` object

**Example:**
```python
trend = analyzer.analyze_violation_trend("my_project", days=7)

if trend.delta > 10:
    print(f"Violations increased by {int(trend.delta)}")
```

##### `detect_anomalies(project, metric_type, days=7) → List[Anomaly]`

Detect statistical anomalies in metrics.

**Parameters:**
- `project` (str): Project name
- `metric_type` (MetricType): Type of metric
- `days` (int): Number of days to analyze

**Returns:** List of `Anomaly` objects

**Example:**
```python
anomalies = analyzer.detect_anomalies(
    "my_project",
    MetricType.COVERAGE,
    days=30
)

for anomaly in anomalies:
    print(f"Anomaly at {anomaly.timestamp}: {anomaly.actual_value} (expected {anomaly.expected_value})")
```

---

### AlertGenerator

**Purpose:** Generate alerts based on trend analysis.

**Import:**
```python
from intelligence.monitoring.alert_generator import AlertGenerator, AlertSeverity
```

**Initialization:**
```python
alert_gen = AlertGenerator(trend_analyzer)
```

**Parameters:**
- `trend_analyzer` (TrendAnalyzer): TrendAnalyzer instance

#### Methods

##### `generate_alerts(project, days=7) → List[Alert]`

Generate all alerts for a project.

**Parameters:**
- `project` (str): Project name
- `days` (int): Number of days to analyze

**Returns:** List of `Alert` objects, sorted by severity (CRITICAL first)

**Example:**
```python
alerts = alert_gen.generate_alerts("my_project", days=7)

for alert in alerts:
    print(alert.format_detailed())
```

##### `get_most_critical_alert(project, days=7) → Alert | None`

Get single most critical alert.

**Parameters:**
- `project` (str): Project name
- `days` (int): Number of days to analyze

**Returns:** Most critical `Alert` or `None`

**Example:**
```python
alert = alert_gen.get_most_critical_alert("my_project")

if alert:
    print(f"🔴 {alert.title}")
```

##### `format_alerts_for_cli(alerts) → str`

Format alerts for CLI display.

**Parameters:**
- `alerts` (List[Alert]): List of alerts

**Returns:** Formatted string

**Example:**
```python
alerts = alert_gen.generate_alerts("my_project")
print(alert_gen.format_alerts_for_cli(alerts))
```

---

## Layer 4: Smart Recommendations

### FileSelector

**Purpose:** Intelligent file selection for recommendations.

**Import:**
```python
from intelligence.recommendations.file_selector import FileSelector
```

**Initialization:**
```python
selector = FileSelector(project_path, context=None)
```

**Parameters:**
- `project_path` (Path): Path to project directory
- `context` (dict, optional): Additional context

#### Methods

##### `select_for_coverage_improvement(limit=5) → List[FileInfo]`

Select files for coverage improvement.

**Parameters:**
- `limit` (int): Maximum number of files

**Returns:** List of `FileInfo` objects with priority ranking

**Example:**
```python
files = selector.select_for_coverage_improvement(limit=5)

for file_info in files:
    print(f"Priority {file_info.priority}: {file_info.path}")
    print(f"Reason: {file_info.reason}")
```

##### `select_for_recommendation_type(rec_type, context=None, limit=5) → List[FileInfo]`

Select files based on recommendation type.

**Parameters:**
- `rec_type` (str): Type ("coverage", "goal", "health")
- `context` (dict, optional): Additional context
- `limit` (int): Maximum number of files

**Returns:** List of `FileInfo` objects

**Example:**
```python
files = selector.select_for_recommendation_type(
    rec_type="coverage",
    context={"goal": "Improve test coverage"},
    limit=3
)
```

---

### SmartRecommendationGenerator

**Purpose:** Generate context-aware recommendations.

**Import:**
```python
from intelligence.recommendations.smart_generator import SmartRecommendationGenerator
```

**Initialization:**
```python
generator = SmartRecommendationGenerator(file_selector=None)
```

**Parameters:**
- `file_selector` (FileSelector, optional): FileSelector instance

#### Methods

##### `generate_alert_recommendations(alerts) → List[Recommendation]`

Generate recommendations from alerts.

**Parameters:**
- `alerts` (List[AdaptedAlert]): List of adapted alerts

**Returns:** List of `Recommendation` objects

**Example:**
```python
from intelligence.recommendations.alert_adapter import adapt_alerts

# Adapt Layer 3 alerts to Layer 4 format
adapted = adapt_alerts(layer3_alerts)

# Generate recommendations
recs = generator.generate_alert_recommendations(adapted)
```

---

### RecommendationEngine (Top-Level API)

**Purpose:** Top-level API integrating all 4 layers.

**Import:**
```python
from recommendation_engine import RecommendationEngine
```

**Initialization:**
```python
engine = RecommendationEngine(project_path=None, enable_learning=True, enable_patterns=True)
```

**Parameters:**
- `project_path` (Path, optional): Project path. Defaults to current directory.
- `enable_learning` (bool): Enable Layer 3 learning system
- `enable_patterns` (bool): Enable Layer 2 pattern memory

#### Methods

##### `generate_recommendations(tasks=None, goals=None, context=None, limit=10) → List[Recommendation]`

Generate prioritized recommendations.

**Parameters:**
- `tasks` (List[Task], optional): Current tasks
- `goals` (List[Goal], optional): Active goals
- `context` (dict, optional): Additional context
- `limit` (int): Maximum recommendations

**Returns:** List of `Recommendation` objects, sorted by priority

**Example:**
```python
from recommendation_engine import RecommendationEngine, Task, Goal

engine = RecommendationEngine()

tasks = [Task(id="1", title="Fix bug", status="blocked", metadata=None)]
goals = [Goal(id="1", name="80% coverage", target_value=80, current_value=65, metric_type="coverage")]

recs = engine.generate_recommendations(tasks=tasks, goals=goals, limit=10)

for rec in recs:
    print(f"{rec.title} - Priority: {rec.priority}")
```

##### `get_active_alerts(project=None, days=7) → List[Alert]`

Get active alerts for a project.

**Parameters:**
- `project` (str, optional): Project name. Defaults to current directory name.
- `days` (int): Number of days to analyze

**Returns:** List of `Alert` objects

**Example:**
```python
alerts = engine.get_active_alerts("my_project", days=7)

for alert in alerts:
    print(f"{alert.severity.value}: {alert.title}")
```

##### `get_project_health(project=None, days=7) → Dict`

Get comprehensive project health.

**Parameters:**
- `project` (str, optional): Project name
- `days` (int): Number of days to analyze

**Returns:** Dict with health metrics

**Example:**
```python
health = engine.get_project_health("my_project")

print(f"Coverage: {health['coverage']['current']:.1f}%")
print(f"Trend: {health['coverage']['trend']}")
print(f"Alerts: {health['alerts']['total']}")
```

---

### AlertAdapter

**Purpose:** Bridge Layer 3 alerts to Layer 4 format.

**Import:**
```python
from intelligence.recommendations.alert_adapter import adapt_alerts, AdaptedAlert
```

#### Functions

##### `adapt_alerts(layer3_alerts) → List[AdaptedAlert]`

Convert Layer 3 alerts to Layer 4 format.

**Parameters:**
- `layer3_alerts` (List[Alert]): Layer 3 alerts

**Returns:** List of `AdaptedAlert` objects

**Example:**
```python
from intelligence.monitoring.alert_generator import AlertGenerator

# Generate Layer 3 alerts
alert_gen = AlertGenerator(trend_analyzer)
layer3_alerts = alert_gen.generate_alerts("my_project")

# Adapt to Layer 4 format
adapted = adapt_alerts(layer3_alerts)

# Use in Layer 4
recs = smart_generator.generate_alert_recommendations(adapted)
```

---

## Integration Examples

### Example 1: Complete Metric → Alert → Recommendation Flow

```python
from pathlib import Path
from intelligence.monitoring.metric_tracker import MetricTracker, MetricType
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
from intelligence.monitoring.alert_generator import AlertGenerator
from intelligence.recommendations.alert_adapter import adapt_alerts
from intelligence.recommendations.smart_generator import SmartRecommendationGenerator
from intelligence.recommendations.file_selector import FileSelector

# Layer 3: Track metrics
tracker = MetricTracker()
tracker.track_coverage("my_project", 80.0)
tracker.track_coverage("my_project", 75.0)
tracker.track_coverage("my_project", 70.0)

# Analyze trends
analyzer = TrendAnalyzer(tracker)
trend = analyzer.analyze_coverage_trend("my_project", days=7)

# Generate alerts
alert_gen = AlertGenerator(analyzer)
alerts = alert_gen.generate_alerts("my_project", days=7)

# Layer 4: Adapt alerts and generate recommendations
adapted_alerts = adapt_alerts(alerts)

selector = FileSelector(Path.cwd())
generator = SmartRecommendationGenerator(file_selector=selector)

recommendations = generator.generate_alert_recommendations(adapted_alerts)

for rec in recommendations:
    print(f"Recommendation: {rec.title}")
```

### Example 2: Using RecommendationEngine (Simplified API)

```python
from recommendation_engine import RecommendationEngine

# Initialize engine (auto-initializes all layers)
engine = RecommendationEngine()

# Get project health
health = engine.get_project_health("my_project", days=7)
print(f"Coverage: {health['coverage']['current']:.1f}%")
print(f"Alerts: {health['alerts']['total']}")

# Generate recommendations
recs = engine.generate_recommendations(limit=5)

for rec in recs:
    print(f"- {rec.title}")
```

### Example 3: CLI Integration

```python
# Track metrics
from intelligence.monitoring.metric_tracker import get_tracker

tracker = get_tracker()
tracker.track_coverage("my_project", 85.5)

# View alerts
from recommendation_engine import RecommendationEngine

engine = RecommendationEngine()
alerts = engine.get_active_alerts("my_project")

for alert in alerts:
    print(alert.format_detailed())
```

---

## Data Models

### Metric

```python
@dataclass
class Metric:
    id: int | None
    project: str
    metric_type: MetricType
    metric_value: float
    timestamp: datetime
    metadata: dict
```

### Trend

```python
@dataclass
class Trend:
    direction: TrendDirection  # IMPROVING, STABLE, DEGRADING
    delta: float
    rate: float
    alert_level: AlertLevel  # NONE, WARNING, CRITICAL
    start_value: float
    end_value: float
    start_timestamp: datetime
    end_timestamp: datetime
    data_points: int
    confidence: float  # R² score
    message: str
```

### Alert

```python
@dataclass
class Alert:
    alert_type: AlertType  # DEGRADATION, ACTIVITY, CRITICAL_FILE
    severity: AlertSeverity  # CRITICAL, WARNING, INFO
    title: str
    message: str
    metric_type: str
    metadata: dict
    created_at: datetime
    project: str
```

---

## Performance

All operations are optimized for sub-second performance:

- Metric tracking: < 10ms per operation
- Trend analysis: < 50ms for 30 days of data
- Alert generation: < 100ms per project
- Context injection: < 500ms (with caching)

---

## Best Practices

1. **Metric Tracking:** Track metrics consistently (daily or on each build)
2. **Retention:** Adjust `retention_days` based on your analysis needs
3. **Alert Thresholds:** Configure `AlertRules` for your project
4. **Caching:** Use singleton pattern (`get_tracker()`) for metric tracker
5. **Performance:** Use batch operations when tracking multiple metrics

---

## See Also

- [User Guide](/docs/user_guide/getting_started.md)
- [Integration Tests](/tests/test_layer3_4_integration.py)
- [INTEGRATION_COMPLETE.md](/INTEGRATION_COMPLETE.md)
