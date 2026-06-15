# Databricks notebook source
# Orchestration Task 1: parse new XML notices from Volume → bronze Delta tables.

# COMMAND ----------

import subprocess, sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "lxml>=5.0", "tqdm", "--quiet"],
    check=True,
)

# COMMAND ----------

import os

# Find repo root from the workspace path of this notebook.
# dbutils is a Databricks built-in — always available in notebooks.
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
nb_path = ctx.notebookPath().get()
# nb_path = '/Users/.../procurement-intelligence/orchestration/bronze_runner'
# Repo root is two levels up (strip '/orchestration/bronze_runner')
repo_root = "/Workspace" + "/".join(nb_path.split("/")[:-2])

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

os.chdir(repo_root)
print(f"repo_root: {repo_root}")

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
