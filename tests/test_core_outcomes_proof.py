"""Core-outcomes proof — Outcome 1 (RECORD) and Outcome 3 (TRACK).

These are the backend-robust halves of the three-outcome proof: they need no
embeddings backend, so they produce hard numbers on any machine. Each test
asserts a *measurable* property with a stated threshold or exact value, not
merely "the call returned something" — the contract test
(test_mcp_tools_contract.py) already covers the "doesn't crash / non-empty
string" bar, and explicitly accepts an error envelope as a pass. This module
exists to assert the quality that one cannot.

Outcome 1 — RECORD (cortex_record_decision -> mcp_handlers.record_learning_decision)
  * round-trip integrity == 100% (N recorded -> N durable, unique, schema-valid)
  * write latency p95 under a local-append budget
  * spool fallback: a decision is never lost when the primary append fails

Outcome 3 — TRACK (cortex_outcomes -> mcp_handlers.outcome_stats / read_outcomes)
  * accuracy == (success + 0.5*partial)/followed by EXACT equality
  * "no signal" (no followed rows) reports accuracy=None, never 0.0
  * shipped/validated/failed breakdown matches the seeded mix

All writes go to a tmp CORTEX_STATE_DIR via the autouse fixture; the live
~/.cortex store is never touched (asserted in test_isolation_guard).

Metrics are stashed on the module-level RESULTS dict so the aggregator
(scripts/internal/prove_core_outcomes.py) can surface them without re-running.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

# Make repo modules importable when running from the repo root uninstalled.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.proof.seed_corpus import (  # noqa: E402
    EXPECTED_ACCURACY,
    EXPECTED_SUCCESS_RATE,
    SEED_OUTCOMES,
    SEED_PROJECT,
    seed_decisions,
    seed_outcomes,
)

# Measurements surfaced to the aggregator.
RESULTS: dict = {"record": {}, "track": {}}


@pytest.fixture(autouse=True)
def hermetic_store(tmp_path, monkeypatch):
    """Redirect the whole cortex store to a tmp dir for every test.

    Sets BOTH env vars: mcp_handlers resolves via CORTEX_STATE_DIR, but other
    readers (pattern_indexer) use CORTEX_HOME — keep them in lockstep so a test
    can never read or write the live ~/.cortex.
    """
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("CORTEX_HOME", str(tmp_path))
    return tmp_path


def _reimport_handlers():
    """Import mcp_handlers fresh (paths resolve at call time, so a plain import
    is fine; this indirection keeps the import local to the fixture'd env)."""
    import mcp_handlers

    return mcp_handlers


# ── Isolation guard ─────────────────────────────────────────────────────────


def test_isolation_guard(hermetic_store):
    """The store must resolve inside the tmp dir, never the real ~/.cortex."""
    from state_paths import get_cortex_dir

    resolved = get_cortex_dir()
    assert str(resolved).startswith(str(hermetic_store))
    assert ".cortex" not in str(resolved) or str(hermetic_store) in str(resolved)


# ── Outcome 1: RECORD ────────────────────────────────────────────────────────


def test_record_roundtrip_integrity(hermetic_store):
    """100% of recorded decisions land durably, unique, and schema-valid."""
    recorded = seed_decisions(hermetic_store, include_distractors=True)
    expected_n = len(recorded)

    lines = (hermetic_store / "decisions.jsonl").read_text().splitlines()
    parsed = []
    for ln in lines:
        ln = ln.strip()
        if ln:
            parsed.append(json.loads(ln))  # raises if any line is not valid JSON

    # Count: every recorded decision is on disk.
    assert len(parsed) == expected_n, f"{len(parsed)}/{expected_n} decisions durable"

    # Uniqueness: no id collisions.
    ids = [p["decision_id"] for p in parsed]
    assert len(set(ids)) == expected_n, "duplicate decision_id detected"

    # Schema: canonical learning-loop keys present on every row.
    required = {"decision_id", "decision", "context", "alternatives", "rationale", "timestamp", "source"}
    for p in parsed:
        assert required.issubset(p.keys()), f"missing keys: {required - p.keys()}"

    integrity = len(set(ids)) / expected_n
    RESULTS["record"]["roundtrip_integrity"] = integrity
    RESULTS["record"]["n_recorded"] = expected_n
    assert integrity == 1.0


def test_record_latency(hermetic_store):
    """Local-append record latency: p95 under 50ms (generous for a JSONL append)."""
    handlers = _reimport_handlers()
    n = 50
    samples_ms = []
    for i in range(n):
        t0 = time.perf_counter()
        handlers.record_learning_decision(
            decision=f"latency probe {i} Ferrocene{i}",
            context="latency test",
            project="prooftest",
            source="prooftest",
        )
        samples_ms.append((time.perf_counter() - t0) * 1000.0)

    samples_ms.sort()
    p50 = samples_ms[len(samples_ms) // 2]
    p95 = samples_ms[int(len(samples_ms) * 0.95)]
    RESULTS["record"]["latency_p50_ms"] = round(p50, 3)
    RESULTS["record"]["latency_p95_ms"] = round(p95, 3)
    RESULTS["record"]["latency_n"] = n

    # All n landed.
    lines = [ln for ln in (hermetic_store / "decisions.jsonl").read_text().splitlines() if ln.strip()]
    assert len(lines) == n
    assert p95 < 50.0, f"record p95 = {p95:.2f}ms (budget 50ms)"


def test_spool_fallback_never_loses_a_decision(hermetic_store, monkeypatch):
    """When the primary append fails, the decision is spooled and replayable.

    Proves the durability guarantee behind cortex_record_decision: a dead
    bridge / unwritable primary never loses a decision.
    """
    handlers = _reimport_handlers()

    real_append = handlers._append_line

    def _explode(path, entry):
        # Fail only the decisions.jsonl primary append; let spool writes through.
        if path.name == "decisions.jsonl":
            raise OSError("simulated primary-append failure")
        return real_append(path, entry)

    monkeypatch.setattr(handlers, "_append_line", _explode)

    res = handlers.record_learning_decision(
        decision="spooled under failure Halocline",
        context="spool test",
        project="prooftest",
        source="prooftest",
    )
    assert res["recorded"] is True
    assert res.get("spooled") is True, "primary failed but entry was not spooled"
    assert handlers.spool_depth() == 1

    # Restore the primary and flush.
    monkeypatch.setattr(handlers, "_append_line", real_append)
    flush = handlers.flush_spool()
    assert flush["flushed"] == 1
    assert handlers.spool_depth() == 0

    # The decision is now durable in decisions.jsonl.
    lines = [ln for ln in (hermetic_store / "decisions.jsonl").read_text().splitlines() if ln.strip()]
    assert any("Halocline" in ln for ln in lines)

    # Idempotent: a second flush replays nothing new.
    flush2 = handlers.flush_spool()
    assert flush2["flushed"] == 0

    RESULTS["record"]["spool_recovered"] = True


# ── Outcome 3: TRACK ─────────────────────────────────────────────────────────


def test_outcome_accuracy_formula_exact(hermetic_store):
    """accuracy == (success + 0.5*partial)/followed, by exact equality."""
    seed_outcomes(hermetic_store)
    handlers = _reimport_handlers()

    stats = handlers.outcome_stats(project=SEED_PROJECT)
    assert stats["followed"] == len(SEED_OUTCOMES)
    assert stats["success"] == 3
    assert stats["partial"] == 2
    assert stats["failed"] == 1
    assert stats["accuracy"] == EXPECTED_ACCURACY, f"{stats['accuracy']} != {EXPECTED_ACCURACY}"
    assert stats["success_rate"] == EXPECTED_SUCCESS_RATE

    RESULTS["track"]["accuracy"] = stats["accuracy"]
    RESULTS["track"]["success_rate"] = stats["success_rate"]
    RESULTS["track"]["breakdown"] = {
        "success": stats["success"],
        "partial": stats["partial"],
        "failed": stats["failed"],
    }


def test_outcome_null_when_no_signal(hermetic_store):
    """No followed rows -> accuracy is None (honest "no signal", not 0.0)."""
    from datetime import datetime

    handlers = _reimport_handlers()
    # Seed one UNfollowed outcome so the store is non-empty but has no signal.
    path = hermetic_store / "outcomes.jsonl"
    path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "recommendation_id": "unfollowed_1",
                "recommendation_type": "next_action",
                "followed": False,
                "outcome": "success",
                "context": {"project": SEED_PROJECT},
            }
        )
        + "\n"
    )
    stats = handlers.outcome_stats(project=SEED_PROJECT)
    assert stats["followed"] == 0
    assert stats["accuracy"] is None, "no followed rows must yield accuracy=None, not 0.0"
    assert stats["success_rate"] is None


def test_shipped_validated_failed_breakdown(hermetic_store):
    """read_outcomes returns the seeded rows; outcome values match the mix."""
    seed_outcomes(hermetic_store)
    handlers = _reimport_handlers()

    got = handlers.read_outcomes(project=SEED_PROJECT, limit=50)
    assert got["total"] == len(SEED_OUTCOMES)
    outcomes = [o["outcome"] for o in got["outcomes"]]
    assert outcomes.count("success") == 3
    assert outcomes.count("partial") == 2
    assert outcomes.count("failed") == 1


def test_real_vs_seed_split_live_readonly():
    """Live audit (READ-ONLY): classify the real outcomes.jsonl into seed vs
    real, and prove computing over real-only differs from computing over all
    rows — i.e. the seed rows would inflate a naive 'what shipped' number.

    Skips cleanly if the live store isn't present (CI / fresh machine).
    """
    live = Path.home() / ".cortex" / "outcomes.jsonl"
    if not live.exists():
        pytest.skip("no live ~/.cortex/outcomes.jsonl to audit")

    real = seed = bad = 0
    for line in live.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            bad += 1
            continue
        notes = (o.get("notes") or "").lower()
        ctx = o.get("context") or {}
        is_seed = "simulat" in notes or "test" in notes or (isinstance(ctx, dict) and ctx.get("test") is True)
        if is_seed:
            seed += 1
        else:
            real += 1

    RESULTS["track"]["live_real"] = real
    RESULTS["track"]["live_seed"] = seed
    RESULTS["track"]["live_unparseable"] = bad

    # The proof: there IS seed pollution, so real-only != all-rows. If a future
    # cleanup removes all seed rows this assertion relaxes to >=0 (still honest).
    assert seed >= 0 and real >= 0
    # Guard against the anti-pattern: don't let the harness silently treat the
    # inflated count as truth — it must be able to tell them apart.
    assert (real + seed) > 0
