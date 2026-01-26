# Anti-Pattern Detector - Quick Start

## Installation

No installation needed - the detector is already integrated into Cortex.

## Basic Usage

### 1. Check for Anti-Patterns

```bash
# Via CLI status command
python cli.py status

# Via test script (detailed report)
cd orchestration
python test_detection_real.py
```

### 2. Programmatic Usage

```python
from orchestration.anti_pattern_detector import AntiPatternDetector
from pathlib import Path

# Create detector
detector = AntiPatternDetector(db=None, root_dir=Path.cwd())

# Run detection
alerts = detector.detect_all()

# Process results
for alert in alerts:
    if alert.severity.value in ["critical", "high"]:
        print(f"{alert.project}: {alert.validated_item}")
        print(f"  Metrics: {alert.improvement_metrics}")
        print(f"  Action: {alert.suggested_action}")
```

### 3. With Database Persistence

```python
from orchestration.anti_pattern_detector import AntiPatternDetector
from orchestration.database import OrchestrationDatabase
from pathlib import Path

# Create database and detector
db = OrchestrationDatabase()
detector = AntiPatternDetector(db=db, root_dir=Path.cwd())

# Run detection (automatically stores alerts)
alerts = detector.detect_all()

# Query stored alerts
vortex_alerts = db.get_anti_pattern_alerts(project="VortexV2")

# Resolve an alert
db.resolve_anti_pattern_alert(
    alert_id="VortexV2_Model_20260115",
    notes="Deployed to production in PR #123"
)
```

## Adding a New Project

Edit `orchestration/anti_pattern_detector.py`:

```python
self.projects["my_project"] = {
    "validation_dir": "my_project/validation",
    "production_config": "my_project/production_config.json",
    "api_files": ["my_project/api/*.py"],
    "model_files": ["my_project/models/*.py"],
    "entry_points": ["my_project/main.py"],
}
```

## Validation Report Format

For best detection, structure validation reports like:

```markdown
# Project Validation Report

Date: 2026-01-26

## Model Comparison

| Model | MAE | RMSE | Notes |
|-------|-----|------|-------|
| NewModel | 0.45 | 0.62 | **Better** - 6.3% improvement |
| Baseline | 0.48 | 0.65 | Current production |

## Key Findings

NewModel shows 6.3% improvement over baseline.

## Recommendations

**P0: Deploy NewModel to production**

NewModel has been validated and shows significant improvement.
Estimated effort: 4-8 hours.
```

## Production Config Format

```json
{
  "current_production_model": {
    "name": "ModelName",
    "version": "1.0",
    "deployed_at": "2026-01-01T00:00:00"
  }
}
```

## Resolving Alerts

### When a Model is Deployed

1. Update production config
2. Update API routing
3. Deploy to production
4. Resolve alert in database:

```python
db.resolve_anti_pattern_alert(
    alert_id="project_model_date",
    notes="Deployed in PR #123, updated routing in commit abc123"
)
```

### When a Recommendation is Addressed

1. Complete the recommended action
2. Commit changes
3. Resolve alert:

```python
db.resolve_anti_pattern_alert(
    alert_id="project_rec_date",
    notes="Implemented monitoring in PR #456"
)
```

## Common Patterns

### Check Before Deployment

```python
detector = AntiPatternDetector(db=None)
alerts = detector.detect_validated_undeployed("VortexV2")

if alerts:
    print("⚠️ Undeployed improvements found!")
    for alert in alerts:
        print(f"  - {alert.validated_item}: {alert.improvement_metrics}")
```

### Periodic Scanning

```python
import schedule
import time

def scan_projects():
    detector = AntiPatternDetector(db=db)
    alerts = detector.detect_all()

    critical = [a for a in alerts if a.severity.value == "critical"]
    if critical:
        send_slack_alert(f"🚨 {len(critical)} critical anti-patterns detected")

schedule.every().day.at("09:00").do(scan_projects)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Dashboard Integration

```python
import streamlit as st

db = OrchestrationDatabase()
alerts = db.get_anti_pattern_alerts(unresolved_only=True)

if alerts:
    st.warning(f"⚠️ {len(alerts)} undeployed improvements")

    for alert in alerts:
        with st.expander(f"{alert.severity.upper()}: {alert.validated_item}"):
            st.write(f"**Project**: {alert.project}")
            st.write(f"**Metrics**: {alert.improvement_metrics}")
            st.write(f"**Action**: {alert.suggested_action}")

            if st.button("Mark as Resolved", key=alert.id):
                db.resolve_anti_pattern_alert(alert.id, "Resolved via dashboard")
                st.rerun()
```

## Troubleshooting

### No Alerts Detected

**Problem**: Detector finds no issues
**Solutions**:
1. Check validation reports exist in configured paths
2. Verify report format includes improvement keywords
3. Check production config exists and is readable
4. Run test script with verbose logging

### False Positives

**Problem**: Detector reports model as undeployed but it is deployed
**Solutions**:
1. Ensure production config is updated
2. Check model name matches exactly (case-sensitive)
3. Verify API files are in configured paths
4. Update project configuration with correct file patterns

### Git History Errors

**Problem**: Git scan fails
**Solutions**:
1. Ensure running in git repository
2. Check git is installed and accessible
3. Verify git history is available
4. Disable git scanning if not needed

## Testing

```bash
# Run full test suite
pytest orchestration/test_anti_pattern_detector.py -v

# Run specific test
pytest orchestration/test_anti_pattern_detector.py::TestAntiPatternDetector::test_detect_validated_undeployed -v

# Run with coverage
pytest orchestration/test_anti_pattern_detector.py --cov=orchestration.anti_pattern_detector
```

## Performance

- **Small repos** (< 100 commits): < 50ms per project
- **Medium repos** (100-1000 commits): 100-500ms per project
- **Large repos** (> 1000 commits): 500ms-2s per project

Optimize by:
- Limiting git history scan window (`since` parameter)
- Caching production configs
- Running detection in background

## Support

- Documentation: `orchestration/ANTI_PATTERN_DETECTOR.md`
- Implementation Report: `orchestration/IMPLEMENTATION_REPORT.md`
- Tests: `orchestration/test_anti_pattern_detector.py`
- Example: `orchestration/test_detection_real.py`

## Next Steps

1. Run `python cli.py status` to see it in action
2. Add your projects to configuration
3. Set up periodic scanning
4. Integrate with dashboard/notifications
5. Establish deployment workflow for resolving alerts
