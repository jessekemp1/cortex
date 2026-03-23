#!/bin/bash
# Cortex Morning Briefing Script
# Runs daily to generate briefing and save to file

CORTEX_DIR="/Users/jesse/dev/cortex"
BRIEFING_DIR="/Users/jesse/.cortex/briefings"
ABSORBER_LOG="/Users/jesse/.cortex/work_absorber.log"
DATE=$(date +%Y-%m-%d)
BRIEFING_FILE="$BRIEFING_DIR/briefing_$DATE.txt"

# Ensure directories exist
mkdir -p "$BRIEFING_DIR"

cd "$CORTEX_DIR"

# Step 1: Run work absorber to capture overnight progress
echo "$(date): Starting work absorption..." >> "$ABSORBER_LOG"
python3 -c "
import sys
sys.path.insert(0, '.')
from work_absorber import WorkAbsorber
from work_absorber.storage import WorkAbsorberStorage

storage = WorkAbsorberStorage()
absorber = WorkAbsorber(storage)
report = absorber.absorb(incremental=True)
print(f'Absorbed: {report.signals_absorbed} signals, {report.work_items_created + report.work_items_updated} items')
" >> "$ABSORBER_LOG" 2>&1

# Step 2: Generate briefing (now includes absorbed work)
python3 cli.py briefing > "$BRIEFING_FILE" 2>&1

# Send macOS notification
osascript -e 'display notification "Your daily briefing is ready" with title "Cortex" subtitle "Check ~/.cortex/briefings/"'

# Log execution
echo "$(date): Briefing generated at $BRIEFING_FILE" >> "$BRIEFING_DIR/briefing.log"

# Optional: Open in terminal if user is logged in
# open -a Terminal "$BRIEFING_FILE"
