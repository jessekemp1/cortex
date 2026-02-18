# Cortex Usage Examples

**Real-world examples of using Cortex**

This guide provides practical examples of using Cortex in common scenarios.

---

## Example 1: Daily Workflow

### Morning Routine

```bash
#!/bin/bash
# morning_briefing.sh

echo "=== MORNING BRIEFING ==="

# Get session context
echo "Current Context:"
python bridge.py session-context

# Get portfolio overview
echo -e "\nPortfolio Overview:"
python bridge.py portfolio stats

# Get metrics dashboard
echo -e "\nMetrics Dashboard:"
python3 -c "
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()
dashboard = tracker.get_dashboard(days=7)
print(f\"Velocity Improvement: {dashboard.get('velocity', {}).get('improvement_pct', 0):.1f}%\")
print(f\"Mistake Prevention Rate: {dashboard.get('mistakes', {}).get('prevention_rate', 0):.1f}%\")
print(f\"ROI: {dashboard.get('roi', {}).get('ratio', 0):.2f}x\")
"
```

**Output**:
```
=== MORNING BRIEFING ===
Current Context:
Project: cortex
Branch: main
Recent commits: 3
Focus: Documentation

Portfolio Overview:
Total projects: 3
Active projects: 2
Tech stack: python (3), fastapi (3)

Metrics Dashboard:
Velocity Improvement: 66.7%
Mistake Prevention Rate: 85.0%
ROI: 3.88x
```

---

## Example 2: Project Analysis

### Before Starting a New Feature

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# 1. Get project context
context = bridge.get_portfolio_context("VortexV2")
print(f"Project: {context['project']['name']}")
print(f"Tech Stack: {', '.join(context['tech_stack'])}")

# 2. Find similar work
results = bridge.search_specs("GRIB data processing", project="VortexV2", limit=3)
print(f"\nSimilar Work Found: {len(results)}")
for result in results:
    print(f"  - {result['spec_name']} (similarity: {result['similarity']:.2f})")

# 3. Get applicable patterns
patterns = bridge.get_portfolio_patterns(pattern_type="data_processing")
print(f"\nApplicable Patterns: {len(patterns)}")
for pattern in patterns[:3]:
    print(f"  - {pattern['name']}: {pattern['description']}")

# 4. Get relevant lessons
lessons = bridge.get_lessons(category="data_validation")
print(f"\nRelevant Lessons: {len(lessons)}")
for lesson in lessons[:3]:
    print(f"  - {lesson['title']}: {lesson['prevention']}")
```

**Output**:
```
Project: VortexV2
Tech Stack: python, grib, fastapi, postgresql

Similar Work Found: 3
  - GRIB_PROCESSING.md (similarity: 0.92)
  - DATA_PIPELINE.md (similarity: 0.85)
  - WEATHER_DATA.md (similarity: 0.78)

Applicable Patterns: 2
  - GRIB Data Processing Pipeline: Multi-stage pipeline for GRIB weather data
  - Data Validation Pattern: Validate before processing

Relevant Lessons: 3
  - Always check GRIB index files: Use Herbie.inv() before download
  - Validate data quality: Check for missing values and bounds
  - Cache decoded data: Avoid re-processing
```

---

## Example 3: Cross-Project Pattern Discovery

### Finding Reusable Patterns

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Get all cross-project patterns
patterns = bridge.get_portfolio_patterns()

# Group by category
from collections import defaultdict
by_category = defaultdict(list)
for pattern in patterns:
    category = pattern.get('category', 'other')
    by_category[category].append(pattern)

# Display patterns by category
for category, pattern_list in by_category.items():
    print(f"\n{category.upper()} Patterns ({len(pattern_list)}):")
    for pattern in pattern_list:
        projects = ', '.join(pattern.get('projects', []))
        print(f"  - {pattern['name']}: Used in {projects}")
        print(f"    {pattern['description']}")
```

**Output**:
```
DATA_PROCESSING Patterns (2):
  - GRIB Data Processing Pipeline: Used in VortexV2
    Multi-stage pipeline for GRIB weather data: download → decode → validate → store
  - Market Data Pipeline: Used in AlphaArena
    Real-time market data processing: fetch → validate → store

API Patterns (1):
  - Async FastAPI Pattern: Used in VortexV2, AlphaArena, Cortex
    Async endpoints with proper error handling and validation
```

---

## Example 4: Spec Search

### Finding Documentation

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Search for API documentation
results = bridge.search_specs("API rate limiting", project="cortex", limit=5)

print(f"Found {len(results)} relevant specs:\n")
for i, result in enumerate(results, 1):
    print(f"{i}. {result['spec_name']}")
    print(f"   Project: {result.get('project', 'unknown')}")
    print(f"   Similarity: {result.get('similarity', 0):.2f}")
    print(f"   Summary: {result.get('summary', '')[:100]}...")
    print()
```

**Output**:
```
Found 5 relevant specs:

1. API_DOCUMENTATION.md
   Project: cortex
   Similarity: 0.92
   Summary: Complete API documentation including rate limiting, authentication, and error handling...

2. SECURITY_GUIDE.md
   Project: cortex
   Similarity: 0.85
   Summary: Security best practices including rate limiting, input validation, and secrets management...

3. DEPLOYMENT.md
   Project: cortex
   Similarity: 0.78
   Summary: Deployment guide including production configuration, monitoring, and scaling...
```

---

## Example 5: Metrics Tracking

### Tracking Your Work

```python
from metrics_tracker import MetricsTracker

tracker = MetricsTracker()

# Example: Track velocity for a completed task
tracker.record_velocity(
    task="Implement API rate limiting",
    time_without_cortex=120,  # Estimated 2 hours without Cortex
    time_with_cortex=30,       # Actual 30 minutes with Cortex
    project="cortex",
    notes="Used spec search to find existing pattern, saved 90 minutes"
)

# Example: Track mistake prevention
tracker.record_mistake(
    mistake_type="security",
    was_prevented=True,
    lesson_id="rate_limiting_check",
    project="cortex",
    impact_minutes=60,
    notes="Remembered to add rate limiting from portfolio patterns"
)

# Example: Track prediction and outcome
prediction_id = "pred_001"
tracker.record_prediction(
    prediction_id=prediction_id,
    task="Implement feature",
    predicted_outcome="success",
    confidence=0.85,
    predicted_time=30,
    project="cortex"
)

# Later, record actual outcome
tracker.record_outcome(
    prediction_id=prediction_id,
    actual_outcome="success",
    actual_time=25
)

# Get dashboard
dashboard = tracker.get_dashboard(days=30)
print(f"Velocity Improvement: {dashboard['velocity']['improvement_pct']:.1f}%")
print(f"Mistake Prevention Rate: {dashboard['mistakes']['prevention_rate']:.1f}%")
print(f"ROI: {dashboard['roi']['ratio']:.2f}x")
```

**Output**:
```
Velocity Improvement: 75.0%
Mistake Prevention Rate: 90.0%
ROI: 4.25x
```

---

## Example 6: Dependency Analysis

### Analyzing Project Dependencies

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Get dependency analysis
analysis = bridge.get_dependency_analysis("cortex")
print(f"Files analyzed: {analysis['files_analyzed']}")
print(f"External dependencies: {len(analysis['external_deps'])}")
print(f"Top dependencies: {', '.join(analysis['external_deps'][:5])}")

# Check dependency health
health = bridge.get_dependency_health("cortex")
print(f"\nDependency Health Score: {health['total_score']}/100")
print(f"Assessment: {health['assessment']}")

# Find circular dependencies
circular = bridge.find_circular_dependencies("cortex")
if circular['has_cycles']:
    print(f"\nCircular Dependencies: {circular['cycle_count']}")
    for cycle in circular['cycles']:
        print(f"  Cycle: {' -> '.join(cycle)}")

# Export dependency graph
graph = bridge.export_dependency_graph("cortex", format="mermaid")
print(f"\nDependency Graph (Mermaid):")
print(graph['graph'][:500] + "...")
```

**Output**:
```
Files analyzed: 103
External dependencies: 15
Top dependencies: anthropic, fastapi, structlog, rich, PyYAML

Dependency Health Score: 85/100
Assessment: good

Circular Dependencies: 0

Dependency Graph (Mermaid):
flowchart TD
  Bridge[bridge] --> Portfolio[portfolio_memory]
  Bridge --> Session[session_manager]
  Bridge --> SpecKB[spec_knowledge_base]
  ...
```

---

## Example 7: Unified Intelligence Query

### Getting Complete Intelligence

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Query unified intelligence
result = bridge.query_intelligence(
    "implement API rate limiting",
    project="cortex",
    query_type="impl"
)

print(f"Query Time: {result['query_time_ms']:.1f}ms")
print(f"Sources Queried: {', '.join(result['sources_queried'])}")

print(f"\nSimilar Work: {len(result['similar_work'])}")
for work in result['similar_work'][:3]:
    print(f"  - {work['title']} (similarity: {work['similarity_score']:.2f})")

print(f"\nApplicable Patterns: {len(result['applicable_patterns'])}")
for pattern in result['applicable_patterns'][:3]:
    print(f"  - {pattern['name']}: {pattern['description']}")

print(f"\nLessons: {len(result['lessons'])}")
for lesson in result['lessons'][:3]:
    print(f"  - {lesson['title']}: {lesson['prevention']}")

print(f"\nRecommendations: {len(result['recommendations'])}")
for rec in result['recommendations'][:3]:
    print(f"  - {rec['title']}: {rec['rationale']}")
```

**Output**:
```
Query Time: 245.3ms
Sources Queried: spec_knowledge_base, portfolio_memory, session_manager

Similar Work: 5
  - API_RATE_LIMITING.md (similarity: 0.92)
  - SECURITY_GUIDE.md (similarity: 0.85)
  - DEPLOYMENT.md (similarity: 0.78)

Applicable Patterns: 2
  - Async FastAPI Pattern: Async endpoints with proper error handling
  - Security Pattern: Input validation and rate limiting

Lessons: 3
  - Always add rate limiting: Prevents abuse and ensures fair usage
  - Validate input: Prevents injection attacks
  - Use environment variables: Never hardcode API keys

Recommendations: 2
  - Implement rate limiting: High priority security feature
  - Add monitoring: Track rate limit violations
```

---

## Example 8: Automated Workflow

### CI/CD Integration

```yaml
# .github/workflows/cortex-track.yml
name: Track Cortex Metrics

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

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install Cortex
        run: |
          cd cortex
          pip install -e .

      - name: Track metrics
        run: |
          python bridge.py track --project ${{ github.repository }}

      - name: Check health
        run: |
          python bridge.py health
```

---

## Example 9: Custom Automation Script

### Morning Briefing Script

```python
#!/usr/bin/env python3
"""Morning briefing script using Cortex"""

from cortex.bridge import CortexBridge
from metrics_tracker import MetricsTracker

def morning_briefing():
    bridge = CortexBridge()
    tracker = MetricsTracker()

    print("=" * 60)
    print("MORNING BRIEFING")
    print("=" * 60)

    # Session context
    context = bridge.get_session_context()
    print(f"\nCurrent Project: {context['project']['name']}")
    print(f"Branch: {context.get('git', {}).get('branch', 'unknown')}")
    print(f"Focus: {context.get('focus', 'unknown')}")

    # Portfolio stats
    stats = bridge.get_portfolio_stats()
    print(f"\nPortfolio: {stats['total_projects']} projects")
    print(f"Active: {stats.get('active_projects', 0)} projects")

    # Metrics
    dashboard = tracker.get_dashboard(days=7)
    print(f"\nMetrics (Last 7 Days):")
    print(f"  Velocity Improvement: {dashboard.get('velocity', {}).get('improvement_pct', 0):.1f}%")
    print(f"  Mistake Prevention: {dashboard.get('mistakes', {}).get('prevention_rate', 0):.1f}%")
    print(f"  ROI: {dashboard.get('roi', {}).get('ratio', 0):.2f}x")

    # Health check
    health = bridge.get_portfolio_health_summary(days=7)
    healthy = health.get('aggregate', {}).get('healthy_projects', 0)
    at_risk = health.get('aggregate', {}).get('at_risk_projects', 0)
    print(f"\nProject Health:")
    print(f"  Healthy: {healthy}")
    print(f"  At Risk: {at_risk}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    morning_briefing()
```

---

## Example 10: Error Handling

### Robust Error Handling

```python
from cortex.bridge import CortexBridge

bridge = CortexBridge()

# Always check for errors
result = bridge.get_portfolio_stats()
if "error" in result:
    print(f"Error: {result['error']}")
    # Handle error appropriately
    return

# Use result safely
print(f"Total projects: {result['total_projects']}")

# Handle missing modules gracefully
if not bridge.spec_kb:
    print("Spec KB not available, using alternative search")
    # Use alternative method
else:
    results = bridge.search_specs("query")
    if results and "error" not in results[0]:
        print(f"Found {len(results)} results")
    else:
        print("Search failed or no results")
```

---

## Next Steps

- [Advanced Usage](advanced_usage.md) - Advanced features and customization
- [Best Practices](best_practices.md) - Optimization tips
- [API Documentation](../API.md) - Complete API reference

---

**Version**: 1.0  
**Last Updated**: 2025-12-24
