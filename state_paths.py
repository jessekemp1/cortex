"""Centralized helpers for Cortex state directories."""

import os
from pathlib import Path


def get_cortex_dir() -> Path:
    """
    Resolve the writable Cortex state directory.

    Prefers `CORTEX_STATE_DIR`, then `CORTEX_HOME`, otherwise defaults to
    `~/.cortex`. Directory is created if missing.
    """
    base = os.getenv("CORTEX_STATE_DIR") or os.getenv("CORTEX_HOME")
    path = Path(base).expanduser() if base else Path.home() / ".cortex"
    path.mkdir(parents=True, exist_ok=True)
    return path
