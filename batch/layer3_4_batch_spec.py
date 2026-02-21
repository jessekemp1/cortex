#!/usr/bin/env python3
"""
Batch job specification for implementing Layers 3-4.

This creates a batch of Claude API requests to implement:
- Layer 3: Warning System (metric tracking, trend analysis, alerts)
- Layer 4: Smart Recommendations (file-level guidance, actionable steps)
"""

import json
import sys
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.batch_api_client import BatchRequest
from batch.model_policy import AnthropicBatchModels

MODELS = AnthropicBatchModels()


def create_layer3_requests() -> List[BatchRequest]:
    """Create batch requests for Layer 3 implementation."""

    requests = []

    # Read the strategic plan
    plan_path = Path("~/projects/cortex/LAYERS_3_4_STRATEGIC_PLAN.md")
    plan_content = plan_path.read_text()

    # Task 1: Implement metric_tracker.py
    requests.append(
        BatchRequest(
            custom_id="layer3_metric_tracker",
            params={
                "model": MODELS.strong,
                "max_tokens": 16000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""You are implementing Layer 3 (Warning System) for the Cortex Intelligence Stack.

# Context

{plan_content[:10000]}

# Your Task

Implement `intelligence/monitoring/metric_tracker.py` (~300 lines) with:

1. **MetricTracker Class**:
   - SQLite database connection and initialization
   - Schema: metrics table (project, metric_type, metric_value, timestamp, metadata)
   - Methods:
     - track_coverage(project, coverage_pct, metadata)
     - track_violations(project, count, linter, metadata)
     - track_commits(project, count, timeframe)
     - track_file_changes(project, file_path, uncommitted_time)
     - get_metrics(project, metric_type, days)

2. **Database Operations**:
   - Create tables with proper indexes
   - Upsert metrics (update if duplicate timestamp)
   - Query metrics with time range filters

3. **Integration Points**:
   - Called by Layer 1 project profiler
   - Called by inject_context.py
   - Stores data to ~/.cortex/metrics.db

# Requirements

- Use SQLite3 (built-in, no dependencies)
- Proper error handling (database locked, disk full)
- Timestamps in UTC
- Metadata as JSON text field
- Indexes for performance

# Output

Provide the complete implementation of `metric_tracker.py` as a single code block.
Include comprehensive docstrings and error handling.
""",
                    }
                ],
                "system": "You are an expert Python developer implementing a production-quality metric tracking system. Write clean, well-documented, robust code with proper error handling.",
            },
        )
    )

    # Task 2: Implement trend_analyzer.py
    requests.append(
        BatchRequest(
            custom_id="layer3_trend_analyzer",
            params={
                "model": MODELS.strong,
                "max_tokens": 16000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""You are implementing Layer 3 (Warning System) for the Cortex Intelligence Stack.

# Context

{plan_content[:10000]}

# Your Task

Implement `intelligence/monitoring/trend_analyzer.py` (~250 lines) with:

1. **TrendAnalyzer Class**:
   - Takes MetricTracker instance in constructor
   - Methods:
     - analyze_coverage_trend(project, days=7) -> Trend
     - analyze_violation_trend(project, days=7) -> Trend
     - analyze_activity_trend(project, days=7) -> Trend
     - detect_anomalies(project, metric_type, days=7) -> List[Anomaly]

2. **Trend Object**:
   - direction: "improving", "stable", "degrading"
   - delta: absolute change
   - rate: change per day (slope from linear regression)
   - alert_level: "none", "warning", "critical"
   - start_value, end_value, timestamps

3. **Statistical Analysis**:
   - Simple linear regression (numpy not available, use manual calculation)
   - Standard deviation for anomaly detection
   - Threshold-based alert levels

4. **Alert Thresholds**:
   - Coverage: critical if dropped >5%, warning if >2%
   - Violations: critical if increased >10, warning if >5
   - Activity: critical if active project dormant >3 days

# Output

Provide the complete implementation of `trend_analyzer.py` as a single code block.
Include Trend and Anomaly dataclasses, statistical functions, and comprehensive docstrings.
""",
                    }
                ],
                "system": "You are an expert Python developer implementing statistical analysis. Write efficient code without external dependencies (no numpy/pandas).",
            },
        )
    )

    # Task 3: Implement alert_generator.py
    requests.append(
        BatchRequest(
            custom_id="layer3_alert_generator",
            params={
                "model": MODELS.strong,
                "max_tokens": 16000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""You are implementing Layer 3 (Warning System) for the Cortex Intelligence Stack.

# Context

{plan_content[:10000]}

# Your Task

Implement `intelligence/monitoring/alert_generator.py` (~200 lines) with:

1. **AlertGenerator Class**:
   - Takes TrendAnalyzer instance in constructor
   - Methods:
     - generate_alerts(project, days=7) -> List[Alert]
     - generate_degradation_alerts(project) -> List[Alert]
     - generate_activity_alerts(project) -> List[Alert]
     - generate_critical_file_alerts(project) -> List[Alert]

2. **Alert Object**:
   - alert_type: "degradation", "activity", "critical_file"
   - severity: "critical", "warning", "info"
   - title: Short description
   - message: Full description with context
   - metric_type: "coverage", "violations", "commits", "files"
   - metadata: Additional context (trend, delta, etc.)
   - created_at: Timestamp

3. **Alert Rules**:
   - Degradation: based on Trend alert_level
   - Activity: active project (3+ commits/week) dormant >3 days
   - Critical files: main.py, config.py, app.py uncommitted >24h

4. **Formatting**:
   - Compact format for context injection
   - Detailed format for CLI display
   - Emoji indicators (⚠️  for warning, 🔴 for critical)

# Output

Provide the complete implementation of `alert_generator.py` as a single code block.
Include Alert dataclass, alert rules, and formatting methods.
""",
                    }
                ],
                "system": "You are an expert Python developer implementing an alert system. Write clear, maintainable code with good formatting.",
            },
        )
    )

    # Task 4: Integration with inject_context.py
    requests.append(
        BatchRequest(
            custom_id="layer3_inject_integration",
            params={
                "model": MODELS.integration,
                "max_tokens": 8000,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": """You are integrating Layer 3 (Warning System) into the inject_context.py hook.

# Context

Layer 3 provides alerts for project health degradation.
The inject_context.py hook already has Layer 1 (tech stack) integration.

# Your Task

Modify `.claude/hooks/inject_context.py` to:

1. Import Layer 3 components:
   - from intelligence.monitoring.metric_tracker import MetricTracker
   - from intelligence.monitoring.trend_analyzer import TrendAnalyzer
   - from intelligence.monitoring.alert_generator import AlertGenerator

2. Add `get_alerts()` function:
   - Initialize components
   - Generate alerts for current project
   - Return most critical alert (if any)
   - Fallback gracefully if Layer 3 unavailable

3. Update `get_enhanced_context()`:
   - Call get_alerts()
   - If critical alert exists, replace warning with alert
   - Format: "Project: X (Tech) | 🔴 Coverage dropped 8%"

4. Performance:
   - Cache alerts for 5 minutes (don't regenerate on every prompt)
   - Timeout after 100ms (don't block context injection)

# Current inject_context.py

```python
def get_enhanced_context() -> str:
    \"\"\"Get enhanced context with tech stack and warnings.\"\"\"
    try:
        from intelligence.analysis.project_profiler import profile_project

        cwd = Path.cwd()
        profile = profile_project(cwd, quick=True)

        parts = []

        # Project name with tech stack
        tech = profile.tech_stack.to_compact_str()
        if tech:
            parts.append(f"Project: {profile.project_name} ({tech})")
        else:
            parts.append(f"Project: {profile.project_name}")

        # Git branch
        try:
            branch = subprocess.check_output(...)
            if branch:
                parts.append(f"Branch: {branch}")
        except Exception:
            pass

        # Warning (most important one)
        if profile.warnings:
            parts.append(f"⚠️  {profile.warnings[0]}")

        return " | ".join(parts)

    except Exception:
        return get_basic_git_context()
```

# Output

Provide the modified `inject_context.py` code showing the integration.
Focus on the new `get_alerts()` function and changes to `get_enhanced_context()`.
""",
                    }
                ],
                "system": "You are integrating a warning system into an existing hook. Write efficient, non-blocking code with proper error handling.",
            },
        )
    )

    return requests


def create_layer4_requests() -> List[BatchRequest]:
    """Create batch requests for Layer 4 implementation."""

    requests = []

    plan_path = Path("~/projects/cortex/LAYERS_3_4_STRATEGIC_PLAN.md")
    plan_content = plan_path.read_text()

    # Task 5: Implement file_selector.py
    requests.append(
        BatchRequest(
            custom_id="layer4_file_selector",
            params={
                "model": MODELS.strong,
                "max_tokens": 16000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""You are implementing Layer 4 (Smart Recommendations) for the Cortex Intelligence Stack.

# Context

{plan_content[20000:35000]}

# Your Task

Implement `intelligence/recommendations/file_selector.py` (~200 lines) with:

1. **FileSelector Class**:
   - Takes project path and context dict
   - Methods:
     - select_for_coverage_improvement(limit=5) -> List[FileInfo]
     - select_for_goal_work(goal, limit=3) -> List[FileInfo]
     - select_recently_modified(days=7, limit=3) -> List[FileInfo]
     - select_critical_files(limit=5) -> List[FileInfo]

2. **FileInfo Object**:
   - path: Relative file path
   - reason: Why this file was selected
   - priority: 1-10 score
   - metadata: Additional context (coverage, lines, last_modified)

3. **Selection Heuristics**:
   - Coverage: Files with 0% coverage AND >100 lines
   - Goal work: Last modified files + files from similar patterns
   - Critical: main.py, config.py, app.py, plus high-churn files
   - Recently modified: git log --since=7.days

4. **Integration with Layers 1-2**:
   - Use Layer 1 project profiler for coverage data
   - Use Layer 2 pattern memory for similar work files
   - Git analysis for recent/critical files

# Output

Provide the complete implementation of `file_selector.py` as a single code block.
Include FileInfo dataclass, selection algorithms with scoring, and integration with Layers 1-2.
""",
                    }
                ],
                "system": "You are an expert at code analysis and file relevance scoring. Write intelligent heuristics for file selection.",
            },
        )
    )

    # Task 6: Implement smart_generator.py
    requests.append(
        BatchRequest(
            custom_id="layer4_smart_generator",
            params={
                "model": MODELS.strong,
                "max_tokens": 16000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": f"""You are implementing Layer 4 (Smart Recommendations) for the Cortex Intelligence Stack.

# Context

{plan_content[35000:55000]}

# Your Task

Implement `intelligence/recommendations/smart_generator.py` (~400 lines) with:

1. **SmartRecommendationGenerator Class**:
   - Integrates Layers 1, 2, 3
   - Methods:
     - generate_alert_recommendations(alerts) -> List[Recommendation]
     - generate_goal_recommendations(goals, project_activity) -> List[Recommendation]
     - generate_health_recommendations(project_activity) -> List[Recommendation]
     - enrich_with_intelligence(recommendation) -> Recommendation

2. **Intelligence Gathering**:
   - gather_project_intelligence(project) -> Dict
     - Layer 1: tech stack, coverage, quality tools
     - Layer 2: similar patterns
     - Layer 3: active alerts
     - Git: recent files, critical files

3. **File-Level Guidance**:
   - Add specific files to work on (from FileSelector)
   - Add test files to create
   - Add documentation files to update

4. **Step Generation**:
   - generate_steps(recommendation_type, context) -> List[str]
   - 3-5 concrete, actionable steps
   - Include commands to run
   - Include success criteria

5. **Pattern Integration**:
   - For each recommendation, find similar work from Layer 2
   - Add "Similar work:" section with files changed
   - Extract lessons from patterns

# Output

Provide the complete implementation of `smart_generator.py` as a single code block.
Include all methods, comprehensive intelligence gathering, and step generation logic.
""",
                    }
                ],
                "system": "You are creating an intelligent recommendation system. Write code that synthesizes multiple data sources into actionable guidance.",
            },
        )
    )

    # Task 7: Integration with recommendation_engine.py
    requests.append(
        BatchRequest(
            custom_id="layer4_engine_integration",
            params={
                "model": MODELS.integration,
                "max_tokens": 8000,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": """You are integrating Layer 4 (Smart Recommendations) into the recommendation engine.

# Your Task

Modify `cortex/recommendation_engine.py` to:

1. Import Layer 4 components:
   - from intelligence.recommendations.smart_generator import SmartRecommendationGenerator
   - from intelligence.recommendations.file_selector import FileSelector

2. Replace generic recommendation generators:
   - _generate_blocker_recommendations() → SmartGenerator
   - _generate_goal_recommendations() → SmartGenerator
   - _generate_health_recommendations() → SmartGenerator
   - _generate_momentum_recommendations() → SmartGenerator

3. Add intelligence enrichment:
   - Before sorting, call smart_generator.enrich_with_intelligence()
   - This adds files, steps, patterns to all recommendations

4. Update Recommendation object if needed:
   - Add files: List[str] field
   - Add steps: List[str] field
   - Keep existing fields compatible

# Current Flow

```python
def generate_recommendations(...) -> List[Recommendation]:
    recommendations = []

    # 1. Blocker resolution
    recommendations.extend(self._generate_blocker_recommendations(...))

    # 2. Goal progress
    recommendations.extend(self._generate_goal_recommendations(...))

    # 3. Health
    recommendations.extend(self._generate_health_recommendations(...))

    # 4. Momentum
    recommendations.extend(self._generate_momentum_recommendations(...))

    # Apply learning adjustments
    if self.learning_system:
        recommendations = self._apply_learning_adjustments(recommendations)

    # Enrich with patterns (Layer 2)
    if self.pattern_memory:
        recommendations = self._enrich_with_patterns(recommendations)

    # Sort and return
    recommendations.sort(key=lambda r: self._priority_score(r), reverse=True)
    return recommendations[:limit]
```

# Output

Show the modified code for:
1. New imports
2. SmartGenerator initialization in __init__
3. Updated generate_recommendations() flow
4. How to replace the 4 generators with SmartGenerator
""",
                    }
                ],
                "system": "You are refactoring code to use a new smart recommendation system. Maintain backward compatibility while integrating new features.",
            },
        )
    )

    # Task 8: Create CLI commands and documentation
    requests.append(
        BatchRequest(
            custom_id="layer3_4_cli_docs",
            params={
                "model": MODELS.integration,
                "max_tokens": 8000,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": """You are creating CLI commands and documentation for Layers 3-4.

# Your Task

Create the following files:

1. **cortex/cli.py additions** (new commands):
   - `cortex alerts` - Show all active alerts for all projects
   - `cortex metrics <project>` - Show metric history for a project
   - `cortex track` - Manually trigger metric tracking for current project

2. **intelligence/monitoring/README.md**:
   - Overview of Layer 3 (Warning System)
   - How metric tracking works
   - Alert types and thresholds
   - Usage examples
   - Configuration options

3. **intelligence/recommendations/README.md**:
   - Overview of Layer 4 (Smart Recommendations)
   - How file selection works
   - How step generation works
   - Example recommendations (before/after)
   - Integration with Layers 1-3

4. **INTELLIGENCE_STACK.md** (complete guide):
   - All 4 layers overview
   - How they work together
   - Data flow diagram
   - Usage examples
   - Troubleshooting

# Output Format

For each file, provide:
1. File path
2. Complete content
3. Brief description

Make documentation clear, practical, and example-driven.
""",
                    }
                ],
                "system": "You are writing technical documentation for developers. Be clear, concise, and provide many examples.",
            },
        )
    )

    return requests


def create_all_batch_requests() -> List[BatchRequest]:
    """Create all batch requests for Layers 3-4."""
    requests = []
    requests.extend(create_layer3_requests())
    requests.extend(create_layer4_requests())
    return requests


def save_batch_spec(output_path: Path):
    """Save batch specification to JSON file."""
    requests = create_all_batch_requests()

    # Convert to JSON
    spec = {
        "description": "Cortex Intelligence Stack - Layers 3-4 Implementation",
        "created_at": "2025-12-22T23:30:00Z",
        "total_requests": len(requests),
        "requests": [{"custom_id": req.custom_id, "params": req.params} for req in requests],
    }

    output_path.write_text(json.dumps(spec, indent=2))
    print(f"✅ Saved batch spec to {output_path}")
    print(f"   Total requests: {len(requests)}")
    print("   Layer 3 requests: 4")
    print("   Layer 4 requests: 4")


if __name__ == "__main__":
    output_path = Path(__file__).parent / "layer3_4_batch.json"
    save_batch_spec(output_path)
