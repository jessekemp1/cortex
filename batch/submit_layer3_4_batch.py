#!/usr/bin/env python3
"""
Submit Layers 3-4 implementation as overnight batch job.

This script:
1. Creates batch requests for all Layer 3-4 tasks
2. Submits to Anthropic Batch API
3. Saves batch ID for monitoring
4. Provides status check commands
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.batch_api_client import BatchAPIClient, BatchRequest
from batch.layer3_4_batch_spec import create_all_batch_requests


def submit_batch():
    """Submit Layers 3-4 implementation batch."""

    print("=" * 60)
    print("CORTEX INTELLIGENCE STACK - LAYERS 3-4 BATCH SUBMISSION")
    print("=" * 60)
    print()

    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not set")
        print()
        print("Set your API key:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print()
        sys.exit(1)

    print("✅ API key found")
    print()

    # Create batch requests
    print("📝 Creating batch requests...")
    requests = create_all_batch_requests()
    print(f"   Created {len(requests)} requests")
    print()

    # Show breakdown
    layer3_requests = [r for r in requests if r.custom_id.startswith("layer3")]
    layer4_requests = [r for r in requests if r.custom_id.startswith("layer4")]

    print("📊 Batch breakdown:")
    print(f"   Layer 3 (Warning System): {len(layer3_requests)} tasks")
    for req in layer3_requests:
        print(f"     - {req.custom_id}")
    print()
    print(f"   Layer 4 (Smart Recommendations): {len(layer4_requests)} tasks")
    for req in layer4_requests:
        print(f"     - {req.custom_id}")
    print()

    # Estimate cost
    # Each task uses Opus with ~10k input tokens + 16k max output
    # Input: ~10k tokens × $15/M = $0.15 per request
    # Output: ~16k tokens × $75/M = $1.20 per request (worst case)
    # Total per request: ~$1.35
    total_requests = len(requests)
    estimated_cost = total_requests * 1.35

    print("💰 Estimated cost:")
    print(f"   {total_requests} requests × ~$1.35 = ~${estimated_cost:.2f}")
    print(f"   (Assumes Opus with max tokens; actual cost likely lower)")
    print()

    # Confirm submission
    print("⏱️  Expected completion: 24 hours (batch API SLA)")
    print()
    response = input("Submit batch? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("❌ Batch submission cancelled")
        sys.exit(0)

    # Submit batch
    print()
    print("🚀 Submitting batch to Anthropic API...")
    try:
        client = BatchAPIClient(api_key=api_key)
        batch_id = client.submit_batch(
            requests=requests,
            description="Cortex Intelligence Stack - Layers 3-4 Implementation",
        )

        print(f"✅ Batch submitted successfully!")
        print(f"   Batch ID: {batch_id}")
        print()

        # Save batch info
        batch_info = {
            "batch_id": batch_id,
            "submitted_at": datetime.now().isoformat(),
            "total_requests": len(requests),
            "layer3_tasks": len(layer3_requests),
            "layer4_tasks": len(layer4_requests),
            "description": "Layers 3-4 implementation",
            "status": "submitted",
        }

        info_path = Path.home() / ".cortex" / "batches" / f"{batch_id}.json"
        info_path.parent.mkdir(parents=True, exist_ok=True)
        info_path.write_text(json.dumps(batch_info, indent=2))

        print("📁 Batch info saved to:")
        print(f"   {info_path}")
        print()

        # Show monitoring commands
        print("=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print()
        print("Monitor batch status:")
        print(f"  python batch/check_batch_status.py {batch_id}")
        print()
        print("Or use the orchestrator (recommended for overnight):")
        print(f"  python batch/monitor_batch_overnight.py {batch_id}")
        print()
        print("The orchestrator will:")
        print("  - Check status every 30 minutes")
        print("  - Download results when complete")
        print("  - Apply code changes automatically")
        print("  - Run tests to verify")
        print("  - Send notification when done")
        print()

    except Exception as e:
        print(f"❌ Error submitting batch: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    submit_batch()
