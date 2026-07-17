#!/usr/bin/env bash
# Install Cortex + project LaunchAgents (macOS) or systemd user units (Linux).
# Uses __HOME__/__DEV_DIR__ placeholder substitution — never hardcode paths in plists.
#
# Usage:
#   bash cortex/scripts/install_launchagents.sh [--dry-run]
#
# macOS: installs to ~/Library/LaunchAgents/, loads via launchctl
# Linux: installs to ~/.config/systemd/user/, enables via systemctl --user

set -euo pipefail

HOME_DIR="$HOME"
DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DRY_RUN=false
OS="$(uname -s)"

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

PLISTS=(
  "cortex/com.cortex.bridge.plist"
  "cortex/com.cortex.heartbeat.plist"
  "cortex/automation/com.cortex.alert-monitor.plist"
  "cortex/automation/com.cortex.daily.plist"
  "cortex/batch/automation/com.cortex.batch.morning.plist"
  "cortex/batch/automation/com.cortex.batch.nightly.plist"
  "cortex/batch/automation/com.cortex.flywheel.plist"
  "alpha_arena/scripts/com.alphaarena.venezuela.intelligence.plist"
)

# ── macOS path ────────────────────────────────────────────────────────────────

install_plist_macos() {
  local src="$DEV_DIR/$1"
  local label
  label=$(basename "$1")
  local dest="$HOME_DIR/Library/LaunchAgents/$label"

  [[ ! -f "$src" ]] && echo "SKIP (not found): $src" && return

  local py_bin
  py_bin=$(command -v python3 || command -v python || echo "/usr/local/bin/python")

  local content
  content=$(sed "s|__HOME__|$HOME_DIR|g; s|__DEV_DIR__|$DEV_DIR|g; s|/usr/local/bin/python\b|$py_bin|g" "$src")

  if $DRY_RUN; then
    echo "--- DRY RUN: $dest ---"
    echo "$content"
    return
  fi

  mkdir -p "$HOME_DIR/Library/LaunchAgents"
  echo "$content" > "$dest"
  echo "Installed: $dest"
  launchctl unload "$dest" 2>/dev/null || true
  launchctl load "$dest"
  echo "Loaded:    $label"
}

# ── Linux/systemd path ────────────────────────────────────────────────────────

# Converts a plist (with substituted paths) to systemd .service + optional .timer
# using Python's stdlib xml.etree. Prints the unit file(s) to stdout as:
#   UNIT:<name>.service
#   <content>
#   UNIT:<name>.timer      (only if StartInterval or StartCalendarInterval present)
#   <content>
plist_to_systemd() {
  local plist_content="$1"
  python3 - "$plist_content" <<'PYEOF'
import sys, xml.etree.ElementTree as ET, re

content = sys.argv[1]
root = ET.fromstring(content)
d = root.find('dict')

def node_value(node):
    if node.tag == 'string': return node.text or ''
    if node.tag == 'integer': return int(node.text)
    if node.tag == 'true': return True
    if node.tag == 'false': return False
    if node.tag == 'array': return [node_value(c) for c in node]
    if node.tag == 'dict':
        it = iter(node)
        result = {}
        for key in it:
            val = next(it)
            result[key.text] = node_value(val)
        return result
    return node.text

data = node_value(d)

label = data.get('Label', 'unknown')
args = data.get('ProgramArguments', [])
exec_start = ' '.join(args)
interval = data.get('StartInterval')  # seconds
env_vars = data.get('EnvironmentVariables', {})
stdout = data.get('StandardOutPath', '')
stderr = data.get('StandardErrorPath', '')

env_lines = '\n'.join(f'Environment="{k}={v}"' for k, v in env_vars.items()) if env_vars else ''
stdout_line = f'StandardOutput=append:{stdout}' if stdout else ''
stderr_line = f'StandardError=append:{stderr}' if stderr else ''

service = f"""[Unit]
Description={label}
After=network.target

[Service]
Type=oneshot
ExecStart={exec_start}
{env_lines}
{stdout_line}
{stderr_line}

[Install]
WantedBy=default.target
""".strip()

print(f"UNIT:{label}.service")
print(service)

if interval:
    timer = f"""[Unit]
Description={label} timer
Requires={label}.service

[Timer]
OnBootSec=60
OnUnitActiveSec={interval}
Unit={label}.service

[Install]
WantedBy=timers.target
""".strip()
    print(f"UNIT:{label}.timer")
    print(timer)
PYEOF
}

install_plist_linux() {
  local src="$DEV_DIR/$1"
  [[ ! -f "$src" ]] && echo "SKIP (not found): $src" && return

  # Resolve python path for this machine (/usr/local/bin/python may not exist on Linux)
  local py_bin
  py_bin=$(command -v python3 || command -v python || echo "/usr/bin/python3")

  local content
  content=$(sed "s|__HOME__|$HOME_DIR|g; s|__DEV_DIR__|$DEV_DIR|g; s|/usr/local/bin/python\b|$py_bin|g" "$src")

  local systemd_dir="$HOME_DIR/.config/systemd/user"
  local units
  units=$(plist_to_systemd "$content")

  # Parse UNIT: blocks
  local current_name=""
  local current_body=""
  while IFS= read -r line; do
    if [[ "$line" == UNIT:* ]]; then
      # Flush previous unit
      if [[ -n "$current_name" ]]; then
        local dest="$systemd_dir/$current_name"
        if $DRY_RUN; then
          echo "--- DRY RUN: $dest ---"
          echo "$current_body"
        else
          mkdir -p "$systemd_dir"
          echo "$current_body" > "$dest"
          echo "Installed: $dest"
        fi
      fi
      current_name="${line#UNIT:}"
      current_body=""
    else
      current_body+="$line"$'\n'
    fi
  done <<< "$units"

  # Flush last unit
  if [[ -n "$current_name" ]]; then
    local dest="$systemd_dir/$current_name"
    if $DRY_RUN; then
      echo "--- DRY RUN: $dest ---"
      echo "$current_body"
    else
      mkdir -p "$systemd_dir"
      echo "$current_body" > "$dest"
      echo "Installed: $dest"
      systemctl --user daemon-reload
      # Enable timer if present, else enable service directly
      if [[ "$current_name" == *.timer ]]; then
        systemctl --user enable --now "$current_name" 2>/dev/null && echo "Enabled:   $current_name" || echo "WARN: could not enable $current_name"
      fi
    fi
  fi
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

for plist in "${PLISTS[@]}"; do
  if [[ "$OS" == "Darwin" ]]; then
    install_plist_macos "$plist"
  else
    install_plist_linux "$plist"
  fi
done

echo ""
if [[ "$OS" == "Darwin" ]]; then
  echo "Done. Run 'launchctl list | grep cortex' to verify."
else
  echo "Done. Run 'systemctl --user list-units | grep cortex' to verify."
fi
