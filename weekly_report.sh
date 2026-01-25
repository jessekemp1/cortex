#!/bin/bash
# Cortex Weekly Summary
# Generates a comprehensive weekly report of Cortex activity and improvements
# Usage: ./weekly_report.sh

set -e

CORTEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="$HOME/.cortex"
LOG_DIR="$CORTEX_HOME/logs"
REPORT_LOG="$LOG_DIR/weekly_report_$(date +%Y%m%d).log"

cd "$CORTEX_DIR"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "📈 Cortex Weekly Report - Week of $(date +%Y-%m-%d)" | tee "$REPORT_LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$REPORT_LOG"
echo "" | tee -a "$REPORT_LOG"

# Count activity
CONTRACTS=0
EXECUTIONS=0
SIGNALS=0
MEMORIES=0

if [ -d "$CORTEX_HOME/contracts" ]; then
    CONTRACTS=$(find "$CORTEX_HOME/contracts" -type f -mtime -7 | wc -l | tr -d ' ')
fi

if [ -d "$CORTEX_HOME/execution_results" ]; then
    EXECUTIONS=$(find "$CORTEX_HOME/execution_results" -type f -mtime -7 | wc -l | tr -d ' ')
fi

if [ -d "$CORTEX_HOME/signals" ]; then
    SIGNALS=$(find "$CORTEX_HOME/signals" -type f -mtime -7 | wc -l | tr -d ' ')
fi

if [ -d "$CORTEX_HOME/memories" ]; then
    MEMORIES=$(find "$CORTEX_HOME/memories" -type f -mtime -7 | wc -l | tr -d ' ')
fi

echo "📊 Activity (Last 7 Days):" | tee -a "$REPORT_LOG"
echo "  Contracts Generated: $CONTRACTS" | tee -a "$REPORT_LOG"
echo "  Executions Completed: $EXECUTIONS" | tee -a "$REPORT_LOG"
echo "  Signals Detected: $SIGNALS" | tee -a "$REPORT_LOG"
echo "  Memories Captured: $MEMORIES" | tee -a "$REPORT_LOG"
echo "" | tee -a "$REPORT_LOG"

# Recent improvements
echo "🎯 Recent Improvements:" | tee -a "$REPORT_LOG"

VORTEX_CONFIG="/Users/jesse.kemp/Dev/Vortex/VortexV2/data/validation/production_config.json"
if [ -f "$VORTEX_CONFIG" ]; then
    echo "  VortexV2 Production Config:" | tee -a "$REPORT_LOG"
    MOD_TIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$VORTEX_CONFIG" 2>/dev/null || echo "Unknown")
    echo "    Last updated: $MOD_TIME" | tee -a "$REPORT_LOG"

    # Extract improvement percentages if available
    python3 << 'EOF' | tee -a "$REPORT_LOG"
import json
from pathlib import Path

config_file = Path("/Users/jesse.kemp/Dev/Vortex/VortexV2/data/validation/production_config.json")
if config_file.exists():
    try:
        config = json.loads(config_file.read_text())
        fields = config.get('fields', {})

        improvements = []
        for field_name, field_config in fields.items():
            if 'improvement_pct' in field_config:
                model = field_config.get('model', 'Unknown')
                improvement = field_config.get('improvement_pct', 0)
                improvements.append((field_name, model, improvement))

        if improvements:
            print("    Active Improvements:")
            for field, model, pct in sorted(improvements, key=lambda x: x[2], reverse=True):
                print(f"      {field}: {model} (+{pct:.1f}%)")
        else:
            print("    No improvement metrics found")
    except Exception as e:
        print(f"    Error reading config: {e}")
EOF
else
    echo "  VortexV2 config not found" | tee -a "$REPORT_LOG"
fi

echo "" | tee -a "$REPORT_LOG"

# Recent contracts
echo "📋 Recent Contracts:" | tee -a "$REPORT_LOG"
if [ -d "$CORTEX_HOME/contracts" ]; then
    RECENT_CONTRACTS=$(find "$CORTEX_HOME/contracts" -type f -mtime -7 -name "*.json" | sort -r | head -5)
    if [ -n "$RECENT_CONTRACTS" ]; then
        echo "$RECENT_CONTRACTS" | while read -r contract; do
            BASENAME=$(basename "$contract")
            CREATED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$contract" 2>/dev/null || echo "Unknown")
            echo "  - $BASENAME (created: $CREATED)" | tee -a "$REPORT_LOG"
        done
    else
        echo "  No contracts generated this week" | tee -a "$REPORT_LOG"
    fi
else
    echo "  Contracts directory not found" | tee -a "$REPORT_LOG"
fi

echo "" | tee -a "$REPORT_LOG"

# Recent executions
echo "⚡ Recent Executions:" | tee -a "$REPORT_LOG"
if [ -d "$CORTEX_HOME/execution_results" ]; then
    RECENT_EXECS=$(find "$CORTEX_HOME/execution_results" -type f -mtime -7 -name "*.json" | sort -r | head -5)
    if [ -n "$RECENT_EXECS" ]; then
        echo "$RECENT_EXECS" | while read -r exec; do
            BASENAME=$(basename "$exec")
            COMPLETED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$exec" 2>/dev/null || echo "Unknown")
            echo "  - $BASENAME (completed: $COMPLETED)" | tee -a "$REPORT_LOG"
        done
    else
        echo "  No executions completed this week" | tee -a "$REPORT_LOG"
    fi
else
    echo "  Execution results directory not found" | tee -a "$REPORT_LOG"
fi

echo "" | tee -a "$REPORT_LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$REPORT_LOG"
echo "✅ Weekly report complete. Full details in dashboard:" | tee -a "$REPORT_LOG"
echo "   ./launch_dashboard.sh" | tee -a "$REPORT_LOG"
echo "" | tee -a "$REPORT_LOG"
echo "📝 Report saved to: $REPORT_LOG" | tee -a "$REPORT_LOG"
