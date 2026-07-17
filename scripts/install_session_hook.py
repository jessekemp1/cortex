#!/usr/bin/env python3
"""Wire the Cortex session briefing into a workspace's Claude Code settings.

Merges a SessionStart hook entry into <workspace>/.claude/settings.json,
preserving everything already there (never clobbers other hooks). Idempotent:
running twice leaves one entry. The hook command carries its own existence
guard, so a checkout that predates hooks/session_briefing.sh degrades to a
silent no-op instead of a "No such file or directory" hook error.

Usage:
    python3 scripts/install_session_hook.py <workspace_dir> [--remove]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKER = "session_briefing.sh"


def _hook_command(repo_root: Path) -> str:
    # Existence-guarded: silent no-op if the script is missing (e.g. the
    # checkout is on a branch that predates it). Always exits 0.
    hook_script = repo_root / "hooks" / "session_briefing.sh"
    return f'bash -c \'[ -f "{hook_script}" ] && bash "{hook_script}" || true\''


def install(workspace: Path, remove: bool = False, repo_root: Path = REPO_ROOT) -> int:
    settings_path = workspace / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"refusing to touch malformed {settings_path}: {e}", file=sys.stderr)
            return 1

    hooks = settings.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])

    # Drop any existing briefing entries (idempotency / clean remove).
    def _is_briefing(group: dict) -> bool:
        return any(MARKER in h.get("command", "") for h in group.get("hooks", []))

    session_start[:] = [g for g in session_start if not _is_briefing(g)]

    if not remove:
        session_start.append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _hook_command(repo_root),
                        "timeout": 5,
                    }
                ]
            }
        )

    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    action = "removed from" if remove else "wired into"
    print(f"Cortex session briefing {action} {settings_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path, help="workspace dir containing .claude/")
    ap.add_argument("--remove", action="store_true", help="unwire the briefing hook")
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="cortex checkout whose hooks/session_briefing.sh the hook should run",
    )
    args = ap.parse_args()
    return install(
        args.workspace.expanduser().resolve(),
        remove=args.remove,
        repo_root=args.repo_root.expanduser().resolve(),
    )


if __name__ == "__main__":
    sys.exit(main())
