import os
#!/usr/bin/env python3
"""Nightly Portfolio Health Scan"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

DEV_ROOT = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
SCAN_DIR = Path.home() / ".cortex" / "scans"
SCAN_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd, desc):
    print(f"\n{desc}")
    try:
        result = subprocess.run(
            ["/bin/bash", "-c", cmd],
            shell=False, capture_output=True, text=True, timeout=180,
            cwd=str(DEV_ROOT),
        )
        return {
            "description": desc,
            "success": result.returncode == 0,
            "output": (result.stdout or result.stderr or "")[:2000],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "description": desc,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def main():
    scans = {
        "scan_date": datetime.now().isoformat(),
        "scans": [
            run("./cortex health 2>&1", "Health Check"),
            run("./cortex status 2>&1", "Status"),
            run("./cortex git 2>&1", "Git"),
            run("./cortex batch status 2>&1", "Batch"),
        ],
    }

    success = sum(1 for s in scans["scans"] if s.get("success"))
    scans["summary"] = {"successful": success, "total": len(scans["scans"])}

    output = SCAN_DIR / f"nightly_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output, "w") as f:
        json.dump(scans, f, indent=2)
    with open(SCAN_DIR / "latest_scan.json", "w") as f:
        json.dump(scans, f, indent=2)

    print(f"\n✓ {success}/{len(scans['scans'])} successful -> {output}")
    return 0


if __name__ == "__main__":
    exit(main())
