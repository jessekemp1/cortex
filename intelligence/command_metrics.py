#!/usr/bin/env python3
"""
Command Metrics - Decorator for CLI command performance tracking.

Wraps CLI command handlers to capture:
- Execution duration (ms)
- Success/failure status
- Error messages
- Token usage (when available)

Data feeds into the consolidated outcome store for learning.
"""

import functools
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

def _get_store():
    """Get the consolidated store (always use the current singleton)."""
    try:
        from intelligence.storage.consolidated_store import get_consolidated_store

        return get_consolidated_store()
    except Exception:
        return None


def track_command(command_name: Optional[str] = None):
    """
    Decorator that tracks command execution metrics.

    Usage:
        @track_command("next")
        def cmd_next(args):
            ...

        # Or auto-detect from function name:
        @track_command()
        def cmd_status(args):
            ...
    """

    def decorator(func: Callable) -> Callable:
        name = command_name or func.__name__.replace("cmd_", "")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            success = True
            error_msg = None

            try:
                result = func(*args, **kwargs)
                return result
            except SystemExit as e:
                # SystemExit with code 0 is success
                if e.code and e.code != 0:
                    success = False
                    error_msg = f"exit code {e.code}"
                raise
            except Exception as e:
                success = False
                error_msg = str(e)[:200]
                raise
            finally:
                duration_ms = (time.monotonic() - start) * 1000
                try:
                    store = _get_store()
                    if store:
                        store.log_command_metric(
                            command=name,
                            duration_ms=round(duration_ms, 1),
                            success=success,
                            error_message=error_msg,
                        )
                except Exception:
                    pass  # Never let metrics tracking break the command

        return wrapper

    return decorator
