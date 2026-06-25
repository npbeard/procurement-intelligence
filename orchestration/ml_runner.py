# Databricks notebook source
# Orchestration Task 3: score IT tenders with ML models → gold tables.
#
# Runs AFTER run_silver_dbt so gold_it_lots and silver_lots_enriched are fresh.
# On first run: trains XGBoost and saves the model to DBFS.
# On all subsequent runs: loads the saved model and scores only (no retraining).

# COMMAND ----------

import subprocess, sys

subprocess.run(
    [sys.executable, "-m", "pip", "install",
     "xgboost", "scikit-learn", "joblib", "databricks-connect", "--quiet"],
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

from pyspark.sql import SparkSession
from ml_models.opportunity_scorer import run_opportunity_scoring, DEFAULT_MODEL_PATH

spark = SparkSession.builder.getOrCreate()

# Inject Databricks credentials so feature_engineering.py can open a
# Databricks Connect session (it needs host + token even inside Databricks).
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
os.environ["DATABRICKS_HOST"]  = ctx.apiUrl().get()
os.environ["DATABRICKS_TOKEN"] = ctx.apiToken().get()

results = run_opportunity_scoring(
    spark=spark,
    days_lookback=90,
    force_retrain=False,   # load saved model; only trains on very first run
    model_path=DEFAULT_MODEL_PATH,
    write_gold=True,
)

opps = results["opportunities"]
if opps is not None:
    print(f"\nML scoring complete.")
    print(f"  Opportunities written: {len(opps):,}")
    print(f"  Total pipeline EV:     €{opps['expected_value'].sum()/1e6:.1f}M")
else:
    print("\nML scoring skipped — nb_tenders_received not yet populated.")
