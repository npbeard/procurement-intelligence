# Databricks notebook source
# Orchestration Task 2: build silver dbt models.

# COMMAND ----------

import subprocess, sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "dbt-databricks>=1.8", "--quiet"],
    check=True,
)

# COMMAND ----------

import os, shutil, tempfile

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
nb_path = ctx.notebookPath().get()
repo_root = "/Workspace" + "/".join(nb_path.split("/")[:-2])
print(f"repo_root: {repo_root}")

# Copy dbt project to a local temp dir to avoid WSFS FUSE filesystem quirks.
# The WSFS mount used by Databricks Repos returns non-standard errors for
# optional files (e.g. selectors.yml) that dbt tries to read on startup,
# causing dbt to abort. A local copy avoids this entirely.
tmp_dir = tempfile.mkdtemp(dir="/tmp")

for fname in ["dbt_project.yml", "profiles.yml", "package-lock.yml", "packages.yml"]:
    src = os.path.join(repo_root, fname)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(tmp_dir, fname))

for dname in ["models", "seeds", "macros", "tests", "analyses", "snapshots"]:
    src = os.path.join(repo_root, dname)
    if os.path.exists(src):
        shutil.copytree(src, os.path.join(tmp_dir, dname))

os.chdir(tmp_dir)

# Get runtime credentials from the Databricks notebook context.
# DATABRICKS_HOST / DATABRICKS_TOKEN are not auto-set as env vars in serverless,
# but are available via dbutils context and needed by the dbt-databricks adapter.
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
dbt_env = os.environ.copy()
dbt_env["DATABRICKS_HOST"]      = ctx.apiUrl().get()           # includes https://
dbt_env["DATABRICKS_TOKEN"]     = ctx.apiToken().get()
dbt_env["DATABRICKS_HTTP_PATH"] = dbt_env.get(
    "DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/9d31ee3378c194b4"
)

# Install dbt packages (dbt-utils etc. from packages.yml)
if os.path.exists(os.path.join(tmp_dir, "packages.yml")):
    subprocess.run(["dbt", "deps", "--profiles-dir", tmp_dir], env=dbt_env, check=False)

# Run silver models (capture output so errors surface in job logs)
result = subprocess.run(
    ["dbt", "run", "--select", "silver", "--profiles-dir", tmp_dir],
    capture_output=True, text=True, env=dbt_env,
)

if result.returncode != 0:
    out_tail = (result.stdout + "\n" + result.stderr)[-3000:]
    raise RuntimeError(f"dbt run failed (exit {result.returncode}):\n{out_tail}")

print("dbt silver models completed successfully.")
