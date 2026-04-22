"""
Rollover policy text — canonical source for agent prompting.

Loaded from the repo-root CLAUDE.md so interactive and dispatched agents
share the same policy. Keep CLAUDE.md as the single writable source; this
module is a read-only accessor.
"""

from __future__ import annotations

from pathlib import Path

_CLAUDE_MD = Path(__file__).resolve().parent.parent / "CLAUDE.md"


_FALLBACK = """\
Rollover policy: do NOT recommend /compact, /clear, or "fresh session" to
the user. Do NOT estimate context-% in user-facing output. The harness owns
rollover. If context is genuinely tight, finish the current atomic unit,
append up to six YAML fields to .workflow/current/handoff.yaml, and stop.
Delegate large work units via Task() rather than suggesting a new session.
Never silently skip a file write claiming "to preserve context."
"""


def _read_claude_md() -> str:
    try:
        return _CLAUDE_MD.read_text().strip()
    except OSError:
        return _FALLBACK.strip()


# Full policy — injected as system-prompt prefix for dispatched agents.
ROLLOVER_POLICY_TEXT: str = _read_claude_md()


# Compact one-paragraph version — for prompts that must stay short
# (classifier, haiku-tier tasks, status-line contexts).
ROLLOVER_POLICY_SHORT: str = (
    "Rollover policy: never recommend /compact, /clear, or 'fresh session'. "
    "Never estimate context-% in user output. Finish atomic units; write "
    "handoff.yaml (not progress.md); delegate via Task() instead of "
    "asking the user to open a new session."
)


__all__ = ["ROLLOVER_POLICY_TEXT", "ROLLOVER_POLICY_SHORT"]
