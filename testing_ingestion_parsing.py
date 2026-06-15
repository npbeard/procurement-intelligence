"""test_one_document.py — end-to-end smoke test for ONE TED notice."""
import io
import tempfile
from pathlib import Path

from databricks.sdk import WorkspaceClient

import config
from scripts.bronze_ingest_spark import download_package, _iter_xml
from scripts.bronze_to_silver_spark import parse_bytes


YEAR, EDITION = 2026, 22                 # adjust if this edition wasn't published
ojs = f"{YEAR}{EDITION:05d}"
volume_dir = f"{config.RAW_XML_VOLUME}/ojs={ojs}"

w = WorkspaceClient()

# 1) DOWNLOAD one edition archive to local temp, grab the FIRST xml in it
tmp = Path(tempfile.mkdtemp())
archive = download_package(ojs, tmp)
assert archive is not None, f"No edition published for {ojs} — try another EDITION number"
filename, data = next(_iter_xml(archive))
print(f"1) DOWNLOADED  {filename}  ({len(data)} bytes)")

# 2) SAVE that one file into the Volume, then read it back to prove the write
dest = f"{volume_dir}/{filename}"
w.files.upload(dest, io.BytesIO(data), overwrite=True)
print(f"2) SAVED       {dest}")
roundtrip = w.files.download(dest).contents.read()
print(f"   verified    read back {len(roundtrip)} bytes from the Volume")

# 3) PARSE it — the SAME parser the Spark job uses, run locally on one file
parsed = parse_bytes(roundtrip, dest)
print("3) PARSED:")
for table in ["notices", "lots", "award_criteria", "organizations"]:
    print(f"   {table:15s} {len(parsed[table])} row(s)")
if parsed["errors"]:
    print("   errors:", parsed["errors"])
if parsed["notices"]:
    print("\n   notice row:", parsed["notices"][0])