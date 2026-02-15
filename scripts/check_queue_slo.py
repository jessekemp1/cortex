#!/usr/bin/env python3
"""Print queue SLO status and exit non-zero on critical."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.bandwidth.queue_slo import check_queue_slo


def main() -> int:
    status = check_queue_slo()
    print(json.dumps(status, indent=2))
    return 2 if status.get("status") == "critical" else 0


if __name__ == "__main__":
    raise SystemExit(main())
