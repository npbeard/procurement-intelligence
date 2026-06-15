# Databricks notebook source
# Orchestration Task 2: build silver dbt models.
# Runs on serverless compute in Databricks Jobs (Git source).
#
# dbt-databricks is installed via the job environment (task library).
# DATABRICKS_HOST and DATABRICKS_TOKEN are auto-set by the Databricks runtime.
# DATABRICKS_HTTP_PATH falls back to the default warehouse in profiles.yml.

# COMMAND ----------

import os
import subprocess
import sys

repo_root = os.getcwd()

result = subprocess.run(
    ["dbt", "run", "--select", "silver", "--profiles-dir", repo_root],
    check=False,
)

if result.returncode != 0:
    raise RuntimeError(f"dbt run failed with exit code {result.returncode}")

print("dbt silver models completed successfully.")
