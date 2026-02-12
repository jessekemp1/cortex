#!/usr/bin/env python3
"""
Wrapper script to run converx CLI from any location
"""

import sys
from pathlib import Path

# Add the Grok MVP directory to path
grok_mvp_dir = Path(__file__).parent
sys.path.insert(0, str(grok_mvp_dir))

# Change to the directory so relative imports work
import os

original_cwd = os.getcwd()
os.chdir(str(grok_mvp_dir))

try:
    # Now import and run
    from cli import main

    if __name__ == "__main__":
        main()
finally:
    os.chdir(original_cwd)
