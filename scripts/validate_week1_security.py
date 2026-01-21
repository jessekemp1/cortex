#!/usr/bin/env python3
"""
Week 1 Security Validation Script

Validates that all Week 1 critical security fixes have been applied:
1. No exposed usernames in documentation
2. No hardcoded API keys in source code
3. Critical CVE dependencies are patched
4. Config file permissions are secure

Usage:
    python scripts/validate_week1_security.py [--project-root ~/Dev]
"""

import re
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from security import get_file_permissions, get_permission_string, is_permission_secure

# ANSI color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class ValidationResult:
    """Tracks validation results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def pass_check(self, message: str):
        self.passed.append(message)
        print(f"{GREEN}✓{RESET} {message}")

    def fail_check(self, message: str, detail: str = ""):
        self.failed.append((message, detail))
        print(f"{RED}✗{RESET} {message}")
        if detail:
            print(f"  {detail}")

    def warn_check(self, message: str, detail: str = ""):
        self.warnings.append((message, detail))
        print(f"{YELLOW}⚠{RESET} {message}")
        if detail:
            print(f"  {detail}")

    def print_summary(self):
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"{GREEN}Passed:{RESET} {len(self.passed)}")
        print(f"{RED}Failed:{RESET} {len(self.failed)}")
        print(f"{YELLOW}Warnings:{RESET} {len(self.warnings)}")
        print()

        if self.failed:
            print(f"{RED}FAILED CHECKS:{RESET}")
            for msg, detail in self.failed:
                print(f"  • {msg}")
                if detail:
                    print(f"    {detail}")
            print()

        if self.warnings:
            print(f"{YELLOW}WARNINGS:{RESET}")
            for msg, detail in self.warnings:
                print(f"  • {msg}")
                if detail:
                    print(f"    {detail}")
            print()

        if not self.failed:
            print(f"{GREEN}✓ All critical security checks passed!{RESET}")
            return 0
        else:
            print(f"{RED}✗ Some security checks failed. Please review and fix.{RESET}")
            return 1


def check_username_exposures(root_dir: Path, results: ValidationResult):
    """Check for exposed usernames in documentation files."""
    print(f"\n{BLUE}[1] Checking for Username Exposures...{RESET}")

    # Patterns that indicate username exposure
    username_patterns = [
        r'/Users/[a-zA-Z][a-zA-Z0-9._-]+/',  # macOS paths
        r'C:\\Users\\[a-zA-Z][a-zA-Z0-9._-]+\\',  # Windows paths
        r'username:\s*[a-zA-Z][a-zA-Z0-9._-]+@',  # Email-like usernames
    ]

    # Files to check
    patterns_to_check = [
        'README.md',
        '**/README.md',
        '**/*.md',
        'requirements.txt',
        '**/requirements.txt',
        '**/.env.template',
        '**/.env.example',
    ]

    exposed_files = []

    for pattern in patterns_to_check:
        for file_path in root_dir.glob(pattern):
            # Skip hidden dirs, venv, node_modules
            if any(part.startswith('.') or part in {'venv', 'node_modules', '__pycache__'}
                   for part in file_path.parts):
                continue

            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    for pattern_re in username_patterns:
                        if re.search(pattern_re, content):
                            exposed_files.append((file_path, pattern_re))
                            break
                except Exception:
                    pass

    if exposed_files:
        for file_path, pattern in exposed_files:
            results.fail_check(
                f"Username exposure in {file_path.relative_to(root_dir)}",
                f"Found pattern: {pattern}"
            )
    else:
        results.pass_check("No username exposures found in documentation")


def check_hardcoded_credentials(root_dir: Path, results: ValidationResult):
    """Check for hardcoded API keys and credentials."""
    print(f"\n{BLUE}[2] Checking for Hardcoded Credentials...{RESET}")

    # Patterns for hardcoded credentials
    credential_patterns = [
        (r'api[_-]?key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', 'Hardcoded API key'),
        (r'secret\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', 'Hardcoded secret'),
        (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
        (r'sk-[a-zA-Z0-9]{20,}', 'Anthropic/OpenAI API key'),
        (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Access Token'),
        (r'xai-[a-zA-Z0-9]{20,}', 'XAI API key'),
    ]

    # Files to check (only .py files)
    python_files = list(root_dir.glob('**/*.py'))

    hardcoded_found = []

    for file_path in python_files:
        # Skip venv, __pycache__, etc.
        if any(part in {'.venv', 'venv', 'node_modules', '__pycache__', '.git'}
               for part in file_path.parts):
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            for pattern_re, description in credential_patterns:
                matches = re.finditer(pattern_re, content, re.IGNORECASE)
                for match in matches:
                    # Skip if it's obviously a template/example
                    matched_text = match.group(0)
                    if any(placeholder in matched_text.lower()
                           for placeholder in ['your_', 'example', 'placeholder', 'xxx', 'yyy']):
                        continue

                    hardcoded_found.append((file_path, description, matched_text[:50]))
        except Exception:
            pass

    if hardcoded_found:
        for file_path, desc, snippet in hardcoded_found:
            results.fail_check(
                f"{desc} in {file_path.relative_to(root_dir)}",
                f"Snippet: {snippet}..."
            )
    else:
        results.pass_check("No hardcoded credentials found in source code")


def check_dependency_versions(root_dir: Path, results: ValidationResult):
    """Check that critical CVE dependencies are patched."""
    print(f"\n{BLUE}[3] Checking Critical Dependency Versions...{RESET}")

    # Required minimum versions to fix CVEs
    required_versions = {
        'requests': '2.31.0',
        'urllib3': '2.0.7',
        'PyYAML': '6.0.1',
        'setuptools': '70.0.0',
    }

    requirements_files = [
        root_dir / 'cortex' / 'requirements.txt',
        root_dir / 'alpha_arena' / 'requirements.txt',
        root_dir / 'Vortex' / 'VortexV2' / 'requirements.txt',
    ]

    all_passed = True

    for req_file in requirements_files:
        if not req_file.exists():
            results.warn_check(f"Requirements file not found: {req_file.relative_to(root_dir)}")
            continue

        content = req_file.read_text(encoding='utf-8')

        for package, min_version in required_versions.items():
            # Check if package is mentioned and has correct version
            pattern = rf'{package}\s*>=?\s*([0-9.]+)'
            match = re.search(pattern, content, re.IGNORECASE)

            if match:
                found_version = match.group(1)
                # Simple version comparison (works for these cases)
                if found_version >= min_version:
                    results.pass_check(
                        f"{req_file.name}: {package}>={found_version} (CVE patched)"
                    )
                else:
                    results.fail_check(
                        f"{req_file.name}: {package}>={found_version} (needs >={min_version})"
                    )
                    all_passed = False
            # If package not found, it might not be used in this project (OK)

    if all_passed:
        results.pass_check("All critical CVE patches applied where applicable")


def check_config_permissions(results: ValidationResult):
    """Check that config file permissions are secure."""
    print(f"\n{BLUE}[4] Checking Config File Permissions...{RESET}")

    config_dir = Path.home() / '.cortex'

    if not config_dir.exists():
        results.warn_check(f"Config directory {config_dir} does not exist")
        return

    # Check directory itself
    if is_permission_secure(config_dir, is_directory=True):
        results.pass_check(f"{config_dir} has secure permissions (700)")
    else:
        perms = get_permission_string(get_file_permissions(config_dir))
        results.fail_check(
            f"{config_dir} has insecure permissions ({perms})",
            "Run: python scripts/fix_config_permissions.py"
        )

    # Sample some important files
    important_files = [
        config_dir / 'config.yaml',
        config_dir / '.env',
    ]

    for file_path in important_files:
        if not file_path.exists():
            continue

        if is_permission_secure(file_path, is_directory=False):
            results.pass_check(f"{file_path.name} has secure permissions (600)")
        else:
            perms = get_permission_string(get_file_permissions(file_path))
            results.fail_check(
                f"{file_path.name} has insecure permissions ({perms})",
                "Run: python scripts/fix_config_permissions.py"
            )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate Week 1 Security Fixes")
    parser.add_argument(
        '--project-root',
        type=Path,
        default=Path.home() / 'Dev',
        help="Project root directory (default: ~/Dev)"
    )

    args = parser.parse_args()
    root_dir = args.project_root.resolve()

    if not root_dir.exists():
        print(f"{RED}Error: Project root does not exist: {root_dir}{RESET}")
        sys.exit(1)

    print("=" * 60)
    print("🔒 Week 1 Security Validation")
    print("=" * 60)
    print(f"Project Root: {root_dir}")
    print("=" * 60)

    results = ValidationResult()

    # Run all checks
    check_username_exposures(root_dir, results)
    check_hardcoded_credentials(root_dir, results)
    check_dependency_versions(root_dir, results)
    check_config_permissions(results)

    # Print summary
    exit_code = results.print_summary()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
