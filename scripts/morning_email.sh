#!/bin/bash
# Cortex Kempion Morning Email Script
# Sends the full Kempion-infused briefing via Resend at 8am daily
#
# Setup:
#   1. Set RESEND_API_KEY in ~/.cortex/secrets/resend_api_key or environment
#   2. Install cron: crontab -e, add: 0 8 * * * /path/to/cortex/scripts/morning_email.sh
#   Or run manually: ./scripts/morning_email.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$HOME/.cortex/logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/morning_email.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

cd "$CORTEX_DIR"

# Load environment
if [ -f "$CORTEX_DIR/.env" ]; then
    export $(grep -v '^#' "$CORTEX_DIR/.env" | xargs)
fi

# Load secrets
if [ -f "$HOME/.cortex/secrets/resend_api_key" ]; then
    export RESEND_API_KEY=$(cat "$HOME/.cortex/secrets/resend_api_key")
fi

echo "$(date): Starting Kempion morning email..." >> "$LOG_FILE"

# Step 1: Run work absorber to capture overnight progress
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from work_absorber import WorkAbsorber
    from work_absorber.storage import WorkAbsorberStorage
    storage = WorkAbsorberStorage()
    absorber = WorkAbsorber(storage)
    report = absorber.absorb(incremental=True)
    print(f'Absorbed: {report.signals_absorbed} signals')
except Exception as e:
    print(f'Work absorber skipped: {e}')
" >> "$LOG_FILE" 2>&1

# Step 2: Send Kempion briefing email
python3 cli.py morning-email --to jessekemp1@gmail.com >> "$LOG_FILE" 2>&1

# Step 3: Also save text briefing to file
BRIEFING_DIR="$HOME/.cortex/briefings"
mkdir -p "$BRIEFING_DIR"
python3 cli.py briefing --no-color > "$BRIEFING_DIR/briefing_$DATE.txt" 2>&1

echo "$(date): Morning email complete" >> "$LOG_FILE"
