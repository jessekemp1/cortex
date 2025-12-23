# Layers 3-4: Warning System + Smart Recommendations - Strategic Plan

## Executive Summary

This plan completes the Cortex Intelligence Stack by building:
- **Layer 3: Warning System** - Proactive metric monitoring and alerts
- **Layer 4: Smart Recommendations** - Context-aware, specific, actionable recommendations

These layers will transform Cortex from providing generic suggestions to offering precise, data-driven guidance based on project health, patterns, and trends.

**Timeline**: 2 days (6-8 hours total)
**Current Progress**: 50% (Layers 1-2 complete)
**Final State**: 100% (All 4 layers operational)

---

## Current State Analysis

### What We Have (Layers 1-2)

**Layer 1: Deep Project Analysis** ✅
- Tech stack detection (Python/FastAPI, JS/React, etc.)
- Test coverage estimation
- Quality tooling detection (linters, formatters)
- Warning generation (missing linters, low coverage)

**Layer 2: Pattern Memory** ✅
- 216 patterns indexed from git history
- Cross-project pattern recognition
- Similar work suggestions
- Pattern-enriched recommendations

### What's Missing (Layers 3-4)

**Layer 3: Warning System** ❌
- No trend monitoring (metrics over time)
- No degradation alerts (coverage dropping, violations increasing)
- No proactive warnings (before issues become critical)
- No metric history tracking

**Layer 4: Smart Recommendations** ❌
- Recommendations still too generic ("continue momentum")
- No file-specific guidance ("work on these 3 files")
- No integration of all intelligence layers
- No actionable step-by-step plans

### Pain Points Remaining

From user feedback, addressing ALL FOUR pain points:

1. **Too Generic** 🟡 PARTIALLY ADDRESSED
   - Layer 1: Adds tech stack context
   - Layer 2: Adds pattern context
   - **Layer 4 NEEDED**: Make recommendations file-specific and actionable

2. **No Warnings** 🔴 NOT ADDRESSED
   - Layer 1: Static warnings only (snapshot)
   - **Layer 3 NEEDED**: Trend-based warnings (degradation over time)

3. **Reinventing Wheels** ✅ ADDRESSED
   - Layer 2: Pattern memory finds similar work

4. **Wrong Priorities** 🟡 PARTIALLY ADDRESSED
   - Layer 1: Knows project health
   - **Layers 3-4 NEEDED**: Surface critical issues based on trends and data

---

## Architecture: Layers 3-4 Integration

```
┌─────────────────────────────────────────────────────────┐
│                   LAYER 4: SMART RECOMMENDATIONS         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Recommendation Generator                         │   │
│  │ - Consumes Layers 1-3                           │   │
│  │ - Generates specific, actionable recommendations│   │
│  │ - File-level guidance                           │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ Uses all layers
                          │
┌─────────────────────────────────────────────────────────┐
│                   LAYER 3: WARNING SYSTEM                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Metric       │  │ Trend        │  │ Alert        │ │
│  │ Tracker      │→ │ Analyzer     │→ │ Generator    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│         │                  │                  │         │
│         ▼                  ▼                  ▼         │
│  [Metrics DB]      [Trend Analysis]    [Warnings]     │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ Tracks over time
                          │
┌─────────────────────────────────────────────────────────┐
│              LAYER 2: PATTERN MEMORY (DONE)              │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────────────────────────────────────┐
│           LAYER 1: DEEP PROJECT ANALYSIS (DONE)          │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 3: Warning System - Detailed Design

### Objective

**Proactively detect project health degradation before it becomes critical.**

Examples:
- "Test coverage dropped from 45% → 32% in last 7 days"
- "Lint violations increased by 15 in last commit"
- "No commits to VortexV2 in 3 days (active project going dormant)"
- "Critical file main.py has 5 uncommitted changes"

### Architecture

```
MetricTracker
  ├── track_test_coverage()
  ├── track_lint_violations()
  ├── track_commit_frequency()
  └── track_file_changes()
         ▼
    [SQLite DB]
    ~/.cortex/metrics.db
         ▼
TrendAnalyzer
  ├── analyze_coverage_trend()
  ├── analyze_violation_trend()
  └── detect_anomalies()
         ▼
AlertGenerator
  ├── generate_degradation_alerts()
  ├── generate_activity_alerts()
  └── generate_critical_file_alerts()
         ▼
   [Warnings List]
```

### Data Model

**Metrics Table:**
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    project TEXT NOT NULL,
    metric_type TEXT NOT NULL,  -- 'coverage', 'violations', 'commits', 'files'
    metric_value REAL NOT NULL,
    timestamp DATETIME NOT NULL,
    metadata JSON,              -- Additional context
    UNIQUE(project, metric_type, timestamp)
);

CREATE INDEX idx_project_type_time ON metrics(project, metric_type, timestamp);
```

**Example Rows:**
```
| project  | metric_type | metric_value | timestamp           | metadata                    |
|----------|-------------|--------------|---------------------|-----------------------------|
| cortex   | coverage    | 34.0         | 2025-12-22 10:00:00 | {"test_files": 41}          |
| cortex   | coverage    | 32.0         | 2025-12-22 23:00:00 | {"test_files": 40}          |
| VortexV2 | violations  | 12.0         | 2025-12-22 10:00:00 | {"linter": "ruff"}          |
| VortexV2 | commits     | 5.0          | 2025-12-22 00:00:00 | {"timeframe": "24h"}        |
```

### Metrics to Track

1. **Test Coverage**
   - Source: Layer 1 project profiler
   - Frequency: Every 4 hours (when active) or on-demand
   - Alert: Drop > 5% in 24h OR drop > 10% in 7d

2. **Lint Violations**
   - Source: Run linter (if configured)
   - Frequency: On-demand or on commit
   - Alert: Increase > 10 violations in single commit

3. **Commit Frequency**
   - Source: Git log analysis
   - Frequency: Daily
   - Alert: Active project (3+ commits/week) goes 3+ days without commits

4. **Critical File Changes**
   - Source: Git status
   - Frequency: Real-time (on context injection)
   - Alert: Critical file (main.py, config.py) has uncommitted changes > 24h

### Trend Analysis

**Coverage Trend:**
```python
def analyze_coverage_trend(project: str, days: int = 7) -> Trend:
    """
    Analyze test coverage trend.

    Returns:
        Trend object with:
        - direction: "improving", "stable", "degrading"
        - delta: change in percentage points
        - rate: change per day
        - alert_level: "none", "warning", "critical"
    """
    # Get coverage metrics for last N days
    metrics = get_metrics(project, "coverage", days)

    # Linear regression to detect trend
    slope, intercept = linear_regression(metrics)

    # Calculate delta
    first = metrics[0].value
    last = metrics[-1].value
    delta = last - first

    # Determine alert level
    if delta < -5:  # Dropped > 5%
        alert_level = "critical"
    elif delta < -2:  # Dropped 2-5%
        alert_level = "warning"
    else:
        alert_level = "none"

    return Trend(
        direction="degrading" if slope < 0 else "improving",
        delta=delta,
        rate=slope,
        alert_level=alert_level
    )
```

### Alert Generation

**Alert Types:**

1. **Degradation Alerts** (RED)
   - Test coverage dropped significantly
   - Lint violations increased
   - Example: "⚠️  [CRITICAL] cortex: Test coverage dropped 8% (45% → 37%) in last 7 days"

2. **Activity Alerts** (YELLOW)
   - Active project going dormant
   - Unusual commit patterns
   - Example: "⚠️  [WARNING] VortexV2: No commits in 3 days (was active: 5 commits/day avg)"

3. **Critical File Alerts** (ORANGE)
   - Important files uncommitted for too long
   - High-change files modified
   - Example: "⚠️  [WARNING] main.py: Uncommitted changes for 2 days (critical file)"

### Implementation Plan

**Files to Create:**

1. `intelligence/monitoring/metric_tracker.py` (~300 lines)
   - MetricTracker class
   - Database operations
   - Metric collection methods

2. `intelligence/monitoring/trend_analyzer.py` (~250 lines)
   - TrendAnalyzer class
   - Statistical analysis (linear regression, anomaly detection)
   - Trend detection methods

3. `intelligence/monitoring/alert_generator.py` (~200 lines)
   - AlertGenerator class
   - Alert rule definitions
   - Alert formatting

4. `intelligence/monitoring/__init__.py`
   - Public API exports

**Integration Points:**

1. **Context Injection** (inject_context.py)
   - Add alert check on every prompt
   - Show most critical alert in context
   - Example: `<cortex_context>Project: cortex (Python/FastAPI) | ⚠️  Coverage dropped 8%</cortex_context>`

2. **Recommendations** (recommendation_engine.py)
   - High-priority recommendations for critical alerts
   - Example: "Fix test coverage degradation (dropped 8% in 7d)"

3. **CLI Commands**
   - `cortex alerts` - Show all active alerts
   - `cortex metrics <project>` - Show metric history
   - `cortex track` - Manually trigger metric tracking

**Metric Collection Strategy:**

1. **Automatic Tracking** (Background)
   - Cron job or launchd task runs every 4 hours
   - Tracks all active projects (3+ commits in 7d)
   - Stores metrics to SQLite

2. **On-Demand Tracking** (Real-time)
   - When context is injected, track current metrics
   - Compare to historical data
   - Generate alerts if degradation detected

3. **Manual Tracking** (User-initiated)
   - `cortex track` command
   - Useful for testing or one-off checks

### Success Criteria

✅ Metrics tracked over time (7+ day history)
✅ Trends detected accurately (coverage degradation)
✅ Alerts generated for critical issues
✅ Alerts shown in context injection
✅ Performance: <50ms overhead for alert check

---

## Layer 4: Smart Recommendations - Detailed Design

### Objective

**Generate specific, actionable, file-level recommendations using all intelligence layers.**

**Before (Generic):**
```
[MEDIUM] Continue momentum on cortex
```

**After (Smart):**
```
[HIGH] Fix test coverage degradation in cortex

Why: Coverage dropped 8% (45% → 37%) in last 7 days [Layer 3 Alert]
Tech: Python/FastAPI project [Layer 1]
Similar work: We fixed this in VortexV2 (added 15 tests to app/tests/) [Layer 2]

Next Steps:
1. Add tests for cortex/intelligence/analysis/project_profiler.py (0% coverage)
2. Add tests for cortex/intelligence/memory/pattern_indexer.py (0% coverage)
3. Run: pytest --cov=intelligence --cov-report=term

Files to work on:
- tests/intelligence/test_project_profiler.py (create)
- tests/intelligence/test_pattern_indexer.py (create)

Estimated effort: 2-3h
Impact: HIGH (prevents technical debt)
Confidence: 90% (based on 12 similar successful outcomes)
```

### Architecture

```
SmartRecommendationGenerator
  ├── gather_intelligence()
  │   ├── Layer 1: Project profile
  │   ├── Layer 2: Pattern memory
  │   └── Layer 3: Active alerts
  │
  ├── generate_alert_recommendations()
  │   └── High-priority recs for alerts
  │
  ├── generate_goal_recommendations()
  │   ├── Use patterns to suggest approach
  │   └── Use profiler to suggest files
  │
  ├── generate_health_recommendations()
  │   ├── Identify specific files needing work
  │   └── Suggest concrete steps
  │
  └── enrich_recommendations()
      ├── Add file-level guidance
      ├── Add pattern context
      └── Add step-by-step plan
```

### Recommendation Types

**1. Alert-Based Recommendations** (Highest Priority)

Triggered by Layer 3 alerts:
- Coverage degradation → Add tests to specific files
- Lint violations → Fix violations in specific files
- Dormant project → Continue work on last-modified files

**Example:**
```python
Recommendation(
    type="alert_response",
    priority="high",
    title="Fix test coverage degradation in cortex",
    rationale="Coverage dropped 8% (45% → 37%) in last 7 days",
    description="""
Test coverage has degraded significantly in the last week.
This trend indicates new code is being added without tests.

**Files with 0% coverage (add tests):**
- intelligence/analysis/project_profiler.py (650 lines, 0% coverage)
- intelligence/memory/pattern_indexer.py (580 lines, 0% coverage)
- intelligence/memory/pattern_memory.py (380 lines, 0% coverage)

**Next steps:**
1. Create tests/intelligence/test_project_profiler.py
2. Create tests/intelligence/test_pattern_indexer.py
3. Create tests/intelligence/test_pattern_memory.py
4. Run: pytest --cov=intelligence --cov-report=html
5. Target: 70% coverage for new modules

**Similar work from pattern memory:**
- [VortexV2] Added comprehensive test suite (15 tests, 85% coverage)
  Files: tests/unit/test_confidence_calibrator.py, tests/unit/test_lstm_model.py
""",
    files=["intelligence/analysis/project_profiler.py", ...],
    estimated_effort="2-3h",
    confidence=0.90
)
```

**2. Goal-Based Recommendations** (High Priority)

Enhanced with all layers:
- Layer 1: Detect project tech stack → Suggest language-specific approach
- Layer 2: Find similar implementations → Show relevant files
- Layer 3: Check for blockers → Flag if metrics degrading

**Example:**
```python
Recommendation(
    type="goal_progress",
    priority="high",
    title="Complete VortexV2 Lake Huron integration",
    rationale="Priority A goal, VortexV2 is active (189 commits this week)",
    description="""
Goal: VortexV2 Lake Huron integration - GRIB data testing and validation

**Tech Stack:** Python 3.11, FastAPI, PostgreSQL [Layer 1]

**Similar work from pattern memory:** [Layer 2]
- [VortexV2] Add historical weather data acquisition for Lake Huron
  Files: app/core/weather/grib_loader.py, app/core/weather/grib_exporter.py

**Current status:** [Layer 3]
✅ No active alerts
✅ Test coverage: 65% (target: 70%)

**Next steps:**
1. Complete GRIB data validation pipeline
   - Work on: app/core/weather/grib_loader.py (last modified: 2 days ago)
   - Add validation tests: tests/e2e/test_grib_e2e.py

2. Test with Lake Huron coordinates
   - Run: python verify_grib_setup.py
   - Verify: GRIB data loads correctly

3. Update documentation
   - File: docs/API_GUIDE.md
   - Add: Lake Huron endpoint examples

**Files to work on:**
- app/core/weather/grib_loader.py (validation logic)
- tests/e2e/test_grib_e2e.py (end-to-end tests)
- docs/API_GUIDE.md (documentation)
""",
    files=["app/core/weather/grib_loader.py", ...],
    estimated_effort="3-4h",
    confidence=0.85
)
```

**3. Health-Based Recommendations** (Medium Priority)

Proactive health improvements:
- Add missing linters (detected by Layer 1)
- Improve low coverage modules (detected by Layer 1 + Layer 3 trends)
- Update dependencies (detected by security scans)

**Example:**
```python
Recommendation(
    type="project_health",
    priority="medium",
    title="Add linter configuration to cortex",
    rationale="Python project without linter detected [Layer 1]",
    description="""
Project: cortex (Python/FastAPI)
Missing: Linter configuration

**Why add a linter:**
- Catch bugs early (type errors, unused imports)
- Enforce consistent style
- Reduce code review time

**Similar work from pattern memory:** [Layer 2]
- [VortexV2] Added ruff linter configuration
  Files: pyproject.toml, .github/workflows/lint.yml

**Recommended approach:**
1. Add ruff configuration to pyproject.toml
2. Run: ruff check . --fix
3. Add pre-commit hook (optional)
4. Add CI lint check (optional)

**Files to create/modify:**
- pyproject.toml (add [tool.ruff] section)
- .pre-commit-config.yaml (optional)
- .github/workflows/lint.yml (optional)

**Example configuration:**
```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I"]
ignore = ["E501"]
```

**Estimated effort:** 30min - 1h
""",
    files=["pyproject.toml"],
    estimated_effort="30min-1h",
    confidence=0.80
)
```

### File-Level Guidance

**Critical Feature: Specific Files to Work On**

Every recommendation includes:
1. **Primary files**: Files that need changes
2. **Test files**: Tests to add/update
3. **Doc files**: Documentation to update
4. **Config files**: Configuration changes needed

**How to identify files:**

1. **From Layer 1 (Project Profiler)**
   - Critical files (main.py, config.py)
   - Low coverage files (0% coverage modules)
   - Recently changed files (git log)

2. **From Layer 2 (Pattern Memory)**
   - Files changed in similar work
   - Common patterns (tests/ structure)

3. **From Layer 3 (Warning System)**
   - Files with uncommitted changes
   - Files causing metric degradation

4. **From Git Analysis**
   - Last-modified files (continue work)
   - High-churn files (need attention)

**Example File Selection Logic:**
```python
def select_files_for_recommendation(
    recommendation_type: str,
    project: str,
    context: Dict
) -> List[str]:
    """Select specific files for recommendation."""

    files = []

    if recommendation_type == "test_coverage":
        # Get files with 0% coverage from Layer 1
        profile = layer1_profiler.profile(project)
        untested_files = [
            f for f in profile.source_files
            if f.coverage == 0 and f.lines > 100
        ]
        files.extend(untested_files[:5])  # Top 5

    elif recommendation_type == "goal_progress":
        # Get last-modified files from git
        recent_files = git.get_recently_modified(project, days=7)
        files.extend(recent_files[:3])  # Top 3

        # Add similar files from Layer 2
        similar_work = layer2_patterns.find_similar(context)
        for work in similar_work[:2]:
            files.extend(work.files_changed[:2])

    return list(set(files))  # Deduplicate
```

### Step-by-Step Plans

**Critical Feature: Actionable Next Steps**

Every recommendation includes:
1. **Numbered steps** (3-5 concrete actions)
2. **Commands to run** (pytest, linter, scripts)
3. **Success criteria** (how to verify completion)

**Example:**
```
Next Steps:
1. Create test file
   - File: tests/intelligence/test_project_profiler.py
   - Copy structure from: tests/test_orchestrator.py

2. Add unit tests for tech stack detection
   - Test: test_detect_python_stack()
   - Test: test_detect_js_stack()
   - Run: pytest tests/intelligence/test_project_profiler.py -v

3. Add unit tests for coverage estimation
   - Test: test_estimate_coverage()
   - Run: pytest tests/intelligence/ --cov=intelligence

4. Verify coverage improved
   - Run: pytest --cov=intelligence --cov-report=term
   - Expected: >70% coverage

5. Commit changes
   - git add tests/intelligence/
   - git commit -m "test: add unit tests for project profiler"
```

### Implementation Plan

**Files to Create:**

1. `intelligence/recommendations/smart_generator.py` (~400 lines)
   - SmartRecommendationGenerator class
   - Integration with Layers 1-3
   - File selection logic
   - Step generation

2. `intelligence/recommendations/file_selector.py` (~200 lines)
   - File selection algorithms
   - Priority scoring for files
   - Deduplication

3. `intelligence/recommendations/__init__.py`
   - Public API exports

**Files to Modify:**

1. `recommendation_engine.py`
   - Replace generic generators with SmartRecommendationGenerator
   - Integrate Layer 3 alerts
   - Use file selector for all recommendations

**Integration Points:**

1. **All Recommendations**
   - Use Layer 1 for tech context
   - Use Layer 2 for pattern context
   - Use Layer 3 for alert context
   - Add file-level guidance
   - Add step-by-step plans

2. **Context Injection**
   - Include file guidance in compact context
   - Example: `Project: cortex (Python/FastAPI) | Fix: project_profiler.py (needs tests)`

3. **CLI Output**
   - Rich formatting for file lists
   - Collapsible step-by-step plans
   - Clickable file paths

### Success Criteria

✅ All recommendations include specific files
✅ All recommendations include next steps (3-5 items)
✅ Alert-based recommendations generated for critical issues
✅ Goal recommendations enhanced with patterns and files
✅ Health recommendations include concrete fixes
✅ User reports recommendations are actionable (not generic)

---

## Implementation Timeline

### Day 1: Layer 3 - Warning System (4 hours)

**Morning (2h): Core Infrastructure**
- Create `intelligence/monitoring/` directory
- Implement `metric_tracker.py` (database, tracking methods)
- Implement `trend_analyzer.py` (trend detection, statistics)
- Test metric tracking and storage

**Afternoon (2h): Alert Generation & Integration**
- Implement `alert_generator.py` (alert rules, formatting)
- Integrate with `inject_context.py` (show alerts in context)
- Integrate with `recommendation_engine.py` (alert-based recs)
- Test end-to-end alert flow

**Deliverables:**
- ✅ Metrics tracked to SQLite
- ✅ Trends detected (coverage, violations)
- ✅ Alerts generated for degradation
- ✅ Alerts shown in context

### Day 2: Layer 4 - Smart Recommendations (4 hours)

**Morning (2h): Smart Generator Core**
- Create `intelligence/recommendations/` directory
- Implement `smart_generator.py` (core generator)
- Implement `file_selector.py` (file selection logic)
- Test file selection algorithms

**Afternoon (2h): Integration & Polish**
- Replace generic generators in `recommendation_engine.py`
- Add step-by-step plan generation
- Enhance CLI output formatting
- End-to-end testing
- Documentation

**Deliverables:**
- ✅ Smart recommendations with files
- ✅ Step-by-step plans included
- ✅ All recommendations enhanced
- ✅ CLI output polished

### Total Time: 8 hours (2 days)

---

## Risk Assessment

### Technical Risks

1. **SQLite Performance** (Low Risk)
   - Mitigation: Small dataset (<10k rows), indexed queries
   - Fallback: In-memory cache if too slow

2. **Metric Collection Overhead** (Medium Risk)
   - Mitigation: Async collection, 4-hour intervals
   - Fallback: On-demand only (no background tracking)

3. **Alert Noise** (Medium Risk)
   - Mitigation: Careful threshold tuning, alert levels
   - Fallback: User-configurable alert sensitivity

4. **File Selection Accuracy** (Medium Risk)
   - Mitigation: Multiple heuristics, user feedback loop
   - Fallback: Show top N files, let user choose

### User Experience Risks

1. **Recommendations Still Too Generic** (Low Risk)
   - Mitigation: Layer 4 explicitly addresses this
   - Validation: User testing before completion

2. **Alert Fatigue** (Medium Risk)
   - Mitigation: Only show critical alerts in context
   - Fallback: `/cortex alerts` command for full list

3. **Overwhelming Information** (Low Risk)
   - Mitigation: Collapsible sections, clear priorities
   - Fallback: Short mode with minimal details

---

## Success Metrics

### Layer 3: Warning System

| Metric | Target | Measurement |
|--------|--------|-------------|
| Metric tracking works | 100% | All active projects tracked |
| Alerts generated | >0 | At least 1 alert for degraded project |
| Alert accuracy | >80% | True positives / total alerts |
| Performance overhead | <50ms | Alert check on context injection |
| User finds alerts useful | >70% | User feedback survey |

### Layer 4: Smart Recommendations

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recommendations include files | 100% | All recs have file list |
| Recommendations include steps | 100% | All recs have 3+ steps |
| File relevance | >80% | User marks files as relevant |
| Step actionability | >80% | User can execute without clarification |
| User satisfaction | >80% | "Recommendations are specific and actionable" |

### Overall Stack

| Metric | Target | Measurement |
|--------|--------|-------------|
| All pain points addressed | 4/4 | Too generic, No warnings, Reinventing wheels, Wrong priorities |
| Context injection speed | <500ms | End-to-end timing |
| Recommendation quality | >4/5 | User rating scale |
| Daily usage | >5 uses/day | CLI command frequency |

---

## Testing Strategy

### Layer 3 Testing

**Unit Tests:**
- MetricTracker: database operations, metric collection
- TrendAnalyzer: trend detection, anomaly detection
- AlertGenerator: alert rules, formatting

**Integration Tests:**
- End-to-end metric tracking → trend analysis → alert generation
- Context injection with alerts
- Recommendation generation from alerts

**Manual Tests:**
- Create project with degrading coverage
- Verify alert generated
- Verify alert shown in context
- Verify recommendation created

### Layer 4 Testing

**Unit Tests:**
- SmartRecommendationGenerator: file selection, step generation
- FileSelector: priority scoring, deduplication

**Integration Tests:**
- Full recommendation generation with all layers
- File relevance for different recommendation types
- Step generation for different contexts

**Manual Tests:**
- Generate recommendations for 5 different projects
- Verify file lists are specific and relevant
- Verify steps are actionable
- User feedback: "Can I follow these steps?"

---

## Documentation Plan

### User Documentation

1. **Layer 3 Guide**: `intelligence/monitoring/README.md`
   - How metric tracking works
   - Alert types and thresholds
   - How to use `/cortex alerts` command
   - How to configure alert sensitivity

2. **Layer 4 Guide**: `intelligence/recommendations/README.md`
   - How smart recommendations work
   - How files are selected
   - How to interpret step-by-step plans
   - How to provide feedback

3. **Complete Stack Guide**: `INTELLIGENCE_STACK.md`
   - Overview of all 4 layers
   - How they work together
   - Usage examples
   - Troubleshooting

### Developer Documentation

1. **Architecture**: `ARCHITECTURE.md`
   - System design diagrams
   - Data flow
   - Integration points

2. **API Reference**: Auto-generated docstrings
   - All public methods documented
   - Example usage in docstrings

---

## Future Enhancements (Not in Current Plan)

### Layer 3 Enhancements
- Email/Slack alerts for critical issues
- Customizable alert thresholds per project
- Machine learning for anomaly detection
- Predictive alerts ("coverage will drop below 50% in 3 days at current rate")

### Layer 4 Enhancements
- AI-generated code snippets (using patterns from Layer 2)
- Interactive mode (ask questions about recommendations)
- Confidence explanations (why 90% confidence?)
- A/B testing different recommendation strategies

### Cross-Layer Enhancements
- Web dashboard for visualization
- Team collaboration (shared pattern memory)
- Integration with GitHub Issues/PRs
- VS Code extension

---

## Conclusion

This plan completes the Cortex Intelligence Stack:

**Current State (50%)**:
- ✅ Layer 1: Deep Project Analysis
- ✅ Layer 2: Pattern Memory
- ❌ Layer 3: Warning System
- ❌ Layer 4: Smart Recommendations

**After Implementation (100%)**:
- ✅ Layer 1: Deep Project Analysis
- ✅ Layer 2: Pattern Memory
- ✅ Layer 3: Warning System
- ✅ Layer 4: Smart Recommendations

**Pain Points Addressed**:
- ✅ Too Generic → Layer 4 makes recommendations file-specific
- ✅ No Warnings → Layer 3 adds proactive alerts
- ✅ Reinventing Wheels → Layer 2 finds similar work
- ✅ Wrong Priorities → Layers 3-4 surface critical issues

**Timeline**: 2 days (8 hours total)
**ROI**: 8 hours invested → ~10 hours saved per month

**Next Step**: Begin Layer 3 implementation (metric tracking).

---

**Plan Version**: 1.0
**Created**: 2025-12-22
**Status**: Ready for implementation
**Approval Required**: Yes (confirm timeline and approach)
