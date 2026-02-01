# Databricks notebook source
# MAGIC %md
# MAGIC # 02 Run Calibration
# MAGIC Reads outcomes, computes per (context_id, strategy_id) success/failure/partial counts and Beta posterior, writes context_strategy_edges.

# COMMAND ----------

dbutils.widgets.text("catalog", "cortex_catalog", "Catalog")
dbutils.widgets.text("schema", "cortex_mvp", "Schema")

# COMMAND ----------

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# Read outcomes
outcomes_df = spark.table(f"{CATALOG}.{SCHEMA}.outcomes")

# COMMAND ----------

# Aggregate per (context_id, strategy_id): success_count, failure_count, partial_count
aggregated = outcomes_df.groupBy("context_id", "strategy_id").agg(
    F.sum(F.when(F.col("result") == "SUCCESS", 1).otherwise(0)).alias("success_count"),
    F.sum(F.when(F.col("result") == "FAILURE", 1).otherwise(0)).alias("failure_count"),
    F.sum(F.when(F.col("result") == "PARTIAL", 1).otherwise(0)).alias("partial_count"),
    F.max("created_at").alias("last_updated"),
)

# COMMAND ----------

# Beta-Binomial: alpha = prior_alpha + success + 0.5*partial, beta = prior_beta + failure + 0.5*partial
# confidence = alpha / (alpha + beta)
edges_df = aggregated.withColumn(
    "alpha",
    F.lit(PRIOR_ALPHA) + F.col("success_count") + 0.5 * F.col("partial_count"),
).withColumn(
    "beta",
    F.lit(PRIOR_BETA) + F.col("failure_count") + 0.5 * F.col("partial_count"),
).withColumn(
    "confidence",
    F.col("alpha") / (F.col("alpha") + F.col("beta")),
)

# COMMAND ----------

# Write context_strategy_edges
edges_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.context_strategy_edges")

# COMMAND ----------

# Verify
display(spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.context_strategy_edges ORDER BY confidence DESC LIMIT 20"))
display(spark.sql(f"SELECT COUNT(*) as total_edges FROM {CATALOG}.{SCHEMA}.context_strategy_edges"))
