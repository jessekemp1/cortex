---
name: status
version: 1.0.0
description: Show comprehensive project status with Cortex-powered intelligent analysis
author: Jesse Kemp
requires:
  python: ">=3.11"
  packages: []
  optional:
    anthropic: "For AI-powered commit suggestions"
tags: [core, git, orchestration, intelligence]
enabled: true
homepage: https://github.com/jessekemp1/cortex
repository: https://github.com/jessekemp1/cortex
license: MIT
---

# Status Plugin

Shows comprehensive project status with Cortex-powered intelligent analysis, including:
- Git status and recent commits
- Running services (VortexV2, Alpha Arena)
- Intelligent commit suggestions grouped semantically
- Missing test detection
- High-risk change warnings

## Usage

```bash
/status [options]
```

### Options

- `--quick` - Quick status without detailed analysis
- `--project PROJECT` - Show status for specific project (vortex, arena, cortex)
- `--verbose, -v` - Verbose output with debugging info
- `--help, -h` - Show this help message

## Examples

### Full Status

```bash
$ /status
📊 Cortex Portfolio Status
═══════════════════════════════════

🔧 Git Status
─────────────
Branch: main
Status: 5 files modified, 2 untracked

🏃 Running Services
──────────────────
✓ VortexV2 API (PID 12345) - http://localhost:8000
✓ VortexV2 UI (PID 12346) - http://localhost:8501
✗ Alpha Arena - Not running

📝 Recent Commits
────────────────
a1b2c3d feat(vortex): Add wind speed validation
d4e5f6g fix(arena): Fix portfolio calculation bug
g7h8i9j docs: Update README

🧠 Cortex Intelligence: Commit Suggestions
──────────────────────────────────────────
Group 1: "Add VortexV3 React components" (Confidence: 95%)
  ✓ Safe to commit
  Files:
    - Vortex/VortexV3/src/components/FleetOverview.tsx
    - Vortex/VortexV3/src/components/RaceReplay.tsx

Group 2: "Update Alpha Arena calculations" (Confidence: 88%)
  ⚠ Missing tests - consider adding tests first
  Files:
    - alpha_arena/ui/utils/calculations.py

Group 3: "Runtime data - DO NOT COMMIT" (Confidence: 99%)
  ❌ High risk - runtime data
  Files:
    - alpha_arena/data/competition_log.jsonl
    - Vortex/VortexV2/data/validation/latest.json

Next Actions:
  1. Commit Group 1 (safe)
  2. Add tests for calculations.py
  3. Add competition_log.jsonl to .gitignore
```

### Quick Status

```bash
$ /status --quick
✓ 3 projects active
⚠ 2 anomalies (1 CRITICAL)
✓ 5 safe commits ready
⚠ 2 files need tests
```

### Project-Specific Status

```bash
$ /status --project vortex
📊 VortexV2 Status
═══════════════════

Git: main branch, 3 files modified
Services: API ✓, UI ✓
Recent: "feat: Add GRIB validation" (2 hours ago)

Recommendations:
  - Commit validation changes (safe)
  - Run integration tests before push
```

## Configuration

Optional configuration in `~/.cortex/plugins/status.json`:

```json
{
  "show_git": true,
  "show_services": true,
  "show_anomalies": true,
  "max_commits": 10,
  "max_recommendations": 5,
  "projects": {
    "vortex": {
      "path": "Vortex/VortexV2",
      "ports": [8000, 8501]
    },
    "arena": {
      "path": "alpha_arena",
      "ports": [8502]
    },
    "cortex": {
      "path": "cortex",
      "ports": []
    }
  }
}
```

### Configuration Options

- `show_git` - Show git status section (default: true)
- `show_services` - Show running services section (default: true)
- `show_anomalies` - Show anomaly detection section (default: true)
- `max_commits` - Maximum recent commits to show (default: 10)
- `max_recommendations` - Maximum commit groups to recommend (default: 5)
- `projects` - Project-specific configuration

## Implementation Details

### How It Works

1. **Git Analysis**: Runs `git status` and `git log` to gather current state
2. **Service Detection**: Checks configured ports using `lsof` to find running services
3. **Intelligent Analysis**: Calls `cortex/intelligence/status/analyze.py` which:
   - Groups uncommitted changes semantically using file paths and git diff
   - Detects missing test files for code changes
   - Identifies runtime data files (logs, .jsonl, validation data)
   - Generates conventional commit messages
   - Assigns confidence scores to each recommendation
4. **Presentation**: Formats results with rich text, colors, and emojis

### Performance

- Runtime: ~500ms for full analysis
- Memory: Minimal (<50MB)
- API calls: None (intelligence runs locally)

### Dependencies

#### Required

None - uses only stdlib and git

#### Optional

- `anthropic` - For enhanced AI-powered commit message suggestions (future)
- `rich` - For enhanced terminal formatting (future)

## Troubleshooting

### Common Issues

**Issue 1: "git command not found"**

```
Error: git is not installed or not in PATH
```

**Solution:** Install git: `brew install git` (macOS) or `apt-get install git` (Linux)

**Issue 2: "analyze.py not found"**

```
Error: /path/to/cortex/intelligence/status/analyze.py not found
```

**Solution:** Ensure you're running from Dev directory and Cortex is properly installed

**Issue 3: "Service detection shows wrong PIDs"**

```
Warning: lsof permission denied
```

**Solution:** Run with sudo or check system security settings for process monitoring

## Development

### Running Tests

```bash
pytest cortex/plugins/status/tests/ -v
```

### Adding Features

To add new status sections:

1. Add new method to StatusPlugin class (e.g., `_get_docker_status()`)
2. Call method in `execute()` workflow
3. Add configuration option in default config
4. Update PLUGIN.md with new section documentation
5. Add tests for new functionality

### Integration with Other Plugins

The status plugin can be extended by other plugins:

```python
from cortex.plugins.status.plugin import StatusPlugin

class MyPlugin(BasePlugin):
    def execute(self, args: List[str], **kwargs) -> int:
        # Get status data
        status_plugin = StatusPlugin(...)
        # Use status data for your plugin logic
```

## See Also

- `/briefing` - Morning briefing with next actions
- `/next` - Next recommended action only
- `/commit` - Intelligent git commit workflow
- `cortex/intelligence/status/` - Status analysis implementation
