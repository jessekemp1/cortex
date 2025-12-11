# Quick Dependency Fix

**Problem**: Local-orchestrator dependencies missing, blocking full E2E testing

**Solution**: Run automated installation script

```bash
cd local-orchestrator
./resolve_dependencies.sh
```

**Verify**:
```bash
source venv/bin/activate
python -c "import structlog, apscheduler, fastapi, uvicorn, pydantic; print('✓ All installed')"
```

**Test Integration**:
```bash
cd /Users/jesse.kemp/Dev
local-orchestrator/venv/bin/python -c "
import sys
sys.path.insert(0, 'cortex')
from integration.local_orchestrator import CortexLocalOrchestratorIntegration
i = CortexLocalOrchestratorIntegration()
print(f'Integration available: {i.is_available()}')
"
```

**Full Details**: See `cortex/DEPENDENCY_RESOLUTION_PLAN.md`
