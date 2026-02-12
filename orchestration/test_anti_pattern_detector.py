"""
Tests for anti-pattern detector.

Tests validated-but-undeployed detection using mock data and
real VortexV2 validation reports if available.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from .anti_pattern_detector import (
    AntiPatternAlert,
    AntiPatternDetector,
    AntiPatternType,
    Severity,
)
from .database import OrchestrationDatabase


class TestAntiPatternAlert:
    """Test AntiPatternAlert serialization."""

    def test_to_dict(self):
        """Test alert serialization."""
        alert = AntiPatternAlert(
            id="test_alert_1",
            pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
            severity=Severity.HIGH,
            project="VortexV2",
            validated_item="FieldSelectiveEnsemble",
            validation_source="data/validation/report.md",
            validation_date=datetime(2026, 1, 15),
            improvement_metrics={"mae_improvement": "6.3%"},
            evidence=["Found in report", "Not in production"],
            suggested_action="Deploy to production",
        )

        result = alert.to_dict()

        assert result["id"] == "test_alert_1"
        assert result["pattern_type"] == "validated_undeployed"
        assert result["severity"] == "high"
        assert result["project"] == "VortexV2"
        assert result["validated_item"] == "FieldSelectiveEnsemble"
        assert '"mae_improvement": "6.3%"' in result["improvement_metrics"]

    def test_from_dict(self):
        """Test alert deserialization."""
        data = {
            "id": "test_alert_1",
            "pattern_type": "validated_undeployed",
            "severity": "high",
            "project": "VortexV2",
            "validated_item": "FieldSelectiveEnsemble",
            "validation_source": "data/validation/report.md",
            "validation_date": "2026-01-15T00:00:00",
            "production_item": None,
            "production_source": None,
            "improvement_metrics": '{"mae_improvement": "6.3%"}',
            "recommendation_priority": None,
            "evidence": '["Found in report", "Not in production"]',
            "suggested_action": "Deploy to production",
            "estimated_effort": None,
            "blocking_factors": "[]",
            "detected_at": "2026-01-26T00:00:00",
            "resolved_at": None,
            "resolution_notes": None,
        }

        alert = AntiPatternAlert.from_dict(data)

        assert alert.id == "test_alert_1"
        assert alert.pattern_type == AntiPatternType.VALIDATED_UNDEPLOYED
        assert alert.severity == Severity.HIGH
        assert alert.validated_item == "FieldSelectiveEnsemble"
        assert alert.improvement_metrics["mae_improvement"] == "6.3%"
        assert len(alert.evidence) == 2


class TestAntiPatternDetector:
    """Test anti-pattern detection logic."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure for testing."""
        # Create project directories
        vortex_dir = tmp_path / "Vortex" / "VortexV2"
        validation_dir = vortex_dir / "data" / "validation"
        validation_dir.mkdir(parents=True)

        # Create mock validation report
        report = validation_dir / "VORTEXV2_VALIDATION_REPORT_20260115.md"
        report.write_text("""
# VortexV2 Validation Report

Date: 2026-01-15

## Model Comparison

| Model | MAE | RMSE | Notes |
|-------|-----|------|-------|
| FieldSelectiveEnsemble | 0.45 | 0.62 | **Better** - 6.3% improvement |
| SimpleEnsemble | 0.48 | 0.65 | Baseline |
| GFS | 0.52 | 0.71 | Raw model |

## Key Findings

FieldSelectiveEnsemble shows 6.3% improvement over baseline in MAE.
The adaptive approach reduces RMSE by 4.6%.

## Recommendations

**P0: Deploy FieldSelectiveEnsemble to production**

The validated model shows significant improvement and should replace
the current production ensemble.

**P1: Update API routing to use new model**

Estimated effort: 4-8 hours
""")

        # Create mock production config (without the new model)
        prod_config = validation_dir / "production_config.json"
        prod_config.write_text(
            json.dumps(
                {
                    "current_production_model": {
                        "name": "SimpleEnsemble",
                        "version": "1.0",
                        "deployed_at": "2026-01-01T00:00:00",
                    }
                }
            )
        )

        # Create mock API file (without the new model)
        api_dir = vortex_dir / "app" / "api" / "v2"
        api_dir.mkdir(parents=True)
        api_file = api_dir / "weather.py"
        api_file.write_text("""
from app.models.simple_ensemble import SimpleEnsemble

@app.get("/forecast")
def get_forecast():
    model = SimpleEnsemble()
    return model.predict()
""")

        return tmp_path

    def test_parse_improvements(self, temp_project):
        """Test parsing improvement information from reports."""
        detector = AntiPatternDetector(db=None, root_dir=temp_project)

        report_path = (
            temp_project
            / "Vortex"
            / "VortexV2"
            / "data"
            / "validation"
            / "VORTEXV2_VALIDATION_REPORT_20260115.md"
        )

        improvements = detector._parse_improvements(report_path)

        assert len(improvements) > 0

        # Check for FieldSelectiveEnsemble
        field_selective = [
            imp for imp in improvements if "FieldSelectiveEnsemble" in imp["model_name"]
        ]
        assert len(field_selective) > 0

        # Check metrics
        improvement = field_selective[0]
        assert "improvement" in str(improvement["metrics"]).lower() or "6.3%" in str(
            improvement["metrics"]
        )

    def test_check_production_deployment_not_deployed(self, temp_project):
        """Test detecting model NOT in production."""
        detector = AntiPatternDetector(db=None, root_dir=temp_project)

        project_config = detector.projects["VortexV2"]
        is_deployed = detector._check_production_deployment(
            "VortexV2", "FieldSelectiveEnsemble", project_config
        )

        assert not is_deployed, "Model should not be detected in production"

    def test_check_production_deployment_is_deployed(self, temp_project):
        """Test detecting model IS in production."""
        # Update production config to include the model
        prod_config_path = (
            temp_project / "Vortex" / "VortexV2" / "data" / "validation" / "production_config.json"
        )
        prod_config_path.write_text(
            json.dumps(
                {
                    "current_production_model": {
                        "name": "FieldSelectiveEnsemble",
                        "version": "2.0",
                        "deployed_at": "2026-01-20T00:00:00",
                    }
                }
            )
        )

        detector = AntiPatternDetector(db=None, root_dir=temp_project)
        project_config = detector.projects["VortexV2"]

        is_deployed = detector._check_production_deployment(
            "VortexV2", "FieldSelectiveEnsemble", project_config
        )

        assert is_deployed, "Model should be detected in production"

    def test_detect_validated_undeployed(self, temp_project):
        """Test detecting validated-but-undeployed models."""
        detector = AntiPatternDetector(db=None, root_dir=temp_project)

        alerts = detector.detect_validated_undeployed("VortexV2")

        assert len(alerts) > 0, "Should detect at least one undeployed improvement"

        # Check alert details
        alert = alerts[0]
        assert alert.pattern_type == AntiPatternType.VALIDATED_UNDEPLOYED
        assert alert.project == "VortexV2"
        assert "FieldSelectiveEnsemble" in alert.validated_item
        assert alert.severity in [Severity.HIGH, Severity.CRITICAL, Severity.MEDIUM]
        assert "Deploy" in alert.suggested_action

    def test_parse_recommendations(self, temp_project):
        """Test parsing recommendations from reports."""
        detector = AntiPatternDetector(db=None, root_dir=temp_project)

        report_path = (
            temp_project
            / "Vortex"
            / "VortexV2"
            / "data"
            / "validation"
            / "VORTEXV2_VALIDATION_REPORT_20260115.md"
        )

        recommendations = detector._parse_recommendations(report_path)

        assert len(recommendations) > 0

        # Check for P0 recommendation
        p0_recs = [rec for rec in recommendations if rec["priority"] == "P0"]
        assert len(p0_recs) > 0

        # Check recommendation content
        rec = p0_recs[0]
        assert "Deploy" in rec["action"] or "production" in rec["action"].lower()

    def test_calculate_severity(self):
        """Test severity calculation based on improvement metrics."""
        detector = AntiPatternDetector(db=None)

        # Critical improvement (>= 10%)
        severity = detector._calculate_severity({"improvement": "+12.5%"})
        assert severity == Severity.CRITICAL

        # High improvement (>= 5%)
        severity = detector._calculate_severity({"mae_improvement": "6.3%"})
        assert severity == Severity.HIGH

        # Medium improvement (>= 2%)
        severity = detector._calculate_severity({"improvement": "+3.0%"})
        assert severity == Severity.MEDIUM

        # Low improvement (< 2%)
        severity = detector._calculate_severity({"improvement": "+1.5%"})
        assert severity == Severity.LOW

    def test_extract_date_from_report(self, temp_project):
        """Test date extraction from report filename and content."""
        detector = AntiPatternDetector(db=None, root_dir=temp_project)

        report_path = (
            temp_project
            / "Vortex"
            / "VortexV2"
            / "data"
            / "validation"
            / "VORTEXV2_VALIDATION_REPORT_20260115.md"
        )

        content = report_path.read_text()
        date = detector._extract_date_from_report(report_path, content)

        assert date.year == 2026
        assert date.month == 1
        assert date.day == 15

    def test_get_production_model(self, temp_project):
        """Test retrieving current production model."""
        detector = AntiPatternDetector(db=None, root_dir=temp_project)

        project_config = detector.projects["VortexV2"]
        prod_model = detector._get_production_model("VortexV2", project_config)

        assert prod_model is not None
        assert prod_model["name"] == "SimpleEnsemble"
        assert "production_config.json" in prod_model["source"]


class TestDatabaseIntegration:
    """Test database integration for anti-pattern alerts."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        db = OrchestrationDatabase(db_path)
        yield db

        # Cleanup
        db_path.unlink()

    def test_create_alert(self, temp_db):
        """Test creating anti-pattern alert in database."""
        alert = AntiPatternAlert(
            id="test_db_alert_1",
            pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
            severity=Severity.HIGH,
            project="VortexV2",
            validated_item="FieldSelectiveEnsemble",
            validation_source="data/validation/report.md",
            validation_date=datetime(2026, 1, 15),
            improvement_metrics={"mae_improvement": "6.3%"},
            evidence=["Found in report", "Not in production"],
            suggested_action="Deploy to production",
        )

        temp_db.create_anti_pattern_alert(alert)

        # Retrieve and verify
        alerts = temp_db.get_anti_pattern_alerts(project="VortexV2")
        assert len(alerts) == 1
        assert alerts[0].id == "test_db_alert_1"
        assert alerts[0].validated_item == "FieldSelectiveEnsemble"

    def test_get_alerts_by_project(self, temp_db):
        """Test filtering alerts by project."""
        # Create alerts for different projects
        alert1 = AntiPatternAlert(
            id="vortex_alert",
            pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
            severity=Severity.HIGH,
            project="VortexV2",
            validated_item="Model1",
            validation_source="report1.md",
            validation_date=datetime.now(),
            suggested_action="Deploy",
        )

        alert2 = AntiPatternAlert(
            id="arena_alert",
            pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
            severity=Severity.MEDIUM,
            project="alpha_arena",
            validated_item="Model2",
            validation_source="report2.md",
            validation_date=datetime.now(),
            suggested_action="Deploy",
        )

        temp_db.create_anti_pattern_alert(alert1)
        temp_db.create_anti_pattern_alert(alert2)

        # Get VortexV2 alerts
        vortex_alerts = temp_db.get_anti_pattern_alerts(project="VortexV2")
        assert len(vortex_alerts) == 1
        assert vortex_alerts[0].project == "VortexV2"

        # Get all alerts
        all_alerts = temp_db.get_anti_pattern_alerts(project=None, unresolved_only=False)
        assert len(all_alerts) == 2

    def test_resolve_alert(self, temp_db):
        """Test resolving an alert."""
        alert = AntiPatternAlert(
            id="resolve_test",
            pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
            severity=Severity.HIGH,
            project="VortexV2",
            validated_item="TestModel",
            validation_source="report.md",
            validation_date=datetime.now(),
            suggested_action="Deploy",
        )

        temp_db.create_anti_pattern_alert(alert)

        # Verify unresolved
        unresolved = temp_db.get_anti_pattern_alerts(unresolved_only=True)
        assert len(unresolved) == 1

        # Resolve
        temp_db.resolve_anti_pattern_alert("resolve_test", "Deployed to production")

        # Verify resolved
        unresolved = temp_db.get_anti_pattern_alerts(unresolved_only=True)
        assert len(unresolved) == 0

        # Verify in all alerts
        all_alerts = temp_db.get_anti_pattern_alerts(unresolved_only=False)
        assert len(all_alerts) == 1
        assert all_alerts[0].resolved_at is not None
        assert all_alerts[0].resolution_notes == "Deployed to production"


class TestEndToEnd:
    """End-to-end tests with database integration."""

    @pytest.fixture
    def temp_system(self, tmp_path):
        """Create complete temporary system."""
        # Create database
        db_path = tmp_path / "test.db"
        db = OrchestrationDatabase(db_path)

        # Create project structure
        vortex_dir = tmp_path / "Vortex" / "VortexV2"
        validation_dir = vortex_dir / "data" / "validation"
        validation_dir.mkdir(parents=True)

        # Create validation report
        report = validation_dir / "VALIDATION_REPORT.md"
        report.write_text("""
# Validation Report

## Results

FieldSelectiveEnsemble achieves +8.5% improvement over baseline.

## Recommendations

**P0: Deploy validated model**
""")

        # Create production config
        prod_config = validation_dir / "production_config.json"
        prod_config.write_text(json.dumps({"current_production_model": {"name": "Baseline"}}))

        return db, tmp_path

    def test_full_detection_cycle(self, temp_system):
        """Test complete detection and storage cycle."""
        db, root_dir = temp_system

        # Run detector
        detector = AntiPatternDetector(db=db, root_dir=root_dir)
        alerts = detector.detect_all()

        # Should find at least one alert
        assert len(alerts) > 0

        # Verify stored in database
        stored_alerts = db.get_anti_pattern_alerts()
        assert len(stored_alerts) == len(alerts)

        # Verify alert details
        alert = stored_alerts[0]
        assert alert.project == "VortexV2"
        assert alert.pattern_type in [
            AntiPatternType.VALIDATED_UNDEPLOYED,
            AntiPatternType.RECOMMENDATION_NOT_ACTED,
        ]
        assert alert.severity in [Severity.CRITICAL, Severity.HIGH]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
