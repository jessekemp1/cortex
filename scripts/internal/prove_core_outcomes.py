#!/usr/bin/env python3
"""Prove Cortex's three core outcomes with verified, measurable data.

One command that produces a durable JSON artifact with a number + threshold +
pass/fail for each of the three outcomes cortex exists to deliver:

  1. RECORD  — cortex_record_decision durably persists a decision.
  2. RECALL  — cortex_intelligence surfaces a recorded decision for a query.
  3. TRACK   — cortex_outcomes reports what shipped / validated / failed.

Modes:
  --hermetic (default)  run the pytest proof suite on isolated tmp stores and
                        collect its metrics. Reproducible, CI-safe, never reads
                        the live store.
  --live                READ-ONLY audit of the live ~/.cortex/{decisions,
                        recall_events,outcomes}.jsonl — the "does it work in
                        production" number. Never writes the live store.
  --both                run hermetic then live.

  --strict              exit non-zero if any outcome's gate is not met.
  --out PATH            artifact path (default ~/.cortex/metrics/outcomes_proof.json)

The live audit is where the open-loop finding surfaces: live recall
decisions_resurfaced is currently 0 (recorded decisions are not being surfaced
in production), and outcomes.jsonl is ~37% simulated/test seed rows — both are
reported as numbers, not hidden.

This script writes ONLY to the metrics artifact path; it never mutates any
decisions/outcomes/recall store.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RECALL_THRESHOLD = 0.60
RECORD_INTEGRITY_THRESHOLD = 1.0

# Proof test files whose metrics we collect for the hermetic report.
PROOF_TESTS = [
    "tests/test_core_outcomes_proof.py",
    "tests/test_decision_recall_benchmark.py",
]


# ── Hermetic: run the proof suite and collect metrics ───────────────────────


def run_hermetic() -> dict:
    """Run the pytest proof suite and collect the RESULTS + benchmark metrics.

    We run pytest in-process for the record/track RESULTS dict (populated as a
    side effect of the tests) and read the recall benchmark's JSON artifact
    from the tmp store via a dedicated invocation. To keep it simple and
    robust, we import the test modules and drive their helpers directly on a
    fresh tmp store rather than parsing pytest output.
    """
    import os
    import tempfile

    import mcp_handlers
    from tests.proof.seed_corpus import (
        EXPECTED_ACCURACY,
        EXPECTED_SUCCESS_RATE,
        SEED_OUTCOMES,
        seed_decisions,
        seed_outcomes,
    )

    tmp = Path(tempfile.mkdtemp(prefix="cortex_proof_"))
    os.environ["CORTEX_STATE_DIR"] = str(tmp)
    os.environ["CORTEX_HOME"] = str(tmp)

    # RECORD: round-trip integrity.
    recorded = seed_decisions(tmp, include_distractors=True)
    lines = [ln for ln in (tmp / "decisions.jsonl").read_text().splitlines() if ln.strip()]
    ids = [json.loads(ln)["decision_id"] for ln in lines]
    integrity = len(set(ids)) / len(recorded) if recorded else 0.0
    record_block = {
        "metric": "round_trip_integrity",
        "value": round(integrity, 4),
        "threshold": RECORD_INTEGRITY_THRESHOLD,
        "n_recorded": len(recorded),
        "n_durable_unique": len(set(ids)),
        "pass": integrity >= RECORD_INTEGRITY_THRESHOLD,
    }

    # TRACK: accuracy exact.
    seed_outcomes(tmp)
    stats = mcp_handlers.outcome_stats(project="prooftest")
    track_pass = (
        stats["accuracy"] == EXPECTED_ACCURACY
        and stats["success_rate"] == EXPECTED_SUCCESS_RATE
        and stats["followed"] == len(SEED_OUTCOMES)
    )
    track_block = {
        "metric": "accuracy_exact",
        "value": stats["accuracy"],
        "expected": EXPECTED_ACCURACY,
        "success_rate": stats["success_rate"],
        "breakdown": {"success": stats["success"], "partial": stats["partial"], "failed": stats["failed"]},
        "pass": bool(track_pass),
    }

    # RECALL: run the benchmark suite (needs the fixture/monkeypatch machinery),
    # so shell out to pytest for just the recall file and read its artifact.
    recall_block = _run_recall_via_pytest()

    return {"record": record_block, "recall": recall_block, "track": track_block}


def _run_recall_via_pytest() -> dict:
    """Run the recall benchmark through pytest and recover its metric.

    The benchmark writes decision_recall_benchmark.json under its tmp store,
    which we can't easily reach from here, so we re-run its core in a subprocess
    that prints the recall number as the last stdout line.
    """
    driver = (
        "import os, tempfile, json, sys;"
        "sys.path.insert(0, os.getcwd());"
        "tmp=tempfile.mkdtemp(prefix='cortex_recall_');"
        "os.environ['CORTEX_STATE_DIR']=tmp; os.environ['CORTEX_HOME']=tmp;"
        "import intelligence.memory.hybrid_retriever as hr;"
        "hr._DECISIONS_PATH=__import__('pathlib').Path(tmp)/'decisions.jsonl';"
        "hr._OUTCOMES_PATH=__import__('pathlib').Path(tmp)/'outcomes.jsonl';"
        "hr._DIGESTS_PATH=__import__('pathlib').Path(tmp)/'conversation_digests.jsonl';"
        "hr._decision_cache=None; hr._decision_cache_mtime=0.0;"
        "from tests.test_decision_recall_benchmark import _build_retriever, _run_benchmark;"
        "r=_build_retriever(__import__('pathlib').Path(tmp));"
        "recall,mrr,results=_run_benchmark(r,10);"
        "print('RECALL_JSON'+json.dumps({'recall_at_10':recall,'mrr':mrr,"
        "'misses':[x['token'] for x in results if not x['hit']],'n_queries':len(results)}))"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", driver],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        line = next(
            (ln for ln in proc.stdout.splitlines() if ln.startswith("RECALL_JSON")),
            None,
        )
        if line is None:
            return {"metric": "recall_at_10", "value": None, "threshold": RECALL_THRESHOLD,
                    "pass": False, "error": (proc.stderr or proc.stdout)[-500:]}
        data = json.loads(line[len("RECALL_JSON"):])
        return {
            "metric": "recall_at_10",
            "value": round(data["recall_at_10"], 4),
            "threshold": RECALL_THRESHOLD,
            "mrr": round(data["mrr"], 4),
            "misses": data["misses"],
            "n_queries": data["n_queries"],
            "pass": data["recall_at_10"] >= RECALL_THRESHOLD,
        }
    except Exception as e:  # noqa: BLE001
        return {"metric": "recall_at_10", "value": None, "threshold": RECALL_THRESHOLD,
                "pass": False, "error": str(e)}


# ── Live: read-only audit of the production store ───────────────────────────


def run_live() -> dict:
    """READ-ONLY audit of the live ~/.cortex store. Never writes."""
    from state_paths import get_cortex_dir

    # Resolve WITHOUT any test env override — the real store.
    import os

    saved = {k: os.environ.pop(k, None) for k in ("CORTEX_STATE_DIR", "CORTEX_HOME")}
    try:
        cortex_dir = get_cortex_dir()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    # RECORD (live): parseable-line ratio in decisions.jsonl.
    dpath = cortex_dir / "decisions.jsonl"
    d_total = d_ok = 0
    if dpath.exists():
        for ln in dpath.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            d_total += 1
            try:
                json.loads(ln)
                d_ok += 1
            except (json.JSONDecodeError, ValueError):
                pass
    record_live = {
        "decisions_total": d_total,
        "decisions_parseable": d_ok,
        "parseable_ratio": round(d_ok / d_total, 4) if d_total else None,
    }

    # RECALL (live): decisions_resurfaced from recall_events.jsonl.
    recall_live: dict = {"total_recalls": 0, "decisions_resurfaced": 0, "predictions_surfaced": 0}
    try:
        from intelligence.recall_events import recall_summary

        # recall_summary reads via get_cortex_dir; ensure live resolution.
        saved = {k: os.environ.pop(k, None) for k in ("CORTEX_STATE_DIR", "CORTEX_HOME")}
        try:
            summ = recall_summary()
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
        recall_live = {
            "total_recalls": summ.get("total_recalls", 0),
            "decisions_resurfaced": summ.get("decisions_resurfaced", 0),
            "predictions_surfaced": summ.get("predictions_surfaced", 0),
        }
    except Exception as e:  # noqa: BLE001
        recall_live["error"] = str(e)
    # RED flag: the open-loop finding — recorded decisions never surfaced live.
    recall_live["open_loop_flag"] = recall_live.get("decisions_resurfaced", 0) == 0

    # TRACK (live): real vs seed split + real-only breakdown.
    opath = cortex_dir / "outcomes.jsonl"
    real = seed = bad = 0
    r_success = r_partial = r_failed = r_followed = 0
    if opath.exists():
        for ln in opath.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except (json.JSONDecodeError, ValueError):
                bad += 1
                continue
            notes = (o.get("notes") or "").lower()
            ctx = o.get("context") or {}
            is_seed = "simulat" in notes or "test" in notes or (isinstance(ctx, dict) and ctx.get("test") is True)
            if is_seed:
                seed += 1
                continue
            real += 1
            if o.get("followed"):
                r_followed += 1
                oc = o.get("outcome")
                if oc == "success":
                    r_success += 1
                elif oc == "partial":
                    r_partial += 1
                else:
                    r_failed += 1
    track_live = {
        "outcomes_total": real + seed + bad,
        "real": real,
        "seed": seed,
        "unparseable": bad,
        "seed_ratio": round(seed / (real + seed), 4) if (real + seed) else None,
        "real_only_breakdown": {"success": r_success, "partial": r_partial, "failed": r_failed},
        "real_only_accuracy": round((r_success + 0.5 * r_partial) / r_followed, 4) if r_followed else None,
    }

    return {"record": record_live, "recall": recall_live, "track": track_live}


# ── Report ──────────────────────────────────────────────────────────────────


def _print_report(artifact: dict) -> None:
    print("\n=== Cortex Core-Outcomes Proof ===")
    print(f"generated_at: {artifact['generated_at']}  mode: {artifact['mode']}")
    herm = artifact.get("hermetic")
    if herm:
        print("\n-- HERMETIC (isolated tmp store) --")
        r = herm["record"]
        print(f"  RECORD  round-trip integrity : {r['value']:.0%}  (>= {r['threshold']:.0%})  {'PASS' if r['pass'] else 'FAIL'}")
        rc = herm["recall"]
        v = rc["value"]
        vtxt = f"{v:.0%}" if isinstance(v, (int, float)) else str(v)
        print(f"  RECALL  decisions Recall@10  : {vtxt}  (>= {rc['threshold']:.0%})  {'PASS' if rc['pass'] else 'FAIL'}")
        t = herm["track"]
        print(f"  TRACK   accuracy (exact)      : {t['value']}  (== {t['expected']})  {'PASS' if t['pass'] else 'FAIL'}")
    live = artifact.get("live")
    if live:
        print("\n-- LIVE (read-only audit of ~/.cortex) --")
        r = live["record"]
        print(f"  RECORD  decisions parseable   : {r['decisions_parseable']}/{r['decisions_total']}  ({r['parseable_ratio']})")
        rc = live["recall"]
        flag = "  <== OPEN LOOP: recorded decisions not surfaced in production" if rc.get("open_loop_flag") else ""
        print(f"  RECALL  decisions_resurfaced  : {rc['decisions_resurfaced']} over {rc['total_recalls']} recalls{flag}")
        t = live["track"]
        print(f"  TRACK   outcomes real/seed    : {t['real']} real / {t['seed']} seed ({t['seed_ratio']} seed) | real-only accuracy {t['real_only_accuracy']}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--hermetic", action="store_true", help="hermetic proof only (default)")
    mode.add_argument("--live", action="store_true", help="live read-only audit only")
    mode.add_argument("--both", action="store_true", help="hermetic then live")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if any hermetic gate fails")
    ap.add_argument("--out", default=None, help="artifact path (default ~/.cortex/metrics/outcomes_proof.json)")
    args = ap.parse_args()

    do_hermetic = args.hermetic or args.both or not (args.live or args.both)
    do_live = args.live or args.both

    artifact: dict = {
        "generated_at": datetime.now().isoformat(),
        "mode": "both" if (do_hermetic and do_live) else ("live" if do_live else "hermetic"),
    }
    if do_hermetic:
        artifact["hermetic"] = run_hermetic()
    if do_live:
        artifact["live"] = run_live()

    # Resolve the artifact path against the REAL store (ignore any test env).
    if args.out:
        out_path = Path(args.out).expanduser()
    else:
        import os

        saved = {k: os.environ.pop(k, None) for k in ("CORTEX_STATE_DIR", "CORTEX_HOME")}
        try:
            from state_paths import get_cortex_dir

            out_path = get_cortex_dir() / "metrics" / "outcomes_proof.json"
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2))

    _print_report(artifact)
    print(f"artifact: {out_path}")

    if args.strict and do_hermetic:
        gates = [artifact["hermetic"][k]["pass"] for k in ("record", "recall", "track")]
        if not all(gates):
            print("STRICT: one or more hermetic gates FAILED", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
