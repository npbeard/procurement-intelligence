"""
Uploads locally downloaded Bronze packages to a Databricks Unity Catalog Volume.

Re-tars each package directory into a single archive and uploads via the
Databricks Files API — one upload per package instead of one per XML file.

After uploading, run extract_bronze.py in a Databricks notebook to unpack.

Usage:
    python -m ingestion.upload_to_volume
"""

import io
import os
import tarfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_HOST = os.getenv("DATABRICKS_HOST", "https://dbc-d86376d9-e045.cloud.databricks.com")
WORKSPACE_TOKEN = os.getenv("DATABRICKS_TOKEN")
LOCAL_BRONZE = os.getenv("LOCAL_BRONZE_PATH", "data/bronze/ted")
VOLUME_BRONZE = os.getenv("BRONZE_PATH", "/Volumes/capstone/ted/bronze")


def _tar_package_to_bytes(pkg_dir: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for xml in pkg_dir.glob("*.xml"):
            tf.add(xml, arcname=xml.name)
    return buf.getvalue()


def upload_package(client: WorkspaceClient, pkg_dir: Path) -> str:
    year_part = pkg_dir.parent.name
    pkg_part = pkg_dir.name
    volume_path = f"{VOLUME_BRONZE}/{year_part}/{pkg_part}.tar.gz"

    data = _tar_package_to_bytes(pkg_dir)
    client.files.upload(volume_path, io.BytesIO(data), overwrite=True)
    return f"[ok]   {pkg_dir.name} ({len(data) / 1024 / 1024:.1f} MB) → {volume_path}"


def upload_all(local_root: str = LOCAL_BRONZE, workers: int = 4):
    client = WorkspaceClient(host=WORKSPACE_HOST, token=WORKSPACE_TOKEN)

    pkg_dirs = sorted(Path(local_root).rglob("pkg=*"))
    if not pkg_dirs:
        print(f"No packages found under {local_root}")
        return

    print(f"Uploading {len(pkg_dirs)} packages to {VOLUME_BRONZE} ...")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(upload_package, client, d): d for d in pkg_dirs}
        for future in as_completed(futures):
            try:
                print(future.result())
            except Exception as e:
                print(f"[fail] {futures[future].name} — {e}")

    print("\nDone.")


if __name__ == "__main__":
    upload_all()
