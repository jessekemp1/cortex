# Cortex Installation Guide

**Version**: 1.0  
**Last Updated**: 2025-12-24

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Methods](#installation-methods)
3. [Environment Setup](#environment-setup)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Common Issues](#common-issues)

---

## System Requirements

### Minimum Requirements

- **Python**: 3.9+ (3.10+ recommended)
- **Operating System**: macOS, Linux, Windows (WSL)
- **Git**: 2.0+ (for session intelligence)
- **Disk Space**: ~100MB (for data storage)

### Recommended

- **Python**: 3.11+ (current development version)
- **Memory**: 512MB+ available
- **Projects**: 3+ projects in workspace (for portfolio intelligence)

---

## Installation Methods

### Method 1: Development Installation (Recommended)

**Best for**: Development, customization, contributions

```bash
# Navigate to cortex directory
cd ~/Dev/cortex

# Create virtual environment (optional but recommended)
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install cortex in development mode
pip install -e .

# Verify installation
cortex --help
```

**Advantages**:
- Editable installation (changes reflect immediately)
- Full development tools access
- Easy to modify and contribute

---

### Method 2: Standard Installation

**Best for**: Production use, stable deployment

```bash
# Navigate to cortex directory
cd ~/Dev/cortex

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install cortex
pip install -e .

# Verify installation
cortex --help
```

**Advantages**:
- Clean installation
- Isolated dependencies
- Production-ready

---

### Method 3: Minimal Installation

**Best for**: Metadata-only usage (no AI features)

```bash
# Install only core dependencies
pip install structlog rich PyYAML python-dotenv pytz

# Use cortex modules directly (no CLI)
python3 -c "from portfolio_memory import PortfolioMemory; print(PortfolioMemory().get_stats())"
```

**Advantages**:
- Minimal dependencies
- Fast installation
- No external API keys required

**Limitations**:
- No spec knowledge base (requires chromadb)
- No AI-powered features
- Limited functionality

---

## Environment Setup

### Required Environment Variables

**ANTHROPIC_API_KEY** (Optional):
- Purpose: Anthropic Claude API access (for embeddings, batch API)
- Required for: Spec knowledge base embeddings, batch processing
- How to get: https://console.anthropic.com/
- Example: `export ANTHROPIC_API_KEY="sk-ant-api03-..."`

**Note**: Not required for metadata-only usage

### Optional Environment Variables

**CORTEX_ROOT**:
- Purpose: Override default workspace root
- Default: `~/Dev` or `~/Dev`
- Example: `export CORTEX_ROOT="/path/to/workspace"`

**OPENAI_API_KEY** (Optional):
- Purpose: OpenAI API access (if using OpenAI features)
- Required for: OpenAI-powered features
- How to get: https://platform.openai.com/
- Example: `export OPENAI_API_KEY="sk-..."`

### Setting Environment Variables

**macOS/Linux**:
```bash
# Add to ~/.zshrc or ~/.bashrc
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export CORTEX_ROOT="~/Dev"

# Reload shell
source ~/.zshrc  # or source ~/.bashrc
```

**Windows**:
```powershell
# Set environment variable
$env:ANTHROPIC_API_KEY="sk-ant-api03-..."
$env:CORTEX_ROOT="C:\Users\...\Dev"

# Or use System Properties > Environment Variables
```

---

## Configuration

### Configuration File

Cortex stores configuration in `~/.cortex/config.yaml`.

### Create Default Config

```bash
# Method 1: Using Python
python -c "from config import create_default_config; create_default_config()"

# Method 2: Manual creation
mkdir -p ~/.cortex
cat > ~/.cortex/config.yaml <<EOF
root_dir: ~/Dev
learning_enabled: true
default_limit: 3
EOF
```

### Configuration Options

```yaml
# Workspace root directory
root_dir: ~/Dev

# Enable learning from execution history
learning_enabled: true

# Default limit for recommendations
default_limit: 3

# Portfolio index location (optional)
portfolio_index: ~/.claude/portfolio/project_index.json

# Metrics database location (optional)
metrics_db: ~/.claude/metrics.db

# Spec knowledge base location (optional)
specs_path: ~/.claude/specs
```

---

## Verification

### Step 1: Verify Installation

```bash
# Check cortex command
cortex --help

# Expected output: Command help text
```

### Step 2: Test Core Modules

```bash
# Test portfolio memory
python3 -c "from portfolio_memory import PortfolioMemory; print(PortfolioMemory().get_stats())"

# Test session manager
python3 -c "from intelligence.session_manager import SessionManager; print(SessionManager().load_session_context())"

# Test bridge API
python3 -c "from bridge import CortexBridge; bridge = CortexBridge(); print(bridge.get_portfolio_stats())"
```

### Step 3: Run Enterprise Tests

```bash
cd ~/Dev/cortex
python test_enterprise_grade.py

# Expected: 15/15 tests pass (100%)
```

### Step 4: Verify Data Directories

```bash
# Check data directories created
ls -la ~/.claude/

# Expected:
# portfolio/
# specs/
# session/
# metrics/
```

---

## Initialization

### Automatic Initialization

Data directories and files are created automatically on first run:

```bash
# First run creates directories
cortex status

# Directories created:
# ~/.claude/portfolio/
# ~/.claude/specs/
# ~/.claude/session/
# ~/.claude/metrics/
```

### Manual Initialization

```bash
# Create data directories
mkdir -p ~/.claude/{portfolio,specs,session,metrics}

# Initialize JSON files
python3 -c "from portfolio_memory import PortfolioMemory; PortfolioMemory()"
python3 -c "from intelligence.spec_knowledge_base import SpecKnowledgeBase; SpecKnowledgeBase()"
```

---

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'cortex'"

**Cause**: Cortex not installed or Python path incorrect

**Solution**:
```bash
# Install cortex
cd ~/Dev/cortex
pip install -e .

# Or add to Python path
export PYTHONPATH="~/Dev/cortex:$PYTHONPATH"
```

---

### Issue: "ANTHROPIC_API_KEY not set"

**Cause**: API key not configured (only needed for embeddings)

**Solution**:
```bash
# Set environment variable
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Or use without embeddings (metadata-only mode)
# Spec knowledge base will use hash-based search instead
```

---

### Issue: "chromadb not available"

**Cause**: ChromaDB not installed (optional dependency)

**Solution**:
```bash
# Install chromadb (optional)
pip install chromadb

# Or use without chromadb (hash-based search)
# Spec knowledge base will fall back to hash-based similarity
```

---

### Issue: "Permission denied" when accessing ~/.claude/

**Cause**: Insufficient permissions

**Solution**:
```bash
# Fix permissions
chmod -R 755 ~/.claude/

# Or run with appropriate permissions
```

---

### Issue: "Portfolio memory not available"

**Cause**: PortfolioMemory module not initialized

**Solution**:
```bash
# Initialize portfolio memory
python3 -c "from portfolio_memory import PortfolioMemory; PortfolioMemory()"

# Check data directory exists
ls -la ~/.claude/portfolio/
```

---

### Issue: "No projects found"

**Cause**: No projects in workspace or portfolio not indexed

**Solution**:
```bash
# Check workspace root
echo $CORTEX_ROOT  # or check config.yaml

# Verify projects exist
ls ~/Dev/

# Projects should have .git directories or .claude/project.yaml files
```

---

## Post-Installation Setup

### 1. Index Specifications

```bash
# Index specs for a project
python bridge.py index-spec /path/to/spec.md --project ProjectName

# Or index entire project
python3 -c "
from intelligence.spec_knowledge_base import SpecKnowledgeBase
kb = SpecKnowledgeBase()
count = kb.index_project('/path/to/project', 'ProjectName')
print(f'Indexed {count} specs')
"
```

### 2. Set Up Session Hooks (Optional)

```bash
# Create hooks directory
mkdir -p ~/.claude/hooks

# Create session start hook
cat > ~/.claude/hooks/SessionStart.compact.sh <<'EOF'
#!/bin/bash
cd ~/Dev/cortex
python3 bridge.py session-context 2>/dev/null
EOF

# Make executable
chmod +x ~/.claude/hooks/SessionStart.compact.sh
```

### 3. Configure Git Integration

Cortex automatically detects git repositories. No additional configuration needed.

---

## Upgrade Instructions

### Upgrading Cortex

```bash
# Navigate to cortex directory
cd ~/Dev/cortex

# Pull latest changes
git pull

# Reinstall
pip install -e . --upgrade

# Verify
cortex --help
python test_enterprise_grade.py
```

### Migrating Data

If upgrading from an older version:

```bash
# Backup existing data
cp -r ~/.claude ~/.claude.backup

# Run migration (if needed)
python3 -c "from data_migration import DataMigrator; DataMigrator().migrate()"
```

---

## Uninstallation

### Remove Cortex

```bash
# Uninstall package
pip uninstall cortex

# Remove data (optional)
rm -rf ~/.cortex
rm -rf ~/.claude/portfolio
rm -rf ~/.claude/specs
```

**Note**: Removing data will delete all portfolio memory, indexed specs, and metrics.

---

## Troubleshooting

### Debug Mode

```bash
# Enable debug logging
export CORTEX_DEBUG=1

# Run with verbose output
cortex status --verbose
```

### Check Installation

```bash
# Check Python version
python3 --version  # Should be 3.9+

# Check installed packages
pip list | grep cortex

# Check data directories
ls -la ~/.claude/
```

### Verify Dependencies

```bash
# Check core dependencies
python3 -c "import structlog, yaml, dotenv; print('Core dependencies OK')"

# Check optional dependencies
python3 -c "import chromadb; print('ChromaDB available')" 2>/dev/null || echo "ChromaDB not installed (optional)"
```

---

## Next Steps

After installation:

1. **Read [Getting Started Guide](user_guide/getting_started.md)** - Quick start tutorial
2. **Review [Core Concepts](user_guide/core_concepts.md)** - Understand Cortex components
3. **Try [Examples](user_guide/examples.md)** - Real-world usage examples
4. **Check [Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

---

## References

- [Architecture Documentation](ARCHITECTURE.md)
- [API Documentation](API.md)
- [Design Specification](DESIGN.md)
- [Dependencies](../DEPENDENCIES.md)

---

**Version**: 1.0  
**Last Updated**: 2025-12-24  
**Status**: Production
