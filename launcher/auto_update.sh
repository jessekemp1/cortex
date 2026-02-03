#!/bin/bash
# Cortex Launcher Auto-Update Service
# Runs project_scanner.py every 10 seconds to keep launcher data fresh

LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$LAUNCHER_DIR/auto_update.log"

echo "🚀 Cortex Launcher Auto-Update Service Started" | tee -a "$LOG_FILE"
echo "   Scanning every 10 seconds..." | tee -a "$LOG_FILE"
echo "   Data: $LAUNCHER_DIR/launcher_data.json" | tee -a "$LOG_FILE"
echo "   Press Ctrl+C to stop" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    echo "[$TIMESTAMP] Running scan..." >> "$LOG_FILE"

    cd "$LAUNCHER_DIR"
    python3 project_scanner.py >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
        echo "[$TIMESTAMP] ✅ Scan complete" >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] ❌ Scan failed" >> "$LOG_FILE"
    fi

    sleep 10
done
