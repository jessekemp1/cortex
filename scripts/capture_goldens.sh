#!/usr/bin/env bash
#
# Capture golden CLI outputs for the slim-down ratchet.
#
# Phase 0 deliverable from /root/.claude/plans/can-we-also-run-shimmying-globe.md
# ("Phase 4 success criteria: cortex briefing/status/doctor produce byte-identical
#  output to pre-phase baseline (capture in Phase 0).").
#
# Goldens are environment-specific (depend on ~/.cortex/ state, git history,
# installed deps). They are NOT checked into git — they're per-developer
# baselines captured immediately before each refactor phase.
#
# Workflow:
#   1. Before starting Phase 4 (or any consolidation phase), run:
#        ./scripts/capture_goldens.sh
#   2. Make refactor changes.
#   3. Run ./scripts/verify_goldens.sh to confirm no output drift.
#
# Usage:
#   ./scripts/capture_goldens.sh [GOLDENS_DIR]
#   default GOLDENS_DIR=./goldens

set -euo pipefail

GOLDENS_DIR="${1:-./goldens}"
mkdir -p "$GOLDENS_DIR"

echo "Capturing CLI goldens to $GOLDENS_DIR/"

# Commands to capture. Each entry: <name>:<command>
# Add entries here as the slim-down touches additional CLI surface.
COMMANDS=(
    "doctor:cortex doctor"
    "status:cortex status"
    "briefing:cortex briefing"
)

for entry in "${COMMANDS[@]}"; do
    name="${entry%%:*}"
    cmd="${entry#*:}"
    outfile="$GOLDENS_DIR/$name.txt"
    echo "  capturing: $cmd → $outfile"
    if eval "$cmd" > "$outfile" 2>&1; then
        echo "    ok ($(wc -l < "$outfile") lines)"
    else
        rc=$?
        echo "    WARNING: '$cmd' exited $rc — captured stderr too"
    fi
done

echo
echo "Goldens captured. Commit them locally if you want the diff ratchet:"
echo "    git add -f $GOLDENS_DIR/ && git stash push -m 'phase-N goldens'"
echo
echo "Run ./scripts/verify_goldens.sh after refactor to diff."
