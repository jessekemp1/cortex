# DISASTER RECOVERY PLAYBOOK
## Cortex Portfolio - Recovery Procedures

**Version**: 1.0  
**Last Updated**: 2026-01-19  
**Reference**: See GOLDEN_SPEC.md for system details

---

## QUICK REFERENCE

| Scenario | Time | Difficulty | Prerequisites |
|----------|------|------------|---------------|
| **Scenario 1: Complete Wipe** | 3-3.5 hours | Medium | Internet, GitHub access |
| **Scenario 2: Internet Outage** | 15 minutes | Easy | Local git repo exists |
| **Scenario 3: Compromised System** | 1.5 hours | Medium | Clean OS, GitHub access |
| **Scenario 4: New Team Member** | 1-2 hours | Easy | Internet, GitHub access |

**Recovery Time Objective (RTO)**: 3.5 hours (full system with data)  
**Recovery Point Objective (RPO)**: 0 minutes (continuous git sync)

---

## SCENARIO 1: COMPLETE SYSTEM WIPE
### (Ransomware, Theft, Hardware Failure)

**Time**: 3-3.5 hours  
**Difficulty**: Medium  
**Prerequisites**: Fresh OS install, internet connection, GitHub access

### Phase 1: Fresh System Setup (10 minutes)

```bash
# Boot from macOS installer or Linux USB
# Complete OS installation
# Connect to internet

# Install Homebrew (macOS)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# OR install apt packages (Linux)
sudo apt-get update && sudo apt-get upgrade -y
```

### Phase 2: Install Core Dependencies (10 minutes)

```bash
# macOS
brew install python@3.11 git direnv

# Linux
sudo apt-get install python3.11 python3.11-venv git

# Verify installations
python3.11 --version    # Should be 3.11+
git --version           # Should be 2.x+
```

### Phase 3: Clone Repository (5 minutes)

```bash
# Create dev directory
mkdir -p /Users/jesse.kemp/Dev
cd /Users/jesse.kemp/Dev

# Clone from GitHub
git clone https://github.com/jessekemp1/dev.git .

# Verify
git log --oneline -5
git status
```

### Phase 4: Setup Python Environments (45 minutes)

```bash
# Cortex
cd /Users/jesse.kemp/Dev/cortex
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# VortexV2
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Alpha Arena
cd /Users/jesse.kemp/Dev/alpha_arena
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "✅ All virtual environments created"
```

### Phase 5: Restore Configuration & Secrets (10 minutes)

```bash
# Create cortex data directory structure
mkdir -p ~/.cortex/secrets
mkdir -p ~/.cortex/batch
mkdir -p ~/.cortex/memories
mkdir -p ~/.cortex/strategic_plans

# Option A: Restore from backup (if available)
# tar -xzf ~/Backups/cortex-backup-YYYYMMDD.tar.gz -C ~/

# Option B: Manual setup (if no backup)
# Create minimal config
cat > ~/.cortex/config.yaml <<'EOF'
root_dir: /Users/jesse.kemp/Dev
learning_enabled: true
default_limit: 3
EOF

# Set Anthropic API key
# Option 1: From secure note/password manager
echo "YOUR_ANTHROPIC_API_KEY" > ~/.cortex/secrets/anthropic_batch_key
chmod 600 ~/.cortex/secrets/anthropic_batch_key

# Option 2: From environment variable (one-time)
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Set other API keys (alpha_arena)
# Edit alpha_arena/.envrc or create .env file
cat > /Users/jesse.kemp/Dev/alpha_arena/.env <<'EOF'
BINANCE_API_KEY=your_binance_key
BINANCE_SECRET=your_binance_secret
# Other optional keys...
EOF
```

### Phase 6: Verify Installation (20 minutes)

```bash
# Test cortex
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate
cortex --help
cortex status
pytest tests/ -v --tb=short
deactivate

# Test VortexV2
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
source .venv/bin/activate
pytest tests/unit/ -v --tb=short
deactivate

# Test alpha_arena
cd /Users/jesse.kemp/Dev/alpha_arena
source venv/bin/activate
pytest tests/ -v --tb=short
deactivate

echo "✅ All verification tests passed"
```

### Phase 7: Data Restoration (90-180 minutes, OPTIONAL)

**Option A: Restore from Backup** (if available)
```bash
# Restore GRIB data (58 GB)
tar -xzf ~/Backups/vortexv2-grib-YYYYMMDD.tar.gz -C /Users/jesse.kemp/Dev/Vortex/VortexV2/data/

# Restore cortex memories
tar -xzf ~/Backups/cortex-memories-YYYYMMDD.tar.gz -C ~/.cortex/

echo "✅ Data restored from backup"
```

**Option B: Re-download** (if no backup, takes 2-3 hours)
```bash
# Download GRIB data (only if needed for VortexV2)
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
source .venv/bin/activate
python scripts/ingest_grib.py --model ecmwf --days 7
python scripts/ingest_grib.py --model gfs --days 7
deactivate

# Note: Market data for alpha_arena rebuilds automatically on first API call
```

**Option C: Use Golden Dataset** (fastest, for validation only)
```bash
# Golden validation dataset is already in git
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
source .venv/bin/activate
pytest tests/integration/test_golden_validation.py -v
# This confirms system works without full GRIB download
deactivate

echo "✅ System functional with golden dataset"
```

### Phase 8: Final Validation

```bash
# Full system check
cd /Users/jesse.kemp/Dev
cortex status
cortex next
cortex briefing

# Verify all projects
pytest cortex/tests/ alpha_arena/tests/ Vortex/VortexV2/tests/ -v

echo "✅ DISASTER RECOVERY COMPLETE"
echo "   Total time: ~3.5 hours (with GRIB data)"
echo "   System fully operational"
```

---

## SCENARIO 2: INTERNET OUTAGE
### (Work Offline with Existing System)

**Time**: 15 minutes  
**Difficulty**: Easy  
**Prerequisites**: Local git repo exists, virtual environments set up

### Offline Capabilities Check

```bash
# What works offline?
cd /Users/jesse.kemp/Dev

# ✅ Cortex (works offline)
cortex status                    # Uses local portfolio memory
cortex next                      # Uses local intelligence
pytest cortex/tests/             # All tests are local

# ✅ VortexV2 (works with cached data)
cd Vortex/VortexV2
pytest tests/                    # Uses golden dataset
# Note: Can't fetch new GRIB data without internet

# ⚠️ Alpha Arena (limited offline)
cd alpha_arena
pytest tests/                    # Tests work
# Note: Live market data requires internet, backtesting works
```

### Offline Workarounds

```bash
# Use cached/golden data
cd /Users/jesse.kemp/Dev/Vortex/VortexV2
ls data/validation/golden/       # Pre-validated datasets

# Alpha Arena: Use existing competition logs
cd /Users/jesse.kemp/Dev/alpha_arena
ls data/competition_log.jsonl    # Historical data

# Git operations (commit locally)
git add .
git commit -m "Offline work"
# Push when internet returns
```

### When Internet Returns

```bash
# Sync git
cd /Users/jesse.kemp/Dev
git pull origin main
git push origin main

# Refresh VortexV2 GRIB data
cd Vortex/VortexV2
source .venv/bin/activate
python scripts/refresh_grib.py
deactivate

# Alpha Arena market data refreshes automatically on next API call
```

---

## SCENARIO 3: COMPROMISED SYSTEM
### (Ransomware, Hack, Malware - Clean Rebuild Required)

**Time**: 1.5 hours  
**Difficulty**: Medium  
**Prerequisites**: Clean OS, internet, GitHub access

### Quick Rebuild (Minimal Data)

```bash
# Boot into recovery mode or fresh OS

# Step 1: Minimal clone (10 minutes)
cd /tmp
git clone --depth 1 https://github.com/jessekemp1/dev.git
cd dev/cortex

# Step 2: Create minimal venv (20 minutes)
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Step 3: Create cortex skeleton (2 minutes)
mkdir -p ~/.cortex/secrets ~/.cortex/batch

# Step 4: Set API key securely (don't expose in shell history)
# Use password manager or macOS Keychain
echo "YOUR_KEY" > ~/.cortex/secrets/anthropic_batch_key
chmod 600 ~/.cortex/secrets/anthropic_batch_key

# Step 5: Verify integrity (10 minutes)
python -c "from cortex import bridge; print('✓ Cortex loads')"
pytest cortex/tests/ -q

# Step 6: Verify no malware artifacts
rg -i "eval|exec|__import__|subprocess\.call.*shell=True" --type py cortex/

echo "✅ Clean system verified"
```

### Security Verification Checklist

- [ ] OS is freshly installed (no existing malware)
- [ ] All code from trusted GitHub source
- [ ] No secrets in environment variables (use files)
- [ ] All tests pass (no malicious code)
- [ ] No suspicious network connections (`netstat -an | grep ESTABLISHED`)
- [ ] API keys rotated after breach
- [ ] Review recent git commits for unauthorized changes

### Post-Breach Actions

```bash
# 1. Rotate all API keys
# - Generate new Anthropic API key
# - Update BINANCE_API_KEY, BINANCE_SECRET
# - Update any other external API credentials

# 2. Review git history for unauthorized commits
git log --since="2 weeks ago" --all --author="$(git config user.name)" --oneline

# 3. Check for backdoors
rg -i "socket|urllib|requests\.post.*http" --type py cortex/ alpha_arena/

# 4. Full system scan (if available)
# Run antivirus/malware detection tool

# 5. Enable 2FA on GitHub (if not already)
# Settings → Password and authentication → Two-factor authentication
```

---

## SCENARIO 4: NEW TEAM MEMBER ONBOARDING
### (Cold Start from Zero Knowledge)

**Time**: 1-2 hours  
**Difficulty**: Easy  
**Prerequisites**: Basic Python knowledge, GitHub account, internet

### Onboarding Checklist

**Before Starting**:
- [ ] GitHub account created
- [ ] Added to jessekemp1/dev repository
- [ ] Laptop meets minimum specs (8GB RAM, 100GB disk)
- [ ] Internet connection available

### Step 1: Prerequisites (15 minutes)

```bash
# Install required software

# macOS
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11 git direnv

# Linux
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv git

# Verify
python3.11 --version
git --version
```

### Step 2: Clone & Explore (10 minutes)

```bash
# Clone repository
mkdir -p ~/Dev
cd ~/Dev
git clone https://github.com/jessekemp1/dev.git
cd dev

# Read documentation
cat START_HERE.md          # Quick start guide
cat CLAUDE.md              # Rules and architecture
cat GOLDEN_SPEC.md         # System specification
cat DISASTER_RECOVERY.md   # This document
```

### Step 3: Automated Setup (45 minutes)

```bash
# Run automated setup (TO BE CREATED)
# bash scripts/setup-dev-environment.sh

# Manual alternative (until script exists):
cd cortex
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .            # Editable install for development
cortex --help
deactivate

cd ../Vortex/VortexV2
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/unit/test_basic.py -v
deactivate

cd ../../alpha_arena
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py --help
deactivate
```

### Step 4: Configuration (10 minutes)

```bash
# Get API keys from team lead
# Create secrets directory
mkdir -p ~/.cortex/secrets

# Add Anthropic API key (provided by team lead)
echo "API_KEY_FROM_TEAM_LEAD" > ~/.cortex/secrets/anthropic_batch_key
chmod 600 ~/.cortex/secrets/anthropic_batch_key

# Create minimal config
cat > ~/.cortex/config.yaml <<'EOF'
root_dir: /Users/YOUR_USERNAME/Dev
learning_enabled: true
default_limit: 3
EOF
```

### Step 5: Onboarding Walkthrough (30 minutes)

```bash
# Learn cortex
cd ~/Dev/cortex
source venv/bin/activate

# Get portfolio overview
python -c "from cortex import bridge; b = bridge.CortexBridge(); print(b.context_intelligence.portfolio_summary())"

# See current status
cortex status

# Get first task
cortex next --with-context

# Read architecture docs
cat docs/TECHNICAL_REFERENCE.md
cat docs/INSTALLATION.md
cat docs/DEPLOYMENT.md

deactivate
```

### Step 6: First Contribution (Guided)

```bash
# Create feature branch
git checkout -b onboarding/YOUR_NAME

# Make small test change
echo "# Onboarding test" >> cortex/README.md

# Commit and push
git add cortex/README.md
git commit -m "test: onboarding commit for YOUR_NAME

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
git push origin onboarding/YOUR_NAME

# Create pull request
gh pr create --title "Onboarding: YOUR_NAME" --body "Test PR for onboarding"
```

### Step 7: Knowledge Transfer

**Key Concepts to Learn**:
1. Read CLAUDE.md - Project rules and anti-patterns
2. Understand 3-project architecture (cortex, VortexV2, alpha_arena)
3. Review GOALS.md - Current priorities
4. Explore recent commits (`git log --oneline -20`)
5. Run test suites to see quality standards

**Questions to Ask Team Lead**:
- What's the current priority (check GOALS.md)?
- Are there any known issues or blockers?
- Which project should I focus on first?
- How often should I commit/push?

---

## BACKUP PROCEDURES

### What to Backup

**Critical (Must Backup)**:
```
~/.cortex/batch_queue.db         # Batch task queue
~/.cortex/config.yaml            # User configuration
~/.cortex/secrets/               # API keys
~/.cortex/memories/              # Cross-project learnings
~/.cortex/strategic_plans/       # Long-term plans
```

**Optional (Can Re-Download)**:
```
Vortex/VortexV2/data/grib/       # 58 GB GRIB files
alpha_arena/data/                # Market data (22 MB)
```

### Backup Script

```bash
#!/bin/bash
# File: scripts/backup-cortex-data.sh

BACKUP_DIR=~/Backups
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/cortex-backup-$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

# Backup critical data
tar -czf "$BACKUP_FILE" \
  ~/.cortex/batch_queue.db \
  ~/.cortex/config.yaml \
  ~/.cortex/secrets/ \
  ~/.cortex/memories/ \
  ~/.cortex/strategic_plans/

echo "✅ Backup created: $BACKUP_FILE"
echo "   Size: $(du -sh "$BACKUP_FILE" | cut -f1)"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "cortex-backup-*.tar.gz" -mtime +7 -delete
```

### Restore Script

```bash
#!/bin/bash
# File: scripts/restore-cortex-data.sh

if [ -z "$1" ]; then
  echo "Usage: ./restore-cortex-data.sh ~/Backups/cortex-backup-YYYYMMDD.tar.gz"
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "❌ Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "Restoring from: $BACKUP_FILE"
tar -xzf "$BACKUP_FILE" -C ~/

echo "✅ Restore complete"
echo "   Verify with: ls -lh ~/.cortex/"
```

### Automated Backup Schedule

```bash
# Add to crontab for daily backups
# Run: crontab -e
# Add this line:
0 2 * * * /Users/jesse.kemp/Dev/scripts/backup-cortex-data.sh >> /var/log/cortex-backup.log 2>&1
```

---

## ROLLBACK PROCEDURES

### Rollback to Previous Commit

```bash
# See recent commits
git log --oneline -10

# Rollback to specific commit (soft - keeps changes)
git reset --soft COMMIT_HASH

# Rollback to specific commit (hard - discards changes)
git reset --hard COMMIT_HASH

# Push (if already pushed, use force-with-lease)
git push origin main --force-with-lease
```

### Rollback Python Dependencies

```bash
# If new pip install breaks things
cd cortex
source venv/bin/activate

# Reinstall from requirements.txt (known-good versions)
pip install --force-reinstall -r requirements.txt

# Or recreate venv entirely
deactivate
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Rollback Configuration

```bash
# Restore config from backup
tar -xzf ~/Backups/cortex-backup-YYYYMMDD.tar.gz -C ~/ ~/.cortex/config.yaml

# Or reset to defaults
cat > ~/.cortex/config.yaml <<'EOF'
root_dir: /Users/jesse.kemp/Dev
learning_enabled: true
default_limit: 3
EOF
```

---

## HEALTH CHECK SCRIPT

```bash
#!/bin/bash
# File: scripts/health-check.sh

echo "🔍 Cortex Health Check"
echo "======================"

# Check Python version
echo -n "Python version: "
python3 --version

# Check git status
echo -n "Git status: "
cd /Users/jesse.kemp/Dev
git status --short | wc -l | xargs -I {} echo "{} uncommitted files"

# Check cortex
echo -n "Cortex CLI: "
cortex --help > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAILED"

# Check data directories
echo -n "~/.cortex: "
[ -d ~/.cortex ] && echo "✅ OK" || echo "❌ MISSING"

echo -n "API key: "
[ -f ~/.cortex/secrets/anthropic_batch_key ] && echo "✅ OK" || echo "❌ MISSING"

# Run quick tests
echo ""
echo "Running tests..."
pytest cortex/tests/ -q --tb=no > /dev/null 2>&1
CORTEX_EXIT=$?
echo "Cortex tests: $([ $CORTEX_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"

pytest alpha_arena/tests/ -q --tb=no > /dev/null 2>&1
ARENA_EXIT=$?
echo "Alpha Arena tests: $([ $ARENA_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"

pytest Vortex/VortexV2/tests/unit/ -q --tb=no > /dev/null 2>&1
VORTEX_EXIT=$?
echo "VortexV2 tests: $([ $VORTEX_EXIT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"

echo ""
if [ $CORTEX_EXIT -eq 0 ] && [ $ARENA_EXIT -eq 0 ] && [ $VORTEX_EXIT -eq 0 ]; then
  echo "✅ System healthy - all checks passed"
  exit 0
else
  echo "❌ System unhealthy - some checks failed"
  exit 1
fi
```

---

## TROUBLESHOOTING COMMON ISSUES

### Issue: "cortex: command not found"

**Cause**: cortex not in PATH or venv not activated

**Solution**:
```bash
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate
cortex --help

# Or use python -m
python -m cortex.cli --help
```

### Issue: "No module named 'anthropic'"

**Cause**: Virtual environment not activated or packages not installed

**Solution**:
```bash
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: "API authentication error (401)"

**Cause**: Invalid or missing Anthropic API key

**Solution**:
```bash
# Check if key exists
cat ~/.cortex/secrets/anthropic_batch_key

# Set in environment
export ANTHROPIC_API_KEY=$(cat ~/.cortex/secrets/anthropic_batch_key)

# Test
python -c "from anthropic import Anthropic; client = Anthropic(); print('✓ Valid')"
```

### Issue: "pytest: not found"

**Cause**: pytest not installed or venv not activated

**Solution**:
```bash
cd /Users/jesse.kemp/Dev/cortex
source venv/bin/activate
pip install pytest
```

### Issue: "Permission denied: ~/.cortex/secrets/"

**Cause**: Wrong file permissions

**Solution**:
```bash
chmod 700 ~/.cortex/secrets
chmod 600 ~/.cortex/secrets/*
```

---

## EMERGENCY CONTACTS & RESOURCES

**GitHub Repository**: https://github.com/jessekemp1/dev.git  
**Anthropic Console**: https://console.anthropic.com  
**Documentation**: /Users/jesse.kemp/Dev/docs/

**Key Documents**:
- GOLDEN_SPEC.md - System specification
- CLAUDE.md - Rules and architecture
- START_HERE.md - Quick start guide

---

## VERSION HISTORY

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-01-19 | Initial disaster recovery playbook | Claude + Jesse |

---

**Recovery tested on**: Clean macOS installation  
**Last validated**: 2026-01-19  
**Next validation due**: 2026-02-19 (monthly DR drill)

---

*This playbook should be tested quarterly to ensure procedures remain valid.*
