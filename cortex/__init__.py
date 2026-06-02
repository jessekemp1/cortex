"""Cortex namespace shim — maps `cortex.X` imports to top-level modules.

The repo uses a flat layout: `state_paths.py`, `feedback.py`, `bridge.py`, the
`intelligence/` package, etc., live at the repo root. ~82 files import them
through the `cortex.<name>` namespace (e.g. `from cortex.state_paths import
get_cortex_dir`).

Implementation: extend the `cortex` package's `__path__` with the repo root.
Python's import machinery (`_find_and_load`) then searches BOTH directories
when resolving `cortex.X`:

    cortex/__init__.py    # this file — its parent dir is added to __path__
    cortex/<X.py>         # not present; nothing lives directly under cortex/
    <repo_root>/<X.py>    # the real top-level modules get picked up here

This is how Python's own `namespace packages` work, except we mix the
two-directory search into a single regular package. The result is that:
  - `from cortex.state_paths import get_cortex_dir` resolves to the real
    `state_paths.py` at the repo root.
  - `from cortex.intelligence.foo import bar` resolves through cortex.intelligence
    (the directory at repo root) → foo submodule, exactly as it would for a
    top-level `import intelligence.foo`.

Why not a 82-file refactor:
  - Each import site would need editing to drop the `cortex.` prefix.
  - This shim is a single small file, well-scoped, and lets callers migrate
    individually if they ever want to drop the prefix.

Why this pattern over PEP 562 __getattr__:
  - `__getattr__` only fires for ATTRIBUTE access, not for the
    `_find_and_load` step that `from cortex.X import Y` uses. So __getattr__
    can't intercept submodule imports. Extending `__path__` does.

Why this pattern over an eager pre-import:
  - Eager pre-imports trigger circular dependencies when an imported module's
    own __init__ tries to `from cortex.X import …` while the cortex package
    is still initializing.
"""

from __future__ import annotations

import os as _os

# Add the repo root (one level up from this file) to the package search path.
# Python's import system now treats `cortex` as a package whose submodules
# can live either under cortex/ OR at the repo root.
__path__.append(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
