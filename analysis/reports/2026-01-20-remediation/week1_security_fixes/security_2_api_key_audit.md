# security_2_api_key_audit

# Security Audit: Hardcoded API Keys in Alpha Arena Data Providers

## Executive Summary

I'll conduct a comprehensive security audit of the Alpha Arena data providers for hardcoded credentials, then provide specific remediation steps.

---

## Audit Process & Findings

### 1. Automated Pattern Search

First, let's create an audit script to scan for potential credential leaks:

```python
#!/usr/bin/env python3
"""
Security audit script for detecting hardcoded credentials.
File: scripts/security_audit.py
"""

import re
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import json


@dataclass
class SecurityFinding:
    """Represents a potential security issue."""
    file_path: str
    line_number: int
    line_content: str
    pattern_matched: str
    severity: str  # HIGH, MEDIUM, LOW
    masked_value: Optional[str] = None


class CredentialAuditor:
    """Audits codebase for hardcoded credentials."""
    
    # Patterns that indicate potential hardcoded credentials
    CREDENTIAL_PATTERNS = {
        # API Keys
        r'api[_-]?key\s*[=:]\s*["\'][^"\']{10,}["\']': 'API Key Assignment',
        r'apikey\s*[=:]\s*["\'][^"\']{10,}["\']': 'API Key Assignment',
        r'API_KEY\s*=\s*["\'][^"\']{10,}["\']': 'API Key Constant',
        
        # Secrets
        r'secret[_-]?key\s*[=:]\s*["\'][^"\']{10,}["\']': 'Secret Key Assignment',
        r'api[_-]?secret\s*[=:]\s*["\'][^"\']{10,}["\']': 'API Secret Assignment',
        r'SECRET\s*=\s*["\'][^"\']{10,}["\']': 'Secret Constant',
        
        # Tokens
        r'token\s*[=:]\s*["\'][^"\']{20,}["\']': 'Token Assignment',
        r'access[_-]?token\s*[=:]\s*["\'][^"\']{10,}["\']': 'Access Token',
        r'bearer\s+[a-zA-Z0-9_-]{20,}': 'Bearer Token',
        
        # Passwords
        r'password\s*[=:]\s*["\'][^"\']{4,}["\']': 'Password Assignment',
        r'passwd\s*[=:]\s*["\'][^"\']{4,}["\']': 'Password Assignment',
        r'pwd\s*[=:]\s*["\'][^"\']{4,}["\']': 'Password Assignment',
        
        # Binance Specific
        r'binance[_-]?api[_-]?key\s*[=:]\s*["\'][^"\']{10,}["\']': 'Binance API Key',
        r'binance[_-]?secret\s*[=:]\s*["\'][^"\']{10,}["\']': 'Binance Secret',
        
        # Generic credential patterns
        r'credentials\s*[=:]\s*\{[^}]*["\']key["\']\s*:': 'Credentials Object',
        r'auth[_-]?key\s*[=:]\s*["\'][^"\']{10,}["\']': 'Auth Key',
        
        # Base64 encoded secrets (common pattern)
        r'["\'][A-Za-z0-9+/]{40,}={0,2}["\']': 'Potential Base64 Secret',
        
        # Connection strings
        r'mongodb(\+srv)?://[^:]+:[^@]+@': 'MongoDB Connection String',
        r'postgres://[^:]+:[^@]+@': 'PostgreSQL Connection String',
        r'mysql://[^:]+:[^@]+@': 'MySQL Connection String',
        r'redis://[^:]+:[^@]+@': 'Redis Connection String',
    }
    
    # Files/patterns to exclude from scanning
    EXCLUDE_PATTERNS = [
        r'\.pyc$',
        r'__pycache__',
        r'\.git/',
        r'\.env\.example',
        r'\.env\.template',
        r'test.*mock',
        r'\.md$',
        r'requirements.*\.txt$',
    ]
    
    # Known safe patterns (false positives)
    SAFE_PATTERNS = [
        r'os\.environ\.get\s*\(\s*["\']',
        r'os\.getenv\s*\(\s*["\']',
        r'env\s*\(\s*["\']',
        r'config\.get\s*\(\s*["\']',
        r'settings\.',
        r'#.*example',
        r'#.*placeholder',
        r'<your[_-]?api[_-]?key>',
        r'YOUR[_-]?API[_-]?KEY',
        r'xxx+',
        r'\*{3,}',
    ]
    
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.findings: List[SecurityFinding] = []
        
    def should_exclude_file(self, file_path: str) -> bool:
        """Check if file should be excluded from scanning."""
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        return False
    
    def is_safe_pattern(self, line: str) -> bool:
        """Check if line matches known safe patterns."""
        for pattern in self.SAFE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def mask_credential(self, value: str) -> str:
        """Mask a potential credential for safe reporting."""
        if len(value) <= 8:
            return '*' * len(value)
        return value[:4] + '*' * (len(value) - 8) + value[-4:]
    
    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """Scan a single file for credential patterns."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return findings
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments that are clearly documentation
            stripped = line.strip()
            if stripped.startswith('#') and 'example' in stripped.lower():
                continue
                
            # Skip safe patterns
            if self.is_safe_pattern(line):
                continue
            
            # Check each credential pattern
            for pattern, description in self.CREDENTIAL_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    # Double-check it's not a safe pattern
                    if not self.is_safe_pattern(line):
                        # Determine severity
                        severity = 'HIGH'
                        if 'example' in line.lower() or 'template' in line.lower():
                            severity = 'LOW'
                        elif 'test' in str(file_path).lower():
                            severity = 'MEDIUM'
                        
                        findings.append(SecurityFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            line_content=line.strip()[:100],  # Truncate long lines
                            pattern_matched=description,
                            severity=severity,
                            masked_value=self.mask_credential(match.group())
                        ))
        
        return findings
    
    def scan_directory(self, directory: str = "src/data/providers") -> List[SecurityFinding]:
        """Scan a directory recursively for credential patterns."""
        target_path = self.root_path / directory
        
        if not target_path.exists():
            print(f"Warning: Directory {target_path} does not exist")
            return []
        
        for file_path in target_path.rglob("*.py"):
            if not self.should_exclude_file(str(file_path)):
                self.findings.extend(self.scan_file(file_path))
        
        return self.findings
    
    def scan_git_history(self, num_commits: int = 10) -> List[dict]:
        """Scan recent git history for accidentally committed secrets."""
        git_findings = []
        
        try:
            # Get list of recent commits
            result = subprocess.run(
                ['git', 'log', f'-{num_commits}', '--pretty=format:%H'],
                capture_output=True,
                text=True,
                cwd=self.root_path
            )
            
            if result.returncode != 0:
                print("Warning: Could not access git history")
                return git_findings
            
            commits = result.stdout.strip().split('\n')
            
            for commit in commits:
                if not commit:
                    continue
                    
                # Get diff for this commit
                diff_result = subprocess.run(
                    ['git', 'show', commit, '--pretty=format:', '--name-only'],
                    capture_output=True,
                    text=True,
                    cwd=self.root_path
                )
                
                files_changed = diff_result.stdout.strip().split('\n')
                
                # Check if any provider files were modified
                provider_files = [f for f in files_changed if 'provider' in f.lower()]
                
                if provider_files:
                    # Get the actual diff content
                    content_result = subprocess.run(
                        ['git', 'show', commit],
                        capture_output=True,
                        text=True,
                        cwd=self.root_path
                    )
                    
                    # Scan diff for credential patterns
                    for pattern, description in self.CREDENTIAL_PATTERNS.items():
                        if re.search(pattern, content_result.stdout, re.IGNORECASE):
                            git_findings.append({
                                'commit': commit[:8],
                                'files': provider_files,
                                'pattern': description,
                                'severity': 'HIGH'
                            })
                            
        except FileNotFoundError:
            print("Warning: git not found, skipping history scan")
        except Exception as e:
            print(f"Warning: Error scanning git history: {e}")
        
        return git_findings
    
    def check_gitignore(self) -> dict:
        """Verify .env and other sensitive files are in .gitignore."""
        gitignore_path = self.root_path / '.gitignore'
        
        required_entries = [
            '.env',
            '.env.local',
            '.env.*.local',
            '*.pem',
            '*.key',
            'secrets/',
            'credentials/',
        ]
        
        result = {
            'gitignore_exists': gitignore_path.exists(),
            'missing_entries': [],
            'present_entries': []
        }
        
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                content = f.read()
                
            for entry in required_entries:
                # Check for exact match or pattern match
                if entry in content or entry.replace('*', '') in content:
                    result['present_entries'].append(entry)
                else:
                    result['missing_entries'].append(entry)
        else:
            result['missing_entries'] = required_entries
            
        return result
    
    def check_env_usage(self, directory: str = "src/data/providers") -> dict:
        """Verify environment variables are used for credentials."""
        target_path = self.root_path / directory
        
        env_usage = {
            'files_checked': [],
            'proper_env_usage': [],
            'missing_env_usage': []
        }
        
        if not target_path.exists():
            return env_usage
        
        for file_path in target_path.rglob("*.py"):
            env_usage['files_checked'].append(str(file_path))
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check for proper environment variable patterns
            proper_patterns = [
                r'os\.environ\.get\s*\(\s*["\'].*(?:API|KEY|SECRET|TOKEN)',
                r'os\.getenv\s*\(\s*["\'].*(?:API|KEY|SECRET|TOKEN)',
                r'config\.[a-z_]+\s*#.*(?:from env|environment)',
            ]
            
            has_proper_usage = any(
                re.search(p, content, re.IGNORECASE) 
                for p in proper_patterns
            )
            
            if has_proper_usage:
                env_usage['proper_env_usage'].append(str(file_path))
            
            # Check if file likely needs credentials but doesn't use env vars
            needs_creds = any(
                keyword in content.lower() 
                for keyword in ['api', 'authenticate', 'client', 'connect']
            )
            
            if needs_creds and not has_proper_usage:
                env_usage['missing_env_usage'].append(str(file_path))
        
        return env_usage
    
    def generate_report(self) -> str:
        """Generate a comprehensive security audit report."""
        report = []
        report.append("=" * 70)
        report.append("ALPHA ARENA SECURITY AUDIT REPORT")
        report.append("Data Providers Credential Scan")
        report.append("=" * 70)
        report.append("")
        
        # Scan providers directory
        report.append("## 1. CREDENTIAL PATTERN SCAN")
        report.append("-" * 40)
        
        self.findings = []  # Reset findings
        self.scan_directory("src/data/providers")
        
        if self.findings:
            report.append(f"⚠️  FOUND {len(self.findings)} POTENTIAL ISSUES:")
            report.append("")
            
            for finding in sorted(self.findings, key=lambda x: x.severity):
                report.append(f"  [{finding.severity}] {finding.file_path}:{finding.line_number}")
                report.append(f"    Pattern: {finding.pattern_matched}")
                report.append(f"    Content: {finding.line_content[:60]}...")
                report.append(f"    Masked:  {finding.masked_value}")
                report.append("")
        else:
            report.append("✅ No hardcoded credentials detected in pattern scan")
        
        report.append("")
        
        # Git history scan
        report.append("## 2. GIT HISTORY SCAN (Last 10 commits)")
        report.append("-" * 40)
        
        git_findings = self.scan_git_history()
        
        if git_findings:
            report.append(f"⚠️  FOUND {len(git_findings)} POTENTIAL ISSUES IN GIT HISTORY:")
            for finding in git_findings:
                report.append(f"  Commit: {finding['commit']}")
                report.append(f"  Files: {', '.join(finding['files'])}")
                report.append(f"  Pattern: {finding['pattern']