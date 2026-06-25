"""
shred_batched.py — Stage 2 (local), tuned for ~400k files.

Same parsing as shred.py, but:
  * files are parsed in PARALLEL across all CPU cores (multiprocessing), and
  * results are flushed to DuckDB in BATCHES, so memory stays flat and you get
    live progress instead of waiting for one giant load at the end.

Cross-batch de-duplication is handled by a PRIMARY KEY on each table plus
INSERT OR IGNORE, so a notice seen twice is stored once.

Run:
    python shred_batched.py --bronze data/bronze --db data/silver.duckdb \
        --workers 8 --batch-size 5000
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import time
from pathlib import Path

import duckdb
import polars as pl
from lxml import etree

# --- Namespaces (unchanged) --------------------------------------------------
NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "efac": "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1",
    "efbc": "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1",
}


def _text(node, path: str) -> str | None:
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _num(node, path: str) -> float | None:
    raw = _text(node, path)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None



def parse_one(xml_path: Path) -> dict[str, list[dict]]:
    root = etree.parse(str(xml_path)).getroot()
    pub_id = _text(root, ".//efbc:NoticePublicationID")
    notice_type = etree.QName(root).localname

    notices = [{
        "notice_publication_id": pub_id,
        "notice_uuid": _text(root, "./cbc:ID"),
        "notice_type": notice_type,
        "subtype_code": _text(root, ".//efac:NoticeSubType/cbc:SubTypeCode"),
        "issue_date": _text(root, "./cbc:IssueDate"),
        "publication_date": _text(root, ".//efbc:PublicationDate"),
        "gazette_id": _text(root, ".//efbc:GazetteID"),
        "language": _text(root, "./cbc:NoticeLanguageCode"),
        "regulatory_domain": _text(root, "./cbc:RegulatoryDomain"),
        "buyer_org_ref": _text(
            root, "./cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID"
        ),
        "buyer_legal_type": _text(
            root, "./cac:ContractingParty/cac:ContractingPartyType/cbc:PartyTypeCode"
        ),
        "procurement_procedure": _text(root, "./cac:TenderingProcess/cbc:ProcedureCode"),
        "source_file": xml_path.name,
    }]

    # Build lot -> tenderer org_ref lookup (only present in CAN award notices).
    lot_tender: dict[str, str] = {}
    for lr in root.findall(".//efac:NoticeResult/efac:LotResult", NS):
        lot_ref = _text(lr, "./efac:TenderLot/cbc:ID")
        tender_ref = _text(lr, "./efac:LotTender/cbc:ID")
        if lot_ref and tender_ref:
            lot_tender[lot_ref] = tender_ref

    tender_tpa: dict[str, str] = {}
    for lt in root.findall(".//efac:NoticeResult/efac:LotTender", NS):
        tid = _text(lt, "./cbc:ID")
        tpa = _text(lt, "./efac:TenderingParty/cbc:ID")
        if tid and tpa:
            tender_tpa[tid] = tpa

    tpa_org: dict[str, str] = {}
    for tpa in root.findall(".//efac:NoticeResult/efac:TenderingParty", NS):
        tpa_id = _text(tpa, "./cbc:ID")
        org = _text(tpa, "./efac:Tenderer/cbc:ID")
        if tpa_id and org:
            tpa_org[tpa_id] = org

    lots: list[dict] = []
    award_criteria: list[dict] = []
    for lot in root.findall(".//cac:ProcurementProjectLot", NS):
        lot_id = _text(lot, "./cbc:ID")
        project = "./cac:ProcurementProject"
        tender_id = lot_tender.get(lot_id)
        tpa_id = tender_tpa.get(tender_id) if tender_id else None
        lots.append({
            "notice_publication_id": pub_id,
            "lot_id": lot_id,
            "name": _text(lot, f"{project}/cbc:Name"),
            "description": _text(lot, f"{project}/cbc:Description"),
            "procurement_type": _text(lot, f"{project}/cbc:ProcurementTypeCode"),
            "cpv_code": _text(
                lot, f"{project}/cac:MainCommodityClassification/cbc:ItemClassificationCode"
            ),
            "tenderer_org_ref": tpa_org.get(tpa_id) if tpa_id else None,
        })
        for i, crit in enumerate(lot.findall(".//cac:SubordinateAwardingCriterion", NS)):
            award_criteria.append({
                "notice_publication_id": pub_id,
                "lot_id": lot_id,
                "criterion_index": i,
                "criterion_type": _text(crit, "./cbc:AwardingCriterionTypeCode"),
                "description": _text(crit, "./cbc:Description"),
                "weight": _num(crit, ".//efbc:ParameterNumeric"),
                "weight_type": _text(crit, ".//efbc:ParameterCode"),
            })

    organizations: list[dict] = []
    for org in root.findall(".//efac:Organizations/efac:Organization", NS):
        company = "./efac:Company"
        organizations.append({
            "notice_publication_id": pub_id,
            "org_ref": _text(org, f"{company}/cac:PartyIdentification/cbc:ID"),
            "name": _text(org, f"{company}/cac:PartyName/cbc:Name"),
            "city": _text(org, f"{company}/cac:PostalAddress/cbc:CityName"),
            "country_code": _text(
                org, f"{company}/cac:PostalAddress/cac:Country/cbc:IdentificationCode"
            ),
            "company_id": _text(org, f"{company}/cac:PartyLegalEntity/cbc:CompanyID"),
            "website": _text(org, f"{company}/cbc:WebsiteURI"),
        })

    return {"notices": notices, "lots": lots,
            "award_criteria": award_criteria, "organizations": organizations}


def parse_one_safe(xml_path: Path):
    """Worker wrapper: never raises, so one bad file can't kill the pool.

    Returns (parsed_dict, None) on success, or (None, (filename, reason)) on error.
    """
    try:
        return parse_one(xml_path), None
    except Exception as exc:
        return None, (xml_path.name, f"{type(exc).__name__}: {exc}")


# --- Schemas + keys ----------------------------------------------------------
SCHEMAS: dict[str, dict] = {
    "notices": {
        "notice_publication_id": pl.Utf8, "notice_uuid": pl.Utf8,
        "notice_type": pl.Utf8, "subtype_code": pl.Utf8, "issue_date": pl.Utf8,
        "publication_date": pl.Utf8, "gazette_id": pl.Utf8, "language": pl.Utf8,
        "regulatory_domain": pl.Utf8, "buyer_org_ref": pl.Utf8,
        "buyer_legal_type": pl.Utf8, "procurement_procedure": pl.Utf8,
        "source_file": pl.Utf8,
    },
    "lots": {
        "notice_publication_id": pl.Utf8, "lot_id": pl.Utf8, "name": pl.Utf8,
        "description": pl.Utf8, "procurement_type": pl.Utf8, "cpv_code": pl.Utf8,
        "tenderer_org_ref": pl.Utf8,
    },
    "award_criteria": {
        "notice_publication_id": pl.Utf8, "lot_id": pl.Utf8,
        "criterion_index": pl.Int64, "criterion_type": pl.Utf8,
        "description": pl.Utf8, "weight": pl.Float64, "weight_type": pl.Utf8,
    },
    "organizations": {
        "notice_publication_id": pl.Utf8, "org_ref": pl.Utf8, "name": pl.Utf8,
        "city": pl.Utf8, "country_code": pl.Utf8, "company_id": pl.Utf8, "website": pl.Utf8,
    },
}

KEYS: dict[str, list[str]] = {
    "notices": ["notice_publication_id"],
    "lots": ["notice_publication_id", "lot_id"],
    "award_criteria": ["notice_publication_id", "lot_id", "criterion_index"],
    "organizations": ["notice_publication_id", "org_ref"],
}

# Map Polars types to DuckDB column types for the CREATE TABLE statements.
PL_TO_DUCK = {pl.Utf8: "VARCHAR", pl.Int64: "BIGINT", pl.Float64: "DOUBLE"}


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the four tables once, each with a PRIMARY KEY for cross-batch dedup."""
    for name, schema in SCHEMAS.items():
        cols = ", ".join(f"{c} {PL_TO_DUCK[t]}" for c, t in schema.items())
        pk = ", ".join(KEYS[name])
        con.execute(f"CREATE TABLE IF NOT EXISTS {name} ({cols}, PRIMARY KEY ({pk}))")


def flush(con: duckdb.DuckDBPyConnection, buckets: dict[str, list[dict]]) -> None:
    """Write one batch of accumulated rows into DuckDB, ignoring duplicates."""
    for name, rows in buckets.items():
        if not rows:
            continue
        df = (
            pl.DataFrame(rows, schema=SCHEMAS[name])
            .drop_nulls(subset=KEYS[name])      # a row needs a complete key
            .unique(subset=KEYS[name], keep="first")  # dedup within this batch
        )
        con.register("incoming", df)
        # INSERT OR IGNORE skips rows whose key already exists (dedup across batches).
        con.execute(f"INSERT OR IGNORE INTO {name} SELECT * FROM incoming")
        con.unregister("incoming")


def build_and_load(bronze_dir: Path, db_path: Path, workers: int, batch_size: int) -> None:
    """Parse all files in parallel and stream the rows into DuckDB in batches."""
    files = sorted(bronze_dir.rglob("*.xml"))
    total = len(files)
    print(f"Parsing {total} notices with {workers} workers, batch size {batch_size}...")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    create_tables(con)

    buckets: dict[str, list[dict]] = {name: [] for name in SCHEMAS}
    failures: list[tuple[str, str]] = []
    skipped_no_id = 0
    done = 0
    start = time.perf_counter()

    # imap_unordered streams results back as each worker finishes a file,
    # which keeps memory low and lets us flush in batches. chunksize batches
    # the hand-off to workers to cut inter-process overhead.
    with mp.Pool(workers) as pool:
        for parsed, err in pool.imap_unordered(parse_one_safe, files, chunksize=50):
            done += 1
            if err is not None:
                failures.append(err)
            elif not parsed["notices"][0]["notice_publication_id"]:
                skipped_no_id += 1
            else:
                for name, rows in parsed.items():
                    buckets[name].extend(rows)

            # Every batch_size files, write what we have and free the memory.
            if done % batch_size == 0:
                flush(con, buckets)
                buckets = {name: [] for name in SCHEMAS}
                rate = done / (time.perf_counter() - start)
                print(f"  {done:>7}/{total}   ({rate:,.0f} files/sec)")

    flush(con, buckets)  # write the final partial batch

    # Final report.
    elapsed = time.perf_counter() - start
    print(f"\nParsed {total} files in {elapsed:,.1f}s ({total / elapsed:,.0f} files/sec)")
    for name in SCHEMAS:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  {name:15s} {n:8d} rows")
    if skipped_no_id:
        print(f"  (skipped {skipped_no_id} notices with no publication ID)")
    if failures:
        log = db_path.parent / "parse_failures.log"
        log.write_text("\n".join(f"{f}\t{r}" for f, r in failures))
        print(f"  {len(failures)} file(s) failed; see {log}")
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Batched, parallel XML shredder.")
    parser.add_argument("--bronze", type=Path, default=Path("../data/bronze"))
    parser.add_argument("--db", type=Path, default=Path("../data/silver/database.duckdb"))
    parser.add_argument("--workers", type=int, default=mp.cpu_count(),
                        help="parallel processes (default: all CPU cores)")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="files per DuckDB flush")
    args = parser.parse_args()
    build_and_load(args.bronze, args.db, args.workers, args.batch_size)


if __name__ == "__main__":          # required: multiprocessing needs this guard
    main()
