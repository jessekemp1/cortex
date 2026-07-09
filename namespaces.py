"""Namespaced private state helpers for Cortex.

These helpers keep application-specific/private state outside the repository
working tree and under the Cortex state directory, e.g.:

    ~/.cortex/namespaces/<namespace>/

The first reference workload is KempOS, but this module is intentionally generic.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


VALID_NAMESPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class InvalidNamespaceError(ValueError):
    """Raised when a namespace is invalid or unsafe."""


def validate_namespace(namespace: str) -> str:
    """Validate and return a safe namespace name."""
    if not isinstance(namespace, str):
        raise InvalidNamespaceError("Namespace must be a string")

    candidate = namespace.strip()
    if not candidate:
        raise InvalidNamespaceError("Namespace cannot be empty")

    if not VALID_NAMESPACE_RE.fullmatch(candidate):
        raise InvalidNamespaceError(
            "Namespace must match ^[a-z0-9][a-z0-9_-]{0,63}$"
        )

    return candidate


def cortex_config_dir(config_dir: Path | str | None = None) -> Path:
    """Return the Cortex state/config directory.

    Tests can inject a temp config_dir. Production defaults to ~/.cortex or
    CORTEX_CONFIG_DIR when explicitly set.
    """
    if config_dir is not None:
        return Path(config_dir).expanduser().resolve()
    return Path(os.environ.get("CORTEX_CONFIG_DIR", Path.home() / ".cortex")).expanduser().resolve()


def namespace_dir(namespace: str, config_dir: Path | str | None = None) -> Path:
    """Resolve the directory for a validated namespace."""
    safe_namespace = validate_namespace(namespace)
    root = cortex_config_dir(config_dir)
    namespaces_root = (root / "namespaces").resolve()
    path = (namespaces_root / safe_namespace).resolve()

    if namespaces_root not in path.parents:
        raise InvalidNamespaceError("Resolved namespace path escapes Cortex config dir")

    return path


def ensure_namespace(namespace: str, config_dir: Path | str | None = None) -> Path:
    """Create and return the namespace directory with private permissions."""
    path = namespace_dir(namespace, config_dir=config_dir)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        # chmod may fail on some platforms/filesystems. Directory creation still
        # succeeds and health checks can surface permission concerns later.
        pass
    return path
