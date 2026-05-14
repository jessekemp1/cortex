---
name: briefing
version: 1.0.0
description: Morning briefing with project status, anomalies, and next actions
author: Jesse Kemp
requires:
  python: ">=3.11"
  packages: []
tags: [core, orchestration, morning, intelligence]
enabled: true
---

# Briefing Plugin

Generates comprehensive morning briefing with:
- Project status summary
- Overnight changes
- Anomalies and alerts
- Prioritized next actions
- Batch job results (if any)

## Usage

```bash
/briefing [options]
```

### Options

- `--date DATE` - Briefing for specific date (default: today)
- `--format FORMAT` - Output format: text, markdown, json (default: text)
- `--help, -h` - Show help

## Examples

### Morning Briefing

```bash
$ /briefing
📊 Morning Briefing - Friday, Jan 31, 2026
═══════════════════════════════════════════

🌙 Overnight Summary
──────────────────
- 3 commits pushed
- 2 batch jobs completed
- 1 anomaly detected (MEDIUM)

📈 Project Status
───────────────
✓ VortexV2: Healthy (forecast accuracy: 94%)
✓ Alpha Arena: Active (5 positions, +2.3% PnL)
⚠ Cortex: 1 failed test

🔔 Alerts & Anomalies
───────────────────
⚠ MEDIUM: Wind forecast MAE spike (12.5 → 18.2 m/s)
  Location: NREL-5MW offshore
  Action: Review GRIB data quality

📋 Next Actions (Priority Order)
──────────────────────────────
1. ✅ Review wind forecast anomaly
2. 📝 Fix failing Cortex test
3. 🚢 Deploy VortexV3 React components
4. 📊 Analyze Alpha Arena performance

💡 Cortex Recommendations
────────────────────────
- Consider adding tests for calculations.py
- Safe to commit VortexV3 components
- Review competition_log size (24MB)
```

## Implementation

Aggregates data from:
- Git status and recent commits
- Anomaly detector
- Batch job results
- Intelligence recommendations
- Project health checks

Present in priority order for efficient morning workflow.
