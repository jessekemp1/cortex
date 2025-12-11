#!/bin/bash
# Cortex Morning Briefing Script
# Runs daily to generate briefing and save to file

CORTEX_DIR="/Users/jesse.kemp/Dev/cortex"
BRIEFING_DIR="/Users/jesse.kemp/.cortex/briefings"
DATE=$(date +%Y-%m-%d)
BRIEFING_FILE="$BRIEFING_DIR/briefing_$DATE.txt"

# Ensure briefing directory exists
mkdir -p "$BRIEFING_DIR"

# Generate briefing
cd "$CORTEX_DIR"
python3 cli.py briefing > "$BRIEFING_FILE" 2>&1

# Send macOS notification
osascript -e 'display notification "Your daily briefing is ready" with title "Cortex" subtitle "Check ~/.cortex/briefings/"'

# Log execution
echo "$(date): Briefing generated at $BRIEFING_FILE" >> "$BRIEFING_DIR/briefing.log"

# Optional: Open in terminal if user is logged in
# open -a Terminal "$BRIEFING_FILE"
