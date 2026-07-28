"""Decision-store importance heuristic (P1 curation).

Scores a learning-loop decision 1..10 so the write path can flag low-signal
noise (test rows, empty template entries) and the retriever can down-weight it.
The research (cortex dec_824f8f0f2bd4) found that a decision store which only
grows recalls worse — curation, not capacity, separates useful memory from
noise. This is the cheap, deterministic first line of that curation: NO model
call, NO I/O, pure function of the four decision fields.

An optional LLM 1..10 scorer (the Generative-Agents pattern) is a future,
flag-gated addition; this heuristic is the always-on baseline.
"""
from __future__ import annotations

import os
import re

# Below this score a decision is flagged low_signal on write and down-weighted
# on recall. Env-overridable; default 3 keeps genuine one-liners in but drops
# empty/template noise.
IMPORTANCE_FLOOR = int(os.environ.get("CORTEX_IMPORTANCE_FLOOR", "3"))

# Template / test-row markers — the class of junk that floods the store.
_TEMPLATE_RE = re.compile(
    r"^\s*(test[\s_]|integration test|placeholder|todo|tbd|ok\b|foo\b|bar\b|example\b)",
    re.IGNORECASE,
)

_BASE = 5


def _importance_score(
    decision: str,
    context: str = "",
    alternatives: str = "",
    rationale: str = "",
) -> int:
    """Return an importance score in 1..10. Deterministic, side-effect free.

    Heuristic: start at a neutral base, reward supporting fields and substance,
    penalise emptiness, brevity, and template/test markers.
    """
    decision = (decision or "").strip()
    context = (context or "").strip()
    alternatives = (alternatives or "").strip()
    rationale = (rationale or "").strip()

    score = _BASE

    # Supporting fields: each present field is evidence of a real decision.
    for field in (context, alternatives, rationale):
        if field:
            score += 1

    # Substance: a developed decision statement.
    if len(decision) >= 80:
        score += 1
    if len(decision) < 40:
        score -= 2

    # Total corpus length — a rich record across all fields.
    total = len(decision) + len(context) + len(alternatives) + len(rationale)
    if total >= 400:
        score += 1

    # Template / test noise — the thing we most want to suppress.
    if _TEMPLATE_RE.match(decision):
        score -= 3

    # An entry with no supporting context AND no rationale is weak signal.
    if not context and not rationale:
        score -= 2

    return max(1, min(10, score))
