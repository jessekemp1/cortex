#!/bin/bash
# Wrapper script to run Cortex CLI with local-orchestrator venv Python

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/local-orchestrator/venv/bin/python"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: local-orchestrator venv not found"
    echo "Run: cd local-orchestrator && ./resolve_dependencies.sh"
    exit 1
fi

# Run with proper path setup
cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/cortex:$ROOT_DIR/local-orchestrator:$PYTHONPATH" \
  "$VENV_PYTHON" -c "
import sys
sys.path.insert(0, 'cortex')
sys.path.insert(1, 'local-orchestrator')
from cortex.cli import main
main()
" "$@"

