# iTerm2 Multi-Project Setup (Actually Useful Edition)

**Goal:** Ctrl+1-5 opens project-specific tabs (Opus, Sonnet, Cortex, VortexV2, Arena) instantly.
**Time to implement:** 2 minutes (automated script).
**Maintenance cost:** Zero.

---

## The 20% That Delivers 80%

### 1. Tab Shortcuts Per Project (⭐️ DO THIS FIRST)

**What:** Ctrl+1 = Opus tab. Ctrl+2 = Sonnet tab. Ctrl+3 = Cortex. Ctrl+4 = VortexV2. Ctrl+5 = Arena.

**Why:** Zero context switching time. All projects in one window. Clean tab organization.

**Setup:**
```bash
# One-command install (from cortex directory)
./config-backups/cleanup-iterm2-profiles.sh
```

**What it does:**
1. Removes old static profiles (if any)
2. Installs clean dynamic profiles with proper working directories
3. Configures Ctrl+1-5 keyboard shortcuts to open tabs
4. Sets up smart triggers (error highlighting, force-push warnings, etc.)

**Result:** Press Ctrl+1 = new Opus tab. Ctrl+2 = new Sonnet tab. Etc.

---

### 2. Fix Shell Alias Loading (Why Your Opus Profile Crashes)

**Problem:** Custom commands in iTerm2 don't load your shell aliases by default.

**Solution:** Use login shell flag for commands that need aliases:
```bash
/bin/zsh -l -c 'your-command-here'
```

**For your opus profile:**
- Settings → Profiles → opus → General → Command
- Enable "Custom Command"
- Set to: `/bin/zsh -l -c 'claude --model opus'`

---

### 3. Auto-Environment Switching with direnv (Optional but High Value)

**What:** `cd ~/Dev/Vortex/VortexV2` automatically loads Python venv, sets DB URLs, exports env vars.

**Setup:**
```bash
# Install
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc

# Per-project config (example: VortexV2)
cd ~/Dev/Vortex/VortexV2
cat > .envrc << 'EOF'
# Auto-activate venv
layout python python3.11

# Load environment variables
export DATABASE_URL="postgresql://localhost:5432/vortex_dev"
export ENVIRONMENT="development"

# Project bins in PATH
PATH_add bin
PATH_add .venv/bin
EOF

# Approve it (required once per project)
direnv allow
```

**Result:** No more manual `source .venv/bin/activate` or `export $(cat .env)`. Just cd.

---

### 4. Git Worktrees for Parallel AI Sessions (Advanced)

**What:** Run 3+ Claude sessions on different features simultaneously without conflicts.

**Setup:**
```bash
# Main repo stays on main branch
cd ~/Dev/alpha_arena

# Create isolated checkouts for parallel work
git worktree add ../arena-feature-auth feature/auth
git worktree add ../arena-refactor-db refactor/database
git worktree add ../arena-new-model feature/lstm-v2

# Launch Claude in each (separate iTerm windows)
cd ../arena-feature-auth && claude    # Terminal 1
cd ../arena-refactor-db && claude     # Terminal 2
cd ../arena-new-model && claude       # Terminal 3
```

**Result:** 3 AI agents working in parallel. No file conflicts. Merge when ready.

---

## What NOT to Do

❌ **tmuxinator** - Unnecessary for local dev (adds config burden)
❌ **Python API scripts** - Use profiles instead
❌ **Complex status bars** - Your prompt already shows git branch
❌ **AppleScript automation** - Premature optimization
❌ **Dynamic profile JSON** - Only if you need version control (you don't yet)

---

## Productivity Metrics That Actually Matter

Track these monthly:
- **Deep work hours/day** (target: 4+ hrs uninterrupted)
- **Context switches/day** (minimize)
- **Time to full project context** (should be <5 seconds with hotkeys)

Don't track:
- Lines of code
- Commits per day
- Tool configurations added

---

## Your Current Setup Assessment

**You already have:**
- ✅ 37 slash commands (`/status`, `/next`, `/briefing`, etc.)
- ✅ Project-specific test commands
- ✅ Cortex intelligence system
- ✅ Git workflow commands (`/pr`, `/commit`)
- ✅ Ctrl+1-5 tab shortcuts (Opus, Sonnet, Cortex, VortexV2, Arena)
- ✅ Smart triggers (error highlighting, anti-patterns)
- ✅ Automated profile management

**Optional enhancements:**
- ⚠️ direnv auto-environment (medium ROI)
- ⚠️ Git worktrees for parallel sessions (only if needed)

**You don't need:**
- ❌ tmux (your workflow is local-first)
- ❌ Complex automation scripts
- ❌ Window arrangement presets
- ❌ Hotkey windows (tabs are cleaner for your workflow)

---

## Implementation Priority

### Phase 1: Automated Setup (2 minutes) ✅
```bash
cd ~/Dev/cortex
./config-backups/cleanup-iterm2-profiles.sh
```

**Done!** You now have:
- ✅ Ctrl+1-5 tab shortcuts configured
- ✅ Clean profiles (Opus, Sonnet, Cortex, VortexV2, Arena)
- ✅ Smart triggers (error highlighting, force-push warnings)
- ✅ Proper working directories for each project

### Phase 2: Reduce Friction (Optional, 30 minutes)
4. Set up direnv in your top 2 most-used projects
5. Customize badge colors/text if needed
6. Add project-specific triggers for log patterns

### Phase 3: Advanced (Only If Needed)
7. Git worktrees if you're running parallel AI sessions
8. Additional keyboard shortcuts for other workflows
9. Profile inheritance if you need shared settings

**STOP after Phase 1 unless you have specific pain points.**

---

## The Real Productivity Lever

Your terminal optimization should be **invisible**. If you're thinking about your terminal setup, it's not optimized—it's over-engineered.

The best setup:
- Ctrl+[1-6] muscle memory (no thought required)
- Auto-environment switching (no manual exports)
- Everything else: defaults

Configuration is liability. Simplicity is speed.

---

## Quick Reference: Your Tab Shortcuts

```
Ctrl+1  →  Opus          (🤖 Claude Opus in /Dev)
Ctrl+2  →  Sonnet        (🤖 Claude Sonnet in /Dev)
Ctrl+3  →  Cortex        (🧠 Intelligence Layer)
Ctrl+4  →  VortexV2      (🌪️  Weather API)
Ctrl+5  →  AlphaArena    (📊 Trading System)
```

**From anywhere in iTerm2:** Ctrl+number = new tab with project context.
**No hunting. No switching. No friction.**

---

*Last updated: 2026-01-18*
*Maintenance schedule: Review quarterly, delete what you don't use.*
