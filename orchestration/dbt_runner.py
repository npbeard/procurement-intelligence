# Databricks notebook source
# Orchestration Task 2: build silver dbt models.

# COMMAND ----------

import subprocess, sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "dbt-databricks>=1.8", "--quiet"],
    check=True,
)

# COMMAND ----------

import os

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
nb_path = ctx.notebookPath().get()
repo_root = "/Workspace" + "/".join(nb_path.split("/")[:-2])
os.chdir(repo_root)
print(f"repo_root: {repo_root}")

# COMMAND ----------

result = subprocess.run(
    ["dbt", "run", "--select", "silver", "--profiles-dir", repo_root],
    check=False,
)

if result.returncode != 0:
    raise RuntimeError(f"dbt run failed with exit code {result.returncode}")

print("dbt silver models completed successfully.")
