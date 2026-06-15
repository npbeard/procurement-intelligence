# Databricks notebook source
# Orchestration Task 2: build silver dbt models.
# Runs on serverless compute in Databricks Jobs (Git source).

# COMMAND ----------

import subprocess, sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "dbt-databricks>=1.8", "--quiet"],
    check=True,
)

# COMMAND ----------

import os

repo_root = os.getcwd()

result = subprocess.run(
    ["dbt", "run", "--select", "silver", "--profiles-dir", repo_root],
    check=False,
)

if result.returncode != 0:
    raise RuntimeError(f"dbt run failed with exit code {result.returncode}")

print("dbt silver models completed successfully.")
