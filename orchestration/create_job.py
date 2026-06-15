"""
create_job.py — Create (or update) the TED daily silver pipeline in Databricks Jobs.

Run this once from your local machine:
    python orchestration/create_job.py

Prerequisites:
  1. .env must contain DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH
  2. Your GitHub repo must be connected in Databricks:
       Settings → Linked accounts → Add a git credential (GitHub, Personal Access Token)
     (Without this, the Git-source job can't clone the repo.)

What this creates:
  A Databricks Job named "TED — Daily Silver Pipeline" with two tasks:
    parse_bronze   — runs scripts/bronze_to_silver_spark.py (incremental XML → Delta)
    run_silver_dbt — runs orchestration/dbt_runner.py (dbt run --select silver)

  The job is scheduled daily at 08:00 UTC but starts PAUSED so you can test
  manually first. Unpause it in Jobs & Pipelines → Edit → Schedule → Unpaused.
"""

from __future__ import annotations

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

HOST  = os.environ["DATABRICKS_HOST"].rstrip("/")
TOKEN = os.environ["DATABRICKS_TOKEN"]
HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]

GITHUB_REPO = "https://github.com/npbeard/procurement-intelligence.git"
GITHUB_BRANCH = "main"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


JOB_CONFIG = {
    "name": "TED — Daily Silver Pipeline",

    "git_source": {
        "git_url": GITHUB_REPO,
        "git_provider": "gitHub",
        "git_branch": GITHUB_BRANCH,
    },

    "schedule": {
        "quartz_cron_expression": "0 0 8 * * ?",
        "timezone_id": "UTC",
        "pause_status": "PAUSED",
    },

    # Serverless environments — libraries installed before the task runs.
    "environments": [
        {
            "environment_key": "bronze_env",
            "spec": {
                "client": "1",
                "dependencies": ["lxml>=5.0", "tqdm"],
            },
        },
        {
            "environment_key": "dbt_env",
            "spec": {
                "client": "1",
                "dependencies": ["dbt-databricks>=1.8"],
            },
        },
    ],

    "tasks": [
        {
            "task_key": "parse_bronze",
            "description": "Parse new XML notices from Volume → bronze Delta tables (incremental).",
            "python_file_task": {
                "python_file": "scripts/bronze_to_silver_spark.py",
            },
            "environment_key": "bronze_env",
        },
        {
            "task_key": "run_silver_dbt",
            "description": "Build silver dbt models from bronze Delta tables.",
            "depends_on": [{"task_key": "parse_bronze"}],
            "python_file_task": {
                "python_file": "orchestration/dbt_runner.py",
            },
            "environment_key": "dbt_env",
            "task_key_env_vars": {
                "DATABRICKS_HTTP_PATH": HTTP_PATH,
            },
        },
    ],
}


def get_existing_job_id(name: str) -> int | None:
    """Return the job ID if a job with this name already exists, else None."""
    url = f"{HOST}/api/2.1/jobs/list"
    resp = requests.get(url, headers=HEADERS, params={"name": name})
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    for job in jobs:
        if job["settings"]["name"] == name:
            return job["job_id"]
    return None


def create_job(config: dict) -> int:
    url = f"{HOST}/api/2.1/jobs/create"
    resp = requests.post(url, headers=HEADERS, json=config)
    resp.raise_for_status()
    return resp.json()["job_id"]


def update_job(job_id: int, config: dict) -> None:
    url = f"{HOST}/api/2.1/jobs/reset"
    resp = requests.post(url, headers=HEADERS, json={"job_id": job_id, "new_settings": config})
    resp.raise_for_status()


def main() -> None:
    job_name = JOB_CONFIG["name"]
    existing_id = get_existing_job_id(job_name)

    if existing_id:
        print(f"Job '{job_name}' already exists (id={existing_id}). Updating...")
        update_job(existing_id, JOB_CONFIG)
        job_id = existing_id
        print(f"Updated job {job_id}.")
    else:
        job_id = create_job(JOB_CONFIG)
        print(f"Created job '{job_name}' (id={job_id}).")

    workspace_url = f"{HOST}/jobs/{job_id}"
    print(f"\nOpen in Databricks: {workspace_url}")
    print("\nNext steps:")
    print("  1. Open the link above and run the job manually once to verify it works.")
    print("  2. When happy, unpause the schedule: Edit → Schedule → Unpaused.")
    print("  3. Make sure your GitHub repo is linked in Databricks:")
    print("     Settings → Linked accounts → Add a git credential.")


if __name__ == "__main__":
    main()
