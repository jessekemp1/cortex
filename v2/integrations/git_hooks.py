"""Git hook integration for automated outcome detection."""

import os
import stat
from pathlib import Path
from typing import Optional

POST_COMMIT_HOOK = """#!/bin/bash
# Cortex V2 Automated Outcome Detection
# Installed by: cortex2 hooks install

# Get commit info
COMMIT_HASH=$(git rev-parse HEAD)
COMMIT_MSG=$(git log -1 --pretty=%B | head -1)
BRANCH=$(git branch --show-current)
FILES_CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD | wc -l | tr -d ' ')
REPO_PATH=$(git rev-parse --show-toplevel)

# Escape message for Python
COMMIT_MSG_ESCAPED=$(echo "$COMMIT_MSG" | sed "s/'/\\\\'/g")

# Record outcome (async to not slow down commits)
python3 << EOF &
import sys
sys.path.insert(0, '{cortex_path}')
try:
    from cortex.v2.learning.outcomes import OutcomeDetector
    from pathlib import Path

    detector = OutcomeDetector()
    detector.record_git_outcome(
        commit_hash='$COMMIT_HASH',
        message='$COMMIT_MSG_ESCAPED',
        branch='$BRANCH',
        files_changed=$FILES_CHANGED,
        repo_path=Path('$REPO_PATH')
    )
except Exception:
    pass  # Silently fail to not disrupt git workflow
EOF
"""


class GitHookInstaller:
    """Installs git hooks for outcome detection."""

    def __init__(self, cortex_path: Optional[Path] = None):
        """Initialize installer.

        Args:
            cortex_path: Path to cortex installation. Auto-detected if not provided.
        """
        if cortex_path is None:
            # Find cortex path from this file's location
            cortex_path = Path(__file__).parent.parent.parent

        self.cortex_path = cortex_path

    def install(self, repo_path: Path, force: bool = False) -> bool:
        """Install git hooks in a repository.

        Args:
            repo_path: Path to git repository
            force: Overwrite existing hooks

        Returns:
            True if installed successfully
        """
        hooks_dir = repo_path / ".git" / "hooks"

        if not hooks_dir.exists():
            return False

        post_commit_path = hooks_dir / "post-commit"

        # Check for existing hook
        if post_commit_path.exists() and not force:
            # Check if it's already our hook
            content = post_commit_path.read_text()
            if "Cortex V2" in content:
                return True  # Already installed
            else:
                # Existing non-cortex hook
                return False

        # Write hook
        hook_content = POST_COMMIT_HOOK.format(cortex_path=str(self.cortex_path))

        post_commit_path.write_text(hook_content)

        # Make executable
        st = os.stat(post_commit_path)
        os.chmod(post_commit_path, st.st_mode | stat.S_IEXEC)

        return True

    def uninstall(self, repo_path: Path) -> bool:
        """Remove git hooks from a repository.

        Args:
            repo_path: Path to git repository

        Returns:
            True if uninstalled successfully
        """
        post_commit_path = repo_path / ".git" / "hooks" / "post-commit"

        if not post_commit_path.exists():
            return True

        content = post_commit_path.read_text()
        if "Cortex V2" not in content:
            return False  # Not our hook

        post_commit_path.unlink()
        return True

    def is_installed(self, repo_path: Path) -> bool:
        """Check if hooks are installed in a repository.

        Args:
            repo_path: Path to git repository

        Returns:
            True if installed
        """
        post_commit_path = repo_path / ".git" / "hooks" / "post-commit"

        if not post_commit_path.exists():
            return False

        content = post_commit_path.read_text()
        return "Cortex V2" in content

    def install_all(self, root_dir: Path, force: bool = False) -> dict:
        """Install hooks in all git repositories under root_dir.

        Args:
            root_dir: Root directory to scan
            force: Overwrite existing hooks

        Returns:
            Dict with installed/skipped/failed counts
        """
        results = {"installed": 0, "skipped": 0, "failed": 0, "repos": []}

        for git_dir in root_dir.rglob(".git"):
            if not git_dir.is_dir():
                continue

            repo_path = git_dir.parent

            # Skip nested git repos (submodules)
            if ".git" in str(repo_path.relative_to(root_dir)).split("/")[:-1]:
                continue

            try:
                if self.is_installed(repo_path):
                    results["skipped"] += 1
                elif self.install(repo_path, force=force):
                    results["installed"] += 1
                    results["repos"].append(str(repo_path))
                else:
                    results["failed"] += 1
            except Exception:
                results["failed"] += 1

        return results
