#!/usr/bin/env python3
"""
Claude Code Context Injection Hook

This hook is called by Claude Code to inject strategic context at session start.
Target: 200-400 char context string with actionable intelligence.
Constraint: Must complete in under 500ms.

Usage:
    python inject_context.py [task_description]
"""

import logging
import sys
import time
from pathlib import Path

# Add cortex to path
CORTEX_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(CORTEX_DIR))

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)


def inject_via_hook_manager(cwd: Path, task: str) -> tuple[str, float]:
    """Inject context using the HookManager system.

    Args:
        cwd: Current working directory
        task: Task description

    Returns:
        tuple: (context_string, elapsed_time_ms)

    Raises:
        Exception: If hook manager fails
    """
    from hooks import ContextInjectorHook, HookManager

    # Create manager and register context injector hook
    manager = HookManager()
    dev_root = CORTEX_DIR.parent
    hook = ContextInjectorHook(root_dir=dev_root)
    manager.register_hook(hook)

    # Execute context injection
    start = time.time()
    output, results = manager.inject_context(cwd=str(cwd), task=task)
    elapsed = (time.time() - start) * 1000

    # Check if hook succeeded
    if results and results[0].success:
        return output, elapsed
    else:
        error = results[0].error if results else "Unknown error"
        raise RuntimeError(f"Hook execution failed: {error}")


def inject_via_direct_injector(cwd: Path, task: str) -> tuple[str, float]:
    """Fallback: Inject context using ContextInjector directly.

    Args:
        cwd: Current working directory
        task: Task description

    Returns:
        tuple: (context_string, elapsed_time_ms)
    """
    from intelligence.context_injector import ContextInjector

    dev_root = CORTEX_DIR.parent
    injector = ContextInjector(dev_root)

    start = time.time()
    context = injector.inject(cwd, task)
    elapsed = (time.time() - start) * 1000

    return context, elapsed


def main():
    """Entry point for Claude Code hook."""
    overall_start = time.time()

    try:
        cwd = Path.cwd()
        task = sys.argv[1] if len(sys.argv) > 1 else ""

        # Try HookManager first (new system)
        try:
            context, elapsed = inject_via_hook_manager(cwd, task)
            logger.debug(f"Context injection via HookManager: {elapsed:.1f}ms")
        except Exception as e:
            # Fallback to direct injection
            logger.warning(f"HookManager failed ({e}), falling back to direct injection")
            context, elapsed = inject_via_direct_injector(cwd, task)
            logger.debug(f"Context injection via fallback: {elapsed:.1f}ms")

        # Check overall timing
        total_elapsed = (time.time() - overall_start) * 1000
        if total_elapsed > 500:
            logger.warning(f"Context injection took {total_elapsed:.1f}ms (over 500ms budget)")

        # Output context
        print("<cortex_context>")
        print(context)
        print("</cortex_context>")

    except Exception as e:
        # Graceful degradation - output minimal context
        logger.error(f"Context injection failed: {e}", exc_info=True)
        print(f"<cortex_context>Project: {Path.cwd().name}</cortex_context>")


if __name__ == "__main__":
    main()
