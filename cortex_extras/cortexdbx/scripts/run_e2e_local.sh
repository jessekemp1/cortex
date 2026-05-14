#!/usr/bin/env bash
# Run CortexDBx unit tests and e2e tests locally (validate before Databricks).
# Usage: from repo root: ./cortexdbx/scripts/run_e2e_local.sh
#        or: cd cortex && ../cortexdbx/scripts/run_e2e_local.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

echo "Running CortexDBx tests (unit + e2e)..."
python -m pytest cortexdbx/tests/ -v --tb=short
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "All tests passed."
else
  echo "Some tests failed (exit $EXIT_CODE)."
fi
exit $EXIT_CODE
