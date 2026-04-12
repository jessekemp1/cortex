#!/bin/bash
# Batch Queue Processor Daemon Wrapper
#
# Loads API key and runs queue_manager.py to submit queued jobs to Anthropic.
# Called by com.cortex.batch.processor launchd agent at 22:05 nightly.

set -euo pipefail

REPO_ROOT="${HOME}/Dev"
VENV_PYTHON="${REPO_ROOT}/cortex/.venv/bin/python"
QUEUE_MANAGER="${REPO_ROOT}/cortex/batch/queue_manager.py"

# Load API key from Anthropic config (used by Claude Code)
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    if [ -f "$HOME/.anthropic/api_key" ]; then
        export ANTHROPIC_API_KEY=$(/bin/cat "$HOME/.anthropic/api_key")
    else
        echo "ERROR: ANTHROPIC_API_KEY not set and ~/.anthropic/api_key not found" >&2
        exit 1
    fi
fi

# Load any additional env vars from .env if present
if [ -f "${REPO_ROOT}/.env" ]; then
    set -a
    source "${REPO_ROOT}/.env"
    set +a
fi

export PYTHONPATH="${REPO_ROOT}/cortex:${REPO_ROOT}"

exec "${VENV_PYTHON}" "${QUEUE_MANAGER}" \
    --duration 8 \
    --check-interval 300 \
    --max-concurrent 5
