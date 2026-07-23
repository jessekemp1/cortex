#!/bin/bash
# cortex_gc.sh — keep ~/.cortex from silently eating the disk.
#
# Two jobs:
#   1. Rotate oversized live logs (default): any ~/.cortex/logs/*.log over
#      --cap-mb (default 50) is gzip-copied to logs/archive/ and truncated
#      in place (copytruncate — daemons keep their fd, no restart needed).
#   2. --archive: move dead non-cortex tenant data into ~/.cortex/attic/.
#      Reversible — nothing is deleted, logs are gzipped, dirs are tar.gz'd.
#
# Safety: anything modified in the last $FRESH_DAYS days is skipped, even if
# it's on the tenant list — never yank files from under a live workload.
#
# Usage:
#   scripts/cortex_gc.sh [--dry-run] [--archive] [--cap-mb N]

set -euo pipefail

CORTEX_DIR="${CORTEX_STATE_DIR:-$HOME/.cortex}"
LOGS_DIR="$CORTEX_DIR/logs"
ATTIC_DIR="$CORTEX_DIR/attic"
CAP_MB=50
FRESH_DAYS=14
DRY_RUN=0
ARCHIVE=0

# Non-cortex tenant data that historically accumulated in ~/.cortex.
# Paths relative to $CORTEX_DIR. Live entries are skipped by the
# freshness guard, so listing something here is safe.
TENANT_LOGS=(
    "logs/vortex-backend.log"
    "logs/telegram-gateway.log"
    "logs/grib_rsync.log"
    "logs/nowcast-competition.log"
    "logs/runtime.log"
)
TENANT_DIRS=(
    "logs/hetzner_batch"
)

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --archive) ARCHIVE=1 ;;
        --cap-mb) shift; CAP_MB="$1" ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
    shift
done

say() { echo "[gc] $*"; }
act() {  # act <description> <command...>
    local desc="$1"; shift
    if [ "$DRY_RUN" = 1 ]; then
        say "DRY-RUN: $desc"
    else
        say "$desc"
        "$@"
    fi
}

fresh() {  # fresh <path> -> 0 if modified within FRESH_DAYS
    [ -n "$(find "$1" -maxdepth 0 -mtime -"$FRESH_DAYS" 2>/dev/null)" ]
}

size_mb() { du -sm "$1" 2>/dev/null | cut -f1; }

# ── 1. Rotate oversized live logs ──────────────────────────────────────
if [ -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR/archive"
    stamp=$(date +%Y%m%d)
    for log in "$LOGS_DIR"/*.log; do
        [ -f "$log" ] || continue
        # In archive mode, tenant logs go to the attic whole — don't
        # rotate them first (that would gzip GBs twice).
        if [ "$ARCHIVE" = 1 ]; then
            skip=0
            for rel in "${TENANT_LOGS[@]}"; do
                [ "$log" = "$CORTEX_DIR/$rel" ] && skip=1 && break
            done
            [ "$skip" = 1 ] && continue
        fi
        mb=$(size_mb "$log")
        if [ "$mb" -ge "$CAP_MB" ]; then
            name=$(basename "$log")
            dest="$LOGS_DIR/archive/${name%.log}.$stamp.log.gz"
            act "rotate $name (${mb}MB >= ${CAP_MB}MB) -> archive/ + truncate" \
                bash -c "gzip -c '$log' > '$dest' && : > '$log'"
        fi
    done
fi

# ── 2. Archive dead tenant data ────────────────────────────────────────
if [ "$ARCHIVE" = 1 ]; then
    stamp=$(date +%Y%m%d)
    dest_dir="$ATTIC_DIR/$stamp"
    [ "$DRY_RUN" = 1 ] || mkdir -p "$dest_dir"

    for rel in "${TENANT_LOGS[@]}"; do
        f="$CORTEX_DIR/$rel"
        [ -f "$f" ] || continue
        if fresh "$f"; then
            say "SKIP (modified <${FRESH_DAYS}d ago — may be live): $rel"
            continue
        fi
        mb=$(size_mb "$f")
        act "attic ${rel} (${mb}MB, gzip)" \
            bash -c "gzip -c '$f' > '$dest_dir/$(basename "$f").gz' && rm '$f'"
    done

    for rel in "${TENANT_DIRS[@]}"; do
        d="$CORTEX_DIR/$rel"
        [ -d "$d" ] || continue
        if fresh "$d"; then
            say "SKIP (modified <${FRESH_DAYS}d ago — may be live): $rel"
            continue
        fi
        mb=$(size_mb "$d")
        act "attic ${rel}/ (${mb}MB, tar.gz)" \
            bash -c "tar -czf '$dest_dir/$(basename "$d").tar.gz' -C '$(dirname "$d")' '$(basename "$d")' && rm -r '$d'"
    done
fi

say "done. ~/.cortex: $(du -sh "$CORTEX_DIR" 2>/dev/null | cut -f1) (logs: $(du -sh "$LOGS_DIR" 2>/dev/null | cut -f1))"
