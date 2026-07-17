"""`cortex stats` — Value receipts, real data only.

Proves Cortex is being USED, not just installed. Every number here is read
from a real store under the Cortex state dir; nothing is invented.

Two honesty invariants, enforced in code (not by convention):

  1. **n<10 → not a rate.** Any rate computed from fewer than
     ``MIN_RATE_SAMPLES`` (=10) samples renders as ``n=X — too few to rate``,
     never a percentage. A rate over a tiny sample is noise dressed as signal.

  2. **All-zero → empty state, not fake stats.** On a fresh install every
     receipt is genuinely zero. Rather than print a wall of ``0``s (which reads
     like a broken dashboard), we render a designed EMPTY STATE: a short "no
     receipts yet — here's how to earn them" plus a milestone checklist and a
     nudge to run ``cortex demo``. The receipts region carries no fabricated
     digits.

Data sources (all real):
  * decisions.jsonl                — recorded decisions (total + last 7d)
  * compound_metrics.full_report() — outcomes / sessions / memory items
  * ImplicitFeedbackCollector      — follow / ignore / override + follow_rate
  * recall_events.jsonl            — decisions resurfaced / memory recalls
  * prompt_outcomes.jsonl          — FK outcome links (prompt → commit/test)
  * seed_patterns.get_seed_patterns() — active anti-pattern count (runtime)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# A rate needs at least this many samples before we quote a number.
MIN_RATE_SAMPLES = 10

_LINE = "═" * 58
_THIN = "─" * 58


# ── real-data readers ──────────────────────────────────────────────────────


def _cortex_dir() -> Path:
    from state_paths import get_cortex_dir

    return get_cortex_dir()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL file into a list of dicts. Missing/corrupt → []."""
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                out.append(obj)
    except OSError:
        return []
    return out


def _decisions_stats(cortex_dir: Path) -> Dict[str, int]:
    """Total decisions recorded + those in the last 7 days (real jsonl)."""
    entries = _read_jsonl(cortex_dir / "decisions.jsonl")
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    recent = 0
    for e in entries:
        ts = str(e.get("timestamp") or e.get("created_at") or "")
        if ts and ts >= cutoff:
            recent += 1
    return {"total": len(entries), "recent_7d": recent}


def _fk_links_count(cortex_dir: Path) -> int:
    """Count real FK outcome links (prompt → commit/test) on disk."""
    return len(_read_jsonl(cortex_dir / "prompt_outcomes.jsonl"))


def _feedback_stats(cortex_dir: Path) -> Dict[str, Any]:
    """Implicit feedback follow/ignore/override over 7d, from the real store."""
    try:
        from intelligence.feedback.implicit_collector import ImplicitFeedbackCollector

        collector = ImplicitFeedbackCollector(
            storage_path=cortex_dir / "implicit_feedback.jsonl"
        )
        return collector.get_stats(7)
    except Exception:
        return {
            "total_signals": 0,
            "follows": 0,
            "ignores": 0,
            "overrides": 0,
            "avg_time_to_action": 0,
            "follow_rate": 0,
        }


def _anti_pattern_count() -> int:
    """Active seed anti-patterns — counted at runtime, never hardcoded."""
    try:
        from intelligence.memory.seed_patterns import get_seed_patterns

        return len(get_seed_patterns())
    except Exception:
        return 0


def _bridge_up() -> bool:
    import socket

    try:
        s = socket.create_connection(("127.0.0.1", 8765), timeout=0.5)
        s.close()
        return True
    except OSError:
        return False


# ── report assembly (structured — testable without parsing text) ────────────


def build_stats_report() -> Dict[str, Any]:
    """Assemble the value-receipts report from real data only.

    Returns a structured dict. ``empty`` is True iff every usage receipt is
    genuinely zero (day-1) — the renderer uses that to switch to the empty
    state. No field is ever fabricated; absent data reads as 0.
    """
    cortex_dir = _cortex_dir()

    decisions = _decisions_stats(cortex_dir)
    fk_links = _fk_links_count(cortex_dir)
    feedback = _feedback_stats(cortex_dir)

    # Outcomes / sessions / memory items via the compounding report.
    try:
        from measurement.compound_metrics import full_report

        compound = full_report()
    except Exception:
        compound = {}
    outcomes = compound.get("outcomes", {}) or {}
    sessions = compound.get("sessions", {}) or {}
    working_memory = compound.get("working_memory", {}) or {}

    # Recall usage (Workstream B2 events).
    try:
        from intelligence.recall_events import recall_summary

        recall = recall_summary(7)
    except Exception:
        recall = {
            "total_recalls": 0,
            "recalls_7d": 0,
            "decisions_resurfaced": 0,
            "predictions_surfaced": 0,
        }

    memory_items = int(working_memory.get("items", 0) or 0)
    outcomes_total = int(outcomes.get("total", 0) or 0)
    sessions_total = int(sessions.get("total_sessions", 0) or 0)

    # Day-1 detector: every usage receipt is zero.
    usage_total = (
        decisions["total"]
        + memory_items
        + sessions_total
        + outcomes_total
        + int(recall.get("total_recalls", 0) or 0)
        + int(feedback.get("total_signals", 0) or 0)
        + fk_links
    )

    return {
        "empty": usage_total == 0,
        "anti_patterns_active": _anti_pattern_count(),
        "bridge_up": _bridge_up(),
        "decisions": decisions,
        "memory_items": memory_items,
        "sessions_total": sessions_total,
        "outcomes_total": outcomes_total,
        "outcomes_recent_7d": int(outcomes.get("recent_7d", 0) or 0),
        "fk_outcome_links": fk_links,
        "recall": recall,
        "feedback": feedback,
    }


# ── rate helper (the n<10 honesty gate) ─────────────────────────────────────


def format_rate(numerator: int, denominator: int, label: str = "") -> str:
    """Render a rate, or refuse to when the sample is too small.

    Denominator (sample size) < MIN_RATE_SAMPLES → ``n=X — too few to rate``.
    Otherwise a percentage. This is the single choke point for every rate in
    the report, so the n<10 rule can't be bypassed by accident.
    """
    if denominator < MIN_RATE_SAMPLES:
        return f"n={denominator} — too few to rate"
    pct = round(100 * numerator / denominator)
    return f"{pct}%  (n={denominator})"


# ── renderers ────────────────────────────────────────────────────────────────


def _render_empty(report: Dict[str, Any]) -> str:
    """Day-1 empty state: milestone checklist + demo nudge, no fake numbers.

    Layout note (honesty contract): the anti-pattern count and bridge health
    are FACTS and live in the header/status region ABOVE the "No receipts yet"
    marker. Everything from that marker down is the RECEIPTS region, which in
    the empty state carries no fabricated digits — the only digit-bearing line
    is the ``n >= 10`` checklist item.
    """
    ap = report["anti_patterns_active"]
    bridge = "up" if report["bridge_up"] else "not running (in-process OK)"
    lines = [
        _LINE,
        "  CORTEX — VALUE RECEIPTS   (real data only)",
        _LINE,
        "",
        f"  Health:  bridge {bridge} · MCP recall in-process",
        f"  {ap} anti-patterns active (seeded, surfacing on matching tasks)",
        "",
        "  No receipts yet — here's how to earn them.",
        "",
        "  Cortex is installed but hasn't recorded anything yet. Receipts",
        "  accrue automatically as you work. Milestones:",
        "",
        "    ☐ First decision recorded",
        "    ☐ First memory recall",
        "    ☐ First outcome linked  (prompt → commit)",
        "    ☐ Follow-rate measurable  (needs n ≥ 10 feedback signals)",
        "",
        "  Start now:  cortex demo    (a fast, no-API-key proof of the loop)",
        _LINE,
    ]
    return "\n".join(lines)


def _render_populated(report: Dict[str, Any]) -> str:
    """Populated report: real receipts, with the n<10 gate on the follow-rate."""
    d = report["decisions"]
    fb = report["feedback"]
    recall = report["recall"]
    ap = report["anti_patterns_active"]
    bridge = "up" if report["bridge_up"] else "not running (in-process OK)"

    total_signals = int(fb.get("total_signals", 0) or 0)
    follows = int(fb.get("follows", 0) or 0)
    overrides = int(fb.get("overrides", 0) or 0)
    ignores = int(fb.get("ignores", 0) or 0)
    # follow_rate = (follows + overrides) / total_signals — gated by sample size.
    follow_rate_str = format_rate(follows + overrides, total_signals)

    lines = [
        _LINE,
        "  CORTEX — VALUE RECEIPTS   (real data only)",
        _LINE,
        "",
        f"  Health:  bridge {bridge} · MCP recall in-process",
        f"  {ap} anti-patterns active (seeded)",
        "",
        "  Receipts",
        _THIN,
        f"  Decisions recorded      : {d['total']:>5}   ({d['recent_7d']} in last 7d)",
        f"  Memory items            : {report['memory_items']:>5}",
        f"  Sessions tracked        : {report['sessions_total']:>5}",
        f"  Outcomes recorded       : {report['outcomes_total']:>5}   "
        f"({report['outcomes_recent_7d']} in last 7d)",
        f"  FK outcome links        : {report['fk_outcome_links']:>5}   (prompt → commit/test)",
        "",
        "  Memory is being used",
        _THIN,
        f"  Intelligence recalls    : {recall['total_recalls']:>5}   "
        f"({recall['recalls_7d']} in last 7d)",
        f"  Decisions resurfaced    : {recall['decisions_resurfaced']:>5}",
        f"  Predictions surfaced    : {recall['predictions_surfaced']:>5}",
        "",
        "  Recommendation feedback",
        _THIN,
        f"  Follows / Overrides     : {follows} / {overrides}",
        f"  Ignores                 : {ignores}",
        f"  Follow-rate             : {follow_rate_str}",
        _LINE,
    ]
    return "\n".join(lines)


def render_stats(report: Dict[str, Any]) -> str:
    """Render either the empty state or the populated receipts report."""
    if report.get("empty"):
        return _render_empty(report)
    return _render_populated(report)


# ── CLI entry point ──────────────────────────────────────────────────────────


def cmd_stats(args: Optional[Any] = None) -> None:
    """`cortex stats` — print the value-receipts report (real data only).

    ``--json`` emits the structured report for scripting; otherwise the
    human-readable report (empty state on day-1).
    """
    # SHOULD-tier opportunistic outcome-linker (B3): produce genuine FK links
    # from any new real interaction-queue entries before we count them. No
    # daemon, best-effort — never blocks the report.
    try:
        _run_opportunistic_linker()
    except Exception:
        pass

    report = build_stats_report()

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, default=str))
        return

    print(render_stats(report))


def _run_opportunistic_linker() -> Dict[str, int]:
    """B3: link new real interaction_queue entries → prompt_outcomes.jsonl.

    Uses the real ``intelligence.outcome_linker`` against the live
    interaction_queue.jsonl under the Cortex state dir, then appends only NEW
    links (the linker is idempotent by prompt_id). Returns a small summary.
    Never invents data: if the queue is absent/empty, nothing is written.
    """
    from intelligence.outcome_linker import (
        _existing_prompt_ids,
        link_outcomes,
        write_linked_outcomes,
    )

    cortex_dir = _cortex_dir()
    queue = cortex_dir / "interaction_queue.jsonl"
    outcomes = cortex_dir / "prompt_outcomes.jsonl"
    if not queue.exists():
        return {"linked": 0, "new": 0}

    linked = link_outcomes(queue_path=queue)
    before = len(_existing_prompt_ids(outcomes_path=outcomes))
    write_linked_outcomes(linked, outcomes_path=outcomes)
    after = len(_existing_prompt_ids(outcomes_path=outcomes))
    return {"linked": len(linked), "new": after - before}
