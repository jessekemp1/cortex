# 🚀 Cortex Launch Control

**Cortex-managed developer portal** for all your projects with web interfaces.

## Features

- **Auto-discovery**: Scans monorepo for React, Streamlit, FastAPI projects
- **Port conflict detection**: Warns before starting services that would conflict
- **Real-time status**: Shows running processes, PIDs, and port usage
- **Auto-refresh**: Updates every 10 seconds via Cortex background service
- **Quick actions**: One-click Open, Stop, Start buttons

## Quick Start

```bash
cd ~/Dev/cortex/launcher

# Start the HTTP server (port 3333)
python3 -m http.server 3333 &

# Start auto-update service
./auto_update.sh &

# Open in browser
open http://localhost:3333
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser (http://localhost:3333)               │
│  - Auto-refresh every 10s                      │
│  - Reads launcher_data.json                    │
└─────────────────────────────────────────────────┘
                     ▲
                     │ reads JSON
                     │
┌─────────────────────────────────────────────────┐
│  auto_update.sh (background service)            │
│  - Runs project_scanner.py every 10s           │
│  - Updates launcher_data.json                  │
└─────────────────────────────────────────────────┘
                     ▲
                     │ executes
                     │
┌─────────────────────────────────────────────────┐
│  project_scanner.py                             │
│  - Scans ~/Dev for web projects                │
│  - Detects running processes (lsof)            │
│  - Matches ports to projects                   │
│  - Identifies conflicts                        │
└─────────────────────────────────────────────────┘
```

## Files

- `index.html` - Launch page UI
- `launcher.js` - Frontend JavaScript (render projects, handle clicks)
- `project_scanner.py` - Python scanner (detect projects + ports)
- `launcher_data.json` - Generated data (auto-updated every 10s)
- `auto_update.sh` - Background service (keeps data fresh)
- `auto_update.log` - Service logs

## Detected Projects

Currently tracking:

1. **Cortex Command Center** (React, port 5173)
2. **Cortex Orchestration** (Streamlit, port 8502)
3. **Cortex Bridge API** (FastAPI, port 8765)
4. **VortexV2** (Mixed: API @ 8000, UI @ 8503)
5. **VortexV3** (React, port 5173)
6. **Alpha Arena** (Streamlit, port 8503)
7. **Kempion Research** (React, port 5173)
8. **DJ CoPilot** (React)

## Port Conflict Resolution

When conflicts are detected (red ⚠️ badge):

1. **Stop conflicting service** - Check which one is running, stop it
2. **Change port** - Update vite.config.ts or streamlit config
3. **Start on different port** - Use `--port XXXX` flag

Example: To run Cortex Command Center on 5174 instead:
```bash
cd ~/Dev/cortex/site
npm run dev -- --port 5174
```

## Adding New Projects

Edit `project_scanner.py` and add to `known_projects` dict:

```python
"my-project/path": {
    "name": "My Project",
    "type": "react"  # or "streamlit", "fastapi", "mixed"
}
```

The scanner will auto-detect ports and start commands based on type.

## Stopping Services

```bash
# Stop HTTP server
lsof -i :3333 | grep LISTEN | awk '{print $2}' | xargs kill

# Stop auto-update service
ps aux | grep auto_update.sh | grep -v grep | awk '{print $2}' | xargs kill
```

## Integration with Cortex

The launcher is **Cortex-managed**, meaning:

- Auto-discovers new projects when you add them
- Updates status without manual refresh
- Prevents port conflicts before they happen
- Provides single source of truth for "what's running?"

Future: Cortex CLI integration - `/launch project-name` to start services directly.

## Troubleshooting

**"Port Conflicts showing incorrectly"**
- Run `python3 project_scanner.py` manually to regenerate data
- Check if projects are actually using different ports in their configs

**"Projects not showing"**
- Verify project exists in `~/Dev/{path}`
- Add to `known_projects` in project_scanner.py
- Check logs: `tail -f auto_update.log`

**"Auto-refresh not working"**
- Check if auto_update.sh is running: `ps aux | grep auto_update`
- Look for errors in auto_update.log
- Verify browser isn't blocking fetch() calls

## Live Demo

Open **http://localhost:3333** to see your full development landscape!
