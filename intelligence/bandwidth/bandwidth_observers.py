"""Real-data bandwidth experiments (non-simulated)."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from intelligence.bandwidth.contracts import ContractMetricsStore
from intelligence.bandwidth.handoff_capture import HandoffStorage
from intelligence.bandwidth.predictions import PredictionTracker


def _ensure(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)


def run_context_compression(results_dir: str) -> Dict[str, Any]:
    out = Path(results_dir)
    _ensure(out)
    handoffs = HandoffStorage().load_recent(limit=200)
    sizes: List[int] = []
    for h in handoffs:
        try:
            sizes.append(len(json.dumps(h.to_dict())))
        except Exception:
            continue

    avg = (sum(sizes) / len(sizes)) if sizes else 0.0
    p90 = sorted(sizes)[int(0.9 * (len(sizes) - 1))] if sizes else 0
    result = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "context_compression",
        "method": "observed_handoff_payloads",
        "sample_size": len(sizes),
        "metrics": {"avg_handoff_payload_bytes": round(avg, 1), "p90_handoff_payload_bytes": p90},
        "summary": {
            "best_format": "hybrid_observed" if sizes else "insufficient_data",
            "avg_token_savings": None,
        },
    }
    (out / "context_compression_results.json").write_text(json.dumps(result, indent=2))
    return result


def run_trust_calibration(results_dir: str) -> Dict[str, Any]:
    out = Path(results_dir)
    _ensure(out)
    cal = PredictionTracker().get_calibration()
    domains = {k: v.to_dict() for k, v in cal.items()}
    populated = {k: v for k, v in domains.items() if v.get("total", 0) > 0}
    result = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "trust_calibration",
        "method": "observed_prediction_tracker",
        "domains": domains,
        "summary": {
            "highest_trust": (
                max(populated.items(), key=lambda x: x[1]["calibrated_confidence"])[0]
                if populated
                else None
            ),
            "lowest_trust": (
                min(populated.items(), key=lambda x: x[1]["calibrated_confidence"])[0]
                if populated
                else None
            ),
            "populated_domains": len(populated),
        },
    }
    (out / "trust_calibration_results.json").write_text(json.dumps(result, indent=2))
    return result


def run_handoff_protocol(results_dir: str) -> Dict[str, Any]:
    out = Path(results_dir)
    _ensure(out)
    handoffs = HandoffStorage().load_recent(limit=200)
    completeness = []
    for h in handoffs:
        d = h.to_dict()
        checks = [
            bool(d.get("project")),
            bool(d.get("active_task")),
            bool(d.get("workstream")),
            bool(d.get("next_action")),
            bool(d.get("files_modified")),
        ]
        completeness.append(sum(1 for c in checks if c) / len(checks))

    avg = (sum(completeness) / len(completeness)) if completeness else 0.0
    result = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "handoff_protocol",
        "method": "observed_schema_completeness",
        "tests": [{"scenario": "observed_handoffs", "retention_rate": round(avg, 3)}],
        "summary": {"avg_retention_rate": round(avg, 3), "baseline_improvement": None},
    }
    (out / "handoff_protocol_results.json").write_text(json.dumps(result, indent=2))
    return result


def run_idea_augmentation(results_dir: str) -> Dict[str, Any]:
    out = Path(results_dir)
    _ensure(out)
    agg = ContractMetricsStore().aggregate(days=30)
    result = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "idea_augmentation",
        "method": "observed_contract_novelty",
        "protocols": [
            {
                "name": "observed",
                "novelty_score": agg.get("novelty_score", 0),
                "sessions": agg.get("sessions", 0),
            }
        ],
        "summary": {
            "best_protocol": "observed",
            "novelty_improvement": None,
            "implementation_rate": None,
        },
    }
    (out / "idea_augmentation_results.json").write_text(json.dumps(result, indent=2))
    return result


def run_synthesis(results_dir: str) -> Dict[str, Any]:
    out = Path(results_dir)
    _ensure(out)
    files = [
        "context_compression_results.json",
        "trust_calibration_results.json",
        "handoff_protocol_results.json",
        "idea_augmentation_results.json",
    ]
    loaded = {}
    for f in files:
        p = out / f
        if p.exists():
            loaded[f] = json.loads(p.read_text())

    findings = []
    if "trust_calibration_results.json" in loaded:
        s = loaded["trust_calibration_results.json"]["summary"]
        if s.get("highest_trust"):
            findings.append(f"Highest trust domain: {s['highest_trust']}")
        if s.get("lowest_trust"):
            findings.append(f"Needs calibration work: {s['lowest_trust']}")
    if "handoff_protocol_results.json" in loaded:
        r = loaded["handoff_protocol_results.json"]["summary"].get("avg_retention_rate")
        findings.append(f"Handoff completeness retention: {round(r * 100, 1)}%")
    if "idea_augmentation_results.json" in loaded:
        nov = loaded["idea_augmentation_results.json"]["protocols"][0].get("novelty_score", 0)
        findings.append(f"Observed novelty score: {nov}/10")

    report = {
        "timestamp": datetime.now().isoformat(),
        "experiments_completed": len(loaded),
        "key_findings": findings,
        "recommendations": [
            "Increase contract session coverage for stronger confidence intervals",
            "Prioritize outcome logging in low-trust domains",
            "Enforce handoff next_action completeness",
        ],
        "metrics": {"observational_mode": True, "sufficient_data": len(loaded) >= 2},
    }
    (out / "synthesis_report.json").write_text(json.dumps(report, indent=2))
    return report
