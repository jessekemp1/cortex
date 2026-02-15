"""Baseline report generation with frozen windows and confidence intervals."""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from intelligence.bandwidth.contracts import ContractMetricsStore
from intelligence.bandwidth.meter import BandwidthMeter


def _mean_ci(values: List[float]) -> Tuple[float, Optional[Tuple[float, float]]]:
    if not values:
        return 0.0, None
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, None
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    se = math.sqrt(var) / math.sqrt(n)
    margin = 1.96 * se
    return mean, (mean - margin, mean + margin)


def generate_baseline_report(
    output_dir: Path,
    project: Optional[str] = None,
    days: int = 14,
    storage_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    end = datetime.now()
    start = end - timedelta(days=days)

    meter = BandwidthMeter(storage_dir=storage_dir)
    contracts = ContractMetricsStore(storage_dir=storage_dir)

    bandwidth = meter.load_metrics(days=days, project=project)
    contract_rows = contracts.load_metrics(days=days, project=project)

    signal_mean, signal_ci = _mean_ci([r.signal_ratio for r in bandwidth])
    corr_mean, corr_ci = _mean_ci([r.correction_rate for r in bandwidth])
    ttp_mean, ttp_ci = _mean_ci([r.time_to_productive_seconds for r in bandwidth])
    over_mean, over_ci = _mean_ci([r.override_rate for r in contract_rows])
    auto_mean, auto_ci = _mean_ci([r.autonomy_level for r in contract_rows])
    nov_mean, nov_ci = _mean_ci([r.novelty_score for r in contract_rows])

    report = {
        "generated_at": datetime.now().isoformat(),
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
            "frozen": True,
            "project": project,
        },
        "sample_sizes": {
            "bandwidth_sessions": len(bandwidth),
            "contract_sessions": len(contract_rows),
        },
        "metrics": {
            "signal_ratio": {"mean": round(signal_mean, 4), "ci95": signal_ci},
            "correction_rate": {"mean": round(corr_mean, 4), "ci95": corr_ci},
            "time_to_productive_seconds": {"mean": round(ttp_mean, 2), "ci95": ttp_ci},
            "override_rate": {"mean": round(over_mean, 4), "ci95": over_ci},
            "autonomy_level": {"mean": round(auto_mean, 4), "ci95": auto_ci},
            "novelty_score": {"mean": round(nov_mean, 3), "ci95": nov_ci},
        },
    }

    (output_dir / "baseline_report.json").write_text(json.dumps(report, indent=2, default=str))
    lines = [
        "# Bandwidth Baseline Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Window: {start.date()} -> {end.date()} ({days}d, frozen)",
        "",
        "## Sample Sizes",
        f"- Bandwidth sessions: {len(bandwidth)}",
        f"- Contract sessions: {len(contract_rows)}",
        "",
        "## Metrics (mean, 95% CI)",
    ]
    for k, v in report["metrics"].items():
        lines.append(f"- {k}: {v['mean']} (ci95={v['ci95']})")
    (output_dir / "baseline_report.md").write_text("\n".join(lines) + "\n")

    return report
