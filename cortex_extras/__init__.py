"""
cortex_extras — staging area for subsystems on the path to sibling repos.

Each subdirectory is intended to become its own pip-installable package.
Until then this __init__.py injects this directory into sys.path so that
intra-subsystem imports (e.g. `from synthetic.generator import ...` inside
synthetic/ itself) keep working without rewriting every internal site.

When a subsystem moves to its sibling repo, remove its entry from this
directory and the path injection becomes irrelevant for it.

See README.md for the migration roadmap.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_this_dir = _Path(__file__).resolve().parent
if str(_this_dir) not in _sys.path:
    _sys.path.insert(0, str(_this_dir))
