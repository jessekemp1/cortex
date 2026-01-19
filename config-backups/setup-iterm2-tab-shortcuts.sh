#!/bin/bash
# Configure iTerm2 keyboard shortcuts to open profiles in new tabs
# Uses Ctrl+1-5 to open Opus, Sonnet, Cortex, VortexV2, AlphaArena in tabs

set -e

echo "⌨️  iTerm2 Tab Shortcuts Setup"
echo "=============================="
echo ""

# Check if iTerm2 is running
if pgrep -x "iTerm2" > /dev/null; then
    echo "⚠️  iTerm2 is running. Please close iTerm2 first."
    echo "   1. Save any work in your terminals"
    echo "   2. Quit iTerm2 (⌘Q)"
    echo "   3. Run this script again"
    exit 1
fi

echo "🔧 Configuring keyboard shortcuts..."
echo ""

# Profile GUIDs (must match dev-monorepo.json)
OPUS_GUID="claude-opus-main-001"
SONNET_GUID="claude-sonnet-main-002"
CORTEX_GUID="cortex-main-003"
VORTEX_GUID="vortex-main-004"
ARENA_GUID="alpha-arena-main-005"

# Configure keyboard shortcuts
# Action: "New Tab with Profile" = 0
# Ctrl key modifier = 262144
# Key codes: 1=18, 2=19, 3=20, 4=21, 5=23

# Create keyboard shortcuts array
/usr/libexec/PlistBuddy -c "Delete :GlobalKeyMap" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap dict" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true

# Ctrl+1 -> Opus (new tab)
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x31-0x40000 dict" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x31-0x40000:Action integer 0" ~/Library/Preferences/com.googlecode.iterm2.plist
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x31-0x40000:Text string $OPUS_GUID" ~/Library/Preferences/com.googlecode.iterm2.plist
echo "✅ Ctrl+1 -> Opus (new tab)"

# Ctrl+2 -> Sonnet (new tab)
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x32-0x40000 dict" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x32-0x40000:Action integer 0" ~/Library/Preferences/com.googlecode.iterm2.plist
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x32-0x40000:Text string $SONNET_GUID" ~/Library/Preferences/com.googlecode.iterm2.plist
echo "✅ Ctrl+2 -> Sonnet (new tab)"

# Ctrl+3 -> Cortex (new tab)
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x33-0x40000 dict" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x33-0x40000:Action integer 0" ~/Library/Preferences/com.googlecode.iterm2.plist
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x33-0x40000:Text string $CORTEX_GUID" ~/Library/Preferences/com.googlecode.iterm2.plist
echo "✅ Ctrl+3 -> Cortex (new tab)"

# Ctrl+4 -> VortexV2 (new tab)
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x34-0x40000 dict" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x34-0x40000:Action integer 0" ~/Library/Preferences/com.googlecode.iterm2.plist
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x34-0x40000:Text string $VORTEX_GUID" ~/Library/Preferences/com.googlecode.iterm2.plist
echo "✅ Ctrl+4 -> VortexV2 (new tab)"

# Ctrl+5 -> AlphaArena (new tab)
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x35-0x40000 dict" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x35-0x40000:Action integer 0" ~/Library/Preferences/com.googlecode.iterm2.plist
/usr/libexec/PlistBuddy -c "Add :GlobalKeyMap:0x35-0x40000:Text string $ARENA_GUID" ~/Library/Preferences/com.googlecode.iterm2.plist
echo "✅ Ctrl+5 -> AlphaArena (new tab)"

echo ""
echo "✅ Keyboard shortcuts configured!"
echo ""
echo "Next steps:"
echo "  1. Open iTerm2"
echo "  2. Press Ctrl+1 to open Opus in a new tab"
echo "  3. Press Ctrl+2 to open Sonnet in a new tab"
echo "  4. Press Ctrl+3 to open Cortex in a new tab"
echo "  5. Press Ctrl+4 to open VortexV2 in a new tab"
echo "  6. Press Ctrl+5 to open AlphaArena in a new tab"
echo ""
