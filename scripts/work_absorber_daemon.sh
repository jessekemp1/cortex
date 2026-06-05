#!/bin/bash
# Cortex Work Absorber Daemon
# Runs periodically to capture work progress from git, docs, and batch results
# Designed to run every 4-6 hours via launchd

CORTEX_DIR="${CORTEX_ROOT:-$HOME/Dev/cortex}"
LOG_FILE="$HOME/.cortex/work_absorber.log"
REPORT_FILE="${CORTEX_ROOT:-$HOME/Dev/cortex}/WORK_PROGRESS_REPORT.md"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

cd "$CORTEX_DIR" || exit 1

echo "========================================" >> "$LOG_FILE"
echo "$(date): Work Absorber Daemon Started" >> "$LOG_FILE"

# Run incremental absorption
${CORTEX_ROOT:-$HOME/Dev/cortex}/.venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from datetime import datetime
from work_absorber import WorkAbsorber
from work_absorber.storage import WorkAbsorberStorage

storage = WorkAbsorberStorage()
absorber = WorkAbsorber(storage)

# Incremental absorption (only new signals since last run)
report = absorber.absorb(incremental=True)

print(f'Duration: {report.duration_seconds:.2f}s')
print(f'Signals: {report.signals_detected} detected, {report.signals_absorbed} absorbed')
print(f'Work items: {report.work_items_created} new, {report.work_items_updated} updated')
print(f'Drifts: {report.drifts_detected}')

if report.errors:
    print(f'Errors: {len(report.errors)}')
    for e in report.errors[:3]:
        print(f'  - {e}')
" >> "$LOG_FILE" 2>&1

# Update progress report
${CORTEX_ROOT:-$HOME/Dev/cortex}/.venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from datetime import datetime
from pathlib import Path
from work_absorber.storage import WorkAbsorberStorage
from work_absorber.models import DriftType

storage = WorkAbsorberStorage()

# Get stats
all_items = storage.get_all_work_items(limit=50)
drifts = storage.get_unresolved_drifts()

# Generate mini-report
lines = [
    '# Cortex Work Progress Report',
    f'**Auto-updated:** {datetime.now().strftime(\"%Y-%m-%d %H:%M\")}',
    '',
    f'- **Work items tracked:** {len(all_items)}',
    f'- **Plan drifts:** {len(drifts)}',
    f'- **Unplanned work:** {sum(1 for d in drifts if d.drift_type == DriftType.UNPLANNED_WORK)}',
    '',
    '---',
    '',
    '## Recent Work',
    '',
]

# Add recent items
for item in sorted(all_items, key=lambda x: x.last_activity, reverse=True)[:10]:
    status = '✅' if 'COMPLETE' in item.title.upper() else '🔄'
    date = item.last_activity.strftime('%Y-%m-%d')
    lines.append(f'- {status} [{item.project}] {item.title} ({date})')

Path('$REPORT_FILE').write_text('\\n'.join(lines))
" >> "$LOG_FILE" 2>&1

echo "$(date): Work Absorber Daemon Completed" >> "$LOG_FILE"
