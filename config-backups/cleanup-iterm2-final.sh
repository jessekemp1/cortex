#!/bin/bash
# Final iTerm2 cleanup - removes ONLY the duplicate profiles, keeps Terminal default

set -e

echo "🧹 iTerm2 Final Cleanup - Remove Duplicate Profiles"
echo "===================================================="
echo ""

# Check if iTerm2 is running
if pgrep -x "iTerm2" > /dev/null; then
    echo "⚠️  iTerm2 is running. Please close iTerm2 first."
    echo "   1. Save any work"
    echo "   2. Quit iTerm2 (⌘Q)"
    echo "   3. Run this script again"
    exit 1
fi

# Backup
echo "📦 Creating backup..."
cp ~/Library/Preferences/com.googlecode.iterm2.plist ~/Library/Preferences/com.googlecode.iterm2.plist.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created"
echo ""

# Get the number of profiles
PROFILE_COUNT=$(/usr/libexec/PlistBuddy -c "Print :New\ Bookmarks" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null | grep -c "Dict {" || echo "0")
echo "📊 Found $PROFILE_COUNT static profiles"
echo ""

# Remove profiles by name (keep only Terminal, delete duplicates of dynamic profiles)
echo "🗑️  Removing duplicate profiles..."

PROFILES_TO_REMOVE=("Opus" "Sonnet" "Cortex" "VortexV2" "AlphaArena")

for i in $(seq $((PROFILE_COUNT - 1)) -1 0); do
    PROFILE_NAME=$(/usr/libexec/PlistBuddy -c "Print :New\ Bookmarks:$i:Name" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || echo "")
    
    if [[ " ${PROFILES_TO_REMOVE[@]} " =~ " ${PROFILE_NAME} " ]]; then
        echo "   Removing: $PROFILE_NAME (index $i)"
        /usr/libexec/PlistBuddy -c "Delete :New\ Bookmarks:$i" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null || true
    fi
done

echo "✅ Duplicate profiles removed"
echo ""

# Verify
REMAINING=$(/usr/libexec/PlistBuddy -c "Print :New\ Bookmarks" ~/Library/Preferences/com.googlecode.iterm2.plist 2>/dev/null | grep "Name =" | sed 's/.*= //')
echo "📊 Remaining static profiles:"
echo "$REMAINING"
echo ""

echo "✅ Cleanup complete!"
echo ""
echo "Next steps:"
echo "  1. Open iTerm2"
echo "  2. Verify profiles - should see Opus, Sonnet, Cortex, VortexV2, AlphaArena (from dynamic)"
echo "  3. Press Ctrl+1-5 to test hotkeys"
echo ""
