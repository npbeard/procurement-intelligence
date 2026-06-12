"""config.py — single source of truth for auth + paths. Imported by both stages."""
from __future__ import annotations
import os

# load .env automatically. (Or run with `uv run --env-file .env ...`.)
from dotenv import load_dotenv

load_dotenv()

# --- Auth defaults (real secrets come from .env / environment) ----------------
# Pick ONE compute. Leave HOST/TOKEN to the environment; don't hardcode them.
os.environ.setdefault("DATABRICKS_SERVERLESS_COMPUTE_ID", "auto")
# os.environ.setdefault("DATABRICKS_CLUSTER_ID", "0101-xxxxxx-xxxxxxxx")

# --- Paths --------------------------------------------------------------------
CATALOG = "procurement"
SCHEMA  = "ted"
VOLUME  = "raw"

# ORIGIN: raw XML in the Volume (the ONLY thing that lives in a volume)
RAW_XML_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

# TARGET: parsed Delta tables (the dbt source layer) — same schema
PARSED_TARGET = f"{CATALOG}.{SCHEMA}"

# MODELS: dbt writes here too (same schema)
MODEL_TARGET = f"{CATALOG}.{SCHEMA}"


def get_spark():
    """Notebook → ambient spark. Local/VSCode → Databricks Connect."""
    try:
        from databricks.connect import DatabricksSession
        print("Databricks connected")
        return DatabricksSession.builder.getOrCreate()
    except ImportError:
        from pyspark.sql import SparkSession
        print('Spark session created')
        return SparkSession.builder.getOrCreate()