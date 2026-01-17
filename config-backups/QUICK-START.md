# Quick Start Guide

**Goal:** Get your 5-profile iTerm2 setup working in <5 minutes.

---

## ✅ What You Get

- **Ctrl+1** → Claude Opus terminal
- **Ctrl+2** → Claude Sonnet terminal
- **Ctrl+3** → Cortex project terminal
- **Ctrl+4** → VortexV2 project terminal
- **Ctrl+5** → AlphaArena project terminal

**Plus:**
- Clickable file paths in error messages
- Red highlighting on test failures
- Git force-push protection
- Auto-environment switching (if using direnv)

---

## 🚀 New Machine Setup

### **Step 1: Clone Cortex** (if not already)
```bash
cd ~/Dev
git clone <your-cortex-repo-url> cortex
cd cortex/config-backups
```

### **Step 2: Run Restore Script**
```bash
./restore-all.sh
```

### **Step 3: Set Hotkeys (5 min)**
1. Open **iTerm2 → Settings (⌘,)**
2. Go to **Profiles** tab
3. For **each profile** (Opus, Sonnet, Cortex, VortexV2, AlphaArena):
   - Select profile
   - Click **Keys** tab
   - ✅ Check "A hotkey opens a dedicated window with this profile"
   - Click **"Configure Hotkey Window"**
   - Press the hotkey (Ctrl+1, Ctrl+2, etc.)
   - Set **Window Style:** "Full-Width Top of Screen"
   - ✅ Check "Pin hotkey window"
   - Click **OK**

### **Step 4: Test**
```bash
# From ANY app, press:
Ctrl+1  # Should open Opus terminal
Ctrl+2  # Should open Sonnet terminal
Ctrl+3  # Should open Cortex terminal
Ctrl+4  # Should open VortexV2 terminal
Ctrl+5  # Should open AlphaArena terminal
```

✅ **Working?** You're done!

---

## 🔄 Sync Changes to Backup

After modifying iTerm2 profiles or shell aliases:

```bash
cd ~/Dev/cortex/config-backups
./sync-configs.sh --commit
git push
```

---

## 🧪 Test Triggers

### **Test File Hyperlinks**
```bash
# In any profile, run:
python -c "raise Exception('test')"

# Click the "File ..." line - should open in editor
```

### **Test Error Highlighting**
```bash
# Run failing test:
pytest /path/to/failing/test.py

# "FAILED" lines should be red
```

### **Test Git Protection**
```bash
# Try to type (don't actually run!):
git push --force origin main

# Should see alert popup if typed
```

---

## 📖 Full Documentation

- **Setup details:** [README.md](README.md)
- **Complete inventory:** [INVENTORY.md](INVENTORY.md)
- **Productization ideas:** [PRODUCTIZATION.md](PRODUCTIZATION.md)
- **iTerm2 optimization guide:** [../iterm2-optimizations.md](../iterm2-optimizations.md)

---

## 🆘 Troubleshooting

### **"Profiles don't appear in iTerm2"**
```bash
# Check if file exists:
ls -la ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json

# If missing, run restore again:
./restore-all.sh
```

### **"Hotkeys don't work"**
- Check System Settings → Keyboard → Keyboard Shortcuts
- Ensure Ctrl+1-5 not used by other apps
- Restart iTerm2

### **"Triggers not activating"**
```bash
# Validate JSON:
python3 -m json.tool ~/Library/Application\ Support/iTerm2/DynamicProfiles/dev-monorepo.json

# Check trigger syntax in iTerm2:
# Settings → Profiles → [Profile] → Advanced → Triggers
```

### **"Shell aliases not working"**
```bash
# Re-source shell:
source ~/.zshrc

# Check if aliases exist:
alias | grep claude
```

---

**Last Updated:** 2026-01-17
**Time to complete:** <5 minutes
