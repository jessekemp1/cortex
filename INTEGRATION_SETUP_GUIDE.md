# Cortex-Local-Orchestrator Integration Setup Guide

**Quick Start**: Run `local-orchestrator/resolve_dependencies.sh` to install all dependencies automatically.

---

## Dependencies Required

### Core Dependencies

- **structlog** (>=23.2.0) - Structured logging for local-orchestrator
- **apscheduler** (>=3.10.0) - Task scheduling engine
- **fastapi** (>=0.104.0) - API server for event triggers
- **uvicorn** (>=0.24.0) - ASGI server
- **pydantic** (>=2.5.0) - Data validation
- **python-dotenv** (>=1.0.0) - Environment variable management
- **pytz** (>=2023.3) - Timezone support

### Why These Are Needed

- **structlog**: Local-orchestrator uses structured logging
- **apscheduler**: Required for scheduled task execution
- **fastapi/uvicorn**: Required for API server and webhooks
- **pydantic**: Data models and validation
- **python-dotenv**: Configuration management
- **pytz**: Timezone-aware scheduling

---

## Quick Resolution

### Automated (Recommended)

```bash
cd local-orchestrator
./resolve_dependencies.sh
```

This will:
1. Create virtual environment (if needed)
2. Install all dependencies
3. Verify installation
4. Report status

### Manual Installation

```bash
cd local-orchestrator

# Create venv (if needed)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify
python -c "import structlog, apscheduler, fastapi, uvicorn, pydantic; print('✓ All installed')"
```

---

## Verification

### Check Integration Availability

```bash
cd /Users/jesse.kemp/Dev
python3 -c "
import sys
sys.path.insert(0, 'cortex')
from integration.local_orchestrator import CortexLocalOrchestratorIntegration
i = CortexLocalOrchestratorIntegration()
print(f'Integration available: {i.is_available()}')
"
```

**Expected**: `Integration available: True`

### Test Full E2E

```bash
# Get recommendation
cortex next --limit 1

# Schedule it (requires dependencies)
cortex schedule

# Check scheduled agents (requires orchestrator running)
curl http://localhost:8000/api/v1/tasks 2>/dev/null | grep cortex_ || echo "Orchestrator not running"
```

---

## Troubleshooting

### "Integration available: False"

**Cause**: Dependencies not installed or not in Python path

**Solution**:
1. Run `./resolve_dependencies.sh`
2. Ensure you're using the venv Python: `which python` should show venv path
3. Verify: `python -c "import structlog; print('OK')"`

### "ModuleNotFoundError: No module named 'structlog'"

**Cause**: Dependencies installed in different Python environment

**Solution**:
1. Activate correct venv: `source local-orchestrator/venv/bin/activate`
2. Reinstall: `pip install -r requirements.txt`
3. Use venv Python explicitly: `local-orchestrator/venv/bin/python`

### "Integration available: True but schedule fails"

**Cause**: Local-orchestrator service not running

**Solution**:
1. Start orchestrator: `cd local-orchestrator && source venv/bin/activate && python orchestrator.py`
2. Or use systemd service: `sudo systemctl start local-orchestrator`

---

## Full E2E Test After Resolution

```bash
# 1. Install dependencies
cd local-orchestrator
./resolve_dependencies.sh

# 2. Activate venv
source venv/bin/activate

# 3. Start orchestrator (in background or separate terminal)
python orchestrator.py &
ORCHESTRATOR_PID=$!

# 4. Test Cortex integration
cd /Users/jesse.kemp/Dev
python3 cortex/cli.py next --limit 1
python3 cortex/cli.py schedule

# 5. Verify agent registered
sleep 2
curl http://localhost:8000/api/v1/tasks 2>/dev/null | grep cortex_

# 6. Cleanup
kill $ORCHESTRATOR_PID 2>/dev/null || true
```

---

## Status After Resolution

Once dependencies are installed:

- ✅ `CortexLocalOrchestratorIntegration.is_available()` → `True`
- ✅ `cortex schedule` command works
- ✅ Recommendations convert to agents successfully
- ✅ Agents register with local-orchestrator
- ✅ Execution history tracking active
- ✅ Learning mechanisms can access history

---

**Next Action**: Run `local-orchestrator/resolve_dependencies.sh` to enable full E2E testing.

