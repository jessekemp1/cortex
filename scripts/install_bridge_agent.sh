#!/usr/bin/env bash
# Install ONLY the com.cortex.bridge keep-alive LaunchAgent (macOS) or systemd
# user unit (Linux). This is the scoped counterpart to install_launchagents.sh
# (which installs the full curated set) — used by `install.sh --yes` so the
# golden path supervises just the :8765 bridge, nothing else.
#
# Degrades gracefully when launchctl/systemctl are unavailable (CI/sandbox):
# it substitutes paths and writes the unit, but a failed load is non-fatal.
#
# Env overrides (for isolated installs): CORTEX_VENV, CORTEX_STATE_DIR.

set -uo pipefail

HOME_DIR="$HOME"
DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CORTEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="$CORTEX_DIR/com.cortex.bridge.plist"
VENV="${CORTEX_VENV:-$CORTEX_DIR/.venv}"
OS="$(uname -s)"

[[ ! -f "$PLIST_SRC" ]] && { echo "SKIP: $PLIST_SRC not found"; exit 0; }

# CORTEX_SKIP_LAUNCHD=1 writes nothing and loads nothing — used by tests/CI so a
# non-interactive install never touches the real launchd session.
if [[ "${CORTEX_SKIP_LAUNCHD:-0}" == "1" ]]; then
    echo "CORTEX_SKIP_LAUNCHD=1 — skipping launch agent install"
    exit 0
fi

# Ensure the bridge log dir exists (plist writes stdout/stderr there).
mkdir -p "${CORTEX_STATE_DIR:-$HOME_DIR/.cortex}/logs" 2>/dev/null || true

if [[ "$OS" == "Darwin" ]]; then
    if ! command -v launchctl >/dev/null 2>&1; then
        echo "launchctl unavailable — skipping load (non-fatal)"
        exit 0
    fi
    dest="$HOME_DIR/Library/LaunchAgents/com.cortex.bridge.plist"
    py_bin="$VENV/bin/python3"
    [[ -x "$py_bin" ]] || py_bin="$(command -v python3 || echo python3)"
    mkdir -p "$HOME_DIR/Library/LaunchAgents"
    # Substitute placeholders + point at the resolved venv python.
    sed "s|__HOME__|$HOME_DIR|g; s|__DEV_DIR__|$DEV_DIR|g; s|__DEV_DIR__/cortex/.venv/bin/python3|$py_bin|g" \
        "$PLIST_SRC" > "$dest"
    echo "Installed: $dest"
    launchctl unload "$dest" 2>/dev/null || true
    if launchctl load "$dest" 2>/dev/null; then
        echo "Loaded:    com.cortex.bridge"
    else
        echo "Load skipped (launchctl load failed — non-fatal)"
    fi
    exit 0
fi

# Linux/systemd (best-effort)
if command -v systemctl >/dev/null 2>&1; then
    unit_dir="$HOME_DIR/.config/systemd/user"
    mkdir -p "$unit_dir"
    py_bin="$VENV/bin/python3"
    [[ -x "$py_bin" ]] || py_bin="$(command -v python3 || echo python3)"
    cat > "$unit_dir/com.cortex.bridge.service" <<UNIT
[Unit]
Description=Cortex Bridge API keep-alive
After=network.target

[Service]
Type=simple
WorkingDirectory=$CORTEX_DIR
Environment="PYTHONPATH=$DEV_DIR"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$py_bin $CORTEX_DIR/api/bridge_endpoint.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
UNIT
    echo "Installed: $unit_dir/com.cortex.bridge.service"
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable --now com.cortex.bridge.service 2>/dev/null \
        && echo "Enabled: com.cortex.bridge.service" \
        || echo "Enable skipped (systemctl --user unavailable — non-fatal)"
    exit 0
fi

echo "No launchctl/systemctl — bridge agent not supervised (non-fatal)"
exit 0
