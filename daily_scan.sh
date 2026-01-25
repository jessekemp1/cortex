#!/bin/bash
# Cortex Daily Morning Scan
# Scans for opportunities, checks health, and surfaces high-priority signals
# Usage: ./daily_scan.sh

set -e

CORTEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORTEX_HOME="$HOME/.cortex"
LOG_DIR="$CORTEX_HOME/logs"
SCAN_LOG="$LOG_DIR/daily_scan.log"

cd "$CORTEX_DIR"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "🌅 Cortex Daily Scan - $(date)" | tee -a "$SCAN_LOG"
echo "" | tee -a "$SCAN_LOG"

# System health check
echo "📊 System Health:" | tee -a "$SCAN_LOG"
./cortex_mvp health 2>&1 | tee -a "$SCAN_LOG"
echo "" | tee -a "$SCAN_LOG"

# Scan for signals
echo "🔍 Scanning for new opportunities..." | tee -a "$SCAN_LOG"
./cortex_mvp scan 2>&1 | tee -a "$SCAN_LOG"
echo "" | tee -a "$SCAN_LOG"

# Show high-value signals
echo "🎯 High-Priority Signals:" | tee -a "$SCAN_LOG"
python3 << 'EOF' | tee -a "$SCAN_LOG"
import json
from pathlib import Path
import sys

scan_file = Path.home() / '.cortex' / 'latest_scan.json'
if scan_file.exists():
    try:
        data = json.loads(scan_file.read_text())
        signals = data.get('signals', [])

        critical = [s for s in signals if s.get('severity') == 'critical']
        high = [s for s in signals if s.get('severity') == 'high']

        if not critical and not high:
            print("  ✅ No critical or high-priority signals detected")
        else:
            for s in critical:
                print(f"  🔴 CRITICAL: {s.get('title', 'Unknown')}")
                print(f"     Impact: {s.get('estimated_impact', 'Unknown')}")
                print(f"     ID: {s.get('id', 'Unknown')}")
                print()

            for s in high:
                print(f"  🟡 HIGH: {s.get('title', 'Unknown')}")
                print(f"     Impact: {s.get('estimated_impact', 'Unknown')}")
                print(f"     ID: {s.get('id', 'Unknown')}")
                print()

        # Summary
        by_severity = data.get('by_severity', {})
        total = data.get('count', 0)
        print(f"\n📈 Total Signals: {total}")
        print(f"   Critical: {by_severity.get('critical', 0)}")
        print(f"   High: {by_severity.get('high', 0)}")
        print(f"   Medium: {by_severity.get('medium', 0)}")
        print(f"   Low: {by_severity.get('low', 0)}")

    except Exception as e:
        print(f"  ⚠️  Error reading scan data: {e}", file=sys.stderr)
else:
    print("  ⚠️  No scan data found. Run './cortex_mvp scan' first.")
EOF

echo "" | tee -a "$SCAN_LOG"
echo "✅ Daily scan complete. Review signals in dashboard:" | tee -a "$SCAN_LOG"
echo "   ./launch_dashboard.sh" | tee -a "$SCAN_LOG"
echo "" | tee -a "$SCAN_LOG"
echo "📝 Log saved to: $SCAN_LOG" | tee -a "$SCAN_LOG"
