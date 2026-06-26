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

import datetime
from pyspark.sql import SparkSession
from ml_models.opportunity_scorer import run_opportunity_scoring, DEFAULT_MODEL_PATH

spark = SparkSession.builder.getOrCreate()

# Inject Databricks credentials so feature_engineering.py can open a
# Databricks Connect session (it needs host + token even inside Databricks).
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
os.environ["DATABRICKS_HOST"]  = ctx.apiUrl().get()
os.environ["DATABRICKS_TOKEN"] = ctx.apiToken().get()

STATUS_TABLE = "capstone.ted.pipeline_status"


def _write_status(task: str, status: str, message: str):
    """Append a single-row status record to the pipeline_status Delta table."""
    row = [{
        "run_time": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "task":     task,
        "status":   status,
        "message":  message[:500],
    }]
    (spark.createDataFrame(row)
          .write
          .mode("append")
          .option("mergeSchema", "true")
          .saveAsTable(STATUS_TABLE))


# COMMAND ----------

# Ensure the Unity Catalog Volume exists before saving the model.
# DBFS root is disabled in this workspace; Volumes are the correct storage layer.
spark.sql("CREATE VOLUME IF NOT EXISTS capstone.ted.models")

status = "FAILED"
message = "Unknown error before scoring started."

try:
    results = run_opportunity_scoring(
        spark=spark,
        days_lookback=90,
        force_retrain=False,   # load saved model; only trains on very first run
        model_path=DEFAULT_MODEL_PATH,
        write_gold=True,
    )

    opps = results["opportunities"]
    pins = results.get("pins")

    if opps is not None:
        n_opps = len(opps)
        n_pins = len(pins) if pins is not None else 0
        ev_m   = opps["expected_value"].sum() / 1e6
        message = (
            f"{n_opps:,} opportunities scored, {n_pins:,} PINs flagged, "
            f"pipeline EV €{ev_m:.1f}M"
        )
        status = "SUCCESS"
        print(f"\nML scoring complete.")
        print(f"  Opportunities written: {n_opps:,}")
        print(f"  PIN Monitor rows:      {n_pins:,}")
        print(f"  Total pipeline EV:     €{ev_m:.1f}M")
    else:
        status = "SKIPPED"
        message = "nb_tenders_received not yet populated — model cannot train."
        print(f"\n{message}")

except Exception as exc:
    message = str(exc)[:500]
    print(f"\n[ERROR] ML scoring failed: {exc}")
    raise

finally:
    try:
        _write_status("run_ml_scoring", status, message)
        print(f"\nPipeline status written → {STATUS_TABLE}: {status}")
    except Exception as log_exc:
        print(f"\n[WARNING] Could not write pipeline status: {log_exc}")
