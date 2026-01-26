# Anti-Pattern Detector

Automated detection of validated-but-undeployed code to prevent the "shipping gate" anti-pattern.

## Purpose

The anti-pattern detector scans validation reports, production configurations, and git history to identify cases where:

1. **Validated Undeployed**: Models validated to be better but not deployed to production
2. **Fixed Not Integrated**: Bug fixes validated but not merged into production
3. **Recommendations Not Acted**: Critical recommendations from validation reports not addressed
4. **Orphaned Validation**: Validation data with no follow-up actions

## How It Works

### Detection Algorithm

For each project (VortexV2, alpha_arena):

1. **Scan validation reports** in `{project}/data/validation/*REPORT*.md`
2. **Parse improvements** looking for patterns:
   - "Model X shows Y% improvement"
   - Comparison tables with "better" indicators
   - Explicit improvement metrics
3. **Check production deployment**:
   - Read `production_config.json` for current production model
   - Grep production code (API routes, entry points) for model references
   - Scan git history for deployment commits
4. **Create alerts** when improvements found but not deployed

### Severity Levels

Alerts are prioritized by improvement magnitude:

- **CRITICAL**: >= 10% improvement not deployed
- **HIGH**: >= 5% improvement not deployed
- **MEDIUM**: >= 2% improvement not deployed
- **LOW**: < 2% improvement not deployed

## Usage

### Programmatic API

```python
from orchestration.anti_pattern_detector import AntiPatternDetector
from orchestration.database import OrchestrationDatabase

# Initialize
db = OrchestrationDatabase()  # Optional, for persistence
detector = AntiPatternDetector(db=db)

# Run detection
alerts = detector.detect_all()

# Print results
for alert in alerts:
    print(f"{alert.severity}: {alert.validated_item} in {alert.project}")
    print(f"  Action: {alert.suggested_action}")
    print(f"  Metrics: {alert.improvement_metrics}")
```

### Test Script

```bash
cd orchestration
python test_detection_real.py
```

This scans all projects and prints a formatted report of detected anti-patterns.

### CLI Integration

The detector is integrated into `/status` command:

```python
from orchestration.anti_pattern_detector import AntiPatternDetector

detector = AntiPatternDetector(db=None, root_dir=Path(args.root))
alerts = detector.detect_all()

critical_alerts = [a for a in alerts if a.severity in ["critical", "high"]]

if critical_alerts:
    anomalies.append(
        f"Anti-patterns detected: {len(critical_alerts)} validated improvements not deployed"
    )
```

## Database Schema

Alerts are stored in `anti_pattern_alerts` table:

```sql
CREATE TABLE anti_pattern_alerts (
    id TEXT PRIMARY KEY,
    pattern_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    project TEXT NOT NULL,
    validated_item TEXT NOT NULL,
    validation_source TEXT NOT NULL,
    validation_date TEXT NOT NULL,
    production_item TEXT,
    production_source TEXT,
    improvement_metrics TEXT DEFAULT '{}',
    recommendation_priority TEXT,
    evidence TEXT DEFAULT '[]',
    suggested_action TEXT NOT NULL,
    estimated_effort TEXT,
    blocking_factors TEXT DEFAULT '[]',
    detected_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution_notes TEXT
);
```

### Database Operations

```python
from orchestration.database import OrchestrationDatabase

db = OrchestrationDatabase()

# Get unresolved alerts
alerts = db.get_anti_pattern_alerts(project="VortexV2", unresolved_only=True)

# Resolve an alert
db.resolve_anti_pattern_alert(
    alert_id="VortexV2_FieldSelectiveEnsemble_20260115",
    notes="Deployed to production in PR #123"
)
```

## Project Configuration

Projects are configured in `anti_pattern_detector.py`:

```python
self.projects = {
    "VortexV2": {
        "validation_dir": "Vortex/VortexV2/data/validation",
        "production_config": "Vortex/VortexV2/data/validation/production_config.json",
        "api_files": ["Vortex/VortexV2/app/api/v2/weather.py"],
        "model_files": ["Vortex/VortexV2/app/models/*.py"],
        "entry_points": ["Vortex/VortexV2/ui/app.py"],
    },
}
```

Add new projects by extending this dictionary.

## Parsing Patterns

### Improvement Detection

The detector looks for these patterns in reports:

1. **Direct statements**: "ModelName shows 6.3% improvement"
2. **Comparison tables**: Markdown tables with "better" indicators
3. **Headlines**: "## ModelName: 6.3% MAE Reduction"

### Recommendation Detection

Looks for recommendation sections with priority markers:

- `**P0: Deploy to production**`
- `**CRITICAL: Update routing**`
- `**HIGH: Add monitoring**`

### Date Extraction

Dates extracted from:
1. Filename: `REPORT_20260115.md`
2. Content: `Date: 2026-01-15`
3. File modification time (fallback)

## Example Alert

```python
AntiPatternAlert(
    id="VortexV2_FieldSelectiveEnsemble_20260115",
    pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
    severity=Severity.HIGH,
    project="VortexV2",
    validated_item="FieldSelectiveEnsemble",
    validation_source="Vortex/VortexV2/data/validation/VORTEXV2_VALIDATION_REPORT.md",
    validation_date=datetime(2026, 1, 15),
    production_item="SimpleEnsemble",
    production_source="Vortex/VortexV2/data/validation/production_config.json",
    improvement_metrics={"mae_improvement": "6.3%", "rmse_improvement": "4.6%"},
    evidence=[
        "Validated in report: VORTEXV2_VALIDATION_REPORT.md",
        "Not found in production config",
        "Not found in API routes",
    ],
    suggested_action="Deploy FieldSelectiveEnsemble to production and update routing",
    estimated_effort="4-8h",
)
```

## Testing

Run the test suite:

```bash
pytest orchestration/test_anti_pattern_detector.py -v
```

Tests cover:
- Alert serialization/deserialization
- Improvement parsing from reports
- Production deployment checking
- Recommendation parsing
- Severity calculation
- Database integration
- End-to-end detection cycle

## Integration Points

### Status Command (cortex/cli.py)

Add to anomaly detection around line 217:

```python
from orchestration.anti_pattern_detector import AntiPatternDetector

detector = AntiPatternDetector(db=None, root_dir=Path(args.root))
alerts = detector.detect_all()

critical_alerts = [a for a in alerts if a.severity in ["critical", "high"]]

if critical_alerts:
    anomalies.append(
        f"Anti-patterns detected: {len(critical_alerts)} validated improvements not deployed"
    )
```

### Dashboard

The Streamlit dashboard can display alerts:

```python
alerts = db.get_anti_pattern_alerts(unresolved_only=True)

if alerts:
    st.warning(f"⚠️ {len(alerts)} validated improvements not deployed")

    for alert in alerts:
        with st.expander(f"{alert.severity.upper()}: {alert.validated_item}"):
            st.write(f"**Project**: {alert.project}")
            st.write(f"**Validated**: {alert.validation_date.strftime('%Y-%m-%d')}")
            st.write(f"**Action**: {alert.suggested_action}")
            st.json(alert.improvement_metrics)
```

## Deployment Workflow

When an alert is detected:

1. **Review** the validation report to confirm improvement
2. **Plan** deployment (update production config, API routing, tests)
3. **Deploy** the validated model
4. **Verify** deployment in production
5. **Resolve** the alert in database:
   ```python
   db.resolve_anti_pattern_alert(alert_id, "Deployed in PR #123")
   ```

## Future Enhancements

1. **Auto-deployment**: For low-risk improvements, automatically create deployment PR
2. **Slack notifications**: Alert team when high-severity patterns detected
3. **Trend analysis**: Track how long improvements sit before deployment
4. **Deployment blockers**: Automatically detect what's preventing deployment
5. **Performance tracking**: Compare pre/post deployment metrics

## Files

- `orchestration/anti_pattern_detector.py`: Main detector logic (500+ lines)
- `orchestration/test_anti_pattern_detector.py`: Comprehensive test suite (450+ lines)
- `orchestration/test_detection_real.py`: Manual testing script
- `orchestration/database.py`: Database schema and operations (extended)
- `orchestration/ANTI_PATTERN_DETECTOR.md`: This documentation

## References

- `.claude/commands/validate-ship.sh`: Audit workflow that inspired this
- `.cortex/memories/vortex_shipping_gate_lesson.md`: Lesson learned about shipping validated work
- `CLAUDE.md`: Anti-pattern rule: "Validated but not deployed"
