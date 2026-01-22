#!/bin/bash
# Cortex Batch Queue Manager Helper Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUEUE_MANAGER="$SCRIPT_DIR/queue_manager.py"
PID_FILE="$HOME/.cortex/batches/queue_manager.pid"
LOG_FILE="$HOME/.cortex/batches/queue_manager.log"

export PYTHONPATH="$(dirname $(dirname $SCRIPT_DIR)):$PYTHONPATH"

case "$1" in
    start)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "⚠️  Queue manager already running (PID: $(cat $PID_FILE))"
            exit 1
        fi

        echo "🚀 Starting queue manager..."
        echo "   Log file: $LOG_FILE"

        nohup python3 "$QUEUE_MANAGER" \
            --check-interval ${CHECK_INTERVAL:-300} \
            --max-concurrent ${MAX_CONCURRENT:-5} \
            >> "$LOG_FILE" 2>&1 &

        echo $! > "$PID_FILE"
        echo "✅ Queue manager started (PID: $(cat $PID_FILE))"
        echo ""
        echo "Commands:"
        echo "  $0 status  - Check queue status"
        echo "  $0 logs    - Tail logs"
        echo "  $0 stop    - Stop queue manager"
        ;;

    stop)
        if [ ! -f "$PID_FILE" ]; then
            echo "⚠️  Queue manager not running (no PID file)"
            exit 1
        fi

        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "🛑 Stopping queue manager (PID: $PID)..."
            kill "$PID"
            rm "$PID_FILE"
            echo "✅ Queue manager stopped"
        else
            echo "⚠️  Queue manager not running (stale PID file)"
            rm "$PID_FILE"
        fi
        ;;

    status)
        echo "📊 Queue Status"
        echo "═══════════════════════════════════════════════════════"

        # Check if queue manager is running
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "Queue Manager: ✅ RUNNING (PID: $(cat $PID_FILE))"
        else
            echo "Queue Manager: ❌ STOPPED"
        fi
        echo ""

        # Show queue status
        python3 "$QUEUE_MANAGER" --status-only
        echo ""

        # Show recent batch activity
        echo "═══════════════════════════════════════════════════════"
        echo "📥 Recent Batch Activity (via API)"
        echo "═══════════════════════════════════════════════════════"
        export ANTHROPIC_API_KEY=$(security find-generic-password -s "anthropic-api-key" -w 2>/dev/null)
        python3 -c "
from cortex.batch.batch_api_client import BatchAPIClient
client = BatchAPIClient()
batches = client.list_batches(limit=5)
for b in batches:
    counts = b['request_counts']
    total = sum(counts.values())
    done = counts['succeeded'] + counts['errored']
    status_emoji = '✅' if b['status'] == 'ended' else '⏳'
    print(f\"{status_emoji} {b['id'][:24]}... | {b['status']:12} | {done}/{total} done | {b['created_at']}\")
"
        ;;

    logs)
        if [ ! -f "$LOG_FILE" ]; then
            echo "❌ No log file found: $LOG_FILE"
            exit 1
        fi
        echo "📜 Tailing queue manager logs (Ctrl-C to stop)"
        echo "Log file: $LOG_FILE"
        echo ""
        tail -f "$LOG_FILE"
        ;;

    process)
        echo "🔄 Processing queue (single iteration)..."
        export ANTHROPIC_API_KEY=$(security find-generic-password -s "anthropic-api-key" -w 2>/dev/null)
        python3 -c "
from cortex.batch.queue_manager import BatchQueueManager
manager = BatchQueueManager()
stats = manager.process_queue()
print(f\"✅ Jobs submitted: {stats['jobs_submitted']}\")
print(f\"📋 Jobs pending: {stats['jobs_pending']}\")
print(f\"📊 Capacity available: {stats['capacity_available']}\")
"
        ;;

    *)
        echo "Usage: $0 {start|stop|status|logs|process}"
        echo ""
        echo "Commands:"
        echo "  start   - Start queue manager in background"
        echo "  stop    - Stop queue manager"
        echo "  status  - Show queue and batch status"
        echo "  logs    - Tail queue manager logs"
        echo "  process - Run one queue processing iteration"
        echo ""
        echo "Environment variables:"
        echo "  CHECK_INTERVAL - Seconds between checks (default: 300)"
        echo "  MAX_CONCURRENT - Max concurrent batches (default: 5)"
        exit 1
        ;;
esac
