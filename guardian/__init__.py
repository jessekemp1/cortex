"""Cortex Repo Guardian — advisory file claims, snapshots, and recovery.

Usage:
    from cortex.guardian import get_guardian

    guardian = get_guardian()
    result = guardian.claim("/path/to/file.py", agent_id="session_abc")
"""

from __future__ import annotations

from typing import Optional

_guardian_instance: Optional["GuardianProcess"] = None


def get_guardian() -> "GuardianProcess":
    """Get or create the singleton GuardianProcess."""
    global _guardian_instance
    if _guardian_instance is None:
        from cortex.guardian.process import GuardianProcess

        _guardian_instance = GuardianProcess()
    return _guardian_instance
