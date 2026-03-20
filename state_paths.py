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


def get_domain() -> str:
    """
    Detect the current portfolio domain.

    Resolution order:
    1. CORTEX_DOMAIN env var (set by cmode launcher or session hook)
    2. CWD heuristic: ~/dbx-dev → "databricks", else "aidev"
    3. Fallback: "aidev"
    """
    explicit = os.environ.get("CORTEX_DOMAIN")
    if explicit:
        return explicit

    cwd = os.getcwd()
    if "dbx-dev" in cwd:
        return "databricks"

    return "aidev"
