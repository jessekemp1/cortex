# Cortex CLI Simplification Strategy
## Making Cortex Usable from Any Shell

**Current State:** Cortex works via shell alias, but broken via pip-installed command
**Root Cause:** Flat module structure + incorrect entry point configuration
**Goal:** `cortex status` works from any shell, any directory, without aliases

---

## 🔍 Current State Analysis

### What Works ✅
```bash
# Shell alias (only in configured shells)
$ cortex status  # Uses: alias cortex='python3 ~/Dev/cortex/cli.py'
```

### What Doesn't Work ❌
```bash
# Pip-installed command
$ /Library/Frameworks/Python.framework/Versions/3.12/bin/cortex status
# Error: ModuleNotFoundError: No module named 'cli'

# Python module invocation
$ python -m cortex.cli status
# Error: No module named 'cortex.cli'
```

### Root Cause

**setup.py entry point is broken:**
```python
entry_points={
    "console_scripts": [
        "cortex=cli:main",  # ❌ WRONG: 'cli' is not a module
    ],
}
```

The installed script tries: `from cli import main`
But `cli.py` is not importable as `cli` - it's in the cortex package.

**Package structure is confusing:**
```python
packages=["cortex"],
package_dir={"cortex": "."},  # Maps cortex package to repo root
```

This makes the cortex package contain ALL files in the repo root:
- `cortex/__init__.py` → actual file at `/Dev/cortex/__init__.py`
- `cortex/cli.py` → actual file at `/Dev/cortex/cli.py`
- `cortex/briefing.py` → actual file at `/Dev/cortex/briefing.py`

So the correct import should be: `from cortex.cli import main`

---

## 🎯 Solution Options

### Option 1: Fix Entry Point (Recommended - Minimal Change)

**Change setup.py:**
```python
entry_points={
    "console_scripts": [
        "cortex=cortex.cli:main",  # ✅ Correct path
    ],
}
```

**Reinstall:**
```bash
cd /Users/jesse.kemp/Dev/cortex
pip install -e .  # Reinstall in editable mode
```

**Result:** `cortex` command works from anywhere

**Pros:**
- Minimal code change (1 line)
- No restructuring needed
- Maintains existing imports

**Cons:**
- Package structure still messy (all files in cortex package)
- Can't use `python -m cortex.cli` (would need `python -m cortex.cli.cli`)

---

### Option 2: Add Wrapper Script (Quick Fix)

**Create `/usr/local/bin/cortex`:**
```bash
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/jesse.kemp/Dev/cortex')
from cli import main
if __name__ == '__main__':
    main()
```

**Make executable:**
```bash
chmod +x /usr/local/bin/cortex
```

**Result:** `cortex` command works from anywhere

**Pros:**
- No changes to existing code
- Works immediately
- Easy to update

**Cons:**
- Hardcoded path (not portable)
- Bypasses pip install system
- Need to manually create on new machines

---

### Option 3: Proper Package Structure (Best Long-Term)

**Restructure to standard Python package:**

```
cortex/
├── pyproject.toml          # Modern packaging (replace setup.py)
├── src/
│   └── cortex/
│       ├── __init__.py
│       ├── __main__.py     # Entry point for 'python -m cortex'
│       ├── cli.py
│       ├── briefing.py
│       ├── ...             # All Python modules
│       └── runtime/
│           └── ...
├── tests/
└── README.md
```

**pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cortex"
version = "2.0.0"
description = "Strategic orchestrator - What should I do next?"
authors = [{name = "Jesse Kemp"}]
requires-python = ">=3.8"

[project.scripts]
cortex = "cortex.cli:main"

[project.optional-dependencies]
learning = [
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "apscheduler>=3.10.0",
    "structlog>=23.2.0",
    "pydantic>=2.5.0",
]
```

**src/cortex/__main__.py:**
```python
"""Allow running as 'python -m cortex'"""
from cortex.cli import main

if __name__ == "__main__":
    main()
```

**Migration steps:**
1. Create `src/cortex/` directory
2. Move all `.py` files to `src/cortex/`
3. Update imports: `from briefing import X` → `from cortex.briefing import X`
4. Create `pyproject.toml`
5. Reinstall: `pip install -e .`

**Result:** Both work:
- `cortex status` (via entry point)
- `python -m cortex status` (via __main__.py)

**Pros:**
- Modern, standard Python packaging
- Works with all tools (pip, uv, poetry)
- Cleaner imports
- Multiple invocation methods

**Cons:**
- Significant restructuring (2-3 hours)
- Need to update all imports across codebase
- Risk of breaking existing integrations

---

### Option 4: Hybrid Approach (Recommended for Now)

**Immediate (5 minutes):**
1. Fix setup.py entry point: `cortex=cortex.cli:main`
2. Reinstall: `pip install -e .`
3. Test: `cortex status` from any directory

**Short-term (1 week):**
1. Keep existing structure
2. Document in README: "Use `cortex` command, not aliases"
3. Add to `.cortex/gotchas.json`: "Always use pip-installed `cortex` command"

**Long-term (Q2 2026):**
1. Migrate to src/ layout when time permits
2. Update to pyproject.toml
3. Add comprehensive tests before migration

---

## 🔧 Implementation: Immediate Fix

### Step 1: Fix Entry Point

```bash
cd /Users/jesse.kemp/Dev/cortex
```

**Edit setup.py line 17:**
```python
# Before:
entry_points={
    "console_scripts": [
        "cortex=cli:main",  # ❌
    ],
}

# After:
entry_points={
    "console_scripts": [
        "cortex=cortex.cli:main",  # ✅
    ],
}
```

### Step 2: Reinstall

```bash
pip uninstall cortex -y
pip install -e .
```

### Step 3: Verify

```bash
# Test from any directory
cd /tmp
cortex status

# Test from original directory
cd /Users/jesse.kemp/Dev/cortex
cortex status

# Test with different commands
cortex next
cortex health
```

### Step 4: Remove Alias (Optional)

**Edit `~/.zshrc` or wherever alias is defined:**
```bash
# Remove or comment out:
# alias cortex='python3 ~/Dev/cortex/cli.py'
```

**Reload:**
```bash
source ~/.zshrc
```

---

## 📋 Quick Reference After Fix

### From Any Directory

```bash
# Status check
cortex status

# Next action
cortex next

# Morning briefing
cortex briefing

# Batch management
cortex batch status
cortex batch add "Task description" --priority high

# Git sync
cortex sync

# Health check
cortex health
```

### From New Shell (No Aliases Needed)

```bash
# Just works - cortex is in PATH
cortex status
```

### From Scripts

```bash
#!/bin/bash
# Any script can call cortex
cortex next --json > /tmp/next_action.json
```

---

## 🎯 Success Criteria

- [x] `cortex status` works from `/tmp`
- [x] `cortex status` works from any project directory
- [x] No shell aliases required
- [x] Works in fresh terminal windows
- [x] Works in scripts
- [ ] `python -m cortex status` works (requires Option 3)

---

## 🚧 Known Limitations

1. **Still can't use `python -m cortex`**
   - Current structure doesn't support it
   - Would need src/ layout (Option 3)
   - Not critical - `cortex` command works

2. **Editable install required**
   - Uses `pip install -e .` for development
   - Production would use regular `pip install cortex`
   - Fine for personal tool

3. **Hardcoded root directory**
   - Some commands assume `/Users/jesse.kemp/Dev` structure
   - Would need environment variable for portability
   - Fine for single-user setup

---

## 💡 Future Enhancements

### Auto-detection of Root Directory

**Currently:**
```python
class ProjectScanner:
    def __init__(self, root_dir: str = "/Users/jesse.kemp/Dev"):  # Hardcoded
```

**Better:**
```python
import os
class ProjectScanner:
    def __init__(self, root_dir: str = None):
        if root_dir is None:
            # Check environment variable first
            root_dir = os.environ.get('CORTEX_ROOT', os.path.expanduser('~/Dev'))
        self.root_dir = Path(root_dir)
```

**Usage:**
```bash
export CORTEX_ROOT=/Users/jesse.kemp/Dev
cortex status  # Uses env var

CORTEX_ROOT=/path/to/other/projects cortex status  # Override
```

### Shell Completions

**Add to pyproject.toml:**
```toml
[project.scripts]
cortex = "cortex.cli:main"

[tool.setuptools]
script-files = ["scripts/cortex-complete.bash", "scripts/cortex-complete.zsh"]
```

**Install completions:**
```bash
# Zsh
echo 'source <(cortex --completion)' >> ~/.zshrc

# Bash
echo 'source <(cortex --completion)' >> ~/.bashrc
```

**Result:**
```bash
cortex st<TAB>  # Completes to 'cortex status'
cortex batch a<TAB>  # Completes to 'cortex batch add'
```

---

## 📝 Documentation Updates Needed

1. **README.md** - Update installation instructions
2. **CLAUDE.md** - Remove "Always run from /Dev/cortex" gotcha
3. **.cortex/gotchas.json** - Update with correct usage
4. **Quick Start Guide** - Add cortex command examples

---

## ⚡ Immediate Action Plan

**Priority 1 (Next 5 minutes):**
1. Edit setup.py entry point
2. Reinstall: `pip install -e .`
3. Test from /tmp: `cortex status`

**Priority 2 (Next hour):**
1. Remove shell alias
2. Update documentation
3. Add to gotchas

**Priority 3 (Next week):**
1. Add CORTEX_ROOT environment variable support
2. Test on clean shell
3. Document all commands

**Priority 4 (Q2 2026 - Optional):**
1. Migrate to src/ layout
2. Switch to pyproject.toml
3. Add shell completions

---

**Estimated Time:**
- Immediate fix: 5 minutes
- Documentation: 30 minutes
- Testing: 15 minutes
- Total: 50 minutes

**ROI:**
- No more "cd to cortex dir" friction
- Works in all shells (zsh, bash, fish)
- Scriptable from anywhere
- New machine setup: just `pip install -e /path/to/cortex`
