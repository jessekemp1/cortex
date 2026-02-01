---
name: next
version: 1.0.0
description: Recommend next action using Cortex intelligence
author: Jesse Kemp
requires:
  python: ">=3.11"
tags: [core, intelligence, recommendation]
enabled: true
---

# Next Plugin

Recommends the single best next action based on:
- Current context
- Project priorities
- Blocking issues
- Intelligent analysis

## Usage

```bash
/next [--verbose]
```

## Example

```bash
$ /next
🎯 Next Recommended Action

Fix failing test in cortex/tests/test_anomaly.py
Priority: HIGH | Confidence: 95%

Rationale:
- Blocks deployment
- Quick fix (~10 min)
- High impact

Command: pytest cortex/tests/test_anomaly.py -v
```
