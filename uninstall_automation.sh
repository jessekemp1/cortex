#!/bin/bash
# Uninstall Cortex Daily Automation
# Removes LaunchAgent for automated daily scans
# Usage: ./uninstall_automation.sh

set -e

PLIST_DEST="$HOME/Library/LaunchAgents/com.cortex.daily.plist"

echo "🛑 Uninstalling Cortex Daily Automation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if installed
if [ ! -f "$PLIST_DEST" ]; then
    echo "⚠️  Automation not installed (plist not found)"
    exit 0
fi

# Unload if loaded
if launchctl list | grep -q "com.cortex.daily"; then
    echo "📤 Unloading LaunchAgent..."
    launchctl unload "$PLIST_DEST"
    echo "  ✓ Unloaded"
else
    echo "⚠️  LaunchAgent not currently loaded"
fi

# Remove plist
echo "🗑️  Removing LaunchAgent file..."
rm "$PLIST_DEST"
echo "  ✓ Removed"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Cortex Daily Automation uninstalled"
echo ""
echo "💡 You can still run manual scans:"
echo "   ./daily_scan.sh"
echo ""
echo "🔄 Re-install anytime:"
echo "   ./install_automation.sh"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
