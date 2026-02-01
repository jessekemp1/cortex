---
name: commit
version: 1.0.0
description: Intelligent git commit with Cortex-powered message suggestions
author: Jesse Kemp
requires:
  python: ">=3.11"
tags: [core, git, intelligence]
enabled: true
---

# Commit Plugin

Intelligent git commit workflow:
- Analyzes staged changes
- Suggests conventional commit messages
- Groups related files semantically
- Warns about risky commits

## Usage

```bash
/commit [options]
```

### Options

- `-m MESSAGE` - Custom commit message
- `--amend` - Amend last commit
- `--help, -h` - Show help

## Examples

```bash
$ /commit
🧠 Analyzing changes...

Suggested commit message:
feat(vortex): Add wind speed validation

Files:
  - Vortex/VortexV2/validation/wind.py
  - Vortex/VortexV2/tests/test_wind.py

Proceed? [y/N]: y
✅ Committed successfully
```
