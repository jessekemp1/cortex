# Deep Mode Developer Guide

**Audience**: Contributors to Cortex deep mode architecture
**Level**: Intermediate to Advanced
**Last Updated**: 2026-01-18

---

## Architecture Overview

### Design Philosophy

**Depth-First Architecture** prioritizes:
1. **Intelligence quality** (comprehensive context)
2. **Code simplicity** (synchronous, no premature optimization)
3. **Performance** (tertiary - acceptable if <10s)

**Key Principle**: "Accept 5s startup to eliminate 30s of follow-up queries"

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Layer (cli.py)                   │
│  Commands: deep, quick, auto, config                    │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │   cli_display.py    │
          │  (Formatters)       │
          └──────────┬──────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Bridge API (bridge.py)                     │
│  Methods: analyze_deep(), analyze_quick(), analyze_auto()│
└──────┬──────────────────────────────────────┬───────────┘
       │                                      │
   ┌───▼────────────────┐          ┌─────────▼──────────┐
   │ AdaptiveLatency    │          │   DeepAnalyzer     │
   │ Manager            │          │                    │
   │ (Mode Selection)   │          │  (Core Analysis)   │
   └────────────────────┘          └────────────────────┘
           │                                  │
           │                       ┌──────────▼──────────┐
           │                       │  Git Analysis       │
           │                       │  Health Calculation │
           │                       │  Quality Metrics    │
           │                       │  Warnings Generator │
           │                       │  Recommendations    │
           │                       └─────────────────────┘
           │
   ┌───────▼──────────┐
   │  Preferences      │
   │  (JSON Storage)   │
   └──────────────────┘
```

---

## Core Modules

### 1. `intelligence/adaptive_latency.py` (412 LOC)

**Purpose**: Manages mode selection and configuration

**Key Classes**:

```python
class AnalysisMode(Enum):
    FAST = "fast"      # <1s analysis
    DEEP = "deep"      # 2-5s analysis (DEFAULT)
    AUTO = "auto"      # Adaptive selection

class AnalysisConfig:
    """Configuration for each analysis mode"""
    git_days: int
    spec_search_enabled: bool
    pattern_semantic: bool
    health_fresh: bool
    model: str
    use_batch_api: bool
    expected_latency_ms: int

class SessionContext:
    """Context for adaptive mode selection"""
    last_session_time: Optional[datetime]
    time_since_last_session: Optional[timedelta]
    project_name: str
    has_uncommitted_changes: bool
    branch_is_stale: bool
    user_preference: Optional[AnalysisMode]

class AdaptiveLatencyManager:
    """Manages mode selection and preferences"""
    def select_mode(requested_mode, context) -> AnalysisConfig
    def set_project_preference(project, mode)
```

**Design Decisions**:

**Why three modes?**
- DEEP = Default (strategic priority)
- FAST = Opt-in (edge cases only)
- AUTO = Adaptive (learns from context)

**Why SessionContext?**
- Enables intelligent auto mode selection
- Factors: time, state, preferences
- Extensible for future heuristics

**Storage**: `~/.cortex/mode_preferences.json`

---

### 2. `intelligence/deep_analysis.py` (594 LOC)

**Purpose**: Core deep analysis engine (synchronous, comprehensive)

**Key Classes**:

```python
@dataclass
class DeepIntelligence:
    """Complete analysis result"""
    timestamp: datetime
    project: str
    mode: str
    latency_ms: float
    health: HealthAnalysis
    git: GitAnalysis
    specs: List[SpecMatch]
    patterns: List[PatternMatch]
    quality: CodeQuality
    dependencies: Optional[DependencyGraph]
    warnings: List[str]
    recommendations: List[Dict]
    next_actions: List[str]

class DeepAnalyzer:
    """Main analysis engine"""
    def analyze(project, config) -> DeepIntelligence
```

**Analysis Pipeline**:

```python
def analyze(self, project: str, config: Dict) -> DeepIntelligence:
    # 1. Git analysis (90 days)
    git = self._analyze_git(project_path, config)

    # 2. Health calculation (fresh)
    health = self._analyze_health(git, config)

    # 3. Spec search (semantic)
    specs = self._search_specs(project, config)

    # 4. Pattern matching (cross-project)
    patterns = self._match_patterns(project, config)

    # 5. Quality metrics (tech debt, complexity)
    quality = self._analyze_quality(project_path, config)

    # 6. Dependency analysis (optional)
    deps = self._analyze_dependencies(project_path, config)

    # 7. Generate warnings
    warnings = self._generate_warnings(git, health, quality)

    # 8. Generate recommendations
    recommendations = self._generate_recommendations(git, health, specs, patterns)

    # 9. Identify next actions
    next_actions = self._identify_next_actions(recommendations)

    return DeepIntelligence(...)
```

**Design Decisions**:

**Why synchronous?**
- Simpler to debug
- No async complexity
- Latency acceptable (<10s)

**Why no caching?**
- Fresh data > speed
- Eliminates cache bugs
- Simplifies codebase

**Why comprehensive?**
- One analysis = complete context
- Eliminates follow-up queries
- Net time savings

---

### 3. `intelligence/cli_display.py` (338 LOC)

**Purpose**: Terminal formatting with progressive disclosure

**Key Functions**:

```python
def format_deep_intelligence_compact(result) -> str:
    """Default view: top 3 warnings/recommendations"""

def format_deep_intelligence_verbose(result) -> str:
    """Full view: everything"""

def format_health_score(score, assessment) -> str:
    """Color-coded health with progress bar"""

def display_deep_intelligence(result, verbose, json_output):
    """Main display dispatcher"""
```

**Visual Design**:

**Color Coding**:
- Green (32m): Good status, health ≥80
- Yellow (33m): Warning status, health 60-79
- Red (31m): Critical status, health <60
- Blue (34m): Informational
- Cyan (36m): Highlights (project name, branch)
- Dim (2m): Secondary info

**Progressive Disclosure**:
```
Compact Mode (default):
- Health score + progress bar
- Git summary
- Quality metrics
- Top 3 warnings
- Top 3 recommendations
- Tip: "Use --verbose for full details"

Verbose Mode (--verbose):
- Everything in compact
- All warnings
- All recommendations
- Spec matches
- Pattern matches
```

---

### 4. `cli.py` (Commands Integration)

**Added Commands**:

```python
def cmd_deep(args):
    """Run comprehensive deep analysis"""
    bridge = CortexBridge(root_dir=Path(args.root))
    result = bridge.analyze_deep(project=args.project, output_json=args.json)
    display_deep_intelligence(result, verbose=args.verbose, json_output=args.json)

def cmd_quick(args):
    """Run minimal fast analysis"""
    # Currently shows fallback message

def cmd_auto(args):
    """Run adaptive analysis"""
    bridge = CortexBridge(root_dir=Path(args.root))
    result = bridge.analyze_auto(project=args.project)
    # Routes to appropriate display

def cmd_config(args):
    """Manage configuration"""
    if args.show:
        # Display config
    elif args.set_default:
        # Update preferences
```

---

## Adding New Features

### Adding a New Warning

**File**: `intelligence/deep_analysis.py`

**Location**: `_generate_warnings()` method

```python
def _generate_warnings(self, git, health, quality) -> List[str]:
    warnings = []

    # Existing warnings
    warnings.extend(health.warnings)
    if quality.tech_debt_markers > 50:
        warnings.append(f"High technical debt markers: {quality.tech_debt_markers}")

    # NEW WARNING: Add here
    if quality.test_coverage and quality.test_coverage < 50:
        warnings.append(f"Low test coverage: {quality.test_coverage:.1f}%")

    return warnings
```

**Testing**:
```bash
# Create test project with low coverage
python cli.py deep test_project --verbose
# Verify warning appears
```

---

### Adding a New Recommendation

**File**: `intelligence/deep_analysis.py`

**Location**: `_generate_recommendations()` method

```python
def _generate_recommendations(self, git, health, specs, patterns) -> List[Dict]:
    recommendations = []

    # Existing recommendations
    if git.uncommitted_files > 20:
        recommendations.append({
            "priority": "high",
            "title": "Commit or clean up uncommitted work",
            "rationale": f"{git.uncommitted_files} uncommitted files reduce project health",
        })

    # NEW RECOMMENDATION: Add here
    if health.commits_30d < 10:
        recommendations.append({
            "priority": "medium",
            "title": "Increase commit frequency",
            "rationale": f"Only {health.commits_30d} commits in 30 days - consider smaller commits",
        })

    return recommendations
```

**Display Format**:
```
💡 Recommendations (2):
  ⭐ [MEDIUM] Increase commit frequency
     Only 8 commits in 30 days - consider smaller commits
```

---

### Adding a New Quality Metric

**File**: `intelligence/deep_analysis.py`

**Step 1**: Add to `CodeQuality` dataclass

```python
@dataclass
class CodeQuality:
    linting_issues: int
    complexity_score: float
    test_coverage: Optional[float]
    todos: int
    fixmes: int
    tech_debt_markers: int
    # NEW METRIC: Add here
    duplicate_code_pct: Optional[float] = None
```

**Step 2**: Calculate in `_analyze_quality()`

```python
def _analyze_quality(self, project_path, config) -> CodeQuality:
    # Existing calculations...

    # NEW METRIC: Calculate here
    duplicate_code_pct = None
    if config.get("quality_enabled"):
        # Run duplicate detection tool
        duplicate_code_pct = self._detect_duplicates(project_path)

    return CodeQuality(
        linting_issues=linting_issues,
        complexity_score=complexity_score,
        test_coverage=test_coverage,
        todos=todos,
        fixmes=fixmes,
        tech_debt_markers=tech_debt_markers,
        duplicate_code_pct=duplicate_code_pct,  # NEW
    )
```

**Step 3**: Display in `cli_display.py`

```python
def format_quality_metrics(quality_data: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"{Colors.BOLD}Code Quality:{Colors.RESET}")

    # Existing metrics...

    # NEW METRIC: Display here
    duplicate_code = quality_data.get('duplicate_code_pct')
    if duplicate_code is not None:
        color = Colors.GREEN if duplicate_code < 5 else Colors.YELLOW if duplicate_code < 15 else Colors.RED
        lines.append(f"  Duplicate code: {color}{duplicate_code:.1f}%{Colors.RESET}")

    return "\n".join(lines)
```

---

### Adding a New Display Formatter

**File**: `intelligence/cli_display.py`

**Example**: Adding trend sparkline to health score

```python
def format_health_trend(trend_data: List[int]) -> str:
    """
    Generate sparkline for health trend

    Args:
        trend_data: List of health scores (e.g., [75, 78, 80, 82])

    Returns:
        Sparkline string (e.g., "▁▃▅▇")
    """
    if not trend_data:
        return ""

    min_val, max_val = min(trend_data), max(trend_data)
    range_val = max_val - min_val or 1

    sparks = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    sparkline = ""

    for val in trend_data:
        index = int((val - min_val) / range_val * (len(sparks) - 1))
        sparkline += sparks[index]

    return f"{Colors.DIM}{sparkline}{Colors.RESET}"
```

**Usage in compact formatter**:
```python
# In format_deep_intelligence_compact()
trend_sparkline = format_health_trend(health.trend_history)
lines.append(f"  Trend (30d): {trend_sparkline}")
```

---

## Testing Guidelines

### Unit Tests

**Location**: `cortex/tests/unit/`

**Example**: Testing warning generation

```python
# tests/unit/test_deep_analysis.py

from intelligence.deep_analysis import DeepAnalyzer
from pathlib import Path

def test_warning_generation_high_uncommitted():
    """Test warning triggered for high uncommitted files"""
    analyzer = DeepAnalyzer(Path("/Users/jesse.kemp/Dev"))

    # Create mock git analysis with 25 uncommitted files
    git_analysis = GitAnalysis(
        commit_count=100,
        uncommitted_files=25,  # Above threshold
        ...
    )

    health = HealthAnalysis(score=70, warnings=["High uncommitted changes: 25 files"])
    quality = CodeQuality(tech_debt_markers=10)

    warnings = analyzer._generate_warnings(git_analysis, health, quality)

    assert any("uncommitted" in w.lower() for w in warnings)
    assert len(warnings) > 0
```

---

### Integration Tests

**Location**: `cortex/test_cli_integration.py`

**Example**: Testing new CLI option

```python
def test_deep_with_new_option():
    """Test deep command with --format option"""
    result = subprocess.run(
        "python cli.py deep cortex --format=table",
        shell=True,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "│" in result.stdout  # Table borders
```

---

### Manual Testing

**Checklist for new features**:

```bash
# 1. Test on multiple projects
cortex deep cortex --verbose
cortex deep vortexv2 --verbose
cortex deep alpha_arena --verbose

# 2. Test JSON output
cortex deep cortex --json | jq '.'

# 3. Test error handling
cortex deep nonexistent_project  # Should fail gracefully

# 4. Test performance
time cortex deep cortex  # Should be <10s

# 5. Test config persistence
cortex config --set-default deep
cortex config --show  # Verify saved
```

---

## Performance Optimization

### Current Performance Characteristics

**Deep Mode Latency** (90th percentile):
- Small projects (<100 commits): ~2s
- Medium projects (100-500 commits): ~4s
- Large projects (500+ commits): ~6s

**Bottlenecks** (measured):
1. Git log parsing (~40% of time)
2. File system operations (~30%)
3. Quality analysis (~20%)
4. Other (~10%)

---

### Optimization Opportunities (Phase 4)

**Git Analysis**:
```python
# CURRENT: Parse all commits
commits = subprocess.run(["git", "log", f"--since={days} days ago"])

# OPTIMIZED: Use git's native filtering
commits = subprocess.run([
    "git", "log",
    f"--since={days} days ago",
    "--pretty=format:%H|%an|%ae|%s|%ad",
    "--date=iso",
    "--no-merges"  # Skip merge commits
])
```

**Quality Analysis**:
```python
# CURRENT: Separate grep calls
todos = subprocess.run(["grep", "-r", "TODO"])
fixmes = subprocess.run(["grep", "-r", "FIXME"])

# OPTIMIZED: Single grep call
tech_debt = subprocess.run(["grep", "-r", "-E", "(TODO|FIXME)"])
```

---

### When NOT to Optimize

**Premature optimization is evil.** Only optimize when:
1. **Data-driven**: Profiling shows bottleneck
2. **User-impacting**: >10s latency (current: ~5s)
3. **Simple fix**: <50 LOC, no complexity increase

**Current status**: Phase 1 performance is acceptable. Phase 4 may optimize based on real usage data.

---

## Code Style & Patterns

### Dataclasses Over Dicts

**Why**: Type safety, auto-completion, clarity

```python
# GOOD: Dataclass
@dataclass
class HealthAnalysis:
    score: int
    assessment: str
    trend: str

# BAD: Dict
health = {
    "score": 80,
    "assessment": "excellent",
    # Typo risk, no type checking
}
```

---

### Explicit Over Implicit

**Why**: Readability, debugging ease

```python
# GOOD: Explicit
if config.get("spec_search_enabled", False):
    specs = self._search_specs(project, config)
else:
    specs = []

# BAD: Implicit
specs = self._search_specs(project, config) if config.get("spec_search_enabled") else []
```

---

### Synchronous Over Async

**Why**: Simplicity, debugging ease (unless proven bottleneck)

```python
# GOOD: Synchronous (current)
git_analysis = self._analyze_git(project_path, config)
health_analysis = self._analyze_health(git_analysis, config)

# BAD: Async (premature optimization)
async def analyze():
    git_task = asyncio.create_task(self._analyze_git())
    health_task = asyncio.create_task(self._analyze_health())
    # Complexity without proven benefit
```

---

## Common Pitfalls

### Pitfall 1: Caching Too Early

**Problem**: Adds complexity before understanding access patterns

**Example**:
```python
# BAD: Premature caching
self._health_cache = {}
if project in self._health_cache:
    return self._health_cache[project]
```

**Solution**: Only add caching when profiling shows repeated expensive calls

---

### Pitfall 2: Swallowing Exceptions

**Problem**: Silent failures are debugging nightmares

```python
# BAD: Silent failure
try:
    result = self._analyze_git(project)
except Exception:
    pass  # User has no idea what went wrong

# GOOD: Graceful degradation with logging
try:
    result = self._analyze_git(project)
except Exception as e:
    logger.warning(f"Git analysis failed: {e}")
    result = GitAnalysis(commit_count=0, ...)  # Safe fallback
```

---

### Pitfall 3: Over-Engineering Display

**Problem**: Terminal output doesn't need pixel-perfect alignment

```python
# BAD: Complex alignment logic
max_len = max(len(item) for item in items)
for item in items:
    print(f"{item:<{max_len}} {value}")

# GOOD: Simple, readable
for item, value in zip(items, values):
    print(f"  {item}: {value}")
```

---

## Debugging Tips

### Enable Verbose Logging

```python
# In deep_analysis.py, add at top
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# In analysis methods
logger.debug(f"Analyzing {project} with config: {config}")
logger.debug(f"Git analysis found {len(commits)} commits")
```

### Test Individual Components

```python
# Test DeepAnalyzer directly
from intelligence.deep_analysis import DeepAnalyzer
from pathlib import Path

analyzer = DeepAnalyzer(Path("/Users/jesse.kemp/Dev"))
result = analyzer.analyze("cortex", {"git_days": 90, "quality_enabled": True})
print(result)
```

### Use IPython for Exploration

```python
# In IPython or Jupyter
from bridge import CortexBridge
from pathlib import Path

bridge = CortexBridge(Path("/Users/jesse.kemp/Dev"))
result = bridge.analyze_deep("cortex")

# Explore result
result.health.score
result.git.commit_count
result.warnings
```

---

## Contributing Workflow

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/cortex.git
cd cortex
git remote add upstream https://github.com/jessekemp/cortex.git
```

### 2. Create Feature Branch

```bash
git checkout -b feature/add-coverage-warning
```

### 3. Make Changes

- Follow code style (dataclasses, explicit, sync)
- Add tests (unit + integration)
- Update documentation

### 4. Test Locally

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
python test_cli_integration.py

# Manual testing
python cli.py deep cortex --verbose
```

### 5. Commit & Push

```bash
git add .
git commit -m "feat: Add low test coverage warning

- Triggers when coverage <50%
- Displays in quality metrics
- Added integration test"

git push origin feature/add-coverage-warning
```

### 6. Create Pull Request

**PR Template**:
```markdown
## Description
Adds warning for low test coverage (<50%)

## Changes
- Modified `deep_analysis.py` to detect low coverage
- Updated `cli_display.py` to show coverage metric
- Added test case in `test_cli_integration.py`

## Testing
- ✅ Unit tests pass
- ✅ Integration tests pass
- ✅ Manual testing on 3 projects

## Screenshots
(Attach screenshot of warning output)
```

---

## Resources

### Key Files Reference

- `intelligence/adaptive_latency.py` - Mode selection
- `intelligence/deep_analysis.py` - Core analysis engine
- `intelligence/cli_display.py` - Terminal formatting
- `cli.py` - Command handlers
- `bridge.py` - Universal API
- `docs/deep_mode.md` - User guide
- `test_cli_integration.py` - Integration tests

### Related Documentation

- [DESIGN_PRINCIPLES.md](../DESIGN_PRINCIPLES.md) - Strategic direction
- [DEPTH_FIRST_IMPLEMENTATION.md](../DEPTH_FIRST_IMPLEMENTATION.md) - Implementation status
- [.claude/plans/phase1-deep-mode-integration.md](../.claude/plans/phase1-deep-mode-integration.md) - Detailed plan

---

## Getting Help

**Questions?**
- Check this guide first
- Review existing code examples
- Ask in team chat
- Create GitHub discussion

**Found a bug?**
- Create GitHub issue with reproduction steps
- Include `cortex deep --verbose` output
- Share your environment (OS, Python version)

---

**Ready to contribute?** Pick an issue labeled `good-first-issue` and dive in! 🚀
