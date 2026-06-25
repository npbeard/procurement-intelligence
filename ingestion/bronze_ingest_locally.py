"""
bronze_ingest.py — Stage 1 of the local TED data lake.

Downloads TED daily XML "packages" (one archive per day) and stores the raw,
untouched notices in the bronze layer as individual .xml files.

Run examples:
    python bronze_ingest.py --year 2026 --start 22 --count 1     # one day
    python bronze_ingest.py --year 2026 --start 22 --count 180   # bulk backfill
"""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path

import requests

# --- Configuration -----------------------------------------------------------

TED_DAILY_URL = "https://ted.europa.eu/packages/daily/{ojs}"

BRONZE_DIR = Path("../data/bronze")     # raw .xml files live here
LANDING_DIR = Path("../data/extracted")   # archives land here briefly before extraction


def build_package_url(ojs_number: str) -> str:
    """Turn an OJ S edition number like '202600022' into its download URL."""
    return TED_DAILY_URL.format(ojs=ojs_number)


def download_package(ojs_number: str, landing_dir: Path = LANDING_DIR) -> Path | None:
    """
    Download one daily package archive from TED.

    Returns the path to the saved archive, or None if no edition was published
    for that number (TED returns a 404 on non-publishing days).
    """
    landing_dir.mkdir(parents=True, exist_ok=True)
    url = build_package_url(ojs_number)
    archive_path = landing_dir / f"{ojs_number}.archive"

    # stream=True downloads the file in pieces instead of holding it all in memory.
    with requests.get(url, stream=True, timeout=60) as response:
        if response.status_code == 404:
            print(f"  [skip] OJ S {ojs_number}: no edition published")
            return None
        response.raise_for_status()  # turn any other bad status into an error

        with open(archive_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    print(f"  [ok]   downloaded {archive_path.name}")
    return archive_path


def extract_package(archive_path: Path, dest_dir: Path) -> int:
    """
    Extract every .xml file from the archive into dest_dir (flattened, no
    sub-folders). Handles both .tar.gz and .zip. Returns the count of files written.
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
                    (dest_dir / Path(member.name).name).write_bytes(zf.read(name))
                    count += 1
    else:
        raise ValueError(f"{archive_path} is neither a tar nor a zip archive")

    return count


def ingest_one(ojs_number: int, bronze_dir: Path = BRONZE_DIR) -> int:
    """
    Full bronze step for ONE edition: skip if we already have it, otherwise
    download + extract + clean up. Returns the number of notices ingested.
    """
    target_dir = bronze_dir / f"ojs={ojs_number}"

    # Idempotency: if this edition is already on disk, don't download it again.
    if target_dir.exists() and any(target_dir.glob("*.xml")):
        print(f"  [have] OJ S {ojs_number} already in bronze, skipping")
        return 0

    archive_path = download_package(ojs_number)
    if archive_path is None:
        return 0

    n = extract_package(archive_path, target_dir)
    archive_path.unlink()  # we keep the raw XML, not the archive
    print(f"  [done] OJ S {ojs_number}: {n} notices -> {target_dir}")
    return n


def ingest_range(start_ojs: int, count: int, year: int) -> None:
    """Bulk mode: ingest `count` consecutive editions starting at start_ojs."""
    total = 0
    for i in range(count):
        edition = start_ojs + i
        ojs_number = f"{year}{edition:05d}"  # 2026 + 22 -> '202600022'
        print(f"OJ S {edition}/{year}:")
        total += ingest_one(int(ojs_number))
    print(f"\nFinished. {total} notices ingested into {BRONZE_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest TED daily packages into the bronze layer."
    )
    parser.add_argument("--year", type=int, required=True, help="OJ S year, e.g. 2026")
    parser.add_argument("--start", type=int, required=True, help="First OJ S edition number, e.g. 22")
    parser.add_argument("--count", type=int, default=1, help="How many consecutive editions to fetch")
    args = parser.parse_args()

    ingest_range(args.start, args.count, args.year)


if __name__ == "__main__":
    main()
