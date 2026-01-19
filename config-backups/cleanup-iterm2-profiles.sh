#!/bin/bash
# Clean up iTerm2 profiles - remove all static profiles and use only dynamic profiles
# This fixes the "huge folder setup" issue

set -e

echo "🧹 iTerm2 Profile Cleanup"
echo "=========================="
echo ""

# Check if iTerm2 is running
if pgrep -x "iTerm2" > /dev/null; then
    echo "⚠️  iTerm2 is running. Please close iTerm2 first."
    echo "   1. Save any work in your terminals"
    echo "   2. Quit iTerm2 (⌘Q)"
    echo "   3. Run this script again"
    exit 1
fi

# Backup current preferences
echo "📦 Backing up current preferences..."
cp ~/Library/Preferences/com.googlecode.iterm2.plist ~/Library/Preferences/com.googlecode.iterm2.plist.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created"
echo ""

# Remove all static profiles (keep only dynamic profiles)
echo "🗑️  Removing static profiles..."
defaults delete com.googlecode.iterm2 "New Bookmarks" 2>/dev/null && echo "✅ Removed static profiles" || echo "ℹ️  No static profiles to remove"
defaults delete com.googlecode.iterm2 "Default Bookmark Guid" 2>/dev/null && echo "✅ Cleared default bookmark" || echo "ℹ️  No default bookmark set"
echo ""

# Restore clean dynamic profiles
echo "📦 Restoring clean dynamic profiles..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/iterm2/dev-monorepo.json" ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json
echo "✅ Clean profiles restored"
echo ""

# Verify
echo "🔍 Verification:"
PROFILE_COUNT=$(cat ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json | python3 -c "import sys, json; print(len(json.load(sys.stdin)['Profiles']))")
echo "   Dynamic profiles: $PROFILE_COUNT"
echo ""

echo "✅ Cleanup complete!"
echo ""

# Configure tab shortcuts
echo "🔧 Configuring keyboard shortcuts for tabs..."
"$SCRIPT_DIR/setup-iterm2-tab-shortcuts.sh"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open iTerm2"
echo "  2. Press Ctrl+1 to open Opus in a new tab"
echo "  3. Press Ctrl+2 to open Sonnet in a new tab"
echo "  4. Press Ctrl+3 to open Cortex in a new tab"
echo "  5. Press Ctrl+4 to open VortexV2 in a new tab"
echo "  6. Press Ctrl+5 to open AlphaArena in a new tab"
echo ""
