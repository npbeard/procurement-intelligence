# Databricks notebook source
# Orchestration Task 0: download new TED daily packages → raw XML Volume.

# COMMAND ----------

import subprocess, sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "databricks-sdk", "tqdm", "--quiet"],
    check=True,
)

# COMMAND ----------

import os

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
nb_path = ctx.notebookPath().get()
repo_root = "/Workspace" + "/".join(nb_path.split("/")[:-2])

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

os.chdir(repo_root)
print(f"repo_root: {repo_root}")

# COMMAND ----------

from scripts.bronze_ingest_spark import ingest_latest

ingest_latest()
