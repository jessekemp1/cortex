#!/usr/bin/env python3
"""
iTerm2 Orchestrator for Exponential Collaboration

Uses iTerm2's Python API to manage workstream-based terminal layouts.
Integrates with Cortex WorkstreamOrchestrator for context injection.

Features:
- Profile creation with Cortex shell hooks
- Window arrangement management (save/restore layouts)
- Badge-based workstream identification
- Status bar integration for trust levels + batch status
- Trigger setup for error detection and Cortex alerts
- Keyboard shortcut orchestration

Requirements:
- iTerm2 3.5+ with Python API enabled
- pip install iterm2

Usage (standalone):
    python cortex/automation/iterm_orchestrator.py setup    # Install profiles
    python cortex/automation/iterm_orchestrator.py layout    # Apply standard layout
    python cortex/automation/iterm_orchestrator.py switch <project> <phase>

Usage (from Cortex):
    cortex workspace setup
    cortex workspace switch vortex build
    cortex workspace layout research-lab
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── Profile Definitions ────────────────────────────────────

PROJECTS = {
    "vortex": {
        "name": "Vortex",
        "emoji": "⚡",
        "color": {"r": 30, "g": 100, "b": 200},  # Blue
        "working_dir": "~/Dev/Vortex/backend",
        "badge": "VORTEX",
    },
    "winfield": {
        "name": "Winfield",
        "emoji": "🌊",
        "color": {"r": 0, "g": 180, "b": 180},  # Cyan
        "working_dir": "~/Dev/Vortex/Winfield",
        "badge": "WINFIELD",
    },
    "cortex": {
        "name": "Cortex",
        "emoji": "🧠",
        "color": {"r": 130, "g": 50, "b": 200},  # Purple
        "working_dir": "~/Dev/cortex",
        "badge": "CORTEX",
    },
    "alpha_arena": {
        "name": "Alpha Arena",
        "emoji": "🎯",
        "color": {"r": 220, "g": 120, "b": 20},  # Orange
        "working_dir": "~/Dev/alpha_arena",
        "badge": "ALPHA",
    },
    "pupil": {
        "name": "Pupil",
        "emoji": "📊",
        "color": {"r": 200, "g": 170, "b": 20},  # Gold
        "working_dir": "~/Dev/Pupil",
        "badge": "PUPIL",
    },
    "dj_copilot": {
        "name": "DJ CoPilot",
        "emoji": "🎵",
        "color": {"r": 220, "g": 50, "b": 130},  # Pink
        "working_dir": "~/Dev/DJ-CoPilot",
        "badge": "DJ",
    },
    "kempion": {
        "name": "Kempion",
        "emoji": "🔬",
        "color": {"r": 50, "g": 180, "b": 80},  # Green
        "working_dir": "~/Dev/kempion-research-site",
        "badge": "KEMPION",
    },
}

PHASES = {
    "plan": {"emoji": "🧠", "badge_suffix": ":PLAN", "model": "opus"},
    "design": {"emoji": "🎨", "badge_suffix": ":DESIGN", "model": "opus"},
    "build": {"emoji": "⚡", "badge_suffix": ":BUILD", "model": "sonnet"},
    "test": {"emoji": "🧪", "badge_suffix": ":TEST", "model": "sonnet"},
    "verify": {"emoji": "✅", "badge_suffix": ":VERIFY", "model": "sonnet"},
    "ship": {"emoji": "🚀", "badge_suffix": ":SHIP", "model": "sonnet"},
    "connect": {"emoji": "🔗", "badge_suffix": ":CONNECT", "model": "opus"},
    "research": {"emoji": "🔬", "badge_suffix": ":RESEARCH", "model": "opus"},
}

WINDOW_LAYOUTS = {
    "active-project": {
        "description": "Standard 5-tab layout for active project work",
        "tabs": ["plan", "build", "test", "ship", "connect"],
    },
    "research-lab": {
        "description": "Research-focused layout with data analysis",
        "tabs": ["research", "build", "test"],
    },
    "mission-control": {
        "description": "Cortex dashboard + monitoring",
        "tabs": ["cortex:research", "cortex:build", "cortex:test"],
    },
    "ship-mode": {
        "description": "Deployment-focused with monitoring",
        "tabs": ["ship", "test", "connect"],
    },
}

# ─── iTerm2 Dynamic Profile Generator ───────────────────────


@dataclass
class ITermProfile:
    """An iTerm2 dynamic profile definition."""

    name: str
    guid: str
    badge: str
    working_directory: str
    initial_text: str
    tab_color: Dict[str, int]
    tags: List[str]
    triggers: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to iTerm2 dynamic profile JSON format."""
        return {
            "Name": self.name,
            "Guid": self.guid,
            "Badge Text": self.badge,
            "Working Directory": self.working_directory,
            "Custom Directory": "Yes",
            "Initial Text": self.initial_text,
            "Tab Color": {
                "Red Component": self.tab_color["r"] / 255,
                "Green Component": self.tab_color["g"] / 255,
                "Blue Component": self.tab_color["b"] / 255,
                "Color Space": "sRGB",
            },
            "Use Tab Color": True,
            "Tags": self.tags,
            "Triggers": self.triggers,
            # Shell integration
            "Shell Integration Installed": True,
            # Status bar with Cortex info
            "Show Status Bar": True,
        }


def generate_profiles() -> List[Dict[str, Any]]:
    """Generate all iTerm2 dynamic profiles for workstream orchestration."""
    profiles = []

    for proj_key, proj in PROJECTS.items():
        for phase_key, phase in PHASES.items():
            name = f"{proj['emoji']} {proj['name']}-{phase_key.title()}"
            guid = f"cortex-{proj_key}-{phase_key}"
            badge = f"{proj['badge']}{phase['badge_suffix']}"
            working_dir = Path(proj["working_dir"]).expanduser()

            # Shell init command with Cortex context injection
            init_cmd = (
                f"echo '\\n{proj['emoji']} {proj['name']} — {phase['emoji']} {phase_key.upper()}\\n'"
                f' && python3 -c "'
                f"import sys; sys.path.insert(0, '{Path('~/Dev/cortex').expanduser()}');"
                f" from engines.workstream_orchestrator import WorkstreamOrchestrator;"
                f" o = WorkstreamOrchestrator();"
                f" ws = o.activate_workstream('{proj_key}', '{phase_key}');"
                f" print(f'  Workstream: {{ws.project}}:{{ws.phase.value}}')"
                f'" 2>/dev/null || true'
            )

            # Smart triggers for error/success detection
            triggers = [
                {
                    "partial": True,
                    "parameter": "Error|ERROR|error|Exception|FAILED",
                    "regex": True,
                    "action": 1,  # Highlight
                },
                {
                    "partial": True,
                    "parameter": "PASSED|passed|✓|SUCCESS",
                    "regex": True,
                    "action": 1,  # Highlight
                },
                {
                    "partial": True,
                    "parameter": "force.push|--force",
                    "regex": True,
                    "action": 1,  # Highlight (danger)
                },
            ]

            profile = ITermProfile(
                name=name,
                guid=guid,
                badge=badge,
                working_directory=str(working_dir),
                initial_text=init_cmd,
                tab_color=proj["color"],
                tags=[proj_key, phase_key, "cortex-managed"],
                triggers=triggers,
            )
            profiles.append(profile.to_dict())

    # Add special cross-cutting profiles
    profiles.extend(_generate_special_profiles())

    return profiles


def _generate_special_profiles() -> List[Dict[str, Any]]:
    """Generate special cross-cutting profiles."""
    specials = []

    # Cortex Hotkey Window — quick intelligence queries
    specials.append(
        {
            "Name": "🧠 Cortex Quick Query",
            "Guid": "cortex-hotkey-query",
            "Badge Text": "CORTEX:QUERY",
            "Working Directory": str(Path("~/Dev/cortex").expanduser()),
            "Custom Directory": "Yes",
            "Initial Text": (
                "echo '🧠 Cortex Quick Query — type your intelligence request'"
                " && echo '  Usage: python cortex/bridge.py intelligence \"<query>\"'"
            ),
            "Tags": ["cortex", "hotkey", "cortex-managed"],
            "Tab Color": {
                "Red Component": 0.5,
                "Green Component": 0.2,
                "Blue Component": 0.8,
                "Color Space": "sRGB",
            },
            "Use Tab Color": True,
            "Show Status Bar": True,
        }
    )

    # Batch Monitor
    specials.append(
        {
            "Name": "📊 Batch Monitor",
            "Guid": "cortex-batch-monitor",
            "Badge Text": "BATCH",
            "Working Directory": str(Path("~/Dev/cortex").expanduser()),
            "Custom Directory": "Yes",
            "Initial Text": (
                "echo '📊 Cortex Batch Monitor'"
                ' && python3 -c "'
                "import sys; sys.path.insert(0, '.');"
                " from batch.queue_manager import BatchQueueManager;"
                " m = BatchQueueManager();"
                " print(m.get_queue_summary())"
                "\" 2>/dev/null || echo '  No active batches'"
            ),
            "Tags": ["cortex", "batch", "cortex-managed"],
            "Tab Color": {
                "Red Component": 0.1,
                "Green Component": 0.6,
                "Blue Component": 0.3,
                "Color Space": "sRGB",
            },
            "Use Tab Color": True,
            "Show Status Bar": True,
        }
    )

    return specials


def install_profiles() -> Path:
    """Install dynamic profiles to iTerm2.

    Returns path to installed profile file.
    """
    profiles = generate_profiles()
    profile_doc = {"Profiles": profiles}

    # iTerm2 dynamic profiles directory
    profiles_dir = Path("~/Library/Application Support/iTerm2/DynamicProfiles").expanduser()
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_path = profiles_dir / "cortex-workstreams.json"
    with open(profile_path, "w") as f:
        json.dump(profile_doc, f, indent=2)

    print(f"✅ Installed {len(profiles)} profiles to {profile_path}")
    return profile_path


# ─── Shell Integration Hooks ────────────────────────────────


def generate_shell_hooks() -> str:
    """Generate shell hooks for .zshrc that integrate with Cortex.

    These hooks:
    1. Auto-detect project from cwd and set workstream context
    2. Inject Cortex context into shell prompt
    3. Track command execution for signal capture
    """
    return """
# ═══════════════════════════════════════════════════════════
# Cortex Workstream Integration (auto-generated)
# Add to ~/.zshrc: source ~/.cortex/shell_hooks.zsh
# ═══════════════════════════════════════════════════════════

# Project detection from directory
_cortex_detect_project() {
    local dir="$PWD"
    case "$dir" in
        */Vortex/Winfield*) echo "winfield:build" ;;
        */Vortex/frontend*) echo "vortex:build" ;;
        */Vortex/backend*|*/Vortex*) echo "vortex:build" ;;
        */alpha_arena*) echo "alpha_arena:build" ;;
        */cortex*) echo "cortex:research" ;;
        */Pupil*) echo "pupil:build" ;;
        */DJ-CoPilot*) echo "dj_copilot:build" ;;
        */kempion*) echo "kempion:build" ;;
        *) echo "" ;;
    esac
}

# Activate workstream on directory change
_cortex_chpwd_hook() {
    local ws=$(_cortex_detect_project)
    if [[ -n "$ws" ]]; then
        local project="${ws%%:*}"
        local phase="${ws##*:}"
        export CORTEX_PROJECT="$project"
        export CORTEX_PHASE="$phase"

        # Lightweight activation (no heavy Python on every cd)
        # Full context available via: cortex context
    fi
}

# Register hook
autoload -Uz add-zsh-hook
add-zsh-hook chpwd _cortex_chpwd_hook

# Quick commands
alias cx='python3 ~/Dev/cortex/bridge.py'
alias cxi='cx intelligence'
alias cxc='cx context'
alias cxs='cx session-context'
alias cxh='cx health summary'
alias cxp='cx portfolio stats'

# Workstream switch (updates iTerm badge)
cxw() {
    local project="$1"
    local phase="${2:-build}"
    export CORTEX_PROJECT="$project"
    export CORTEX_PHASE="$phase"
    printf "\\e]1337;SetBadgeFormat=%s\\a" $(echo -n "${project^^}:${phase^^}" | base64)
    echo "🧠 Workstream: $project:$phase"
}

# Quick trust check
cxt() {
    python3 -c "
import sys; sys.path.insert(0, '$HOME/Dev/cortex')
from engines.workstream_orchestrator import WorkstreamOrchestrator
o = WorkstreamOrchestrator()
summary = o.get_trust_summary()
for domain, info in summary['domains'].items():
    level_icons = ['🔴', '🟠', '🟡', '🟢', '💚']
    icon = level_icons[info['level']]
    print(f'  {icon} {domain:20s} L{info[\"level\"]} ({info[\"accuracy\"]*100:.0f}% acc, {info[\"outcomes\"]} outcomes)')
print(f'\\n  📊 Avg trust: L{summary[\"aggregate\"][\"avg_trust_level\"]:.1f}')
" 2>/dev/null || echo "  ⚠ Cortex not available"
}

# Initialize on shell start
_cortex_chpwd_hook
"""


def install_shell_hooks() -> Path:
    """Install shell hooks to ~/.cortex/shell_hooks.zsh."""
    hooks_path = Path("~/.cortex/shell_hooks.zsh").expanduser()
    hooks_path.parent.mkdir(parents=True, exist_ok=True)

    with open(hooks_path, "w") as f:
        f.write(generate_shell_hooks())

    print(f"✅ Shell hooks installed to {hooks_path}")
    print(f"   Add to ~/.zshrc: source {hooks_path}")
    return hooks_path


# ─── Keyboard Shortcut Configuration ────────────────────────


def generate_shortcut_guide() -> str:
    """Generate a keyboard shortcut reference guide."""
    return """
═══════════════════════════════════════════════════════════
  COMMAND CENTER — Keyboard Orchestration Guide
═══════════════════════════════════════════════════════════

  WORKSTREAM SWITCHING
  ──────────────────────────────────────────────────────
  ⌘1-5         Switch between PLAN/BUILD/TEST/SHIP/CONNECT tabs
  ⌘⇧1-5        Switch between project window groups
  ⌘T           New tab with current project profile

  CORTEX QUICK ACCESS
  ──────────────────────────────────────────────────────
  ⌘⌥C          Hotkey: Quick Cortex intelligence query
  ⌘⌥B          Hotkey: Batch status dashboard
  ⌘⌥T          Hotkey: Smart test runner

  PANE MANAGEMENT
  ──────────────────────────────────────────────────────
  ⌘D           Split pane horizontally
  ⌘⇧D          Split pane vertically
  ⌘⌥←/→        Navigate between panes
  ⌘⇧Enter      Broadcast input to all panes

  NAVIGATION
  ──────────────────────────────────────────────────────
  ⌘⇧↑/↓        Scroll to previous/next command (shell integration)
  ⌘⇧A          Select output of last command
  ⌘;            Autocomplete from command history
  ⌘⇧;           Open command history window

  CUSTOM ALIASES (after shell hooks installed)
  ──────────────────────────────────────────────────────
  cx            Cortex bridge shortcut
  cxi <query>   Intelligence query
  cxc           Get current context
  cxw <proj>    Switch workstream + update badge
  cxt           Trust level summary

═══════════════════════════════════════════════════════════
"""


# ─── CLI Entry Point ─────────────────────────────────────────


def main():
    """CLI entry point for iTerm orchestrator."""
    if len(sys.argv) < 2:
        print("Usage: iterm_orchestrator.py <command>")
        print("Commands: setup, profiles, hooks, shortcuts, layout")
        sys.exit(1)

    command = sys.argv[1]

    if command == "setup":
        print("═══ Cortex iTerm2 Orchestrator Setup ═══\n")
        install_profiles()
        install_shell_hooks()
        print(f"\n{generate_shortcut_guide()}")
        print("\n✅ Setup complete! Restart iTerm2 to load profiles.")

    elif command == "profiles":
        install_profiles()

    elif command == "hooks":
        install_shell_hooks()

    elif command == "shortcuts":
        print(generate_shortcut_guide())

    elif command == "layout":
        layout_name = sys.argv[2] if len(sys.argv) > 2 else "active-project"
        if layout_name in WINDOW_LAYOUTS:
            layout = WINDOW_LAYOUTS[layout_name]
            print(f"Layout: {layout_name} — {layout['description']}")
            print(f"Tabs: {', '.join(layout['tabs'])}")
            print("\n(iTerm2 Python API layout application requires iTerm2 running)")
        else:
            print(f"Unknown layout: {layout_name}")
            print(f"Available: {', '.join(WINDOW_LAYOUTS.keys())}")

    elif command == "switch":
        if len(sys.argv) < 3:
            print("Usage: iterm_orchestrator.py switch <project> [phase]")
            sys.exit(1)
        project = sys.argv[2]
        phase = sys.argv[3] if len(sys.argv) > 3 else "build"
        print(f"Switching to {project}:{phase}")
        # Would use iTerm2 Python API to switch tabs

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
