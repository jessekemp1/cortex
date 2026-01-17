#!/bin/bash
# Restore all development environment configurations
# Usage: ./restore-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR"

echo "🔄 Restoring development environment configurations..."
echo ""

# Restore iTerm2 profiles
echo "📦 Restoring iTerm2 profiles..."
mkdir -p ~/Library/Application\ Support/iTerm2/DynamicProfiles/
cp "$BACKUP_DIR/iterm2/dev-monorepo.json" \
   ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json
echo "✅ iTerm2 profiles restored"
echo "   → Profiles will load automatically"
echo "   → Set hotkeys: iTerm2 → Settings → Profiles → Keys"
echo ""

# Restore shell aliases
echo "📦 Restoring shell aliases..."
if ! grep -q "# Claude Session Management" ~/.zshrc 2>/dev/null; then
    echo "" >> ~/.zshrc
    cat "$BACKUP_DIR/shell/claude-aliases.sh" >> ~/.zshrc
    echo "✅ Shell aliases added to ~/.zshrc"
else
    echo "⚠️  Shell aliases already exist in ~/.zshrc (skipped)"
fi
echo ""

# Validate installations
echo "🔍 Validating installations..."

# Check iTerm2
if [ -d "/Applications/iTerm.app" ]; then
    echo "✅ iTerm2 installed"
else
    echo "⚠️  iTerm2 not found at /Applications/iTerm.app"
fi

# Check Claude CLI
if command -v claude &> /dev/null; then
    echo "✅ Claude CLI installed ($(claude --version))"
else
    echo "⚠️  Claude CLI not found (install from https://claude.com/claude-code)"
fi

echo ""
echo "✅ Restore complete!"
echo ""
echo "Next steps:"
echo "  1. Restart iTerm2 (or open Settings to see new profiles)"
echo "  2. Assign hotkeys: Settings → Profiles → Keys → Configure Hotkey Window"
echo "  3. Run 'source ~/.zshrc' to load shell aliases"
echo "  4. Test: 'claude-model' to verify aliases work"
echo ""
