# Cortex Installation

The canonical install guide is **[`INSTALL.md`](../INSTALL.md)** in the repo root.

It is kept current; this file previously held a separate (Dec 2025) copy that
drifted out of date. The full prior version remains in git history if needed.

Quick start:

```bash
git clone https://github.com/jessekemp1/cortex && cd cortex
python -m venv .venv && source .venv/bin/activate
pip install -e .
cortex doctor
```

See [`INSTALL.md`](../INSTALL.md) for configuration, MCP/Claude Code
integration, and troubleshooting.
