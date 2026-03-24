#!/usr/bin/env bash
# ============================================================
# Cortex Fresh Install Test
#
# Run this in a fresh container/VM to verify beta-readiness.
# Designed for: Ubuntu 22.04+ / Debian 12+ on Hetzner
#
# Usage:
#   curl -sSL <raw-url> | bash
#   # or
#   chmod +x test_fresh_install.sh && ./test_fresh_install.sh
# ============================================================

set -euo pipefail

PASS=0
FAIL=0
WARN=0

pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }
warn() { echo "  [WARN] $1"; ((WARN++)); }

echo "============================================================"
echo "  CORTEX FRESH INSTALL TEST"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "  Host: $(hostname)"
echo "  OS: $(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'"' -f2 || uname -s)"
echo "============================================================"
echo

# ── Prerequisites ──
echo "--- Prerequisites ---"

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    pass "Python3 found: $PY_VER"
else
    fail "Python3 not found"
    echo "Install with: apt install python3 python3-pip python3-venv"
    exit 1
fi

PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MINOR" -ge 11 ]; then
    pass "Python >= 3.11"
else
    fail "Python $PY_VER < 3.11 (required)"
    exit 1
fi

if command -v git &>/dev/null; then
    pass "Git found: $(git --version)"
else
    fail "Git not found"
    echo "Install with: apt install git"
    exit 1
fi

echo

# ── Clone ──
echo "--- Clone & Install ---"

WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"
echo "  Working directory: $WORK_DIR"

if git clone https://github.com/jessekemp1/cortex.git cortex 2>/dev/null; then
    pass "Repository cloned"
else
    # Fallback: if repo is private or we're testing locally
    if [ -d "/home/user/cortex/.git" ]; then
        cp -r /home/user/cortex cortex
        pass "Repository copied (local fallback)"
    else
        fail "Cannot clone repository"
        exit 1
    fi
fi

cd cortex

# Create venv
python3 -m venv .venv
source .venv/bin/activate
pass "Virtual environment created"

# Install core only (no optional deps)
pip install -e . --quiet 2>/dev/null
if python3 -c "import yaml; import rich; import requests" 2>/dev/null; then
    pass "Core dependencies installed"
else
    fail "Core dependency install failed"
fi

echo

# ── Core Module Imports ──
echo "--- Core Module Imports (stdlib only) ---"

CORE_MODULES=(
    "intelligence.ensemble_decider"
    "intelligence.temporal_router"
    "intelligence.verifiable_expertise"
    "intelligence.model_selection.recommender"
    "intelligence.model_selection.classifier"
    "intelligence.model_selection.rules"
    "intelligence.model_selection.models"
    "batch.subscription_optimizer"
    "batch.utilization_learning"
    "batch.routing_framework"
    "cortex_setup"
)

for mod in "${CORE_MODULES[@]}"; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "$mod"
    else
        fail "$mod: $(python3 -c "import $mod" 2>&1 | tail -1)"
    fi
done

echo

# ── Optional Module Imports ──
echo "--- Optional Module Imports ---"

# Install optional deps
pip install -e ".[llm]" --quiet 2>/dev/null || warn "Could not install [llm] extras"
pip install -e ".[embeddings]" --quiet 2>/dev/null || warn "Could not install [embeddings] extras"

OPTIONAL_MODULES=(
    "intelligence.contracts"
    "intelligence.signals"
    "batch.batch_api_client"
)

for mod in "${OPTIONAL_MODULES[@]}"; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "$mod"
    else
        warn "$mod (optional dep missing)"
    fi
done

echo

# ── Test Suite ──
echo "--- Test Suite ---"

pip install pytest --quiet 2>/dev/null

RESULT=$(python3 -m pytest \
    batch/tests/test_subscription_optimizer.py \
    batch/tests/test_utilization_learning.py \
    intelligence/tests/test_vortex_systems.py \
    -q --tb=line 2>&1)

LAST_LINE=$(echo "$RESULT" | tail -1)
if echo "$LAST_LINE" | grep -q "passed"; then
    pass "Tests: $LAST_LINE"
else
    fail "Tests: $LAST_LINE"
    echo "$RESULT" | tail -5
fi

echo

# ── Setup Wizard ──
echo "--- Setup Wizard (non-interactive) ---"

# Run setup wizard non-interactively
WIZARD_OUTPUT=$(echo "" | python3 -c "
import sys
sys.argv = ['cortex_setup', '--non-interactive']
from cortex_setup import CortexSetupWizard
wizard = CortexSetupWizard(non_interactive=True)
wizard.run()
" 2>&1) || true

if echo "$WIZARD_OUTPUT" | grep -q "CORTEX IS READY"; then
    pass "Setup wizard completed successfully"
else
    fail "Setup wizard did not complete"
    echo "$WIZARD_OUTPUT" | tail -10
fi

# Check artifacts
if [ -f "$HOME/.cortex/config.yaml" ] || [ -f "$HOME/.cortex/config.json" ]; then
    pass "Config file created"
else
    fail "Config file not created"
fi

if [ -d "$HOME/.cortex/memories" ] && [ -d "$HOME/.cortex/ensemble" ]; then
    pass "Directory structure created"
else
    fail "Directory structure incomplete"
fi

echo

# ── CLI Entry Point ──
echo "--- CLI Entry Point ---"

if python3 -c "from cli import main; print('OK')" 2>/dev/null; then
    pass "CLI imports successfully"
else
    fail "CLI import failed: $(python3 -c 'from cli import main' 2>&1 | tail -1)"
fi

echo

# ── Functional Smoke Tests ──
echo "--- Functional Smoke Tests ---"

# Test subscription optimizer
if python3 -c "
from batch.subscription_optimizer import SubscriptionOptimizer
opt = SubscriptionOptimizer()
opt.configure_subscription('anthropic', 'pro', 5000000, 20.0, 1)
status = opt.get_utilization_status('anthropic')
assert status is not None
print('Subscription optimizer: OK')
" 2>/dev/null; then
    pass "Subscription optimizer"
else
    fail "Subscription optimizer"
fi

# Test ensemble decider
if python3 -c "
from intelligence.ensemble_decider import FieldEnsembleDecider
decider = FieldEnsembleDecider()
decision = decider.decide({'task_type': 'code_review', 'request_text': 'review code'})
assert decision.model_tier in ('haiku', 'sonnet', 'opus')
print('Ensemble decider: OK')
" 2>/dev/null; then
    pass "Field ensemble decider"
else
    fail "Field ensemble decider"
fi

# Test temporal router
if python3 -c "
from intelligence.temporal_router import TemporalHorizonRouter
router = TemporalHorizonRouter()
profile = router.classify({'request_text': 'fix this bug', 'task_type': 'debugging'})
assert profile.horizon.value == 'immediate'
print('Temporal router: OK')
" 2>/dev/null; then
    pass "Temporal horizon router"
else
    fail "Temporal horizon router"
fi

# Test verifiable expertise
if python3 -c "
from intelligence.verifiable_expertise import VerifiableExpertise
ve = VerifiableExpertise()
pid = ve.record_prediction('model_selection', 'sonnet', 0.8, 'test')
correct = ve.resolve_prediction(pid, 'sonnet')
assert correct == True
print('Verifiable expertise: OK')
" 2>/dev/null; then
    pass "Verifiable expertise"
else
    fail "Verifiable expertise"
fi

# Test learning engine
if python3 -c "
from batch.utilization_learning import UtilizationLearningEngine
engine = UtilizationLearningEngine()
engine.observe_routing_decision('code_review', 'batch', 25000, 50.0, True)
report = engine.format_learning_report()
assert 'Learning Engine' in report
print('Learning engine: OK')
" 2>/dev/null; then
    pass "Utilization learning engine"
else
    fail "Utilization learning engine"
fi

echo

# ── Cleanup ──
deactivate 2>/dev/null || true

echo "============================================================"
echo "  RESULTS"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Warnings: $WARN"
echo "============================================================"

if [ "$FAIL" -eq 0 ]; then
    echo "  ALL TESTS PASSED - Ready for beta"
else
    echo "  $FAIL FAILURES - Review above"
fi

echo
echo "  Working directory preserved at: $WORK_DIR"
echo "  Clean up with: rm -rf $WORK_DIR"

exit $FAIL
