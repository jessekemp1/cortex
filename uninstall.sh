#!/bin/bash
# =============================================================================
# Cortex Uninstall Script
# =============================================================================
# Usage: ./uninstall.sh [--yes] [--purge]
#
#   --yes     Non-interactive; assume "yes" to prompts.
#   --purge   Also wipe Cortex state (~/.cortex or CORTEX_STATE_DIR) via
#             `cortex reset --force`. Without --purge, state is left intact.
#
# Reverses what install.sh set up, each step degrading gracefully if the tool
# is absent:
#   - unloads the com.cortex.bridge LaunchAgent / systemd unit
#   - removes the Cortex MCP entry from Claude Code (claude mcp remove cortex)
#   - removes the ~/.local/bin/cortex + cx symlinks
#   - optionally wipes state (--purge)
# =============================================================================

set -uo pipefail

ASSUME_YES=false
PURGE=false
for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES=true ;;
        --purge) PURGE=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$SCRIPT_DIR"
HOME_DIR="$HOME"
LOCAL_BIN="$HOME_DIR/.local/bin"
VENV="${CORTEX_VENV:-$CORTEX_DIR/.venv}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

if [ "$ASSUME_YES" = false ] && [ -t 0 ]; then
    echo "This will unload the Cortex bridge agent, remove its MCP entry from"
    echo "Claude Code, and delete the ~/.local/bin/cortex symlinks."
    [ "$PURGE" = true ] && echo "It will ALSO wipe all Cortex state (--purge)."
    read -rp "Proceed? [y/N]: " CONFIRM || true
    [[ "$CONFIRM" =~ ^[Yy] ]] || { echo "Aborted."; exit 0; }
fi

# ─── Step 1: Unload the bridge launch agent / systemd unit ──────────────────
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    PLIST="$HOME_DIR/Library/LaunchAgents/com.cortex.bridge.plist"
    if [ -f "$PLIST" ]; then
        if command -v launchctl >/dev/null 2>&1; then
            launchctl unload "$PLIST" 2>/dev/null || true
        fi
        rm -f "$PLIST"
        log "Removed bridge LaunchAgent"
    else
        info "No bridge LaunchAgent found (nothing to unload)"
    fi
else
    UNIT="$HOME_DIR/.config/systemd/user/com.cortex.bridge.service"
    if [ -f "$UNIT" ]; then
        command -v systemctl >/dev/null 2>&1 && systemctl --user disable --now com.cortex.bridge.service 2>/dev/null || true
        rm -f "$UNIT"
        log "Removed bridge systemd unit"
    else
        info "No bridge systemd unit found"
    fi
fi

# ─── Step 2: Remove the Cortex MCP entry from Claude Code ───────────────────
CLAUDE_BIN="${CORTEX_CLAUDE_BIN:-$(command -v claude || true)}"
if [ -n "${CLAUDE_BIN:-}" ]; then
    if "$CLAUDE_BIN" mcp remove cortex >/dev/null 2>&1; then
        log "Removed Cortex MCP entry from Claude Code"
    else
        info "Cortex MCP entry not present in Claude Code (or already removed)"
    fi
else
    info "Claude CLI not found — remove the MCP entry manually: claude mcp remove cortex"
fi

# ─── Step 3: Remove PATH symlinks ────────────────────────────────────────────
for link in cortex cx; do
    if [ -L "$LOCAL_BIN/$link" ]; then
        rm -f "$LOCAL_BIN/$link"
        log "Removed symlink ~/.local/bin/$link"
    fi
done

# ─── Step 4: Optionally wipe state ──────────────────────────────────────────
if [ "$PURGE" = true ]; then
    if [ -x "$VENV/bin/python" ]; then
        "$VENV/bin/python" -m cli reset --force 2>&1 | sed 's/^/    /' || warn "state wipe reported warnings"
    else
        warn "venv python not found — wipe state manually: rm -rf ~/.cortex"
    fi
else
    info "Cortex state left intact. Re-run with --purge to wipe it."
fi

echo ""
log "Cortex uninstalled."
