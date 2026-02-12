#!/usr/bin/env python3
"""
VortexV2 Forecast Accuracy Monitor

Monitors VortexV2 forecast validation results and triggers alerts when:
- Forecast accuracy drops below threshold (MAE too high)
- Model performance degrades significantly
- Validation data becomes stale

Integrates with Cortex alert manager for desktop notifications.
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add cortex to path for imports
cortex_root = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_root.parent))


@dataclass
class ForecastAccuracyThresholds:
    """Thresholds for forecast accuracy monitoring."""

    # MAE (Mean Absolute Error) thresholds in knots
    wind_speed_mae_critical: float = 5.0  # MAE > 5 knots is CRITICAL
    wind_speed_mae_warning: float = 4.0  # MAE > 4 knots is WARNING

    # Direction MAE thresholds in degrees
    wind_direction_mae_critical: float = 50.0  # MAE > 50° is CRITICAL
    wind_direction_mae_warning: float = 40.0  # MAE > 40° is WARNING

    # Wave height MAE thresholds in meters
    wave_height_mae_critical: float = 1.5  # MAE > 1.5m is CRITICAL
    wave_height_mae_warning: float = 1.2  # MAE > 1.2m is WARNING

    # Data staleness (hours since last validation)
    data_stale_critical: int = 48  # No data in 48h is CRITICAL
    data_stale_warning: int = 24  # No data in 24h is WARNING


@dataclass
class ValidationIssue:
    """A validation accuracy issue."""

    severity: str  # "CRITICAL", "WARNING", "INFO"
    field: str  # "wind_speed", "wind_direction", "wave_height"
    metric: str  # "MAE", "RMSE", "staleness"
    current_value: float
    threshold_value: float
    message: str
    recommendation: str


class VortexForecastMonitor:
    """
    Monitor VortexV2 forecast validation results.

    Reads validation JSON files and triggers alerts when accuracy degrades.
    """

    def __init__(
        self,
        vortex_data_dir: Optional[Path] = None,
        thresholds: Optional[ForecastAccuracyThresholds] = None,
        enable_alerts: bool = True,
    ):
        """
        Initialize forecast monitor.

        Args:
            vortex_data_dir: Path to VortexV2 data directory
            thresholds: Custom thresholds (uses defaults if None)
            enable_alerts: Whether to send alerts via alert manager
        """
        if vortex_data_dir is None:
            vortex_data_dir = Path(__file__).parent.parent.parent / "Vortex" / "VortexV2" / "data"

        self.vortex_data_dir = vortex_data_dir
        self.validation_dir = vortex_data_dir / "validation"
        self.thresholds = thresholds or ForecastAccuracyThresholds()
        self.enable_alerts = enable_alerts

        # Lazy-load alert manager
        self._alert_manager = None

    # =========================================================================
    # Main Monitoring Interface
    # =========================================================================

    def check_forecast_accuracy(self, verbose: bool = False) -> List[ValidationIssue]:
        """
        Check forecast accuracy and return issues.

        Args:
            verbose: Print detailed output

        Returns:
            List of validation issues found
        """
        issues = []

        if verbose:
            print("🌪️  VortexV2 Forecast Accuracy Monitor")
            print("=" * 60)

        # Check if validation directory exists
        if not self.validation_dir.exists():
            issue = ValidationIssue(
                severity="CRITICAL",
                field="system",
                metric="validation_dir",
                current_value=0,
                threshold_value=1,
                message=f"Validation directory not found: {self.validation_dir}",
                recommendation="Check VortexV2 installation and run validation",
            )
            issues.append(issue)
            if verbose:
                print(f"✗ {issue.message}")
            return issues

        # Check latest validation results
        latest_validation = self._get_latest_validation_file()

        if not latest_validation:
            issue = ValidationIssue(
                severity="WARNING",
                field="system",
                metric="validation_file",
                current_value=0,
                threshold_value=1,
                message="No validation results found",
                recommendation="Run validation: scripts/run_30day_adaptive_validation.py",
            )
            issues.append(issue)
            if verbose:
                print(f"⚠ {issue.message}")
            return issues

        # Load and check validation data
        validation_data = self._load_validation_file(latest_validation)

        if not validation_data:
            if verbose:
                print(f"⚠ Could not load validation file: {latest_validation}")
            return issues

        if verbose:
            print(f"✓ Loaded validation data: {latest_validation.name}")
            print(f"  Timestamp: {validation_data.get('timestamp', 'unknown')}")
            print(f"  Total pairs: {validation_data.get('total_pairs', 0)}")

        # Check data staleness
        stale_issue = self._check_data_staleness(validation_data, verbose)
        if stale_issue:
            issues.append(stale_issue)

        # Check field accuracy
        for field in ["wind_speed", "wind_direction", "wave_height"]:
            field_issues = self._check_field_accuracy(field, validation_data, verbose)
            issues.extend(field_issues)

        # Send alerts if enabled
        if self.enable_alerts and issues:
            self._send_alerts(issues)

        if verbose:
            print("\n" + "=" * 60)
            print(f"Issues found: {len(issues)}")
            critical = sum(1 for i in issues if i.severity == "CRITICAL")
            warnings = sum(1 for i in issues if i.severity == "WARNING")
            print(f"  🚨 CRITICAL: {critical}")
            print(f"  ⚠️  WARNING: {warnings}")

        return issues

    # =========================================================================
    # Validation Checks
    # =========================================================================

    def _check_data_staleness(
        self, validation_data: Dict, verbose: bool
    ) -> Optional[ValidationIssue]:
        """Check if validation data is stale."""
        timestamp_str = validation_data.get("timestamp")

        if not timestamp_str:
            return None

        try:
            # Parse timestamp (ISO format with timezone)
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            age_hours = (datetime.now(timestamp.tzinfo) - timestamp).total_seconds() / 3600

            if age_hours > self.thresholds.data_stale_critical:
                severity = "CRITICAL"
                icon = "🚨"
            elif age_hours > self.thresholds.data_stale_warning:
                severity = "WARNING"
                icon = "⚠️"
            else:
                if verbose:
                    print(f"✓ Validation data fresh ({age_hours:.1f}h old)")
                return None

            issue = ValidationIssue(
                severity=severity,
                field="system",
                metric="staleness",
                current_value=age_hours,
                threshold_value=(
                    self.thresholds.data_stale_critical
                    if severity == "CRITICAL"
                    else self.thresholds.data_stale_warning
                ),
                message=f"Validation data is {age_hours:.1f}h old (threshold: {self.thresholds.data_stale_warning}h)",
                recommendation="Run fresh validation to get current accuracy metrics",
            )

            if verbose:
                print(f"{icon} {issue.message}")

            return issue

        except (ValueError, TypeError) as e:
            if verbose:
                print(f"⚠ Could not parse timestamp: {e}")
            return None

    def _check_field_accuracy(
        self, field: str, validation_data: Dict, verbose: bool
    ) -> List[ValidationIssue]:
        """Check accuracy for a specific field."""
        issues = []

        # Get thresholds for this field
        if field == "wind_speed":
            critical_threshold = self.thresholds.wind_speed_mae_critical
            warning_threshold = self.thresholds.wind_speed_mae_warning
        elif field == "wind_direction":
            critical_threshold = self.thresholds.wind_direction_mae_critical
            warning_threshold = self.thresholds.wind_direction_mae_warning
        elif field == "wave_height":
            critical_threshold = self.thresholds.wave_height_mae_critical
            warning_threshold = self.thresholds.wave_height_mae_warning
        else:
            return issues

        # Look for MAE in validation data
        # Check location_winners for field-specific MAE
        location_winners = validation_data.get("location_winners", [])

        for location in location_winners:
            if location.get("field") != field:
                continue

            winner_mae = location.get("winner_mae", 0)

            if winner_mae > critical_threshold:
                severity = "CRITICAL"
                icon = "🚨"
            elif winner_mae > warning_threshold:
                severity = "WARNING"
                icon = "⚠️"
            else:
                if verbose:
                    print(f"✓ {field} accuracy good (MAE: {winner_mae:.2f})")
                continue

            location_name = location.get("location_name", "Unknown")
            winner_model = location.get("winner", "Unknown")

            issue = ValidationIssue(
                severity=severity,
                field=field,
                metric="MAE",
                current_value=winner_mae,
                threshold_value=warning_threshold,
                message=(
                    f"{field} MAE ({winner_mae:.2f}) exceeds threshold "
                    f"({warning_threshold:.2f}) at {location_name} "
                    f"(model: {winner_model})"
                ),
                recommendation=(
                    f"Review {field} forecasts at {location_name}. "
                    f"Consider bias correction or model tuning."
                ),
            )

            issues.append(issue)

            if verbose:
                print(f"{icon} {issue.message}")

        return issues

    # =========================================================================
    # File Operations
    # =========================================================================

    def _get_latest_validation_file(self) -> Optional[Path]:
        """Get the most recent validation JSON file."""
        if not self.validation_dir.exists():
            return None

        # Look for common validation result files
        candidates = [
            "location_competition_latest.json",
            "adaptive_potential_summary.json",
            "30day_adaptive_validation_report.json",
        ]

        for candidate in candidates:
            file_path = self.validation_dir / candidate
            if file_path.exists():
                return file_path

        # Fall back to newest .json file
        json_files = list(self.validation_dir.glob("*.json"))
        if json_files:
            return max(json_files, key=lambda p: p.stat().st_mtime)

        return None

    def _load_validation_file(self, file_path: Path) -> Optional[Dict]:
        """Load validation JSON file."""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None

    # =========================================================================
    # Alerts
    # =========================================================================

    def _send_alerts(self, issues: List[ValidationIssue]):
        """Send alerts for validation issues."""
        # Lazy-load alert manager
        if self._alert_manager is None:
            try:
                import sys
                from pathlib import Path

                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from cortex.notifications.alert_manager import AlertManager

                self._alert_manager = AlertManager()
            except ImportError as e:
                print(f"Alert manager not available: {e}")
                return

        # Send alerts for CRITICAL issues only
        for issue in issues:
            if issue.severity == "CRITICAL":
                try:
                    self._alert_manager.send_alert(
                        title=f"VortexV2: {issue.field} accuracy degraded",
                        message=f"{issue.message}\n\nRecommendation: {issue.recommendation}",
                        severity="CRITICAL",
                        source="vortex_monitor",
                        metadata={
                            "field": issue.field,
                            "metric": issue.metric,
                            "current_value": issue.current_value,
                            "threshold": issue.threshold_value,
                        },
                    )
                except Exception as e:
                    print(f"Failed to send alert: {e}")


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI for forecast monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="VortexV2 forecast accuracy monitor")
    parser.add_argument("--no-alerts", action="store_true", help="Disable alerts")
    parser.add_argument("--quiet", action="store_true", help="Quiet mode")
    args = parser.parse_args()

    monitor = VortexForecastMonitor(enable_alerts=not args.no_alerts)
    issues = monitor.check_forecast_accuracy(verbose=not args.quiet)

    # Exit code: 0 = no critical issues, 1 = critical issues found
    critical_count = sum(1 for i in issues if i.severity == "CRITICAL")
    sys.exit(1 if critical_count > 0 else 0)


if __name__ == "__main__":
    main()
