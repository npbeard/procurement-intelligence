"""
create_job.py — Create (or update) the TED daily silver pipeline in Databricks Jobs.

Run once from your local machine:
    python orchestration/create_job.py

Prerequisites:
  1. .env must contain DATABRICKS_HOST and DATABRICKS_TOKEN
  2. A Databricks Repo must exist at REPO_PATH below, checked out to the
     branch you want the job to run (sync it via the Repos API or the UI
     before each deploy — this workspace is serverless-only, which doesn't
     support git_source/python_file_task, so notebooks run from the Repo's
     WORKSPACE path instead of a live git checkout).

What this creates:
  A Databricks Job named "TED — Daily Silver Pipeline" with three tasks:
    ingest_bronze  — orchestration/ingest_runner (TED → raw XML Volume, resumes from latest edition)
    parse_bronze   — orchestration/bronze_runner (incremental XML → Delta tables)
    run_silver_dbt — orchestration/dbt_runner (dbt run --select +silver)

  The job runs on serverless compute and is scheduled daily at 08:00 UTC.
"""

from __future__ import annotations

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

HOST  = os.environ["DATABRICKS_HOST"].rstrip("/")
TOKEN = os.environ["DATABRICKS_TOKEN"]

REPO_PATH = "/Repos/nicopbeard@gmail.com/procurement-intelligence"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


JOB_CONFIG: dict = {
    "name": "TED — Daily Silver Pipeline",

    "schedule": {
        "quartz_cron_expression": "0 0 8 * * ?",
        "timezone_id": "UTC",
        "pause_status": "UNPAUSED",
    },

    # Packages are installed inside each notebook via pip (no environment_key needed).
    # Notebooks run from the Databricks Repo's WORKSPACE path (serverless doesn't
    # support git_source notebook/python_file tasks on this workspace).
    "tasks": [
        {
            "task_key": "ingest_bronze",
            "description": "Download new TED daily packages → raw XML Volume (resumes from latest edition).",
            "notebook_task": {
                "notebook_path": f"{REPO_PATH}/orchestration/ingest_runner",
                "source": "WORKSPACE",
            },
        },
        {
            "task_key": "parse_bronze",
            "description": "Parse new XML notices from Volume → bronze Delta tables (incremental).",
            "depends_on": [{"task_key": "ingest_bronze"}],
            "notebook_task": {
                "notebook_path": f"{REPO_PATH}/orchestration/bronze_runner",
                "source": "WORKSPACE",
            },
        },
        {
            "task_key": "run_silver_dbt",
            "description": "Build silver dbt models from bronze Delta tables.",
            "depends_on": [{"task_key": "parse_bronze"}],
            "notebook_task": {
                "notebook_path": f"{REPO_PATH}/orchestration/dbt_runner",
                "source": "WORKSPACE",
            },
        },
    ],
}


def get_existing_job_id(name: str) -> int | None:
    resp = requests.get(
        f"{HOST}/api/2.1/jobs/list",
        headers=HEADERS,
        params={"name": name},
    )
    resp.raise_for_status()
    for job in resp.json().get("jobs", []):
        if job["settings"]["name"] == name:
            return job["job_id"]
    return None


def create_job(config: dict) -> int:
    resp = requests.post(f"{HOST}/api/2.1/jobs/create", headers=HEADERS, json=config)
    if not resp.ok:
        raise RuntimeError(f"Job creation failed ({resp.status_code}): {resp.text}")
    return resp.json()["job_id"]


def update_job(job_id: int, config: dict) -> None:
    resp = requests.post(
        f"{HOST}/api/2.1/jobs/reset",
        headers=HEADERS,
        json={"job_id": job_id, "new_settings": config},
    )
    if not resp.ok:
        raise RuntimeError(f"Job update failed ({resp.status_code}): {resp.text}")


def main() -> None:
    job_name = JOB_CONFIG["name"]
    existing_id = get_existing_job_id(job_name)

    if existing_id:
        print(f"Updating existing job '{job_name}' (id={existing_id})...")
        update_job(existing_id, JOB_CONFIG)
        job_id = existing_id
    else:
        print(f"Creating job '{job_name}'...")
        job_id = create_job(JOB_CONFIG)

    print(f"\nJob id: {job_id}")
    print(f"Open:   {HOST}/jobs/{job_id}")
    print()
    print("Note: this job runs notebooks from the Databricks Repo's WORKSPACE path.")
    print(f"Sync the Repo at {REPO_PATH} to the branch you want before each deploy.")


if __name__ == "__main__":
    main()
