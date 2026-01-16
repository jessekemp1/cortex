#!/usr/bin/env python3
"""
Quick batch status checker.

Usage:
    python batch/check_batch_status.py <batch_id>
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.batch_api_client import BatchAPIClient


def check_status(batch_id: str):
    """Check batch status and display summary."""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = BatchAPIClient(api_key=api_key)

    print("=" * 60)
    print(f"BATCH STATUS: {batch_id}")
    print("=" * 60)
    print()

    try:
        status = client.get_batch_status(batch_id)

        print(f"Status: {status['status']}")
        print(f"Created: {status.get('created_at', 'Unknown')}")
        print()

        request_counts = status.get("request_counts", {})
        total = sum(request_counts.values())

        print("Request Counts:")
        print(f"  Total: {total}")
        print(f"  Processing: {request_counts.get('processing', 0)}")
        print(f"  Succeeded: {request_counts.get('succeeded', 0)}")
        print(f"  Errored: {request_counts.get('errored', 0)}")
        print(f"  Expired: {request_counts.get('expired', 0)}")
        print(f"  Canceled: {request_counts.get('canceled', 0)}")
        print()

        # Progress bar
        if total > 0:
            succeeded = request_counts.get("succeeded", 0)
            progress = succeeded / total * 100
            bar_length = 40
            filled = int(bar_length * progress / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"Progress: [{bar}] {progress:.1f}%")
            print()

        # Estimate completion time
        if status["status"] == "in_progress":
            print("⏳ Batch is still processing...")
            print("   Expected completion: 24 hours from submission (API SLA)")
            print()
            print("Monitor overnight with:")
            print(f"  python batch/monitor_batch_overnight.py {batch_id}")
        elif status["status"] in ["ended", "completed"]:
            print("✅ Batch complete! Download results with:")
            print(f"  python batch/monitor_batch_overnight.py {batch_id}")
        elif status["status"] in ["failed", "expired", "canceled"]:
            print(f"❌ Batch {status['status']}")

        print()

    except Exception as e:
        print(f"❌ Error checking status: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch/check_batch_status.py <batch_id>")
        sys.exit(1)

    check_status(sys.argv[1])
