#!/usr/bin/env python3
"""
Shell hooks for Cortex workstream detection.

This is NOT a profile generator. Create your 5 iTerm profiles manually:
  1. Vortex (blue)     — cd ~/Dev/Vortex/backend
  2. Cortex (purple)   — cd ~/Dev/cortex
  3. Pupil (gold)      — cd ~/Dev/Pupil
  4. Research (magenta) — cd ~/Dev/cortex
  5. Ship (red)        — project-specific

This file generates ~/.cortex/shell_hooks.zsh — the only automation
that actually reduces friction. Install once:

    python cortex/automation/iterm_orchestrator.py
    # then add to ~/.zshrc: source ~/.cortex/shell_hooks.zsh
"""

from pathlib import Path

SHELL_HOOKS = r"""
# Cortex Workstream Detection (auto-generated)
# source ~/.cortex/shell_hooks.zsh

# Auto-detect project from cwd
_cortex_detect_project() {
    case "$PWD" in
        */Vortex*)          echo "vortex" ;;
        */alpha_arena*)     echo "alpha_arena" ;;
        */cortex*)          echo "cortex" ;;
        */Pupil*)           echo "pupil" ;;
        */DJ-CoPilot*)      echo "dj_copilot" ;;
        */kempion*)         echo "kempion" ;;
        *)                  echo "" ;;
    esac
}

# Set env vars on cd (lightweight — no Python)
_cortex_chpwd() {
    local proj=$(_cortex_detect_project)
    [[ -n "$proj" ]] && export CORTEX_PROJECT="$proj"
}
autoload -Uz add-zsh-hook
add-zsh-hook chpwd _cortex_chpwd

# Aliases — the useful ones
alias cx='python3 ~/Dev/cortex/bridge.py'
alias cxi='cx intelligence'
alias cxc='cx context'

# Switch workstream + update iTerm badge
cxw() {
    export CORTEX_PROJECT="${1:-$CORTEX_PROJECT}"
    printf "\e]1337;SetBadgeFormat=%s\a" $(echo -n "${1^^}" | base64)
    echo "🧠 $1"
}

_cortex_chpwd
"""


def install():
    path = Path("~/.cortex/shell_hooks.zsh").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SHELL_HOOKS)
    print(f"✅ Installed to {path}")
    print(f"   Add to ~/.zshrc: source {path}")


if __name__ == "__main__":
    install()
