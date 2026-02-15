# Codex Hook Setup

Codex can publish events into the same Cortex interaction queue used by Claude hooks.

## Install

```bash
cd /Users/jesse.kemp/Dev/cortex
./hooks/install_codex_hooks.sh
```

## Verify

```bash
printf '{"event":"prompt","session_id":"cx1","cwd":"/tmp","prompt":"hello"}' | python hooks/codex_interaction_capture.py
printf '{"event":"session_end","session_id":"cx1","cwd":"/tmp","reason":"exit"}' | python hooks/codex_interaction_capture.py
python cli.py interactions --process
python cli.py bandwidth queue-slo --json
```
