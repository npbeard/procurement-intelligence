"""
Download TED daily packages into the Bronze layer.

Each package is a ZIP of eForms XML notices published that day.
XMLs are extracted and stored as-is — no parsing happens here.

Bronze layout:
    <BRONZE_PATH>/year=<year>/pkg=<nnnnn>/<notice>.xml

Usage:
    python -m ingestion.ted_downloader --year 2026 --start 1 --end 50
"""

import os
import time
import tarfile
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TED_BASE_URL = "https://ted.europa.eu/packages/daily"
BRONZE_PATH = os.getenv("BRONZE_PATH", "data/bronze/ted")


def _pkg_dir(output_root: str, year: int, pkg_num: int) -> Path:
    return Path(output_root) / f"year={year}" / f"pkg={pkg_num:05d}"


def download_package(year: int, pkg_num: int, output_root: str = BRONZE_PATH) -> bool:
    dest_dir = _pkg_dir(output_root, year, pkg_num)

    if dest_dir.exists() and any(dest_dir.glob("*.xml")):
        print(f"[skip] {year}{pkg_num:05d} — already present")
        return False

    url = f"{TED_BASE_URL}/{year}{pkg_num:05d}"
    r = requests.get(url, timeout=120)

    if r.status_code == 404:
        print(f"[miss] {year}{pkg_num:05d} — not published")
        return False

    r.raise_for_status()

    if len(r.content) == 0:
        print(f"[warn] {year}{pkg_num:05d} — empty response, skipping")
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)
    tar_path = dest_dir / "_package.tar.gz"
    tar_path.write_bytes(r.content)

    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            xml_members = [m for m in tf.getmembers() if m.name.endswith(".xml")]
            for member in xml_members:
                member.name = Path(member.name).name
                tf.extract(member, dest_dir, filter="data")
    except (tarfile.ReadError, tarfile.TarError) as e:
        print(f"[warn] {year}{pkg_num:05d} — tar error ({e}), skipping")
        tar_path.unlink(missing_ok=True)
        return False

    tar_path.unlink()
    print(f"[ok]   {year}{pkg_num:05d} — {len(xml_members)} notices → {dest_dir}")
    return True


def download_range(year: int, start: int, end: int, output_root: str = BRONZE_PATH, delay: float = 2.0) -> int:
    downloaded = 0
    for pkg_num in range(start, end + 1):
        if download_package(year, pkg_num, output_root):
            downloaded += 1
        time.sleep(delay)
    print(f"\nDone — {downloaded} new packages downloaded.")
    return downloaded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest TED daily packages into Bronze layer")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--start", type=int, required=True, help="First package number (e.g. 1)")
    parser.add_argument("--end", type=int, required=True, help="Last package number (e.g. 90)")
    parser.add_argument("--output", default=BRONZE_PATH, help="Override BRONZE_PATH")
    args = parser.parse_args()

    download_range(args.year, args.start, args.end, args.output)
