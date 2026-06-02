# Contributing to Cortex

Thanks for looking. Cortex is small, opinionated, and still finding its shape — your critique is more valuable than your patches at this stage.

## Quickstart (60 seconds)

```bash
git clone https://github.com/jessekemp1/cortex.git
cd cortex
pip install -e ".[server]"           # core + FastAPI bridge
cortex demo                           # 30-second proof of the FK loop, no API key needed
```

If `cortex demo` prints an FK trail with linked prompts and commit hashes, your install works. That demo is the canonical falsifiable artifact for the project's headline claim.

To use the LLM-backed commands:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cortex doctor                         # full environment health check
cortex status                         # current state across your projects
cortex briefing                       # daily summary with recommendations
```

## Running tests

```bash
pytest --collect-only -q              # must exit 0 with no collection errors
pytest tests/test_outcome_linker.py   # FK contract integration test
pytest                                # full suite (some tests require a populated ~/.cortex)
```

If `pytest --collect-only` reports errors, that's a release blocker — file an issue.

## Filing issues

- Bugs → use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Include `cortex doctor` output and the commit SHA you saw the bug on (`git rev-parse HEAD`).
- Feature requests → use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml). Check `ROADMAP.md` first.
- Audit findings / depth-probe critique → especially welcome. See `SHIP_PUNCHLIST.md` for what's already known.

## Where to start reading

| Goal | Read |
|---|---|
| Understand the value proposition | `README.md` |
| Run the 30-second proof | `cortex demo` (then `cli/commands/demo.py`) |
| Understand the FK loop | `intelligence/outcome_linker.py` (≤ 130 LOC) |
| Understand routing | `supervisor/router.py` |
| Understand the audit posture | `SHIP_PUNCHLIST.md`, `CORTEX_VERIFICATION_*.md` |
| Understand strategy | `ROADMAP.md` |

## Style

- Python ≥ 3.11. Type hints on public functions.
- Tests are required for behavior changes. Trivial assertions (`assert x is not None` standalone) are not accepted — assert on values.
- Commits use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`).
- One concern per PR. Sweeping refactors get reverted.

## Honesty policy

If the README claims something the code doesn't do, the README is the bug. File the issue against the docs.

Cortex's principal author runs an adversarial audit of the public repo periodically (see `SHIP_PUNCHLIST.md` for the most recent). External findings that lower the next audit's score are particularly appreciated.
