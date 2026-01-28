#!/bin/bash
# Cortex Batch API Shell Aliases
# Source this file: source /Users/jesse.kemp/Dev/cortex/batch/aliases.sh

CORTEX_DIR="/Users/jesse.kemp/Dev/cortex"

# Quick batch submission
batch-review() {
    python "$CORTEX_DIR/batch/quick_batch.py" review "$@"
}

batch-docs() {
    python "$CORTEX_DIR/batch/quick_batch.py" docs "$@"
}

batch-research() {
    python "$CORTEX_DIR/batch/quick_batch.py" research "$@"
}

batch-security() {
    python "$CORTEX_DIR/batch/quick_batch.py" security "$@"
}

batch-patterns() {
    python "$CORTEX_DIR/batch/quick_batch.py" patterns "$@"
}

batch-test-gaps() {
    python "$CORTEX_DIR/batch/quick_batch.py" test-gaps "$@"
}

# Status commands
batch-status() {
    python "$CORTEX_DIR/batch/quick_batch.py" status
}

batch-dashboard() {
    python "$CORTEX_DIR/batch/dashboard.py" "$@"
}

batch-orchestrate() {
    python "$CORTEX_DIR/batch/intelligent_orchestrator.py" "$@"
}

# Quick help
batch-help() {
    echo "Cortex Batch Commands (50% cost savings)"
    echo "========================================="
    echo ""
    echo "Submit jobs:"
    echo "  batch-review <path>      Code review"
    echo "  batch-docs <path>        Documentation"
    echo "  batch-research \"topic\"   Research question"
    echo "  batch-security           Security audit"
    echo "  batch-patterns           Pattern analysis"
    echo "  batch-test-gaps <path>   Test coverage"
    echo ""
    echo "Monitor:"
    echo "  batch-status             Quick status"
    echo "  batch-dashboard          Full dashboard"
    echo "  batch-orchestrate        Fill overnight queue"
    echo ""
    echo "Options: --priority {low,normal,high} --deadline N"
}

echo "Cortex batch aliases loaded. Run 'batch-help' for commands."
