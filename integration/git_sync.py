"""
Git Synchronizer for Cortex

Provides safe git sync operations:
- Pull and rebase on main
- Fetch from all remotes
- Clean stale branches
- Full sync workflow
"""

import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    operation: str
    message: str
    details: Optional[str] = None


@dataclass
class SyncStatus:
    """Preview of what sync operations would do."""
    current_branch: str
    is_on_main: bool
    has_uncommitted: bool
    uncommitted_count: int
    behind_main: int
    ahead_of_main: int
    stale_branches: List[str]
    merged_branches: List[str]
    unmerged_stale: List[str]
    remote_deleted: List[str]
    actions_needed: List[str]


class GitSynchronizer:
    """
    Safe git synchronization operations.

    Usage:
        sync = GitSynchronizer("/path/to/repo")
        status = sync.get_sync_status()
        results = sync.full_sync(clean_branches=True)
    """

    PROTECTED_BRANCHES = {"main", "master", "develop", "staging", "production"}

    def __init__(self, repo_path: str = None):
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()

    def _run_git(self, args: List[str], check: bool = True) -> Tuple[bool, str, str]:
        """Run a git command and return (success, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def _get_current_branch(self) -> str:
        success, stdout, _ = self._run_git(["branch", "--show-current"])
        return stdout if success else "unknown"

    def _has_uncommitted_changes(self) -> Tuple[bool, int]:
        success, stdout, _ = self._run_git(["status", "--porcelain"])
        if not success:
            return False, 0
        # Ignore untracked (??) and submodule changes (lowercase first char like 'm')
        lines = [l for l in stdout.split("\n")
                 if l.strip() and not l.startswith("??") and not l[0].islower()]
        return len(lines) > 0, len(lines)

    def _get_ahead_behind(self, branch: str = None) -> Tuple[int, int]:
        branch = branch or self._get_current_branch()
        if branch == "main":
            return 0, 0
        success, stdout, _ = self._run_git([
            "rev-list", "--left-right", "--count", f"main...{branch}"
        ])
        if success and stdout:
            parts = stdout.split()
            if len(parts) == 2:
                return int(parts[1]), int(parts[0])
        return 0, 0

    def _get_stale_branches(self, days: int = 7) -> List[str]:
        stale = []
        success, stdout, _ = self._run_git([
            "for-each-ref", "--sort=-committerdate",
            "--format=%(refname:short)|%(committerdate:unix)", "refs/heads/"
        ])
        if not success:
            return stale

        now = datetime.now().timestamp()
        cutoff = now - (days * 24 * 60 * 60)

        for line in stdout.split("\n"):
            if "|" not in line:
                continue
            branch, timestamp = line.split("|")
            if branch in self.PROTECTED_BRANCHES:
                continue
            try:
                if float(timestamp) < cutoff:
                    stale.append(branch)
            except ValueError:
                continue
        return stale

    def _is_branch_merged(self, branch: str) -> bool:
        success, stdout, _ = self._run_git(["branch", "--merged", "main"])
        if success:
            merged = [b.strip().lstrip("* ") for b in stdout.split("\n")]
            return branch in merged
        return False

    def _get_gone_branches(self) -> List[str]:
        gone = []
        success, stdout, _ = self._run_git([
            "for-each-ref", "--format=%(refname:short) %(upstream:track)", "refs/heads/"
        ])
        if success:
            for line in stdout.split("\n"):
                if "[gone]" in line:
                    branch = line.split()[0]
                    if branch not in self.PROTECTED_BRANCHES:
                        gone.append(branch)
        return gone

    def get_sync_status(self) -> SyncStatus:
        current = self._get_current_branch()
        has_uncommitted, uncommitted_count = self._has_uncommitted_changes()
        ahead, behind = self._get_ahead_behind()
        stale = self._get_stale_branches()
        gone = self._get_gone_branches()

        merged = [b for b in stale if self._is_branch_merged(b)]
        unmerged = [b for b in stale if not self._is_branch_merged(b)]

        actions = []
        if behind > 0:
            actions.append(f"Rebase on main ({behind} commits behind)")
        if stale:
            actions.append(f"Clean {len(stale)} stale branches")
        if gone:
            actions.append(f"Remove {len(gone)} gone remote branches")
        if not actions:
            actions.append("Already in sync")

        return SyncStatus(
            current_branch=current, is_on_main=(current == "main"),
            has_uncommitted=has_uncommitted, uncommitted_count=uncommitted_count,
            behind_main=behind, ahead_of_main=ahead, stale_branches=stale,
            merged_branches=merged, unmerged_stale=unmerged,
            remote_deleted=gone, actions_needed=actions
        )

    def fetch_all(self, prune: bool = True) -> SyncResult:
        args = ["fetch", "--all"]
        if prune:
            args.append("--prune")
        success, stdout, stderr = self._run_git(args)
        return SyncResult(success, "fetch",
            "Fetched from all remotes" if success else "Fetch failed", stdout or stderr)

    def pull_main(self) -> SyncResult:
        current = self._get_current_branch()
        self._run_git(["fetch", "origin", "main"])

        if current != "main":
            success, _, err = self._run_git(["checkout", "main"])
            if not success:
                return SyncResult(False, "pull_main", f"Failed to checkout main: {err}")
            success, stdout, err = self._run_git(["pull", "origin", "main"])
            if not success:
                self._run_git(["checkout", current])
                return SyncResult(False, "pull_main", f"Failed to pull main: {err}")
            self._run_git(["checkout", current])
            return SyncResult(True, "pull_main", "Updated main branch", stdout)
        else:
            success, stdout, err = self._run_git(["pull", "origin", "main"])
            return SyncResult(success, "pull_main",
                "Updated main branch" if success else f"Pull failed: {err}", stdout)

    def rebase_on_main(self) -> SyncResult:
        current = self._get_current_branch()
        if current == "main":
            return SyncResult(True, "rebase", "Already on main, nothing to rebase")

        has_changes, count = self._has_uncommitted_changes()
        if has_changes:
            return SyncResult(False, "rebase",
                f"Cannot rebase: {count} uncommitted changes. Commit or stash first.")

        success, stdout, stderr = self._run_git(["rebase", "main"])
        if not success:
            self._run_git(["rebase", "--abort"])
            return SyncResult(False, "rebase", "Rebase failed - conflicts detected. Aborted.", stderr)
        return SyncResult(True, "rebase", f"Rebased {current} on main", stdout)

    def clean_stale_branches(self, force: bool = False, dry_run: bool = False) -> SyncResult:
        current = self._get_current_branch()
        stale = self._get_stale_branches()
        stale = [b for b in stale if b != current and b not in self.PROTECTED_BRANCHES]

        if not stale:
            return SyncResult(True, "clean", "No stale branches to clean")

        deleted, skipped = [], []
        for branch in stale:
            is_merged = self._is_branch_merged(branch)
            if dry_run:
                deleted.append(f"{branch} ({'merged' if is_merged else 'unmerged'})")
                continue
            if is_merged or force:
                flag = "-d" if is_merged else "-D"
                success, _, _ = self._run_git(["branch", flag, branch])
                if success:
                    deleted.append(branch)
                else:
                    skipped.append(branch)
            else:
                skipped.append(f"{branch} (unmerged, use --force)")

        if dry_run:
            return SyncResult(True, "clean", f"Would delete {len(deleted)} branches", "\n".join(deleted))

        msg = f"Deleted {len(deleted)} branches"
        if skipped:
            msg += f", skipped {len(skipped)}"
        return SyncResult(True, "clean", msg, f"Deleted: {', '.join(deleted)}" if deleted else None)

    def prune_gone_branches(self, dry_run: bool = False) -> SyncResult:
        gone = self._get_gone_branches()
        current = self._get_current_branch()
        gone = [b for b in gone if b != current]

        if not gone:
            return SyncResult(True, "prune_gone", "No gone branches to prune")
        if dry_run:
            return SyncResult(True, "prune_gone", f"Would delete {len(gone)} gone branches", "\n".join(gone))

        deleted = []
        for branch in gone:
            success, _, _ = self._run_git(["branch", "-D", branch])
            if success:
                deleted.append(branch)
        return SyncResult(True, "prune_gone", f"Deleted {len(deleted)} gone branches",
            ", ".join(deleted) if deleted else None)

    def full_sync(self, clean_branches: bool = False, force_clean: bool = False) -> List[SyncResult]:
        results = []
        has_changes, count = self._has_uncommitted_changes()
        if has_changes:
            results.append(SyncResult(False, "preflight",
                f"Cannot sync: {count} uncommitted changes. Commit or stash first."))
            return results

        results.append(self.fetch_all(prune=True))
        results.append(self.pull_main())

        current = self._get_current_branch()
        if current != "main":
            results.append(self.rebase_on_main())

        if clean_branches:
            results.append(self.clean_stale_branches(force=force_clean))
            results.append(self.prune_gone_branches())

        return results

    def format_status(self, status: SyncStatus) -> str:
        lines = ["## Git Sync Status\n"]
        lines.append(f"**Branch**: `{status.current_branch}`")
        if status.has_uncommitted:
            lines.append(f"**Warning**: {status.uncommitted_count} uncommitted changes")
        if status.behind_main > 0:
            lines.append(f"**Behind main**: {status.behind_main} commits")
        if status.ahead_of_main > 0:
            lines.append(f"**Ahead of main**: {status.ahead_of_main} commits")

        if status.stale_branches:
            lines.append(f"\n### Stale Branches ({len(status.stale_branches)})")
            for branch in status.merged_branches[:5]:
                lines.append(f"- `{branch}` (merged, safe to delete)")
            for branch in status.unmerged_stale[:5]:
                lines.append(f"- `{branch}` (unmerged)")

        if status.remote_deleted:
            lines.append(f"\n### Gone Remote Branches ({len(status.remote_deleted)})")
            for branch in status.remote_deleted[:5]:
                lines.append(f"- `{branch}`")

        lines.append("\n### Actions Needed")
        for action in status.actions_needed:
            lines.append(f"- {action}")
        return "\n".join(lines)

    def format_results(self, results: List[SyncResult]) -> str:
        lines = ["## Sync Results\n"]
        for result in results:
            icon = "✅" if result.success else "❌"
            lines.append(f"{icon} **{result.operation}**: {result.message}")
            if result.details:
                lines.append(f"   {result.details[:100]}")

        success_count = sum(1 for r in results if r.success)
        total = len(results)
        if success_count == total:
            lines.append(f"\n✅ All {total} operations completed successfully")
        else:
            lines.append(f"\n⚠️ {success_count}/{total} operations succeeded")
        return "\n".join(lines)


def get_sync_status(repo_path: str = None) -> SyncStatus:
    return GitSynchronizer(repo_path).get_sync_status()

def quick_sync(repo_path: str = None) -> List[SyncResult]:
    return GitSynchronizer(repo_path).full_sync(clean_branches=False)

def full_sync(repo_path: str = None, force_clean: bool = False) -> List[SyncResult]:
    return GitSynchronizer(repo_path).full_sync(clean_branches=True, force_clean=force_clean)
