# Dependency Resolution Plan: Full E2E Execution

**Date**: December 8, 2025  
**Status**: ⚠️ **DEPENDENCIES REQUIRED**  
**Priority**: HIGH - Blocks full E2E testing with active tasks

---

## Problem Statement

The Cortex-local-orchestrator integration is **structurally complete** but cannot execute fully because local-orchestrator dependencies are not installed. This prevents:

- Full agent registration
- Actual task scheduling
- Execution history tracking
- Complete E2E testing with active tasks

---

## Missing Dependencies

### Required Packages

From `local-orchestrator/requirements.txt`:

1. **structlog** (>=23.2.0) - Structured logging
2. **apscheduler** (>=3.10.0) - Task scheduling
3. **fastapi** (>=0.104.0) - API server
4. **uvicorn** (>=0.24.0) - ASGI server
5. **pydantic** (>=2.5.0) - Data validation
6. **python-dotenv** (>=1.0.0) - Environment variables
7. **pytz** (>=2023.3) - Timezone support

### Current Status

**System Python**: Missing all dependencies  
**Virtual Environment**: Not checked (may have dependencies)

---

## Resolution Plan

### Option 1: Install in System Python (Quick Test)

**Pros**: Fast, immediate testing  
**Cons**: System-wide installation

```bash
# Install all dependencies
pip3 install structlog>=23.2.0 apscheduler>=3.10.0 fastapi>=0.104.0 uvicorn>=0.24.0 pydantic>=2.5.0 python-dotenv>=1.0.0 pytz>=2023.3

# Verify installation
python3 -c "import structlog, apscheduler, fastapi, uvicorn, pydantic; print('✓ All dependencies installed')"
```

### Option 2: Use Virtual Environment (Recommended)

**Pros**: Isolated, clean, best practice  
**Cons**: Requires venv setup

```bash
# Create venv
cd local-orchestrator
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify
python -c "import structlog, apscheduler, fastapi, uvicorn, pydantic; print('✓ All dependencies installed')"
```

### Option 3: Use Existing Virtual Environment

If a venv already exists:

```bash
# Activate existing venv
cd local-orchestrator
source venv/bin/activate  # or: . venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Verify
python -c "import structlog, apscheduler, fastapi, uvicorn, pydantic; print('✓ All dependencies installed')"
```

---

## Implementation Steps

### Step 1: Check Current State

```bash
cd /Users/jesse.kemp/Dev/local-orchestrator

# Check if venv exists
if [ -d "venv" ]; then
    echo "✓ Virtual environment exists"
    source venv/bin/activate
    pip list | grep -E "structlog|apscheduler|fastapi|uvicorn|pydantic"
else
    echo "⚠ No virtual environment found"
fi
```

### Step 2: Install Dependencies

**If venv exists**:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**If venv doesn't exist**:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Verify Installation

```bash
python -c "
import sys
deps = ['structlog', 'apscheduler', 'fastapi', 'uvicorn', 'pydantic', 'python_dotenv', 'pytz']
missing = [d for d in deps if __import__('importlib').util.find_spec(d.replace('_', '-')) is None]
if missing:
    print(f'✗ Missing: {missing}')
    sys.exit(1)
else:
    print('✓ All dependencies installed')
"
```

### Step 4: Test Integration

```bash
# Test local-orchestrator imports
python -c "
from orchestrator import Orchestrator
from agents.task_agent import ScheduledTaskAgent
print('✓ local-orchestrator imports work')
"

# Test Cortex integration
cd /Users/jesse.kemp/Dev
python3 -c "
import sys
sys.path.insert(0, 'cortex')
from integration.local_orchestrator import CortexLocalOrchestratorIntegration
i = CortexLocalOrchestratorIntegration()
print(f'✓ Integration available: {i.is_available()}')
"
```

### Step 5: Run Full E2E Test

```bash
# Get recommendation and schedule it
cd /Users/jesse.kemp/Dev
python3 cortex/cli.py next --limit 1
python3 cortex/cli.py schedule
```

---

## Automated Resolution Script

Create a script to handle all of this:

```bash
#!/bin/bash
# resolve_dependencies.sh

set -e

ORCHESTRATOR_DIR="/Users/jesse.kemp/Dev/local-orchestrator"
cd "$ORCHESTRATOR_DIR"

echo "Checking dependencies..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Verify
echo "Verifying installation..."
python -c "
import sys
deps = ['structlog', 'apscheduler', 'fastapi', 'uvicorn', 'pydantic']
missing = [d for d in deps if __import__('importlib').util.find_spec(d) is None]
if missing:
    print(f'✗ Missing: {missing}')
    sys.exit(1)
else:
    print('✓ All dependencies installed')
"

echo ""
echo "✓ Dependencies resolved!"
echo ""
echo "To use:"
echo "  cd $ORCHESTRATOR_DIR"
echo "  source venv/bin/activate"
echo "  python orchestrator.py"
```

---

## Testing After Resolution

### Test 1: Local-Orchestrator Standalone

```bash
cd local-orchestrator
source venv/bin/activate
python -c "from orchestrator import Orchestrator; o = Orchestrator(); print('✓ Orchestrator works')"
```

### Test 2: Cortex Integration

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

### Test 3: Full E2E with Active Tasks

```bash
# Get recommendation
cortex next --limit 1

# Schedule it
cortex schedule

# Verify it's registered (if orchestrator running)
curl http://localhost:8000/api/v1/tasks | grep cortex_
```

---

## Expected Outcomes

### After Resolution

1. ✅ `CortexLocalOrchestratorIntegration.is_available()` returns `True`
2. ✅ `cortex schedule` command works
3. ✅ Recommendations can be converted to agents
4. ✅ Agents can be registered with local-orchestrator
5. ✅ Execution history tracking works
6. ✅ Learning mechanisms can access history

### Verification Commands

```bash
# Check integration
python3 -c "
import sys
sys.path.insert(0, 'cortex')
from integration.local_orchestrator import CortexLocalOrchestratorIntegration
i = CortexLocalOrchestratorIntegration()
assert i.is_available(), 'Integration should be available'
print('✓ Integration available')
"

# Test scheduling
cortex schedule --help  # Should work
cortex schedule  # Should attempt to schedule (may need orchestrator running)
```

---

## Next Steps

1. **Run resolution script** (or manual installation)
2. **Verify dependencies installed**
3. **Test integration availability**
4. **Run full E2E tests**
5. **Start local-orchestrator service** (optional, for full testing)
6. **Test end-to-end scheduling**

---

## Notes

- Dependencies are only needed for **full execution**
- **Code structure is complete** - just needs runtime environment
- Virtual environment is **recommended** to avoid system-wide installs
- Can test **structure** without dependencies (current state)
- Can test **full E2E** with dependencies (after resolution)

---

**Status**: ⚠️ **PLAN READY** - Execute resolution steps to enable full E2E testing

