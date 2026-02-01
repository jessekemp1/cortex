# CortexDBx

Intelligence Layer for Databricks: outcome-based learning with calibrated recommendations.

## Overview

CortexDBx tracks context, strategy, and outcome; calibrates confidence via Beta-Binomial; and surfaces recommendations. It runs locally (in-memory) for dev and tests, or on Databricks (Delta/Unity Catalog) for production.

## Structure

```
cortexdbx/
├── __init__.py           # Package exports
├── synthetic/            # Synthetic data generator (6 domains)
├── calibration/          # Bayesian calibration
├── sdk/                   # Python SDK (local + Spark-ready)
├── agents/                # Agent team architecture
├── scripts/               # Local verification
│   ├── run_e2e_local.sh  # Run unit + e2e tests
│   └── run_e2e_local.py
├── notebooks/             # Databricks notebooks
│   ├── 01_generate_synthetic_data.py
│   ├── 02_run_calibration.py
│   └── 03_run_recommendations.py
├── databricks/            # Databricks deployment
│   ├── jobs/              # Job JSON definitions
│   └── README.md          # How to run on Databricks
└── tests/
    ├── test_e2e_learning_loop.py  # Full learning loop e2e
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

## E2E: Run locally first

Validate the full learning loop (generate, ingest, calibrate, recommend) before Databricks:

```bash
cd /path/to/cortex
./cortexdbx/scripts/run_e2e_local.sh
# or
python cortexdbx/scripts/run_e2e_local.py
```

This runs all unit tests and e2e tests (`test_e2e_learning_loop.py`). Success criteria: Brier < 0.25, at least one recommendation for a seen context.

## Databricks: Build and run

Same flow (generate synthetic data, run calibration, write recommendations) on Databricks:

1. Clone the cortex repo into Databricks Repos; set `PYTHONPATH` to the repo root so `import cortexdbx` works.
2. Run notebooks in order: `01_generate_synthetic_data` -> `02_run_calibration` -> `03_run_recommendations` (or create jobs from `cortexdbx/databricks/jobs/*.json`).
3. Verify: query `outcomes`, `context_strategy_edges`, and `recommendations` (see verification queries in `cortexdbx/databricks/README.md`).

Full steps, job definitions, and verification: [cortexdbx/databricks/README.md](databricks/README.md).

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
