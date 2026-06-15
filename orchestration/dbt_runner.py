"""
dbt_runner.py — Databricks Job task: build silver dbt models.

Runs as a Python file task inside a Databricks Job (Git source).
The job's runtime automatically provides DATABRICKS_HOST and DATABRICKS_TOKEN;
you only need to set DATABRICKS_HTTP_PATH as a task environment variable
(the SQL Warehouse HTTP path, e.g. /sql/1.0/warehouses/<warehouse-id>).

Required task library (set in the job config): dbt-databricks
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
os.chdir(repo_root)

if "DATABRICKS_HTTP_PATH" not in os.environ:
    raise EnvironmentError(
        "DATABRICKS_HTTP_PATH is not set. "
        "Add it as a task environment variable in the Databricks job config."
    )

result = subprocess.run(
    [
        "dbt", "run",
        "--select", "silver",
        "--profiles-dir", str(repo_root),
    ],
    check=False,
)
sys.exit(result.returncode)
