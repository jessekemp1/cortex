#!/bin/bash
# Setup nightly portfolio scan cron job (runs at 2 AM daily)

set -e

CRON_CMD="0 2 * * * cd /Users/jesse.kemp/Dev && python3 scripts/nightly_portfolio_scan.py >> ${HOME}/.cortex/logs/nightly_scan.log 2>&1"

echo "Setting up nightly portfolio scan..."
echo "Cron: $CRON_CMD"

if crontab -l 2>/dev/null | grep -q "nightly_portfolio_scan.py"; then
    echo "⚠️  Already exists. Remove first with:"
    echo "   crontab -l | grep -v 'nightly_portfolio_scan.py' | crontab -"
    exit 1
fi

mkdir -p "${HOME}/.cortex/logs"
(crontab -l 2>/dev/null || true; echo "$CRON_CMD") | crontab -

echo "✅ Installed! Verify: crontab -l"
echo "Test: python3 scripts/nightly_portfolio_scan.py"
echo "Logs: ${HOME}/.cortex/logs/nightly_scan.log"
