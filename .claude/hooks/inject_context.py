#!/usr/bin/env python3
"""
Claude Code Context Injection Hook

This hook is called by Claude Code to inject strategic context at session start.
Target: 200-400 char context string with actionable intelligence.
Constraint: Must complete in under 500ms.

Usage:
    python inject_context.py [task_description]
"""

import sys
import time
from pathlib import Path

# Add cortex to path
CORTEX_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(CORTEX_DIR))


def main():
    """Entry point for Claude Code hook."""
    start = time.time()

    try:
        cwd = Path.cwd()
        task = sys.argv[1] if len(sys.argv) > 1 else ""

        from intelligence.context_injector import ContextInjector

        # Root is one level up from cortex (Dev directory)
        dev_root = CORTEX_DIR.parent
        injector = ContextInjector(dev_root)

        context = injector.inject(cwd, task)

        # Ensure under 500ms
        elapsed = (time.time() - start) * 1000

        # Log timing if over budget (for debugging)
        if elapsed > 500:
            import logging

            logging.warning(f"Context injection took {elapsed:.1f}ms (over 500ms budget)")

        # Output context
        print(f"<cortex_context>")
        print(context)
        print(f"</cortex_context>")

    except Exception as e:
        # Graceful degradation - output minimal context
        import logging

        logging.error(f"Context injection failed: {e}")
        print(f"<cortex_context>Project: {Path.cwd().name}</cortex_context>")


if __name__ == "__main__":
    main()
