#!/bin/bash
# Sync current configurations to backup directory
# Usage: ./sync-configs.sh [--commit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR"
COMMIT=false

if [ "$1" == "--commit" ]; then
    COMMIT=true
fi

echo "🔄 Syncing configurations to backup..."
echo ""

# Backup iTerm2 profiles
echo "📦 Backing up iTerm2 profiles..."
if [ -f ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json ]; then
    cp ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json \
       "$BACKUP_DIR/iterm2/dev-monorepo.json"
    echo "✅ iTerm2 profiles backed up"
else
    echo "⚠️  iTerm2 profiles not found"
fi
echo ""

# Backup shell aliases
echo "📦 Backing up shell aliases..."
if grep -q "# Claude" ~/.zshrc 2>/dev/null; then
    grep -A 20 "# Claude" ~/.zshrc > "$BACKUP_DIR/shell/claude-aliases.sh"
    echo "✅ Shell aliases backed up"
else
    echo "⚠️  No Claude aliases found in ~/.zshrc"
fi
echo ""

# Backup Claude settings
echo "📦 Backing up Claude settings..."
# Try multiple possible locations
CLAUDE_SETTINGS_FOUND=false
for path in ~/.claude/settings.json ~/.config/claude/settings.json ~/Library/Application\ Support/Claude/settings.json; do
    if [ -f "$path" ]; then
        cp "$path" "$BACKUP_DIR/claude/settings.json"
        echo "✅ Claude settings backed up from $path"
        CLAUDE_SETTINGS_FOUND=true
        break
    fi
done

if [ "$CLAUDE_SETTINGS_FOUND" = false ]; then
    echo "⚠️  Claude settings not found in standard locations"
fi
echo ""

# Show diff
echo "📊 Changes:"
cd "$BACKUP_DIR"
git diff --stat 2>/dev/null || echo "Not in git repository"
echo ""

# Commit if requested
if [ "$COMMIT" = true ]; then
    echo "💾 Committing changes..."
    git add .
    git commit -m "chore: Sync environment config backups [$(date +%Y-%m-%d)]" || echo "No changes to commit"
    echo "✅ Changes committed"
fi

echo ""
echo "✅ Sync complete!"
echo ""
echo "Files backed up:"
echo "  → $BACKUP_DIR/iterm2/dev-monorepo.json"
echo "  → $BACKUP_DIR/shell/claude-aliases.sh"
echo "  → $BACKUP_DIR/claude/settings.json (if found)"
echo ""

if [ "$COMMIT" = false ]; then
    echo "💡 Tip: Run with --commit flag to auto-commit changes"
fi
