# Converx - Design Specification

**Version**: 1.0  
**Date**: January 2025  
**Status**: Design Phase  
**MVP Target**: 2-3 hours  
**Full Product Target**: 12-18 hours (post-MVP validation)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [MVP Design](#mvp-design)
3. [Future Product Vision](#future-product-vision)
4. [Technical Requirements](#technical-requirements)
5. [Testing Use Cases](#testing-use-cases)
6. [Documentation Requirements](#documentation-requirements)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

**Converx** is a strategic orchestrator that answers: "What should I do next?"

**Core Value Proposition**: Single command that combines project activity, goals, recommendations, and context into actionable next steps.

**Key Insight**: 80% of functionality already exists in the codebase. Converx is a thin orchestration layer that unifies:
- `ai_intelligence.py` - Project activity tracking
- `goal_parser.py` - Goal extraction from ACTION_PLAN.md
- `recommendation_engine.py` - Strategic recommendations
- `context_intelligence.py` - Context prediction
- `personal-ai-dataset` - Knowledge search

**MVP Philosophy**: Validate the core concept (strategist interface) before building complex features (virtual twin, scenario forecasting).

---

## MVP Design

### MVP Goal

**Single command that returns the most important next action with clear rationale.**

### MVP Scope (2-3 hours)

**What's Included**:
- ✅ CLI interface (`converx next [PROJECT]`)
- ✅ Orchestration of existing tools
- ✅ Formatted strategist output
- ✅ Project-specific filtering

**What's NOT Included** (deferred to post-MVP):
- ❌ Virtual twin simulation
- ❌ Scenario bands (optimistic/likely/conservative)
- ❌ Multi-domain Life Status Map
- ❌ Complex persistence (JSON files are fine)
- ❌ Web search integration
- ❌ Route/waypoint tracking
- ❌ Reflection/learning system

### MVP Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    converx CLI                          │
│  (converx next [PROJECT])                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ConverxOrchestrator                        │
│  - Calls ai_intelligence.py (project activity)          │
│  - Calls goal_parser.py (goals)                        │
│  - Calls recommendation_engine.py (recommendations)      │
│  - Calls context_intelligence.py (context)             │
│  - Formats output as strategist response               │
└─────────────────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Existing │  │ Existing │  │ Existing │
│  Tools   │  │  Tools   │  │  Tools   │
└──────────┘  └──────────┘  └──────────┘
```

### MVP File Structure

```
converx/
├── __init__.py              # Package initialization
├── cli.py                    # CLI entry point (argparse)
├── orchestrator.py           # Core orchestration logic
├── formatter.py              # Output formatting
├── README.md                 # Usage documentation
└── tests/
    ├── __init__.py
    ├── test_orchestrator.py  # Unit tests
    └── test_cli.py           # CLI tests
```

### MVP CLI Interface

```bash
# Get next action (global)
converx next

# Get next action for specific project
converx next vortexv2

# Get next action with context
converx next --with-context

# Get next action (JSON output)
converx next --json

# Show current state summary
converx status

# Show help
converx --help
```

### MVP Output Format

**Example Output**:
```
╔══════════════════════════════════════════════════════════╗
║              CONVERX - STRATEGIC NEXT ACTION             ║
╚══════════════════════════════════════════════════════════╝

📊 CURRENT STATE
────────────────
Active Projects: 3 (VortexV2, alpha_arena, personal-ai-dataset)
Priority A Goals: 2 pending, 1 in progress
Blockers: 1 (VortexV2: Missing sensor preprocessing)

🎯 NEXT ACTION
────────────────
[HIGH PRIORITY] Complete Block 1.2: Sensor Data Preprocessing

Why: Priority A goal from ACTION_PLAN.md. Blocks VortexV2 MVP 
completion (currently 60% complete). High commercial value (⭐⭐⭐⭐⭐).

Effort: 4-6 hours
Impact: High
Confidence: 90%

Next Steps:
  • Migrate sensor preprocessing from Vortex
  • Add outlier detection, quality scoring
  • Create API endpoint for sensor data ingestion
  • Verification: pytest tests/unit/test_sensor_preprocessing.py

Related Projects: VortexV2
Related Goals: vortexv2-mvp-completion

────────────────────────────────────────────────────────────
💡 ALTERNATIVE ACTIONS
────────────────────────────────────────────────────────────
2. [MEDIUM] Configure environment for keto-tracker (5-10 min)
3. [MEDIUM] Alpha Arena - Trading Engine Hardening (2-3 weeks)
```

### MVP Data Flow

1. **User runs**: `converx next`
2. **CLI calls**: `ConverxOrchestrator.get_next_action()`
3. **Orchestrator**:
   - Calls `ProjectScanner` (from `ai_intelligence.py`) → project activity
   - Calls `GoalParser` → goals from ACTION_PLAN.md
   - Calls `RecommendationEngine` → recommendations
   - Filters by priority/impact
   - Formats output
4. **Output**: Formatted strategist response

### MVP Success Criteria

✅ **MVP is successful if**:
1. Single command (`converx next`) returns actionable next step
2. Output is more useful than running `recommendation_engine.py` directly
3. Can focus on specific project (`converx next PROJECT`)
4. Takes <5 seconds to run
5. No new dependencies required
6. Integrates cleanly with existing tools

---

## Future Product Vision

### Vision Statement

**Converx becomes your "Strategic Co-Pilot" - a system that understands your work context, predicts what you need, and guides you toward optimal decisions across all life domains.**

### Full Product Features (Post-MVP)

#### 1. Virtual Twin System

**Concept**: Digital representation of your work state that can simulate outcomes.

**Features**:
- **State Model**: Current project status, goals, blockers, momentum
- **Outcome Simulation**: "If I do X, what happens to Y?"
- **Dependency Tracking**: How actions affect other projects/goals
- **Momentum Analysis**: Detect when you're in flow vs blocked

**Example**:
```bash
converx simulate "Complete VortexV2 Block 1.2"
# Output: Shows impact on other goals, estimated completion dates, blockers that might emerge
```

#### 2. Scenario Forecasting

**Concept**: Multiple outcome scenarios (optimistic/likely/conservative) for strategic decisions.

**Features**:
- **Optimistic Scenario**: Best-case outcomes (no blockers, high momentum)
- **Likely Scenario**: Realistic outcomes (some blockers, normal pace)
- **Conservative Scenario**: Worst-case outcomes (blockers, low momentum)
- **Confidence Bands**: Probability ranges for each scenario

**Example**:
```bash
converx forecast "VortexV2 MVP Completion"
# Output: 
# Optimistic: 2 weeks (90% confidence)
# Likely: 3-4 weeks (70% confidence)
# Conservative: 6-8 weeks (50% confidence)
```

#### 3. Multi-Domain Life Status Map

**Concept**: Visual representation of "weather" across life domains (Work, Health, Finance, Relationships).

**Features**:
- **Domain Status**: Current state of each domain (sunny/cloudy/stormy)
- **Cross-Domain Impact**: How work decisions affect other domains
- **Trend Analysis**: Is this domain improving or declining?
- **Risk Alerts**: Early warning for potential storms

**Example**:
```bash
converx weather
# Output: Visual map showing:
# Work: ☀️ Sunny (high momentum, no blockers)
# Health: ⛅ Cloudy (keto-tracker needs attention)
# Finance: ☀️ Sunny (all accounts synced)
```

#### 4. Route & Waypoint System

**Concept**: Strategic path from current state to goal completion.

**Features**:
- **Route Planning**: Optimal sequence of actions to reach goal
- **Waypoints**: Milestone markers along the route
- **Progress Tracking**: Current position on route
- **Route Optimization**: Recalculate if blockers emerge

**Example**:
```bash
converx route "VortexV2 MVP Completion"
# Output: 
# Route: 5 waypoints
# Current: Waypoint 2/5 (Sensor Preprocessing)
# Next: Waypoint 3/5 (ML Models Integration)
# ETA: 2 weeks
```

#### 5. Reflection & Learning System

**Concept**: System learns from your patterns and improves recommendations.

**Features**:
- **Pattern Recognition**: What actions lead to success?
- **Preference Learning**: Adapt to your work style
- **Momentum Detection**: Recognize when you're in flow
- **Blocker Prediction**: Anticipate blockers before they emerge

**Example**:
```bash
converx reflect
# Output: 
# Patterns detected:
# - You're most productive 13:00-20:00
# - Complex tasks work best after morning planning
# - You prefer 2-3 hour focused blocks
```

#### 6. Knowledge Integration

**Concept**: Deep integration with personal-ai-dataset for context-aware recommendations.

**Features**:
- **Context Retrieval**: Auto-load relevant knowledge for recommendations
- **Historical Patterns**: Learn from past project patterns
- **Cross-Project Insights**: "This worked in VortexV2, try it in Alpha Arena"
- **Documentation Search**: Find relevant docs automatically

**Example**:
```bash
converx next --with-knowledge
# Output: Includes relevant context from personal-ai-dataset
```

#### 7. Web Search Integration

**Concept**: Augment recommendations with external knowledge when needed.

**Features**:
- **Smart Web Search**: Only when local knowledge insufficient
- **Result Filtering**: High-quality sources only
- **Context Integration**: Merge web results with local knowledge

**Example**:
```bash
converx next --web-search
# Output: Includes relevant web results if local knowledge insufficient
```

---

## Technical Requirements

### MVP Technical Requirements

#### 1. Dependencies

**No new dependencies required** - use existing Python stdlib:
- `argparse` - CLI interface
- `pathlib` - File paths
- `typing` - Type hints
- `dataclasses` - Data structures

**Existing tool imports**:
- `ai_intelligence.py` - ProjectScanner, ProjectActivity
- `goal_parser.py` - GoalParser, Goal
- `recommendation_engine.py` - RecommendationEngine, Recommendation
- `context_intelligence.py` - ContextIntelligence, ContextPrediction

#### 2. Performance Requirements

- **Startup Time**: <1 second
- **Command Execution**: <5 seconds (including all tool calls)
- **Memory Usage**: <50MB (lightweight orchestration)

#### 3. Compatibility

- **Python**: 3.10+ (matches existing codebase)
- **OS**: macOS (primary), Linux (compatible)
- **Dependencies**: None (uses existing tools)

#### 4. Error Handling

- **Graceful Degradation**: If one tool fails, continue with others
- **Clear Error Messages**: Tell user which tool failed and why
- **Fallback Behavior**: If recommendations unavailable, show project status

#### 5. Configuration

- **Config File**: Optional `~/.converx/config.json` for preferences
- **Environment Variables**: `CONVERX_ROOT` (default: `/Users/jesse.kemp/Dev`)
- **CLI Flags**: All configuration via command-line flags

### Full Product Technical Requirements

#### 1. Persistence Layer

**MVP**: JSON files in `~/.converx/data/`
**Future**: SQLite database for:
- Historical recommendations
- User preferences
- Learning patterns
- Virtual twin state

#### 2. API Interface

**Future**: REST API for integration with other tools:
- `GET /api/v1/next-action` - Get next action
- `GET /api/v1/status` - Current state
- `POST /api/v1/simulate` - Run simulation
- `GET /api/v1/weather` - Life status map

#### 3. Web Interface

**Future**: Streamlit dashboard for:
- Visual Life Status Map
- Route visualization
- Scenario comparison
- Historical patterns

#### 4. Performance (Full Product)

- **Simulation Time**: <10 seconds for complex scenarios
- **Database Queries**: <100ms for historical lookups
- **Web Search**: <3 seconds (with caching)

---

## Testing Use Cases

### MVP Testing Use Cases

#### Test Case 1: Basic Next Action

**Given**: User runs `converx next`  
**When**: All tools available and working  
**Then**: 
- Returns top priority recommendation
- Includes rationale and next steps
- Takes <5 seconds
- Output is well-formatted

**Test Command**:
```bash
converx next
```

**Expected Output**: Formatted strategist response with top recommendation

---

#### Test Case 2: Project-Specific Next Action

**Given**: User runs `converx next vortexv2`  
**When**: VortexV2 has active goals and recommendations  
**Then**:
- Returns VortexV2-specific recommendation
- Filters out other project recommendations
- Includes project context if available

**Test Command**:
```bash
converx next vortexv2
```

**Expected Output**: VortexV2-focused recommendation

---

#### Test Case 3: Error Handling - Missing Tools

**Given**: `recommendation_engine.py` is unavailable  
**When**: User runs `converx next`  
**Then**:
- Gracefully handles missing tool
- Falls back to project status + goals
- Shows clear error message
- Still provides useful output

**Test Command**:
```bash
# Simulate missing tool
mv recommendation_engine.py recommendation_engine.py.bak
converx next
mv recommendation_engine.py.bak recommendation_engine.py
```

**Expected Output**: Project status + goals (no recommendations)

---

#### Test Case 4: Error Handling - Missing ACTION_PLAN.md

**Given**: ACTION_PLAN.md doesn't exist  
**When**: User runs `converx next`  
**Then**:
- Gracefully handles missing file
- Uses project activity only
- Shows warning message
- Still provides recommendations from activity

**Test Command**:
```bash
# Simulate missing file
mv ACTION_PLAN.md ACTION_PLAN.md.bak
converx next
mv ACTION_PLAN.md.bak ACTION_PLAN.md
```

**Expected Output**: Recommendations from project activity only

---

#### Test Case 5: JSON Output Format

**Given**: User runs `converx next --json`  
**When**: All tools available  
**Then**:
- Returns valid JSON
- Includes all recommendation fields
- Can be parsed by other tools
- Maintains same data as formatted output

**Test Command**:
```bash
converx next --json | jq .
```

**Expected Output**: Valid JSON with recommendation data

---

#### Test Case 6: Status Command

**Given**: User runs `converx status`  
**When**: Multiple projects exist  
**Then**:
- Shows current state summary
- Lists active projects
- Shows goal progress
- Identifies blockers

**Test Command**:
```bash
converx status
```

**Expected Output**: Current state summary

---

#### Test Case 7: With Context Integration

**Given**: User runs `converx next --with-context`  
**When**: personal-ai-dataset is available  
**Then**:
- Includes relevant context snippets
- Shows context source
- Limits context to relevant information
- Doesn't slow down significantly

**Test Command**:
```bash
converx next --with-context
```

**Expected Output**: Recommendation + relevant context snippets

---

#### Test Case 8: Empty State

**Given**: No active projects, no goals  
**When**: User runs `converx next`  
**Then**:
- Handles empty state gracefully
- Suggests next steps (e.g., "Check ACTION_PLAN.md")
- Doesn't crash or show errors
- Provides helpful message

**Test Command**:
```bash
# In empty test environment
converx next
```

**Expected Output**: Helpful empty state message

---

### Full Product Testing Use Cases

#### Test Case 9: Virtual Twin Simulation

**Given**: User runs `converx simulate "Complete VortexV2 Block 1.2"`  
**When**: Virtual twin system is implemented  
**Then**:
- Shows impact on other goals
- Estimates completion dates
- Identifies potential blockers
- Provides confidence scores

**Test Command**:
```bash
converx simulate "Complete VortexV2 Block 1.2"
```

---

#### Test Case 10: Scenario Forecasting

**Given**: User runs `converx forecast "VortexV2 MVP Completion"`  
**When**: Scenario system is implemented  
**Then**:
- Shows optimistic/likely/conservative scenarios
- Provides confidence bands
- Explains assumptions
- Updates based on current state

**Test Command**:
```bash
converx forecast "VortexV2 MVP Completion"
```

---

#### Test Case 11: Life Status Map

**Given**: User runs `converx weather`  
**When**: Multi-domain system is implemented  
**Then**:
- Shows status for each domain
- Identifies cross-domain impacts
- Shows trends
- Provides risk alerts

**Test Command**:
```bash
converx weather
```

---

#### Test Case 12: Route Planning

**Given**: User runs `converx route "VortexV2 MVP Completion"`  
**When**: Route system is implemented  
**Then**:
- Shows optimal action sequence
- Displays waypoints
- Tracks progress
- Recalculates if blockers emerge

**Test Command**:
```bash
converx route "VortexV2 MVP Completion"
```

---

### Integration Test Cases

#### Test Case 13: Integration with ai_intelligence.py

**Given**: Converx calls ProjectScanner  
**When**: Multiple projects exist  
**Then**:
- Correctly retrieves project activity
- Handles errors gracefully
- Maintains performance

**Test**: Unit test in `test_orchestrator.py`

---

#### Test Case 14: Integration with goal_parser.py

**Given**: Converx calls GoalParser  
**When**: ACTION_PLAN.md exists  
**Then**:
- Correctly parses goals
- Handles malformed goals
- Maintains performance

**Test**: Unit test in `test_orchestrator.py`

---

#### Test Case 15: Integration with recommendation_engine.py

**Given**: Converx calls RecommendationEngine  
**When**: Goals and activity available  
**Then**:
- Correctly generates recommendations
- Filters appropriately
- Maintains performance

**Test**: Unit test in `test_orchestrator.py`

---

### Performance Test Cases

#### Test Case 16: Performance - Fast Execution

**Given**: All tools available  
**When**: User runs `converx next`  
**Then**:
- Completes in <5 seconds
- Doesn't block on slow operations
- Shows progress if needed

**Test**: Performance test with timing

---

#### Test Case 17: Performance - Large Project Set

**Given**: 20+ projects in repository  
**When**: User runs `converx next`  
**Then**:
- Still completes in <10 seconds
- Doesn't load all projects unnecessarily
- Caches results appropriately

**Test**: Performance test with large repo

---

## Documentation Requirements

### MVP Documentation

#### 1. README.md

**Required Sections**:
- Quick Start (installation, basic usage)
- Command Reference (all CLI commands)
- Examples (common use cases)
- Integration (how it works with existing tools)
- Troubleshooting (common issues)

**Location**: `converx/README.md`

---

#### 2. CLI Help Text

**Required**: Comprehensive help for all commands:
- Command descriptions
- Argument explanations
- Example usage
- Flag descriptions

**Location**: Inline in `cli.py` (argparse help)

---

#### 3. Architecture Documentation

**Required Sections**:
- System overview
- Component diagram
- Data flow
- Integration points

**Location**: `converx/ARCHITECTURE.md` (optional for MVP, required for full product)

---

### Full Product Documentation

#### 4. User Guide

**Required Sections**:
- Getting Started
- Core Concepts (virtual twin, scenarios, status map)
- Advanced Usage
- Best Practices
- FAQ

**Location**: `converx/docs/USER_GUIDE.md`

---

#### 5. API Documentation

**Required Sections**:
- REST API reference
- Python API reference
- Authentication
- Rate limits
- Error codes

**Location**: `converx/docs/API.md`

---

#### 6. Developer Guide

**Required Sections**:
- Setup instructions
- Architecture deep dive
- Extension points
- Contributing guidelines
- Testing guide

**Location**: `converx/docs/DEVELOPER_GUIDE.md`

---

#### 7. Design Documents

**Required Sections**:
- Virtual Twin Design
- Scenario System Design
- Life Status Map Design
- Route System Design

**Location**: `converx/docs/DESIGN/`

---

## Implementation Roadmap (Aligned with OPUS_DESIGN.md)

### Phase 0: MVP (COMPLETE)

**Status**: Done  
**Effort**: 2-3 hours

**What Was Built**:
- `converx next` - Prioritized next action
- `converx status` - Current state summary
- Project filtering, JSON output, context integration
- 11 tests passing

---

## Phase 1: Status Map + Forecast Range

### Phase 1 Design

**Goal**: Add strategic framing with weather metaphors and forecast range

**Effort**: 2-3 hours

#### 1.1 Data Models

```python
# strategy/weather_map.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from datetime import datetime

class WeatherState(Enum):
    """Weather conditions for a domain."""
    CALM = "calm"                    # Low activity, no pressure
    MODERATE = "moderate_pressure"   # Normal workload
    HIGH_PRESSURE = "high_pressure"  # Deadline approaching, high activity
    STORM = "storm"                  # Critical issues, blockers, overload

@dataclass
class DomainWeather:
    """Weather state for a single domain."""
    domain: str                      # "work_code", "health", "finance", etc.
    state: WeatherState
    pressure_score: float            # 0.0 (calm) to 1.0 (storm)
    factors: List[str]               # What's contributing to the weather
    trend: str                       # "improving", "stable", "worsening"
    last_updated: datetime

@dataclass
class Nowcast:
    """Current state + next 24-72 hours."""
    weather: DomainWeather
    active_blockers: int
    in_progress_items: int
    upcoming_deadlines: List[str]
    recommended_focus: str

# strategy/scenarios.py

@dataclass
class ScenarioBand:
    """Single scenario (optimistic/likely/conservative)."""
    name: str                        # "optimistic", "likely", "conservative"
    estimated_days: int
    confidence: float                # 0.0 to 1.0
    conditions: List[str]            # What needs to be true
    risks: List[str]                 # What could derail this

@dataclass
class ScenarioForecast:
    """Complete forecast with all forecast range."""
    goal: str
    optimistic: ScenarioBand
    likely: ScenarioBand
    conservative: ScenarioBand
    current_tracking: str            # Which scenario we're on
    tracking_reason: str
```

#### 1.2 Weather Calculation Algorithm

```python
def calculate_weather(project_activity: List, goals: List, blockers: List) -> WeatherState:
    """
    Calculate weather based on:
    - Blocker count (each blocker adds 0.2 pressure)
    - Active project count (>3 active adds 0.1 per extra)
    - Goal deadline proximity (within 7 days adds 0.3)
    - Recent commit velocity (high = more pressure)
    
    Pressure Score:
    - 0.0-0.25: CALM
    - 0.25-0.5: MODERATE
    - 0.5-0.75: HIGH_PRESSURE
    - 0.75-1.0: STORM
    """
```

#### 1.3 Scenario Calculation Algorithm

```python
def calculate_scenarios(goal: Goal, current_state: Dict) -> ScenarioForecast:
    """
    Calculate forecast range based on:
    
    Optimistic:
    - Assumes: 25+ focused hours/week, no new blockers, high momentum
    - Days = base_estimate * 0.7
    - Confidence = 0.3 (30% chance)
    
    Likely:
    - Assumes: 15-20 focused hours/week, 1-2 minor blockers
    - Days = base_estimate * 1.0
    - Confidence = 0.5 (50% chance)
    
    Conservative:
    - Assumes: 10-15 focused hours/week, significant interruptions
    - Days = base_estimate * 1.5
    - Confidence = 0.2 (20% chance)
    
    Base estimate derived from:
    - Historical velocity (commits/day)
    - Remaining waypoints
    - Complexity score
    """
```

#### 1.4 New CLI Commands

```bash
converx weather                    # Show current weather for Work/Code
converx weather --all              # Show all domains
converx next --scenarios           # Include forecast range with recommendation
converx complete WAYPOINT_ID       # Mark waypoint as complete
```

#### 1.5 Files to Create

```
converx/
  strategy/
    __init__.py
    weather_map.py      # WeatherState, DomainWeather, Nowcast
    scenarios.py        # ScenarioBand, ScenarioForecast, calculations
    waypoints.py        # Waypoint tracking, completion
```

---

### Phase 1 Test Cases

#### Test Case P1.1: Weather Calculation - Calm State

**Given**: 
- 0 blockers
- 2 active projects
- No deadlines within 7 days

**When**: `converx weather` is run

**Then**:
- Weather state = CALM
- Pressure score < 0.25
- Factors list is empty or minimal

**Test**:
```python
def test_weather_calm_state():
    weather = calculate_weather(
        project_activity=[make_project(status="active") for _ in range(2)],
        goals=[],
        blockers=[]
    )
    assert weather.state == WeatherState.CALM
    assert weather.pressure_score < 0.25
```

---

#### Test Case P1.2: Weather Calculation - Storm State

**Given**:
- 4+ blockers
- 5+ active projects
- Deadline within 3 days

**When**: `converx weather` is run

**Then**:
- Weather state = STORM
- Pressure score > 0.75
- Factors list includes blockers and deadline

**Test**:
```python
def test_weather_storm_state():
    weather = calculate_weather(
        project_activity=[make_project(status="active") for _ in range(5)],
        goals=[make_goal(deadline_days=2)],
        blockers=[make_blocker() for _ in range(4)]
    )
    assert weather.state == WeatherState.STORM
    assert weather.pressure_score > 0.75
    assert "blockers" in str(weather.factors).lower()
```

---

#### Test Case P1.3: Forecast Range - All Three Present

**Given**: A goal with estimated effort of 2 weeks

**When**: `converx next --scenarios` is run

**Then**:
- Returns optimistic, likely, and conservative bands
- Optimistic < Likely < Conservative (in days)
- Confidence sums to ~1.0

**Test**:
```python
def test_scenario_bands_all_present():
    forecast = calculate_scenarios(
        goal=make_goal(effort_weeks=2),
        current_state={"velocity": 1.0}
    )
    assert forecast.optimistic.estimated_days < forecast.likely.estimated_days
    assert forecast.likely.estimated_days < forecast.conservative.estimated_days
    total_confidence = (
        forecast.optimistic.confidence +
        forecast.likely.confidence +
        forecast.conservative.confidence
    )
    assert 0.9 <= total_confidence <= 1.1
```

---

#### Test Case P1.4: Scenario Tracking - Identifies Current Trajectory

**Given**: 
- Goal with 3 forecast range
- Current velocity matches "likely" assumptions

**When**: Scenario forecast is generated

**Then**:
- `current_tracking` = "likely"
- `tracking_reason` explains why

**Test**:
```python
def test_scenario_tracking_identification():
    forecast = calculate_scenarios(
        goal=make_goal(effort_weeks=2),
        current_state={"velocity": 1.0, "blockers": 1}
    )
    assert forecast.current_tracking == "likely"
    assert "velocity" in forecast.tracking_reason.lower()
```

---

#### Test Case P1.5: Waypoint Completion

**Given**: A route with 5 waypoints, 2 completed

**When**: `converx complete WAYPOINT_3` is run

**Then**:
- Waypoint 3 marked as complete
- Progress updated to 3/5
- Next waypoint identified

**Test**:
```python
def test_waypoint_completion():
    route = make_route(total_waypoints=5, completed=2)
    result = complete_waypoint(route, "WAYPOINT_3")
    assert result.completed_count == 3
    assert result.next_waypoint == "WAYPOINT_4"
```

---

#### Test Case P1.6: Weather Trend Detection

**Given**: Historical weather data showing increasing pressure over 3 days

**When**: `converx weather` is run

**Then**:
- `trend` = "worsening"
- Factors include trend analysis

**Test**:
```python
def test_weather_trend_worsening():
    history = [
        make_weather(days_ago=3, pressure=0.3),
        make_weather(days_ago=2, pressure=0.5),
        make_weather(days_ago=1, pressure=0.7),
    ]
    weather = calculate_weather_with_history(history)
    assert weather.trend == "worsening"
```

---

#### Test Case P1.7: Weather Output Formatting

**Given**: Weather state = HIGH_PRESSURE

**When**: `converx weather` is run

**Then**:
- Output uses weather metaphor ("High Pressure")
- Shows pressure factors
- Shows trend

**Expected Output**:
```
LIFE WEATHER MAP - Work/Code
-----------------------------
Weather: High Pressure
Pressure Score: 0.65/1.0
Trend: Stable

Factors:
  - 3 active blockers
  - Deadline in 5 days (VortexV2 MVP)
  - High commit velocity (12/week)

Nowcast (next 72h):
  Focus on clearing blockers before deadline
```

---

## Phase 2: Routes & Multi-Domain

### Phase 2 Design

**Goal**: Move from flat recommendations to route-based planning with multi-domain awareness

**Effort**: 4-6 hours

#### 2.1 Data Models

```python
# strategy/model.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class WaypointStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"

@dataclass
class Waypoint:
    """Single step on a route."""
    id: str
    title: str
    description: str
    estimated_hours: float
    status: WaypointStatus = WaypointStatus.PENDING
    
    # Conditions
    entry_conditions: List[str] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Waypoint IDs
    blocks: List[str] = field(default_factory=list)       # Waypoint IDs
    
    # Cross-domain impacts
    domain_impacts: Dict[str, str] = field(default_factory=dict)
    # e.g., {"health": "High focus may reduce sleep"}
    
    # Tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_hours: Optional[float] = None

@dataclass
class Route:
    """Ordered sequence of waypoints toward a goal."""
    id: str
    goal: str
    domain: str
    waypoints: List[Waypoint]
    created_at: datetime
    
    # Scenario bands
    optimistic_days: int
    likely_days: int
    conservative_days: int
    
    # Progress
    @property
    def completed_count(self) -> int:
        return sum(1 for w in self.waypoints if w.status == WaypointStatus.COMPLETED)
    
    @property
    def progress_percent(self) -> float:
        return (self.completed_count / len(self.waypoints)) * 100
    
    @property
    def current_waypoint(self) -> Optional[Waypoint]:
        for w in self.waypoints:
            if w.status == WaypointStatus.IN_PROGRESS:
                return w
        for w in self.waypoints:
            if w.status == WaypointStatus.PENDING:
                return w
        return None

# strategy/domains.py

class Domain(Enum):
    WORK_CODE = "work_code"
    FINANCE = "finance"
    HEALTH = "health"
    LEARNING = "learning"
    RELATIONSHIPS = "relationships"

@dataclass
class DomainState:
    """Complete state for a domain."""
    domain: Domain
    weather: DomainWeather
    active_routes: List[Route]
    blockers: List[str]
    
    # Cross-domain
    impacts_from: Dict[Domain, str] = field(default_factory=dict)
    impacts_to: Dict[Domain, str] = field(default_factory=dict)

@dataclass
class LifeWeatherMap:
    """Complete multi-domain view."""
    domains: Dict[Domain, DomainState]
    cross_domain_alerts: List[str]
    overall_pressure: float
    recommended_focus: Domain
```

#### 2.2 Route Planning Algorithm

```python
def create_route(goal: str, domain: Domain, context: Dict) -> Route:
    """
    Create a route from goal to completion.
    
    Algorithm:
    1. Parse goal to identify scope
    2. Break into logical waypoints (3-7 typically)
    3. Identify dependencies between waypoints
    4. Estimate hours per waypoint
    5. Calculate forecast range
    6. Identify cross-domain impacts
    
    Waypoint generation:
    - If goal references existing blocks (from ACTION_PLAN.md), use those
    - Otherwise, use AI to suggest logical breakdown
    - Each waypoint should be 2-8 hours of work
    """

def calculate_route_scenarios(route: Route, velocity: float) -> Dict:
    """
    Calculate forecast range for entire route.
    
    Inputs:
    - Total remaining hours
    - Current velocity (hours completed per day)
    - Historical accuracy (actual vs estimated)
    - Current blockers
    
    Outputs:
    - Optimistic/Likely/Conservative days
    - Conditions for each scenario
    """
```

#### 2.3 Cross-Domain Impact Detection

```python
def detect_cross_domain_impacts(action: str, domain: Domain) -> Dict[Domain, str]:
    """
    Detect how an action in one domain affects others.
    
    Rules:
    - "60-hour week" in WORK_CODE -> HEALTH: "Risk of burnout, reduced sleep"
    - "Major expense" in FINANCE -> WORK_CODE: "May increase pressure"
    - "Skip exercise" in HEALTH -> WORK_CODE: "May reduce energy/focus"
    - "Deadline crunch" in WORK_CODE -> RELATIONSHIPS: "Less time available"
    
    Returns dict of affected domains and impact descriptions.
    """
```

#### 2.4 New CLI Commands

```bash
converx route "Ship VortexV2 MVP"    # Create/view route
converx route --list                  # List all active routes
converx route ROUTE_ID --detail       # Detailed route view
converx forecast ROUTE_ID             # Scenario forecast for route
converx domains                       # Show all domain weather
converx domains work_code             # Show specific domain
```

#### 2.5 Files to Create

```
converx/
  strategy/
    model.py            # Waypoint, Route dataclasses
    domains.py          # Domain, DomainState, LifeWeatherMap
    route_planner.py    # Route creation and planning
    cross_domain.py     # Cross-domain impact detection
```

---

### Phase 2 Test Cases

#### Test Case P2.1: Route Creation from Goal

**Given**: Goal "Ship VortexV2 MVP in 3 weeks"

**When**: `converx route "Ship VortexV2 MVP"` is run

**Then**:
- Creates route with 3-7 waypoints
- Each waypoint has entry/exit conditions
- Scenario bands are calculated
- Route is persisted

**Test**:
```python
def test_route_creation():
    route = create_route(
        goal="Ship VortexV2 MVP",
        domain=Domain.WORK_CODE,
        context={"existing_blocks": ["Block 1.4", "Block 1.5"]}
    )
    assert 3 <= len(route.waypoints) <= 7
    assert all(w.entry_conditions for w in route.waypoints)
    assert route.optimistic_days < route.likely_days < route.conservative_days
```

---

#### Test Case P2.2: Waypoint Dependencies

**Given**: Route with waypoints A -> B -> C (B depends on A)

**When**: Trying to start waypoint B before A is complete

**Then**:
- Returns error/warning
- Shows unmet entry conditions
- Suggests completing A first

**Test**:
```python
def test_waypoint_dependency_enforcement():
    route = make_route_with_dependencies()
    result = start_waypoint(route, "waypoint_b")
    assert result.blocked == True
    assert "waypoint_a" in result.unmet_dependencies
```

---

#### Test Case P2.3: Route Progress Tracking

**Given**: Route with 5 waypoints, 2 completed, 1 in progress

**When**: `converx route ROUTE_ID` is run

**Then**:
- Shows 40% progress (2/5)
- Current waypoint highlighted
- Remaining waypoints listed
- Updated scenario estimates

**Test**:
```python
def test_route_progress():
    route = make_route(total=5, completed=2, in_progress=1)
    assert route.progress_percent == 40.0
    assert route.current_waypoint.status == WaypointStatus.IN_PROGRESS
```

---

#### Test Case P2.4: Cross-Domain Impact Detection

**Given**: Action "Push 60-hour week on VortexV2"

**When**: Cross-domain impact is calculated

**Then**:
- Detects HEALTH impact: "Risk of burnout"
- Detects RELATIONSHIPS impact: "Less time available"
- Adds to alerts

**Test**:
```python
def test_cross_domain_impact():
    impacts = detect_cross_domain_impacts(
        action="Push 60-hour week",
        domain=Domain.WORK_CODE
    )
    assert Domain.HEALTH in impacts
    assert "burnout" in impacts[Domain.HEALTH].lower()
```

---

#### Test Case P2.5: Multi-Domain Weather View

**Given**: 3 domains configured (Work, Health, Finance)

**When**: `converx domains` is run

**Then**:
- Shows weather for each domain
- Shows cross-domain alerts
- Shows recommended focus domain

**Expected Output**:
```
LIFE WEATHER MAP - All Domains
================================

Work/Code:    High Pressure  [======|    ] 65%
Health:       Calm           [==|        ] 20%
Finance:      Moderate       [====|      ] 45%

Cross-Domain Alerts:
  - Work pressure may impact Health (sleep)
  
Recommended Focus: Work/Code (highest pressure, deadline in 5d)
```

---

#### Test Case P2.6: Route Scenario Update on Progress

**Given**: Route with likely completion in 14 days, 50% complete

**When**: Velocity is higher than expected

**Then**:
- Scenarios recalculated
- Now tracking "optimistic"
- Days reduced

**Test**:
```python
def test_scenario_update_on_progress():
    route = make_route(likely_days=14, completed_percent=50)
    updated = recalculate_scenarios(route, actual_velocity=1.5)  # 50% faster
    assert updated.current_tracking == "optimistic"
    assert updated.likely_days < 14
```

---

## Phase 3: Deep Integrations

### Phase 3 Design

**Goal**: Connect to real data sources across all domains

**Effort**: 6-8 hours

#### 3.1 Connector Interface

```python
# knowledge/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class DataPoint:
    """Single data point from any connector."""
    source: str                    # "github", "google_fit", etc.
    domain: Domain
    timestamp: datetime
    data_type: str                 # "commits", "heart_rate", "balance"
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchResult:
    """Search result from knowledge layer."""
    source: str
    title: str
    snippet: str
    relevance: float               # 0.0 to 1.0
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class Connector(ABC):
    """Base class for all data connectors."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name."""
        pass
    
    @property
    @abstractmethod
    def domain(self) -> Domain:
        """Primary domain this connector serves."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if connector is configured and available."""
        pass
    
    @abstractmethod
    def fetch_recent(self, days: int = 7) -> List[DataPoint]:
        """Fetch recent data points."""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Search within this data source."""
        pass
```

#### 3.2 Connector Implementations

```python
# knowledge/github.py

class GitHubConnector(Connector):
    """GitHub integration for Work/Code domain."""
    
    name = "github"
    domain = Domain.WORK_CODE
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.client = Github(self.token) if self.token else None
    
    def fetch_recent(self, days: int = 7) -> List[DataPoint]:
        """
        Fetch:
        - Recent commits across repos
        - Open issues/PRs
        - Review requests
        - Notifications
        """
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Search code, issues, PRs."""

# knowledge/google_fit.py

class GoogleFitConnector(Connector):
    """Google Fit integration for Health domain."""
    
    name = "google_fit"
    domain = Domain.HEALTH
    
    def fetch_recent(self, days: int = 7) -> List[DataPoint]:
        """
        Fetch from Pixel Watch / Google Fit:
        - Steps (daily)
        - Heart rate (avg, resting, max)
        - Sleep duration and quality
        - Workouts
        - Stress/HRV if available
        """

# knowledge/personal_ai.py

class PersonalAIConnector(Connector):
    """personal-ai-dataset integration."""
    
    name = "personal_ai"
    domain = Domain.WORK_CODE  # Primary, but searches all
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        Search 911 documents:
        - Full-text search
        - Category filtering
        - Quality filtering
        """

# knowledge/alpha_arena.py

class AlphaArenaConnector(Connector):
    """Alpha Arena integration for Finance domain."""
    
    name = "alpha_arena"
    domain = Domain.FINANCE
    
    def fetch_recent(self, days: int = 7) -> List[DataPoint]:
        """
        Fetch:
        - Portfolio value
        - Recent trades
        - Model performance
        - P&L
        """
```

#### 3.3 Knowledge Aggregator

```python
# knowledge/aggregator.py

class KnowledgeAggregator:
    """Aggregates data from all connectors."""
    
    def __init__(self):
        self.connectors: Dict[str, Connector] = {}
        self._register_available_connectors()
    
    def search_all(self, query: str, domains: List[Domain] = None) -> List[SearchResult]:
        """Search across all relevant connectors."""
    
    def get_domain_data(self, domain: Domain, days: int = 7) -> List[DataPoint]:
        """Get all recent data for a domain."""
    
    def get_cross_domain_summary(self) -> Dict[Domain, Dict]:
        """Summary of all domains for status map."""
```

#### 3.4 New CLI Commands

```bash
converx connectors                    # List available connectors
converx connectors --status           # Show connector health
converx search "query"                # Search across all sources
converx search "query" --domain work  # Search specific domain
converx sync                          # Refresh all connector data
```

---

### Phase 3 Test Cases

#### Test Case P3.1: Connector Registration

**Given**: GitHub token is configured

**When**: Converx initializes

**Then**:
- GitHubConnector is registered
- `is_available()` returns True
- Listed in `converx connectors`

**Test**:
```python
def test_connector_registration():
    aggregator = KnowledgeAggregator()
    assert "github" in aggregator.connectors
    assert aggregator.connectors["github"].is_available()
```

---

#### Test Case P3.2: Graceful Degradation - Missing Connector

**Given**: Google Fit not configured (no OAuth)

**When**: `converx domains health` is run

**Then**:
- Shows warning about missing data
- Uses available data only
- Doesn't crash

**Test**:
```python
def test_missing_connector_graceful():
    aggregator = KnowledgeAggregator()
    # Simulate missing Google Fit
    del aggregator.connectors["google_fit"]
    
    result = aggregator.get_domain_data(Domain.HEALTH)
    assert result is not None  # Empty but not error
```

---

#### Test Case P3.3: GitHub Data Fetching

**Given**: GitHub connector configured with valid token

**When**: `fetch_recent(days=7)` is called

**Then**:
- Returns commits, issues, PRs from last 7 days
- Each DataPoint has correct structure
- Respects rate limits

**Test**:
```python
def test_github_fetch_recent():
    connector = GitHubConnector(token=TEST_TOKEN)
    data = connector.fetch_recent(days=7)
    
    assert len(data) > 0
    assert all(d.source == "github" for d in data)
    assert all(d.domain == Domain.WORK_CODE for d in data)
```

---

#### Test Case P3.4: Cross-Source Search

**Given**: Query "VortexV2 forecasting"

**When**: `converx search "VortexV2 forecasting"` is run

**Then**:
- Searches GitHub (code, issues)
- Searches personal-ai-dataset
- Results ranked by relevance
- Sources clearly labeled

**Test**:
```python
def test_cross_source_search():
    aggregator = KnowledgeAggregator()
    results = aggregator.search_all("VortexV2 forecasting")
    
    sources = set(r.source for r in results)
    assert len(sources) > 1  # Multiple sources
    assert results[0].relevance >= results[-1].relevance  # Sorted
```

---

#### Test Case P3.5: Health Data Integration

**Given**: Google Fit configured with last 7 days of data

**When**: Health domain weather is calculated

**Then**:
- Uses actual sleep data
- Uses actual steps/activity
- Weather reflects real health state

**Test**:
```python
def test_health_weather_from_real_data():
    connector = GoogleFitConnector()
    data = connector.fetch_recent(days=7)
    
    weather = calculate_health_weather(data)
    
    # If sleep avg < 6h, should show pressure
    avg_sleep = get_avg_sleep(data)
    if avg_sleep < 6:
        assert weather.state in [WeatherState.HIGH_PRESSURE, WeatherState.STORM]
```

---

#### Test Case P3.6: Connector Health Check

**Given**: Multiple connectors configured

**When**: `converx connectors --status` is run

**Then**:
- Shows each connector name
- Shows availability status
- Shows last sync time
- Shows any errors

**Expected Output**:
```
CONNECTORS STATUS
=================
github        [OK]     Last sync: 2 min ago
google_fit    [OK]     Last sync: 1 hour ago
personal_ai   [OK]     Last sync: 5 min ago
alpha_arena   [WARN]   Not configured (missing API key)
```

---

## Phase 4: Playbooks & Executor

### Phase 4 Design

**Goal**: Semi-autonomous execution with policy-driven safety

**Effort**: 4-6 hours

#### 4.1 Data Models

```python
# playbooks/base.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

class PlaybookStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"

class ApprovalLevel(Enum):
    NONE = "none"                  # Auto-execute
    NOTIFY = "notify"              # Execute and notify
    CONFIRM = "confirm"            # Require confirmation
    STRICT = "strict"              # Require explicit approval + reason

@dataclass
class PlaybookStep:
    """Single step in a playbook."""
    id: str
    name: str
    action: str                    # Function/command to execute
    parameters: Dict[str, Any]
    approval_level: ApprovalLevel
    rollback_action: Optional[str] = None
    timeout_seconds: int = 300

@dataclass
class Playbook:
    """Declarative action template."""
    id: str
    name: str
    description: str
    domain: Domain
    
    steps: List[PlaybookStep]
    
    # Inputs/outputs
    required_inputs: List[str]
    outputs: List[str]
    
    # Safety
    side_effects: List[str]
    default_approval: ApprovalLevel
    
    # Scheduling
    can_schedule: bool = False
    recommended_frequency: Optional[str] = None  # "daily", "weekly"

@dataclass
class PlaybookExecution:
    """Record of a playbook execution."""
    id: str
    playbook_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: PlaybookStatus
    
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    
    step_results: List[Dict]
    error: Optional[str] = None

# playbooks/policies.py

@dataclass
class Policy:
    """Execution policy for a domain/action type."""
    domain: Domain
    action_pattern: str            # Regex for action matching
    approval_level: ApprovalLevel
    
    # Limits
    max_daily_executions: int = 10
    max_cost_usd: float = 0.0      # For API calls
    
    # Time windows
    allowed_hours: List[int] = field(default_factory=lambda: list(range(24)))
    blocked_days: List[int] = field(default_factory=list)  # 0=Mon, 6=Sun

class PolicyEngine:
    """Evaluates whether an action can proceed."""
    
    def __init__(self, policies: List[Policy]):
        self.policies = policies
    
    def can_execute(self, action: str, domain: Domain) -> Tuple[bool, str]:
        """Check if action can execute. Returns (allowed, reason)."""
    
    def get_approval_level(self, action: str, domain: Domain) -> ApprovalLevel:
        """Get required approval level for action."""
```

#### 4.2 Built-in Playbooks

```python
# playbooks/builtin.py

ANALYZE_REPO = Playbook(
    id="analyze_repo",
    name="Analyze Repository",
    description="Run tests, check coverage, summarize risks",
    domain=Domain.WORK_CODE,
    steps=[
        PlaybookStep(
            id="run_tests",
            name="Run Tests",
            action="shell:pytest tests/ -v",
            parameters={},
            approval_level=ApprovalLevel.NONE
        ),
        PlaybookStep(
            id="check_coverage",
            name="Check Coverage",
            action="shell:pytest --cov=src --cov-report=term",
            parameters={},
            approval_level=ApprovalLevel.NONE
        ),
        PlaybookStep(
            id="summarize",
            name="Summarize Risks",
            action="ai:summarize_test_results",
            parameters={"input": "step:run_tests.output"},
            approval_level=ApprovalLevel.NONE
        )
    ],
    required_inputs=["repo_path"],
    outputs=["test_results", "coverage_percent", "risk_summary"],
    side_effects=["None - read only"],
    default_approval=ApprovalLevel.NONE
)

WEEKLY_HEALTH_REVIEW = Playbook(
    id="weekly_health_review",
    name="Weekly Health Review",
    description="Aggregate health data and generate insights",
    domain=Domain.HEALTH,
    steps=[
        PlaybookStep(
            id="fetch_data",
            name="Fetch Health Data",
            action="connector:google_fit.fetch_recent",
            parameters={"days": 7},
            approval_level=ApprovalLevel.NONE
        ),
        PlaybookStep(
            id="analyze",
            name="Analyze Patterns",
            action="ai:analyze_health_patterns",
            parameters={"data": "step:fetch_data.output"},
            approval_level=ApprovalLevel.NONE
        ),
        PlaybookStep(
            id="recommend",
            name="Generate Recommendations",
            action="ai:health_recommendations",
            parameters={"analysis": "step:analyze.output"},
            approval_level=ApprovalLevel.NOTIFY
        )
    ],
    required_inputs=[],
    outputs=["health_summary", "recommendations"],
    side_effects=["None - read only"],
    default_approval=ApprovalLevel.NONE,
    can_schedule=True,
    recommended_frequency="weekly"
)
```

#### 4.3 Executor Engine

```python
# playbooks/executor.py

class PlaybookExecutor:
    """Executes playbooks with policy enforcement."""
    
    def __init__(self, policy_engine: PolicyEngine):
        self.policy_engine = policy_engine
        self.executions: Dict[str, PlaybookExecution] = {}
    
    async def execute(
        self,
        playbook: Playbook,
        inputs: Dict[str, Any],
        approval_callback: Optional[Callable] = None
    ) -> PlaybookExecution:
        """
        Execute a playbook.
        
        1. Validate inputs
        2. Check policy for each step
        3. Request approval if needed
        4. Execute steps sequentially
        5. Handle errors and rollbacks
        6. Record execution
        """
    
    def _execute_step(self, step: PlaybookStep, context: Dict) -> Dict:
        """Execute a single step."""
        
        if step.action.startswith("shell:"):
            return self._execute_shell(step.action[6:], context)
        elif step.action.startswith("ai:"):
            return self._execute_ai(step.action[3:], step.parameters, context)
        elif step.action.startswith("connector:"):
            return self._execute_connector(step.action[10:], step.parameters, context)
```

#### 4.4 New CLI Commands

```bash
converx playbooks                     # List available playbooks
converx run analyze_repo              # Run a playbook
converx run analyze_repo --dry-run    # Show what would execute
converx executions                    # List recent executions
converx executions EXEC_ID            # Show execution details
converx policies                      # Show current policies
converx approve EXEC_ID               # Approve pending execution
```

---

### Phase 4 Test Cases

#### Test Case P4.1: Playbook Execution - Happy Path

**Given**: "analyze_repo" playbook, valid repo path

**When**: `converx run analyze_repo` is executed

**Then**:
- All steps execute in order
- Test results captured
- Coverage captured
- Summary generated
- Execution recorded

**Test**:
```python
async def test_playbook_execution_happy_path():
    executor = PlaybookExecutor(PolicyEngine([]))
    result = await executor.execute(
        playbook=ANALYZE_REPO,
        inputs={"repo_path": "/path/to/repo"}
    )
    
    assert result.status == PlaybookStatus.COMPLETED
    assert "test_results" in result.outputs
    assert "coverage_percent" in result.outputs
```

---

#### Test Case P4.2: Policy Enforcement - Approval Required

**Given**: Policy requiring CONFIRM for shell commands

**When**: Playbook with shell step is run

**Then**:
- Execution pauses at step
- Status = AWAITING_APPROVAL
- Approval callback invoked

**Test**:
```python
async def test_policy_requires_approval():
    policy = Policy(
        domain=Domain.WORK_CODE,
        action_pattern="shell:.*",
        approval_level=ApprovalLevel.CONFIRM
    )
    executor = PlaybookExecutor(PolicyEngine([policy]))
    
    approvals_requested = []
    async def approval_callback(step):
        approvals_requested.append(step)
        return True
    
    result = await executor.execute(
        playbook=ANALYZE_REPO,
        inputs={"repo_path": "/path/to/repo"},
        approval_callback=approval_callback
    )
    
    assert len(approvals_requested) > 0
```

---

#### Test Case P4.3: Execution Rollback on Failure

**Given**: Playbook with step that fails, rollback defined

**When**: Step fails during execution

**Then**:
- Rollback action executed
- Status = FAILED
- Error recorded
- Previous steps' outputs preserved

**Test**:
```python
async def test_execution_rollback():
    playbook = make_playbook_with_rollback()
    executor = PlaybookExecutor(PolicyEngine([]))
    
    # Inject failure
    result = await executor.execute(
        playbook=playbook,
        inputs={"should_fail": True}
    )
    
    assert result.status == PlaybookStatus.FAILED
    assert result.error is not None
    assert result.step_results[-1]["rollback_executed"] == True
```

---

#### Test Case P4.4: Daily Execution Limit

**Given**: Policy with max_daily_executions = 3

**When**: 4th execution attempted in same day

**Then**:
- Execution blocked
- Returns reason: "Daily limit exceeded"

**Test**:
```python
async def test_daily_execution_limit():
    policy = Policy(
        domain=Domain.WORK_CODE,
        action_pattern=".*",
        approval_level=ApprovalLevel.NONE,
        max_daily_executions=3
    )
    engine = PolicyEngine([policy])
    
    # Execute 3 times
    for _ in range(3):
        allowed, _ = engine.can_execute("test", Domain.WORK_CODE)
        assert allowed
        engine.record_execution("test", Domain.WORK_CODE)
    
    # 4th should fail
    allowed, reason = engine.can_execute("test", Domain.WORK_CODE)
    assert not allowed
    assert "limit" in reason.lower()
```

---

#### Test Case P4.5: Dry Run Mode

**Given**: Any playbook

**When**: `converx run PLAYBOOK --dry-run` is executed

**Then**:
- Shows all steps that would execute
- Shows approval requirements
- No actual execution
- No side effects

**Test**:
```python
def test_dry_run_mode():
    executor = PlaybookExecutor(PolicyEngine([]))
    preview = executor.preview(playbook=ANALYZE_REPO, inputs={"repo_path": "/test"})
    
    assert preview["would_execute"] == True
    assert len(preview["steps"]) == 3
    assert preview["approvals_required"] == 0
    assert preview["side_effects"] == ["None - read only"]
```

---

## Phase 5: Virtual Twin + Advanced Learning

### Phase 5 Design

**Goal**: Predictive simulation and learned optimization

**Effort**: 8-12 hours

#### 5.1 Data Models

```python
# twin/state.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class TwinState:
    """Complete state of the virtual twin."""
    timestamp: datetime
    
    # Work domain
    focus_hours_per_week: float          # 0-60
    active_projects: int
    blockers: int
    momentum: float                       # 0.0 (stalled) to 1.0 (high velocity)
    
    # Health domain
    energy_level: float                   # 0.0 to 1.0
    sleep_quality: float                  # 0.0 to 1.0
    burnout_risk: float                   # 0.0 to 1.0
    stress_level: float                   # 0.0 to 1.0
    
    # Finance domain
    runway_months: float
    monthly_burn: float
    income_stability: float               # 0.0 to 1.0
    
    # Meta
    overall_capacity: float               # Derived: ability to take on more
    risk_tolerance: float                 # User setting
    
    @classmethod
    def from_observations(cls, data: Dict[str, List[DataPoint]]) -> "TwinState":
        """Create state from real observations."""

# twin/transitions.py

@dataclass
class Transition:
    """Rule for how an action changes state."""
    action: str                           # "push_hard", "rest", "cut_scope"
    
    # State changes (deltas)
    focus_hours_delta: float = 0
    energy_delta: float = 0
    burnout_risk_delta: float = 0
    momentum_delta: float = 0
    
    # Conditions
    min_energy: float = 0                 # Required to execute
    max_burnout: float = 1.0              # Max burnout to execute
    
    # Uncertainty
    variance: float = 0.1                 # How much actual differs from predicted

class TransitionModel:
    """Collection of transition rules."""
    
    def __init__(self):
        self.rules: Dict[str, Transition] = self._load_default_rules()
        self.learned_adjustments: Dict[str, float] = {}
    
    def apply(self, state: TwinState, action: str) -> TwinState:
        """Apply action to state, return new state."""
    
    def learn_from_outcome(
        self,
        predicted: TwinState,
        actual: TwinState,
        action: str
    ):
        """Update rules based on prediction error."""

# twin/simulation.py

@dataclass
class SimulationResult:
    """Result of forward simulation."""
    route_id: str
    horizon_days: int
    
    # Scenario outcomes
    optimistic: TwinState
    likely: TwinState
    conservative: TwinState
    
    # Probabilities
    optimistic_probability: float
    likely_probability: float
    conservative_probability: float
    
    # Risks identified
    burnout_risk_days: Optional[int]      # Day when burnout > 0.8
    energy_crash_days: Optional[int]      # Day when energy < 0.2
    
    # Monte Carlo details (if run)
    num_simulations: int
    confidence_interval: Tuple[float, float]  # 95% CI for completion

class Simulator:
    """Runs forward simulations."""
    
    def __init__(self, transition_model: TransitionModel):
        self.transition_model = transition_model
    
    def simulate_route(
        self,
        route: Route,
        initial_state: TwinState,
        horizon_days: int = 30
    ) -> SimulationResult:
        """Simulate route completion under different scenarios."""
    
    def monte_carlo(
        self,
        route: Route,
        initial_state: TwinState,
        num_simulations: int = 1000
    ) -> SimulationResult:
        """Run Monte Carlo simulation for probability distribution."""
```

#### 5.2 Learning System

```python
# memory/reflection.py

@dataclass
class PredictionRecord:
    """Record of a prediction for later comparison."""
    id: str
    timestamp: datetime
    
    # What was predicted
    prediction_type: str              # "route_completion", "weather", "scenario"
    predicted_value: Any
    confidence: float
    
    # Context at prediction time
    state_snapshot: TwinState
    route_snapshot: Optional[Route]
    
    # Actual outcome (filled in later)
    actual_value: Optional[Any] = None
    actual_timestamp: Optional[datetime] = None
    error: Optional[float] = None

class ReflectionEngine:
    """Compares predictions to actuals and learns."""
    
    def __init__(self, transition_model: TransitionModel):
        self.transition_model = transition_model
        self.records: List[PredictionRecord] = []
    
    def record_prediction(self, prediction: PredictionRecord):
        """Store prediction for later comparison."""
    
    def record_actual(self, prediction_id: str, actual: Any):
        """Record actual outcome."""
    
    def reflect(self) -> Dict:
        """
        Analyze prediction accuracy and update models.
        
        Returns:
        - Overall accuracy metrics
        - Systematic biases detected
        - Suggested model adjustments
        """
    
    def get_calibration_score(self) -> float:
        """How well-calibrated are predictions? 1.0 = perfect."""
```

#### 5.3 New CLI Commands

```bash
converx simulate ROUTE_ID             # Simulate route outcomes
converx simulate ROUTE_ID --monte-carlo  # Full probabilistic simulation
converx twin                          # Show current twin state
converx twin --history                # Show state over time
converx reflect                       # Run reflection analysis
converx reflect --predictions         # Show prediction accuracy
converx calibrate                     # Recalibrate models from data
```

---

### Phase 5 Test Cases

#### Test Case P5.1: State from Observations

**Given**: Real data from connectors (commits, sleep, etc.)

**When**: `TwinState.from_observations(data)` is called

**Then**:
- State reflects actual data
- Missing data handled with defaults
- Values in valid ranges

**Test**:
```python
def test_state_from_observations():
    data = {
        "github": [make_commits(count=20, days=7)],
        "google_fit": [make_sleep(avg_hours=7, days=7)]
    }
    state = TwinState.from_observations(data)
    
    assert 0 <= state.focus_hours_per_week <= 60
    assert 0 <= state.energy_level <= 1.0
    assert 0 <= state.burnout_risk <= 1.0
```

---

#### Test Case P5.2: Transition Application

**Given**: State with energy=0.8, burnout_risk=0.3

**When**: Action "push_hard" is applied (energy-0.2, burnout+0.2)

**Then**:
- New energy = 0.6
- New burnout_risk = 0.5
- Other values unchanged

**Test**:
```python
def test_transition_application():
    state = TwinState(energy_level=0.8, burnout_risk=0.3, ...)
    model = TransitionModel()
    
    new_state = model.apply(state, "push_hard")
    
    assert new_state.energy_level == pytest.approx(0.6, abs=0.05)
    assert new_state.burnout_risk == pytest.approx(0.5, abs=0.05)
```

---

#### Test Case P5.3: Route Simulation - All Scenarios

**Given**: Route with 5 waypoints, current state healthy

**When**: `simulate_route(route, state, horizon=30)` is called

**Then**:
- Returns optimistic, likely, conservative outcomes
- Optimistic is best outcome
- Conservative is worst outcome
- Probabilities sum to ~1.0

**Test**:
```python
def test_route_simulation():
    route = make_route(waypoints=5)
    state = make_healthy_state()
    simulator = Simulator(TransitionModel())
    
    result = simulator.simulate_route(route, state, horizon_days=30)
    
    assert result.optimistic.momentum > result.conservative.momentum
    total_prob = (
        result.optimistic_probability +
        result.likely_probability +
        result.conservative_probability
    )
    assert 0.95 <= total_prob <= 1.05
```

---

#### Test Case P5.4: Burnout Risk Detection

**Given**: Route requiring 50 hours/week for 3 weeks

**When**: Simulation is run

**Then**:
- Detects burnout risk
- Returns day when burnout > 0.8
- Suggests mitigation

**Test**:
```python
def test_burnout_detection():
    route = make_intensive_route(hours_per_week=50)
    state = make_healthy_state()
    simulator = Simulator(TransitionModel())
    
    result = simulator.simulate_route(route, state, horizon_days=21)
    
    assert result.burnout_risk_days is not None
    assert result.burnout_risk_days < 21  # Burnout before completion
```

---

#### Test Case P5.5: Monte Carlo Confidence Intervals

**Given**: Route with significant uncertainty

**When**: `monte_carlo(route, state, num_simulations=1000)` is run

**Then**:
- Returns 95% confidence interval
- Interval width reflects uncertainty
- Mean ~= likely scenario

**Test**:
```python
def test_monte_carlo_ci():
    route = make_route(waypoints=5)
    state = make_healthy_state()
    simulator = Simulator(TransitionModel())
    
    result = simulator.monte_carlo(route, state, num_simulations=1000)
    
    assert result.num_simulations == 1000
    low, high = result.confidence_interval
    assert low < high
    assert low <= result.likely.momentum <= high
```

---

#### Test Case P5.6: Learning from Prediction Error

**Given**: Prediction: complete in 10 days. Actual: 15 days.

**When**: `reflect()` is called with this record

**Then**:
- Error calculated (5 days / 50%)
- Model adjusted to be more conservative
- Systematic bias detected if pattern repeats

**Test**:
```python
def test_learning_from_error():
    engine = ReflectionEngine(TransitionModel())
    
    # Record prediction
    pred = PredictionRecord(
        prediction_type="route_completion",
        predicted_value=10,  # days
        confidence=0.7
    )
    engine.record_prediction(pred)
    
    # Record actual
    engine.record_actual(pred.id, actual=15)
    
    # Reflect
    insights = engine.reflect()
    
    assert insights["mean_error"] == 5
    assert insights["bias"] == "optimistic"  # Consistently underestimating
```

---

#### Test Case P5.7: Calibration Score

**Given**: 100 predictions with varying accuracy

**When**: `get_calibration_score()` is called

**Then**:
- Returns score 0.0 to 1.0
- 1.0 = perfect calibration
- Score reflects prediction/actual alignment

**Test**:
```python
def test_calibration_score():
    engine = ReflectionEngine(TransitionModel())
    
    # Add 100 predictions with 80% accuracy
    for i in range(100):
        pred = make_prediction()
        engine.record_prediction(pred)
        # 80% correct
        actual = pred.predicted_value if i < 80 else pred.predicted_value * 1.5
        engine.record_actual(pred.id, actual)
    
    score = engine.get_calibration_score()
    assert 0.7 <= score <= 0.9  # ~80% accurate

---

## Success Metrics (Per Phase)

### Phase 0 (MVP) - COMPLETE
- [x] **Usage**: Used at least once per day
- [x] **Value**: Provides actionable next step
- [x] **Speed**: Completes in <5 seconds
- [x] **Reliability**: Works 95%+ of the time
- [x] **Tests**: 11/11 passing

### Phase 1 Success Metrics
- [ ] Weather metaphor improves state understanding
- [ ] Scenario bands increase confidence in decisions
- [ ] Waypoint completion tracking used regularly
- [ ] <3 seconds execution time maintained

### Phase 2 Success Metrics
- [ ] Routes replace ad-hoc task lists
- [ ] Cross-domain awareness provides useful insights
- [ ] Entry/exit conditions clarify work boundaries
- [ ] Progress visualization used weekly

### Phase 3 Success Metrics
- [ ] 3+ connectors providing real data
- [ ] Search results from multiple sources useful
- [ ] Health/Finance data improves weather accuracy
- [ ] <5 seconds for cross-source search

### Phase 4 Success Metrics
- [ ] 2+ playbooks executing reliably
- [ ] Policy engine prevents unintended actions
- [ ] Approval workflow used without friction
- [ ] Semi-autonomous mode saves >1 hour/week

### Phase 5 Success Metrics
- [ ] Predictions within 20% of actual 70% of time
- [ ] Learned model outperforms static rules
- [ ] Monte Carlo provides actionable confidence intervals
- [ ] Calibration score > 0.7

---

## Risk Assessment

### Phase 1 Risks

**Risk**: Weather metaphor doesn't resonate  
**Mitigation**: A/B test with raw numbers vs metaphor

**Risk**: Scenario bands too optimistic  
**Mitigation**: Start conservative, calibrate from data

### Phase 2 Risks

**Risk**: Route creation too complex  
**Mitigation**: Auto-generate from existing ACTION_PLAN.md blocks

**Risk**: Cross-domain impacts too noisy  
**Mitigation**: Only show high-confidence impacts initially

### Phase 3 Risks

**Risk**: OAuth setup friction for Google Fit  
**Mitigation**: Make health connector optional, provide manual input

**Risk**: API rate limits (GitHub, Google)  
**Mitigation**: Cache aggressively, batch requests

### Phase 4 Risks

**Risk**: Playbook side effects cause damage  
**Mitigation**: Strict CONFIRM approval for all write actions initially

**Risk**: Policy engine too restrictive  
**Mitigation**: Start permissive, tighten based on incidents

### Phase 5 Risks

**Risk**: Virtual twin too complex to maintain  
**Mitigation**: Start with 5 variables, add only if needed

**Risk**: Not enough data to train learned model  
**Mitigation**: Require 30 days of data before enabling learning

**Risk**: Predictions create false confidence  
**Mitigation**: Always show confidence intervals, calibration score

---

## Test Summary

### Total Test Cases by Phase

| Phase | Unit Tests | Integration Tests | E2E Tests | Total |
|-------|------------|-------------------|-----------|-------|
| Phase 0 (MVP) | 11 | - | - | 11 (DONE) |
| Phase 1 | 7 | 2 | 1 | 10 |
| Phase 2 | 6 | 3 | 2 | 11 |
| Phase 3 | 6 | 5 | 2 | 13 |
| Phase 4 | 5 | 4 | 2 | 11 |
| Phase 5 | 7 | 4 | 2 | 13 |
| **Total** | **42** | **18** | **9** | **69** |

### Test Priority

**Critical (must pass before release)**:
- All Phase 0 tests (DONE)
- P1.1-P1.4 (weather + scenarios core)
- P2.1-P2.3 (routes core)
- P4.2 (policy enforcement)
- P5.2-P5.4 (simulation core)

**Important (should pass)**:
- All remaining unit tests
- Integration tests

**Nice to have**:
- E2E tests
- Performance tests

---

---

# Part III: The Success Engine

## How Converx Ensures You Win

This section answers the fundamental question: **How does this system actually ensure successful outcomes - not just plans, but results?**

---

## The Feedback Architecture

### Three Interlocking Loops

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  LOOP 1: CALIBRATION (Tactical)                                  │
│  Predict → Act → Observe → Compare → Adjust                      │
│  Frequency: Daily/Weekly                                          │
│  Output: Accurate self-knowledge                                  │
│                                                                   │
│  LOOP 2: ALIGNMENT (Strategic)                                   │
│  Goal → Route → Actions → Outcome → Was it worth it?             │
│  Frequency: Weekly/Monthly                                        │
│  Output: Wisdom about what matters                                │
│                                                                   │
│  LOOP 3: SUSTAINABILITY (Existential)                            │
│  Work ↔ Health ↔ Finance ↔ Relationships ↔ Purpose               │
│  Frequency: Monthly/Quarterly                                     │
│  Output: Life that actually works                                 │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### What Gets Measured

**Tactical (Daily)**:
- Waypoint velocity
- Blocker resolution time
- Scenario tracking accuracy
- Energy levels

**Strategic (Monthly)**:
- Goal completion rate
- Prediction accuracy (<20% error target)
- Route efficiency (actual vs estimated)
- Cross-domain balance

**Existential (Yearly)**:
- Major milestones achieved
- Capability growth
- Freedom increased
- Wisdom accumulated

---

## Truth-Seeking Mechanisms

### 1. Forced Uncertainty Acknowledgment
Scenario bands make uncertainty visible - you can't pretend you know.

### 2. Retrospective Honesty
Weekly reflection surfaces patterns you'd rather not see.

### 3. Cross-Source Aggregation
When evidence conflicts, Converx shows you - no hiding from reality.

### 4. Weather Doesn't Lie
The metaphor cuts through self-deception: you're in a storm or you're not.

---

## Wisdom Accumulation

### Decision Log
Every significant decision captured with context, rationale, and outcome.

### Pattern Library
Recurring patterns extracted: "When X happens, you tend to do Y, which leads to Z."

### Personal Heuristics
Learned rules specific to you: "Multiply estimates by 1.4" or "No complex work after 8pm."

---

# Part IV: The Vision of Maximum Value

## The Core Question: How Does Converx Ensure You Win?

### What This Section Is

This is not a feature list. This is a **vision of what becomes possible** when a system is genuinely designed around human potential rather than task completion.

Read this not as a spec, but as a **map of the territory you're about to explore**.

---

## 1. The Transformation: From Reactive to Generative

### The Problem With Current Reality

You wake up. You check email. You react to Slack. You handle the urgent thing. Then another. By evening, you've been "productive" but nothing that matters moved forward. You're tired but can't point to what you accomplished. You plan to do better tomorrow. Tomorrow is the same.

This is **reactive existence** - being lived by your inputs rather than living toward your outputs.

### The Converx Shift

```
BEFORE (Reactive)                    AFTER (Generative)
─────────────────                    ──────────────────
Wake up → Check inputs               Wake up → Check strategic position
React to urgent                      Act on important
Feel busy                            Feel directed
End day exhausted                    End day accomplished
Wonder if it mattered                Know exactly what moved

"What should I do?"                  "What's the highest-leverage action
                                      given my current state, energy,
                                      goals, and trajectory?"
```

The difference isn't productivity. It's **agency**. You're no longer a node in other people's systems. You're the strategist of your own life.

---

## 2. The Five Dimensions of Winning

### Dimension 1: Clarity (Knowing What Matters)

**The State**: At any moment, you know exactly what the most important thing is and why. Not because you decided this morning and hope it's still true. Because the system continuously synthesizes your goals, current state, and environmental changes into a clear recommendation.

**What It Feels Like**: The anxiety of "am I working on the right thing?" dissolves. You're not guessing. You're navigating with instruments.

**Example**:
```
7:34 AM - You open Converx

STRATEGIC POSITION: Work/Code
Weather: Moderate Pressure
Current Route: "Ship VortexV2 MVP" (67% complete)
Scenario: Tracking "Likely" (12 days to completion)

RECOMMENDED NEXT ACTION:
Complete sensor preprocessing tests (Block 1.4)

Why this, why now:
- Blocks 3 downstream waypoints
- Your energy is highest in morning (learned pattern)
- No meetings until 11am (calendar clear)
- Finishing this moves you from "Likely" to "Optimistic" scenario

Confidence: 94%
```

You don't wonder what to do. You execute. And you know *why* you're executing.

### Dimension 2: Velocity (Moving At Maximum Sustainable Speed)

**The State**: You're moving as fast as you sustainably can. Not faster (burnout). Not slower (waste). The system knows your actual capacity - not your aspirational capacity - and optimizes around it.

**What It Feels Like**: The guilt of "I should be doing more" fades. You're not comparing yourself to an imaginary superhuman version. You're optimizing *your* actual system.

**Example**:
```
VELOCITY ANALYSIS: Last 30 Days

Your Sustainable Pace:
- Focus hours: 22-26/week (not 40, that's a myth for you)
- Deep work blocks: 3-4 hours max (then diminishing returns)
- Recovery needed: 1 light day per 4 intense days

Current Trajectory:
- This week: 28 focus hours attempted → Quality dropped day 4-5
- Pattern: Pushing beyond 26 hours costs more than it gains

RECOMMENDATION:
Cap focus hours at 26 this week. You'll actually accomplish more.
Historical evidence: When you've done this, completion rate +23%.
```

You stop fighting your nature. You start leveraging it.

### Dimension 3: Sustainability (Winning Without Breaking)

**The State**: Your "wins" don't come at the cost of your health, relationships, or sanity. The system tracks cross-domain impacts and warns you before you sacrifice long-term capacity for short-term output.

**What It Feels Like**: You can push hard *when it matters* because you're not already depleted from pushing hard *all the time*.

**Example**:
```
CROSS-DOMAIN ALERT

You're considering: "Push 50-hour week to hit VortexV2 deadline"

Simulation Results:
                        This Week    Next Week    Net Effect
─────────────────────────────────────────────────────────────
Work/Code Output        +40%         -60%         -20%
Energy Level            0.8 → 0.3    Recovery     2 weeks
Health (sleep/exercise) Degraded     Catch-up     Net negative
Relationship Time       -80%         Guilt        Stress

ALTERNATIVE ROUTE:
Push for 3 days (Mon-Wed), then recover Thu-Fri
- Output: +25% (not +40%)
- But: No crash, sustainable, net positive

The "obvious" choice (push harder) is actually the wrong choice.
Converx shows you what you wouldn't see until it's too late.
```

### Dimension 4: Learning (Getting Wiser, Not Just Busier)

**The State**: Every action, every decision, every outcome feeds back into a system that makes you wiser. You're not just accumulating completed tasks. You're accumulating *understanding*.

**What It Feels Like**: You start recognizing patterns before they fully emerge. You make decisions faster because you've seen this before. You trust yourself more because you have evidence.

**Example**:
```
PATTERN RECOGNIZED

Current situation: New feature request from stakeholder, mid-sprint

Your Historical Pattern (12 instances):
- Times you absorbed the scope: 9
- Times it delayed delivery: 8 (89%)
- Average delay: 3.2 days
- Times you pushed back: 3
- Times delivery stayed on track: 3 (100%)

Your default response: "Sure, it's small, I can fit it in"
Your actual outcome: Almost always regret

SUGGESTED RESPONSE:
"I can add this after the current milestone. If it's urgent,
what should we cut from current scope?"

This isn't generic advice. This is YOUR pattern, from YOUR history.
```

### Dimension 5: Freedom (The Ultimate Outcome)

**The State**: As you win in the other four dimensions, something larger emerges: *options*. You have more choices. More runway. More capability. More flexibility. You're not trapped by circumstances because you've systematically built a position of strength.

**What It Feels Like**: The scarcity mentality fades. You're not making decisions from fear of running out. You're making decisions from a place of abundance and clarity.

**Example**:
```
FREEDOM TRAJECTORY: 12-Month View

Where you were (Jan 2025):
- Financial runway: 4 months
- Active commitments: 6 projects
- Energy baseline: 0.5 (depleted)
- Options: "Keep grinding, can't afford to stop"

Where you are (Jan 2026):
- Financial runway: 14 months
- Active commitments: 2 projects (focused)
- Energy baseline: 0.8 (sustainable)
- Options: "Could take 3 months off, start something new,
           or double down on what's working"

The compounding effect of making good decisions,
calibrated by a system that helps you see clearly.
```

---

## 3. The Ideal State: What Mastery Looks Like

### Year One: The Calibration Year

**What happens**:
- You learn your actual velocity (not imagined)
- You discover your energy patterns (when you're best at what)
- You identify your recurring patterns (traps and superpowers)
- The system calibrates to YOU

**The shift**:
- From "I should be able to do X" to "I actually do Y"
- From generic productivity advice to personal heuristics
- From hoping to knowing

**Measurable outcomes**:
- Prediction accuracy: 50% → 80%
- Goal completion rate: 40% → 70%
- Burnout incidents: Many → Rare

### Year Two: The Acceleration Year

**What happens**:
- Patterns are recognized before they fully emerge
- Decisions are faster because you've seen them before
- Playbooks handle routine, freeing you for high-leverage work
- Cross-domain optimization becomes natural

**The shift**:
- From conscious effort to unconscious competence
- From fighting your nature to leveraging it
- From isolated domains to integrated life

**Measurable outcomes**:
- Time on strategic work: 30% → 60%
- Cross-domain health: Volatile → Stable
- Major goals achieved: 2-3 → 5-7

### Year Three+: The Wisdom Years

**What happens**:
- You have a rich library of personal heuristics
- The system knows you better than you know yourself
- You're teaching others what you've learned
- New domains adopt quickly because the meta-skill is learned

**The shift**:
- From learning to teaching
- From individual optimization to system design
- From personal success to legacy building

**Measurable outcomes**:
- Decision quality: High and consistent
- New domain onboarding: Weeks not months
- Personal capacity: Still growing, not declining

---

## 4. Use Case Examples: A Day in the Life

### Morning: Strategic Orientation (5 minutes)

```
$ converx morning

GOOD MORNING, JESSE
Friday, January 10, 2025 | 7:42 AM

OVERNIGHT CHANGES:
- VortexV2: CI passed, Block 1.4 tests green
- Alpha Arena: Model performance dipped 3% (monitor)
- No urgent emails or messages

LIFE WEATHER MAP:
Work/Code:    ☀️ Calm (blockers cleared, momentum high)
Health:       ⛅ Moderate (sleep 6.2h, below target)
Finance:      ☀️ Calm (runway stable at 14 months)

TODAY'S STRATEGIC POSITION:
Route: "Ship VortexV2 MVP" - Day 12 of 18 (67%)
Scenario: Tracking OPTIMISTIC (ahead of schedule!)

RECOMMENDED FOCUS:
1. [2h] Complete Block 1.5: ML Model Integration
   - Best window: 8am-10am (your peak hours)
   - Why: Clears path to final integration

2. [30m] Weekly health check-in
   - Sleep debt accumulating, schedule early night

3. [1h] Alpha Arena: Investigate model performance dip
   - Not urgent, but don't let it drift

ENERGY FORECAST:
Morning: High (8am-12pm) ← Schedule deep work here
Afternoon: Medium (1pm-4pm) ← Meetings, reviews OK
Evening: Low (after 6pm) ← Light work only

Your day is designed. Execute.
```

### Midday: Decision Support (2 minutes)

```
$ converx decide "Should I take the meeting with potential investor?"

DECISION ANALYSIS: Investor Meeting

THE ASK:
- 1-hour meeting next Tuesday
- Exploratory conversation about Alpha Arena

CURRENT CONTEXT:
- VortexV2 deadline: 6 days
- Alpha Arena: Not actively seeking investment
- Your energy: Moderate (mid-week)

SCENARIO ANALYSIS:
If you take the meeting:
- Time cost: 1h meeting + 30m prep + 30m recovery = 2h
- VortexV2 impact: Likely → Conservative scenario (adds 1 day)
- Opportunity: Unknown (could be high, could be zero)
- Pattern match: Last 3 "exploratory" meetings → 0 outcomes

If you decline:
- VortexV2: Stays on Optimistic
- Relationship: Minimal impact (you're not raising)
- Future: Can revisit after VortexV2 ships

RECOMMENDATION: Decline or defer

Suggested response:
"Thanks for reaching out! I'm in the final sprint on a major project
that ships Jan 16. Could we reconnect after that? I'd be able to give
you my full attention."

CONFIDENCE: 87%
REASONING: Historical pattern shows exploratory meetings during
crunch time have negative ROI. Protect the sprint.
```

### Evening: Reflection (3 minutes)

```
$ converx reflect

DAILY REFLECTION: Friday, January 10

WHAT YOU PLANNED:
1. [x] Block 1.5: ML Model Integration (2h planned, 2.5h actual)
2. [x] Weekly health check-in (30m planned, 20m actual)
3. [~] Alpha Arena investigation (1h planned, 30m actual - deprioritized)

PREDICTION ACCURACY: 85%
- Slight underestimate on Block 1.5 (integration tests took longer)
- This matches your pattern: integration work = +25% estimate

ROUTE PROGRESS:
VortexV2: 67% → 72% (on track for Optimistic)

ENERGY TRACKING:
- Morning focus: 3.5 hours (excellent)
- Afternoon: 2 hours productive (good)
- Evening: Light work only (followed guidance)
- End-of-day energy: 0.6 (sustainable)

PATTERNS OBSERVED:
- You checked Slack 12 times today (down from 18 avg)
- Deep work blocks: 2 uninterrupted (up from 1.5 avg)
- Decision made (investor meeting): Good call, protected sprint

HEALTH NOTE:
Sleep debt: 2.3 hours accumulated this week
RECOMMENDATION: Target 8h+ tonight, no screens after 9pm

TOMORROW PREVIEW:
Saturday - Reduced schedule (recovery day)
- Optional: Light Alpha Arena investigation
- Required: Rest and exercise

You moved the needle today. Rest and come back stronger.
```

### Weekly: Strategic Review (15 minutes)

```
$ converx weekly

WEEKLY STRATEGIC REVIEW: Jan 6-12, 2025

ROUTE PROGRESS:
┌──────────────────────────────────────────────────────────────┐
│ VortexV2 MVP: Ship by Jan 16                                 │
│ ████████████████░░░░░░░░ 72% complete                       │
│                                                              │
│ Week started: 52%                                            │
│ Week ended: 72%                                              │
│ Velocity: +20% (excellent)                                   │
│                                                              │
│ Scenario: OPTIMISTIC (upgraded from Likely on Wednesday)    │
│ Confidence: 91%                                              │
└──────────────────────────────────────────────────────────────┘

WAYPOINTS COMPLETED:
[x] Block 1.4: Sensor Preprocessing (Mon-Tue)
[x] Block 1.5: ML Model Integration (Thu-Fri)
[>] Block 1.6: Scoring System (Next)

PREDICTIONS VS ACTUALS:
┌────────────────────────┬───────────┬────────┬─────────┐
│ Item                   │ Predicted │ Actual │ Error   │
├────────────────────────┼───────────┼────────┼─────────┤
│ Block 1.4              │ 4-6h      │ 5h     │ 0%      │
│ Block 1.5              │ 2h        │ 2.5h   │ +25%    │
│ Focus hours            │ 24h       │ 22h    │ -8%     │
└────────────────────────┴───────────┴────────┴─────────┘
Overall accuracy: 89% (excellent)

CROSS-DOMAIN HEALTH:
Work/Code:    ████████░░ 80% (up from 65%)
Health:       ██████░░░░ 60% (sleep debt, address this week)
Finance:      ████████░░ 80% (stable)
Relationships: ███████░░░ 70% (scheduled time with family)

PATTERNS THIS WEEK:
+ Integration estimates: Add 25% (confirmed pattern)
+ Morning deep work: 3+ hours when protected (new record)
- Slack checking: Still too frequent (12 avg, target <8)

DECISIONS MADE:
1. Declined investor meeting → Protected sprint (good call)
2. Deprioritized Alpha Arena investigation → Right tradeoff
3. Took Friday evening off → Energy preserved

LEARNINGS CAPTURED:
- Integration work with external APIs = multiply by 1.25
- Tuesday afternoon: low energy, schedule meetings not work
- "Quick check" on Slack = 15 min average (not 2 min)

NEXT WEEK PREVIEW:
- Finish VortexV2 (Blocks 1.6, 1.7)
- Ship by Thursday (2 days buffer)
- Friday: Celebration + planning next route

RECOMMENDATION:
Focus is paying off. Protect it. One more week of intensity,
then recovery. You're ahead of schedule - don't self-sabotage
by adding scope. Ship, then expand.

This was a winning week. Keep the momentum.
```

---

## 5. The Compound Effect: Why This Works

### Most Systems Fail Because They Don't Close The Loop

```
Traditional tool:
Plan → Do → (maybe) Review → (rarely) Learn → (never) Adapt

Converx:
Plan → Do → Measure → Compare → Learn → Adapt → Better Plan
  ↑                                                    │
  └────────────────────────────────────────────────────┘
                    CLOSED LOOP
```

### The Compounding Math

**Year 1**: Learn your actual velocity
- Predictions go from 50% → 80% accurate
- You stop wasting time on impossible plans
- Net gain: 10% more effective output

**Year 2**: Patterns recognized and leveraged
- Decisions made 2x faster (you've seen this before)
- Mistakes avoided (you know your traps)
- Net gain: 25% more effective output

**Year 3**: Wisdom accumulated
- Strategic choices compound
- Others seek your advice
- Net gain: 50% more effective output

**The Math**:
- Year 0 baseline: 100 units of output
- Year 1 (+10%): 110
- Year 2 (+25% on new base): 137
- Year 3 (+50% on new base): 206

**You're 2x as effective in 3 years.** Not from working harder. From working smarter, informed by a system that actually learns.

---

## 6. Why You'll Actually Use This

### The Usual Failure Mode

Most productivity systems fail because:
1. They require willpower to use (you don't have spare willpower)
2. They don't provide immediate value (future payoff is abstract)
3. They make you feel bad about not using them (guilt → avoidance)
4. They're disconnected from actual work (another thing to manage)

### Why Converx Is Different

**1. Immediate Value, First Interaction**

You run `converx next` and get a clear action with rationale. You didn't have to set up anything, define goals, or organize tasks. It pulled from your existing work (git repos, ACTION_PLAN.md) and synthesized.

**2. Gets More Valuable Over Time**

The more you use it, the more it knows. The more it knows, the better the recommendations. The better the recommendations, the more you trust it. The more you trust it, the more you use it.

This is a **virtuous cycle**, not a guilt cycle.

**3. Surfaces Truth You'd Avoid**

You *want* to know if you're on track. You *want* to know if you're burning out. You *want* to know if your estimates are systematically wrong. But you won't look on your own.

Converx shows you anyway - not judgmentally, just factually. And somehow, facing truth is easier when it comes from a system than from yourself.

**4. Reduces Cognitive Load, Doesn't Add It**

You're not managing Converx. Converx is managing the complexity. You show up, it tells you what matters. You execute, it tracks. You reflect, it learns.

The system carries the weight. You carry the decisions.

---

## 7. The Invitation

### What You're Really Building

Converx is not a productivity tool. It's a **cognitive exoskeleton** for your strategic mind.

It doesn't make you work harder. It makes you **see clearer**.

It doesn't give you more hours. It makes each hour **count more**.

It doesn't add complexity. It **absorbs complexity** and returns clarity.

### The Question

Right now, you make decisions based on:
- Gut feeling
- Incomplete information
- Optimistic estimates
- Yesterday's priorities

What if you could make decisions based on:
- Empirical patterns from YOUR history
- Complete context across domains
- Calibrated predictions with confidence intervals
- Strategic priorities updated by reality

**That's the difference between hoping and knowing.**

### The Invitation

Use Converx for one week. Just `converx next` each morning and `converx reflect` each evening.

At the end of the week, you'll know:
- What you actually accomplished (not what you were busy with)
- How accurate your intuitions are (probably less than you think)
- What patterns are helping or hurting you (you've never seen this before)

And then you decide: Is this valuable? Do I want to go deeper?

The system doesn't demand anything. It offers.

The choice is yours.

---

## Conclusion

**Current State**: Phase 0 (MVP) complete with 11 tests passing. Ready for validation.

**Next Step**: Use MVP daily for 1 week, then proceed to Phase 1 if validated.

**Key Principle**: Each phase delivers standalone value. Stop at any phase. Don't build Virtual Twin before validating Routes. Don't build Routes before validating Status Map.

**Effort Summary**:
- Phase 0: 2-3 hours (DONE)
- Phase 1: 2-3 hours
- Phase 2: 4-6 hours
- Phase 3: 6-8 hours
- Phase 4: 4-6 hours
- Phase 5: 8-12 hours
- **Total to Full Vision**: 26-38 hours

---

**Document Status**: Complete design specification with detailed test cases for all phases and full vision of maximum value.

**Last Updated**: January 2025

---

*"The system that helps you see clearly is more valuable than the system that helps you do more. Clarity creates leverage. Leverage creates freedom. Freedom creates the space to do what actually matters."*

