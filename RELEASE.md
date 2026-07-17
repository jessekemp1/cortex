# Releasing Cortex

This is the operator runbook for cutting a Cortex release. It is written to be
executed by an agent or a human, top to bottom. **Nothing reaches `main` and no
tag is cut until the confidence gate (below) is fully green.**

Current target: **`1.2.0b1`**, tag **`v1.2.0-beta.1`** — the first shippable
beta. Git-clone-only (no published wheel yet).

---

## 0. Pre-flight

- [ ] You are on the release branch (`release/1.2.0`), not `main`.
- [ ] Working tree clean (`git status`).
- [ ] `pyproject.toml` `version` matches the intended release (`1.2.0b1`).
- [ ] `CHANGELOG.md` has an entry for this version with an accurate date and an
      honest **Known limitations** section.
- [ ] A fresh Python 3.12 venv is available for verification (this repo is
      validated on 3.11 and 3.12).

## 1. Build & install verification (packaging)

The console scripts (`cortex`, `cortex-mcp`) must import from an *installed*
artifact, not just the repo cwd. This has been the #1 source of broken releases.

```bash
python -m venv /tmp/rel-verify && . /tmp/rel-verify/bin/activate
pip install build
python -m build --wheel --outdir /tmp/rel-wheel
pip install "/tmp/rel-wheel/"*.whl"[server]"
cd /tmp                      # leave the repo tree so we import the installed copy
python -c "import cli, mcp_server, mcp_handlers, state_paths, config, bridge; print('installed imports OK')"
cortex --help >/dev/null && echo "cortex --help exit $?"
```

- [ ] Wheel builds.
- [ ] `import cli` and `import mcp_server` succeed from outside the repo.
- [ ] `cortex --help` exits 0.

## 2. Test suite

```bash
# Hermetic CI-scope suite (synthetic/ needs the [analytics] extras; excluded).
CORTEX_ROOT_DIR=/tmp/rel-home python -m pytest -p no:cacheprovider --ignore=synthetic/tests -q
```

- [ ] 0 failed. Record the passed count — it must be >= the CI floor in
      `.github/workflows/ci.yml`.

## 3. MCP surface

```bash
# Without the flag: only the golden-five (+ any briefing-hook tools) register.
python scripts/smoke_mcp.py            # must pass with NO bridge running
```

- [ ] `smoke_mcp.py` passes bridge-down.
- [ ] `list_tools` without `CORTEX_EXPERIMENTAL` returns exactly the golden five
      (+ documented briefing tools); with `CORTEX_EXPERIMENTAL=1` returns the
      full set.

## 4. Honesty sweep

- [ ] No hardcoded/fabricated metrics in any user-facing surface (TUI, CLI,
      dashboard, reports). `GET /v2/outcomes/stats` returns real/empty data, not
      a 501 stub.
- [ ] README test-count badge equals the enforced CI floor.
- [ ] Recall-precision limitation is stated plainly in the beta notes.

## 5. CI

- [ ] CI is green on Linux 3.11 + 3.12 (full suite, enforced floor) AND macOS
      3.12 (install + doctor + demo + suite).
- [ ] Wheel canary job present (non-blocking) — its state reflects reality.

## 6. Confidence gate (all 10 green or NO tag)

1. Clean-machine macOS install (fresh account/VM): clone → `install.sh --yes` →
   `doctor` all-green, ≤15 min, zero interventions.
2. Full suite green in CI: Linux 3.11+3.12 AND macOS 3.12, enforced count floor.
3. Core MCP crash-proof: `smoke_mcp.py` passes bridge-down AND bridge-up; spool
   drains on `doctor --fix`.
4. Chaos test: induce the top-5 failures (bridge dead, spool backlog,
   launchagent unloaded, stale SQLite lock, missing key) → `doctor` detects 5/5,
   `--fix` repairs the repairable.
5. Zero fake data (honesty sweep + repo-wide grep clean).
6. `GETTING_STARTED` executed verbatim by an agent on a clean account, zero
   deviations.
7. Key UX closed: `.env` actually read; briefing works without a shell export.
8. Release artifacts complete (version, CHANGELOG, tag, Release draft).
9. Rollback rehearsed: `git checkout v1.1.0` works after running 1.2 (no
   backward-incompatible `~/.cortex` mutations; new spool/WAL files ignorable by
   1.1).
10. Claims honesty: README badge == enforced CI count; calibrations merged;
    recall limitation stated in beta notes.

> Any gate that can only be *simulated* here (e.g. a true fresh-VM install) is
> run in a sandboxed clean `HOME` and **labeled as a simulation** in the gate
> evidence. A gate that cannot be honestly greened blocks the tag.

## 7. Cut

```bash
# Only after the gate is 10/10 green.
git checkout main && git merge --no-ff release/1.2.0 -m "release: 1.2.0b1"
git tag -a v1.2.0-beta.1 -m "Cortex 1.2.0-beta.1"
git push origin main --tags
```

## 8. Publish

- [ ] Draft a GitHub Release for `v1.2.0-beta.1`:
  - What's new (from CHANGELOG).
  - Known limitations (recall precision; git-clone-only, no wheel).
  - Install: `git clone … && ./install.sh --yes`.
- [ ] Beta cohort capped at 5–10. Issue template requires `cortex doctor --json`
      output.

## 9. Post

- [ ] Record the ship decision + gate evidence to cortex
      (`cortex_record_decision`).
- [ ] Branch cleanup: delete merged release/workstream branches; close
      superseded PRs with a pointer (see the plan's branch-cleanup list).

## 10. Rollback

If a released build misbehaves:

```bash
git checkout v1.1.0        # previous good tag
```

- New `~/.cortex` files introduced by 1.2 (spool/, WAL) are additive and
  ignorable by 1.1 — no destructive migration to undo. Verify the running
  process picks up the older code (restart the bridge / Claude Code MCP).
