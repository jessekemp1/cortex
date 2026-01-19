# Runtime Health Endpoint Documentation

**File**: `runtime/api.py` (lines 44-118)
**Endpoint**: `GET /api/v1/runtime/health`
**Status**: Enhanced with HealthMonitor integration

---

## Overview

The health endpoint provides comprehensive system health information, integrating with the Cortex Supervisor's HealthMonitor to detect issues and provide auto-healing status.

---

## Endpoint Details

### URL
```
GET http://localhost:8000/api/v1/runtime/health
```

### Response Format

#### Healthy State (No Issues)
```json
{
  "status": "healthy",
  "service": "cortex-runtime",
  "timestamp": "2026-01-18T15:30:00",
  "health_monitor": {
    "enabled": true,
    "issues_detected": 0,
    "issues": []
  },
  "queue": {
    "pending": 0,
    "active_batches": 0,
    "batches": []
  }
}
```

#### Healthy with Warnings
```json
{
  "status": "healthy_with_warnings",
  "service": "cortex-runtime",
  "timestamp": "2026-01-18T15:30:00",
  "warnings": 2,
  "health_monitor": {
    "enabled": true,
    "issues_detected": 2,
    "issues": [
      {
        "type": "disk_space",
        "target": "12abc456",
        "severity": "medium",
        "description": "Disk usage above 80%",
        "auto_healable": false
      },
      {
        "type": "stale_task",
        "target": "78def012",
        "severity": "low",
        "description": "Task running for >2 hours",
        "auto_healable": true
      }
    ]
  },
  "queue": {
    "pending": 3,
    "active_batches": 1,
    "batches": [...]
  }
}
```

#### Degraded State (Critical Issues)
```json
{
  "status": "degraded",
  "service": "cortex-runtime",
  "timestamp": "2026-01-18T15:30:00",
  "critical_issues": 1,
  "health_monitor": {
    "enabled": true,
    "issues_detected": 3,
    "issues": [
      {
        "type": "process_failure",
        "target": "batch_12",
        "severity": "critical",
        "description": "Batch processor crashed",
        "auto_healable": true
      },
      ...
    ]
  }
}
```

#### Fallback (HealthMonitor Not Available)
```json
{
  "status": "healthy",
  "service": "cortex-runtime",
  "timestamp": "2026-01-18T15:30:00",
  "health_monitor": {
    "enabled": false,
    "reason": "supervisor module not available"
  }
}
```

---

## Status Levels

### `healthy`
- No issues detected
- All systems operational
- Queue functioning normally

### `healthy_with_warnings`
- Minor issues detected
- System still operational
- No critical problems
- Auto-healing may be in progress

### `degraded`
- Critical issues detected
- System functionality impaired
- Immediate attention recommended
- Auto-healing attempted or in progress

---

## Health Checks Performed

### 1. Runtime Service Status
- Always returns service name
- Includes last run timestamp if available

### 2. HealthMonitor Integration (when available)
Checks for:
- **Disk space issues**: Usage >80%
- **Stale tasks**: Running >2 hours
- **Process failures**: Crashed batch processors
- **Queue blockages**: Stuck tasks
- **Resource exhaustion**: Memory/CPU limits

### 3. Queue Statistics
- Pending tasks count
- Active batches count
- Batch details (ID, status)

---

## Implementation Details

### Code Location
`runtime/api.py` lines 44-118

### Key Components

```python
@app.get("/api/v1/runtime/health")
async def health():
    # 1. Initialize basic health status
    health_status = {
        "status": "healthy",
        "service": "cortex-runtime",
        "timestamp": executor.history.metrics.get("last_run_timestamp", None),
    }

    # 2. Try to integrate with supervisor
    try:
        from supervisor import HealthMonitor
        from intelligence.process_monitor.batch_queue import BatchTaskQueue

        # Create instances
        shell_queue = BatchTaskQueue()
        health_monitor = HealthMonitor(shell_queue=shell_queue)

        # Run health check
        issues = health_monitor.check()

        # 3. Add results to response
        health_status["health_monitor"] = {
            "enabled": True,
            "issues_detected": len(issues),
            "issues": [...]
        }

        # 4. Determine status based on severity
        critical_issues = [i for i in issues if i.severity == "critical"]
        if critical_issues:
            health_status["status"] = "degraded"
        elif issues:
            health_status["status"] = "healthy_with_warnings"

        # 5. Add queue stats
        queue_stats = shell_queue.get_queue_stats()
        health_status["queue"] = queue_stats

    except ImportError:
        # Supervisor not available - basic health only
        health_status["health_monitor"] = {"enabled": False, ...}
    except Exception as e:
        # Check failed but runtime still up
        health_status["health_monitor"] = {"error": str(e), ...}

    return health_status
```

---

## Usage Examples

### Command Line (curl)

```bash
# Basic check
curl http://localhost:8000/api/v1/runtime/health

# Formatted output
curl -s http://localhost:8000/api/v1/runtime/health | jq '.'

# Check specific field
curl -s http://localhost:8000/api/v1/runtime/health | jq '.status'

# Monitor continuously (every 5 seconds)
watch -n 5 'curl -s http://localhost:8000/api/v1/runtime/health | jq ".status"'
```

### Python

```python
import requests

# Get health status
response = requests.get("http://localhost:8000/api/v1/runtime/health")
health = response.json()

# Check status
if health["status"] == "healthy":
    print("✅ System healthy")
elif health["status"] == "healthy_with_warnings":
    print(f"⚠️  System operational with {health['warnings']} warnings")
else:
    print(f"❌ System degraded: {health.get('critical_issues', 0)} critical issues")

# Get issue details
if health["health_monitor"]["enabled"]:
    for issue in health["health_monitor"]["issues"]:
        print(f"- {issue['type']}: {issue['description']} ({issue['severity']})")
```

### Health Check Script

```python
#!/usr/bin/env python3
"""Check Cortex runtime health and alert if degraded"""

import requests
import sys

def check_health():
    try:
        response = requests.get("http://localhost:8000/api/v1/runtime/health", timeout=5)
        health = response.json()

        status = health.get("status", "unknown")

        if status == "degraded":
            print(f"❌ CRITICAL: Runtime degraded")
            print(f"   Critical issues: {health.get('critical_issues', 0)}")
            sys.exit(2)  # Critical
        elif status == "healthy_with_warnings":
            print(f"⚠️  WARNING: Runtime has {health.get('warnings', 0)} warnings")
            sys.exit(1)  # Warning
        else:
            print(f"✅ OK: Runtime healthy")
            sys.exit(0)  # OK

    except requests.exceptions.RequestException as e:
        print(f"❌ CRITICAL: Cannot reach runtime - {e}")
        sys.exit(2)

if __name__ == "__main__":
    check_health()
```

---

## Monitoring & Alerting

### Nagios/Icinga

```bash
# /usr/local/nagios/libexec/check_cortex_health.sh
#!/bin/bash
RESPONSE=$(curl -s http://localhost:8000/api/v1/runtime/health)
STATUS=$(echo "$RESPONSE" | jq -r '.status')

case "$STATUS" in
    "healthy")
        echo "OK - Cortex runtime healthy"
        exit 0
        ;;
    "healthy_with_warnings")
        WARNINGS=$(echo "$RESPONSE" | jq -r '.warnings')
        echo "WARNING - $WARNINGS warnings detected"
        exit 1
        ;;
    "degraded")
        CRITICAL=$(echo "$RESPONSE" | jq -r '.critical_issues')
        echo "CRITICAL - $CRITICAL critical issues"
        exit 2
        ;;
    *)
        echo "UNKNOWN - Status: $STATUS"
        exit 3
        ;;
esac
```

### Prometheus Metrics

```python
# Add to runtime/api.py
from prometheus_client import Gauge

health_status_gauge = Gauge('cortex_runtime_health', 'Health status (0=degraded, 1=warnings, 2=healthy)')
issues_gauge = Gauge('cortex_runtime_issues', 'Number of detected issues')

@app.get("/api/v1/runtime/health")
async def health():
    # ... existing code ...

    # Update metrics
    if health_status["status"] == "healthy":
        health_status_gauge.set(2)
    elif health_status["status"] == "healthy_with_warnings":
        health_status_gauge.set(1)
    else:
        health_status_gauge.set(0)

    issues_gauge.set(health_status.get("health_monitor", {}).get("issues_detected", 0))

    return health_status
```

---

## Testing the Endpoint

### Manual Testing

```bash
# 1. Start the runtime (if not running)
python -m runtime.executor

# 2. Test basic health
curl http://localhost:8000/api/v1/runtime/health

# 3. Verify HealthMonitor integration
curl -s http://localhost:8000/api/v1/runtime/health | jq '.health_monitor.enabled'
# Should return: true

# 4. Check for issues
curl -s http://localhost:8000/api/v1/runtime/health | jq '.health_monitor.issues_detected'
# Should return: 0 (if healthy)

# 5. Verify queue stats
curl -s http://localhost:8000/api/v1/runtime/health | jq '.queue'
# Should return queue statistics
```

### Automated Testing

```python
# tests/test_runtime_health.py

def test_health_endpoint_structure():
    """Test health endpoint returns expected structure"""
    response = requests.get("http://localhost:8000/api/v1/runtime/health")
    assert response.status_code == 200

    health = response.json()
    assert "status" in health
    assert "service" in health
    assert "health_monitor" in health
    assert health["service"] == "cortex-runtime"

def test_health_monitor_integration():
    """Test HealthMonitor integration"""
    response = requests.get("http://localhost:8000/api/v1/runtime/health")
    health = response.json()

    hm = health["health_monitor"]
    assert "enabled" in hm
    assert "issues_detected" in hm

    if hm["enabled"]:
        assert "issues" in hm
        assert isinstance(hm["issues"], list)

def test_status_levels():
    """Test different status levels"""
    response = requests.get("http://localhost:8000/api/v1/runtime/health")
    health = response.json()

    assert health["status"] in ["healthy", "healthy_with_warnings", "degraded"]
```

---

## Troubleshooting

### Issue: HealthMonitor Not Enabled

**Symptom**:
```json
{
  "health_monitor": {
    "enabled": false,
    "reason": "supervisor module not available"
  }
}
```

**Solution**:
1. Check if supervisor module is installed:
   ```bash
   python -c "from supervisor import HealthMonitor; print('✅ Available')"
   ```
2. If missing, check import paths in `runtime/api.py`
3. Ensure supervisor dependencies installed

---

### Issue: Health Check Error

**Symptom**:
```json
{
  "health_monitor": {
    "enabled": true,
    "error": "...",
    "status": "check_failed"
  }
}
```

**Solution**:
1. Check runtime logs for error details
2. Verify BatchTaskQueue is accessible
3. Check supervisor configuration

---

### Issue: Always Returns "healthy"

**Symptom**: Even when issues exist, status shows "healthy"

**Causes**:
1. HealthMonitor not detecting issues
2. Issue severity not set to "critical"
3. Runtime needs restart to pick up changes

**Solution**:
1. Restart runtime: `python -m runtime.executor`
2. Verify HealthMonitor configuration
3. Check issue detection thresholds

---

## Next Steps

1. **Add to CI/CD**: Include health check in deployment validation
2. **Set up monitoring**: Configure Prometheus/Nagios
3. **Create dashboard**: Visualize health metrics
4. **Add alerting**: Notify on degraded status
5. **Document runbooks**: Create response procedures for each issue type

---

## Related Files

- `runtime/api.py` - Health endpoint implementation
- `supervisor/health_monitor.py` - Health checking logic
- `intelligence/process_monitor/batch_queue.py` - Queue statistics

---

**Status**: ✅ Enhanced and production-ready
**Version**: 2.0 (with HealthMonitor integration)
**Last Updated**: 2026-01-18
