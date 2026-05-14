---
name: test
version: 1.0.0
description: Smart test execution with project auto-detection
author: Jesse Kemp
requires:
  python: ">=3.11"
  packages:
    - pytest
tags: [core, testing, quality]
enabled: true
---

# Test Plugin

Smart test execution that:
- Auto-detects project context
- Runs appropriate test suite
- Shows clear pass/fail summary
- Suggests fixes on failure

## Usage

```bash
/test [path] [--quick] [--coverage]
```

### Options

- `--quick` - Fast tests only
- `--coverage` - Include coverage report
- `--verbose, -v` - Verbose output

## Examples

```bash
$ /test
🧪 Running Tests (Auto-detected: VortexV2)
════════════════════════════════════════

pytest Vortex/VortexV2/tests/ -v

✅ 45 passed in 12.3s

$ /test --quick
🧪 Quick Tests
══════════════

✅ 32 passed in 3.2s (13 skipped)
```
