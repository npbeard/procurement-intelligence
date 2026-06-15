"""
create_job.py — Create (or update) the TED daily silver pipeline in Databricks Jobs.

Run once from your local machine:
    python orchestration/create_job.py

Prerequisites:
  1. .env must contain DATABRICKS_HOST and DATABRICKS_TOKEN
  2. Your GitHub repo must be linked in Databricks:
       Settings → Linked accounts → Add a git credential (GitHub PAT with repo scope)

What this creates:
  A Databricks Job named "TED — Daily Silver Pipeline" with two tasks:
    parse_bronze   — orchestration/bronze_runner (incremental XML → Delta tables)
    run_silver_dbt — orchestration/dbt_runner (dbt run --select silver)

  The job runs on serverless compute, is scheduled daily at 08:00 UTC,
  and starts PAUSED so you can test manually first.
  To start: Jobs & Pipelines → TED — Daily Silver Pipeline → Run now.
  To activate schedule: Edit → Schedule → Unpaused.
"""

from __future__ import annotations

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

HOST  = os.environ["DATABRICKS_HOST"].rstrip("/")
TOKEN = os.environ["DATABRICKS_TOKEN"]

GITHUB_REPO   = "https://github.com/npbeard/procurement-intelligence.git"
GITHUB_BRANCH = "main"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


JOB_CONFIG: dict = {
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

    # Serverless environments — packages installed before the task runs.
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
            "notebook_task": {
                "notebook_path": "orchestration/bronze_runner",
                "source": "GIT",
            },
            "environment_key": "bronze_env",
        },
        {
            "task_key": "run_silver_dbt",
            "description": "Build silver dbt models from bronze Delta tables.",
            "depends_on": [{"task_key": "parse_bronze"}],
            "notebook_task": {
                "notebook_path": "orchestration/dbt_runner",
                "source": "GIT",
            },
            "environment_key": "dbt_env",
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
    print("Next steps:")
    print("  1. Make sure your GitHub is linked in Databricks:")
    print("     Settings → Linked accounts → Add a git credential")
    print("  2. Click 'Run now' in the job UI to test it manually.")
    print("  3. When happy, edit the schedule → Unpaused to activate daily runs.")


if __name__ == "__main__":
    main()
