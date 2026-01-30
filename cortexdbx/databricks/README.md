# CortexDBx on Databricks

How to build and run CortexDBx in a Databricks workspace (generate synthetic data, run calibration, write recommendations).

## Prerequisites

- Databricks workspace with Python 3.8+
- Cluster or job cluster with access to Unity Catalog (or use `hive_metastore`)

## Option A: Repos (recommended)

1. **Clone the cortex repo into Databricks Repos**
   - In the workspace: Repos -> Add Repo -> clone your cortex repo (e.g. `https://github.com/<org>/cortex.git`).
   - Repo will be at e.g. `/Repos/<user>/cortex` (or whatever name you gave the repo).

2. **Set PYTHONPATH so `cortexdbx` is importable**
   - On the cluster: Environment variables -> add `PYTHONPATH` = `/Repos/<user>/cortex` (replace with your repo path).
   - Or in the job cluster config: same env var.

3. **Update job notebook paths**
   - Job JSON files in `cortexdbx/databricks/jobs/` use paths like `/Repos/cortex/cortexdbx/notebooks/01_generate_synthetic_data`.
   - If your repo is under a different path (e.g. `/Repos/<user>/cortex`), update the `notebook_path` in each job JSON to match (e.g. `/Repos/<user>/cortex/cortexdbx/notebooks/01_generate_synthetic_data`).

4. **Run notebooks in order**
   - **01_generate_synthetic_data**: Creates catalog/schema if needed, generates synthetic outcomes, writes `contexts`, `strategies`, `outcomes`.
   - **02_run_calibration**: Reads `outcomes`, computes per (context_id, strategy_id) Beta posterior, writes `context_strategy_edges`.
   - **03_run_recommendations**: Reads `context_strategy_edges`, filters by min_confidence, writes `recommendations`.

   You can run them manually from the Repo notebook UI, or create jobs that run these notebooks (see Job definitions below).

## Option B: Job + wheel

1. Build a wheel that includes `cortexdbx` (e.g. from the cortex repo root: ensure `cortexdbx` is a package, then `pip wheel .` or build via setup.py).
2. Install the wheel on the job cluster (e.g. pip install from a volume or from DBFS).
3. Run the same notebooks; they will import `cortexdbx` from the installed package.

## Job definitions

Job JSON files are in `cortexdbx/databricks/jobs/`:

- **generate_synthetic_data_job.json**: Runs 01 once (generate data).
- **calibration_job.json**: Runs 02 on a schedule (e.g. hourly).
- **full_run_job.json**: Runs 01 -> 02 -> 03 in sequence (generate, calibrate, recommendations).

To create a job from JSON (Databricks CLI or API):

```bash
databricks jobs create --json-file cortexdbx/databricks/jobs/full_run_job.json
```

Or in the workspace: Workflows -> Create Job -> paste/import the JSON (and fix notebook paths if needed).

## Widgets / parameters

Notebooks use Databricks widgets for:

- **catalog**: e.g. `cortex_catalog` (use `hive_metastore` if not using Unity Catalog).
- **schema**: e.g. `cortex_mvp`.
- **outcomes_per_domain** (01 only): e.g. `1000`.
- **min_confidence** (03 only): e.g. `0.7`.

Defaults are set in the notebooks; jobs pass them via `base_parameters`.

## Verification in Databricks

After running the notebooks:

1. **After 01**
   - `SELECT COUNT(*) FROM <catalog>.<schema>.outcomes`  
   - Expect hundreds/thousands per domain (e.g. 6000 total for 6 domains x 1000).

2. **After 02**
   - `SELECT COUNT(*) FROM <catalog>.<schema>.context_strategy_edges`  
   - Expect hundreds/thousands of edges.
   - `SELECT * FROM <catalog>.<schema>.context_strategy_edges ORDER BY confidence DESC LIMIT 20`  
   - Spot-check: confidence in [0, 1], alpha/beta positive.

3. **After 03**
   - `SELECT COUNT(*) FROM <catalog>.<schema>.recommendations`  
   - Expect recommendations with confidence >= min_confidence.
   - Optionally, in a Python cell, use `CortexDBxClient(use_local_backend=False)` with Spark to call `recommend(context)` for a known context and assert non-empty result (requires SDK wired to Delta; see docs/v1/CORTEXDBX_MVP.md).

## Success criteria

- Generate and calibration jobs complete without error.
- Tables `outcomes`, `context_strategy_edges`, and (if run) `recommendations` are populated.
- Spot-check: confidence values in [0, 1], at least one recommendation for a context that had outcomes.
