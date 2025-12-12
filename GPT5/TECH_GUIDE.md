# Converx Technical Guide

## Overview

This guide documents Converx's architecture, extension points, and patterns for safe modification. It's written for you as the primary developer, with a focus on **hybrid local/connected** patterns and decision intelligence extensions.

---

## Architecture

### Current MVP (Phase 0)

Converx is a **thin orchestration layer** that combines existing tools:

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

### Core Components

#### 1. CLI (`converx/cli.py`)

**Purpose**: Command-line interface entry point.

**Key Functions**:
- `cmd_next()`: Get next action with optional project filter and context
- `cmd_status()`: Show current state summary
- `main()`: Argument parsing and routing

**Extension Points**:
- Add new commands (e.g., `converx weather`, `converx route`)
- Add new flags (e.g., `--domain`, `--scenario`)
- Add new output formats (e.g., `--markdown`, `--csv`)

#### 2. Orchestrator (`converx/orchestrator.py`)

**Purpose**: Core orchestration logic that combines tools.

**Key Classes**:
- `ConverxOrchestrator`: Main orchestrator class
- `StrategistResponse`: Response data structure

**Key Methods**:
- `get_next_action()`: Orchestrates all tools and returns strategist response
- `_build_current_state()`: Builds current state summary from projects and goals

**Extension Points**:
- Add new tool integrations (e.g., financial-aggregator, keto-tracker)
- Add new filtering logic (e.g., by domain, by risk level)
- Add new aggregation logic (e.g., cross-domain analysis)

#### 3. Formatter (`converx/formatter.py`)

**Purpose**: Formats strategist responses for display.

**Key Classes**:
- `ConverxFormatter`: Formatter class

**Key Methods**:
- `format_response()`: Main formatting method (text or JSON)
- `_format_text()`: Human-readable text formatting
- `_format_json()`: Machine-readable JSON formatting

**Extension Points**:
- Add new output formats (e.g., markdown, HTML, CSV)
- Add new visualization elements (e.g., progress bars, charts)
- Add new formatting styles (e.g., compact, verbose)

---

## Extension Patterns

### Pattern 1: Adding a New Domain Analyzer

**Use Case**: Add finance domain analysis (e.g., runway tracking, opportunity cost).

**Steps**:

1. **Create analyzer module** (`converx/analyzers/finance.py`):
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class FinanceState:
    runway_months: float
    volatility: str
    opportunity_cost: Optional[str]

class FinanceAnalyzer:
    def analyze(self) -> FinanceState:
        # Read from financial-aggregator or Alpha Arena
        # Return finance state
        pass
```

2. **Integrate into orchestrator** (`converx/orchestrator.py`):
```python
# Add to ConverxOrchestrator.__init__()
try:
    from .analyzers.finance import FinanceAnalyzer
    self.finance_analyzer = FinanceAnalyzer()
except ImportError:
    self.finance_analyzer = None

# Add to get_next_action()
finance_state = None
if self.finance_analyzer:
    try:
        finance_state = self.finance_analyzer.analyze()
    except Exception as e:
        print(f"Warning: Could not analyze finance: {e}", file=sys.stderr)
```

3. **Include in state summary** (`_build_current_state()`):
```python
state["finance"] = {
    "runway_months": finance_state.runway_months if finance_state else None,
    "volatility": finance_state.volatility if finance_state else None,
}
```

4. **Update formatter** (`converx/formatter.py`):
```python
# Add finance section to _format_text()
if "finance" in state:
    finance = state["finance"]
    if finance.get("runway_months"):
        lines.append(f"Finance Runway: {finance['runway_months']} months")
```

**Hybrid Local/Connected Pattern**:
- **Local**: Read from local files (e.g., `financial-aggregator` outputs)
- **Connected**: Optionally call APIs (e.g., Alpha Arena API) if available
- **Fallback**: Gracefully degrade if analyzer unavailable

### Pattern 2: Adding a Risk Detector

**Use Case**: Add early-warning system for emerging risks (e.g., burnout risk, runway risk).

**Steps**:

1. **Create risk detector module** (`converx/detectors/risk.py`):
```python
from dataclasses import dataclass
from typing import List

@dataclass
class Risk:
    domain: str
    severity: str  # "low", "medium", "high"
    description: str
    horizon_days: int  # When risk might materialize

class RiskDetector:
    def detect_risks(
        self,
        project_activity: List,
        goals: List,
        finance_state: Optional[FinanceState] = None
    ) -> List[Risk]:
        risks = []

        # Example: Detect burnout risk
        if self._high_workload_with_low_energy(project_activity):
            risks.append(Risk(
                domain="health",
                severity="high",
                description="High workload with low energy signals burnout risk",
                horizon_days=14
            ))

        # Example: Detect runway risk
        if finance_state and finance_state.runway_months < 3:
            risks.append(Risk(
                domain="finance",
                severity="high",
                description="Runway below 3 months",
                horizon_days=90
            ))

        return risks
```

2. **Integrate into orchestrator**:
```python
# Add to get_next_action()
risks = []
if self.risk_detector:
    try:
        risks = self.risk_detector.detect_risks(
            project_activity=project_activity,
            goals=goals,
            finance_state=finance_state
        )
    except Exception as e:
        print(f"Warning: Could not detect risks: {e}", file=sys.stderr)

# Add to StrategistResponse
@dataclass
class StrategistResponse:
    # ... existing fields ...
    risks: List[Risk] = None
```

3. **Update formatter**:
```python
# Add risks section to _format_text()
if response.risks:
    lines.append("⚠️  RISKS DETECTED")
    lines.append("────────────────")
    for risk in response.risks:
        severity_icon = "🔴" if risk.severity == "high" else "🟡" if risk.severity == "medium" else "⚪"
        lines.append(f"{severity_icon} [{risk.domain.upper()}] {risk.description}")
        lines.append(f"   Horizon: {risk.horizon_days} days")
        lines.append("")
```

**Hybrid Local/Connected Pattern**:
- **Local**: Analyze local data (project activity, goals, finance state)
- **Connected**: Optionally use AI models for complex risk detection (e.g., pattern recognition)
- **Fallback**: Return empty list if detector unavailable

### Pattern 3: Adding Scenario Bands (Phase 1 Preview)

**Use Case**: Add optimistic/likely/conservative scenario bands to recommendations.

**Steps**:

1. **Create scenario module** (`converx/strategy/scenarios.py`):
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ScenarioBand:
    optimistic: str  # Best-case outcome
    likely: str       # Most likely outcome
    conservative: str # Worst-case outcome
    optimistic_conditions: str
    conservative_conditions: str

class ScenarioCalculator:
    def calculate_scenarios(
        self,
        recommendation: Recommendation,
        project_activity: List,
        goals: List
    ) -> ScenarioBand:
        # Calculate based on:
        # - Project momentum (commits, activity)
        # - Blockers and risks
        # - Historical patterns (if available)

        momentum = self._calculate_momentum(project_activity)
        blockers = self._count_blockers(project_activity)

        if momentum > 0.8 and blockers == 0:
            # High momentum, no blockers = optimistic
            optimistic = "2 weeks"
            likely = "3 weeks"
            conservative = "4 weeks"
        elif momentum > 0.5 and blockers <= 1:
            # Moderate momentum, few blockers = likely
            optimistic = "3 weeks"
            likely = "4 weeks"
            conservative = "6 weeks"
        else:
            # Low momentum or many blockers = conservative
            optimistic = "4 weeks"
            likely = "6 weeks"
            conservative = "8 weeks"

        return ScenarioBand(
            optimistic=optimistic,
            likely=likely,
            conservative=conservative,
            optimistic_conditions="High momentum, no blockers, 25h focused/week",
            conservative_conditions="Low momentum, blockers present, interruptions likely"
        )
```

2. **Integrate into orchestrator**:
```python
# Add to get_next_action()
if self.scenario_calculator and recommendations:
    for rec in recommendations:
        rec.scenarios = self.scenario_calculator.calculate_scenarios(
            recommendation=rec,
            project_activity=project_activity,
            goals=goals
        )
```

3. **Update formatter**:
```python
# Add scenarios to recommendation formatting
if hasattr(rec, 'scenarios') and rec.scenarios:
    lines.append("Scenario Bands:")
    lines.append(f"  Optimistic:    {rec.scenarios.optimistic} ({rec.scenarios.optimistic_conditions})")
    lines.append(f"  Most Likely:   {rec.scenarios.likely} <-- tracking")
    lines.append(f"  Conservative:  {rec.scenarios.conservative} ({rec.scenarios.conservative_conditions})")
```

**Hybrid Local/Connected Pattern**:
- **Local**: Calculate scenarios from local data (momentum, blockers)
- **Connected**: Optionally use AI models for complex scenario modeling (e.g., Monte Carlo simulation)
- **Fallback**: Return simple scenarios if calculator unavailable

---

## Hybrid Local/Connected Patterns

### Pattern: Local-First with Optional Cloud

**Principle**: Keep core logic and data local, but allow cloud/AI augmentation when beneficial.

**Example**: Risk Detection
```python
class RiskDetector:
    def detect_risks(self, data):
        # Local: Analyze local data first
        local_risks = self._analyze_local(data)

        # Connected: Optionally augment with AI if available
        if self.ai_model_available:
            ai_risks = self._analyze_with_ai(data)
            # Merge local + AI insights
            return self._merge_risks(local_risks, ai_risks)
        else:
            return local_risks
```

### Pattern: Graceful Degradation

**Principle**: Always provide value even if some components are unavailable.

**Example**: Multi-Domain Analysis
```python
def get_next_action(self):
    # Try to get finance state (optional)
    finance_state = None
    if self.finance_analyzer:
        try:
            finance_state = self.finance_analyzer.analyze()
        except Exception as e:
            print(f"Warning: Finance analysis unavailable: {e}", file=sys.stderr)
            # Continue without finance - still provide value

    # Try to get health state (optional)
    health_state = None
    if self.health_analyzer:
        try:
            health_state = self.health_analyzer.analyze()
        except Exception as e:
            print(f"Warning: Health analysis unavailable: {e}", file=sys.stderr)
            # Continue without health - still provide value

    # Return recommendations with available data
    return self._generate_recommendations(
        finance_state=finance_state,  # May be None
        health_state=health_state     # May be None
    )
```

### Pattern: Configurable Connectivity

**Principle**: Allow users to configure which services to connect to.

**Example**: Configuration File (`~/.converx/config.json`)
```json
{
  "local_only": false,
  "connected_services": {
    "ai_models": {
      "enabled": true,
      "provider": "anthropic",
      "api_key_env": "ANTHROPIC_API_KEY"
    },
    "github": {
      "enabled": true,
      "token_env": "GITHUB_TOKEN"
    },
    "google_fit": {
      "enabled": false
    }
  }
}
```

---

## Safety and Failure Modes

### Error Handling Philosophy

**Graceful Degradation**: If a tool is unavailable, continue with available tools and show warnings.

**Example** (`converx/orchestrator.py`):
```python
try:
    from ai_intelligence import ProjectScanner
    self.project_scanner = ProjectScanner(str(root_dir))
except ImportError:
    print("Warning: ai_intelligence.py not available", file=sys.stderr)
    self.project_scanner = None
```

### Failure Modes

1. **Missing Tool**: If `ai_intelligence.py` is unavailable, continue with goals and recommendations only.
2. **Missing File**: If `ACTION_PLAN.md` is missing, use project activity only.
3. **Tool Error**: If a tool throws an exception, catch it, log warning, continue with other tools.
4. **Invalid Data**: If tool returns invalid data, validate and use defaults if needed.

### Testing Extension Points

**Unit Tests**: Test each extension point in isolation.
```python
def test_finance_analyzer():
    analyzer = FinanceAnalyzer()
    state = analyzer.analyze()
    assert state.runway_months > 0
    assert state.volatility in ["low", "medium", "high"]
```

**Integration Tests**: Test extension points with orchestrator.
```python
def test_orchestrator_with_finance():
    orchestrator = ConverxOrchestrator()
    response = orchestrator.get_next_action()
    assert "finance" in response.current_state
```

---

## Performance Considerations

### Current Performance (Phase 0)
- **Startup**: <1 second
- **Execution**: <5 seconds (including all tool calls)
- **Memory**: <50MB

### Optimization Patterns

1. **Lazy Loading**: Only load tools when needed.
2. **Caching**: Cache expensive operations (e.g., project scanning).
3. **Parallel Execution**: Run independent tools in parallel.
4. **Incremental Updates**: Only update changed data.

### Example: Parallel Tool Execution
```python
import concurrent.futures

def get_next_action(self):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Run tools in parallel
        project_future = executor.submit(self._scan_projects)
        goals_future = executor.submit(self._parse_goals)
        finance_future = executor.submit(self._analyze_finance)

        # Wait for results
        project_activity = project_future.result()
        goals = goals_future.result()
        finance_state = finance_future.result()
```

---

## Extension Checklist

When adding a new feature:

- [ ] **Create module**: New file in appropriate directory (e.g., `converx/analyzers/`, `converx/detectors/`)
- [ ] **Integrate orchestrator**: Add to `ConverxOrchestrator.__init__()` with graceful error handling
- [ ] **Update state**: Add new data to `_build_current_state()` if needed
- [ ] **Update formatter**: Add new section to `_format_text()` if displaying to user
- [ ] **Add tests**: Unit tests for new module, integration tests with orchestrator
- [ ] **Document**: Update this guide with new extension pattern
- [ ] **Hybrid pattern**: Ensure local-first with optional cloud connectivity
- [ ] **Error handling**: Graceful degradation if feature unavailable

---

## Future Architecture (Phase 1-5)

### Phase 1: Weather Map + Scenarios
- `converx/strategy/weather_map.py`: Weather state and metaphors
- `converx/strategy/scenarios.py`: Scenario band calculation

### Phase 2: Routes & Multi-Domain
- `converx/strategy/model.py`: Goal, Route, Waypoint dataclasses
- `converx/strategy/domains.py`: Multi-domain weather map

### Phase 3: Deep Integrations
- `converx/knowledge/personal_ai.py`: personal-ai-dataset connector
- `converx/knowledge/alpha_arena.py`: Alpha Arena connector
- `converx/knowledge/google_fit.py`: Health data connector

### Phase 4: Playbooks & Executor
- `converx/playbooks/base.py`: Playbook interface
- `converx/playbooks/executor.py`: Execution engine
- `converx/playbooks/policies.py`: Policy definitions

### Phase 5: Virtual Twin
- `converx/twin/state.py`: State model
- `converx/twin/transitions.py`: Transition rules
- `converx/twin/simulation.py`: Forward simulation engine

---

## Summary

Converx is designed for **safe extension**:
- **Thin orchestration layer**: Easy to understand and modify
- **Graceful degradation**: Works even if some tools unavailable
- **Hybrid local/connected**: Local-first with optional cloud augmentation
- **Clear extension points**: Well-defined patterns for adding features
- **Performance-conscious**: Fast execution, low memory footprint

**Key Principle**: Every extension should follow the same patterns: graceful error handling, hybrid local/connected, and clear integration points.
