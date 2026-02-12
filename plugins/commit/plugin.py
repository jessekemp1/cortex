#!/usr/bin/env python3
"""Commit Plugin - Intelligent git commits"""

import subprocess
from typing import List

from cortex.plugins.base import BasePlugin


class CommitPlugin(BasePlugin):
    """Intelligent git commit plugin."""

    def execute(self, args: List[str], **kwargs) -> int:
        """Execute commit plugin."""
        if "--help" in args or "-h" in args:
            print(self.help())
            return 0

        print("🧠 Analyzing changes...")

        # Check for staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
        )

        if not result.stdout.strip():
            print("❌ No staged changes to commit")
            print("   Use 'git add' to stage files first")
            return 1

        files = result.stdout.strip().split("\n")
        print(f"\nFiles to commit: {len(files)}")
        for f in files[:5]:
            print(f"  - {f}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")

        # Simple commit
        if "-m" in args:
            msg_idx = args.index("-m")
            if msg_idx + 1 < len(args):
                message = args[msg_idx + 1]
                result = subprocess.run(["git", "commit", "-m", message])
                return result.returncode

        print("\n💡 Tip: Use /commit -m 'your message'")
        return 1
