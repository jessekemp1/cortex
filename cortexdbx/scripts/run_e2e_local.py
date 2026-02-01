#!/usr/bin/env python3
"""
Run CortexDBx unit and e2e tests locally and print summary.

Usage: from repo root: python cortexdbx/scripts/run_e2e_local.py
       or: cd cortex && python cortexdbx/scripts/run_e2e_local.py
"""

import sys
import subprocess
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))
    os.chdir(repo_root)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "cortexdbx/tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode == 0:
        print("All tests passed.")
    else:
        print(f"Some tests failed (exit {result.returncode}).")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
