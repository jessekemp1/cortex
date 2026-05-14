#!/usr/bin/env bash
#
# Verify CLI output matches captured goldens.
#
# Pair to scripts/capture_goldens.sh. Run after a refactor phase to confirm
# that golden CLI output (briefing, status, doctor) is unchanged.
#
# Exit codes:
#   0 — all goldens match
#   1 — at least one golden drifted (diff printed)
#   2 — goldens dir doesn't exist (must run capture_goldens.sh first)

set -euo pipefail

GOLDENS_DIR="${1:-./goldens}"

if [ ! -d "$GOLDENS_DIR" ]; then
    echo "ERROR: $GOLDENS_DIR does not exist. Run ./scripts/capture_goldens.sh first."
    exit 2
fi

# Keep this list in sync with capture_goldens.sh.
COMMANDS=(
    "doctor:cortex doctor"
    "status:cortex status"
    "briefing:cortex briefing"
)

failures=0
for entry in "${COMMANDS[@]}"; do
    name="${entry%%:*}"
    cmd="${entry#*:}"
    golden="$GOLDENS_DIR/$name.txt"

    if [ ! -f "$golden" ]; then
        echo "MISSING: $golden (run capture_goldens.sh)"
        failures=$((failures + 1))
        continue
    fi

    actual=$(mktemp)
    if ! eval "$cmd" > "$actual" 2>&1; then
        rc=$?
        echo "WARNING: '$cmd' exited $rc"
    fi

    if diff -u "$golden" "$actual" > /dev/null; then
        echo "OK:    $name"
    else
        echo "DRIFT: $name"
        diff -u "$golden" "$actual" | head -40
        failures=$((failures + 1))
    fi
    rm -f "$actual"
done

if [ "$failures" -gt 0 ]; then
    echo
    echo "$failures golden(s) drifted. Investigate before merging the refactor."
    exit 1
fi
echo
echo "All goldens match."
