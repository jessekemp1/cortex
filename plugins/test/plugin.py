#!/usr/bin/env python3
"""Test Plugin - Smart test execution"""

import subprocess
from typing import List
from cortex.plugins.base import BasePlugin


class TestPlugin(BasePlugin):
    """Smart test execution plugin."""

    def execute(self, args: List[str], **kwargs) -> int:
        """Execute test plugin."""
        if "--help" in args or "-h" in args:
            print(self.help())
            return 0

        print("🧪 Running Tests")
        print("═" * 40)

        # Simple implementation: run pytest
        try:
            result = subprocess.run(
                ["python", "-m", "pytest"] + args,
                timeout=300
            )
            return result.returncode
        except Exception as e:
            print(f"❌ Error: {e}")
            return 1
