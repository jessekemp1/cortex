"""Setup / lifecycle helpers shared by the CLI, doctor, install.sh and uninstall.sh.

Everything here degrades gracefully when the external tool (``claude`` CLI,
``launchctl``) is absent — it returns a structured result instead of raising,
so callers (doctor checks, the ``--yes`` installer, the manual-fallback path)
can act on it without try/except sprawl.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

MCP_NAME = "cortex"


# ── claude CLI discovery ───────────────────────────────────────────────────────


def claude_bin() -> str | None:
    """Path to the Claude Code CLI, or None if not installed.

    ``CORTEX_CLAUDE_BIN`` overrides discovery — tests point it at a stub (or an
    empty string / bogus path) to exercise the not-installed fallback without
    touching the real ``~/.claude.json``.
    """
    override = os.environ.get("CORTEX_CLAUDE_BIN")
    if override is not None:
        return override or None
    return shutil.which("claude")


def mcp_server_command() -> str:
    """The command Claude Code should run to launch the in-process MCP server.

    Prefers the ``cortex-mcp`` console script if it is on PATH (installed via
    the venv), else falls back to ``<python> -m mcp_server`` from the repo.
    """
    override = os.environ.get("CORTEX_MCP_COMMAND")
    if override:
        return override
    console = shutil.which("cortex-mcp")
    if console:
        return console
    import sys

    return f"{sys.executable} -m mcp_server"


def mcp_registration_entry(scope: str = "user") -> Dict[str, str]:
    """The exact registration Claude Code would store — used to show the user
    and to build the manual copy-paste block when the CLI is unavailable."""
    cmd = mcp_server_command()
    parts = cmd.split()
    program, args = parts[0], parts[1:]
    manual = f"claude mcp add {MCP_NAME} -s {scope} -- {cmd}"
    return {
        "name": MCP_NAME,
        "scope": scope,
        "command": program,
        "args": " ".join(args),
        "full_command": cmd,
        "manual": manual,
    }


# ── MCP registration ──────────────────────────────────────────────────────────


def mcp_is_registered() -> Dict[str, Any]:
    """Is the cortex MCP server registered in Claude Code?

    Returns {"registered": bool, "available": bool, "detail": str}. ``available``
    is False when the ``claude`` CLI itself is missing (an UNKNOWN, not a FAIL).
    """
    cbin = claude_bin()
    if not cbin:
        return {"registered": False, "available": False, "detail": "claude CLI not installed"}
    try:
        proc = subprocess.run(
            [cbin, "mcp", "get", MCP_NAME],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return {"registered": False, "available": False, "detail": f"claude mcp get failed: {e}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    # `claude mcp get` exits 0 whether or not the server exists; the absence
    # marker is the reliable signal.
    if "No MCP server named" in out or f'"{MCP_NAME}"' in out and "No MCP server" in out:
        return {"registered": False, "available": True, "detail": "not registered"}
    if MCP_NAME in out and ("Scope" in out or "Status" in out or "Command" in out):
        return {"registered": True, "available": True, "detail": "registered"}
    # Ambiguous output — report unknown rather than a false negative.
    return {"registered": False, "available": True, "detail": "not registered"}


def register_mcp(scope: str = "user") -> Dict[str, Any]:
    """Register the cortex MCP server with Claude Code (idempotent).

    Returns {"ok": bool, "action": str, "detail": str, "manual": str}. When the
    ``claude`` CLI is absent, ``ok`` is False and ``manual`` carries the exact
    copy-paste block the caller should print — never raises.
    """
    entry = mcp_registration_entry(scope)
    cbin = claude_bin()
    if not cbin:
        return {
            "ok": False,
            "action": "manual",
            "detail": "claude CLI not installed — register manually",
            "manual": entry["manual"],
            "entry": entry,
        }

    status = mcp_is_registered()
    if status.get("registered"):
        return {
            "ok": True,
            "action": "already",
            "detail": "already registered",
            "manual": entry["manual"],
            "entry": entry,
        }

    cmd = [cbin, "mcp", "add", MCP_NAME, "-s", scope, "--", *entry["full_command"].split()]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return {
            "ok": False,
            "action": "error",
            "detail": f"claude mcp add failed: {e}",
            "manual": entry["manual"],
            "entry": entry,
        }
    if proc.returncode == 0:
        return {
            "ok": True,
            "action": "added",
            "detail": f"registered ({scope} scope): {entry['full_command']}",
            "manual": entry["manual"],
            "entry": entry,
        }
    return {
        "ok": False,
        "action": "error",
        "detail": (proc.stderr or proc.stdout or "unknown error").strip(),
        "manual": entry["manual"],
        "entry": entry,
    }


def unregister_mcp(scope: str | None = None) -> Dict[str, Any]:
    """Remove the cortex MCP entry from Claude Code. Degrades gracefully."""
    cbin = claude_bin()
    if not cbin:
        return {"ok": False, "detail": "claude CLI not installed (nothing to remove)"}
    cmd = [cbin, "mcp", "remove", MCP_NAME]
    if scope:
        cmd += ["-s", scope]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "detail": f"claude mcp remove failed: {e}"}
    if proc.returncode == 0:
        return {"ok": True, "detail": "removed"}
    return {"ok": False, "detail": (proc.stderr or proc.stdout or "").strip() or "not present"}


# ── in-process MCP import ──────────────────────────────────────────────────────


def mcp_import_ok() -> Dict[str, Any]:
    """Can the in-process MCP server be imported (the [server] extra present)?"""
    try:
        import importlib

        importlib.import_module("mcp.server.fastmcp")
        importlib.import_module("mcp_server")
        return {"ok": True, "detail": "importable"}
    except Exception as e:  # ImportError or transitive failure
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}


def server_extra_ok() -> Dict[str, Any]:
    """Are the [server] extra packages importable (fastapi + mcp)?"""
    missing: List[str] = []
    for pkg in ("fastapi", "mcp"):
        try:
            __import__(pkg)
        except Exception:
            missing.append(pkg)
    if missing:
        return {"ok": False, "detail": f"missing: {', '.join(missing)}"}
    return {"ok": True, "detail": "fastapi, mcp present"}


# ── hooks installed ────────────────────────────────────────────────────────────


def hooks_installed() -> Dict[str, Any]:
    """Is the session-briefing hook wired into a workspace .claude/settings.json?

    Best-effort: checks the CORTEX_ROOT_DIR workspace and the repo parent. This
    is informational for a new user — a missing hook is a soft finding.
    """
    from pathlib import Path as _P

    roots = []
    root_env = os.environ.get("CORTEX_ROOT_DIR")
    if root_env:
        roots.append(_P(root_env).expanduser())
    roots.append(_P(__file__).resolve().parent.parent)  # repo parent (workspace)
    seen = set()
    for root in roots:
        settings = root / ".claude" / "settings.json"
        if str(settings) in seen:
            continue
        seen.add(str(settings))
        if settings.is_file():
            try:
                if "cortex" in settings.read_text(encoding="utf-8").lower():
                    return {"ok": True, "detail": str(settings)}
            except Exception:
                continue
    return {"ok": False, "detail": "no cortex hook found in workspace .claude/settings.json"}


# ── launchd bridge ─────────────────────────────────────────────────────────────


def launchd_bridge_status() -> Dict[str, Any]:
    """launchd com.cortex.bridge keep-alive status.

    Returns {"status": "loaded"|"not_loaded"|"skip", "detail": str}. On non-macOS
    or when launchctl is unavailable, status is "skip" (not a failure).
    """
    import sys

    if sys.platform != "darwin":
        return {"status": "skip", "detail": "not macOS"}
    if not shutil.which("launchctl"):
        return {"status": "skip", "detail": "launchctl unavailable"}
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        return {"status": "skip", "detail": f"launchctl error: {e}"}
    if "com.cortex.bridge" in out:
        return {"status": "loaded", "detail": "loaded"}
    return {"status": "not_loaded", "detail": "not loaded — run scripts/install_launchagents.sh"}


# ── reset ──────────────────────────────────────────────────────────────────────


def reset_state(force: bool = False) -> Dict[str, Any]:
    """Wipe the Cortex state directory. Caller is responsible for confirmation.

    Returns {"ok": bool, "removed": str|None, "detail": str}. Never touches
    anything outside the resolved state dir.
    """
    from state_paths import get_cortex_dir

    state = get_cortex_dir()
    if not state.exists():
        return {"ok": True, "removed": None, "detail": f"{state} does not exist"}
    # Safety: refuse to wipe an obviously-wrong target (home dir, root).
    resolved = state.resolve()
    if resolved == Path.home().resolve() or resolved == Path("/"):
        return {"ok": False, "removed": None, "detail": f"refusing to wipe {resolved}"}
    try:
        shutil.rmtree(resolved)
        return {"ok": True, "removed": str(resolved), "detail": "state wiped"}
    except Exception as e:
        return {"ok": False, "removed": None, "detail": f"{type(e).__name__}: {e}"}
