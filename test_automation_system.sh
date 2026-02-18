#!/bin/bash
# Test Cortex Daily Automation System
# Verifies all components are in place and working

set -e

CORTEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CORTEX_DIR"

echo "🧪 Testing Cortex Daily Automation System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PASS=0
FAIL=0

# Test function
test_item() {
    local name="$1"
    local command="$2"

    if eval "$command" > /dev/null 2>&1; then
        echo "✅ $name"
        PASS=$((PASS + 1))
    else
        echo "❌ $name"
        FAIL=$((FAIL + 1))
    fi
}

# Test scripts exist and are executable
echo "📄 Testing Scripts..."
test_item "daily_scan.sh exists" "[ -f daily_scan.sh ]"
test_item "daily_scan.sh is executable" "[ -x daily_scan.sh ]"
test_item "weekly_report.sh exists" "[ -f weekly_report.sh ]"
test_item "weekly_report.sh is executable" "[ -x weekly_report.sh ]"
test_item "install_automation.sh exists" "[ -f install_automation.sh ]"
test_item "install_automation.sh is executable" "[ -x install_automation.sh ]"
test_item "uninstall_automation.sh exists" "[ -f uninstall_automation.sh ]"
test_item "uninstall_automation.sh is executable" "[ -x uninstall_automation.sh ]"

echo ""
echo "📚 Testing Documentation..."
test_item "DAILY_WORKFLOW.md exists" "[ -f DAILY_WORKFLOW.md ]"
test_item "DAILY_QUICK_START.md exists" "[ -f DAILY_QUICK_START.md ]"
test_item "README_DAILY_AUTOMATION.md exists" "[ -f README_DAILY_AUTOMATION.md ]"
test_item "AUTOMATION_SETUP_COMPLETE.md exists" "[ -f AUTOMATION_SETUP_COMPLETE.md ]"
test_item "automation/README.md exists" "[ -f automation/README.md ]"

echo ""
echo "⚙️  Testing Automation Config..."
test_item "LaunchAgent plist exists" "[ -f automation/com.cortex.daily.plist ]"
test_item "automation directory exists" "[ -d automation ]"

echo ""
echo "📁 Testing Directories..."
test_item "~/.cortex exists" "[ -d ~/.cortex ]"
test_item "~/.cortex/logs exists" "[ -d ~/.cortex/logs ]"
test_item "~/.cortex/signals exists" "[ -d ~/.cortex/signals ]"
test_item "~/.cortex/contracts exists" "[ -d ~/.cortex/contracts ]"
test_item "~/.cortex/execution_results exists" "[ -d ~/.cortex/execution_results ]"

echo ""
echo "🔧 Testing Core Components..."
test_item "cortex_mvp exists" "[ -f cortex_mvp ]"
test_item "cortex_mvp is executable" "[ -x cortex_mvp ]"
test_item "launch_dashboard.sh exists" "[ -f launch_dashboard.sh ]"
test_item "launch_dashboard.sh is executable" "[ -x launch_dashboard.sh ]"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Test Results:"
echo "   Passed: $PASS"
echo "   Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✅ All tests passed! System is ready for use."
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Run first scan: ./daily_scan.sh"
    echo "   2. View dashboard: ./launch_dashboard.sh"
    echo "   3. Enable automation: ./install_automation.sh"
    exit 0
else
    echo "❌ Some tests failed. Please review the output above."
    exit 1
fi
