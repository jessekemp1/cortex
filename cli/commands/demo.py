"""`cortex demo` — 30-second self-contained proof of the prompt→outcome FK loop.

Synthesizes 5 prompts and 3 outcomes (commits) in an isolated tempdir, runs
the real `intelligence.outcome_linker.link_outcomes()` against them, and prints
the FK trail with computed outcome scores.

No API key required. No network. Read-only against the system Cortex install
(uses a tempdir for its data).

This is the falsifiable demonstration of the "compounding intelligence" claim:
if it prints links, the FK contract is live in this build.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _build_synthetic_queue() -> list[dict]:
    base = datetime.now(timezone.utc)
    sessions = ["sess_alpha", "sess_beta", "sess_alpha", "sess_gamma", "sess_alpha"]
    prompts = [
        "Why is the test suite hanging on Redis?",
        "Add idempotency to outcome_linker",
        "Recheck Redis hang root cause",
        "Score the new prompt-outcome FK loop",
        "Land idempotency patch",
    ]
    events: list[dict] = []
    for i, (sid, p) in enumerate(zip(sessions, prompts)):
        events.append(
            {
                "type": "prompt_received",
                "session_id": sid,
                "prompt": p,
                "queued_at": (base + timedelta(seconds=i * 120)).isoformat(),
            }
        )
    # 3 outcomes within the 90-second window of a select prompts (idx 1, 3, 4)
    for prompt_idx, sha, msg in [
        (1, "abc123", "feat: idempotency in outcome_linker"),
        (3, "def456", "fix: tune FK score weights"),
        (4, "789aaa", "feat: land idempotency patch"),
    ]:
        events.append(
            {
                "type": "git_commit",
                "session_id": sessions[prompt_idx],
                "hash": sha,
                "message": msg,
                "queued_at": (base + timedelta(seconds=prompt_idx * 120 + 30)).isoformat(),
            }
        )
    return events


def cmd_demo(args) -> None:
    print("╔══════════════════════════════════════════════════════╗")
    print("║   CORTEX DEMO — prompt→outcome FK loop (30 sec)     ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print("• Synthesizing isolated queue (5 prompts, 3 commits)...")

    events = _build_synthetic_queue()

    with tempfile.TemporaryDirectory(prefix="cortex_demo_") as tmp:
        tmp_path = Path(tmp)
        queue = tmp_path / "interaction_queue.jsonl"
        outcomes = tmp_path / "prompt_outcomes.jsonl"
        with open(queue, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        # Use the real linker module; redirect its module-level paths so it
        # operates against the synthesized tempdir queue.
        import intelligence.outcome_linker as ol

        original_queue, original_outcomes = ol.QUEUE, ol.OUTCOMES
        ol.QUEUE = queue
        ol.OUTCOMES = outcomes
        try:
            linked = ol.link_outcomes()
            ol.write_linked_outcomes(linked)
        finally:
            ol.QUEUE, ol.OUTCOMES = original_queue, original_outcomes

    print(f"• Ran intelligence.outcome_linker.link_outcomes() → {len(linked)} prompts linked")
    print()
    if not linked:
        print("⚠ No links produced — FK contract is BROKEN in this build.")
        sys.exit(1)

    print("FK trail:")
    print("─" * 56)
    for entry in linked:
        score = entry["outcome_score"]
        prompt = entry["prompt_text"]
        outs = entry["outcomes"]
        commit_sha = next((o.get("hash", "") for o in outs if o.get("type") == "git_commit"), "")
        flag = "✓" if commit_sha else "·"
        commit_str = f"  → commit {commit_sha[:7]}" if commit_sha else ""
        print(f"  {flag} [score {score:>4.2f}] {prompt[:48]:<48}{commit_str}")
    print("─" * 56)
    print()
    print(f"Score components (per intelligence/outcome_linker.py):")
    print("  0.4 * test_pass_ratio  +  0.4 * commit_landed  +  0.2 * activity")
    print()
    print("This output was generated with NO API key and NO network call.")
    print("The same linker runs every 15 min via com.cortex.outcome-linker")
    print("on your installed Cortex once you set it up.")
