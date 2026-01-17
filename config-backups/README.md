# Development Environment Configuration Backups

**Last Updated:** 2026-01-17
**Purpose:** Version-controlled backups of all development environment configurations for disaster recovery and productization.

---

## 📦 What's Backed Up

### **iTerm2 Configuration**
- **Location:** `iterm2/dev-monorepo.json`
- **Live Path:** `~/Library/Application Support/iTerm2/DynamicProfiles/dev-monorepo.json`
- **Contents:**
  - 5 project profiles (Opus, Sonnet, Cortex, VortexV2, AlphaArena)
  - Productivity triggers (file hyperlinks, error highlighting, git safety)
  - Custom colors, badges, working directories
- **Hotkey Mapping:**
  - Ctrl+1 → Opus (Claude Opus AI)
  - Ctrl+2 → Sonnet (Claude Sonnet AI)
  - Ctrl+3 → Cortex (Intelligence project)
  - Ctrl+4 → VortexV2 (Weather API)
  - Ctrl+5 → AlphaArena (Trading system)

### **Claude Code Configuration**
- **Location:** `claude/settings.json`
- **Live Path:** TBD (not found in standard locations)
- **Shell Aliases:** `shell/claude-aliases.sh`
- **Contents:**
  - Model switching aliases (claude-opus, claude-sonnet, claude-haiku)
  - Session management functions
  - iTerm2 integration scripts

### **Shell Configuration**
- **Location:** `shell/claude-aliases.sh`
- **Live Path:** Extracted from `~/.zshrc`
- **Contents:**
  - Claude model switching commands
  - Session management helpers
  - iTerm2 window automation

---

## 🔄 Restore Instructions

### **Restore iTerm2 Profiles**
```bash
cp ~/Dev/cortex/config-backups/iterm2/dev-monorepo.json \
   ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json

# Profiles load automatically (no restart needed)
# Assign hotkeys: Settings → Profiles → Keys → Configure Hotkey Window
```

### **Restore Shell Aliases**
```bash
cat ~/Dev/cortex/config-backups/shell/claude-aliases.sh >> ~/.zshrc
source ~/.zshrc
```

---

## 📝 Triggers Reference

All 5 profiles include these productivity triggers:

### **1. File Path Hyperlinks**
```regex
File "([^"]+)", line (\d+)       → Clickable file://path:line
([a-zA-Z0-9_/.\\-]+\.py):(\d+)   → Clickable file:line references
```

### **2. Error Highlighting**
```regex
(FAILED|ERROR|AssertionError)    → Red highlight (impossible to miss)
```

### **3. Git Safety Net**
```regex
force.*push.*(main|master)       → Alert: "⛔️ BLOCKED: Never force push to main"
```

### **Project-Specific Triggers:**
- **Cortex:** Batch job completion notifications
- **VortexV2:** Yellow highlight for missing GRIB fixtures
- **AlphaArena:** Yellow highlight for circular import warnings

---

## 🔧 Maintenance

### **Update Backups**
Run after any configuration changes:
```bash
# iTerm2
cp ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json \
   ~/Dev/cortex/config-backups/iterm2/dev-monorepo.json

# Shell aliases
grep -A 10 "# Claude" ~/.zshrc > ~/Dev/cortex/config-backups/shell/claude-aliases.sh

# Commit changes
cd ~/Dev/cortex
git add config-backups/
git commit -m "chore: Update environment config backups"
```

### **Sync Across Machines**
```bash
# On new machine after git clone
cd ~/Dev/cortex
./config-backups/restore-all.sh   # (to be created)
```

---

## 🎯 Productization Opportunities

### **1. iTerm2 Profile Generator**
- Input: Project list (name, path, emoji)
- Output: Dynamic profiles JSON with triggers
- Use case: Onboard new team members instantly

### **2. Claude Code Session Manager**
- GUI or TUI for model switching
- Session persistence across restarts
- Context tracking per project

### **3. Dev Environment Bootstrap Script**
- One command to:
  - Install iTerm2 + profiles
  - Configure shell aliases
  - Set up hotkeys
  - Validate installations

---

## 📚 Related Documentation

- [iTerm2 Optimizations Guide](../iterm2-optimizations.md)
- [CLAUDE.md](../CLAUDE.md) - Development rules and conventions
- [GOALS.md](../GOALS.md) - Active priorities

---

## 🔒 Security Notes

- **API Keys:** NOT stored in this backup (use system keychain)
- **Secrets:** .env files excluded from git
- **Credentials:** Claude API key managed via keychain, not shell aliases

---

## 📅 Backup History

| Date | Change | Commit |
|------|--------|--------|
| 2026-01-17 | Initial backup structure created | TBD |
| 2026-01-17 | Added Phase 1 triggers to all profiles | TBD |

---

**Maintained by:** Cortex Intelligence System
**Auto-sync:** TBD (future: git pre-commit hook)
