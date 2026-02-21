#!/usr/bin/env python3
"""
Workflow Hooks for Automatic Batch Job Creation

Integrates with git hooks and other workflows to automatically queue batch jobs.
"""

import subprocess
import sys
from pathlib import Path


class WorkflowBatchHooks:
    """Auto-batch common tasks based on workflow events"""

    def __init__(self, root_dir: str = os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))):
        self.root_dir = Path(root_dir)
        self.cortex_dir = self.root_dir / "cortex"

    def _run_batch_add(
        self, description: str, priority: str = "normal", deadline_hours: int = 24
    ) -> bool:
        """Helper to add batch job via CLI"""
        try:
            cmd = [
                "python",
                str(self.cortex_dir / "cli.py"),
                "batch",
                "add",
                description,
                "--priority",
                priority,
                "--deadline",
                str(deadline_hours),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except Exception as e:
            print(f"Warning: Failed to queue batch job: {e}", file=sys.stderr)
            return False

    def on_pr_created(self, pr_number: int, pr_url: str = None) -> None:
        """
        Hook: After PR created → queue code review batch job

        Usage:
            from cortex.batch.workflow_hooks import WorkflowBatchHooks
            hooks = WorkflowBatchHooks()
            hooks.on_pr_created(pr_number=4, pr_url="https://github.com/.../pull/4")
        """
        description = f"Code review for PR #{pr_number}"
        if pr_url:
            description += f" - {pr_url}"
        description += " (security, performance, correctness, maintainability)"

        success = self._run_batch_add(description, priority="normal", deadline_hours=24)

        if success:
            print(f"✅ Queued overnight review for PR #{pr_number}")
            print("💰 Saving 50% vs real-time review")
            print("📊 Check status: cortex batch status")
        else:
            print(f"⚠️  Failed to queue batch review for PR #{pr_number}")
            print(f"💡 Run manually: /batch-submit review PR #{pr_number}")

    def on_feature_merged(self, project: str, files: list[str] = None) -> None:
        """
        Hook: After feature merged → queue docs generation

        Usage:
            hooks.on_feature_merged(project="vortex-backend", files=["app/api.py", "models/ensemble.py"])
        """
        file_list = ", ".join(files) if files else "project files"
        description = f"Generate/update documentation for {project}: {file_list}"

        success = self._run_batch_add(description, priority="low", deadline_hours=48)

        if success:
            print(f"✅ Queued docs generation for {project}")
            print("📚 Docs will be ready in 24-48 hours")
        else:
            print("⚠️  Failed to queue docs generation")
            print(f"💡 Run manually: /batch-submit docs {project}")

    def on_end_of_day(self) -> None:
        """
        Hook: End of day → queue overnight pattern scan

        Usage in ~/.cortex/LaunchAgents or cron:
            0 22 * * * cd ~/projects/cortex && python -c "from batch.workflow_hooks import WorkflowBatchHooks; WorkflowBatchHooks().on_end_of_day()"
        """
        description = "Nightly pattern scan: anti-patterns, circular imports, security issues, code duplication across all active projects"

        success = self._run_batch_add(description, priority="normal", deadline_hours=12)

        if success:
            print("✅ Queued nightly pattern scan")
            print("🔍 Results will be in morning briefing")
        else:
            print("⚠️  Failed to queue pattern scan")

    def on_dependency_update(self, project: str) -> None:
        """
        Hook: After dependency update → queue security audit

        Usage:
            hooks.on_dependency_update(project="alpha_arena")
        """
        description = f"Security audit after dependency update: Check {project} for vulnerable dependencies and security issues"

        success = self._run_batch_add(description, priority="high", deadline_hours=24)

        if success:
            print(f"✅ Queued security audit for {project}")
            print("🛡️  Results in 24 hours")
        else:
            print("⚠️  Failed to queue security audit")

    def suggest_batch_for_files(self, changed_files: list[str]) -> None:
        """
        Suggest batch jobs based on what files changed

        Usage in git hooks:
            hooks.suggest_batch_for_files(["Vortex/backend/tests/test_api.py", "Vortex/backend/app/api.py"])
        """
        suggestions = []

        # Check if tests changed → suggest test coverage analysis
        test_files = [f for f in changed_files if "test" in f.lower()]
        if test_files:
            suggestions.append("test-coverage: Analyze test coverage gaps")

        # Check if docs changed → suggest docs validation
        doc_files = [
            f for f in changed_files if any(ext in f.lower() for ext in [".md", "/docs/", "readme"])
        ]
        if doc_files:
            suggestions.append("docs: Validate documentation completeness")

        # Check if API files changed → suggest API docs
        api_files = [
            f
            for f in changed_files
            if any(pattern in f.lower() for pattern in ["api", "endpoint", "route"])
        ]
        if api_files:
            suggestions.append("docs: Update API documentation")

        if suggestions:
            print("\n💡 Batch Job Suggestions (50% cost savings):")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"   {i}. {suggestion}")
            print("\n   Submit with: /batch-submit <type>")
            print('   Or manually: cortex batch add "<description>"')


def install_git_hooks() -> None:
    """
    Install git hooks for automatic batch suggestions

    Creates:
    - post-commit hook: Suggests batch jobs after commit
    - post-merge hook: Suggests batch jobs after PR merge
    """
    hooks_dir = Path("~/projects/.git/hooks")
    if not hooks_dir.exists():
        print("Warning: Not in a git repository root")
        return

    # Post-commit hook
    post_commit = hooks_dir / "post-commit"
    post_commit.write_text(
        """#!/bin/bash
# Auto-suggest batch jobs after commit

python3 -c "
from cortex.batch.workflow_hooks import WorkflowBatchHooks
import subprocess

# Get changed files
files = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'], text=True).strip().split('\\n')

hooks = WorkflowBatchHooks()
hooks.suggest_batch_for_files(files)
" 2>/dev/null || true
"""
    )
    post_commit.chmod(0o755)
    print(f"✅ Installed: {post_commit}")

    # Post-merge hook (for PR merges)
    post_merge = hooks_dir / "post-merge"
    post_merge.write_text(
        """#!/bin/bash
# Auto-queue docs generation after PR merge

python3 -c "
from cortex.batch.workflow_hooks import WorkflowBatchHooks
import subprocess
import os

# Get project name
project = os.path.basename(os.getcwd())

# Get merged files
files = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'], text=True).strip().split('\\n')

hooks = WorkflowBatchHooks()
hooks.on_feature_merged(project=project, files=files[:5])  # Limit to 5 files
" 2>/dev/null || true
"""
    )
    post_merge.chmod(0o755)
    print(f"✅ Installed: {post_merge}")

    print("\n✅ Git hooks installed successfully")
    print("Now automatic batch suggestions will trigger after commits/merges")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Workflow batch hooks")
    parser.add_argument(
        "action", choices=["install-hooks", "on-pr", "on-merge", "on-eod", "suggest"]
    )
    parser.add_argument("--pr", type=int, help="PR number")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--files", nargs="*", help="Changed files")

    args = parser.parse_args()
    hooks = WorkflowBatchHooks()

    if args.action == "install-hooks":
        install_git_hooks()
    elif args.action == "on-pr" and args.pr:
        hooks.on_pr_created(pr_number=args.pr)
    elif args.action == "on-merge" and args.project:
        hooks.on_feature_merged(project=args.project, files=args.files or [])
    elif args.action == "on-eod":
        hooks.on_end_of_day()
    elif args.action == "suggest" and args.files:
        hooks.suggest_batch_for_files(args.files)
