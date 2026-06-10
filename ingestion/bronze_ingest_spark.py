"""
bronze_ingest_spark.py — Stage 1 (Databricks / Spark version).

Downloads TED daily XML "packages" and stores the raw, untouched notices as
individual .xml files in a Unity Catalog **Volume**. Spark is used to run the
per-edition download+extract work in parallel across the cluster instead of
one edition at a time.

Run as a Databricks job (Python file task) or spark-submit:
    bronze_ingest_spark.py --catalog main --schema ted --volume raw \
        --year 2026 --start 22 --count 180

In a notebook you can instead import this module and call
    ingest_range_spark(spark, start=22, count=180, year=2026, bronze_dir=...)
"""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

import requests
from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient

# --- Configuration -----------------------------------------------------------

TED_DAILY_URL = "https://ted.europa.eu/packages/daily/{ojs}"

from databricks.sdk import WorkspaceClient

# Auth via env vars (DATABRICKS_HOST, DATABRICKS_TOKEN) or a profile
w = WorkspaceClient(
    host="https://<your-workspace>.cloud.databricks.com", ## TODO: INSERT THE WORKSPACE
    token="<your-personal-access-token>",                 ## TODO: INSERT THE PERSONAL TOKEN
)

VOLUME_DESTINATION = "{Catalog}/{Schema}/{Volume}"        ## TODO: REPLACE THIS WITH THE ACTUAL PATH


def build_package_url(ojs_number: str) -> str:
    """Turn an OJ S edition number like '202600022' into its download URL."""
    return TED_DAILY_URL.format(ojs=ojs_number)


def download_package(ojs_number: str, landing_dir: Path) -> Path | None:
    """
    Download one daily package archive from TED into a LOCAL temp folder on the
    worker. Returns the archive path, or None if no edition was published (404).
    """
    landing_dir.mkdir(parents=True, exist_ok=True)
    url = build_package_url(ojs_number)
    archive_path = landing_dir / f"{ojs_number}.archive"

    with requests.get(url, stream=True, timeout=60) as response:
        if response.status_code == 404:
            return None
        response.raise_for_status()
        with open(archive_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    return archive_path


def extract_package(archive_path: Path, dest_dir: Path) -> int:
    """
    Extract every .xml file from the archive into dest_dir (a Volume path),
    flattened. Handles both .tar.gz and .zip. Returns the count of files written.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(".xml"):
                    data = tar.extractfile(member).read()
                    (dest_dir / Path(member.name).name).write_bytes(data)
                    count += 1
    elif zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    (dest_dir / Path(name).name).write_bytes(zf.read(name))
                    count += 1
    else:
        raise ValueError(f"{archive_path} is neither a tar nor a zip archive")

    return count


def ingest_one(ojs_number: str, bronze_dir: str) -> tuple[str, str, int]:
    """
    Full bronze step for ONE edition. This runs on a Spark EXECUTOR, so it must
    be self-contained: it downloads to its own local temp dir, then extracts the
    raw XML straight into the Volume. Returns (ojs_number, status, count).
    """
    target_dir = Path(bronze_dir) / f"ojs={ojs_number}"

    # Idempotency: if this edition is already in the Volume, don't re-download.
    if target_dir.exists() and any(target_dir.glob("*.xml")):
        return (ojs_number, "skipped", 0)

    tmp = Path(tempfile.mkdtemp())          # local scratch space on the worker
    try:
        archive_path = download_package(ojs_number, tmp)
        if archive_path is None:
            return (ojs_number, "missing", 0)
        n = extract_package(archive_path, target_dir)
        return (ojs_number, "ingested", n)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)   # always clean up the scratch dir


def ingest_range_spark(
    spark: SparkSession,
    start: int,
    count: int,
    year: int,
    bronze_dir: str,
    parallelism: int = 8,
) -> None:
    """Distribute `count` editions across the cluster and ingest them in parallel."""
    # Build the list of OJ S numbers we want, e.g. ['202600022', '202600023', ...]
    ojs_numbers = [f"{year}{(start + i):05d}" for i in range(count)]

    # parallelize() turns the Python list into a distributed dataset (an RDD),
    # split into `parallelism` chunks so that many editions download at once.
    rdd = spark.sparkContext.parallelize(ojs_numbers, numSlices=parallelism)

    # map() runs ingest_one on every edition, spread across the executors;
    # collect() brings the small (ojs, status, count) results back to the driver.
    results = rdd.map(lambda ojs: ingest_one(ojs, bronze_dir)).collect()

    # Summarise on the driver.
    ingested = [r for r in results if r[1] == "ingested"]
    skipped = [r for r in results if r[1] == "skipped"]
    missing = [r for r in results if r[1] == "missing"]
    total_notices = sum(r[2] for r in ingested)
    print(f"Editions ingested : {len(ingested)}  ({total_notices} notices)")
    print(f"Already present   : {len(skipped)}")
    print(f"No edition (404)  : {len(missing)}")
    print(f"Raw XML written to: {bronze_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest TED daily packages into a Databricks Volume using Spark."
    )
    parser.add_argument("--catalog", required=True, help="Unity Catalog catalog, e.g. main")
    parser.add_argument("--schema", required=True, help="Schema, e.g. ted")
    parser.add_argument("--volume", required=True, help="Volume name, e.g. raw")
    parser.add_argument("--year", type=int, required=True, help="OJ S year, e.g. 2026")
    parser.add_argument("--start", type=int, required=True, help="First OJ S edition number")
    parser.add_argument("--count", type=int, default=1, help="How many consecutive editions")
    parser.add_argument("--parallelism", type=int, default=8, help="Concurrent download tasks")
    args = parser.parse_args()

    # The Volume path. On Databricks, /Volumes/<catalog>/<schema>/<volume> is a
    # real, mounted filesystem path that both driver and executors can write to.
    bronze_dir = f"/Volumes/{args.catalog}/{args.schema}/{args.volume}/bronze" ## TODO: REPLACE WITH VOLUME_DESTINATION

    # In a Databricks notebook a `spark` session already exists; getOrCreate()
    # returns that one. Run as a script, it builds a fresh session.
    spark = SparkSession.builder.appName("ted-bronze-ingest").getOrCreate()

    ingest_range_spark(spark, args.start, args.count, args.year, bronze_dir, args.parallelism)


if __name__ == "__main__":
    main()
