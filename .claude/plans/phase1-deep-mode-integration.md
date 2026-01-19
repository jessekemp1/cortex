# Phase 1: Deep Mode Integration - Ultra-Detailed Implementation Plan

**Status**: Planning Complete
**Priority**: HIGH
**Timeline**: Week 1 (5-7 days)
**Complexity**: Medium
**Risk Level**: Low-Medium

---

## Table of Contents

1. [Strategic Context](#strategic-context)
2. [Architecture Analysis](#architecture-analysis)
3. [Integration Points](#integration-points)
4. [Implementation Steps](#implementation-steps)
5. [Testing Strategy](#testing-strategy)
6. [Risk Mitigation](#risk-mitigation)
7. [Rollout Plan](#rollout-plan)
8. [Success Criteria](#success-criteria)

---

## Strategic Context

### Why This Matters

Phase 1 integration is the **critical path** to realizing the depth-first architecture. Without CLI integration:
- Deep mode remains isolated prototype
- Users can't access comprehensive analysis
- No data to validate hypothesis (depth > speed)
- Can't measure recommendation accuracy improvements

### Current State Analysis

**Prototype Status**:
- ✅ `adaptive_latency.py` - Mode selection (412 LOC, complete)
- ✅ `deep_analysis.py` - Analysis engine (594 LOC, tested)
- ✅ Validated on Cortex project (7s, comprehensive results)

**Current User Experience** (without integration):
```bash
# User must run prototype directly
python intelligence/deep_analysis.py cortex

# Output goes to stdout, no integration with existing commands
# No mode selection, no preference saving
# Isolated from portfolio memory, spec search
```

**Target User Experience** (after integration):
```bash
# Natural CLI commands
cortex                  # Deep mode (default)
cortex deep             # Explicit deep mode
cortex quick            # Fast mode (opt-in)
cortex auto             # Adaptive mode

# Integration with existing commands
cortex next             # Uses deep analysis
cortex briefing         # Uses deep analysis
cortex status           # Uses deep analysis

# Preference management
cortex config set default-mode deep
cortex config set project vortex deep
```

---

## Architecture Analysis

### Current Architecture (Before Integration)

```
┌──────────────────────────────────────────────────────────┐
│                        CLI Layer                         │
│  cli.py (cortex command entry point)                     │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│                     Bridge Layer                          │
│  bridge.py (CortexBridge - unified API)                  │
│  - get_context()                                         │
│  - get_recommendation()                                   │
│  - get_session_context()                                 │
└───────────────────┬──────────────────────────────────────┘
                    │
         ┌──────────┼──────────┐
         │          │          │
         ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │Session │ │Portfolio│ │ Spec  │
    │Manager │ │ Memory │ │  KB   │
    └────────┘ └────────┘ └────────┘
    (cached)   (patterns)  (search)

ISSUE: No deep analysis mode, no adaptive latency
```

### Target Architecture (After Integration)

```
┌──────────────────────────────────────────────────────────┐
│                     CLI Layer (ENHANCED)                 │
│  cli.py + new commands                                   │
│  - cortex deep <project>                                 │
│  - cortex quick <project>                                │
│  - cortex auto <project>                                 │
│  - cortex config set default-mode <mode>                 │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│                Bridge Layer (ENHANCED)                    │
│  bridge.py with mode parameter                           │
│  - get_context(mode="deep")    ← NEW                    │
│  - query_intelligence(mode=...) ← MODIFIED               │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│           Adaptive Latency Manager (NEW)                 │
│  intelligence/adaptive_latency.py                        │
│  - select_mode(requested, context)                       │
│  - get_config_for_mode(mode)                             │
└──────────────┬──────────────────┬────────────────────────┘
               │                  │
        ┌──────┴──────┐    ┌──────┴──────┐
        │             │    │             │
        ▼             ▼    ▼             ▼
┌──────────────┐   ┌─────────────────────────┐
│  Fast Path   │   │    Deep Analysis (NEW)  │
│  (existing)  │   │  deep_analysis.py       │
│  - Session   │   │  - Comprehensive git    │
│  - Portfolio │   │  - Fresh health         │
│  - Spec KB   │   │  - Quality metrics      │
└──────────────┘   └─────────────────────────┘
                        │
                        ▼
                  ┌─────────────┐
                  │ Deep        │
                  │Intelligence │
                  │ (output)    │
                  └─────────────┘
```

---

## Integration Points

### 1. CLI Integration (`cli.py`)

**Current CLI Structure**:
```python
# cli.py (simplified)
@click.group()
def cli():
    """Cortex CLI"""
    pass

@cli.command()
def next():
    """Get next action"""
    bridge = CortexBridge()
    rec = bridge.get_recommendation()
    print(rec)

@cli.command()
def status():
    """Show status"""
    bridge = CortexBridge()
    status = bridge.get_status()
    print(status)
```

**Required Changes**:

#### A. Add Mode Commands

```python
# NEW: Mode-specific commands
@cli.command()
@click.argument('project', required=False)
@click.option('--json', is_flag=True, help='Output as JSON')
def deep(project, json):
    """Run deep portfolio analysis (comprehensive, 2-5s)"""
    bridge = CortexBridge()
    result = bridge.analyze_deep(project, output_json=json)
    if json:
        click.echo(result.to_json())
    else:
        display_deep_intelligence(result)

@cli.command()
@click.argument('project', required=False)
def quick(project):
    """Run quick analysis (minimal, <1s)"""
    bridge = CortexBridge()
    result = bridge.analyze_quick(project)
    display_quick_summary(result)

@cli.command()
@click.argument('project', required=False)
def auto(project):
    """Run adaptive analysis (intelligent mode selection)"""
    bridge = CortexBridge()
    result = bridge.analyze_auto(project)
    display_intelligence(result)
```

#### B. Add Config Commands

```python
# NEW: Configuration management
@cli.group()
def config():
    """Manage Cortex configuration"""
    pass

@config.command('set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """Set configuration value"""
    if key == 'default-mode':
        if value not in ['fast', 'deep', 'auto']:
            click.echo(f"Error: Invalid mode '{value}'", err=True)
            sys.exit(1)

        from intelligence.adaptive_latency import AdaptiveLatencyManager
        manager = AdaptiveLatencyManager()
        manager.set_default_preference(value)
        click.echo(f"✅ Default mode set to: {value}")

    elif key.startswith('project-mode:'):
        project = key.split(':', 1)[1]
        from intelligence.adaptive_latency import AdaptiveLatencyManager
        manager = AdaptiveLatencyManager()
        manager.set_project_preference(project, value)
        click.echo(f"✅ Project '{project}' mode set to: {value}")

    else:
        click.echo(f"Error: Unknown config key '{key}'", err=True)
        sys.exit(1)

@config.command('get')
@click.argument('key', required=False)
def config_get(key):
    """Get configuration value"""
    from intelligence.adaptive_latency import AdaptiveLatencyManager
    manager = AdaptiveLatencyManager()

    if key is None:
        # Show all
        prefs = manager.preferences
        click.echo(json.dumps(prefs, indent=2))
    else:
        # Show specific key
        if key == 'default-mode':
            click.echo(manager.preferences.get('default_mode', 'deep'))
        else:
            click.echo("Unknown key", err=True)
```

#### C. Modify Existing Commands

```python
# MODIFIED: Add --mode option to existing commands
@cli.command()
@click.option('--mode', type=click.Choice(['fast', 'deep', 'auto']), default='deep')
def next(mode):
    """Get next action"""
    bridge = CortexBridge()
    rec = bridge.get_recommendation(mode=mode)
    print(rec)

@cli.command()
@click.option('--mode', type=click.Choice(['fast', 'deep', 'auto']), default='deep')
def briefing(mode):
    """Generate daily briefing"""
    bridge = CortexBridge()
    briefing = bridge.generate_briefing(mode=mode)
    display_briefing(briefing)
```

**File**: `cli.py`
**LOC Impact**: +150 lines (commands + display functions)
**Breaking Changes**: None (backward compatible via defaults)

---

### 2. Bridge API Integration (`bridge.py`)

**Current Bridge Methods**:
```python
class CortexBridge:
    def get_context(self, query, limit=10):
        # Returns shallow context

    def get_recommendation(self, project=None):
        # Uses existing shallow analysis

    def query_intelligence(self, request, project, query_type):
        # Unified intelligence (no mode support)
```

**Required Changes**:

```python
class CortexBridge:
    """Enhanced with adaptive latency support"""

    def __init__(self, root_dir=None):
        self.root_dir = root_dir or Path("/Users/jesse.kemp/Dev")

        # Existing components
        self.orchestrator = CortexOrchestrator(root_dir)
        self.learning = LearningSystem()
        self.portfolio_memory = PortfolioMemory()

        # NEW: Adaptive latency components
        self.latency_manager = AdaptiveLatencyManager()
        self.deep_analyzer = DeepAnalyzer(root_dir)

    def analyze_deep(self, project=None, output_json=False):
        """
        Run comprehensive deep analysis.

        Args:
            project: Project name (auto-detect if None)
            output_json: Return JSON-serializable dict

        Returns:
            DeepIntelligence object or dict
        """
        from intelligence.deep_analysis import DeepAnalyzer
        from intelligence.adaptive_latency import DEEP_MODE

        # Auto-detect project if not specified
        if project is None:
            project = self._detect_current_project()

        # Get deep mode configuration
        config = self.latency_manager.select_mode(
            requested_mode=AnalysisMode.DEEP,
            context=None
        )

        # Run deep analysis
        result = self.deep_analyzer.analyze(project, config.__dict__)

        if output_json:
            return self._serialize_deep_intelligence(result)

        return result

    def analyze_quick(self, project=None):
        """
        Run minimal fast analysis.

        Returns existing shallow context for speed.
        """
        from intelligence.adaptive_latency import FAST_MODE

        if project is None:
            project = self._detect_current_project()

        # Use existing fast path
        context = self.orchestrator.get_context()
        return context

    def analyze_auto(self, project=None):
        """
        Run adaptive analysis with intelligent mode selection.

        Selects mode based on:
        - Time since last session
        - Project state (uncommitted changes, stale branches)
        - User preferences
        """
        from intelligence.adaptive_latency import AnalysisMode, SessionContext
        from datetime import datetime, timedelta

        if project is None:
            project = self._detect_current_project()

        # Build session context for mode selection
        session_ctx = self._build_session_context(project)

        # Select mode adaptively
        config = self.latency_manager.select_mode(
            requested_mode=AnalysisMode.AUTO,
            context=session_ctx
        )

        # Route to appropriate analysis
        if config.mode_name == "fast":
            return self.analyze_quick(project)
        else:
            return self.analyze_deep(project)

    def get_recommendation(self, project=None, mode="deep"):
        """
        Get next recommended action (ENHANCED with mode support).

        Args:
            project: Project name
            mode: Analysis mode ("fast", "deep", "auto")

        Returns:
            Recommendation object
        """
        # Route based on mode
        if mode == "deep":
            intelligence = self.analyze_deep(project)
            # Extract recommendations from deep intelligence
            return intelligence.recommendations[0] if intelligence.recommendations else None

        elif mode == "fast":
            # Use existing fast path
            return self.orchestrator.get_recommendation(project)

        else:  # auto
            intelligence = self.analyze_auto(project)
            return self._extract_recommendation(intelligence)

    def _detect_current_project(self):
        """Auto-detect current project from git repo"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                repo_path = Path(result.stdout.strip())
                return repo_path.name
        except Exception:
            pass
        return "cortex"  # Default

    def _build_session_context(self, project):
        """Build SessionContext for adaptive mode selection"""
        from intelligence.adaptive_latency import SessionContext
        from datetime import datetime

        # Check for uncommitted changes
        has_uncommitted = False
        branch_is_stale = False
        try:
            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.root_dir / project,
                capture_output=True,
                text=True,
                timeout=2
            )
            has_uncommitted = len(status_result.stdout.strip()) > 0
        except Exception:
            pass

        return SessionContext(
            last_session_time=None,  # TODO: Track last session
            time_since_last_session=None,
            project_name=project,
            has_uncommitted_changes=has_uncommitted,
            branch_is_stale=branch_is_stale,
            user_preference=None
        )

    def _serialize_deep_intelligence(self, intelligence):
        """Convert DeepIntelligence to JSON-serializable dict"""
        return {
            "timestamp": intelligence.timestamp.isoformat(),
            "project": intelligence.project,
            "mode": intelligence.mode,
            "latency_ms": intelligence.latency_ms,
            "health": {
                "score": intelligence.health.score,
                "assessment": intelligence.health.assessment,
                "trend": intelligence.health.trend,
                "commits_7d": intelligence.health.commits_7d,
                "commits_30d": intelligence.health.commits_30d,
                "uncommitted_files": intelligence.health.uncommitted_files,
            },
            "git": {
                "commit_count": intelligence.git.commit_count,
                "authors": intelligence.git.authors,
                "current_branch": intelligence.git.current_branch,
                "stale_branches": intelligence.git.stale_branches,
            },
            "quality": {
                "todos": intelligence.quality.todos,
                "fixmes": intelligence.quality.fixmes,
                "tech_debt_markers": intelligence.quality.tech_debt_markers,
            },
            "warnings": intelligence.warnings,
            "recommendations": intelligence.recommendations,
            "next_actions": intelligence.next_actions,
        }
```

**File**: `bridge.py`
**LOC Impact**: +200 lines (new methods + integration)
**Breaking Changes**: None (existing methods preserved)

---

### 3. Display Layer (NEW: `cli_display.py`)

Create formatted output for deep intelligence:

```python
"""CLI display formatters for Cortex intelligence"""

import click
from datetime import datetime


def display_deep_intelligence(intelligence):
    """
    Display comprehensive deep intelligence in terminal.

    Args:
        intelligence: DeepIntelligence object
    """
    # Header
    click.secho(f"\n{'='*60}", fg='cyan')
    click.secho(f" Deep Portfolio Intelligence: {intelligence.project}", fg='cyan', bold=True)
    click.secho(f"{'='*60}\n", fg='cyan')

    # Analysis metadata
    click.echo(f"Analysis time: {intelligence.latency_ms:.0f}ms")
    click.echo(f"Mode: {intelligence.mode}")
    click.echo(f"Timestamp: {intelligence.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Health Score
    color = 'green' if intelligence.health.score >= 80 else 'yellow' if intelligence.health.score >= 60 else 'red'
    click.secho(f"🏥 Health Score: {intelligence.health.score}/100", fg=color, bold=True)
    click.echo(f"   Assessment: {intelligence.health.assessment.upper()}")
    click.echo(f"   Trend: {intelligence.health.trend}")
    click.echo(f"   Activity: {intelligence.health.commits_7d} commits (7d), {intelligence.health.commits_30d} commits (30d)")
    click.echo(f"   Uncommitted: {intelligence.health.uncommitted_files} files\n")

    # Git Overview
    click.secho("📊 Git Analysis", fg='blue', bold=True)
    click.echo(f"   Commits analyzed: {intelligence.git.commit_count} ({intelligence.git.days_analyzed} days)")
    click.echo(f"   Contributors: {len(intelligence.git.authors)}")
    click.echo(f"   Current branch: {intelligence.git.current_branch}")
    if intelligence.git.stale_branches:
        click.echo(f"   ⚠️  Stale branches: {len(intelligence.git.stale_branches)}")

    # Code Quality
    if intelligence.quality.tech_debt_markers > 0:
        click.echo(f"\n💻 Code Quality")
        click.echo(f"   TODOs: {intelligence.quality.todos}")
        click.echo(f"   FIXMEs: {intelligence.quality.fixmes}")
        click.echo(f"   Total tech debt markers: {intelligence.quality.tech_debt_markers}")

    # Warnings
    if intelligence.warnings:
        click.echo(f"\n⚠️  Warnings ({len(intelligence.warnings)}):")
        for warning in intelligence.warnings:
            click.secho(f"   • {warning}", fg='yellow')

    # Recommendations
    if intelligence.recommendations:
        click.echo(f"\n💡 Recommendations ({len(intelligence.recommendations)}):")
        for i, rec in enumerate(intelligence.recommendations, 1):
            priority_color = 'red' if rec['priority'] == 'high' else 'yellow' if rec['priority'] == 'medium' else 'blue'
            click.echo(f"\n   {i}. ", nl=False)
            click.secho(f"[{rec['priority'].upper()}]", fg=priority_color, bold=True, nl=False)
            click.echo(f" {rec['title']}")
            click.echo(f"      {rec['rationale']}")

    # Next Actions
    if intelligence.next_actions:
        click.echo(f"\n🎯 Next Actions:")
        for i, action in enumerate(intelligence.next_actions, 1):
            click.secho(f"   {i}. {action}", fg='green', bold=True)

    click.echo(f"\n{'='*60}\n")


def display_quick_summary(context):
    """Display minimal quick analysis"""
    click.secho("\n⚡ Quick Analysis", fg='cyan', bold=True)
    # Display basic context info
    click.echo(f"Project: {context.get('project', 'unknown')}")
    click.echo(f"Status: {context.get('status', 'unknown')}\n")
```

**File**: `intelligence/cli_display.py` (NEW)
**LOC**: ~150 lines
**Purpose**: Clean separation of display logic

---

## Implementation Steps

### Step 1: Bridge API Enhancement (Day 1-2)

**Goal**: Add mode support to bridge.py

**Tasks**:
1. Add `AdaptiveLatencyManager` initialization to `__init__`
2. Add `DeepAnalyzer` initialization to `__init__`
3. Implement `analyze_deep()` method
4. Implement `analyze_quick()` method
5. Implement `analyze_auto()` method
6. Modify `get_recommendation()` to accept mode parameter
7. Add `_detect_current_project()` helper
8. Add `_build_session_context()` helper
9. Add `_serialize_deep_intelligence()` helper

**Testing**:
```python
# Test script: test_bridge_integration.py
from bridge import CortexBridge

bridge = CortexBridge()

# Test deep mode
print("Testing deep mode...")
result = bridge.analyze_deep("cortex")
assert result is not None
assert result.mode == "deep"
assert result.latency_ms > 0
print(f"✅ Deep mode works ({result.latency_ms}ms)")

# Test quick mode
print("Testing quick mode...")
result = bridge.analyze_quick("cortex")
assert result is not None
print("✅ Quick mode works")

# Test auto mode
print("Testing auto mode...")
result = bridge.analyze_auto("cortex")
assert result is not None
print("✅ Auto mode works")
```

**Success Criteria**:
- All three modes callable via bridge
- Deep mode returns DeepIntelligence object
- Quick mode returns existing context
- Auto mode selects intelligently
- No breaking changes to existing API

---

### Step 2: CLI Integration (Day 2-3)

**Goal**: Add deep/quick/auto/config commands

**Tasks**:
1. Create `intelligence/cli_display.py` with formatters
2. Add `cortex deep` command to cli.py
3. Add `cortex quick` command to cli.py
4. Add `cortex auto` command to cli.py
5. Add `cortex config` group to cli.py
6. Add `cortex config set` command
7. Add `cortex config get` command
8. Modify existing commands to accept --mode option
9. Update CLI help text

**Testing**:
```bash
# Manual testing checklist
cortex deep cortex              # Should run deep analysis
cortex quick cortex             # Should run quick analysis
cortex auto cortex              # Should select mode adaptively
cortex config set default-mode deep  # Should save preference
cortex config get default-mode  # Should show "deep"
cortex next --mode=deep         # Should use deep mode
cortex briefing --mode=deep     # Should use deep mode
```

**Success Criteria**:
- New commands work without errors
- Output is well-formatted and readable
- Config persistence works
- Backward compatibility maintained (existing commands unchanged)

---

### Step 3: Integration Testing (Day 3-4)

**Goal**: Ensure all pieces work together

**Create test suite**:
```python
# tests/integration/test_deep_mode_integration.py

def test_end_to_end_deep_mode():
    """Test complete deep mode flow"""
    # 1. Run deep analysis via CLI
    result = subprocess.run(
        ["cortex", "deep", "cortex", "--json"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0

    # 2. Parse output
    data = json.loads(result.stdout)
    assert "health" in data
    assert "git" in data
    assert "recommendations" in data

    # 3. Verify analysis quality
    assert data["latency_ms"] > 1000  # Deep mode should be slower
    assert data["git"]["commit_count"] > 5  # More than fast mode

def test_mode_preference_persistence():
    """Test config persistence"""
    # Set preference
    subprocess.run(["cortex", "config", "set", "default-mode", "deep"])

    # Verify saved
    from intelligence.adaptive_latency import AdaptiveLatencyManager
    manager = AdaptiveLatencyManager()
    assert manager.preferences["default_mode"] == "deep"

def test_adaptive_mode_selection():
    """Test auto mode selects intelligently"""
    bridge = CortexBridge()

    # Mock session context with uncommitted changes
    result = bridge.analyze_auto("cortex")

    # Should select deep mode when uncommitted changes present
    assert result.mode in ["deep", "balanced"]
```

**Tasks**:
1. Create integration test suite
2. Test all CLI commands
3. Test bridge API methods
4. Test mode selection logic
5. Test config persistence
6. Test backward compatibility
7. Run tests on multiple projects

**Success Criteria**:
- All integration tests pass
- No regressions in existing functionality
- Mode selection works correctly
- Config persistence works

---

### Step 4: Documentation & Examples (Day 4-5)

**Goal**: Make it easy for users to adopt

**Create docs**:

1. **User Guide** (`docs/user_guide/deep_mode.md`):
```markdown
# Deep Mode User Guide

## What is Deep Mode?

Deep mode performs comprehensive portfolio analysis that includes:
- 90 days of git history (vs 5 commits in fast mode)
- Fresh health calculation (no caching)
- Automatic spec search (top 5 relevant specs)
- Code quality metrics (TODOs, FIXMEs, tech debt)
- Proactive warnings and recommendations

## When to Use Each Mode

**Deep Mode** (2-5s startup):
- Morning session start
- After being away from project >1 hour
- When you need comprehensive intelligence
- **DEFAULT mode**

**Quick Mode** (<1s startup):
- Rapid context switches
- Quick status checks
- When you just need basic info

**Auto Mode** (adaptive):
- Let Cortex decide based on context
- Learns from your usage patterns

## Usage

```bash
# Deep mode (default)
cortex
cortex deep
cortex deep vortex

# Quick mode
cortex quick
cortex quick alpha_arena

# Auto mode (intelligent selection)
cortex auto

# Set preferences
cortex config set default-mode deep
cortex config set project-mode:vortex deep
```

## Output Explained

Deep mode provides:
- **Health Score**: 0-100 score with trend analysis
- **Git Analysis**: Full commit history, contributors, branches
- **Code Quality**: Technical debt markers
- **Warnings**: Issues detected proactively
- **Recommendations**: Prioritized action items
- **Next Actions**: Concrete next steps
```

2. **Developer Guide** (`docs/developer/deep_mode_architecture.md`):
```markdown
# Deep Mode Architecture

## Component Overview

[Diagram of adaptive_latency.py + deep_analysis.py + bridge.py]

## Extending Deep Analysis

To add new analyses to deep mode:

1. Add analysis method to `DeepAnalyzer`:
```python
def _analyze_security(self, project_path, config):
    # Your analysis logic
    return SecurityAnalysis(...)
```

2. Call in `analyze()` method:
```python
def analyze(self, project, config):
    # ... existing analyses
    security = self._analyze_security(project_path, config)
    return DeepIntelligence(..., security=security)
```

3. Update display formatter in `cli_display.py`
```

3. **Migration Guide** (`docs/MIGRATION.md`):
```markdown
# Migrating to Depth-First Architecture

## What Changed

### New Default: Deep Mode

Previous default: Fast mode (500ms, shallow)
New default: Deep mode (2-5s, comprehensive)

### Why This Matters

Deep mode eliminates the need for follow-up queries. Instead of:
1. Start session (500ms)
2. Ask "What should I work on?" (2s)
3. Ask "What's blocking me?" (2s)
4. Ask "What patterns apply?" (2s)
**Total: 6.5 seconds**

You now get:
1. Start session with deep mode (5s) - includes all above
**Total: 5 seconds (net time savings)**

### Backward Compatibility

All existing commands work unchanged. Use `--mode=fast` if you need the old behavior.

## Gradual Adoption

### Week 1: Try It
```bash
cortex deep    # Explicit deep mode
```

### Week 2: Set as Default
```bash
cortex config set default-mode deep
```

### Week 3: Project-Specific
```bash
cortex config set project-mode:vortex deep
cortex config set project-mode:small-project quick
```
```

**Tasks**:
1. Write user guide
2. Write developer guide
3. Write migration guide
4. Add examples to README
5. Create video demo (optional)
6. Update CLI help text

**Success Criteria**:
- Clear documentation exists
- Users understand when to use each mode
- Developers can extend deep analysis
- Migration path is clear

---

### Step 5: Rollout (Day 5-7)

**Goal**: Safe, gradual rollout

**Rollout Phases**:

#### Phase A: Opt-In (Days 5-6)
- Deep mode available via `cortex deep`
- Default remains unchanged (fast mode)
- Monitor usage and feedback
- Fix any bugs found

**Metrics to Track**:
- Deep mode invocations per day
- Average latency
- User feedback (manual)
- Error rates

#### Phase B: Default Switch (Day 7)
- Change default to deep mode
- Fast mode still available via `cortex quick` or `--mode=fast`
- Monitor adoption

**Metrics to Track**:
- Percentage using deep mode (should be >80%)
- Percentage manually opting to fast mode
- Average session satisfaction
- Recommendation acceptance rate

#### Phase C: Optimization (Week 2)
- Based on Phase A/B data, optimize slow operations
- Add caching only where proven necessary
- Tune mode selection heuristics

---

## Testing Strategy

### Unit Tests

**Target Coverage**: 80%+

**Key Test Files**:

1. `tests/unit/test_adaptive_latency.py`:
```python
def test_mode_selection_with_recent_session():
    """Auto mode should select balanced for recent sessions"""
    manager = AdaptiveLatencyManager()
    context = SessionContext(
        time_since_last_session=timedelta(minutes=3),
        has_uncommitted_changes=False,
        ...
    )
    config = manager._select_auto_mode(context)
    assert config.mode_name in ["fast", "balanced"]

def test_mode_selection_with_uncommitted_changes():
    """Auto mode should select deep for uncommitted work"""
    manager = AdaptiveLatencyManager()
    context = SessionContext(
        has_uncommitted_changes=True,
        ...
    )
    config = manager._select_auto_mode(context)
    assert config.mode_name == "deep"
```

2. `tests/unit/test_deep_analysis.py`:
```python
def test_deep_analysis_git_parsing():
    """Deep analyzer should parse git history correctly"""
    analyzer = DeepAnalyzer(test_repo_path)
    config = {"git_days": 30, "git_include_stats": True}
    git_analysis = analyzer._analyze_git(test_repo_path, config)

    assert git_analysis.commit_count > 0
    assert len(git_analysis.authors) > 0
    assert git_analysis.current_branch is not None

def test_health_calculation():
    """Health scoring should be consistent"""
    analyzer = DeepAnalyzer(test_repo_path)
    git_data = analyzer._analyze_git(test_repo_path, {"git_days": 30})
    health = analyzer._analyze_health(git_data, {})

    assert 0 <= health.score <= 100
    assert health.assessment in ["excellent", "good", "fair", "poor"]
```

3. `tests/unit/test_bridge_modes.py`:
```python
def test_bridge_deep_mode():
    """Bridge should route deep mode correctly"""
    bridge = CortexBridge()
    result = bridge.analyze_deep("test_project")

    assert isinstance(result, DeepIntelligence)
    assert result.mode == "deep"
    assert result.latency_ms > 0

def test_bridge_mode_parameter_propagation():
    """Mode parameter should propagate through bridge"""
    bridge = CortexBridge()

    # Mock recommendation with deep mode
    rec = bridge.get_recommendation(mode="deep")
    # Should trigger deep analysis path
```

### Integration Tests

**Coverage**: End-to-end flows

```python
def test_cli_deep_command():
    """CLI deep command should work end-to-end"""
    result = subprocess.run(
        ["cortex", "deep", "test_project"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Health Score:" in result.stdout
    assert "Recommendations:" in result.stdout

def test_config_persistence():
    """Config changes should persist across sessions"""
    # Set config
    subprocess.run(["cortex", "config", "set", "default-mode", "deep"])

    # Verify persisted
    manager = AdaptiveLatencyManager()
    assert manager.preferences["default_mode"] == "deep"

    # Clean up
    subprocess.run(["cortex", "config", "set", "default-mode", "auto"])
```

### Performance Tests

**Goal**: Verify latency targets

```python
def test_deep_mode_latency():
    """Deep mode should complete within 10s"""
    import time

    bridge = CortexBridge()
    start = time.time()
    result = bridge.analyze_deep("cortex")
    elapsed = time.time() - start

    assert elapsed < 10.0, f"Deep mode too slow: {elapsed}s"
    assert elapsed > 1.0, "Deep mode suspiciously fast"

def test_quick_mode_latency():
    """Quick mode should complete within 2s"""
    import time

    bridge = CortexBridge()
    start = time.time()
    result = bridge.analyze_quick("cortex")
    elapsed = time.time() - start

    assert elapsed < 2.0, f"Quick mode too slow: {elapsed}s"
```

---

## Risk Mitigation

### Risk 1: Deep Mode Too Slow for Large Projects

**Likelihood**: Medium
**Impact**: High
**Mitigation**:
- Add timeout protection (max 15s)
- Implement progress indicators for long operations
- Add project-size-based heuristics
- Allow per-project latency tuning

**Detection**:
- Monitor P95 latency across projects
- Track user complaints about slowness

**Fallback**:
- Auto-downgrade to balanced mode for large projects
- Add `--timeout` option to CLI

---

### Risk 2: Integration Breaks Existing Workflows

**Likelihood**: Low
**Impact**: High
**Mitigation**:
- Maintain backward compatibility (all existing commands work)
- Add integration tests for existing workflows
- Gradual rollout (opt-in first)
- Clear migration documentation

**Detection**:
- Run full test suite on existing commands
- Monitor error rates after rollout

**Rollback Plan**:
- Keep fast mode as fallback
- Can revert default mode via single line change

---

### Risk 3: Mode Selection Logic Suboptimal

**Likelihood**: Medium
**Impact**: Low
**Mitigation**:
- Start with conservative heuristics
- Log mode selection decisions + outcomes
- Iterate based on data
- Allow user overrides

**Improvement Plan**:
- Track: mode selected, user satisfaction, recommendation accuracy
- Monthly review of heuristics
- Add machine learning later (Phase 3+)

---

## Rollout Plan

### Pre-Rollout Checklist

- [ ] All unit tests pass (target: 80%+ coverage)
- [ ] All integration tests pass
- [ ] Performance tests validate latency targets
- [ ] Documentation complete
- [ ] Migration guide ready
- [ ] Rollback plan documented

### Day 1-3: Internal Testing

- Deploy to development environment
- Test with real projects (cortex, vortex, alpha_arena)
- Fix critical bugs
- Refine display formatting

### Day 4-5: Opt-In Rollout

- Deploy to production with deep mode as opt-in
- Default remains unchanged (fast mode)
- Monitor usage: `cortex deep` invocations
- Collect feedback

### Day 6: Pre-Default-Switch Validation

- Review metrics from opt-in phase:
  - Error rate < 1%
  - Average latency < 7s
  - User feedback positive
- Fix any remaining issues

### Day 7: Default Switch

- Change default mode to deep
- Fast mode remains available
- Announce change via changelog
- Monitor adoption metrics

### Week 2: Optimization

- Analyze performance data
- Optimize slow operations
- Tune mode selection heuristics
- Document learnings

---

## Success Criteria

### Must-Have (Phase 1 Complete)

- [ ] ✅ Deep mode accessible via CLI (`cortex deep`)
- [ ] ✅ Quick mode accessible via CLI (`cortex quick`)
- [ ] ✅ Auto mode accessible via CLI (`cortex auto`)
- [ ] ✅ Config management works (`cortex config set/get`)
- [ ] ✅ Bridge API supports all three modes
- [ ] ✅ Backward compatibility maintained (no breaking changes)
- [ ] ✅ Unit tests pass (80%+ coverage)
- [ ] ✅ Integration tests pass
- [ ] ✅ Documentation complete

### Should-Have (Nice to Have)

- [ ] Progress indicators for deep analysis
- [ ] JSON output mode for scripting
- [ ] Mode selection logging for tuning
- [ ] Performance profiling data

### Won't-Have (Future Phases)

- ❌ Spec search integration (Phase 3)
- ❌ Pattern matching integration (Phase 3)
- ❌ Dependency graph analysis (Phase 3)
- ❌ Machine learning mode selection (Phase 4+)

---

## Metrics & Monitoring

### Key Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Deep mode latency P50 | <5s | Log analysis |
| Deep mode latency P95 | <10s | Log analysis |
| Quick mode latency P95 | <2s | Log analysis |
| Error rate | <1% | Error logs |
| Deep mode adoption | >80% | Usage analytics |
| User satisfaction | >7/10 | Manual feedback |

### Monitoring Plan

**Week 1**:
- Daily review of error logs
- Track mode invocations
- Collect latency data
- Manual user feedback

**Week 2-4**:
- Weekly metrics review
- Compare recommendation accuracy (fast vs deep)
- Tune heuristics based on data

**Ongoing**:
- Monthly health check
- Quarterly architecture review

---

## Implementation Checklist

### Week 1, Day 1-2: Bridge Integration

- [ ] Add `AdaptiveLatencyManager` to bridge.py `__init__`
- [ ] Add `DeepAnalyzer` to bridge.py `__init__`
- [ ] Implement `analyze_deep()` method
- [ ] Implement `analyze_quick()` method
- [ ] Implement `analyze_auto()` method
- [ ] Modify `get_recommendation()` for mode support
- [ ] Add helper methods (_detect_project, _build_context, _serialize)
- [ ] Write unit tests for bridge methods
- [ ] Test manually with test script

### Week 1, Day 2-3: CLI Integration

- [ ] Create `intelligence/cli_display.py`
- [ ] Implement `display_deep_intelligence()`
- [ ] Implement `display_quick_summary()`
- [ ] Add `cortex deep` command to cli.py
- [ ] Add `cortex quick` command to cli.py
- [ ] Add `cortex auto` command to cli.py
- [ ] Add `cortex config` group
- [ ] Add `cortex config set` command
- [ ] Add `cortex config get` command
- [ ] Update existing commands with --mode option
- [ ] Update CLI help text
- [ ] Test all CLI commands manually

### Week 1, Day 3-4: Integration Testing

- [ ] Create integration test suite
- [ ] Write test_end_to_end_deep_mode()
- [ ] Write test_mode_preference_persistence()
- [ ] Write test_adaptive_mode_selection()
- [ ] Write test_cli_commands()
- [ ] Write test_backward_compatibility()
- [ ] Run full test suite
- [ ] Fix any failing tests

### Week 1, Day 4-5: Documentation

- [ ] Write user guide (deep_mode.md)
- [ ] Write developer guide (deep_mode_architecture.md)
- [ ] Write migration guide
- [ ] Update README.md
- [ ] Add examples
- [ ] Update CLI help text

### Week 1, Day 5-7: Rollout

- [ ] Deploy to dev environment
- [ ] Internal testing (cortex, vortex, alpha_arena)
- [ ] Fix critical bugs
- [ ] Deploy to production (opt-in)
- [ ] Monitor metrics
- [ ] Switch default to deep mode
- [ ] Final validation

---

## Follow-Up Actions (Phase 2)

After Phase 1 is complete and stable:

1. **Remove Speed Optimizations** (Week 2)
   - Remove health tracker cache
   - Remove session manager cache
   - Simplify lazy loading
   - Convert unnecessary async to sync

2. **Enhance Deep Analysis** (Week 3-4)
   - Integrate SpecKnowledgeBase
   - Integrate PortfolioMemory
   - Add dependency graph analysis
   - Add linting integration
   - Add test coverage integration

3. **Make Deep Default Permanent** (Week 4)
   - Update documentation
   - Announce architectural shift
   - Celebrate simplification wins

---

## Appendix: Code Snippets

### A. Complete CLI Integration Snippet

```python
# cli.py additions

@cli.command()
@click.argument('project', required=False)
@click.option('--json', is_flag=True)
def deep(project, json):
    """Comprehensive portfolio analysis (2-5s, deep intelligence)"""
    from bridge import CortexBridge
    from intelligence.cli_display import display_deep_intelligence

    bridge = CortexBridge()
    result = bridge.analyze_deep(project, output_json=json)

    if json:
        click.echo(json.dumps(result, indent=2))
    else:
        display_deep_intelligence(result)

@cli.command()
@click.argument('project', required=False)
def quick(project):
    """Minimal fast analysis (<1s, basic context)"""
    from bridge import CortexBridge

    bridge = CortexBridge()
    result = bridge.analyze_quick(project)
    click.echo(f"Project: {result.get('project', 'unknown')}")
    click.echo(f"Status: {result.get('status', 'unknown')}")

@cli.group()
def config():
    """Configuration management"""
    pass

@config.command('set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """Set configuration value"""
    from intelligence.adaptive_latency import AdaptiveLatencyManager

    manager = AdaptiveLatencyManager()

    if key == 'default-mode':
        manager.set_default_preference(value)
        click.echo(f"✅ Default mode: {value}")
    elif key.startswith('project-mode:'):
        project = key.split(':', 1)[1]
        manager.set_project_preference(project, value)
        click.echo(f"✅ {project} mode: {value}")
```

---

**Plan Status**: ✅ **COMPLETE & READY FOR IMPLEMENTATION**

**Next Step**: Begin Day 1-2 tasks (Bridge Integration)

---

*Last Updated: 2026-01-18*
*Plan Version: 1.0 (Ultra-Detailed)*
