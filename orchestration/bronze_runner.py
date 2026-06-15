# Databricks notebook source
# Orchestration Task 1: parse new XML notices from Volume → bronze Delta tables.
# Runs on serverless Spark in Databricks Jobs (Git source).
#
# Databricks Repos sets os.getcwd() to the repo root, so config.py and
# scripts/ are importable without any sys.path manipulation.

# COMMAND ----------

import os
import sys

repo_root = os.getcwd()
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# COMMAND ----------

import config
from scripts.bronze_to_silver_spark import build_table_dataframes, write_delta

spark = config.get_spark()
catalog, schema = config.PARSED_TARGET.split(".")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

tables = build_table_dataframes(spark, config.RAW_XML_VOLUME, config.PARSED_TARGET)
if tables:
    write_delta(tables, config.PARSED_TARGET, writing_mode="append")
    print(f"Done. Appended new rows under {config.PARSED_TARGET}.")
else:
    print("Nothing new — tables are already up to date.")
