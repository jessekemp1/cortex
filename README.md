# Cortex - AI-Powered Task Processing System

An intelligent task processing system that orchestrates complex workflows using Claude AI.

## Features

- **Intelligent Task Processing** - AI-driven analysis and execution
- **Workflow Orchestration** - Complex multi-step task management
- **API Integration** - Seamless integration with external services
- **Extensible Architecture** - Plugin-based system for custom tasks

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd cortex

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies from lock file (recommended)
pip install -r requirements-lock.txt

# Or install from requirements.txt (for development)
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Configuration

Create a `.env` file in the cortex directory:

```env
ANTHROPIC_API_KEY=your_api_key_here
MODEL_NAME=claude-3-5-sonnet-20241022
MAX_TOKENS=4096
```

### Running Cortex

```bash
# Run the main application
python main.py

# Run with specific configuration
python main.py --config config.yaml
```

## Dependency Management

This project uses a two-file dependency strategy:

- **`requirements.txt`** - High-level dependencies with version ranges
- **`requirements-lock.txt`** - Exact versions for reproducible installs

### Installing Dependencies

**For production/stable environments** (recommended):
```bash
pip install -r requirements-lock.txt
```

**For development** (when you need to update dependencies):
```bash
pip install -r requirements.txt
```

### Updating Dependencies

Use the provided automation script:

```bash
# From repository root
./scripts/update-deps.sh cortex
```

Or manually:

```bash
# 1. Update requirements.txt with new dependencies or version constraints
# 2. Install updates
pip install -r requirements.txt --upgrade

# 3. Regenerate lock file
pip freeze > requirements-lock.txt

# 4. Test thoroughly
pytest tests/
```

**Important**: Always commit both `requirements.txt` and `requirements-lock.txt` together.

See [Dependency Management Guide](../docs/DEPENDENCY_MANAGEMENT.md) for detailed information.

## Development

### Project Structure

```
cortex/
├── main.py              # Entry point
├── core/                # Core system modules
├── tasks/               # Task implementations
├── orchestrator/        # Workflow orchestration
├── tests/               # Test suite
├── requirements.txt     # Dependency specifications
└── requirements-lock.txt # Locked dependency versions
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_core.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

### Adding New Dependencies

1. Add dependency to `requirements.txt` with appropriate version constraint:
   ```txt
   new-package>=1.0.0,<2.0.0
   ```

2. Update lock file:
   ```bash
   ./scripts/update-deps.sh cortex
   ```

3. Test thoroughly

4. Commit both files:
   ```bash
   git add requirements.txt requirements-lock.txt
   git commit -m "Add new-package dependency"
   ```

## Architecture

### Core Components

- **Task Processor** - Executes individual tasks
- **Orchestrator** - Manages workflow execution
- **API Client** - Handles external API communication
- **State Manager** - Maintains system state

### Task System

Tasks are modular units of work that can be:
- Executed independently
- Chained together in workflows
- Retried on failure
- Monitored and logged

## API Reference

### Task Execution

```python
from cortex.core import TaskProcessor

processor = TaskProcessor()
result = processor.execute(task_config)
```

### Workflow Creation

```python
from cortex.orchestrator import Workflow

workflow = Workflow()
workflow.add_task('task1', config1)
workflow.add_task('task2', config2, depends_on=['task1'])
workflow.execute()
```

## Troubleshooting

### Common Issues

**Issue**: Import errors after pulling changes

**Solution**: Reinstall dependencies from lock file
```bash
pip install -r requirements-lock.txt --force-reinstall
```

**Issue**: API authentication failures

**Solution**: Verify ANTHROPIC_API_KEY in .env file
```bash
echo $ANTHROPIC_API_KEY  # Should show your key
```

**Issue**: Version conflicts

**Solution**: Clean install from lock file
```bash
pip cache purge
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-lock.txt
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Update dependencies if needed (see above)
5. Run tests and ensure they pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

[Your License Here]

## Support

For issues, questions, or contributions:
- Create an issue on GitHub
- See [Dependency Management Guide](../docs/DEPENDENCY_MANAGEMENT.md)
- Check existing documentation

---

**Last Updated**: 2026-01-20