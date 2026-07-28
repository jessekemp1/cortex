"""Ground-truth corpus for the cortex core-outcomes proof harness.

Data only — no test logic. Two datasets:

* ``SEED_DECISIONS`` / ``DISTRACTOR_DECISIONS`` — synthetic decisions whose
  ``decision`` text carries a deliberately rare token (e.g. ``"Zephyrquay"``)
  that also appears in the paired ``query``. Because the token is shared by the
  decision text (indexed as the pattern *title*) and the query, a retrieval hit
  is unambiguous and **backend-robust**: BM25 alone matches it, so the recall
  metric does not depend on an embeddings backend (Voyage/Ollama) being present.
  Distractors carry their own rare token that appears in NO query, so they can
  only ever be false positives — they keep precision honest.

* ``SEED_OUTCOMES`` — six recommendation outcomes with a known
  3 success / 2 partial / 1 failed mix (all ``followed``), so
  ``outcome_stats`` accuracy can be asserted by exact equality:
  ``(3 + 0.5*2) / 6 == 0.6667`` and ``success_rate == 0.5``.

Seeding gotcha (why ``_point_state_dir`` sets *two* env vars):
  ``mcp_handlers`` resolves the store via ``state_paths.get_cortex_dir()``
  (honors ``CORTEX_STATE_DIR`` then ``CORTEX_HOME``), but
  ``pattern_indexer._load_decisions()`` reads ``CORTEX_HOME`` *directly*. A
  fixture that set only ``CORTEX_STATE_DIR`` would write the seeded decisions
  where the recall benchmark's indexer can't find them. Setting both to the
  same tmp dir keeps writer and reader pointed at one store.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

# ── Ground-truth decisions (10 must-hit) ───────────────────────────────────
# Each rare token appears in BOTH `decision` and `query`. `project` spans the
# real account set so project-scoping paths get exercised incidentally.
SEED_DECISIONS: List[Dict[str, Any]] = [
    {
        "token": "Zephyrquay",
        "decision": "Adopt the Zephyrquay egress queue for Interac outbound batching",
        "context": "Interac serverless is disabled account-wide; needed a classic-compute batching path.",
        "alternatives": "Direct per-message egress; a Kafka bridge.",
        "rationale": "Zephyrquay batches under the CSP egress firewall without serverless.",
        "project": "interac",
        "query": "what did we decide about the Zephyrquay egress queue",
        "must_hit": True,
    },
    {
        "token": "Marlinspike",
        "decision": "Use the Marlinspike snapshot-diff to detect default-enabled Manulife features",
        "context": "Manulife needs feature-governance evidence for default-on previews.",
        "alternatives": "Manual weekly console audit.",
        "rationale": "Marlinspike diffing surfaces silently-enabled features automatically.",
        "project": "manulife-genie",
        "query": "how does Marlinspike snapshot-diff detect default-enabled features",
        "must_hit": True,
    },
    {
        "token": "Basiliskcache",
        "decision": "Route Clio Data Classification tag reads through the Basiliskcache layer",
        "context": "Clio DC->ABAC rollout hit programmatic tag-management limits.",
        "alternatives": "Re-scan per query; in-house YAML tag store.",
        "rationale": "Basiliskcache memoizes class.* tags across regions without re-scan.",
        "project": "clio",
        "query": "why route Clio tag reads through Basiliskcache",
        "must_hit": True,
    },
    {
        "token": "Quokkaflush",
        "decision": "Add the Quokkaflush spool fallback so decisions survive a dead bridge",
        "context": "cortex_record_decision must never lose a decision on primary-append failure.",
        "alternatives": "Fail the write; retry in a loop.",
        "rationale": "Quokkaflush spools one file per entry and replays on next success.",
        "project": "cortex",
        "query": "what is the Quokkaflush spool fallback for recording decisions",
        "must_hit": True,
    },
    {
        "token": "Nimbusgrain",
        "decision": "Seed twin synthetic tables with the Nimbusgrain fidelity profile",
        "context": "twin needs reproducible synthetic UC tables from metadata.",
        "alternatives": "Random seed per run; copy production data.",
        "rationale": "Nimbusgrain fixes seed 42 for byte-stable fidelity checks.",
        "project": "twin",
        "query": "which fidelity profile seeds twin synthetic tables Nimbusgrain",
        "must_hit": True,
    },
    {
        "token": "Obsidiangate",
        "decision": "Gate Interac PCI allow-list changes behind the Obsidiangate review",
        "context": "RFC1918 lockout trap on the account-console IP allow list.",
        "alternatives": "Direct edits; self-service recovery.",
        "rationale": "Obsidiangate blocks private-range entries that would lock out admins.",
        "project": "interac",
        "query": "what does the Obsidiangate review protect on the PCI allow list",
        "must_hit": True,
    },
    {
        "token": "Vermillionsync",
        "decision": "Publish Manulife GWAM CDF through the Vermillionsync bucket workaround",
        "context": "CDF cannot write to a PE-only ADLS; infra migration has no timeline.",
        "alternatives": "Wait for infra migration; abandon CDF.",
        "rationale": "Vermillionsync uses a publicly addressable bucket as the interim path.",
        "project": "manulife-lakebase",
        "query": "how does Vermillionsync unblock Manulife GWAM CDF writes",
        "must_hit": True,
    },
    {
        "token": "Kestrelmark",
        "decision": "Score Genie Spaces with the Kestrelmark /12 rubric aligned to Workbench",
        "context": "genie-iq-score-lite needed a rubric matching the internal Workbench.",
        "alternatives": "Ad-hoc scoring; the old /18 scale.",
        "rationale": "Kestrelmark normalizes to /12 so scores compare to Workbench directly.",
        "project": "genie-iq-score-lite",
        "query": "what is the Kestrelmark rubric for scoring Genie Spaces",
        "must_hit": True,
    },
    {
        "token": "Wolframveil",
        "decision": "Resolve Interac DR-volume FIPS via the Wolframveil egress FQDN allow rules",
        "context": "CSP forces s3-fips endpoints; ca-west-1 FQDN was missing from the allow list.",
        "alternatives": "S3 PrivateLink (refuted: no FIPS support); a shield flag.",
        "rationale": "Wolframveil allow-lists the cross-region FIPS FQDN — minimal correct fix.",
        "project": "interac",
        "query": "how did Wolframveil resolve the Interac DR-volume FIPS blocker",
        "must_hit": True,
    },
    {
        "token": "Cinnabarloop",
        "decision": "Instrument recall with the Cinnabarloop event log to prove memory is used",
        "context": "Needed measurable proof that recorded decisions come back on query.",
        "alternatives": "Trust the tool returns; no instrumentation.",
        "rationale": "Cinnabarloop counts decisions surfaced per query as a hard usage metric.",
        "project": "cortex",
        "query": "what does the Cinnabarloop event log measure about recall",
        "must_hit": True,
    },
]

# ── Distractors (never match any query) ─────────────────────────────────────
DISTRACTOR_DECISIONS: List[Dict[str, Any]] = [
    {
        "token": "Tanglewood",
        "decision": "Tanglewood placeholder decision with no paired query",
        "context": "Distractor: exists only to add corpus noise.",
        "alternatives": "",
        "rationale": "",
        "project": "cortex",
        "query": None,
        "must_hit": False,
    },
    {
        "token": "Umberdrift",
        "decision": "Umberdrift placeholder decision with no paired query",
        "context": "Distractor.",
        "alternatives": "",
        "rationale": "",
        "project": "twin",
        "query": None,
        "must_hit": False,
    },
    {
        "token": "Sablecrest",
        "decision": "Sablecrest placeholder decision with no paired query",
        "context": "Distractor.",
        "alternatives": "",
        "rationale": "",
        "project": "clio",
        "query": None,
        "must_hit": False,
    },
    {
        "token": "Pewtergale",
        "decision": "Pewtergale placeholder decision with no paired query",
        "context": "Distractor.",
        "alternatives": "",
        "rationale": "",
        "project": "interac",
        "query": None,
        "must_hit": False,
    },
    {
        "token": "Fernwhistle",
        "decision": "Fernwhistle placeholder decision with no paired query",
        "context": "Distractor.",
        "alternatives": "",
        "rationale": "",
        "project": "manulife-genie",
        "query": None,
        "must_hit": False,
    },
]

# ── Ground-truth outcomes (3 success / 2 partial / 1 failed, all followed) ──
# `outcome` values only; timestamps are stamped at seed time so they land
# inside outcome_stats' default 30-day window.
SEED_OUTCOMES: List[Dict[str, Any]] = [
    {"recommendation_id": "proof_1", "outcome": "success", "followed": True},
    {"recommendation_id": "proof_2", "outcome": "success", "followed": True},
    {"recommendation_id": "proof_3", "outcome": "success", "followed": True},
    {"recommendation_id": "proof_4", "outcome": "partial", "followed": True},
    {"recommendation_id": "proof_5", "outcome": "partial", "followed": True},
    {"recommendation_id": "proof_6", "outcome": "failed", "followed": True},
]

# Expected stats over SEED_OUTCOMES (asserted by exact equality in tests).
EXPECTED_ACCURACY = round((3 + 0.5 * 2) / 6, 4)  # 0.6667
EXPECTED_SUCCESS_RATE = round(3 / 6, 4)  # 0.5
SEED_PROJECT = "prooftest"


# ── Seeding helpers ─────────────────────────────────────────────────────────


def _point_state_dir(state_dir: Path) -> None:
    """Point both store env vars at ``state_dir``.

    See the module docstring: writer (mcp_handlers via CORTEX_STATE_DIR) and
    reader (pattern_indexer via CORTEX_HOME) resolve the store differently, so
    both must agree for the recall benchmark to see seeded decisions.
    """
    os.environ["CORTEX_STATE_DIR"] = str(state_dir)
    os.environ["CORTEX_HOME"] = str(state_dir)


def _ensure_repo_on_path() -> None:
    """Make ``mcp_handlers`` / ``state_paths`` importable when tests run from
    the repo root without installation. Idempotent."""
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def seed_decisions(state_dir: Path, include_distractors: bool = True) -> List[Dict[str, Any]]:
    """Write the seed (and optionally distractor) decisions to ``state_dir``.

    Uses the real ``mcp_handlers.record_learning_decision`` so the record path
    itself is exercised. Returns the corpus rows augmented with the minted
    ``decision_id`` for each, newest write last.
    """
    _point_state_dir(state_dir)
    _ensure_repo_on_path()
    from mcp_handlers import record_learning_decision

    rows = list(SEED_DECISIONS)
    if include_distractors:
        rows = rows + list(DISTRACTOR_DECISIONS)

    recorded: List[Dict[str, Any]] = []
    for d in rows:
        res = record_learning_decision(
            decision=d["decision"],
            context=d.get("context", ""),
            alternatives=d.get("alternatives", ""),
            rationale=d.get("rationale", ""),
            project=d.get("project", ""),
            source="prooftest",
        )
        recorded.append({**d, "decision_id": res["decision_id"]})
    return recorded


def seed_outcomes(state_dir: Path) -> List[Dict[str, Any]]:
    """Write ``SEED_OUTCOMES`` to ``state_dir/outcomes.jsonl``.

    Written directly in the OutcomeEntry line schema that ``read_outcomes`` /
    ``outcome_stats`` consume (the live writer is ``feedback.FeedbackLogger``,
    which is heavier than this proof needs). Timestamps are stamped now so the
    rows fall inside the default 30-day stats window.
    """
    _point_state_dir(state_dir)
    _ensure_repo_on_path()

    now = datetime.now()
    path = Path(state_dir) / "outcomes.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    written: List[Dict[str, Any]] = []
    with open(path, "a", encoding="utf-8") as f:
        for i, o in enumerate(SEED_OUTCOMES):
            entry = {
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "recommendation_id": o["recommendation_id"],
                "recommendation_title": f"Proof outcome {o['recommendation_id']}",
                "recommendation_type": "next_action",
                "priority": "high",
                "confidence": 0.9,
                "followed": o["followed"],
                "outcome": o["outcome"],
                "notes": "proof harness seed",
                "context": {"project": SEED_PROJECT},
                "domain": "aidev",
            }
            f.write(json.dumps(entry) + "\n")
            written.append(entry)
    return written
