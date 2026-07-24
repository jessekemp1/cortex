# Beta cohort — v1.2.0-beta.1

The release is live (tag `v1.2.0-beta.1`, GitHub prerelease). This is the
operational checklist for **starting** the beta. Keep the cohort small.

## Cohort

- **Cap: 5–10 users.** Small enough that single-maintainer support (doctor-first,
  issue template) stays sane — that's a named risk in the release plan.
- Prefer users who (a) work in Claude Code daily, (b) will actually record
  decisions, and (c) will file a `beta:` issue rather than suffer in silence.
- Candidate pool (fill in): CAN DSA peers with an active build, ______.

## Before inviting anyone

- [x] Tag + GitHub prerelease published.
- [x] `docs/GETTING_STARTED.md` is the single onboarding path (Mode A runbook +
      Mode B `./install.sh --yes`).
- [x] Beta issue template (`.github/ISSUE_TEMPLATE/beta_feedback.yml`) requires
      `cortex doctor --json`.
- [ ] Repo access: confirm the invitees can read `jessekemp1/cortex` (it's public,
      so clone works — no action unless that changes).
- [ ] One-paragraph invite drafted (see below) — **your voice, your send.**

## Invite (draft — review + send yourself)

> Cortex is a persistent memory layer for Claude Code — it remembers the
> decisions you make across sessions and surfaces them when they're relevant.
> v1.2.0-beta.1 is ready for a small beta.
>
> Setup is one command and needs no API key for the core loop:
> `git clone https://github.com/jessekemp1/cortex && cd cortex && ./install.sh --yes`,
> then restart Claude Code. Full walkthrough: `docs/GETTING_STARTED.md`.
>
> Two asks: (1) time yourself — it should be under ~15 min to `cortex demo`
> printing the trail; (2) file anything rough as a **Beta feedback** issue
> (it'll ask for `cortex doctor --json` — that's how I debug your box).
>
> Honest beta caveat: retrieval ranking is still rough — a decision you just
> recorded may not surface in the very next query. The write is durable; ranking
> is the next thing I'm tuning.

## What to watch once they're in

- First `beta:` issues → triage doctor-first (the `--json` block tells you the
  environment in one paste).
- The **≤15-min setup** promise: the issue template captures each user's
  self-reported setup time — watch for anyone who blew past it (that's the #1
  thing to fix for the next beta).
- `cortex stats` follow-rate: only meaningful once a user crosses n≥10 feedback
  signals (renders "too few to rate" below that — by design).

## Explicitly NOT in this beta

Retrieval-precision tuning, PyPI wheel (git-clone-only), Windows, a second
LaunchAgent, telemetry upload. See `docs/releases/v1.2.0-beta.1.md`.
