#!/usr/bin/env bash
# smoke_test_fresh_install.sh — Run on a fresh Hetzner (Ubuntu 22.04+) to validate install path
# Usage: curl -sL <raw-github-url> | bash
# Or: scp this to server, chmod +x, run it.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
PASS=0
FAIL=0
WARN=0

pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS++)); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL++)); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((WARN++)); }

echo "============================================"
echo " Cortex Fresh Install Smoke Test"
echo " $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"
echo ""

# --- Prerequisites ---
echo "--- Prerequisites ---"

PYTHON=""
for py in python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" --version 2>&1 | awk '{print $2}')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$py"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.11+ not found. Install with: apt install python3.11 python3.11-venv"
    echo ""
    echo "Quick fix for Ubuntu 22.04:"
    echo "  sudo add-apt-repository ppa:deadsnakes/ppa -y"
    echo "  sudo apt update && sudo apt install python3.11 python3.11-venv python3.11-dev -y"
    exit 1
fi
pass "Python: $($PYTHON --version)"

if ! command -v git &>/dev/null; then
    fail "git not found"
    exit 1
fi
pass "git: $(git --version | head -1)"

# --- Clone & Install ---
echo ""
echo "--- Clone & Install ---"

WORKDIR=$(mktemp -d)
cd "$WORKDIR"

if git clone --depth 1 https://github.com/jessekemp1/cortex.git cortex 2>/dev/null; then
    pass "git clone succeeded"
else
    fail "git clone failed — is the repo public?"
    exit 1
fi

cd cortex

$PYTHON -m venv .venv
source .venv/bin/activate
pass "venv created and activated"

if pip install -e . -q 2>&1 | tail -3; then
    pass "pip install -e . succeeded (core deps)"
else
    fail "pip install -e . failed"
    exit 1
fi

# --- Import Tests ---
echo ""
echo "--- Import Tests ---"

$PYTHON -c "from config import CortexConfig; print('OK')" 2>/dev/null && pass "import config" || fail "import config"
$PYTHON -c "from bridge import CortexBridge; print('OK')" 2>/dev/null && pass "import bridge" || fail "import bridge"
$PYTHON -c "from orchestrator import CortexOrchestrator; print('OK')" 2>/dev/null && pass "import orchestrator" || fail "import orchestrator"
$PYTHON -c "from briefing import generate_daily_briefing; print('OK')" 2>/dev/null && pass "import briefing" || fail "import briefing"
$PYTHON -c "from formatter import CortexFormatter; print('OK')" 2>/dev/null && pass "import formatter" || fail "import formatter"
$PYTHON -c "from intelligence.unified_intelligence import UnifiedIntelligence; print('OK')" 2>/dev/null && pass "import unified_intelligence" || fail "import unified_intelligence"

# --- CLI Tests ---
echo ""
echo "--- CLI Commands ---"

if $PYTHON cli.py status 2>&1 | grep -q "CORTEX\|STRATEGIC\|focus"; then
    pass "cortex status runs"
else
    fail "cortex status broken"
fi

if $PYTHON cli.py health 2>&1 | grep -q "Active\|Operational\|HEALTH"; then
    pass "cortex health runs"
else
    fail "cortex health broken"
fi

# --- Bridge Instantiation ---
echo ""
echo "--- Bridge Smoke Test ---"

$PYTHON -c "
from bridge import CortexBridge
b = CortexBridge(root_dir='.')
ctx = b.get_session_context()
assert isinstance(ctx, dict), 'session context not a dict'
assert 'git' in ctx, 'no git key in session context'
print('OK')
" 2>/dev/null && pass "CortexBridge instantiation + get_session_context" || fail "CortexBridge smoke test"

# --- Test Suite ---
echo ""
echo "--- Test Suite ---"

pip install pytest -q 2>/dev/null
RESULT=$($PYTHON -m pytest tests/ -q \
    --ignore=tests/integration \
    --ignore=tests/e2e \
    --ignore=tests/benchmark \
    --ignore=tests/_quarantine \
    -k "not moltbot" \
    2>&1 | tail -3)

echo "$RESULT"
PASSED=$(echo "$RESULT" | grep -oP '\d+ passed' | grep -oP '\d+' || echo "0")
FAILED_COUNT=$(echo "$RESULT" | grep -oP '\d+ failed' | grep -oP '\d+' || echo "0")

if [ "$PASSED" -gt 1000 ]; then
    pass "Test suite: $PASSED passed, $FAILED_COUNT failed"
elif [ "$PASSED" -gt 500 ]; then
    warn "Test suite: $PASSED passed, $FAILED_COUNT failed (expected 1200+)"
else
    fail "Test suite: $PASSED passed, $FAILED_COUNT failed"
fi

# --- MCP Server (optional deps) ---
echo ""
echo "--- MCP Server (optional) ---"

pip install -e ".[server]" -q 2>/dev/null
if $PYTHON -c "from mcp_server import mcp; print('OK')" 2>/dev/null; then
    pass "MCP server imports with [server] extras"
else
    warn "MCP server import failed — check mcp package compatibility"
fi

# --- Summary ---
echo ""
echo "============================================"
echo " Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC}"
echo " Workdir: $WORKDIR"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
