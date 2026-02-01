#!/usr/bin/env python3
"""Test anomaly detector + alert manager integration."""

import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cortex.orchestration.database import OrchestrationDatabase
from cortex.orchestration.anomaly_detector import (
    OrchestrationAnomalyManager,
    OrchestrationAnomaly,
    AnomalyType,
    AnomalySeverity,
)

def main():
    """Test the integration."""
    print("🧪 Testing Anomaly Detector + Alert Manager Integration\n")

    # Initialize
    print("1. Initializing anomaly manager with alerts enabled...")
    db = OrchestrationDatabase()
    manager = OrchestrationAnomalyManager(db, enable_alerts=True)
    print("   ✓ Manager initialized\n")

    # Run detection
    print("2. Running anomaly detection...")
    context = {
        "active_projects": 26,  # Will trigger context switching anomaly
        "goals": [],
    }
    anomalies = manager.detect_all(context)
    print(f"   ✓ Detected {len(anomalies)} anomalies\n")

    # Show results
    print("3. Anomaly Results:")
    for i, anomaly in enumerate(anomalies, 1):
        print(f"\n   {i}. [{anomaly.severity.value}] {anomaly.title}")
        print(f"      Type: {anomaly.anomaly_type.value}")
        print(f"      Description: {anomaly.description[:100]}...")
        print(f"      Remediation: {anomaly.remediation[:100]}...")

        if anomaly.severity == AnomalySeverity.CRITICAL:
            print(f"      🚨 ALERT SENT (check desktop notifications!)")

    print("\n4. Checking alert logs...")
    from pathlib import Path
    alerts_file = Path.home() / ".cortex" / "alerts.jsonl"

    if alerts_file.exists():
        import json
        with open(alerts_file, "r") as f:
            lines = f.readlines()
            if lines:
                latest = json.loads(lines[-1])
                print(f"   ✓ Latest alert: {latest['title']}")
                print(f"     Severity: {latest['severity']}")
                print(f"     Source: {latest['source']}")
            else:
                print("   ⚠ No alerts logged yet")
    else:
        print("   ⚠ Alert log file not found")

    print("\n✅ Integration test complete!")
    print("   Check your desktop for notifications (if any CRITICAL anomalies)")

if __name__ == "__main__":
    main()
