#!/usr/bin/env python3
"""
Cortex Health Check - Self-diagnostic system.

Validates installation, dependencies, and configuration.
Provides auto-fix capabilities for common issues.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class HealthIssue:
    """A health check issue."""

    severity: str  # "error", "warning", "info"
    category: str  # "python", "dependencies", "database", "permissions", "config"
    message: str
    fix_command: Optional[str] = None  # Auto-fix command
    fix_description: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Health check results."""

    passed: int = 0
    warnings: int = 0
    errors: int = 0
    issues: List[HealthIssue] = field(default_factory=list)

    @property
    def total_checks(self) -> int:
        """Total checks performed."""
        return self.passed + self.warnings + self.errors

    @property
    def is_healthy(self) -> bool:
        """True if no errors."""
        return self.errors == 0


class HealthChecker:
    """
    Cortex health check system.

    Validates:
    - Python version (3.11+)
    - Virtual environment
    - Core dependencies
    - Optional dependencies
    - Database accessibility
    - Directory permissions
    - Configuration files
    """

    def __init__(self, cortex_root: Optional[Path] = None):
        """Initialize health checker."""
        if cortex_root is None:
            cortex_root = Path(__file__).parent.parent
        self.cortex_root = cortex_root
        self.result = HealthCheckResult()

    # =========================================================================
    # Main Check Interface
    # =========================================================================

    def run_all_checks(self, verbose: bool = False) -> HealthCheckResult:
        """
        Run all health checks.

        Args:
            verbose: Print detailed output

        Returns:
            HealthCheckResult with all issues
        """
        if verbose:
            print("🔍 Cortex Health Check")
            print("=" * 60)

        # Python environment
        self._check_python_version(verbose)
        self._check_virtual_env(verbose)

        # Dependencies
        self._check_core_dependencies(verbose)
        self._check_optional_dependencies(verbose)

        # Storage
        self._check_database(verbose)
        self._check_directories(verbose)

        # Configuration
        self._check_config_files(verbose)

        # Projects
        self._check_active_projects(verbose)

        if verbose:
            self._print_summary()

        return self.result

    # =========================================================================
    # Python Environment Checks
    # =========================================================================

    def _check_python_version(self, verbose: bool):
        """Check Python version is 3.11+."""
        version = sys.version_info

        if version >= (3, 11):
            self.result.passed += 1
            if verbose:
                print(f"✓ Python {version.major}.{version.minor}.{version.micro} installed")
        else:
            self.result.errors += 1
            self.result.issues.append(
                HealthIssue(
                    severity="error",
                    category="python",
                    message=f"Python {version.major}.{version.minor} is too old (need 3.11+)",
                    fix_description="Upgrade to Python 3.11 or later",
                )
            )
            if verbose:
                print(f"✗ Python {version.major}.{version.minor} (need 3.11+)")

    def _check_virtual_env(self, verbose: bool):
        """Check if running in a virtual environment."""
        in_venv = hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        )

        if in_venv:
            self.result.passed += 1
            if verbose:
                print(f"✓ Virtual environment active ({sys.prefix})")
        else:
            self.result.warnings += 1
            self.result.issues.append(
                HealthIssue(
                    severity="warning",
                    category="python",
                    message="Not running in a virtual environment",
                    fix_description="Activate venv: source venv/bin/activate",
                )
            )
            if verbose:
                print("⚠ Not in virtual environment")

    # =========================================================================
    # Dependency Checks
    # =========================================================================

    def _check_core_dependencies(self, verbose: bool):
        """Check core dependencies are installed."""
        core_deps = [
            "anthropic",
            "pydantic",
            "requests",
        ]

        for dep in core_deps:
            try:
                __import__(dep)
                self.result.passed += 1
                if verbose:
                    print(f"✓ {dep} installed")
            except ImportError:
                self.result.errors += 1
                self.result.issues.append(
                    HealthIssue(
                        severity="error",
                        category="dependencies",
                        message=f"Core dependency '{dep}' not installed",
                        fix_command=f"pip install {dep}",
                        fix_description=f"Install {dep}",
                    )
                )
                if verbose:
                    print(f"✗ {dep} missing")

    def _check_optional_dependencies(self, verbose: bool):
        """Check optional dependencies."""
        optional_deps = {
            "fastapi": "Bridge API",
            "uvicorn": "Bridge API server",
            "playwright": "Browser automation",
            "pytest": "Testing",
        }

        for dep, purpose in optional_deps.items():
            try:
                __import__(dep)
                self.result.passed += 1
                if verbose:
                    print(f"✓ {dep} installed ({purpose})")
            except ImportError:
                self.result.warnings += 1
                if verbose:
                    print(f"⚠ {dep} not installed ({purpose} - optional)")

    # =========================================================================
    # Storage Checks
    # =========================================================================

    def _check_database(self, verbose: bool):
        """Check database accessibility."""
        db_path = Path.home() / ".cortex" / "orchestration.db"

        try:
            # Try to import database module
            from orchestration.database import OrchestrationDatabase

            # Try to create database instance
            OrchestrationDatabase()
            self.result.passed += 1
            if verbose:
                print(f"✓ Database accessible ({db_path})")

        except ImportError:
            self.result.warnings += 1
            if verbose:
                print("⚠ Database module not available (optional)")

        except Exception as e:
            self.result.errors += 1
            self.result.issues.append(
                HealthIssue(
                    severity="error",
                    category="database",
                    message=f"Database error: {e}",
                    fix_description="Check database file permissions",
                )
            )
            if verbose:
                print(f"✗ Database error: {e}")

    def _check_directories(self, verbose: bool):
        """Check critical directories are writable."""
        critical_dirs = [
            Path.home() / ".cortex",
            Path.home() / ".claude" / "graph",
        ]

        for dir_path in critical_dirs:
            if not dir_path.exists():
                self.result.warnings += 1
                self.result.issues.append(
                    HealthIssue(
                        severity="warning",
                        category="permissions",
                        message=f"Directory missing: {dir_path}",
                        fix_command=f"mkdir -p {dir_path}",
                        fix_description=f"Create directory: {dir_path}",
                    )
                )
                if verbose:
                    print(f"⚠ Directory missing: {dir_path}")

            elif not os.access(dir_path, os.W_OK):
                self.result.errors += 1
                self.result.issues.append(
                    HealthIssue(
                        severity="error",
                        category="permissions",
                        message=f"Directory not writable: {dir_path}",
                        fix_command=f"chmod u+w {dir_path}",
                        fix_description=f"Fix permissions: {dir_path}",
                    )
                )
                if verbose:
                    print(f"✗ Directory not writable: {dir_path}")

            else:
                self.result.passed += 1
                if verbose:
                    print(f"✓ Directory writable: {dir_path}")

    # =========================================================================
    # Configuration Checks
    # =========================================================================

    def _check_config_files(self, verbose: bool):
        """Check configuration files exist."""
        config_files = [
            (Path.home() / ".cortex" / "preferences.json", False),  # Optional
            (Path.home() / ".cortex" / "session_memory.jsonl", False),  # Optional
        ]

        for config_path, required in config_files:
            if config_path.exists():
                self.result.passed += 1
                if verbose:
                    print(f"✓ Config exists: {config_path.name}")
            elif required:
                self.result.errors += 1
                self.result.issues.append(
                    HealthIssue(
                        severity="error",
                        category="config",
                        message=f"Required config missing: {config_path}",
                        fix_description="Run /onboard to configure",
                    )
                )
                if verbose:
                    print(f"✗ Required config missing: {config_path.name}")
            else:
                self.result.passed += 1
                if verbose:
                    print("✓ Optional config (will be created on first use)")

    # =========================================================================
    # Project Checks
    # =========================================================================

    def _check_active_projects(self, verbose: bool):
        """Check for orchestration issues."""
        try:
            from orchestration.anomaly_detector import OrchestrationAnomalyManager
            from orchestration.database import OrchestrationDatabase

            db = OrchestrationDatabase()
            manager = OrchestrationAnomalyManager(db, enable_alerts=False)
            anomalies = manager.detect_all({})

            critical_count = sum(1 for a in anomalies if a.severity.value == "CRITICAL")
            warning_count = sum(1 for a in anomalies if a.severity.value == "WARNING")

            if critical_count > 0:
                self.result.warnings += 1
                self.result.issues.append(
                    HealthIssue(
                        severity="warning",
                        category="orchestration",
                        message=f"{critical_count} CRITICAL anomalies detected",
                        fix_description="Run /status to see anomalies",
                    )
                )
                if verbose:
                    print(f"⚠ {critical_count} CRITICAL anomalies detected")
            else:
                self.result.passed += 1
                if verbose:
                    print(f"✓ No critical anomalies ({warning_count} warnings)")

        except Exception as e:
            if verbose:
                print(f"⚠ Could not check anomalies: {e}")

    # =========================================================================
    # Auto-fix
    # =========================================================================

    def auto_fix(self, dry_run: bool = True) -> List[str]:
        """
        Auto-fix fixable issues.

        Args:
            dry_run: If True, only show what would be fixed

        Returns:
            List of fix commands executed
        """
        fixed = []

        for issue in self.result.issues:
            if not issue.fix_command:
                continue

            if dry_run:
                print(f"Would run: {issue.fix_command}")
                print(f"  ({issue.fix_description})")
            else:
                try:
                    subprocess.run(issue.fix_command, shell=True, check=True)
                    fixed.append(issue.fix_command)
                    print(f"✓ Fixed: {issue.fix_description}")
                except subprocess.CalledProcessError as e:
                    print(f"✗ Failed to fix: {issue.fix_description}")
                    print(f"  Error: {e}")

        return fixed

    # =========================================================================
    # Output
    # =========================================================================

    def _print_summary(self):
        """Print summary of results."""
        print("\n" + "=" * 60)
        print(f"Checks: {self.result.total_checks}")
        print(f"  ✓ Passed: {self.result.passed}")
        print(f"  ⚠ Warnings: {self.result.warnings}")
        print(f"  ✗ Errors: {self.result.errors}")

        if self.result.issues:
            print("\nIssues:")
            for i, issue in enumerate(self.result.issues, 1):
                icon = "✗" if issue.severity == "error" else "⚠"
                print(f"  {icon} {issue.message}")
                if issue.fix_description:
                    print(f"     → {issue.fix_description}")

        if self.result.errors > 0:
            print("\n💡 Run with --fix to auto-fix issues")

        print("=" * 60)

        if self.result.is_healthy:
            print("✅ Cortex is healthy!")
        else:
            print(f"🔴 {self.result.errors} error(s) need attention")


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI for health checks."""
    import argparse

    parser = argparse.ArgumentParser(description="Cortex health check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--quiet", action="store_true", help="Only show issues")
    args = parser.parse_args()

    checker = HealthChecker()
    result = checker.run_all_checks(verbose=not args.quiet)

    if args.fix and result.issues:
        print("\n🔧 Auto-fixing issues...")
        checker.auto_fix(dry_run=False)

    sys.exit(0 if result.is_healthy else 1)


if __name__ == "__main__":
    main()
