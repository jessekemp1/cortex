#!/bin/bash
# =============================================================================
# Cortex Fresh Install Script
# =============================================================================
# Usage: ./install.sh
#
# Prerequisites: python3.11, node, git, brew (macOS)
#
# This script:
#   1. Creates venv and installs all Python dependencies
#   2. Sets up ~/.cortex/ state directories
#   3. Generates .env from template (prompts for API key)
#   4. Installs Node deps for the site dashboard
#   5. Templates and installs LaunchAgents with correct paths
#   6. Creates python3 -> python3.11 symlink if needed
#   7. Runs self-audit to verify
# =============================================================================

set -euo pipefail

# Detect paths dynamically
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$SCRIPT_DIR"
DEV_DIR="$(dirname "$CORTEX_DIR")"
HOME_DIR="$HOME"
CORTEX_STATE="$HOME_DIR/.cortex"
VENV="$CORTEX_DIR/.venv"
PYTHON_BIN="python3.11"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# ─── Step 0: Prerequisites ─────────────────────────────────────────────
log "Checking prerequisites..."

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3.11 not found. Install: brew install python@3.11"
command -v git >/dev/null 2>&1 || fail "git not found"
command -v node >/dev/null 2>&1 || warn "node not found — site dashboard will not work"

PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ "$PYTHON_VERSION" != "3.11" ]] && [[ "$PYTHON_VERSION" != "3.12" ]]; then
    fail "Python 3.11+ required, got $PYTHON_VERSION"
fi
log "Python $PYTHON_VERSION OK"

# ─── Step 1: Virtual environment ───────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    log "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV"
else
    log "Virtual environment already exists"
fi

log "Installing Python dependencies..."
"$VENV/bin/pip" install --upgrade pip setuptools wheel -q
"$VENV/bin/pip" install -e ".[all]" -q
"$VENV/bin/pip" install chromadb pytest pytest-timeout -q 2>/dev/null || warn "chromadb install failed (optional)"
log "Python packages installed"

# ─── Step 2: State directories ─────────────────────────────────────────
log "Creating state directories..."
mkdir -p "$CORTEX_STATE"/{logs,metrics,batch,secrets,prompts,flywheel,session_metrics,pid_sessions}
chmod 700 "$CORTEX_STATE"

# ─── Step 3: Environment files ─────────────────────────────────────────
if [ ! -f "$CORTEX_DIR/.env" ]; then
    if [ -f "$CORTEX_DIR/.env.template" ]; then
        cp "$CORTEX_DIR/.env.template" "$CORTEX_DIR/.env"
    else
        cat > "$CORTEX_DIR/.env" <<ENVEOF
# Cortex Environment Configuration
CORTEX_ROOT_DIR=/path/to/your/projects
CORTEX_STATE_DIR=$CORTEX_STATE

# Required: Anthropic API key
# ANTHROPIC_API_KEY=sk-ant-...

# Optional: Multi-provider keys
# OPENAI_API_KEY=
# GROQ_API_KEY=
# DEEPSEEK_API_KEY=
ENVEOF
    fi
    log ".env created"
else
    log ".env already exists"
fi

# Prompt for ANTHROPIC_API_KEY
if ! grep -q "^ANTHROPIC_API_KEY=sk-" "$CORTEX_DIR/.env" 2>/dev/null && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo ""
    echo "  Anthropic API key required for intelligence features."
    echo "  Get yours at: https://console.anthropic.com/settings/keys"
    while true; do
        read -rp "  Enter ANTHROPIC_API_KEY (sk-ant-...): " INPUT_KEY
        if [[ "$INPUT_KEY" == sk-* ]]; then
            sed -i '' "s|^# ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$INPUT_KEY|" "$CORTEX_DIR/.env"
            export ANTHROPIC_API_KEY="$INPUT_KEY"
            log "ANTHROPIC_API_KEY saved"
            break
        else
            warn "Key must start with 'sk-'. Try again (or press Ctrl+C to skip)."
        fi
    done
fi

# Prompt for CORTEX_ROOT_DIR
if grep -q "CORTEX_ROOT_DIR=/path/to/your/projects" "$CORTEX_DIR/.env" 2>/dev/null; then
    echo ""
    read -rp "  Enter your projects root directory (e.g. ~/Dev): " INPUT_ROOT
    INPUT_ROOT="${INPUT_ROOT/#\~/$HOME}"
    INPUT_ROOT="${INPUT_ROOT:-$DEV_DIR}"
    sed -i '' "s|CORTEX_ROOT_DIR=.*|CORTEX_ROOT_DIR=$INPUT_ROOT|" "$CORTEX_DIR/.env"
    log "CORTEX_ROOT_DIR set to $INPUT_ROOT"
fi

# Store API key for batch daemons if available
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    mkdir -p "$CORTEX_STATE/secrets"
    echo "$ANTHROPIC_API_KEY" > "$CORTEX_STATE/secrets/anthropic_batch_key"
    chmod 600 "$CORTEX_STATE/secrets/anthropic_batch_key"
    log "Batch API key stored"
fi

# ─── Step 4: python3 symlink ──────────────────────────────────────────
PYTHON311_PATH=$(command -v python3.11)
if [ -n "$PYTHON311_PATH" ]; then
    mkdir -p "$HOME_DIR/.local/bin"
    ln -sf "$PYTHON311_PATH" "$HOME_DIR/.local/bin/python3"
    ln -sf "$PYTHON311_PATH" "$HOME_DIR/.local/bin/python"
    log "python3 -> python3.11 symlink created in ~/.local/bin/"
fi

# ─── Step 5: Site dashboard ───────────────────────────────────────────
if [ -f "$CORTEX_DIR/site/package.json" ] && command -v npm >/dev/null 2>&1; then
    if [ ! -d "$CORTEX_DIR/site/node_modules" ]; then
        log "Installing site dashboard dependencies..."
        cd "$CORTEX_DIR/site" && npm install --silent 2>/dev/null
        cd "$CORTEX_DIR"
    else
        log "Site dashboard node_modules already present"
    fi
fi

# ─── Step 6: LaunchAgents (macOS only) ────────────────────────────────
if [ "$(uname)" = "Darwin" ]; then
    log "Installing LaunchAgents..."
    AGENTS_DIR="$HOME_DIR/Library/LaunchAgents"
    mkdir -p "$AGENTS_DIR"

    # Template function: replaces path tokens in plist files
    install_plist() {
        local src="$1"
        local name=$(basename "$src")
        local dest="$AGENTS_DIR/$name"

        if [ -f "$dest" ]; then
            return 0  # Already installed
        fi

        cp "$src" "$dest"
        # Fix all known path patterns
        sed -i '' \
            -e "s|/Users/jesse.kemp/Dev|$DEV_DIR|g" \
            -e "s|/Users/jesse/Dev|$DEV_DIR|g" \
            -e "s|/Users/jesse.kemp|$HOME_DIR|g" \
            -e "s|/Users/jesse/dev/venv/|$VENV/|g" \
            -e "s|/Users/jesse/dev/cortex/venv/|$VENV/|g" \
            -e "s|alpha_arena/venv/|alpha_arena/.venv/|g" \
            -e "s|Vortex/backend/venv/|Vortex/backend/.venv/|g" \
            "$dest"
        echo "  Installed: $name"
    }

    # Install from batch/automation/ and repo root plists
    for plist in "$CORTEX_DIR"/batch/automation/*.plist "$CORTEX_DIR"/*.plist; do
        [ -f "$plist" ] && install_plist "$plist"
    done

    log "LaunchAgents installed (load with: launchctl load ~/Library/LaunchAgents/com.cortex.*.plist)"
fi

# ─── Step 7: Fix hooks REPO_ROOT ─────────────────────────────────────
HOOKS_DIR="$DEV_DIR/.claude/hooks"
if [ -d "$HOOKS_DIR" ]; then
    for hook in "$HOOKS_DIR"/*.py; do
        if grep -q 'REPO_ROOT.*=.*"/Users/' "$hook" 2>/dev/null; then
            sed -i '' "s|REPO_ROOT.*=.*/Users/[^\"]*\"|REPO_ROOT = \"$DEV_DIR\"|g" "$hook"
        fi
    done
    log "Claude Code hooks updated with correct REPO_ROOT"
fi

# ─── Step 8: Verify ──────────────────────────────────────────────────
log "Running verification..."

echo ""
echo "╔════════════════════════════════════════╗"
echo "║      CORTEX INSTALL VERIFICATION       ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check venv
"$VENV/bin/python" -c "from cli import main; print('  ✅ cortex package importable')" 2>/dev/null || echo "  ❌ cortex package import failed"

# Check CLI
"$VENV/bin/python" -m cli health 2>&1 | grep -q "All Systems Operational" && echo "  ✅ cortex health: all systems operational" || echo "  ⚠️  cortex health: some systems degraded"

# Check state dir
[ -d "$CORTEX_STATE/logs" ] && echo "  ✅ ~/.cortex/ state directory ready" || echo "  ❌ ~/.cortex/ state directory missing"

# Check .env
[ -f "$CORTEX_DIR/.env" ] && echo "  ✅ .env file present" || echo "  ❌ .env file missing"
grep -q "ANTHROPIC_API_KEY=sk-" "$CORTEX_DIR/.env" 2>/dev/null && echo "  ✅ ANTHROPIC_API_KEY configured" || echo "  ⚠️  ANTHROPIC_API_KEY not set in .env"

# Check site
[ -d "$CORTEX_DIR/site/node_modules" ] && echo "  ✅ Site dashboard deps installed" || echo "  ⚠️  Site dashboard not set up (optional)"

echo ""
log "Install complete. Next steps:"
STEP=1
if ! grep -q "ANTHROPIC_API_KEY=sk-" "$CORTEX_DIR/.env" 2>/dev/null; then
    echo "  $STEP. Edit $CORTEX_DIR/.env and set ANTHROPIC_API_KEY"
    STEP=$((STEP + 1))
fi
echo "  $STEP. Activate: source $VENV/bin/activate"
STEP=$((STEP + 1))
echo "  $STEP. Run: cortex status"
STEP=$((STEP + 1))
echo "  $STEP. Load agents: launchctl load ~/Library/LaunchAgents/com.cortex.*.plist"
