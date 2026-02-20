"""
Anti-pattern detection for validated-but-undeployed code.

Scans validation reports, git history, and production configurations to identify:
- Validated improvements not deployed to production
- Fixes not integrated into production
- Recommendations not acted upon
- Orphaned validation data

This prevents the "validated but not shipped" anti-pattern where improvements
are proven but never reach production.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AntiPatternType(str, Enum):
    """Types of anti-patterns to detect."""

    VALIDATED_UNDEPLOYED = "validated_undeployed"  # Model validated but not in production
    FIXED_NOT_INTEGRATED = "fixed_not_integrated"  # Bug fixed but fix not deployed
    RECOMMENDATION_NOT_ACTED = "recommendation_not_acted"  # Critical recommendation ignored
    ORPHANED_VALIDATION = "orphaned_validation"  # Validation data with no follow-up


class Severity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"  # Production impact, immediate action required
    HIGH = "high"  # Significant improvement not deployed
    MEDIUM = "medium"  # Recommended improvement not acted on
    LOW = "low"  # Minor validation finding


@dataclass
class AntiPatternAlert:
    """
    Alert for detected anti-pattern.

    Represents a case where validated work has not been deployed.
    """

    # Identity
    id: str
    pattern_type: AntiPatternType
    severity: Severity

    # Context
    project: str  # e.g., "vortex-backend", "alpha_arena"
    validated_item: str  # e.g., "FieldSelectiveEnsemble", "bias_correction_v2"
    validation_source: str  # Path to validation report
    validation_date: datetime

    # Production state
    production_item: Optional[str] = None  # Current production model/approach
    production_source: Optional[str] = None  # Where production config was found

    # Metrics
    improvement_metrics: Dict[str, Any] = field(
        default_factory=dict
    )  # e.g., {"mae_improvement": "6.3%"}
    recommendation_priority: Optional[str] = None  # e.g., "P0", "P1"

    # Evidence
    evidence: List[str] = field(default_factory=list)  # Supporting facts

    # Action
    suggested_action: str = ""  # What should be done
    estimated_effort: Optional[str] = None  # e.g., "2h", "1d"
    blocking_factors: List[str] = field(default_factory=list)  # What's blocking deployment

    # Tracking
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type.value,
            "severity": self.severity.value,
            "project": self.project,
            "validated_item": self.validated_item,
            "validation_source": self.validation_source,
            "validation_date": self.validation_date.isoformat(),
            "production_item": self.production_item,
            "production_source": self.production_source,
            "improvement_metrics": json.dumps(self.improvement_metrics),
            "recommendation_priority": self.recommendation_priority,
            "evidence": json.dumps(self.evidence),
            "suggested_action": self.suggested_action,
            "estimated_effort": self.estimated_effort,
            "blocking_factors": json.dumps(self.blocking_factors),
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AntiPatternAlert":
        """Deserialize from dict."""
        # Parse enums
        data["pattern_type"] = AntiPatternType(data["pattern_type"])
        data["severity"] = Severity(data["severity"])

        # Parse dates
        data["validation_date"] = datetime.fromisoformat(data["validation_date"])
        data["detected_at"] = datetime.fromisoformat(data["detected_at"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])

        # Parse JSON fields
        if isinstance(data.get("improvement_metrics"), str):
            data["improvement_metrics"] = json.loads(data["improvement_metrics"])
        if isinstance(data.get("evidence"), str):
            data["evidence"] = json.loads(data["evidence"])
        if isinstance(data.get("blocking_factors"), str):
            data["blocking_factors"] = json.loads(data["blocking_factors"])

        return cls(**data)


class AntiPatternDetector:
    """
    Detects validated-but-undeployed code patterns.

    Scans validation reports and production configurations to find
    improvements that have been validated but not deployed.
    """

    def __init__(self, db=None, root_dir: Optional[Path] = None):
        """
        Initialize detector.

        Args:
            db: OrchestrationDatabase instance (optional, for persistence)
            root_dir: Root directory of monorepo (defaults to current dir)
        """
        self.db = db
        self.root_dir = root_dir or Path.cwd()

        # Project configurations
        self.projects = {
            "vortex-backend": {
                "validation_dir": "Vortex/backend/data/validation",
                "production_config": "Vortex/backend/data/validation/production_config.json",
                "api_files": ["Vortex/backend/app/api/v2/weather.py"],
                "model_files": ["Vortex/backend/app/models/*.py"],
                "entry_points": ["Vortex/backend/ui/app.py", "Vortex/backend/app/main.py"],
            },
            "alpha_arena": {
                "validation_dir": "alpha_arena/data/validation",
                "production_config": "alpha_arena/data/production_config.json",
                "api_files": ["alpha_arena/api/*.py"],
                "model_files": ["alpha_arena/models/*.py"],
                "entry_points": ["alpha_arena/app.py", "alpha_arena/main.py"],
            },
        }

    def detect_all(self) -> List[AntiPatternAlert]:
        """
        Run all anti-pattern detections across all projects.

        Returns:
            List of detected anti-pattern alerts
        """
        alerts = []

        for project_name in self.projects.keys():
            logger.info(f"Scanning {project_name} for anti-patterns...")

            # Detect validated-but-undeployed
            alerts.extend(self.detect_validated_undeployed(project_name))

            # Detect fixed-but-not-integrated
            alerts.extend(self.detect_fixed_not_integrated(project_name))

            # Detect recommendations-not-acted
            alerts.extend(self.detect_recommendations_not_acted(project_name))

        logger.info(f"Detected {len(alerts)} anti-patterns")

        # Store in database if available
        if self.db:
            for alert in alerts:
                try:
                    self.db.create_anti_pattern_alert(alert)
                except Exception as e:
                    logger.warning(f"Failed to store alert {alert.id}: {e}")

        return alerts

    def detect_validated_undeployed(self, project: str) -> List[AntiPatternAlert]:
        """
        Detect validated models/approaches not deployed to production.

        Algorithm:
        1. Scan validation reports for improvements
        2. Extract validated model names and improvement metrics
        3. Check if model is in production config
        4. Check if model is referenced in production code
        5. Check git history for deployment commits
        6. Create alert if no evidence of deployment

        Args:
            project: Project name (e.g., "vortex-backend")

        Returns:
            List of alerts for undeployed improvements
        """
        alerts = []

        project_config = self.projects.get(project)
        if not project_config:
            logger.warning(f"Unknown project: {project}")
            return alerts

        # Find validation reports
        validation_dir = self.root_dir / project_config["validation_dir"]
        if not validation_dir.exists():
            logger.debug(f"Validation directory not found: {validation_dir}")
            return alerts

        report_files = list(validation_dir.glob("*REPORT*.md"))

        for report_path in report_files:
            logger.debug(f"Scanning report: {report_path}")

            # Parse improvements from report
            improvements = self._parse_improvements(report_path)

            for improvement in improvements:
                model_name = improvement["model_name"]
                metrics = improvement["metrics"]
                validation_date = improvement.get("date", datetime.now())

                # Check if deployed to production
                is_deployed = self._check_production_deployment(project, model_name, project_config)

                if not is_deployed:
                    # Create alert
                    alert_id = f"{project}_{model_name}_{validation_date.strftime('%Y%m%d')}"

                    # Determine severity based on improvement magnitude
                    severity = self._calculate_severity(metrics)

                    # Get current production model for comparison
                    prod_model = self._get_production_model(project, project_config)

                    alert = AntiPatternAlert(
                        id=alert_id,
                        pattern_type=AntiPatternType.VALIDATED_UNDEPLOYED,
                        severity=severity,
                        project=project,
                        validated_item=model_name,
                        validation_source=str(report_path.relative_to(self.root_dir)),
                        validation_date=validation_date,
                        production_item=prod_model.get("name") if prod_model else None,
                        production_source=prod_model.get("source") if prod_model else None,
                        improvement_metrics=metrics,
                        evidence=[
                            f"Validated in report: {report_path.name}",
                            "Not found in production config",
                            "Not found in API routes",
                            "Not found in entry points",
                        ],
                        suggested_action=f"Deploy {model_name} to production and update routing",
                        estimated_effort="4-8h",
                    )

                    alerts.append(alert)
                    logger.info(f"Found undeployed improvement: {model_name} in {project}")

        return alerts

    def detect_fixed_not_integrated(self, project: str) -> List[AntiPatternAlert]:
        """
        Detect bug fixes validated but not integrated into production.

        Looks for fix reports or validation showing bugs resolved but
        fixes not merged into production branch.

        Args:
            project: Project name

        Returns:
            List of alerts for non-integrated fixes
        """
        alerts = []

        project_config = self.projects.get(project)
        if not project_config:
            return alerts

        # Find fix reports
        validation_dir = self.root_dir / project_config["validation_dir"]
        if not validation_dir.exists():
            return alerts

        fix_reports = list(validation_dir.glob("*FIX*.md"))

        for report_path in fix_reports:
            logger.debug(f"Scanning fix report: {report_path}")

            # Parse fix details
            fix_info = self._parse_fix_report(report_path)

            if not fix_info:
                continue

            fix_name = fix_info["fix_name"]
            issue = fix_info.get("issue", "")

            # Check if fix is in production
            is_integrated = self._check_fix_integrated(project, fix_name, project_config)

            if not is_integrated:
                alert_id = f"{project}_fix_{fix_name}_{datetime.now().strftime('%Y%m%d')}"

                alert = AntiPatternAlert(
                    id=alert_id,
                    pattern_type=AntiPatternType.FIXED_NOT_INTEGRATED,
                    severity=Severity.HIGH,
                    project=project,
                    validated_item=fix_name,
                    validation_source=str(report_path.relative_to(self.root_dir)),
                    validation_date=fix_info.get("date", datetime.now()),
                    improvement_metrics={"issue": issue},
                    evidence=[
                        f"Fix documented in: {report_path.name}",
                        "Fix not found in production code",
                    ],
                    suggested_action=f"Integrate {fix_name} into production",
                    estimated_effort="2-4h",
                )

                alerts.append(alert)

        return alerts

    def detect_recommendations_not_acted(self, project: str) -> List[AntiPatternAlert]:
        """
        Detect high-priority recommendations not acted upon.

        Scans validation reports for P0/P1 recommendations and checks
        if they've been addressed.

        Args:
            project: Project name

        Returns:
            List of alerts for ignored recommendations
        """
        alerts = []

        project_config = self.projects.get(project)
        if not project_config:
            return alerts

        # Find validation reports with recommendations
        validation_dir = self.root_dir / project_config["validation_dir"]
        if not validation_dir.exists():
            return alerts

        report_files = list(validation_dir.glob("*.md"))

        for report_path in report_files:
            # Parse recommendations
            recommendations = self._parse_recommendations(report_path)

            for rec in recommendations:
                priority = rec.get("priority", "")
                action = rec.get("action", "")

                # Only alert on P0/P1
                if priority not in ["P0", "P1", "CRITICAL"]:
                    continue

                # Check if recommendation has been acted on
                acted = self._check_recommendation_acted(project, rec, project_config)

                # Check age - only alert if > 30 days old
                rec_date = rec.get("date", datetime.now())
                age_days = (datetime.now() - rec_date).days

                if not acted and age_days > 30:
                    alert_id = f"{project}_rec_{hash(action)}_{rec_date.strftime('%Y%m%d')}"

                    severity = Severity.CRITICAL if priority == "P0" else Severity.HIGH

                    alert = AntiPatternAlert(
                        id=alert_id,
                        pattern_type=AntiPatternType.RECOMMENDATION_NOT_ACTED,
                        severity=severity,
                        project=project,
                        validated_item=action[:100],
                        validation_source=str(report_path.relative_to(self.root_dir)),
                        validation_date=rec_date,
                        recommendation_priority=priority,
                        evidence=[
                            f"Recommendation in: {report_path.name}",
                            f"Priority: {priority}",
                            f"Age: {age_days} days",
                        ],
                        suggested_action=action,
                        estimated_effort=rec.get("effort", "unknown"),
                    )

                    alerts.append(alert)

        return alerts

    def _check_production_deployment(
        self, project: str, model_name: str, config: Dict[str, Any]
    ) -> bool:
        """
        Check if model is deployed to production.

        Strategies:
        1. Check production_config.json
        2. Grep production code for model name
        3. Check main entry points
        4. Check git history for deployment

        Args:
            project: Project name
            model_name: Model to check
            config: Project configuration

        Returns:
            True if model is in production
        """
        # Strategy 1: Check production config
        prod_config_path = self.root_dir / config.get("production_config", "")
        if prod_config_path.exists():
            try:
                prod_data = json.loads(prod_config_path.read_text())
                current_model = prod_data.get("current_production_model", {}).get("name", "")
                if model_name.lower() in current_model.lower():
                    return True
            except Exception as e:
                logger.debug(f"Failed to parse production config: {e}")

        # Strategy 2: Check API files
        for api_pattern in config.get("api_files", []):
            for api_file in self.root_dir.glob(api_pattern):
                if api_file.exists() and model_name in api_file.read_text():
                    return True

        # Strategy 3: Check entry points
        for entry_pattern in config.get("entry_points", []):
            for entry_file in self.root_dir.glob(entry_pattern):
                if entry_file.exists() and model_name in entry_file.read_text():
                    return True

        # Strategy 4: Check recent git history
        commits = self._scan_git_history(
            project, [model_name, "deploy", "production"], since=datetime.now() - timedelta(days=90)
        )
        if commits:
            return True

        return False

    def _check_fix_integrated(self, project: str, fix_name: str, config: Dict[str, Any]) -> bool:
        """Check if fix is integrated into production code."""
        # Check model files
        for model_pattern in config.get("model_files", []):
            for model_file in self.root_dir.glob(model_pattern):
                if model_file.exists() and fix_name.lower() in model_file.read_text().lower():
                    return True

        # Check git history
        commits = self._scan_git_history(
            project, [fix_name, "fix", "integrate"], since=datetime.now() - timedelta(days=60)
        )
        return len(commits) > 0

    def _check_recommendation_acted(
        self, project: str, recommendation: Dict[str, Any], config: Dict[str, Any]
    ) -> bool:
        """Check if recommendation has been acted upon."""
        action = recommendation.get("action", "")
        keywords = recommendation.get("keywords", [])

        # Check git history for related commits
        commits = self._scan_git_history(
            project, keywords + [action[:50]], since=recommendation.get("date", datetime.now())
        )
        return len(commits) > 0

    def _scan_git_history(
        self, project: str, search_terms: List[str], since: datetime
    ) -> List[str]:
        """
        Scan git commit messages for search terms.

        Args:
            project: Project name
            search_terms: Terms to search for
            since: Only check commits since this date

        Returns:
            List of matching commit SHAs
        """
        try:
            # Format date for git
            since_str = since.strftime("%Y-%m-%d")

            # Get commit messages
            result = subprocess.run(
                ["git", "log", f"--since={since_str}", "--pretty=format:%H %s", "--all"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.split("\n"):
                if not line.strip():
                    continue

                # Check if any search term is in commit message
                for term in search_terms:
                    if term.lower() in line.lower():
                        sha = line.split()[0]
                        commits.append(sha)
                        break

            return commits
        except Exception as e:
            logger.debug(f"Git history scan failed: {e}")
            return []

    def _parse_improvements(self, report_path: Path) -> List[Dict[str, Any]]:
        """
        Parse improvement information from validation report.

        Looks for patterns like:
        - "FieldSelectiveEnsemble shows 6.3% improvement"
        - "adaptive approach reduces MAE by 8%"
        - Comparison tables with "better" indicators

        Args:
            report_path: Path to validation report

        Returns:
            List of improvement dicts with model_name, metrics, date
        """
        improvements = []

        try:
            content = report_path.read_text()

            # Pattern 1: Direct improvement statements
            # Example: "FieldSelectiveEnsemble shows 6.3% improvement"
            pattern1 = r"([A-Za-z_]+(?:Ensemble|Model|Approach))\s+(?:shows?|achieves?|demonstrates?)\s+(?:(?:a|an)\s+)?(\+?[\d.]+%)\s+(?:improvement|better|reduction)"
            matches1 = re.finditer(pattern1, content, re.IGNORECASE)

            for match in matches1:
                model_name = match.group(1)
                pct = match.group(2)

                improvements.append(
                    {
                        "model_name": model_name,
                        "metrics": {"improvement_pct": pct},
                        "date": self._extract_date_from_report(report_path, content),
                    }
                )

            # Pattern 2: Comparison tables
            # Look for markdown tables with "better" or improvement indicators
            table_pattern = r"\|([^\|]+)\|([^\|]+)\|([^\|]+)\|"
            for line in content.split("\n"):
                if "|" in line and any(
                    word in line.lower() for word in ["better", "improvement", "best"]
                ):
                    match = re.search(table_pattern, line)
                    if match:
                        # Extract model name from first column
                        model_name = match.group(1).strip()
                        if model_name and not model_name.startswith("-"):
                            improvements.append(
                                {
                                    "model_name": model_name,
                                    "metrics": {"comparison": "better"},
                                    "date": self._extract_date_from_report(report_path, content),
                                }
                            )

            # Pattern 3: Headline improvements
            # Example: "## FieldSelectiveEnsemble: 6.3% MAE Reduction"
            pattern3 = (
                r"##\s+([A-Za-z_]+):\s+(\+?[\d.]+%)\s+([A-Za-z]+)\s+(?:Reduction|Improvement)"
            )
            matches3 = re.finditer(pattern3, content, re.IGNORECASE)

            for match in matches3:
                model_name = match.group(1)
                pct = match.group(2)
                metric = match.group(3)

                improvements.append(
                    {
                        "model_name": model_name,
                        "metrics": {f"{metric.lower()}_improvement": pct},
                        "date": self._extract_date_from_report(report_path, content),
                    }
                )

        except Exception as e:
            logger.warning(f"Failed to parse improvements from {report_path}: {e}")

        return improvements

    def _parse_fix_report(self, report_path: Path) -> Optional[Dict[str, Any]]:
        """Parse fix information from fix report."""
        try:
            content = report_path.read_text()

            # Extract fix name from filename or title
            fix_name = report_path.stem.replace("_FIX_REPORT", "").replace("_", " ")

            # Look for issue description
            issue_pattern = r"(?:Issue|Problem|Bug):\s*(.+?)(?:\n\n|\Z)"
            issue_match = re.search(issue_pattern, content, re.IGNORECASE | re.DOTALL)
            issue = issue_match.group(1).strip() if issue_match else ""

            return {
                "fix_name": fix_name,
                "issue": issue,
                "date": self._extract_date_from_report(report_path, content),
            }
        except Exception as e:
            logger.warning(f"Failed to parse fix report {report_path}: {e}")
            return None

    def _parse_recommendations(self, report_path: Path) -> List[Dict[str, Any]]:
        """
        Parse recommendations from validation report.

        Looks for sections like:
        - "## Recommendations"
        - "**P0: Deploy FieldSelectiveEnsemble**"
        - "CRITICAL: Update production routing"
        """
        recommendations = []

        try:
            content = report_path.read_text()

            # Find recommendations section
            rec_section_pattern = r"##\s+(?:Recommendations|Next Steps|Action Items)(.*?)(?:##|\Z)"
            rec_section_match = re.search(rec_section_pattern, content, re.IGNORECASE | re.DOTALL)

            if not rec_section_match:
                return recommendations

            rec_section = rec_section_match.group(1)

            # Parse individual recommendations
            # Pattern: **P0: Action** or **CRITICAL: Action**
            rec_pattern = r"\*\*(?:(P[0-9]|CRITICAL|HIGH|MEDIUM|LOW):)?\s*([^*]+)\*\*"
            matches = re.finditer(rec_pattern, rec_section)

            for match in matches:
                priority = match.group(1) or "P2"
                action = match.group(2).strip()

                # Extract keywords from action
                keywords = [word for word in action.split() if len(word) > 4][:5]

                recommendations.append(
                    {
                        "priority": priority,
                        "action": action,
                        "keywords": keywords,
                        "date": self._extract_date_from_report(report_path, content),
                    }
                )

        except Exception as e:
            logger.warning(f"Failed to parse recommendations from {report_path}: {e}")

        return recommendations

    def _extract_date_from_report(self, report_path: Path, content: str) -> datetime:
        """Extract date from report filename or content."""
        # Try filename first
        # Pattern: YYYYMMDD
        filename_date = re.search(r"(\d{8})", report_path.stem)
        if filename_date:
            try:
                return datetime.strptime(filename_date.group(1), "%Y%m%d")
            except ValueError:
                pass

        # Try content - look for date headers
        content_date = re.search(r"(?:Date|Generated|Created):\s*(\d{4}-\d{2}-\d{2})", content)
        if content_date:
            try:
                return datetime.strptime(content_date.group(1), "%Y-%m-%d")
            except ValueError:
                pass

        # Fall back to file modification time
        return datetime.fromtimestamp(report_path.stat().st_mtime)

    def _get_production_model(
        self, project: str, config: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """Get current production model information."""
        prod_config_path = self.root_dir / config.get("production_config", "")

        if prod_config_path.exists():
            try:
                prod_data = json.loads(prod_config_path.read_text())
                current = prod_data.get("current_production_model", {})
                if current:
                    return {
                        "name": current.get("name", "unknown"),
                        "source": str(prod_config_path.relative_to(self.root_dir)),
                    }
            except Exception:
                pass

        return None

    def _calculate_severity(self, metrics: Dict[str, Any]) -> Severity:
        """Calculate severity based on improvement metrics."""
        # Extract percentage improvements
        for key, value in metrics.items():
            if isinstance(value, str) and "%" in value:
                try:
                    pct = float(value.replace("+", "").replace("%", ""))

                    if pct >= 10:
                        return Severity.CRITICAL
                    elif pct >= 5:
                        return Severity.HIGH
                    elif pct >= 2:
                        return Severity.MEDIUM
                    else:
                        return Severity.LOW
                except ValueError:
                    pass

        # Default to MEDIUM if can't parse
        return Severity.MEDIUM
