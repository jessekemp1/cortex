#!/bin/bash
# Install git hooks for automatic calibration tracking
# This makes calibration nearly effortless

set -e

CORTEX_DIR="$HOME/Dev/cortex"
HOOK_DIR=".git/hooks"

echo "🔧 Installing Cortex Calibration Git Hooks..."
echo ""

# Check if we're in a git repo
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    echo "Run this from the root of your git project (VortexV2, Cortex, etc.)"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p "$HOOK_DIR"

# 1. PRE-COMMIT HOOK - Auto-start tracking
echo "📝 Installing pre-commit hook..."
cat > "$HOOK_DIR/pre-commit" << 'HOOK_EOF'
#!/bin/bash
# Cortex Auto-Calibration: Pre-Commit Hook
# Automatically starts task tracking if not already active

TASK_FILE="$HOME/.claude/portfolio/current_task.json"
CORTEX_DIR="$HOME/Dev/cortex"

# Check if task already active
if [ -f "$TASK_FILE" ]; then
    # Task already started, do nothing
    exit 0
fi

# Only prompt if interactive (not during automated commits)
if [ -t 0 ]; then
    echo ""
    echo "🤖 Cortex: No active task detected"
    echo ""
    read -p "Start calibration tracking? (Y/n) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        cd "$CORTEX_DIR"
        python3 auto_calibration.py
        echo ""
    fi
fi

exit 0
HOOK_EOF

chmod +x "$HOOK_DIR/pre-commit"
echo "   ✅ pre-commit hook installed"

# 2. POST-COMMIT HOOK - Suggest completion
echo "📝 Installing post-commit hook..."
cat > "$HOOK_DIR/post-commit" << 'HOOK_EOF'
#!/bin/bash
# Cortex Auto-Calibration: Post-Commit Hook
# Reminds to complete task tracking

TASK_FILE="$HOME/.claude/portfolio/current_task.json"

# Check if task is active
if [ -f "$TASK_FILE" ]; then
    echo ""
    echo "📊 Cortex: Task tracked. Complete with:"
    echo "   ./cal done <minutes>     # Quick complete"
    echo "   ./cal auto-done          # Auto from commit"
    echo ""
fi

exit 0
HOOK_EOF

chmod +x "$HOOK_DIR/post-commit"
echo "   ✅ post-commit hook installed"

# 3. PREPARE-COMMIT-MSG HOOK - Optional reminder in commit message
echo "📝 Installing prepare-commit-msg hook..."
cat > "$HOOK_DIR/prepare-commit-msg" << 'HOOK_EOF'
#!/bin/bash
# Cortex Auto-Calibration: Prepare Commit Message Hook
# Adds calibration reminder to commit message template

TASK_FILE="$HOME/.claude/portfolio/current_task.json"
COMMIT_MSG_FILE=$1

# Only add reminder for regular commits (not merge, squash, etc.)
if [ -f "$TASK_FILE" ] && [ ! -f ".git/MERGE_HEAD" ]; then
    # Add reminder comment at bottom of commit message
    echo "" >> "$COMMIT_MSG_FILE"
    echo "# 📊 Cortex: Task tracked - remember to complete with ./cal done" >> "$COMMIT_MSG_FILE"
fi

exit 0
HOOK_EOF

chmod +x "$HOOK_DIR/prepare-commit-msg"
echo "   ✅ prepare-commit-msg hook installed"

echo ""
echo "✅ Git hooks installed successfully!"
echo ""
echo "📋 What happens now:"
echo ""
echo "BEFORE COMMIT:"
echo "  - If no task active → prompts to start calibration"
echo "  - Auto-detects files, project, estimates time"
echo "  - One-click to accept defaults"
echo ""
echo "DURING COMMIT:"
echo "  - Adds reminder to commit message template"
echo ""
echo "AFTER COMMIT:"
echo "  - Reminds to complete tracking"
echo "  - Shows quick completion commands"
echo ""
echo "🎯 Result: Near-zero friction calibration!"
echo ""
echo "Test it:"
echo "  1. Make a change: echo '# test' >> README.md"
echo "  2. Try to commit: git add . && git commit -m 'test'"
echo "  3. Watch auto-calibration prompt appear!"
echo ""
