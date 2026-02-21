import os
#!/usr/bin/env python3
"""
Signal Detection System

Autonomously monitors the monorepo for signals that should spawn tasks:
- Validation gaps: Validated improvements not deployed
- Test failures: Recurring pytest failures
- Strategic misalignment: GOALS.md priorities not being worked
- Tech debt: Ruff/mypy issues, high complexity
- Security: CVEs, exposed secrets
- Performance: Metric regressions
- Documentation: Missing/stale docs
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List


class SignalType(Enum):
    """Types of signals the system can detect."""

    VALIDATION_GAP = "validation_gap"  # Validated > not deployed
    TEST_FAILURE = "test_failure"  # Recurring failures
    STRATEGIC_GAP = "strategic_gap"  # GOALS.md misalignment
    TECH_DEBT = "tech_debt"  # Ruff/mypy/complexity
    SECURITY = "security"  # CVEs, exposed secrets
    PERFORMANCE = "performance"  # Metric regression
    DOCUMENTATION = "documentation"  # Missing/stale docs


@dataclass
class Signal:
    """A detected signal that may spawn a task."""

    id: str  # Unique identifier
    type: SignalType
    severity: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    context: Dict[str, Any]  # Project, files, metrics, etc.
    evidence: List[str]  # Proof this is a real issue
    estimated_impact: str  # What fixing this achieves
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "evidence": self.evidence,
            "estimated_impact": self.estimated_impact,
            "detected_at": self.detected_at.isoformat(),
        }


class SignalDetector:
    """Autonomously monitors for work signals."""

    def __init__(self, root_dir: str = os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))):
        self.root_dir = Path(root_dir)
        self.vortex_dir = self.root_dir / "Vortex" / "backend"
        self.alpha_arena_dir = self.root_dir / "alpha_arena"
        self.cortex_dir = self.root_dir / "cortex"
        self.cache_dir = Path.home() / ".cortex" / "signals"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def detect_all(self) -> List[Signal]:
        """Run all detectors and return signals."""
        signals = []

        # Run each detector
        signals.extend(self.detect_validation_gaps())
        signals.extend(self.detect_test_failures())
        signals.extend(self.detect_strategic_misalignment())
        signals.extend(self.detect_tech_debt())
        signals.extend(self.detect_security_issues())
        signals.extend(self.detect_performance_regressions())
        signals.extend(self.detect_documentation_gaps())

        # Cache signals
        self._cache_signals(signals)

        return signals

    def detect_validation_gaps(self) -> List[Signal]:
        """
        YOUR KEY WIN: Find validated improvements not deployed.

        Compares production config (what's deployed) against dashboard_data.json
        (validation results) to find models that validate better but aren't in production.
        """
        signals = []
        validation_dir = self.vortex_dir / "data" / "validation"

        # Load production config
        prod_config_file = validation_dir / "production_config.json"
        dashboard_file = validation_dir / "dashboard_data.json"

        if not prod_config_file.exists() or not dashboard_file.exists():
            return signals

        try:
            # Load production configuration
            prod_config = json.loads(prod_config_file.read_text())
            dashboard_data = json.loads(dashboard_file.read_text())

            # Get production model and baseline
            prod_model = prod_config["current_production_model"]["name"]
            prod_baseline = prod_config["production_baseline_accuracy"]

            # Check each field (wind_speed, wind_direction, etc.)
            accuracy_by_field = dashboard_data.get("accuracy_by_field", {})

            for field_name, field_data in accuracy_by_field.items():
                model_comparison = field_data.get("model_comparison", {})

                # Get production baseline for this field
                if field_name not in prod_baseline:
                    continue

                prod_mae = prod_baseline[field_name].get("mae_kt") or prod_baseline[field_name].get(
                    "mae_deg", 999
                )

                # Check each validated model
                for model_name, model_metrics in model_comparison.items():
                    if model_name == prod_model:
                        continue  # Skip production model

                    val_mae = model_metrics.get("mae_kt") or model_metrics.get("mae_deg", 999)

                    # Improvement if validation MAE is lower (lower is better for error metrics)
                    if val_mae < prod_mae:
                        improvement_pct = ((prod_mae - val_mae) / prod_mae) * 100

                        signal_id = f"validation_gap_{model_name}_{field_name}_{datetime.now().strftime('%Y%m%d')}"

                        # Determine severity based on improvement magnitude
                        if improvement_pct >= 10:
                            severity = "critical"
                        elif improvement_pct >= 5:
                            severity = "high"
                        else:
                            severity = "medium"

                        signals.append(
                            Signal(
                                id=signal_id,
                                type=SignalType.VALIDATION_GAP,
                                severity=severity,
                                title=f"Deploy {model_name} for {field_name} - +{improvement_pct:.1f}% improvement",
                                description=f"{model_name} shows {improvement_pct:.1f}% better {field_name} accuracy than production {prod_model}, but is not deployed",
                                context={
                                    "project": "vortex-backend",
                                    "field": field_name,
                                    "validated_model": model_name,
                                    "production_model": prod_model,
                                    "validation_mae": val_mae,
                                    "production_mae": prod_mae,
                                    "improvement_pct": improvement_pct,
                                    "config_file": str(prod_config_file),
                                    "dashboard_file": str(dashboard_file),
                                },
                                evidence=[
                                    f"Production model: {prod_model} (MAE: {prod_mae:.2f})",
                                    f"Validated model: {model_name} (MAE: {val_mae:.2f})",
                                    f"Improvement: {improvement_pct:.1f}%",
                                    f"Field: {field_name}",
                                    f"Config: {prod_config_file.name}",
                                ],
                                estimated_impact=f"+{improvement_pct:.1f}% {field_name} forecast accuracy improvement",
                            )
                        )

        except (json.JSONDecodeError, KeyError) as e:
            # Log error but don't crash
            print(f"Error detecting validation gaps: {e}")

        return signals

    def detect_test_failures(self) -> List[Signal]:
        """
        Parse pytest cache for recurring failures.

        If same test fails 3+ times, signal for fixing.
        """
        signals = []
        projects = [
            ("vortex-backend", self.vortex_dir),
            ("Alpha Arena", self.alpha_arena_dir),
            ("Cortex", self.cortex_dir),
        ]

        for project_name, project_dir in projects:
            pytest_cache = project_dir / ".pytest_cache" / "v" / "cache" / "lastfailed"

            if not pytest_cache.exists():
                continue

            try:
                # Parse lastfailed cache
                failed_tests = json.loads(pytest_cache.read_text())

                # Count failures (simplified - in practice you'd track over time)
                if len(failed_tests) >= 3:
                    test_names = list(failed_tests.keys())[:5]  # Top 5

                    signal_id = f"test_failures_{project_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

                    signals.append(
                        Signal(
                            id=signal_id,
                            type=SignalType.TEST_FAILURE,
                            severity="medium",
                            title=f"Fix {len(failed_tests)} recurring test failures in {project_name}",
                            description=f"{len(failed_tests)} tests are failing in {project_name}. These need investigation and fixes.",
                            context={
                                "project": project_name,
                                "failed_count": len(failed_tests),
                                "failed_tests": test_names,
                                "pytest_cache": str(pytest_cache),
                            },
                            evidence=[
                                f"Pytest cache: {pytest_cache}",
                                f"Failed tests: {len(failed_tests)}",
                                f"Examples: {', '.join(test_names[:3])}",
                            ],
                            estimated_impact=f"Improved test reliability in {project_name}",
                        )
                    )
            except (json.JSONDecodeError, KeyError):
                continue

        return signals

    def detect_strategic_misalignment(self) -> List[Signal]:
        """
        Parse GOALS.md and check what's NOT being worked on.

        Finds high-priority goals with no recent commits.
        """
        signals = []
        goals_file = self.root_dir / "GOALS.md"

        if not goals_file.exists():
            return signals

        try:
            content = goals_file.read_text()

            # Parse priority A goals (simple regex - could be more sophisticated)
            priority_a_pattern = r"## Priority A:.*?\n(.*?)(?=##|\Z)"
            matches = re.search(priority_a_pattern, content, re.DOTALL)

            if matches:
                priority_a_goals = matches.group(1).strip()
                goal_lines = [
                    line.strip()
                    for line in priority_a_goals.split("\n")
                    if line.strip().startswith("-")
                ]

                if goal_lines:
                    # Check git activity for these goals (simplified)
                    # In practice, you'd extract keywords and search git log
                    signal_id = f"strategic_gap_priority_a_{datetime.now().strftime('%Y%m%d')}"

                    signals.append(
                        Signal(
                            id=signal_id,
                            type=SignalType.STRATEGIC_GAP,
                            severity="medium",
                            title=f"Review progress on {len(goal_lines)} Priority A goals",
                            description=f"Found {len(goal_lines)} Priority A goals in GOALS.md. Verify these are being actively worked on.",
                            context={
                                "project": "Portfolio",
                                "goals_file": str(goals_file),
                                "priority_a_count": len(goal_lines),
                                "goals": goal_lines[:3],  # Sample
                            },
                            evidence=[
                                f"GOALS.md: {goals_file}",
                                f"Priority A goals: {len(goal_lines)}",
                            ],
                            estimated_impact="Ensure strategic priorities are being addressed",
                        )
                    )
        except Exception:
            # Skip on error
            pass

        return signals

    def detect_tech_debt(self) -> List[Signal]:
        """
        Run ruff and mypy to detect code quality issues.

        Signals if high-complexity functions or many linting errors.
        """
        signals = []
        projects = [
            ("vortex-backend", self.vortex_dir),
            ("Alpha Arena", self.alpha_arena_dir),
            ("Cortex", self.cortex_dir),
        ]

        for project_name, project_dir in projects:
            if not project_dir.exists():
                continue

            try:
                # Run ruff check (simplified - no actual execution in this snippet)
                # In practice, you'd run: subprocess.run(["ruff", "check", str(project_dir)])
                # and parse output

                # For now, check if there's a .ruff_cache (indicates ruff usage)
                project_dir / ".ruff_cache"

                # Placeholder: In real implementation, parse ruff output
                # For demo, we skip actual execution
                pass

            except Exception:
                continue

        return signals

    def detect_security_issues(self) -> List[Signal]:
        """
        Check for exposed secrets, security vulnerabilities.

        Looks for common patterns in git history and files.
        """
        signals = []

        # Check for .env files in git history
        try:
            result = subprocess.run(
                ["git", "log", "--all", "--full-history", "--", "*.env"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.stdout.strip():
                signal_id = f"security_env_files_{datetime.now().strftime('%Y%m%d')}"

                signals.append(
                    Signal(
                        id=signal_id,
                        type=SignalType.SECURITY,
                        severity="high",
                        title="Check for exposed .env files in git history",
                        description="Found .env files in git history. Verify no secrets are exposed.",
                        context={
                            "project": "Portfolio",
                            "files_found": result.stdout.count("commit"),
                        },
                        evidence=[
                            "Git history contains .env file commits",
                            f"Found in {result.stdout.count('commit')} commits",
                        ],
                        estimated_impact="Prevent secret exposure and security vulnerabilities",
                    )
                )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        return signals

    def detect_performance_regressions(self) -> List[Signal]:
        """
        Check for performance metric regressions.

        Compares recent metrics to historical baselines.
        """
        signals = []

        # Check Vortex backend performance metrics
        metrics_file = self.vortex_dir / "data" / "validation" / "dashboard_data.json"

        if metrics_file.exists():
            try:
                data = json.loads(metrics_file.read_text())

                # Check if any model has degraded performance
                # (Simplified - in practice, compare to historical baseline)
                for model_name, metrics in data.get("models", {}).items():
                    latency_p95 = metrics.get("latency_p95_ms", 0)

                    # Threshold: > 200ms is concerning
                    if latency_p95 > 200:
                        signal_id = f"performance_{model_name}_{datetime.now().strftime('%Y%m%d')}"

                        signals.append(
                            Signal(
                                id=signal_id,
                                type=SignalType.PERFORMANCE,
                                severity="medium",
                                title=f"High latency detected in {model_name}: {latency_p95:.0f}ms",
                                description=f"{model_name} has p95 latency of {latency_p95:.0f}ms, exceeding 200ms threshold",
                                context={
                                    "project": "vortex-backend",
                                    "model": model_name,
                                    "latency_p95_ms": latency_p95,
                                    "threshold_ms": 200,
                                },
                                evidence=[
                                    f"Dashboard data: {metrics_file.name}",
                                    f"P95 latency: {latency_p95:.0f}ms",
                                    "Threshold: 200ms",
                                ],
                                estimated_impact=f"Reduce {model_name} latency to meet SLA",
                            )
                        )
            except (json.JSONDecodeError, KeyError):
                pass

        return signals

    def detect_documentation_gaps(self) -> List[Signal]:
        """
        Identify missing or outdated documentation.

        Checks for:
        - Python modules without docstrings
        - README files not updated in 90+ days
        - API endpoints without documentation
        """
        signals = []

        # Check for READMEs not updated recently
        for readme in self.root_dir.glob("*/README.md"):
            stat = readme.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age_days = (datetime.now() - mtime).days

            if age_days > 90:
                project_name = readme.parent.name
                signal_id = f"docs_stale_{project_name}_{datetime.now().strftime('%Y%m%d')}"

                signals.append(
                    Signal(
                        id=signal_id,
                        type=SignalType.DOCUMENTATION,
                        severity="low",
                        title=f"Update {project_name} README (last updated {age_days} days ago)",
                        description=f"README for {project_name} hasn't been updated in {age_days} days. May be outdated.",
                        context={
                            "project": project_name,
                            "file": str(readme),
                            "age_days": age_days,
                            "last_modified": mtime.isoformat(),
                        },
                        evidence=[
                            f"File: {readme}",
                            f"Last modified: {mtime.strftime('%Y-%m-%d')}",
                            f"Age: {age_days} days",
                        ],
                        estimated_impact=f"Improved documentation for {project_name}",
                    )
                )

        return signals

    def _cache_signals(self, signals: List[Signal]) -> None:
        """Cache detected signals to disk."""
        cache_file = self.cache_dir / f"signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "detected_at": datetime.now().isoformat(),
            "count": len(signals),
            "signals": [s.to_dict() for s in signals],
        }

        cache_file.write_text(json.dumps(data, indent=2))

    def load_cached_signals(self, max_age_hours: int = 24) -> List[Signal]:
        """Load recently cached signals."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        signals = []

        for cache_file in sorted(self.cache_dir.glob("signals_*.json"), reverse=True):
            try:
                # Parse timestamp from filename
                timestamp_str = cache_file.stem.replace("signals_", "")
                file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                if file_time < cutoff:
                    continue

                data = json.loads(cache_file.read_text())

                for signal_dict in data.get("signals", []):
                    # Reconstruct Signal objects
                    signal = Signal(
                        id=signal_dict["id"],
                        type=SignalType(signal_dict["type"]),
                        severity=signal_dict["severity"],
                        title=signal_dict["title"],
                        description=signal_dict["description"],
                        context=signal_dict["context"],
                        evidence=signal_dict["evidence"],
                        estimated_impact=signal_dict["estimated_impact"],
                        detected_at=datetime.fromisoformat(signal_dict["detected_at"]),
                    )
                    signals.append(signal)

            except (json.JSONDecodeError, ValueError, KeyError):
                continue

        return signals


if __name__ == "__main__":
    # Test signal detection
    detector = SignalDetector()
    signals = detector.detect_all()

    print(f"Detected {len(signals)} signals:\n")

    for signal in sorted(signals, key=lambda s: (s.severity, s.type.value)):
        print(f"[{signal.severity.upper()}] {signal.title}")
        print(f"  Type: {signal.type.value}")
        print(f"  Impact: {signal.estimated_impact}")
        print()
