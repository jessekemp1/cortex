"""
Behavioral Firewall — Pre-action verification against historical patterns.

Checks proposed actions (file changes, commands, git operations) against:
1. Seed anti-patterns (shipped with Cortex)
2. Project-specific learned patterns (from ~/.cortex/)
3. Recent fix history (prevents regression reintroduction)

Returns warnings that should be surfaced BEFORE the action executes.
This is the independent verification layer — separate from the model
making the suggestions.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FirewallWarning:
    """A warning from the behavioral firewall."""

    severity: str  # "critical", "high", "medium", "low"
    pattern_id: str
    pattern_name: str
    message: str
    suggestion: str
    confidence: float = 0.8

    def to_string(self) -> str:
        """Format for display."""
        tag = self.severity.upper()
        return f"[{tag}] {self.pattern_name}: {self.message}"


class BehavioralFirewall:
    """Pre-action verification layer.

    Checks proposed changes against known anti-patterns before they execute.
    Acts as an independent trust boundary — the firewall is separate from
    the model making suggestions.
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()

    def check_staged_changes(self) -> List[FirewallWarning]:
        """Check git staged changes against anti-patterns.

        Call this before committing to catch known problems.
        """
        warnings: List[FirewallWarning] = []

        try:
            diff = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if diff.returncode != 0:
                return warnings

            staged_files = diff.stdout.strip().split("\n") if diff.stdout.strip() else []

            # Get diff content for deeper analysis
            diff_content = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10,
            )
            diff_text = diff_content.stdout if diff_content.returncode == 0 else ""

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return warnings

        # Check each pattern category
        warnings.extend(self._check_secrets(staged_files, diff_text))
        warnings.extend(self._check_schema_without_migration(staged_files))
        warnings.extend(self._check_merge_conflicts(diff_text))
        warnings.extend(self._check_large_binaries(staged_files))
        warnings.extend(self._check_debug_in_production(staged_files, diff_text))
        warnings.extend(self._check_recent_fix_regression(staged_files))

        return warnings

    def check_command(self, command: str) -> List[FirewallWarning]:
        """Check a proposed command against anti-patterns.

        Call this before executing destructive commands.
        """
        warnings: List[FirewallWarning] = []
        cmd_lower = command.lower()

        # Force push to main
        if "push" in cmd_lower and ("--force" in cmd_lower or "-f " in cmd_lower):
            if "main" in cmd_lower or "master" in cmd_lower:
                warnings.append(
                    FirewallWarning(
                        severity="critical",
                        pattern_id="seed:git:force-push-main",
                        pattern_name="Force push to main",
                        message="Force pushing to the default branch rewrites shared history.",
                        suggestion="Use 'git revert' instead, or '--force-with-lease' on a feature branch.",
                        confidence=0.95,
                    )
                )

        # Destructive data operations
        destructive_patterns = [
            ("drop table", "DROP TABLE detected"),
            ("truncate ", "TRUNCATE detected"),
            ("rm -rf", "Recursive force delete detected"),
            ("delete from", "DELETE without WHERE clause risk"),
        ]
        for pattern, desc in destructive_patterns:
            if pattern in cmd_lower:
                warnings.append(
                    FirewallWarning(
                        severity="high",
                        pattern_id="seed:data:destructive-operation",
                        pattern_name="Destructive operation",
                        message=f"{desc}. This is irreversible without a backup.",
                        suggestion="Verify you have a backup, or use a soft-delete approach.",
                        confidence=0.90,
                    )
                )
                break

        return warnings

    def _check_secrets(self, staged_files: List[str], diff_text: str) -> List[FirewallWarning]:
        """Check for secrets in staged changes."""
        warnings = []

        # Check file names
        secret_files = [".env", "credentials.json", "secrets.yaml", ".secrets"]
        for f in staged_files:
            fname = Path(f).name.lower()
            if any(s in fname for s in secret_files):
                warnings.append(
                    FirewallWarning(
                        severity="critical",
                        pattern_id="seed:git:secret-in-commit",
                        pattern_name="Secret file staged",
                        message=f"'{f}' looks like a secrets file. It will be in git history permanently.",
                        suggestion="Remove from staging, add to .gitignore, and rotate any exposed credentials.",
                        confidence=0.95,
                    )
                )

        # Check diff content for secret patterns
        import re

        secret_patterns = [
            r'(?:API_KEY|SECRET|PASSWORD|TOKEN|PRIVATE_KEY)\s*[=:]\s*["\'][^"\']{8,}',
            r"(?:aws_secret_access_key|aws_access_key_id)\s*[=:]\s*\S+",
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style keys
            r"ghp_[a-zA-Z0-9]{36,}",  # GitHub personal access tokens
        ]
        for pattern in secret_patterns:
            if re.search(pattern, diff_text, re.IGNORECASE):
                warnings.append(
                    FirewallWarning(
                        severity="critical",
                        pattern_id="seed:git:secret-in-commit",
                        pattern_name="Secret in diff",
                        message="Possible API key or credential detected in staged changes.",
                        suggestion="Remove the secret, use environment variables, and rotate the credential.",
                        confidence=0.90,
                    )
                )
                break

        return warnings

    def _check_schema_without_migration(self, staged_files: List[str]) -> List[FirewallWarning]:
        """Check for schema changes without corresponding migration."""
        schema_files = [
            f
            for f in staged_files
            if any(kw in f.lower() for kw in ["models.py", "schema.py", ".model.ts", "entities.py"])
        ]
        migration_files = [
            f for f in staged_files if "migration" in f.lower() or "alembic" in f.lower()
        ]

        if schema_files and not migration_files:
            return [
                FirewallWarning(
                    severity="high",
                    pattern_id="seed:git:uncommitted-migration",
                    pattern_name="Schema change without migration",
                    message=f"Modified {', '.join(schema_files)} but no migration file.",
                    suggestion="Create a migration file so the change applies on deploy.",
                    confidence=0.80,
                )
            ]

        return []

    def _check_merge_conflicts(self, diff_text: str) -> List[FirewallWarning]:
        """Check for merge conflict markers in diff."""
        if "<<<<<<< " in diff_text or "=======" in diff_text and ">>>>>>> " in diff_text:
            return [
                FirewallWarning(
                    severity="critical",
                    pattern_id="seed:git:merge-conflict-markers",
                    pattern_name="Merge conflict markers",
                    message="Conflict markers (<<<<<<) detected in staged changes.",
                    suggestion="Resolve all merge conflicts before committing.",
                    confidence=0.99,
                )
            ]
        return []

    def _check_large_binaries(self, staged_files: List[str]) -> List[FirewallWarning]:
        """Check for large binary files."""
        binary_extensions = {
            ".pkl",
            ".h5",
            ".hdf5",
            ".parquet",
            ".zip",
            ".tar",
            ".gz",
            ".onnx",
            ".pt",
            ".pth",
            ".bin",
            ".weights",
        }
        large_binaries = [f for f in staged_files if Path(f).suffix.lower() in binary_extensions]

        if large_binaries:
            return [
                FirewallWarning(
                    severity="medium",
                    pattern_id="seed:git:large-binary",
                    pattern_name="Large binary staged",
                    message=f"Binary file(s) staged: {', '.join(large_binaries[:3])}",
                    suggestion="Consider Git LFS or .gitignore for binary/model files.",
                    confidence=0.85,
                )
            ]

        return []

    def _check_debug_in_production(
        self, staged_files: List[str], diff_text: str
    ) -> List[FirewallWarning]:
        """Check for debug mode in production config."""
        prod_files = [f for f in staged_files if "prod" in f.lower() or "deploy" in f.lower()]
        if (
            prod_files
            and "debug" in diff_text.lower()
            and ("true" in diff_text.lower() or "True" in diff_text)
        ):
            return [
                FirewallWarning(
                    severity="high",
                    pattern_id="seed:security:debug-in-production",
                    pattern_name="Debug mode in production",
                    message="DEBUG appears to be enabled in a production config file.",
                    suggestion="Set DEBUG = False for production. Use WARNING log level.",
                    confidence=0.80,
                )
            ]
        return []

    def _check_recent_fix_regression(self, staged_files: List[str]) -> List[FirewallWarning]:
        """Check if staged changes modify code that was recently fixed."""
        warnings = []

        try:
            # Get recent fix commits (last 2 weeks)
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--oneline",
                    "--since=2.weeks",
                    "--grep=fix",
                    "--name-only",
                    "--format=%H %s",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return warnings

            # Parse fix commits and their files
            fix_files: dict[str, str] = {}  # file -> fix commit message
            lines = result.stdout.strip().split("\n")
            current_msg = ""
            for line in lines:
                if line.startswith((" ", "\t")) or not line:
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and len(parts[0]) == 40:
                    current_msg = parts[1]
                elif line.strip():
                    fix_files[line.strip()] = current_msg

            # Check if staged files overlap with recently-fixed files
            for f in staged_files:
                if f in fix_files:
                    warnings.append(
                        FirewallWarning(
                            severity="medium",
                            pattern_id="seed:agent:reintroduce-bug",
                            pattern_name="Recently fixed file modified",
                            message=f"'{f}' was fixed recently: \"{fix_files[f]}\". Verify this change doesn't reintroduce the bug.",
                            suggestion="Review the fix commit before modifying this file.",
                            confidence=0.70,
                        )
                    )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return warnings
