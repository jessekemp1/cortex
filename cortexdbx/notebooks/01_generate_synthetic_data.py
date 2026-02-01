# Databricks notebook source
# MAGIC %md
# MAGIC # 01 Generate Synthetic Data
# MAGIC Creates catalog/schema if needed, generates outcomes for CortexDBx domains, writes to Delta (contexts, strategies, outcomes).
# MAGIC Requires: cortexdbx on PYTHONPATH (e.g. repo root) or installed via pip.

# COMMAND ----------

# Widgets for catalog and schema (defaults work with Unity Catalog or hive_metastore)
dbutils.widgets.text("catalog", "cortex_catalog", "Catalog")
dbutils.widgets.text("schema", "cortex_mvp", "Schema")
dbutils.widgets.text("outcomes_per_domain", "1000", "Outcomes per domain")

# COMMAND ----------

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
OUTCOMES_PER_DOMAIN = int(dbutils.widgets.get("outcomes_per_domain"))

# COMMAND ----------

# Create catalog and schema if using Unity Catalog (skip if hive_metastore)
if CATALOG != "hive_metastore":
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")

# COMMAND ----------

# Import cortexdbx (must be on PYTHONPATH or installed)
from cortexdbx.synthetic.generator import SyntheticDataGenerator, DOMAIN_CONFIGS
import json
from datetime import datetime

# COMMAND ----------

# Generate data for all 6 domains
all_contexts = {}
all_strategies = {}
all_outcomes = []

for domain in DOMAIN_CONFIGS:
    gen = SyntheticDataGenerator(domain, seed=42)
    for record in gen.generate_dataset(OUTCOMES_PER_DOMAIN):
        ctx = record["context"]
        strat = record["strategy"]
        out = record["outcome"]
        all_contexts[ctx["context_id"]] = {
            "context_id": ctx["context_id"],
            "context_hash": ctx["context_hash"],
            "domain": ctx["domain"],
            "factors": json.dumps(ctx["factors"]),
            "first_seen": out["created_at"],
            "last_seen": out["created_at"],
        }
        all_strategies[strat["strategy_id"]] = {
            "strategy_id": strat["strategy_id"],
            "name": strat["name"],
            "domain": strat["domain"],
            "category": strat.get("category", "primary"),
            "created_at": out["created_at"],
        }
        all_outcomes.append({
            "outcome_id": out["outcome_id"],
            "context_id": out["context_id"],
            "strategy_id": out["strategy_id"],
            "result": out["result"],
            "evidence": out["evidence"],
            "actor": out["actor"],
            "created_at": out["created_at"],
        })

# COMMAND ----------

# Write contexts (overwrite for demo; use append for incremental)
contexts_df = spark.createDataFrame(list(all_contexts.values()))
contexts_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.contexts")

# COMMAND ----------

# Write strategies
strategies_df = spark.createDataFrame(list(all_strategies.values()))
strategies_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.strategies")

# COMMAND ----------

# Write outcomes
outcomes_df = spark.createDataFrame(all_outcomes)
outcomes_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.outcomes")

# COMMAND ----------

# Verify
display(spark.sql(f"SELECT domain, COUNT(*) as cnt FROM {CATALOG}.{SCHEMA}.outcomes GROUP BY domain"))
display(spark.sql(f"SELECT COUNT(*) as total_outcomes FROM {CATALOG}.{SCHEMA}.outcomes"))
