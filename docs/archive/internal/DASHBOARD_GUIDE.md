# Cortex Intelligence Dashboard - User Guide

**Status**: ✅ Fully Operational
**Built**: January 23, 2026

## Quick Start

```bash
# Launch the dashboard
./launch_dashboard.sh

# Or manually:
streamlit run mvp/dashboard.py
```

The dashboard will open automatically at `http://localhost:8501`

---

## Dashboard Pages

### 🏥 Health Page

**Real-time system monitoring with actionable alerts**

**Metrics Displayed:**
- **Queue Depth** (optimal: 3-8) - Number of tasks waiting
- **Success Rate** (optimal: >85%) - Percentage of successful completions
- **Cycle Time** (optimal: <4h) - Average time from start to completion
- **Blocked Tasks** (optimal: 0) - Tasks waiting on dependencies
- **Cost/Day** (optimal: <$50) - Daily API spending

**Color Coding:**
- 🟢 Green = Optimal range
- 🟡 Yellow = Warning (outside optimal but acceptable)
- 🔴 Red = Critical (requires attention)

**Alerts Section:**
Shows actionable alerts with specific recommended actions:
- "Queue running low → Run signal detection"
- "High failure rate → Review failed tasks"
- "Tasks blocked → Resolve dependencies"

**Health History:**
Line chart showing success rate over last 24 hours (when data available)

---

### 🔍 Signals Page

**Explore detected work opportunities**

**Features:**

1. **Summary Stats**
   - Last scan timestamp
   - Total signals count
   - Breakdown by severity (Critical, High, Medium, Low)

2. **Filtering**
   - Filter by severity: Critical, High, Medium, Low
   - Filter by type: validation_gap, test_failure, security, etc.
   - Multi-select filters (combine multiple criteria)

3. **Signal Cards**
   Each signal shows:
   - Title with severity icon (🚨 ⚠️ 💡 ℹ️)
   - Description and estimated impact
   - Evidence list (proof this is a real issue)
   - Full context (project, files, metrics)
   - **"Generate Contract" button** - Creates comprehensive task spec

**Workflow:**
```
1. Scan for signals (sidebar button)
2. Review detected signals
3. Click "Generate Contract" for signal
4. Wait 30-60s for Opus to generate contract
5. View contract in Contracts page
```

---

### 📋 Contracts Page

**View all generated contracts**

**Contract Display:**

Each contract shows:
- Risk level badge (🟢 Low, 🟡 Medium, 🟠 High, 🔴 Critical)
- Auto-executable status (✅ or ⚠️)
- Budget (max cost, max attempts)

**Details:**
- **Requirements** - Specific, measurable deliverables
- **Constraints** - What cannot change
- **Success Criteria** - Tests, metrics, benchmarks
- **Human Gates** - Where approval is mandatory

**Metadata:**
- Contract ID (for reference)
- Creation timestamp

---

### 📊 Queue Page

**Task execution monitoring**

**Status Categories:**
- ⏸️ **Pending** - Waiting to start
- ⚙️ **Executing** - Currently running
- ✅ **Completed** - Successfully finished
- ❌ **Failed** - Encountered errors

**Job Details:**
- Description
- Priority level
- Backend (Local or API)
- Job ID
- Error messages (if failed)

**Note**: Currently integrates with batch orchestrator. Full Kanban visualization coming soon.

---

## Sidebar Features

### Quick Actions

**🔄 Scan for Signals**
- Runs signal detection across entire monorepo
- Detects: validation gaps, test failures, security issues, tech debt
- Results appear in Signals page
- Takes ~5-10 seconds

**💾 Refresh Data**
- Clears cached data
- Reloads all components
- Use after external changes (CLI operations, manual file edits)

---

## Usage Patterns

### Daily Workflow

**Morning:**
1. Open dashboard → Health page
2. Check metrics and alerts
3. If "Queue running low" → Click "Scan for Signals"

**Working:**
4. Signals page → Review detected issues
5. Generate contracts for high-priority signals
6. Contracts page → Review and approve
7. Queue page → Monitor execution

**End of Day:**
8. Health page → Check success rate
9. Queue page → Review completed/failed tasks

---

### Signal → Contract → Execute Flow

**Step 1: Detect Signal**
```
Signals Page
  ↓ Click "Scan for Signals" (sidebar)
  ↓ Wait 5-10 seconds
  ↓ View results in table
```

**Step 2: Generate Contract**
```
Signals Page
  ↓ Find interesting signal
  ↓ Click "Generate Contract"
  ↓ Wait 30-60 seconds (Opus processing)
  ↓ See success message
```

**Step 3: Review Contract**
```
Contracts Page
  ↓ Find newly generated contract
  ↓ Expand to view details
  ↓ Check requirements, constraints, success criteria
  ↓ Note risk level and auto-executable status
```

**Step 4: Execute** (via CLI for now)
```bash
./cortex_mvp contract <signal_id>
# Answer: y (approve)
```

**Step 5: Monitor**
```
Queue Page
  ↓ Watch task progress
  ↓ Check for completion or errors
```

---

## Tips & Tricks

### Performance

**Dashboard is slow?**
- Click "Refresh Data" to clear cache
- Close browser tabs you're not using
- Restart dashboard: Ctrl+C and relaunch

**Signal scan taking long?**
- Normal for large repos (10-30 seconds)
- Runs in background, dashboard stays responsive

### Troubleshooting

**"No signals found" after scan:**
- Check if validation reports exist in VortexV2
- Ensure .pytest_cache has data
- Verify GOALS.md exists

**Contract generation fails:**
- Check ANTHROPIC_API_KEY is set
- Verify API key has Opus 4.5 access
- Check error message in terminal

**Queue page shows "No jobs":**
- Tasks may not have been submitted to batch system yet
- Run: `python cortex/batch/orchestrator.py list` (CLI)
- Check ~/.cortex/batches/ directory

### Best Practices

**Scan Frequency:**
- Daily morning scans
- After major code changes
- Before sprint planning

**Contract Generation:**
- Generate contracts for Critical and High signals immediately
- Batch Medium/Low signals weekly

**Health Monitoring:**
- Check at start/end of day
- Monitor during deployments
- Set up automated alerts (future feature)

---

## Keyboard Shortcuts

(Streamlit defaults)

- `R` - Rerun app (refresh)
- `C` - Clear cache
- `?` - Show keyboard shortcuts

---

## Architecture

```
Dashboard (Streamlit)
      │
      ├─ Health Page → HealthMonitor → Real-time metrics
      │
      ├─ Signals Page → SignalDetector → Scans monorepo
      │                      ↓
      │                ContractGenerator (Opus 4.5)
      │
      ├─ Contracts Page → Cached contracts (JSON)
      │
      └─ Queue Page → BatchOrchestrator → Job status
```

---

## Data Storage

All data stored in `~/.cortex/`:

```
~/.cortex/
├── latest_scan.json          # Most recent signal scan
├── signals/                  # Historical signal scans
│   └── signals_*.json
├── contracts/                # Generated contracts
│   └── contract_*.json
├── health_history/           # Health snapshots
│   └── health_*.json
└── batches/                  # Batch job queue
    └── remediation_queue.json
```

**To reset everything:**
```bash
rm -rf ~/.cortex/
# Dashboard will recreate directories on next use
```

---

## Customization

### Theme

Edit `launch_dashboard.sh` to change colors:

```bash
--theme.primaryColor "#FF6B6B"        # Accent color
--theme.backgroundColor "#0E1117"     # Background
--theme.secondaryBackgroundColor "#262730"  # Cards
```

### Port

Change default port (8501):

```bash
--server.port 8080
```

### Auto-open Browser

Disable auto-open:

```bash
--server.headless true
```

---

## Integration with CLI

**Dashboard and CLI work together:**

**Dashboard → CLI:**
- View signals in dashboard
- Copy signal ID
- Generate contract via CLI for more control

**CLI → Dashboard:**
- Run `./cortex_mvp scan` in terminal
- Refresh dashboard to see results
- View contracts in dashboard

**Recommended Workflow:**
- Use dashboard for exploration and monitoring
- Use CLI for automation and scripting

---

## Future Enhancements

Coming soon:

- [ ] In-dashboard contract approval (no CLI needed)
- [ ] Real-time execution monitoring
- [ ] Kanban-style queue visualization
- [ ] Health alerts via notifications
- [ ] Historical trend analysis
- [ ] Contract templates
- [ ] Batch job creation from dashboard
- [ ] Export reports (PDF/Markdown)

---

## Troubleshooting

### Common Issues

**1. Dashboard won't start**

Error: `No module named 'streamlit'`

Fix:
```bash
pip install streamlit
```

**2. "Signal ID not found"**

Fix: Click "Scan for Signals" first, then try again

**3. Contract generation timeout**

Fix: Opus 4.5 can take 60-90s. Be patient.

**4. Empty health metrics**

Fix: Run some tasks first via CLI to generate metrics

**5. Dashboard shows cached data**

Fix: Click "Refresh Data" in sidebar

---

## Performance Notes

**Resource Usage:**
- Memory: ~200MB (typical)
- CPU: <5% (idle), 15-30% (scanning)
- Network: Minimal (only during Opus calls)

**Response Times:**
- Page load: <1s
- Signal scan: 5-15s
- Contract generation: 30-90s
- Health update: <1s

---

## Keyboard Shortcuts Summary

| Key | Action |
|-----|--------|
| `R` | Rerun/Refresh |
| `C` | Clear cache |
| `?` | Show help |

---

## Support

**Issues?**

1. Check this guide first
2. Check `CORTEX_MVP_COMPLETE.md` for technical details
3. Check terminal output for errors
4. File issue with:
   - Error message
   - Steps to reproduce
   - Dashboard page where error occurred

---

**Built with**: Streamlit + Claude Sonnet 4.5
**Status**: Production-ready MVP
**Last Updated**: January 23, 2026
