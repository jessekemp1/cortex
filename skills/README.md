# Cortex Skills Framework

**Domain-specific automation and expertise for active projects**

## Overview

Cortex skills provide automated validation, testing, and report generation across your top 3 active projects (VortexV2, alpha_arena, DJ-CoPilot). Skills run on schedule or via CLI, storing results in both cortex logs and project directories.

**Current Status**: 3 skills implemented (Phase 1)
**Expected Time Savings**: 10-13 hours/week (Phase 1), 21-28 hours/week (all 8 skills)

---

## Quick Start

### List Available Skills
```bash
./cortex skill list
```

### Run a Skill
```bash
# Validate VortexV2 system
./cortex skill run forecasting_validation_expert

# Generate alpha_arena E2E report
./cortex skill run trading_system_e2e_reporter --symbol SPY --days 90

# Process DJ tracks
./cortex skill run audio_processing_orchestrator --directory downloads
```

### View Skill Details
```bash
./cortex skill info forecasting_validation_expert
```

### Run Scheduled Skills
```bash
# Execute all skills that are due to run
./cortex skill schedule
```

---

## Implemented Skills

### 1. Forecasting Validation Expert
**Project**: VortexV2 (Marine Weather Forecasting)
**Priority**: CRITICAL
**Schedule**: Every 6 hours + on startup
**Time Savings**: 2-3 hours/week

**Purpose**: Automate GRIB data validation, forecast accuracy testing, ensemble model verification, and API performance benchmarking.

**What It Validates**:
- GRIB data freshness (< 12 hours old)
- Ensemble model weights (LSTM 48%, GFS 36%, HRRR 13%)
- API performance (forecast endpoint < 5s target)
- Scheduler health (6 jobs)

**Critical Issue Solved**: Diagnoses VortexV2 API timeout (>30s) and suggests caching solutions.

**Usage**:
```bash
# Full validation
./cortex skill run forecasting_validation_expert

# API-only validation
./cortex skill run forecasting_validation_expert --scope api

# GRIB-only validation
./cortex skill run forecasting_validation_expert --scope grib
```

**Output**:
- Report: `Vortex/VortexV2/reports/skills/vortex_validation_YYYYMMDD_HHMMSS.md`
- Log: `cortex/logs/skills/forecasting_validation_expert_YYYYMMDD_HHMMSS.json`

---

### 2. Trading System E2E Reporter
**Project**: alpha_arena (Trading Intelligence)
**Priority**: HIGH
**Schedule**: Daily
**Time Savings**: 3-4 hours/week

**Purpose**: Generate comprehensive E2E test reports comparing historical vs live trading performance with automated grading.

**What It Tests**:
- 90-day historical backtest validation
- 5 use cases (forecasting, nowcasting, macro, pattern, integrated)
- Trading metrics (win rate, profit factor, Sharpe, max drawdown)
- Automated grading (A-F scale)

**Success Criteria**:
- Win Rate: >=60%
- Profit Factor: >=2.0
- Sharpe Ratio: >=1.5
- Max Drawdown: <15%

**Usage**:
```bash
# Generate E2E report for SPY
./cortex skill run trading_system_e2e_reporter --symbol SPY --days 90

# Quick test
./cortex skill run trading_system_e2e_reporter
```

**Output**:
- Report: `alpha_arena/reports/skills/alpha_arena_e2e_YYYYMMDD_HHMMSS.md`
- Log: `cortex/logs/skills/trading_system_e2e_reporter_YYYYMMDD_HHMMSS.json`

---

### 3. Audio Processing Orchestrator
**Project**: DJ-CoPilot (Audio Processing)
**Priority**: MEDIUM
**Schedule**: Disabled (on-demand only)
**Time Savings**: 5-6 hours/week

**Purpose**: Automate batch loop extraction, stem separation with graceful fallback, and Camelot key organization.

**What It Does**:
- Batch loop extraction (4/8/16/32/64 bar loops)
- Stem separation with fallback (Demucs → full mix if torchcodec fails)
- Camelot key detection (1A-12A, 1B-12B)
- FL Studio Akai Fire pad mapping

**Processing Benchmarks**:
- 150 tracks: 2-3 hours
- 6,032 loops extracted
- 100% success rate (full mix fallback)

**Usage**:
```bash
# Process Beast Mode playlist
./cortex skill run audio_processing_orchestrator --directory downloads

# Process specific directory
./cortex skill run audio_processing_orchestrator --directory my_playlist
```

**Output**:
- Report: `DJ-CoPilot/reports/skills/dj_processing_YYYYMMDD_HHMMSS.md`
- Log: `cortex/logs/skills/audio_processing_orchestrator_YYYYMMDD_HHMMSS.json`

---

## Scheduling

Skills can run automatically on schedule. Configuration is defined in each skill's `schedule` property.

### Current Schedule
- **Forecasting Validation Expert**: Every 6 hours + on startup
- **Trading E2E Reporter**: Daily (24 hours)
- **Audio Processing**: Manual only

### Running Scheduled Skills
```bash
# Run all skills that are due
./cortex skill schedule
```

### Integration with Cron
Add to your crontab to run scheduled skills automatically:
```bash
# Run cortex skills every hour
0 * * * * cd /Users/jesse.kemp/Dev/cortex && ./cortex skill schedule >> logs/skill_scheduler.log 2>&1
```

---

## Architecture

### Skill Lifecycle

1. **Registration**: Skills register with `SkillRegistry` on import
2. **Trigger**: Skills triggered by CLI command or scheduler
3. **Execution**: Skill's `execute()` method runs asynchronously
4. **Results**: `SkillResult` generated with status, details, issues, recommendations
5. **Storage**: Results stored in cortex logs + project reports directory
6. **Recording**: Execution metadata tracked (last_run, run_count)

### File Structure
```
cortex/skills/
├── __init__.py                      # Registry initialization
├── base.py                          # Base Skill class, SkillResult
├── registry.py                      # SkillRegistry for management
├── forecasting_validation.py        # VortexV2 validation skill
├── trading_e2e_reporter.py         # alpha_arena E2E testing skill
├── audio_processing.py             # DJ-CoPilot audio processing skill
└── README.md                       # This file

cortex/logs/skills/                 # Execution logs (JSON)
{project}/reports/skills/           # Skill reports (Markdown)
```

### Skill Components

**Metadata Properties**:
- `name`, `display_name`, `version`
- `project`, `domain`, `priority`
- `trigger_patterns`, `schedule`
- `time_savings_per_week`, `dependencies`

**Execution Method**:
- `async def execute(**kwargs) -> SkillResult`

**Helper Methods**:
- `matches_trigger(text)`: Check if text triggers skill
- `should_run_scheduled()`: Check if skill should run
- `get_report_path()`: Get project-specific report path

---

## Development

### Adding a New Skill

1. **Create Skill Class** (`cortex/skills/my_skill.py`):
```python
from .base import Skill, SkillResult, SkillStatus, SkillPriority, SkillSchedule
from typing import List

class MySkill(Skill):
    @property
    def name(self) -> str:
        return "my_skill"

    @property
    def display_name(self) -> str:
        return "My Skill"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def project(self) -> str:
        return "MyProject"

    @property
    def domain(self) -> str:
        return "My Domain"

    @property
    def priority(self) -> SkillPriority:
        return SkillPriority.MEDIUM

    @property
    def description(self) -> str:
        return "Brief description"

    @property
    def trigger_patterns(self) -> List[str]:
        return ["trigger phrase 1", "trigger phrase 2"]

    @property
    def schedule(self) -> SkillSchedule:
        return SkillSchedule(
            enabled=True,
            interval_hours=24,  # Daily
        )

    @property
    def time_savings_per_week(self) -> str:
        return "2-3 hours"

    async def execute(self, **kwargs) -> SkillResult:
        # Implement skill logic
        return SkillResult(
            status=SkillStatus.SUCCESS,
            summary="Success summary",
            details={},
            recommendations=[],
            report_path=self.get_report_path("my_report.md"),
            execution_time=0.0,
        )
```

2. **Register Skill** (add to `cortex/skills/__init__.py`):
```python
from .my_skill import MySkill

registry.register(MySkill())
```

3. **Test Skill**:
```bash
./cortex skill run my_skill
```

### Skill Best Practices

- **Async Execution**: All skills run asynchronously
- **Error Handling**: Wrap execution in try/except, return FAILED status
- **Comprehensive Details**: Include all relevant metrics in `details` dict
- **Actionable Recommendations**: Provide specific, implementable next steps
- **Dual Storage**: Results go to both cortex logs and project directories
- **Execution Time**: Always measure and report execution time

---

## Planned Skills (Phases 2-3)

### Phase 2: Workflow Automation
- **GRIB Data Pipeline Monitor** (VortexV2) - 1-2 hrs/week
- **Test Suite Orchestrator** (All projects) - 2-3 hrs/week

### Phase 3: Intelligence & Optimization
- **Performance Profiler** (VortexV2, alpha_arena) - 3-4 hrs/incident
- **Project Intelligence Analyzer** (All projects) - 2-3 hrs/week
- **Dependency Update Scout** (All projects) - 1-2 hrs/week

---

## Integration with Cortex

Skills integrate seamlessly with cortex's core intelligence:

- **Recommendations**: Skills can be triggered by cortex recommendations
- **Context**: Skills access project context via cortex intelligence
- **Feedback Loop**: Skill results feed back into cortex learning system
- **Scheduling**: Cortex scheduler manages skill execution
- **Logging**: Unified logging to cortex intelligence logs

---

## Troubleshooting

### Skill Not Found
```bash
./cortex skill list  # Verify skill is registered
```

### Import Errors
```bash
cd cortex
python -c "from skills import registry; print(len(registry._skills))"
```

### Permission Errors on Reports
```bash
# Ensure report directories exist
mkdir -p Vortex/VortexV2/reports/skills
mkdir -p alpha_arena/reports/skills
mkdir -p DJ-CoPilot/reports/skills
```

### Async Errors
Skills must use `async def execute()`. CLI handles async execution automatically.

---

## API Reference

### SkillResult
```python
@dataclass
class SkillResult:
    status: SkillStatus  # SUCCESS, PARTIAL, FAILED, SKIPPED
    summary: str  # One-line summary
    details: Dict[str, Any]  # Detailed metrics/data
    issues: List[Dict[str, Any]]  # Issues found (severity, message, location)
    recommendations: List[str]  # Actionable next steps
    report_path: Optional[Path]  # Path to markdown report
    execution_time: float  # Seconds

    def to_dict() -> Dict
    def to_markdown() -> str
```

### SkillSchedule
```python
@dataclass
class SkillSchedule:
    enabled: bool = False
    cron_expression: Optional[str] = None  # e.g., "0 */6 * * *"
    interval_hours: Optional[int] = None   # Alternative to cron
    run_on_startup: bool = False

    def should_run(last_run: Optional[datetime]) -> bool
```

### SkillRegistry
```python
registry.register(skill: Skill)
registry.get(name: str) -> Optional[Skill]
registry.get_all() -> List[Skill]
registry.get_by_project(project: str) -> List[Skill]
registry.get_scheduled() -> List[Skill]
registry.find_by_trigger(text: str) -> List[Skill]
await registry.execute_skill(name: str, **kwargs) -> SkillResult
await registry.execute_scheduled() -> List[SkillResult]
```

---

## Examples

### Morning Validation Routine
```bash
# Run forecasting validation
./cortex skill run forecasting_validation_expert

# If issues found, run detailed scopes
./cortex skill run forecasting_validation_expert --scope api
./cortex skill run forecasting_validation_expert --scope grib
```

### Weekly Trading Analysis
```bash
# Generate comprehensive E2E report
./cortex skill run trading_system_e2e_reporter --symbol SPY --days 90

# Check recent report
cat alpha_arena/reports/skills/alpha_arena_e2e_*.md | tail -100
```

### Playlist Processing
```bash
# Download playlist to DJ-CoPilot/downloads/
# Then process:
./cortex skill run audio_processing_orchestrator --directory downloads
```

---

## Support & Feedback

**Questions**: Review skill source code in `cortex/skills/`
**Issues**: Check `cortex/logs/skills/` for execution logs
**Feature Requests**: Add new skills following development guide above

---

**Skills Directory**: `/Users/jesse.kemp/Dev/cortex/skills/`
**Last Updated**: 2025-12-16
**Version**: 1.0.0
**Status**: Phase 1 Complete (3 skills operational)
