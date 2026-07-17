"""Cortex .env loader — the day-1 fix so a key saved by install.sh is read.

Nothing in Cortex used to load a .env file; entrypoints read raw ``os.environ``
only, so a key written to ``~/.cortex/.env`` (or the repo ``.env``) by the
installer was invisible to ``cortex`` / ``cortex-mcp`` unless the user also
exported it in their shell. This module closes that gap.

Contract (the two properties tests assert):
  1. A value present in a .env file becomes visible to the process WITHOUT a
     shell export.
  2. A REAL environment variable ALWAYS wins over a .env-file value — we never
     clobber something the user (or a launchd plist) set explicitly.

Search order (later files fill only keys still unset by earlier ones — the
state-dir .env is the user's canonical secret store and takes precedence over
a repo-local .env):
  1. ``$CORTEX_STATE_DIR/.env`` (or ``~/.cortex/.env``)  — canonical
  2. repo-local ``<cortex_root>/.env``                   — dev convenience
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Import guard: dotenv is a hard dependency, but the loader must never be the
# thing that crashes an entrypoint. If it is somehow missing we fall back to a
# tiny stdlib parser rather than raising.
try:
    from dotenv import dotenv_values  # type: ignore

    _HAVE_DOTENV = True
except Exception:  # pragma: no cover - dotenv is a declared dependency
    _HAVE_DOTENV = False


def _state_dir() -> Path:
    """Resolve the Cortex state dir WITHOUT importing state_paths.

    state_paths.get_cortex_dir() creates the directory as a side effect; the
    env loader must stay side-effect-free (it runs at import/startup, before
    anything should be written), so it mirrors the resolution logic read-only.
    """
    base = os.environ.get("CORTEX_STATE_DIR") or os.environ.get("CORTEX_HOME")
    return Path(base).expanduser() if base else Path.home() / ".cortex"


def _repo_root() -> Path:
    """The cortex repo root (this file lives at its top level)."""
    return Path(__file__).resolve().parent


def env_file_paths() -> List[Path]:
    """The .env files consulted, in precedence order (highest first)."""
    return [_state_dir() / ".env", _repo_root() / ".env"]


def _parse_env_file(path: Path) -> dict:
    """Parse a .env file into a dict. Uses python-dotenv when available,
    else a minimal KEY=VALUE parser (no interpolation, quotes stripped)."""
    if not path.is_file():
        return {}
    if _HAVE_DOTENV:
        try:
            return {k: v for k, v in dotenv_values(str(path)).items() if v is not None}
        except Exception:
            return {}
    out: dict = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                out[key] = val
    except Exception:
        return {}
    return out


def load_env(*, override: bool = False) -> List[str]:
    """Load Cortex .env files into ``os.environ``.

    Real environment variables win: a key already present in ``os.environ`` is
    left untouched (unless ``override=True``, which is not used by entrypoints).
    Returns the list of keys newly set from files (for diagnostics/tests).
    """
    applied: List[str] = []
    for path in env_file_paths():
        values = _parse_env_file(path)
        for key, val in values.items():
            if val is None:
                continue
            if not override and key in os.environ:
                continue  # real env var wins
            os.environ[key] = val
            applied.append(key)
    return applied


def env_dotenv_parity() -> dict:
    """Report where a key lives in .env but disagrees with the live process env.

    Used by ``cortex doctor``. A "disagreement" is either:
      - a key set in a .env file but NOT visible in os.environ (loader not run,
        or the value is empty), or
      - a key whose .env value differs from the live os.environ value (a real
        env var is shadowing the file — informational, not an error).

    Returns {"ok": bool, "missing": [...], "shadowed": [...], "files": [...]}.
    ``missing`` is the actionable failure; ``shadowed`` is informational.
    """
    file_values: dict = {}
    consulted: List[str] = []
    for path in env_file_paths():
        if path.is_file():
            consulted.append(str(path))
            for k, v in _parse_env_file(path).items():
                # first file wins (matches load precedence)
                file_values.setdefault(k, v)

    missing: List[str] = []
    shadowed: List[str] = []
    for key, fval in file_values.items():
        if not fval:
            continue  # empty/placeholder — nothing to reconcile
        live = os.environ.get(key)
        if live is None:
            missing.append(key)
        elif live != fval:
            shadowed.append(key)

    return {
        "ok": not missing,
        "missing": sorted(missing),
        "shadowed": sorted(shadowed),
        "files": consulted,
    }
