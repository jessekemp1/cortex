"""
Shared pytest fixtures for Cortex Layers 3-4 integration tests.

Provides test fixtures for:
- Temporary databases
- Layer 3 components (MetricTracker, TrendAnalyzer, AlertGenerator)
- Layer 4 components (FileSelector, SmartGenerator, RecommendationEngine)
- Sample test data
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.monitoring.alert_generator import (
    Alert,
    AlertGenerator,
    AlertSeverity,
    AlertType,
)
from intelligence.monitoring.metric_tracker import MetricTracker, MetricType
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
from intelligence.recommendations.file_selector import FileSelector
from intelligence.recommendations.smart_generator import SmartRecommendationGenerator
from recommendations import RecommendationEngine

# Database Fixtures


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# Layer 3 Fixtures


@pytest.fixture
def metric_tracker(temp_db):
    """Create a MetricTracker with temporary database."""
    tracker = MetricTracker(db_path=temp_db)
    yield tracker
    tracker.close()


@pytest.fixture
def trend_analyzer(metric_tracker):
    """Create a TrendAnalyzer with tracker."""
    return TrendAnalyzer(metric_tracker)


@pytest.fixture
def alert_generator(trend_analyzer):
    """Create an AlertGenerator with analyzer."""
    return AlertGenerator(trend_analyzer)


# Layer 4 Fixtures


@pytest.fixture
def file_selector(temp_project_dir):
    """Create a FileSelector with temp project directory."""
    return FileSelector(temp_project_dir)


@pytest.fixture
def smart_generator(file_selector):
    """Create a SmartRecommendationGenerator."""
    return SmartRecommendationGenerator(file_selector=file_selector)


@pytest.fixture
def recommendation_engine(temp_project_dir):
    """Create a RecommendationEngine."""
    return RecommendationEngine(project_path=temp_project_dir)


# Sample Data Fixtures


@pytest.fixture
def sample_coverage_degrading():
    """Sample coverage metrics showing degradation: 80% → 70%."""
    return [
        (80.0, {}),
        (78.0, {}),
        (75.0, {}),
        (72.0, {}),
        (70.0, {}),
    ]


@pytest.fixture
def sample_coverage_stable():
    """Sample coverage metrics showing stability: 80% ± 1%."""
    return [
        (80.0, {}),
        (80.5, {}),
        (79.5, {}),
        (80.2, {}),
        (79.8, {}),
    ]


@pytest.fixture
def sample_coverage_improving():
    """Sample coverage metrics showing improvement: 70% → 80%."""
    return [
        (70.0, {}),
        (72.0, {}),
        (75.0, {}),
        (78.0, {}),
        (80.0, {}),
    ]


@pytest.fixture
def sample_violations_increasing():
    """Sample violation metrics showing increase: 5 → 20."""
    return [
        (5, {}),
        (8, {}),
        (12, {}),
        (16, {}),
        (20, {}),
    ]


@pytest.fixture
def sample_commits_active():
    """Sample commit metrics showing active project."""
    return [
        (15, {"timeframe": "24h"}),
        (18, {"timeframe": "24h"}),
        (20, {"timeframe": "24h"}),
        (12, {"timeframe": "24h"}),
        (16, {"timeframe": "24h"}),
    ]


@pytest.fixture
def sample_alert_critical():
    """Create a sample CRITICAL alert."""
    return Alert(
        alert_type=AlertType.DEGRADATION,
        severity=AlertSeverity.CRITICAL,
        title="Test Project: Coverage dropped 10%",
        message="Test coverage decreased from 80% to 70% over the last 7 days.",
        metric_type="coverage",
        metadata={
            "delta": -10.0,
            "previous": 80.0,
            "current": 70.0,
        },
        created_at=datetime.now(),
        project="test_project",
    )


@pytest.fixture
def sample_alert_warning():
    """Create a sample WARNING alert."""
    return Alert(
        alert_type=AlertType.DEGRADATION,
        severity=AlertSeverity.WARNING,
        title="Test Project: Coverage dropped 3%",
        message="Test coverage decreased from 80% to 77% over the last 7 days.",
        metric_type="coverage",
        metadata={
            "delta": -3.0,
            "previous": 80.0,
            "current": 77.0,
        },
        created_at=datetime.now(),
        project="test_project",
    )


@pytest.fixture
def sample_alerts(sample_alert_critical, sample_alert_warning):
    """List of sample alerts sorted by severity."""
    return [sample_alert_critical, sample_alert_warning]


# Helper Functions


def create_metric_series(
    metric_tracker: MetricTracker,
    project: str,
    metric_type: MetricType,
    values: list,
    start_time: datetime = None,
):
    """
    Helper to create a series of metrics over time.

    Args:
        metric_tracker: MetricTracker instance
        project: Project name
        metric_type: Type of metric
        values: List of (value, metadata) tuples
        start_time: Starting timestamp (defaults to 7 days ago)

    Returns:
        List of created Metric objects
    """
    if start_time is None:
        start_time = datetime.now() - timedelta(days=len(values))

    metrics = []
    for i, (value, metadata) in enumerate(values):
        timestamp = start_time + timedelta(days=i)

        if metric_type == MetricType.COVERAGE:
            metric = metric_tracker.track_coverage(project, value, metadata, timestamp=timestamp)
        elif metric_type == MetricType.VIOLATIONS:
            metric = metric_tracker.track_violations(
                project, value, metadata=metadata, timestamp=timestamp
            )
        elif metric_type == MetricType.COMMITS:
            metric = metric_tracker.track_commits(
                project, value, metadata=metadata, timestamp=timestamp
            )
        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")

        metrics.append(metric)

    return metrics


# Export helper for easy imports
__all__ = [
    "temp_db",
    "temp_project_dir",
    "metric_tracker",
    "trend_analyzer",
    "alert_generator",
    "file_selector",
    "smart_generator",
    "recommendation_engine",
    "sample_coverage_degrading",
    "sample_coverage_stable",
    "sample_coverage_improving",
    "sample_violations_increasing",
    "sample_commits_active",
    "sample_alert_critical",
    "sample_alert_warning",
    "sample_alerts",
    "create_metric_series",
]
