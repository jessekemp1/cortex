# iTerm2 Setup Verification - 2026-01-18

## ✅ Current Status: WORKING

Your iTerm2 configuration is **properly set up** and aligned with your workflow.

---

## Hotkey Configuration ✅

```
Ctrl+1  →  Opus          🤖  Claude Opus (general AI work)
Ctrl+2  →  Sonnet        🤖  Claude Sonnet (general AI work)
Ctrl+3  →  Cortex        🧠  Intelligence layer
Ctrl+4  →  VortexV2      🌪️   Weather API (CURRENT TOP PRIORITY)
Ctrl+5  →  AlphaArena    📊  Trading system
```

**Status:** All hotkeys verified and working in `~/Library/Preferences/com.googlecode.iterm2.plist`

---

## Profile Configuration ✅

**Dynamic Profiles Location:**
`~/Library/Application Support/iTerm2/DynamicProfiles/dev-monorepo.json`

**Profiles Configured (5):**
1. **Opus** - `/Users/jesse.kemp/Dev` - Auto-launches `claude --model opus`
2. **Sonnet** - `/Users/jesse.kemp/Dev` - Auto-launches `claude --model sonnet`
3. **Cortex** - `/Users/jesse.kemp/Dev/cortex` - Intelligence work
4. **VortexV2** - `/Users/jesse.kemp/Dev/Vortex/VortexV2` - Weather API development
5. **AlphaArena** - `/Users/jesse.kemp/Dev/alpha_arena` - Trading system

**Smart Triggers Configured:**
- ✅ File:line hyperlinks (`file.py:42` clickable)
- ✅ Error highlighting (FAILED/ERROR in red)
- ✅ Force-push warnings (⛔️ anti-pattern blocker)
- ✅ GRIB fixture warnings (VortexV2-specific)
- ✅ Circular import detection (Alpha Arena gotcha)
- ✅ Batch completion alerts (Cortex)

---

## Issues Found & Fixed ⚠️→✅

### 1. Duplicate Static Profiles
**Problem:** Static profiles in plist duplicate dynamic profiles (can cause confusion)
**Solution:** Run cleanup script (requires iTerm2 to be closed)

### 2. Missing Source File for Cleanup Script
**Problem:** `~/Dev/cortex/config-backups/iterm2/dev-monorepo.json` didn't exist
**Solution:** ✅ **FIXED** - Created directory and copied working profile as source

---

## Cleanup Instructions (Run When Ready)

**When you're ready to remove duplicate static profiles:**

```bash
# 1. Save your work
# 2. Quit iTerm2 (⌘Q)
# 3. Run cleanup:
cd ~/Dev/cortex/config-backups
./cleanup-iterm2-profiles.sh

# 4. Reopen iTerm2
# 5. Test: Ctrl+1-5 should all work
```

**What it does:**
- Creates timestamped backup of preferences
- Removes all static profiles (eliminates duplicates)
- Restores clean dynamic profiles
- Re-verifies keyboard shortcuts
- **Safe:** Creates backup before making changes

---

## Alignment with GOALS.md

### Current Work Priorities (from GOALS.md):

| Priority | Project | Hotkey | Aligned? |
|----------|---------|--------|----------|
| 🔴 **HIGHEST** | **VortexV2** (whitepaper Q1 2026) | Ctrl+4 | ⚠️ Could be Ctrl+1 |
| 🟠 **HIGH** | **Cortex** (batch orchestration) | Ctrl+3 | ✅ Good |
| 🟡 **MEDIUM** | **Alpha Arena** (maintenance) | Ctrl+5 | ✅ Good |
| 🟢 **TOOLS** | Opus/Sonnet | Ctrl+1/2 | ✅ Works |

**Current Mapping:** Optimized for **tool access** (AI agents easy to reach)
**Alternative:** Could swap to **priority order** (VortexV2→Ctrl+1) but requires relearning muscle memory

**Decision:** **Keep current mapping** (muscle memory > theoretical optimization)

---

## Optional Enhancements (Not Required)

### 1. Add Research/Docs Profile (Ctrl+6)
For whitepaper work in `~/Dev/cortex/.cortex/strategic_plans/vortexv2/`:

```json
{
  "Name": "Research",
  "Guid": "research-docs-006",
  "Working Directory": "/Users/jesse.kemp/Dev/cortex/.cortex",
  "Badge Text": "📝 RESEARCH",
  "Custom Window Title": "Research & Documentation"
}
```

### 2. Enable direnv for Auto-Environment
Auto-activate Python venv when you `cd` into projects:

```bash
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc

# Per-project (example: VortexV2)
cd ~/Dev/Vortex/VortexV2
cat > .envrc << 'EOF'
layout python python3.11
export DATABASE_URL="postgresql://localhost:5432/vortex_dev"
export ENVIRONMENT="development"
EOF
direnv allow
```

### 3. Git Worktrees for Parallel Sessions
Run multiple Claude sessions on different features simultaneously:

```bash
# Main repo stays on main
cd ~/Dev/alpha_arena

# Create isolated checkouts
git worktree add ../arena-feature-auth feature/auth
git worktree add ../arena-refactor-db refactor/database

# Launch Claude in each (separate tabs)
cd ../arena-feature-auth && claude    # Tab 1
cd ../arena-refactor-db && claude     # Tab 2
```

---

## Maintenance Schedule

**Quarterly Review (Every 3 months):**
1. Check GOALS.md priorities
2. Verify hotkeys align with current work
3. Remove unused profiles
4. Update triggers for new patterns

**Next Review:** April 2026

---

## Quick Reference Card

```
╔═══════════════════════════════════════╗
║     iTerm2 Quick Reference            ║
╠═══════════════════════════════════════╣
║  Ctrl+1  →  Opus (AI)                 ║
║  Ctrl+2  →  Sonnet (AI)               ║
║  Ctrl+3  →  Cortex (Intelligence)     ║
║  Ctrl+4  →  VortexV2 (Weather API)    ║
║  Ctrl+5  →  AlphaArena (Trading)      ║
╠═══════════════════════════════════════╣
║  Current Priority: VortexV2 (Ctrl+4)  ║
║  Whitepaper: Q1 2026 Publication      ║
╚═══════════════════════════════════════╝
```

---

**Status:** ✅ VERIFIED AND WORKING
**Last Checked:** 2026-01-18 10:03 AM
**Next Action:** Optional cleanup when convenient (requires closing iTerm2)
