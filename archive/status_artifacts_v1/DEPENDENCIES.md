# Cortex Dependencies

**Last Updated**: 2025-12-23
**Python Version**: 3.9+

---

## External Dependencies

### Core Framework

**anthropic** (latest)
- Purpose: Anthropic Claude API client
- License: MIT
- Installation: `pip install anthropic`
- Usage: AI-powered features (briefing, recommendations, batch processing)
- **Required**: For AI features (optional for metadata-only usage)

**structlog** (>=23.2.0)
- Purpose: Structured logging
- License: MIT
- Installation: `pip install structlog`
- Usage: All logging throughout Cortex
- **Required**: Yes

**APScheduler** (>=3.10.0)
- Purpose: Job scheduling
- License: MIT
- Installation: `pip install APScheduler`
- Usage: Scheduled tasks, automated briefings
- **Required**: For scheduling features

**rich** (latest)
- Purpose: Terminal UI formatting
- License: MIT
- Installation: `pip install rich`
- Usage: CLI output formatting, tables, progress bars
- **Required**: For CLI

### Data Processing

**PyYAML** (>=6.0)
- Purpose: YAML parsing
- License: MIT
- Installation: `pip install PyYAML`
- Usage: Read `.claude/project.yaml` files
- **Required**: Yes (core functionality)

**python-dotenv** (>=1.0.0)
- Purpose: Environment variable management
- License: BSD
- Installation: `pip install python-dotenv`
- Usage: Load API keys from `.env` files
- **Required**: Yes

**pytz** (latest)
- Purpose: Timezone handling
- License: MIT
- Installation: `pip install pytz`
- Usage: Date/time operations in briefings
- **Required**: Yes

### Web Framework (Optional)

**FastAPI** (>=0.104.1)
- Purpose: Web API framework
- License: MIT
- Installation: `pip install fastapi`
- Usage: Optional web interface for Cortex
- **Required**: No (CLI-only usage doesn't need this)

**uvicorn** (>=0.24.0)
- Purpose: ASGI server
- License: BSD
- Installation: `pip install uvicorn`
- Usage: Serve FastAPI if used
- **Required**: No

### AI Providers (Optional)

**openai** (latest)
- Purpose: OpenAI API client
- License: MIT
- Installation: `pip install openai`
- Usage: Optional OpenAI-powered features
- **Required**: No (only if using OpenAI features)

### Advanced Features (Optional)

**chromadb** (>=0.4.0)
- Purpose: Vector database for semantic search
- License: Apache 2.0
- Installation: `pip install chromadb`
- Usage: SpecKnowledgeBase semantic search
- **Required**: No (SpecKnowledgeBase fails gracefully if missing)

---

## System Dependencies

### Required

**Python 3.9+**
- Purpose: Runtime environment
- Installation (macOS): `brew install python@3.9`
- Installation (Ubuntu): `apt-get install python3.9`
- **Minimum**: Python 3.9 (dataclasses, type hints)
- **Recommended**: Python 3.11+

**Git**
- Purpose: Project activity analysis
- Installation (macOS): Included with Xcode Command Line Tools
- Installation (Ubuntu): `apt-get install git`
- Usage: `ai_intelligence.py` scans git repositories

### Optional

**PostgreSQL** (for local-orchestrator integration)
- Purpose: Execution history storage
- Installation (macOS): `brew install postgresql@14`
- Installation (Ubuntu): `apt-get install postgresql-14`
- **Note**: Only needed if using local-orchestrator integration

---

## Internal Dependencies

### Projects This Depends On

**local-orchestrator** (optional)
- Relationship: Executes Cortex recommendations as automated agents
- Integration: `integration/local_orchestrator.py`
- Required: No (Cortex works standalone for recommendations)
- Benefit: Enables closed-loop learning (recommendations → execution → feedback)

### Projects That Depend On This

**All AI-first workspace projects**
- **VortexV2**: Uses Cortex for project discovery
- **dj-copilot**: Discovered and indexed by Cortex
- **windfield**: Discovered and indexed by Cortex
- **Custom scripts**: Use CortexBridge for workspace intelligence

---

## Related Projects

### Same Domain (infrastructure)
- **local-orchestrator**: Task execution and scheduling
- **cortex**: Strategic intelligence (this project)

### Shared Patterns
- Pydantic for data models
- structlog for logging
- Rich for terminal UI
- FastAPI for optional web interfaces

---

## Version Compatibility

### Python Versions
- **3.9**: Minimum (dataclasses, type hints)
- **3.10**: Fully supported
- **3.11**: Recommended (current development)
- **3.12**: Supported

### Dependency Conflicts
- **anthropic**: Latest version compatible with all Python 3.9+
- **structlog**: No known conflicts
- **PyYAML**: Compatible with all versions
- **chromadb**: Requires Python 3.9+ (optional dependency)

---

## Installation Guide

### Basic Installation (CLI Only)

```bash
# Clone or navigate to cortex
cd /Users/jesse.kemp/Dev/cortex

# Create virtual environment (optional but recommended)
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Or install manually
pip install anthropic structlog APScheduler rich PyYAML python-dotenv pytz

# Install cortex in development mode
pip install -e .

# Verify installation
cortex --help
```

### Full Installation (With Optional Features)

```bash
# Install core dependencies
pip install -r requirements.txt

# Install web framework (for optional web interface)
pip install fastapi uvicorn

# Install AI providers
pip install openai

# Install advanced features
pip install chromadb

# Install development tools
pip install pytest pytest-cov black ruff mypy
```

### Minimal Installation (Metadata Only)

For using Cortex as a metadata reader without AI features:

```bash
# Only install core dependencies
pip install structlog rich PyYAML python-dotenv pytz

# Skip anthropic, openai, chromadb
```

---

## Environment Variables

### Required

**ANTHROPIC_API_KEY**
- Purpose: Anthropic Claude API access
- Required for: AI-powered briefings, recommendations, batch processing
- How to get: https://console.anthropic.com/
- Example: `export ANTHROPIC_API_KEY="sk-ant-api03-..."`
- **Note**: Not required for metadata-only usage

### Optional

**OPENAI_API_KEY**
- Purpose: OpenAI API access (if using OpenAI features)
- Required for: OpenAI-powered features
- How to get: https://platform.openai.com/
- Example: `export OPENAI_API_KEY="sk-..."`

**CORTEX_ROOT**
- Purpose: Override default workspace root
- Default: `~/Dev` or `/Users/jesse.kemp/Dev`
- Example: `export CORTEX_ROOT="/path/to/workspace"`

### Configuration File

Create `~/.cortex/config.yaml`:

```yaml
# Workspace root directory
root_dir: /Users/jesse.kemp/Dev

# Enable learning from execution history
learning_enabled: true

# Default limit for recommendations
default_limit: 3

# Portfolio index location (optional)
portfolio_index: ~/.claude/portfolio/project_index.json
```

---

## Setup Checklist

### Initial Setup

1. **Install Python 3.9+**
   ```bash
   python3 --version  # Should be 3.9 or higher
   ```

2. **Clone or navigate to cortex**
   ```bash
   cd /Users/jesse.kemp/Dev/cortex
   ```

3. **Create virtual environment** (recommended)
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

5. **Set environment variables**
   ```bash
   # Add to ~/.zshrc or ~/.bashrc
   export ANTHROPIC_API_KEY="your_key_here"
   export CORTEX_ROOT="/Users/jesse.kemp/Dev"
   ```

6. **Verify installation**
   ```bash
   cortex --help
   cortex projects  # Should list discovered projects
   ```

7. **Optional: Create config file**
   ```bash
   mkdir -p ~/.cortex
   cat > ~/.cortex/config.yaml <<EOF
   root_dir: /Users/jesse.kemp/Dev
   learning_enabled: true
   default_limit: 3
   EOF
   ```

### Context Injection Setup (Optional)

For automatic context injection when starting AI sessions:

1. **Create hooks directory**
   ```bash
   mkdir -p ~/.claude/hooks
   ```

2. **Symlink context hook**
   ```bash
   ln -s /Users/jesse.kemp/Dev/cortex/.claude/hooks/project_context.py \
         ~/.claude/hooks/project_context.py
   ```

3. **Verify hook**
   ```bash
   # Navigate to any AI-first project
   cd /Users/jesse.kemp/Dev/Vortex/VortexV2

   # Start Claude session (should inject project context)
   claude
   ```

### Shell Integration (Optional)

Add alias to shell config:

```bash
# Add to ~/.zshrc or ~/.bashrc
alias cortex="python /Users/jesse.kemp/Dev/cortex/cli.py"

# Reload shell
source ~/.zshrc
```

---

## Troubleshooting

### ImportError: No module named 'anthropic'

**Symptom**: `ModuleNotFoundError: No module named 'anthropic'`

**Solution**:
```bash
pip install anthropic

# Or if using venv, ensure it's activated
source venv/bin/activate
pip install anthropic
```

### YAML parsing errors

**Symptom**: `yaml.scanner.ScannerError` when reading project.yaml

**Solution**:
- Check project.yaml syntax (proper indentation, quotes)
- Validate YAML: https://www.yamllint.com/
- Common issues:
  - Mixed tabs/spaces (use spaces only)
  - Unquoted strings with special characters
  - Missing quotes around strings with colons

**Example Fix**:
```yaml
# BAD (unquoted colon)
description: System: Weather forecasting

# GOOD (quoted)
description: "System: Weather forecasting"

# Or use multi-line
description: >
  System: Weather forecasting
```

### chromadb import fails

**Symptom**: `ImportError: cannot import name 'chromadb'`

**Solution**: This is expected if chromadb not installed (optional)
```bash
# If you want semantic search features
pip install chromadb

# Otherwise, ignore - SpecKnowledgeBase fails gracefully
```

### Permission denied when creating ~/.cortex/

**Symptom**: `PermissionError: [Errno 13] Permission denied: '/Users/jesse.kemp/.cortex'`

**Solution**:
```bash
# Check home directory permissions
ls -la ~/ | grep .cortex

# Create directory manually
mkdir -p ~/.cortex
chmod 755 ~/.cortex
```

### cortex command not found

**Symptom**: `bash: cortex: command not found`

**Solution**:
```bash
# Option 1: Install in development mode
cd /Users/jesse.kemp/Dev/cortex
pip install -e .

# Option 2: Use python -m
python -m cortex.cli projects

# Option 3: Create alias
alias cortex="python /Users/jesse.kemp/Dev/cortex/cli.py"
```

### No projects discovered

**Symptom**: `cortex projects` returns empty or doesn't find projects

**Solution**:
1. Ensure projects have `.claude/project.yaml`:
   ```bash
   # Check for project.yaml files
   find ~/Dev -name "project.yaml" -path "*/.claude/*"
   ```

2. Verify YAML syntax:
   ```bash
   # Test parsing
   python -c "import yaml; yaml.safe_load(open('/path/to/project.yaml'))"
   ```

3. Check workspace root:
   ```bash
   # Verify CORTEX_ROOT
   echo $CORTEX_ROOT

   # Or set explicitly
   export CORTEX_ROOT="/Users/jesse.kemp/Dev"
   ```

### Slow git operations in briefing

**Symptom**: `cortex briefing` takes >60 seconds

**Solution**:
- Expected for large workspaces (many projects)
- Optimization: Exclude large repos with `.cortexignore`
- Git operations are inherently I/O bound
- Typical time: 15-30 seconds for 10-20 projects

### API key not found

**Symptom**: `Error: ANTHROPIC_API_KEY environment variable not set`

**Solution**:
```bash
# Check if set
echo $ANTHROPIC_API_KEY

# Set for current session
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Set permanently (add to ~/.zshrc or ~/.bashrc)
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-..."' >> ~/.zshrc
source ~/.zshrc

# Or use .env file
echo 'ANTHROPIC_API_KEY="sk-ant-api03-..."' > /Users/jesse.kemp/Dev/cortex/.env
```

---

## Development Dependencies

### Testing

**pytest** (>=7.4.0)
- Purpose: Unit and integration testing
- Installation: `pip install pytest`
- Usage: `pytest tests/`

**pytest-cov** (>=4.1.0)
- Purpose: Test coverage reporting
- Installation: `pip install pytest-cov`
- Usage: `pytest --cov=cortex tests/`

**httpx** (>=0.25.0)
- Purpose: HTTP client for testing FastAPI
- Installation: `pip install httpx`
- Usage: FastAPI test client

### Code Quality

**black** (latest)
- Purpose: Code formatting
- Installation: `pip install black`
- Usage: `black cortex/`

**ruff** (latest)
- Purpose: Fast linting
- Installation: `pip install ruff`
- Usage: `ruff check cortex/`

**mypy** (latest)
- Purpose: Type checking
- Installation: `pip install mypy`
- Usage: `mypy cortex/`

---

## Data Sources

### Workspace Projects
- **Source**: `.claude/project.yaml` files in workspace
- **Format**: YAML metadata files
- **Access**: File system (no API)
- **Cost**: Free

### Git Repositories
- **Source**: Local git repositories
- **Format**: Git command output
- **Access**: Git CLI
- **Cost**: Free

### Anthropic Claude API
- **Source**: https://api.anthropic.com/
- **Format**: REST API (JSON)
- **Access**: API key required
- **Cost**: Pay per token (batch API cheaper)
- **Rate Limits**: Varies by plan

### Local-Orchestrator (Optional)
- **Source**: Execution history in `storage/execution_history/`
- **Format**: JSON files
- **Access**: File system
- **Cost**: Free

---

## License Compliance

All dependencies use permissive licenses compatible with commercial use:
- **MIT**: anthropic, structlog, rich, PyYAML, FastAPI, uvicorn
- **BSD**: python-dotenv, pytz
- **Apache 2.0**: APScheduler, chromadb (optional)

---

## Update Frequency

- **anthropic**: Monthly (API changes)
- **structlog**: Quarterly
- **APScheduler**: Infrequent (stable)
- **rich**: Monthly (new features)
- **PyYAML**: Infrequent (stable)

---

## Security Considerations

### API Keys
- Store in `.env` (never commit to git)
- Use environment variables in production
- Rotate keys regularly

### File System Access
- Cortex reads workspace files (read-only for most operations)
- Writes to `~/.cortex/` and `~/.claude/portfolio/`
- No network access except AI APIs

### Git Operations
- Only reads git history (no writes)
- Uses `git log` and `git diff` commands
- No remote push/pull operations

---

**Version**: 1.0
**Last Updated**: 2025-12-23
**Maintained By**: Cortex Team
