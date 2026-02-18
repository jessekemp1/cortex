# security_5_validation

# Week 1: Security Scan Validation Implementation

## Overview

This implementation provides a comprehensive security validation framework including automated scanning, reporting, and CI/CD integration.

---

## 1. Security Validation Script (Main Script)

### File: `scripts/security_scan.py`

```python
#!/usr/bin/env python3
"""
Comprehensive Security Validation Script
Week 1: Critical Security Fixes

This script performs:
1. Dependency vulnerability scanning (safety)
2. Static code analysis (bandit)
3. SQL injection pattern detection
4. Input sanitization validation
5. Comprehensive report generation
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(Enum):
    """Security issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityFinding:
    """Represents a single security finding."""
    tool: str
    severity: Severity
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None
    cwe_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
            "cwe_id": self.cwe_id
        }


@dataclass
class SecurityReport:
    """Aggregated security report."""
    scan_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    project_path: str = ""
    findings: list[SecurityFinding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def add_finding(self, finding: SecurityFinding):
        self.findings.append(finding)

    def generate_summary(self):
        self.summary = {
            "total_findings": len(self.findings),
            "by_severity": {
                "critical": len([f for f in self.findings if f.severity == Severity.CRITICAL]),
                "high": len([f for f in self.findings if f.severity == Severity.HIGH]),
                "medium": len([f for f in self.findings if f.severity == Severity.MEDIUM]),
                "low": len([f for f in self.findings if f.severity == Severity.LOW]),
                "info": len([f for f in self.findings if f.severity == Severity.INFO]),
            },
            "by_tool": {}
        }
        for finding in self.findings:
            tool = finding.tool
            if tool not in self.summary["by_tool"]:
                self.summary["by_tool"][tool] = 0
            self.summary["by_tool"][tool] += 1

    def to_dict(self) -> dict:
        self.generate_summary()
        return {
            "scan_timestamp": self.scan_timestamp,
            "project_path": self.project_path,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings]
        }


class SecurityScanner:
    """Main security scanning orchestrator."""

    # SQL Injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        # String formatting in SQL queries
        (r'execute\s*\(\s*["\'].*%s.*["\'].*%', "String formatting in SQL execute"),
        (r'execute\s*\(\s*f["\']', "F-string in SQL execute"),
        (r'execute\s*\(\s*["\'].*\+', "String concatenation in SQL execute"),
        (r'cursor\.execute\s*\(\s*["\'].*\.format\s*\(', "str.format() in SQL execute"),

        # Raw SQL with user input
        (r'raw\s*\(\s*["\'].*%', "String formatting in raw SQL"),
        (r'raw\s*\(\s*f["\']', "F-string in raw SQL"),
        (r'RawSQL\s*\(\s*["\'].*\+', "String concatenation in RawSQL"),

        # ORM filter with raw input
        (r'\.extra\s*\(\s*where\s*=.*%', "String formatting in extra() where clause"),
        (r'\.extra\s*\(\s*select\s*=.*%', "String formatting in extra() select clause"),

        # Direct query execution
        (r'connection\.cursor\(\).*execute.*\+', "Direct cursor execution with concatenation"),
    ]

    # Input sanitization patterns to validate
    INPUT_SANITIZATION_PATTERNS = [
        # Forms without validation
        (r'request\.(GET|POST|data)\[', "Direct request data access without validation"),
        (r'request\.(GET|POST)\.get\([^,\)]+\)[^.]', "Request data without default or validation"),

        # Unsafe file operations
        (r'open\s*\(\s*request\.', "File open with unsanitized request data"),
        (r'Path\s*\(\s*request\.', "Path construction with unsanitized request data"),

        # Command injection risks
        (r'subprocess\.(run|call|Popen)\s*\(.*request\.', "Subprocess with request data"),
        (r'os\.system\s*\(.*request\.', "os.system with request data"),
        (r'eval\s*\(.*request\.', "eval with request data"),
        (r'exec\s*\(.*request\.', "exec with request data"),

        # Template injection
        (r'Template\s*\(\s*request\.', "Template instantiation with request data"),
        (r'render_template_string\s*\(.*request\.', "render_template_string with request data"),
    ]

    def __init__(self, project_path: str, output_dir: str = "security_reports"):
        self.project_path = Path(project_path).resolve()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.report = SecurityReport(project_path=str(self.project_path))

    def run_all_scans(self) -> SecurityReport:
        """Run all security scans."""
        print("=" * 60)
        print("🔒 Starting Comprehensive Security Scan")
        print("=" * 60)
        print(f"Project Path: {self.project_path}")
        print(f"Timestamp: {self.report.scan_timestamp}")
        print("=" * 60)

        self._run_safety_check()
        self._run_bandit_scan()
        self._check_sql_injection_patterns()
        self._validate_input_sanitization()
        self._check_hardcoded_secrets()

        self.report.generate_summary()
        self._generate_reports()

        return self.report

    def _run_safety_check(self):
        """Run safety check on all requirements files."""
        print("\n📦 Running Safety Check (Dependency Vulnerabilities)...")

        # Find all requirements files
        req_patterns = [
            "requirements*.txt",
            "**/requirements*.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile.lock"
        ]

        req_files = []
        for pattern in req_patterns:
            req_files.extend(self.project_path.glob(pattern))

        if not req_files:
            print("  ⚠️  No requirements files found")
            return

        for req_file in req_files:
            print(f"  Scanning: {req_file.relative_to(self.project_path)}")

            try:
                # Run safety check
                if req_file.suffix == '.txt':
                    cmd = ["safety", "check", "-r", str(req_file), "--json"]
                elif req_file.name == "pyproject.toml":
                    cmd = ["safety", "check", "--file", str(req_file), "--json"]
                else:
                    continue

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.project_path
                )

                if result.returncode != 0 and result.stdout:
                    try:
                        vulnerabilities = json.loads(result.stdout)
                        for vuln in vulnerabilities:
                            # Safety output format varies by version
                            if isinstance(vuln, list):
                                pkg_name, affected_version, installed_version, vuln_desc, vuln_id = vuln[:5]
                            else:
                                pkg_name = vuln.get("package_name", "unknown")
                                vuln_desc = vuln.get("vulnerability_description", "")
                                vuln_id = vuln.get("vulnerability_id", "")
                                installed_version = vuln.get("analyzed_version", "")

                            severity = self._classify_safety_severity(vuln_desc)

                            self.report.add_finding(SecurityFinding(
                                tool="safety",
                                severity=severity,
                                title=f"Vulnerable dependency: {pkg_name}",
                                description=vuln_desc,
                                file_path=str(req_file.relative_to(self.project_path)),
                                recommendation=f"Update {pkg_name} to a patched version",
                                cwe_id=vuln_id if vuln_id else None
                            ))
                    except json.JSONDecodeError:
                        # Handle non-JSON output
                        if "vulnerabilities found" in result.stdout.lower():
                            self.report.add_finding(SecurityFinding(
                                tool="safety",
                                severity=Severity.HIGH,
                                title="Dependency vulnerabilities detected",
                                description=result.stdout[:500],
                                file_path=str(req_file.relative_to(self.project_path)),
                                recommendation="Review safety output and update vulnerable packages"
                            ))

            except FileNotFoundError:
                print("  ⚠️  Safety not installed. Install with: pip install safety")
                self.report.add_finding(SecurityFinding(
                    tool="safety",
                    severity=Severity.INFO,
                    title="Safety scanner not available",
                    description="Install safety to scan for dependency vulnerabilities",
                    recommendation="pip install safety"
                ))
                break
            except Exception as e:
                print(f"  ❌ Error scanning {req_file}: {e}")

    def _run_bandit_scan(self):
        """Run bandit security scanner on Python code."""
        print("\n🔍 Running Bandit Security Scanner...")

        try:
            cmd = [
                "bandit",
                "-r", str(self.project_path),
                "-f", "json",
                "-ll",  # Report medium and higher severity
                "--exclude", ".venv,venv,env,.env,node_modules,__pycache__,.git"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.stdout:
                try:
                    bandit_results = json.loads(result.stdout)

                    for issue in bandit_results.get("results", []):
                        severity = self._map_bandit_severity(issue.get("issue_severity", "MEDIUM"))

                        self.report.add_finding(SecurityFinding(
                            tool="bandit",
                            severity=severity,
                            title=issue.get("issue_text", "Security issue detected"),
                            description=f"{issue.get('test_name', '')}: {issue.get('issue_text', '')}",
                            file_path=issue.get("filename", "").replace(str(self.project_path) + "/", ""),
                            line_number=issue.get("line_number"),
                            code_snippet=issue.get("code", ""),
                            recommendation=issue.get("more_info", ""),
                            cwe_id=f"CWE-{issue.get('issue_cwe', {}).get('id', '')}" if issue.get('issue_cwe') else None
                        ))

                    print(f"  Found {len(bandit_results.get('results', []))} issues")

                except json.JSONDecodeError:
                    print(f"  ⚠️  Could not parse bandit output")

        except FileNotFoundError:
            print("  ⚠️  Bandit not installed. Install with: pip install bandit")
            self.report.add_finding(SecurityFinding(
                tool="bandit",
                severity=Severity.INFO,
                title="Bandit scanner not available",
                description="Install bandit to perform static code analysis",
                recommendation="pip install bandit"
            ))
        except Exception as e:
            print(f"  ❌ Error running bandit: {e}")

    def _check_sql_injection_patterns(self):
        """Check for SQL injection vulnerabilities."""
        print("\n💉 Checking for SQL Injection Patterns...")

        python_files = list(self.project_path.rglob("*.py"))
        python_files = [f for f in python_files if not self._should_skip_file(f)]

        findings_count = 0

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')

                for line_num, line in enumerate(lines, 1):
                    for pattern, description in self.SQL_INJECTION_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            self.report.add_finding(SecurityFinding(
                                tool="sql_injection_scan",
                                severity=Severity.HIGH,
                                title=f"Potential SQL Injection: {description}",
                                description=f"Detected pattern that may indicate SQL injection vulnerability",
                                file_path=str(py_file.relative_to(self.project_path)),
                                line_number=line_num,
                                code_snippet=line.strip()[:200],
                                recommendation="Use parameterized queries or ORM methods instead of string formatting",
                                cwe_id="CWE-89"
                            ))
                            findings_count += 1

            except Exception as e:
                print(f"  ⚠️  Error scanning {py_file}: {e}")

        print(f"  Found {findings_count} potential SQL injection issues")

    def _validate_input_sanitization(self):
        """Validate input handling has proper sanitization."""
        print("\n🧹 Validating Input Sanitization...")

        python_files = list(self.project_path.rglob("*.py"))
        python_files = [f for f in python_files if not self._should_skip_file(f)]

        findings_count = 0

        for py_file in python_files:
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
