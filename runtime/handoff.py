"""
Agent-facing handoff file (`handoff.yaml`) — canonical structured checkpoint.

Per CLAUDE.md §3, agents own `.workflow/current/handoff.yaml` and the Cortex
daemon owns `.workflow/current/progress.md`. This module provides the single
sanctioned writer/reader so agents stop racing the daemon on `progress.md`.

Schema (exactly six agent-authored fields):

    done:            list[str]         atomic units completed this session
    verified:        list[str]         gate_commands that passed
    open_questions:  list[str]         ambiguities blocking progress
    next_action:     str               one-sentence imperative
    gate_command:    str               shell command next session runs first
    confidence:      float in [0,1]    see CLAUDE.md §7

Two metadata fields are written automatically and MUST NOT be set by the
caller:

    _written_at:     ISO-8601 UTC timestamp
    _branch:         current git branch at write time

See docs/PRD-handoff-split.md for the full spec.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

log = logging.getLogger(__name__)

HANDOFF_FILENAME = "handoff.yaml"
_SCHEMA_FIELDS = {
    "done",
    "verified",
    "open_questions",
    "next_action",
    "gate_command",
    "confidence",
}
_META_FIELDS = {"_written_at", "_branch"}


@dataclass
class HandoffFields:
    """Six-field agent handoff schema. See module docstring for semantics."""

    done: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    next_action: str = ""
    gate_command: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        # Clamp, don't reject. CLAUDE.md §7 asks for a confidence scalar;
        # forcing agents through a validation error at write time defeats
        # the purpose of a silent, cheap checkpoint.
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0


def _resolve_workflow_dir(workflow_dir: Optional[Path] = None) -> Path:
    """Path resolution: explicit arg → env override → cwd-relative default.

    Never the monorepo root (CLAUDE.md §4). The caller's responsibility is
    to invoke from inside a project directory.
    """
    if workflow_dir is not None:
        return Path(workflow_dir)
    env_override = os.environ.get("CORTEX_WORKFLOW_DIR")
    if env_override:
        return Path(env_override)
    return Path.cwd() / ".workflow" / "current"


def _current_branch(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(cwd),
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def write_handoff(
    fields: HandoffFields,
    workflow_dir: Optional[Path] = None,
) -> Path:
    """Atomically write agent handoff YAML.

    Uses tempfile + os.replace so a crash mid-write never leaves a partial
    file the daemon might read. Adds `_written_at` and `_branch` metadata.

    Returns the resolved path, or raises OSError if the directory can't
    be created or the write fails outright. Agents MUST NOT silently
    catch and drop these errors (CLAUDE.md §3 anti-pattern).
    """
    target_dir = _resolve_workflow_dir(workflow_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / HANDOFF_FILENAME

    payload: dict[str, Any] = asdict(fields)
    payload["_written_at"] = datetime.now(timezone.utc).isoformat()
    payload["_branch"] = _current_branch(target_dir)

    # Atomic write: tempfile in same directory, then os.replace.
    fd, tmp_path = tempfile.mkstemp(
        prefix=".handoff_", suffix=".yaml.tmp", dir=str(target_dir)
    )
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(payload, f, sort_keys=True, default_flow_style=False)
        os.replace(tmp_path, target_path)
    except Exception:
        # Clean up the temp if replace failed.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    log.info("handoff.yaml written to %s", target_path)
    return target_path


def read_handoff(
    workflow_dir: Optional[Path] = None,
) -> Optional[HandoffFields]:
    """Read and validate handoff YAML. Returns None on any failure.

    Must never raise upward — the daemon calls this during snapshot
    assembly and cannot crash because an agent wrote malformed YAML.
    """
    target_path = _resolve_workflow_dir(workflow_dir) / HANDOFF_FILENAME
    if not target_path.exists():
        return None

    try:
        with open(target_path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        log.warning("handoff.yaml unparseable at %s: %s", target_path, exc)
        return None
    except OSError as exc:
        log.warning("handoff.yaml unreadable at %s: %s", target_path, exc)
        return None

    if not isinstance(raw, dict):
        log.warning("handoff.yaml root is not a mapping at %s", target_path)
        return None

    # Forward compat: log unknown keys but don't crash.
    unknown = set(raw) - _SCHEMA_FIELDS - _META_FIELDS
    if unknown:
        log.info("handoff.yaml has unknown keys (preserved, ignored): %s", sorted(unknown))

    try:
        return HandoffFields(
            done=_coerce_list(raw.get("done", [])),
            verified=_coerce_list(raw.get("verified", [])),
            open_questions=_coerce_list(raw.get("open_questions", [])),
            next_action=_coerce_str(raw.get("next_action", "")),
            gate_command=_coerce_str(raw.get("gate_command", "")),
            confidence=_coerce_float(raw.get("confidence", 0.0)),
        )
    except (TypeError, ValueError) as exc:
        log.warning("handoff.yaml schema violation at %s: %s", target_path, exc)
        return None


def _coerce_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"expected list, got {type(value).__name__}")
    return [str(item) for item in value]


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    raise TypeError(f"expected str-like, got {type(value).__name__}")


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        # bool is a subclass of int; reject to avoid silent confidence=1.0
        raise TypeError("confidence must be numeric, not bool")
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"expected float, got {type(value).__name__}")


def render_handoff_markdown(fields: HandoffFields) -> str:
    """Render a handoff block for embedding in the daemon's progress.md.

    Kept here (next to the schema) so the renderer changes when the schema
    changes. Consumed by cortex/session_snapshot.py.
    """
    def _bullets(items: list[str]) -> str:
        return "\n".join(f"  - {item}" for item in items) if items else "  (none)"

    return (
        "## Agent Handoff\n"
        f"**Confidence:** {fields.confidence:.2f}\n\n"
        "**Done this session:**\n"
        f"{_bullets(fields.done)}\n\n"
        "**Verified gates:**\n"
        f"{_bullets(fields.verified)}\n\n"
        "**Open questions:**\n"
        f"{_bullets(fields.open_questions)}\n\n"
        f"**Next action:** {fields.next_action or '(none)'}\n\n"
        f"**Gate to run first on resume:** `{fields.gate_command or '(none)'}`"
    )


__all__ = [
    "HandoffFields",
    "HANDOFF_FILENAME",
    "read_handoff",
    "render_handoff_markdown",
    "write_handoff",
]
