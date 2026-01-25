#!/bin/bash
# Install Cortex Daily Automation
# Sets up LaunchAgent for automated daily scans at 8am
# Usage: ./install_automation.sh

set -e

CORTEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SOURCE="$CORTEX_DIR/automation/com.cortex.daily.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.cortex.daily.plist"
CORTEX_HOME="$HOME/.cortex"
LOG_DIR="$CORTEX_HOME/logs"

echo "🤖 Installing Cortex Daily Automation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check prerequisites
echo "✓ Checking prerequisites..."

# Ensure LaunchAgents directory exists
mkdir -p "$HOME/Library/LaunchAgents"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check that scripts exist
if [ ! -f "$CORTEX_DIR/daily_scan.sh" ]; then
    echo "❌ Error: daily_scan.sh not found"
    exit 1
fi

if [ ! -x "$CORTEX_DIR/daily_scan.sh" ]; then
    echo "  Making daily_scan.sh executable..."
    chmod +x "$CORTEX_DIR/daily_scan.sh"
fi

if [ ! -f "$PLIST_SOURCE" ]; then
    echo "❌ Error: LaunchAgent plist not found at $PLIST_SOURCE"
    exit 1
fi

echo "  ✓ Scripts are ready"
echo ""

# Unload if already loaded
if launchctl list | grep -q "com.cortex.daily"; then
    echo "⚠️  Automation already installed. Unloading..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist
echo "📄 Installing LaunchAgent..."
cp "$PLIST_SOURCE" "$PLIST_DEST"
echo "  ✓ Copied to $PLIST_DEST"
echo ""

# Load LaunchAgent
echo "🚀 Loading LaunchAgent..."
launchctl load "$PLIST_DEST"

# Verify
sleep 1
if launchctl list | grep -q "com.cortex.daily"; then
    echo "  ✓ LaunchAgent loaded successfully"
else
    echo "  ❌ LaunchAgent failed to load"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Cortex Daily Automation installed successfully!"
echo ""
echo "📅 Schedule: Daily at 8:00 AM"
echo "📝 Logs: $LOG_DIR/daily_scan.log"
echo "❌ Errors: $LOG_DIR/daily_scan_error.log"
echo ""
echo "🧪 Test it now:"
echo "   launchctl start com.cortex.daily"
echo ""
echo "📊 View logs:"
echo "   tail -f ~/.cortex/logs/daily_scan.log"
echo ""
echo "🛑 Uninstall:"
echo "   ./uninstall_automation.sh"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
