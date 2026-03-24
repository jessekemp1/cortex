#!/usr/bin/env bash
# Install Cortex + project LaunchAgents for the current machine.
# Uses __HOME__ placeholder substitution — never hardcode paths in plists.
# Usage: bash cortex/scripts/install_launchagents.sh [--dry-run]

set -euo pipefail

HOME_DIR="$HOME"
DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME_DIR/Library/LaunchAgents"
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

PLISTS=(
  "cortex/com.cortex.heartbeat.plist"
  "cortex/automation/com.cortex.alert-monitor.plist"
  "cortex/automation/com.cortex.daily.plist"
  "cortex/batch/automation/com.cortex.batch.morning.plist"
  "cortex/batch/automation/com.cortex.batch.nightly.plist"
  "cortex/batch/automation/com.cortex.flywheel.plist"
  "alpha_arena/scripts/com.alphaarena.venezuela.intelligence.plist"
)

install_plist() {
  local src="$DEV_DIR/$1"
  local label
  label=$(basename "$1")
  local dest="$LAUNCH_AGENTS_DIR/$label"

  if [[ ! -f "$src" ]]; then
    echo "SKIP (not found): $src"
    return
  fi

  local content
  content=$(sed "s|__HOME__|$HOME_DIR|g; s|__DEV_DIR__|$DEV_DIR|g" "$src")

  if $DRY_RUN; then
    echo "--- DRY RUN: $dest ---"
    echo "$content"
    return
  fi

  echo "$content" > "$dest"
  echo "Installed: $dest"

  # Reload if already loaded
  launchctl unload "$dest" 2>/dev/null || true
  launchctl load "$dest"
  echo "Loaded:    $label"
}

mkdir -p "$LAUNCH_AGENTS_DIR"

for plist in "${PLISTS[@]}"; do
  install_plist "$plist"
done

echo ""
echo "Done. Run 'launchctl list | grep cortex' to verify."
