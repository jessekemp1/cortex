#!/usr/bin/env python3
"""
Batch API Monitoring Dashboard

Provides visibility into batch processing performance and cost savings.

Usage:
    python3 batch_monitoring.py
    python3 batch_monitoring.py --verbose
    python3 batch_monitoring.py --check-batches
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from cortex.batch import BatchConfig

    BATCH_AVAILABLE = True
except ImportError:
    BATCH_AVAILABLE = False


def show_batch_status(verbose=False):
    """Display current batch configuration"""
    print("\n" + "=" * 70)
    print("BATCH API MONITORING DASHBOARD")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not BATCH_AVAILABLE:
        print("\n❌ ERROR: Batch module not available")
        print("   Make sure cortex.batch is properly installed")
        return

    # Check configuration
    print("\nConfiguration:")
    print(f"  Research:        {BatchConfig.is_batch_enabled('research')}")
    print(f"  Recommendations: {BatchConfig.is_batch_enabled('recommendations')}")
    print(f"  Learning:        {BatchConfig.is_batch_enabled('learning')}")

    # Check environment variables
    if verbose:
        print("\nEnvironment Variables:")
        print(
            f"  CORTEX_BATCH_RESEARCH_ENABLED:         {os.getenv('CORTEX_BATCH_RESEARCH_ENABLED', 'not set')}"
        )
        print(
            f"  CORTEX_BATCH_RECOMMENDATIONS_ENABLED:  {os.getenv('CORTEX_BATCH_RECOMMENDATIONS_ENABLED', 'not set')}"
        )
        print(
            f"  CORTEX_BATCH_LEARNING_ENABLED:         {os.getenv('CORTEX_BATCH_LEARNING_ENABLED', 'not set')}"
        )
        print(
            f"  ANTHROPIC_API_KEY:                     {'set' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}"
        )

    # Check batch directory
    batch_dir = Path.home() / ".cortex" / "batches"
    if batch_dir.exists():
        batches = list(batch_dir.glob("*_metadata.json"))
        print("\nBatch Submissions:")
        print(f"  Total batches: {len(batches)}")
        if batches:
            recent = sorted(batches, key=lambda p: p.stat().st_mtime, reverse=True)[:5]
            print("  Recent batches:")
            for b in recent:
                # Get file modified time
                mtime = datetime.fromtimestamp(b.stat().st_mtime)
                # Try to read metadata
                try:
                    with open(b) as f:
                        metadata = json.load(f)
                        status = metadata.get("status", "unknown")
                        batch_id = metadata.get("batch_id", "unknown")
                        print(f"    - {b.stem[:30]}... ({mtime.strftime('%Y-%m-%d %H:%M')})")
                        if verbose:
                            print(f"      Status: {status}, ID: {batch_id}")
                except Exception:
                    print(f"    - {b.stem} (error reading metadata)")
    else:
        print("\nBatch Directory:")
        print(f"  ⚠️  Batch directory does not exist: {batch_dir}")
        print(f"  Create with: mkdir -p {batch_dir}")

    # Check logs directory
    logs_dir = Path.home() / ".cortex" / "logs"
    if logs_dir.exists():
        log_files = list(logs_dir.glob("batch*.log"))
        print("\nBatch Logs:")
        print(f"  Total log files: {len(log_files)}")
        if log_files and verbose:
            for log in log_files[:3]:
                print(f"    - {log.name}")
    else:
        print("\nBatch Logs:")
        print(f"  ⚠️  Logs directory does not exist: {logs_dir}")
        print(f"  Create with: mkdir -p {logs_dir}")

    # System status summary
    print("\nSystem Status:")
    enabled_count = sum(
        [
            BatchConfig.is_batch_enabled("research"),
            BatchConfig.is_batch_enabled("recommendations"),
            BatchConfig.is_batch_enabled("learning"),
        ]
    )

    if enabled_count == 3:
        print("  ✅ All phases enabled")
        print("  💰 Expected annual savings: $900-1,400+")
    elif enabled_count > 0:
        print(f"  ⚠️  Partial deployment ({enabled_count}/3 phases enabled)")
    else:
        print("  ⏸️  All phases disabled (sequential mode)")
        print("  💡 Enable with environment variables:")
        print("     export CORTEX_BATCH_RESEARCH_ENABLED=true")
        print("     export CORTEX_BATCH_RECOMMENDATIONS_ENABLED=true")
        print("     export CORTEX_BATCH_LEARNING_ENABLED=true")

    print("\n" + "=" * 70 + "\n")


def check_batch_details():
    """Display detailed batch information"""
    batch_dir = Path.home() / ".cortex" / "batches"
    if not batch_dir.exists():
        print(f"No batch directory found at {batch_dir}")
        return

    batches = list(batch_dir.glob("*_metadata.json"))
    if not batches:
        print("No batches found")
        return

    print("\n" + "=" * 70)
    print("BATCH DETAILS")
    print("=" * 70)

    for batch_file in sorted(batches, key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        try:
            with open(batch_file) as f:
                metadata = json.load(f)

            print(f"\nBatch: {batch_file.stem}")
            print(f"  Created:  {metadata.get('created_at', 'unknown')}")
            print(f"  Status:   {metadata.get('status', 'unknown')}")
            print(f"  Batch ID: {metadata.get('batch_id', 'unknown')}")
            print(f"  Requests: {len(metadata.get('requests', []))}")

            if "completed_at" in metadata:
                print(f"  Completed: {metadata['completed_at']}")

            if "error" in metadata:
                print(f"  Error: {metadata['error']}")

        except Exception as e:
            print(f"\nBatch: {batch_file.stem}")
            print(f"  Error reading metadata: {e}")

    print("\n" + "=" * 70 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Batch API Monitoring Dashboard")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument(
        "--check-batches",
        "-b",
        action="store_true",
        help="Show detailed batch information",
    )

    args = parser.parse_args()

    if args.check_batches:
        check_batch_details()
    else:
        show_batch_status(verbose=args.verbose)


if __name__ == "__main__":
    main()
