#!/usr/bin/env python3
"""
Status Plugin Implementation

Shows comprehensive project status with Cortex-powered intelligent analysis.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cortex.plugins.base import BasePlugin


class StatusPlugin(BasePlugin):
    """
    Status plugin implementation.

    Provides comprehensive project status including:
    - Git status and recent commits
    - Running services
    - Intelligent commit suggestions
    """

    def __init__(self, plugin_dir: Path):
        """
        Initialize status plugin.

        Args:
            plugin_dir: Path to plugin directory
        """
        super().__init__(plugin_dir)

        # Default configuration
        self.default_config = {
            "show_git": True,
            "show_services": True,
            "show_anomalies": True,
            "max_commits": 10,
            "max_recommendations": 5,
            "projects": {
                "vortex": {"path": "Vortex/VortexV2", "ports": [8000, 8501]},
                "arena": {"path": "alpha_arena", "ports": [8502]},
                "cortex": {"path": "cortex", "ports": []},
            },
        }

        # Load config
        self.config_file = Path.home() / ".cortex" / "plugins" / "status.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load plugin configuration."""
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text())
            except json.JSONDecodeError:
                pass
        return self.default_config

    def execute(self, args: List[str], **kwargs) -> int:
        """
        Execute status plugin.

        Args:
            args: Command-line arguments
            **kwargs: Additional context

        Returns:
            Exit code (0 = success)
        """
        # Handle --help
        if "--help" in args or "-h" in args:
            print(self.help())
            return 0

        # Parse arguments
        parser = argparse.ArgumentParser(
            prog="status",
            description="Show comprehensive project status",
            add_help=False,
        )
        parser.add_argument("--quick", action="store_true", help="Quick status only")
        parser.add_argument("--project", type=str, help="Specific project")
        parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

        try:
            parsed_args = parser.parse_args(args)
        except SystemExit:
            return 1

        try:
            # Get current directory from kwargs or use cwd
            current_dir = kwargs.get("current_dir", Path.cwd())

            if parsed_args.quick:
                return self._quick_status(current_dir, parsed_args.verbose)
            elif parsed_args.project:
                return self._project_status(parsed_args.project, current_dir, parsed_args.verbose)
            else:
                return self._full_status(current_dir, parsed_args.verbose)

        except KeyboardInterrupt:
            print("\n⚠️  Interrupted", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            if parsed_args.verbose:
                import traceback

                traceback.print_exc()
            return 2

    def _quick_status(self, current_dir: Path, verbose: bool = False) -> int:
        """
        Show quick status summary.

        Args:
            current_dir: Current directory
            verbose: Verbose output

        Returns:
            Exit code
        """
        print("📊 Quick Status")
        print("─" * 40)

        # Git status
        branch, modified_count, untracked_count = self._get_git_status(current_dir)
        if branch:
            print(f"📂 Branch: {branch}")
            print(f"📝 Changes: {modified_count} modified, {untracked_count} untracked")
        else:
            print("📂 Not a git repository")

        # Running services
        service_count = 0
        for project, config in self.config["projects"].items():
            for port in config["ports"]:
                if self._is_port_in_use(port):
                    service_count += 1
        print(f"🏃 Services: {service_count} running")

        # Intelligence suggestions
        suggestions = self._get_intelligence_suggestions(current_dir, verbose)
        if suggestions:
            safe_count = sum(1 for s in suggestions if s.get("risk", "") == "safe")
            needs_tests = sum(
                1 for s in suggestions if "missing test" in s.get("warning", "").lower()
            )
            print(
                f"🧠 Suggestions: {len(suggestions)} groups ({safe_count} safe, {needs_tests} need tests)"
            )

        return 0

    def _full_status(self, current_dir: Path, verbose: bool = False) -> int:
        """
        Show full comprehensive status.

        Args:
            current_dir: Current directory
            verbose: Verbose output

        Returns:
            Exit code
        """
        print("📊 Cortex Portfolio Status")
        print("═" * 60)
        print()

        # Git status
        if self.config["show_git"]:
            print("🔧 Git Status")
            print("─" * 40)
            branch, modified_count, untracked_count = self._get_git_status(current_dir)
            if branch:
                print(f"Branch: {branch}")
                print(f"Status: {modified_count} files modified, {untracked_count} untracked")
            else:
                print("Not a git repository")
            print()

        # Running services
        if self.config["show_services"]:
            print("🏃 Running Services")
            print("─" * 40)
            self._show_services()
            print()

        # Recent commits
        print("📝 Recent Commits")
        print("─" * 40)
        self._show_recent_commits(current_dir, self.config["max_commits"])
        print()

        # Cortex intelligence
        print("🧠 Cortex Intelligence: Commit Suggestions")
        print("─" * 60)
        suggestions = self._get_intelligence_suggestions(current_dir, verbose)
        if suggestions:
            self._show_intelligence_suggestions(suggestions, self.config["max_recommendations"])
        else:
            print("No suggestions available")
            print("(Run with --verbose to see debug info)")
        print()

        # Next actions
        print("Next Actions:")
        self._show_next_actions(suggestions)

        return 0

    def _project_status(self, project: str, current_dir: Path, verbose: bool = False) -> int:
        """
        Show status for specific project.

        Args:
            project: Project name
            current_dir: Current directory
            verbose: Verbose output

        Returns:
            Exit code
        """
        if project not in self.config["projects"]:
            print(f"❌ Unknown project: {project}", file=sys.stderr)
            print(f"Available projects: {', '.join(self.config['projects'].keys())}")
            return 1

        project_config = self.config["projects"][project]
        project_path = current_dir / project_config["path"]

        print(f"📊 {project.title()} Status")
        print("═" * 60)
        print()

        # Git status
        branch, modified_count, _ = self._get_git_status(project_path)
        print(f"Git: {branch} branch, {modified_count} files modified")

        # Services
        running_ports = [port for port in project_config["ports"] if self._is_port_in_use(port)]
        if running_ports:
            print(f"Services: {', '.join(f':{p}' for p in running_ports)} ✓")
        else:
            print("Services: Not running")

        # Recent commit
        commits = self._get_recent_commits_data(project_path, 1)
        if commits:
            print(f'Recent: "{commits[0][1]}" ({commits[0][2]})')

        print()
        print("Recommendations:")
        suggestions = self._get_intelligence_suggestions(project_path, verbose)
        if suggestions:
            for suggestion in suggestions[:3]:
                risk_icon = "✓" if suggestion.get("risk") == "safe" else "⚠"
                print(f"  {risk_icon} {suggestion.get('title', 'No title')}")
        else:
            print("  - No recommendations")

        return 0

    def _get_git_status(self, directory: Path) -> Tuple[Optional[str], int, int]:
        """
        Get git status.

        Args:
            directory: Directory to check

        Returns:
            Tuple of (branch, modified_count, untracked_count)
        """
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None, 0, 0

            branch = result.stdout.strip()

            # Get status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return branch, 0, 0

            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            modified_count = sum(1 for line in lines if line and line[0] in "MADRC")
            untracked_count = sum(1 for line in lines if line.startswith("??"))

            return branch, modified_count, untracked_count

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None, 0, 0

    def _show_services(self) -> None:
        """Show running services."""
        for project, config in self.config["projects"].items():
            for port in config["ports"]:
                pid = self._get_pid_for_port(port)
                if pid:
                    service_name = self._get_service_name(project, port)
                    print(f"✓ {service_name} (PID {pid}) - http://localhost:{port}")
                else:
                    service_name = self._get_service_name(project, port)
                    print(f"✗ {service_name} - Not running")

    def _get_service_name(self, project: str, port: int) -> str:
        """Get service name for project and port."""
        names = {
            ("vortex", 8000): "VortexV2 API",
            ("vortex", 8501): "VortexV2 UI",
            ("arena", 8502): "Alpha Arena Dashboard",
        }
        return names.get((project, port), f"{project.title()} (:{port})")

    def _is_port_in_use(self, port: int) -> bool:
        """Check if port is in use."""
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=2
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _get_pid_for_port(self, port: int) -> Optional[int]:
        """Get PID for port."""
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split("\n")[0])
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        return None

    def _show_recent_commits(self, directory: Path, max_commits: int) -> None:
        """Show recent commits."""
        commits = self._get_recent_commits_data(directory, max_commits)
        if commits:
            for commit_hash, message, time_ago in commits:
                print(f"{commit_hash} {message}")
        else:
            print("No recent commits")

    def _get_recent_commits_data(
        self, directory: Path, max_commits: int
    ) -> List[Tuple[str, str, str]]:
        """Get recent commits data."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{max_commits}", "--oneline", "--format=%h %s (%cr)"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        commit_hash = parts[0]
                        rest = parts[1]
                        # Extract message and time
                        if "(" in rest and rest.endswith(")"):
                            message = rest[: rest.rfind("(")].strip()
                            time_ago = rest[rest.rfind("(") + 1 : -1]
                            commits.append((commit_hash, message, time_ago))
                return commits
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return []

    def _get_intelligence_suggestions(self, directory: Path, verbose: bool = False) -> List[Dict]:
        """
        Get intelligence suggestions from analyzer.

        Args:
            directory: Directory to analyze
            verbose: Verbose output

        Returns:
            List of suggestion dicts
        """
        # Path to analyzer script
        analyzer_path = directory / "cortex" / "intelligence" / "status" / "analyze.py"

        if not analyzer_path.exists():
            if verbose:
                print(f"Debug: Analyzer not found at {analyzer_path}", file=sys.stderr)
            return []

        try:
            result = subprocess.run(
                [sys.executable, str(analyzer_path)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                if verbose:
                    print(f"Debug: Analyzer failed: {result.stderr}", file=sys.stderr)
                return []

            # Parse JSON output
            if result.stdout.strip():
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    if verbose:
                        print(f"Debug: JSON parse error: {e}", file=sys.stderr)
                        print(f"Debug: Output was: {result.stdout[:200]}", file=sys.stderr)

        except subprocess.TimeoutExpired:
            if verbose:
                print("Debug: Analyzer timed out", file=sys.stderr)
        except Exception as e:
            if verbose:
                print(f"Debug: Analyzer error: {e}", file=sys.stderr)

        return []

    def _show_intelligence_suggestions(self, suggestions: List[Dict], max_suggestions: int) -> None:
        """Show intelligence suggestions."""
        for i, suggestion in enumerate(suggestions[:max_suggestions], 1):
            title = suggestion.get("title", "Untitled")
            confidence = suggestion.get("confidence", 0)
            risk = suggestion.get("risk", "unknown")
            files = suggestion.get("files", [])
            warning = suggestion.get("warning", "")

            print(f'Group {i}: "{title}" (Confidence: {confidence}%)')

            # Risk indicator
            if risk == "safe":
                print("  ✓ Safe to commit")
            elif "test" in warning.lower():
                print("  ⚠ Missing tests - consider adding tests first")
            else:
                print("  ❌ High risk - review carefully")

            # Files
            if files:
                print("  Files:")
                for file in files[:5]:  # Show first 5 files
                    print(f"    - {file}")
                if len(files) > 5:
                    print(f"    ... and {len(files) - 5} more")

            print()

    def _show_next_actions(self, suggestions: List[Dict]) -> None:
        """Show recommended next actions."""
        if not suggestions:
            print("  1. Make changes and commit")
            return

        actions = []
        for i, suggestion in enumerate(suggestions[:5], 1):
            risk = suggestion.get("risk", "unknown")
            title = suggestion.get("title", "Untitled")

            if risk == "safe":
                actions.append(f"Commit Group {i} ({title[:30]}...)")
            elif "test" in suggestion.get("warning", "").lower():
                file = suggestion.get("files", [""])[0]
                if file:
                    actions.append(f"Add tests for {Path(file).name}")
            else:
                file = suggestion.get("files", [""])[0]
                if file:
                    actions.append(f"Review {Path(file).name} carefully")

        for i, action in enumerate(actions[:5], 1):
            print(f"  {i}. {action}")
