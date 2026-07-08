#!/bin/bash
# =============================================================================
# Cortex Install Script
# =============================================================================
# Usage: ./install.sh [--full]
#
#   --full    Also install optional analytics + orchestration packages
#             (xgboost, shap, openai, litellm). Default: core only.
#
# Prerequisites: Python 3.11+, git. Homebrew auto-offered if Python missing.
# =============================================================================

set -euo pipefail

# ─── Flags ────────────────────────────────────────────────────────────────────
FULL_INSTALL=false
for arg in "$@"; do
    case "$arg" in
        --full) FULL_INSTALL=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$SCRIPT_DIR"
DEV_DIR="$(dirname "$CORTEX_DIR")"
HOME_DIR="$HOME"
CORTEX_STATE="$HOME_DIR/.cortex"
VENV="$CORTEX_DIR/.venv"
LOCAL_BIN="$HOME_DIR/.local/bin"
PYTHON_BIN=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[x]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[i]${NC} $1"; }

# ─── Step 0: Prerequisites ────────────────────────────────────────────────────
log "Checking prerequisites..."

# Find Python 3.11+ — accept any version >= 3.11
for py in python3.13 python3.12 python3.11; do
    if command -v "$py" >/dev/null 2>&1; then
        PYTHON_BIN="$py"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    warn "Python 3.11+ not found."
    if command -v brew >/dev/null 2>&1; then
        INSTALL_PY="Y"
        [ -t 0 ] && { read -rp "  Install Python 3.11 via Homebrew now? [Y/n]: " INSTALL_PY || true; }
        if [[ "$INSTALL_PY" =~ ^[Yy] ]]; then
            brew install python@3.11
            PYTHON_BIN="python3.11"
        else
            fail "Python 3.11+ required. Run: brew install python@3.11"
        fi
    else
        fail "Python 3.11+ not found and Homebrew is not installed.\nInstall Homebrew first:\n  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\nThen re-run this script."
    fi
fi

PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MINOR=$("$PYTHON_BIN" -c "import sys; print(sys.version_info.minor)")
if [[ "$PYTHON_MINOR" -lt 11 ]]; then
    fail "Python 3.11+ required, got $PYTHON_VERSION"
fi
log "Python $PYTHON_VERSION OK"

command -v git >/dev/null 2>&1 || fail "git not found. Install via Xcode CLT: xcode-select --install"
command -v node >/dev/null 2>&1 || warn "node not found — site dashboard will not work (optional)"

# ─── Step 1: Virtual environment ─────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    log "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV"
else
    log "Virtual environment already exists"
fi

log "Installing Python dependencies..."
"$VENV/bin/pip" install --upgrade pip setuptools wheel -q

PIP_LOG=$(mktemp)
if [ "$FULL_INSTALL" = true ]; then
    info "Full install: adding analytics + orchestration packages (this takes a few minutes)..."
    if ! "$VENV/bin/pip" install -e ".[all,server,dev]" 2>"$PIP_LOG"; then
        warn "Some optional packages failed — core install still works:"
        grep "^ERROR" "$PIP_LOG" | head -5 || true
    fi
else
    # Default install includes [server] (FastAPI bridge) and [dev] (pytest)
    # so a fresh-clone user can run `cortex briefing`, the bridge, and the
    # test suite the README badge advertises without a separate pip step.
    if ! "$VENV/bin/pip" install -e ".[server,dev]" 2>"$PIP_LOG"; then
        cat "$PIP_LOG"
        rm -f "$PIP_LOG"
        fail "Core package install failed. See errors above."
    fi
fi
rm -f "$PIP_LOG"

"$VENV/bin/pip" install chromadb -q 2>/dev/null || warn "chromadb install failed (optional vector store)"
log "Python packages installed"

# ─── Step 2: State directories ───────────────────────────────────────────────
log "Creating state directories..."
mkdir -p "$CORTEX_STATE"/{logs,metrics,batch,secrets,prompts,flywheel,session_metrics,pid_sessions}
chmod 700 "$CORTEX_STATE"

# ─── Step 3: Environment configuration ───────────────────────────────────────
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

# Prompt for ANTHROPIC_API_KEY — skip only if a real key (>20 chars) is already present
_key_is_real() {
    local key="$1"
    [[ "$key" == sk-* ]] && [ "${#key}" -gt 20 ]
}

ENV_FILE_KEY=$(grep -E "^ANTHROPIC_API_KEY=sk-" "$CORTEX_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
if _key_is_real "${ENV_FILE_KEY:-}" || _key_is_real "${ANTHROPIC_API_KEY:-}"; then
    log "ANTHROPIC_API_KEY already configured"
elif [ ! -t 0 ]; then
    warn "Non-interactive install: set ANTHROPIC_API_KEY in $CORTEX_DIR/.env before running cortex"
else
    echo ""
    echo "  Anthropic API key required for intelligence features."
    echo "  Get yours at: https://console.anthropic.com/settings/keys"
    while true; do
        read -rp "  Enter ANTHROPIC_API_KEY (sk-ant-...): " INPUT_KEY || true
        if _key_is_real "${INPUT_KEY:-}"; then
            sed -i '' "s|^# ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$INPUT_KEY|" "$CORTEX_DIR/.env"
            sed -i '' "s|^ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY_HERE|ANTHROPIC_API_KEY=$INPUT_KEY|" "$CORTEX_DIR/.env"
            export ANTHROPIC_API_KEY="$INPUT_KEY"
            log "ANTHROPIC_API_KEY saved"
            break
        else
            warn "Key must start with 'sk-' and be a valid length. Try again (or Ctrl+C to skip)."
        fi
    done
fi

# Prompt for CORTEX_ROOT_DIR — show actual default so user can just hit Enter
INPUT_ROOT=""
if grep -q "CORTEX_ROOT_DIR=/path/to/your/projects" "$CORTEX_DIR/.env" 2>/dev/null; then
    echo ""
    INPUT_ROOT=""
    [ -t 0 ] && { read -rp "  Projects root directory [${DEV_DIR}]: " INPUT_ROOT || true; }
    INPUT_ROOT="${INPUT_ROOT/#\~/$HOME}"
    INPUT_ROOT="${INPUT_ROOT:-$DEV_DIR}"
    sed -i '' "s|CORTEX_ROOT_DIR=.*|CORTEX_ROOT_DIR=$INPUT_ROOT|" "$CORTEX_DIR/.env"
    log "CORTEX_ROOT_DIR set to $INPUT_ROOT"
else
    INPUT_ROOT=$(grep "^CORTEX_ROOT_DIR=" "$CORTEX_DIR/.env" 2>/dev/null | cut -d= -f2 || echo "$DEV_DIR")
fi

# Store API key for batch daemons
ACTIVE_KEY="${ANTHROPIC_API_KEY:-$ENV_FILE_KEY}"
if [ -n "${ACTIVE_KEY:-}" ]; then
    mkdir -p "$CORTEX_STATE/secrets"
    echo "$ACTIVE_KEY" > "$CORTEX_STATE/secrets/anthropic_batch_key"
    chmod 600 "$CORTEX_STATE/secrets/anthropic_batch_key"
fi

# ─── Step 4: PATH — cortex entrypoint always available ───────────────────────
mkdir -p "$LOCAL_BIN"
ln -sf "$VENV/bin/cortex" "$LOCAL_BIN/cortex"
ln -sf "$VENV/bin/cx" "$LOCAL_BIN/cx" 2>/dev/null || true
PYTHON311_PATH=$(command -v "$PYTHON_BIN" 2>/dev/null || true)
if [ -n "$PYTHON311_PATH" ]; then
    ln -sf "$PYTHON311_PATH" "$LOCAL_BIN/python3"
    ln -sf "$PYTHON311_PATH" "$LOCAL_BIN/python"
fi
log "cortex linked to ~/.local/bin/cortex"

# Add ~/.local/bin to PATH in shell profile if not already there
PROFILE_UPDATED=false
for profile in "$HOME_DIR/.zprofile" "$HOME_DIR/.zshrc" "$HOME_DIR/.bash_profile" "$HOME_DIR/.bashrc"; do
    if [ -f "$profile" ] && ! grep -q '\.local/bin' "$profile" 2>/dev/null; then
        echo '' >> "$profile"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$profile"
        log "Added ~/.local/bin to PATH in $(basename "$profile")"
        PROFILE_UPDATED=true
        break
    fi
done
export PATH="$LOCAL_BIN:$PATH"

# ─── Step 5: Site dashboard ──────────────────────────────────────────────────
if [ -f "$CORTEX_DIR/site/package.json" ] && command -v npm >/dev/null 2>&1; then
    if [ ! -d "$CORTEX_DIR/site/node_modules" ]; then
        log "Installing site dashboard dependencies..."
        cd "$CORTEX_DIR/site" && npm install --silent 2>/dev/null
        cd "$CORTEX_DIR"
    else
        log "Site dashboard node_modules already present"
    fi
fi

# ─── Step 6: LaunchAgents (macOS + Linux systemd) ───────────────────────────
# Delegated to scripts/install_launchagents.sh — the single source of truth:
# it substitutes paths, actually loads the agents (launchctl bootstrap /
# systemctl enable), and covers the curated plist set including the
# com.cortex.bridge keep-alive that supervises the :8765 bridge.
echo ""
info "Background agents supervise the bridge and run nightly analysis/batch jobs."
info "They are user-level LaunchAgents (macOS) or systemd user units (Linux)."
INSTALL_AGENTS="Y"
[ -t 0 ] && { read -rp "  Install background agents? [Y/n]: " INSTALL_AGENTS || true; }
if [[ "$INSTALL_AGENTS" =~ ^[Yy] ]]; then
    if bash "$SCRIPT_DIR/scripts/install_launchagents.sh"; then
        log "Background agents installed and loaded"
    else
        warn "install_launchagents.sh reported errors (non-fatal); see output above"
    fi
else
    log "Skipped background agents"
fi

# ─── Step 7: Fix Claude Code hooks REPO_ROOT (if present) ───────────────────
HOOKS_DIR="$DEV_DIR/.claude/hooks"
if [ -d "$HOOKS_DIR" ]; then
    for hook in "$HOOKS_DIR"/*.py; do
        if grep -q 'REPO_ROOT.*=.*"/Users/' "$hook" 2>/dev/null; then
            sed -i '' "s|REPO_ROOT.*=.*/Users/[^\"]*\"|REPO_ROOT = \"$DEV_DIR\"|g" "$hook"
        fi
    done
    log "Claude Code hooks updated with correct REPO_ROOT"
fi

# ─── Step 7.5: Wire session briefing into workspace Claude settings ─────────
# JSON-merge (never clobbers existing hooks; idempotent). The hook command is
# existence-guarded, so it silently no-ops on checkouts that lack the script.
if command -v python3 >/dev/null 2>&1; then
    python3 "$SCRIPT_DIR/scripts/install_session_hook.py" "$DEV_DIR" \
        && log "Session briefing hook wired into $DEV_DIR/.claude/settings.json" \
        || warn "Could not wire session briefing hook (non-fatal)"
fi

# ─── Step 8: Verify ──────────────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════╗"
echo "║      CORTEX INSTALL VERIFICATION       ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "  — Install —"
"$VENV/bin/python" -c "from cli import main" 2>/dev/null \
    && echo "  ✅ cortex package importable" \
    || echo "  ❌ cortex package import failed"
[ -d "$CORTEX_STATE/logs" ] \
    && echo "  ✅ ~/.cortex/ state directory ready" \
    || echo "  ❌ ~/.cortex/ state directory missing"
[ -f "$CORTEX_DIR/.env" ] \
    && echo "  ✅ .env present" \
    || echo "  ❌ .env missing"
[ -L "$LOCAL_BIN/cortex" ] \
    && echo "  ✅ cortex on PATH (~/.local/bin/cortex)" \
    || echo "  ⚠️  cortex not linked to ~/.local/bin"

echo ""
echo "  — Runtime —"
VERIFY_KEY=$(grep -E "^ANTHROPIC_API_KEY=sk-" "$CORTEX_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
if _key_is_real "${VERIFY_KEY:-}" || _key_is_real "${ANTHROPIC_API_KEY:-}"; then
    echo "  ✅ ANTHROPIC_API_KEY configured"
else
    echo "  ⚠️  ANTHROPIC_API_KEY not set"
fi
"$VENV/bin/python" -m cli health 2>&1 | grep -q "All Systems Operational" \
    && echo "  ✅ cortex health: all systems operational" \
    || echo "  ⚠️  cortex health: some systems degraded"
[ -d "$CORTEX_DIR/site/node_modules" ] \
    && echo "  ✅ site dashboard ready" \
    || echo "  ⚠️  site dashboard not set up (optional)"

echo ""
log "Install complete."
echo ""
if [ "$PROFILE_UPDATED" = true ]; then
    echo "  PATH updated — open a new terminal or run: source ~/.zprofile"
fi
echo "  Run: cortex status"
echo ""

# ─── Step 9: Onboard ─────────────────────────────────────────────────────────
if [ -n "${INPUT_ROOT:-}" ] && [ -d "${INPUT_ROOT:-}" ]; then
    echo ""
    info "cortex onboard scans $INPUT_ROOT, detects projects, and seeds memory."
    RUN_ONBOARD="n"
    [ -t 0 ] && { read -rp "  Run cortex onboard now? [Y/n]: " RUN_ONBOARD || true; }
    if [[ "$RUN_ONBOARD" =~ ^[Yy] ]]; then
        log "Running cortex onboard..."
        "$VENV/bin/python" -m cli onboard --root "$INPUT_ROOT" --non-interactive 2>&1 \
            || warn "Onboard completed with warnings — run 'cortex onboard' manually to retry"
    fi
fi
