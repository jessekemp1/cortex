# Databricks notebook source
# MAGIC %md
# MAGIC # 03 Run Recommendations
# MAGIC Reads context_strategy_edges, filters by min_confidence, writes to recommendations table for dashboard/API.

# COMMAND ----------

dbutils.widgets.text("catalog", "cortex_catalog", "Catalog")
dbutils.widgets.text("schema", "cortex_mvp", "Schema")
dbutils.widgets.text("min_confidence", "0.7", "Min confidence")

# COMMAND ----------

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
MIN_CONFIDENCE = float(dbutils.widgets.get("min_confidence"))

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# Read edges above threshold
edges_df = spark.table(f"{CATALOG}.{SCHEMA}.context_strategy_edges").filter(
    F.col("confidence") >= MIN_CONFIDENCE
)

# COMMAND ----------

# Build recommendations: recommendation_id (unique per context_id, strategy_id), context_id, strategy_id, confidence, evidence_summary, surface, created_at
recommendations_df = edges_df.select(
    F.concat(F.col("context_id"), F.lit("_"), F.col("strategy_id")).alias("recommendation_id"),
    F.col("context_id"),
    F.col("strategy_id"),
    F.col("confidence"),
    F.concat(F.lit("success_count="), F.col("success_count").cast("string"), F.lit(", failure_count="), F.col("failure_count").cast("string")).alias("evidence_summary"),
    F.lit("dashboard").alias("surface"),
    F.current_timestamp().alias("created_at"),
)

# COMMAND ----------

# Write recommendations (overwrite for demo)
recommendations_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.recommendations")

# COMMAND ----------

# Verify
display(spark.sql(f"SELECT COUNT(*) as total_recommendations FROM {CATALOG}.{SCHEMA}.recommendations"))
display(spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.recommendations ORDER BY confidence DESC LIMIT 10"))
