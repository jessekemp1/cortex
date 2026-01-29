# CortexDBx

Intelligence Layer for Databricks: outcome-based learning with calibrated recommendations.

## Overview

CortexDBx tracks context, strategy, and outcome; calibrates confidence via Beta-Binomial; and surfaces recommendations. It runs locally (in-memory) for dev and tests, or on Databricks (Delta/Unity Catalog) for production.

## Structure

```
cortexdbx/
├── __init__.py           # Package exports
├── synthetic/            # Synthetic data generator (6 domains)
│   ├── generator.py      # SyntheticDataGenerator, DOMAIN_CONFIGS
│   └── __init__.py
├── calibration/          # Bayesian calibration
│   ├── engine.py          # CalibrationEngine, CalibrationState
│   └── __init__.py
├── sdk/                   # Python SDK
│   ├── client.py         # CortexDBxClient (local + Spark-ready)
│   └── __init__.py
├── agents/                # Agent team architecture
│   ├── definitions.py    # Agent configs per domain
│   ├── orchestrator.py   # AgentOrchestrator
│   └── __init__.py
└── tests/
    ├── test_generator.py
    ├── test_calibration.py
    ├── test_sdk.py
    └── test_orchestrator.py
```

## Quick Start

### Local (no Databricks)

```python
from cortexdbx import SyntheticDataGenerator, CalibrationEngine
from cortexdbx.sdk import CortexDBxClient

# Generate synthetic data
gen = SyntheticDataGenerator("fraud_investigation", seed=42)
data = list(gen.generate_dataset(100))

# Calibrate from outcomes
engine = CalibrationEngine()
for r in data:
    engine.update(
        r["context"]["context_id"],
        r["strategy"]["strategy_id"],
        r["outcome"]["result"],
    )

# Or use SDK (in-memory backend)
client = CortexDBxClient()
client.log_outcome({"alert_type": "fraud"}, "escalate_to_analyst", "SUCCESS")
recs = client.recommend({"alert_type": "fraud"}, min_confidence=0.5)
```

### Run Tests

```bash
cd /path/to/cortex
python -m pytest cortexdbx/tests/ -v
```

## Domains (6 use cases)

- fraud_investigation
- clinical_trial
- maintenance
- marketing_campaign
- security_incident
- supply_chain

## Documentation

- [CortexDBx MVP Implementation](../../docs/v1/CORTEXDBX_MVP.md) - Full spec, Delta schema, Databricks jobs
- [Cortex Core](../../docs/v1/CORTEX_CORE.md) - Vision and architecture

## Version

0.1.0
