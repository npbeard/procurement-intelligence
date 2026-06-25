"""
bronze_ingest_spark.py — Stage 1 (Databricks-connected).

Downloads TED daily XML packages and uploads the raw notices into a Unity
Catalog Volume via the Databricks SDK Files API.

CLI:      python bronze_ingest_spark.py --year 2026 --start 22 --count 180
Notebook: from bronze_ingest_spark import ingest_range
          ingest_range(start=22, count=180, year=2026)
"""
from __future__ import annotations
import sys 
from pathlib import Path

import argparse
import io
import shutil
import tarfile
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient

import threading
from datetime import datetime, timezone
from tqdm.auto import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # sets auth env vars + paths on import

TED_DAILY_URL = "https://ted.europa.eu/packages/daily/{ojs}"

# Structuring the URL for the specific ojs
def build_package_url(ojs_number: str) -> str:
    return TED_DAILY_URL.format(ojs=ojs_number)

# Call the API to get the files 
def download_package(ojs_number: str, landing_dir: Path) -> Path | None:
    landing_dir.mkdir(parents=True, exist_ok=True)
    archive_path = landing_dir / f"{ojs_number}.archive"
    with requests.get(build_package_url(ojs_number), stream=True, timeout=60) as resp:
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        with open(archive_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    return archive_path

# Decompress the files to get all XML files 
def _iter_xml(archive_path: Path):
    """Yield (filename, bytes) for every .xml in the archive (tar or zip)."""
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tar:
            for m in tar.getmembers():
                if m.isfile() and m.name.endswith(".xml"):
                    yield Path(m.name).name, tar.extractfile(m).read()
    elif zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    yield Path(name).name, zf.read(name)
    else:
        raise ValueError(f"{archive_path} is neither a tar nor a zip archive")

# Check if the ojs was already downloaded to avoid downloading it again
def _volume_dir_has_files(w: WorkspaceClient, volume_dir: str) -> bool:
    """Idempotency: does this ojs= folder already exist with content?"""
    try:
        return len(list(w.files.list_directory_contents(volume_dir))) > 0
    except Exception:
        return False  # folder not created yet

# Write the xml files into the specific volume in databrikcs
def ingest_one(ojs_number, raw_volume, w, on_file=None, upload_workers=32):
    target_dir = f"{raw_volume}/ojs={ojs_number}"
    if _volume_dir_has_files(w, target_dir):
        return (ojs_number, "skipped", 0)

    tmp = Path(tempfile.mkdtemp())
    try:
        archive_path = download_package(ojs_number, tmp)
        if archive_path is None:
            return (ojs_number, "missing", 0)
        items = list(_iter_xml(archive_path))

        def up(item):
            filename, data = item
            w.files.upload(f"{target_dir}/{filename}", io.BytesIO(data), overwrite=True)
            if on_file:
                on_file()

        with ThreadPoolExecutor(max_workers=upload_workers) as pool:
            list(pool.map(up, items))
        return (ojs_number, "ingested", len(items))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def latest_ingested_edition(w: WorkspaceClient, raw_volume: str) -> tuple[int, int] | None:
    """Highest (year, seq) among existing ojs= folders in the Volume, or None if empty."""
    editions = []
    for entry in w.files.list_directory_contents(raw_volume):
        name = entry.path.rstrip("/").rsplit("/", 1)[-1]  # "ojs=202600001"
        if name.startswith("ojs=") and name[4:].isdigit() and len(name) >= 10:
            num = name[4:]
            editions.append((int(num[:4]), int(num[4:])))
    return max(editions) if editions else None


def ingest_latest(raw_volume: str = config.RAW_XML_VOLUME,
                   max_consecutive_misses: int = 10,
                   hard_cap: int = 260,
                   batch_size: int = 10) -> None:
    """
    Resume from the latest edition already in the Volume and ingest every
    edition published since, up through today. Editions within a batch are
    fetched concurrently. TED publishes on business days only, so a run of
    `max_consecutive_misses` 404s (in submission order) is treated as
    "caught up" rather than an error.
    """
    w = WorkspaceClient()
    last = latest_ingested_edition(w, raw_volume)
    today_year = datetime.now(timezone.utc).year

    if last is None:
        year, seq = today_year, 1
    else:
        year, seq = last
        seq += 1
        if year < today_year:
            year, seq = today_year, 1  # roll over into the new year's numbering

    consecutive_misses = 0
    attempts = 0
    ingested_editions = 0
    ingested_notices = 0

    while consecutive_misses < max_consecutive_misses and attempts < hard_cap:
        batch = range(seq, seq + min(batch_size, hard_cap - attempts))
        ojs_numbers = [f"{year}{s:05d}" for s in batch]

        with ThreadPoolExecutor(max_workers=len(ojs_numbers)) as pool:
            results = list(pool.map(
                lambda o: ingest_one(o, raw_volume, w, upload_workers=8), ojs_numbers
            ))

        for ojs_number, status, n in results:
            print(f"{ojs_number}: {status} ({n} notices)")
            attempts += 1
            if status == "missing":
                consecutive_misses += 1
            else:
                consecutive_misses = 0
                if status == "ingested":
                    ingested_editions += 1
                    ingested_notices += n
            if consecutive_misses >= max_consecutive_misses:
                break

        seq += len(ojs_numbers)

    print(f"\nDone. Ingested {ingested_editions} new edition(s), "
          f"{ingested_notices} notices, into {raw_volume}.")


def ingest_range(start: int, count: int, year: int,
                 raw_volume: str = config.RAW_XML_VOLUME,
                 parallelism: int = 8) -> None:
    w = WorkspaceClient()  # auth from env / ~/.databrickscfg (set via config import)
    ojs_numbers = [f"{year}{(start + i):05d}" for i in range(count)]

    pbar = tqdm(unit="file", desc="Ingesting XML")   # no total = live count-up
    lock = threading.Lock()

    def bump():
        with lock:
            pbar.update(1)

    def run(o):
        return ingest_one(o, raw_volume, w, on_file=bump)

    with ThreadPoolExecutor(max_workers=parallelism) as pool:
        results = list(pool.map(run, ojs_numbers))

    pbar.close()

    ingested = [r for r in results if r[1] == "ingested"]
    skipped  = [r for r in results if r[1] == "skipped"]
    missing  = [r for r in results if r[1] == "missing"]
    print(f"Editions ingested : {len(ingested)}  ({sum(r[2] for r in ingested)} notices)")
    print(f"Already present   : {len(skipped)}")
    print(f"No edition (404)  : {len(missing)}")
    print(f"Raw XML written to: {raw_volume}")


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest TED daily packages into a Volume (RDD-free).")
    p.add_argument("--latest", action="store_true",
                   help="Resume from the latest edition in the Volume and catch up to today.")
    p.add_argument("--year", type=int)
    p.add_argument("--start", type=int)
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--parallelism", type=int, default=8)
    p.add_argument("--raw-volume", default=config.RAW_XML_VOLUME)
    args = p.parse_args()

    if args.latest:
        ingest_latest(args.raw_volume)
    else:
        if args.year is None or args.start is None:
            p.error("--year and --start are required unless --latest is set")
        ingest_range(args.start, args.count, args.year, args.raw_volume, args.parallelism)


if __name__ == "__main__":
    main()