#!/bin/bash
# Verify iTerm2 profile configuration

echo "=== iTerm2 Profile Verification ==="
echo ""

# Check if iTerm is running
if pgrep -x "iTerm2" > /dev/null; then
    echo "⚠️  iTerm2 is RUNNING"
    echo "   Close and reopen iTerm2 to see profile changes"
else
    echo "ℹ️  iTerm2 is not running"
fi
echo ""

# Check dynamic profiles file
PROFILE_FILE="$HOME/Library/Application Support/iTerm2/DynamicProfiles/dev-monorepo.json"
if [ -f "$PROFILE_FILE" ]; then
    COUNT=$(python3 -c "import json; print(len(json.load(open('$PROFILE_FILE'))['Profiles']))" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "✅ Dynamic profiles file: $COUNT profiles"
    else
        echo "❌ Dynamic profiles file: INVALID JSON"
    fi
else
    echo "❌ Dynamic profiles file: NOT FOUND"
fi

# Check if JSON is valid
python3 -m json.tool "$PROFILE_FILE" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ JSON validation: PASSED"
else
    echo "❌ JSON validation: FAILED"
fi

# List profiles
echo ""
echo "Profiles in dynamic file:"
python3 -c "
import json
data = json.load(open('$PROFILE_FILE'))
for p in data['Profiles']:
    print(f\"  • {p['Name']:15} ({p['Guid']})\")
" 2>/dev/null

# Check static profiles
echo ""
echo "Static profiles in plist:"
if defaults read com.googlecode.iterm2 "New Bookmarks" 2>&1 | grep -q "does not exist"; then
    echo "  ✅ None (clean - using dynamic only)"
else
    COUNT=$(defaults read com.googlecode.iterm2 "New Bookmarks" | grep "Name =" | wc -l | tr -d ' ')
    echo "  ⚠️  Found $COUNT static profiles (should be 0)"
fi

# Check default profile
echo ""
DEFAULT_GUID=$(defaults read com.googlecode.iterm2 "Default Bookmark Guid" 2>/dev/null)
if [ -n "$DEFAULT_GUID" ]; then
    echo "✅ Default profile GUID: $DEFAULT_GUID"
else
    echo "⚠️  No default profile set"
fi

# Check keyboard shortcuts
echo ""
echo "Keyboard shortcuts:"
for i in 1 2 3 4 5; do
    HEX="0x3${i}-0x40000"
    if defaults read com.googlecode.iterm2 GlobalKeyMap 2>/dev/null | grep -q "$HEX"; then
        echo "  ✅ Ctrl+$i configured"
    else
        echo "  ❌ Ctrl+$i missing"
    fi
done

echo ""
echo "=== Troubleshooting ==="
echo ""
echo "If profiles don't appear in iTerm:"
echo "  1. Close iTerm2 completely (⌘Q)"
echo "  2. Open iTerm2 again"
echo "  3. Go to: Preferences → Profiles"
echo "  4. You should see: Opus, Sonnet, Cortex, VortexV2, AlphaArena"
echo ""
echo "If keyboard shortcuts don't work:"
echo "  1. Preferences → Keys → Key Bindings"
echo "  2. Look for Ctrl+1 through Ctrl+5"
echo "  3. Each should show: Action = 'New Tab with Profile'"
echo ""
echo "To restore from scratch:"
echo "  cd /Users/jesse.kemp/Dev/cortex/config-backups"
echo "  ./cleanup-iterm2-profiles.sh"
echo ""
