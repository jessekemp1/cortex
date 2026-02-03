# Cortex Orchestration - 7-Day Validation (Jan 31 - Feb 7, 2026)

## Quick Start

```bash
# Collect daily snapshot
cd ~/Dev/cortex/reports/validation_2026-02
python3 collect_metrics.py

# View summary
python3 collect_metrics.py summary

# Read full report
cat VALIDATION_REPORT.md
```

## Validation Period

**Dates**: January 31 - February 7, 2026 (7 days)
**Current Day**: 4 of 7
**Status**: 🔄 In Progress

## Files

- `VALIDATION_REPORT.md` - Main report (update daily, finalize Feb 7)
- `collect_metrics.py` - Automated metrics collector
- `metrics_snapshots.json` - Daily data snapshots
- `README.md` - This file

## Daily Workflow

**Every day at EOD**:
1. Run: `python3 collect_metrics.py`
2. Review snapshot output
3. Update VALIDATION_REPORT.md with observations
4. Note any anomalies or issues

**On Feb 7** (Final Day):
1. Collect final snapshot
2. Run: `python3 collect_metrics.py summary`
3. Complete all TBD sections in VALIDATION_REPORT.md
4. Make SHIP or ITERATE recommendation
5. Commit final report

## Current Metrics (Day 4)

**Snapshot**: 2026-02-03 15:35:12

```json
{
  "batch_queue": {
    "queued": 1384,
    "running": 0
  },
  "infrastructure": {
    "ports_in_use": 17,
    "services": 2
  },
  "projects": {
    "total": 8,
    "running": 2
  }
}
```

## Success Criteria

### Must Have (P0)
- [ ] Dashboard uptime >99%
- [ ] Zero critical anomalies unresolved
- [ ] Batch queue utilization >50% overnight
- [ ] No data loss or corruption
- [ ] All tests passing

### Current Status
- ⚠️ Dashboard: Not running (port 8502)
- ⚠️ Supervisor: Not running
- ✅ Infrastructure: 17 ports active, 2 services running
- ⚠️ Queue: 1,384 jobs queued (needs investigation)

## Next Actions

1. **Start dashboard**: `streamlit run ~/Dev/cortex/dashboard/orchestration.py --server.port 8502 &`
2. **Start supervisor**: `cortex supervisor start`
3. **Investigate queue**: Why 1,384 jobs queued? Clear stale tasks
4. **Collect daily**: Run `collect_metrics.py` every evening
