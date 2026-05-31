"""Links prompts to downstream outcomes via temporal proximity.

A git_commit or test_result within 90 seconds of a prompt_received
is attributed to that prompt. Writes FK linkage to ~/.cortex/prompt_outcomes.jsonl.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE = Path.home() / ".cortex" / "interaction_queue.jsonl"
OUTCOMES = Path.home() / ".cortex" / "prompt_outcomes.jsonl"
WINDOW_SECONDS = 90


def _parse_ts(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def link_outcomes() -> list[dict]:
    """Read interaction_queue, link outcomes to prompts within WINDOW_SECONDS."""
    if not QUEUE.exists():
        return []

    entries = []
    for line in QUEUE.read_text().strip().splitlines():
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Sort by timestamp
    entries.sort(key=lambda e: e.get("queued_at", ""))

    linked = []
    for i, entry in enumerate(entries):
        if entry.get("type") != "prompt_received":
            continue

        prompt_ts = _parse_ts(entry["queued_at"])
        prompt_id = entry.get("session_id", "?") + "_" + str(i)

        outcomes = []
        for j in range(i + 1, len(entries)):
            other = entries[j]
            if other.get("type") == "prompt_received" and other.get("session_id") == entry.get(
                "session_id"
            ):
                break  # Next prompt in same session — stop looking
            other_ts = _parse_ts(other["queued_at"])
            delta = (other_ts - prompt_ts).total_seconds()
            if 0 <= delta <= WINDOW_SECONDS:
                outcomes.append(other)
            elif delta > WINDOW_SECONDS:
                break

        if outcomes:
            score = _compute_outcome_score(outcomes)
            linked.append(
                {
                    "prompt_id": prompt_id,
                    "prompt_text": entry.get("prompt", "")[:120],
                    "session_id": entry.get("session_id"),
                    "prompt_ts": entry["queued_at"],
                    "outcome_score": score,
                    "outcomes": outcomes,
                }
            )

    return linked


def _compute_outcome_score(outcomes: list[dict]) -> float:
    """score = 0.4*(tests_passed_ratio) + 0.4*(commit_landed) + 0.2*(any_outcome)"""
    commit_landed = any(o.get("type") == "git_commit" for o in outcomes)
    test_results = [o for o in outcomes if o.get("type") == "test_result"]

    if test_results:
        last = test_results[-1]
        total = last.get("passed", 0) + last.get("failed", 0) + last.get("error", 0)
        pass_ratio = last.get("passed", 0) / total if total > 0 else 0.5
    else:
        pass_ratio = 0.5

    return round(
        0.4 * pass_ratio + 0.4 * float(commit_landed) + 0.2 * 1.0,  # any outcome = activity signal
        3,
    )


def _existing_prompt_ids() -> set[str]:
    if not OUTCOMES.exists():
        return set()
    seen = set()
    for line in OUTCOMES.read_text().splitlines():
        if not line:
            continue
        try:
            seen.add(json.loads(line).get("prompt_id"))
        except json.JSONDecodeError:
            continue
    return seen


def write_linked_outcomes(linked: list[dict]) -> None:
    existing = _existing_prompt_ids()
    with open(OUTCOMES, "a") as f:
        for entry in linked:
            if entry.get("prompt_id") in existing:
                continue
            f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    linked = link_outcomes()
    existing_before = len(_existing_prompt_ids())
    write_linked_outcomes(linked)
    new_count = len(_existing_prompt_ids()) - existing_before
    print(f"Linked {len(linked)} candidates, {new_count} new (idempotent skip of duplicates)")
    if linked:
        scores = [l["outcome_score"] for l in linked]
        print(
            f"Score range: {min(scores):.2f} – {max(scores):.2f}, mean: {sum(scores) / len(scores):.2f}"
        )
