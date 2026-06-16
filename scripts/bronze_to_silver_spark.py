"""
bronze_to_silver_spark.py — Stage 2 (Databricks / Spark version).

Reads the raw .xml notices from a Unity Catalog Volume, parses the nested
eForms structure with lxml (in parallel across the cluster), builds four
relational Spark DataFrames, and writes them as Delta tables in a catalog
(the silver layer of your Databricks data warehouse).

The parsing logic is identical to the local version — only the orchestration
(reading files, distributing the work, and writing the output) is Spark.

Run as a Databricks job (Python file task) or in a notebook:
    bronze_to_silver_spark.py --bronze /Volumes/main/ted/raw/bronze \
                              --target main.ted_silver
"""

from __future__ import annotations
import sys
from pathlib import Path

import argparse

from lxml import etree
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DoubleType, LongType, StringType, StructField, StructType,
)

import json
import pandas as pd
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from config import get_spark

from tqdm.auto import tqdm

TMP_PARSED = "tmp_parsed_records"

# --- Namespaces (unchanged from the local version) ---------------------------
NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "efac": "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1",
    "efbc": "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1",
}

TABLE_NAMES = ["notices", "lots", "award_criteria", "organizations"]


# --- Small extraction helpers (unchanged) ------------------------------------
def _text(node, path: str) -> str | None:
    """Find ONE element at `path` under `node` and return its stripped text, or None."""
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _num(node, path: str) -> float | None:
    """Same as _text, but convert the value to a float (for weights)."""
    raw = _text(node, path)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
    

def _attr(node, path: str, attr: str) -> str | None:
    """Find ONE element at `path` and return one of its attributes (e.g. currencyID)."""
    found = node.find(path, NS)
    if found is None:
        return None
    value = found.get(attr)
    return value.strip() if value else None


# --- Per-file parsing --------------------------------------------------------
def parse_bytes(content: bytes, source: str) -> dict[str, list]:
    """Parse ONE notice (given its raw bytes) into rows for all four tables.

    This is the old parse_one, with two changes for Spark:
      * it reads from bytes (etree.fromstring) because Spark hands us file
        *content*, not paths;
      * errors are captured in an "errors" list instead of raised, so a single
        bad file can't kill the distributed job.
    """
    out: dict[str, list] = {name: [] for name in TABLE_NAMES}
    out["errors"] = []

    try:
        root = etree.fromstring(content)
    except Exception as exc:
        out["errors"].append((source, f"{type(exc).__name__}: {exc}"))
        return out

    pub_id = _text(root, ".//efbc:NoticePublicationID")
    if not pub_id:                       # no key to join on -> skip, but record it
        out["errors"].append((source, "no publication id"))
        return out

    notice_type = etree.QName(root).localname

    out["notices"].append({
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
        # Notice-level money. Two distinct figures that can both be absent:
        #   estimated_* = the overall estimated contract value (root project)
        #   total_*     = the actual total awarded value (efac:NoticeResult)
        "estimated_value": _num(
            root, "./cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount"
        ),
        "estimated_currency": _attr(
            root,
            "./cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount",
            "currencyID",
        ),
        "total_value": _num(root, ".//efac:NoticeResult/cbc:TotalAmount"),
        "total_currency": _attr(root, ".//efac:NoticeResult/cbc:TotalAmount", "currencyID"),
        "source_file": source.rsplit("/", 1)[-1],
    })

    lot_status: dict[str, str | None] = {}
    for lr in root.findall(".//efac:LotResult", NS):
        ref = _text(lr, "./efac:TenderLot/cbc:ID")
        if ref:
            lot_status[ref] = _text(lr, "./cbc:TenderResultCode")

    # Build lot -> tenderer org_ref lookup (only present in CAN award notices).
    # Chain: LotResult(lot_id -> tender_id) -> LotTender(tender_id -> tpa_id)
    #        -> TenderingParty(tpa_id -> org_ref)
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

    for lot in root.findall(".//cac:ProcurementProjectLot", NS):
        lot_id = _text(lot, "./cbc:ID")
        project = "./cac:ProcurementProject"
        amount_path = f"{project}/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount"
        deadline = "./cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod"
        tender_id = lot_tender.get(lot_id)
        tpa_id = tender_tpa.get(tender_id) if tender_id else None
        out["lots"].append({
            "notice_publication_id": pub_id,
            "lot_id": lot_id,
            "name": _text(lot, f"{project}/cbc:Name"),
            "description": _text(lot, f"{project}/cbc:Description"),
            "procurement_type": _text(lot, f"{project}/cbc:ProcurementTypeCode"),
            "cpv_code": _text(
                lot, f"{project}/cac:MainCommodityClassification/cbc:ItemClassificationCode"
            ),
            "value": _num(lot, amount_path),
            "currency": _attr(lot, amount_path, "currencyID"),
            "status": lot_status.get(lot_id),
            "submission_deadline_date": _text(lot, f"{deadline}/cbc:EndDate"),
            "submission_deadline_time": _text(lot, f"{deadline}/cbc:EndTime"),
            "tenderer_org_ref": tpa_org.get(tpa_id) if tpa_id else None,
        })
        for i, crit in enumerate(lot.findall(".//cac:SubordinateAwardingCriterion", NS)):
            out["award_criteria"].append({
                "notice_publication_id": pub_id,
                "lot_id": lot_id,
                "criterion_index": i,
                "criterion_type": _text(crit, "./cbc:AwardingCriterionTypeCode"),
                "description": _text(crit, "./cbc:Description"),
                "weight": _num(crit, ".//efbc:ParameterNumeric"),
                "weight_type": _text(crit, ".//efbc:ParameterCode"),
            })

    for org in root.findall(".//efac:Organizations/efac:Organization", NS):
        company = "./efac:Company"
        out["organizations"].append({
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

    return out


# --- Spark table schemas + keys ----------------------------------------------
# Same columns/types as the Polars version, expressed as Spark StructTypes.
SCHEMAS: dict[str, StructType] = {
    "notices": StructType([
        StructField("notice_publication_id", StringType()),
        StructField("notice_uuid", StringType()),
        StructField("notice_type", StringType()),
        StructField("subtype_code", StringType()),
        StructField("issue_date", StringType()),
        StructField("publication_date", StringType()),
        StructField("gazette_id", StringType()),
        StructField("language", StringType()),
        StructField("regulatory_domain", StringType()),
        StructField("buyer_org_ref", StringType()),
        StructField("buyer_legal_type", StringType()),
        StructField("procurement_procedure", StringType()),
        StructField("estimated_value", DoubleType()),
        StructField("estimated_currency", StringType()),
        StructField("total_value", DoubleType()),
        StructField("total_currency", StringType()),
        StructField("source_file", StringType()),
    ]),
    "lots": StructType([
        StructField("notice_publication_id", StringType()),
        StructField("lot_id", StringType()),
        StructField("name", StringType()),
        StructField("description", StringType()),
        StructField("procurement_type", StringType()),
        StructField("cpv_code", StringType()),
        StructField("value", DoubleType()),
        StructField("currency", StringType()),
        StructField("status", StringType()),
        StructField("submission_deadline_date", StringType()),
        StructField("submission_deadline_time", StringType()),
        StructField("tenderer_org_ref", StringType()),
    ]),
    "award_criteria": StructType([
        StructField("notice_publication_id", StringType()),
        StructField("lot_id", StringType()),
        StructField("criterion_index", LongType()),
        StructField("criterion_type", StringType()),
        StructField("description", StringType()),
        StructField("weight", DoubleType()),
        StructField("weight_type", StringType()),
    ]),
    "organizations": StructType([
        StructField("notice_publication_id", StringType()),
        StructField("org_ref", StringType()),
        StructField("name", StringType()),
        StructField("city", StringType()),
        StructField("country_code", StringType()),
        StructField("company_id", StringType()),
        StructField("website", StringType()),
    ]),
}

KEYS: dict[str, list[str]] = {
    "notices": ["notice_publication_id"],
    "lots": ["notice_publication_id", "lot_id"],
    "award_criteria": ["notice_publication_id", "lot_id", "criterion_index"],
    "organizations": ["notice_publication_id", "org_ref"],
}

# One row per parsed record: which table it belongs to + the record as JSON.
PARSE_OUTPUT_SCHEMA = StructType([
    StructField("table", StringType()),
    StructField("data",  StringType()),
])

def _parse_partition(iterator):
    """Runs on the cluster. Calls the UNCHANGED parse_bytes per file."""
    for pdf in iterator:                       # columns: path, content
        records = []
        for path, content in zip(pdf["path"], pdf["content"]):
            out = parse_bytes(bytes(content), path)
            for name in TABLE_NAMES:
                for row in out[name]:
                    records.append((name, json.dumps(row)))
            for src, reason in out["errors"]:
                records.append(("__error__",
                                json.dumps({"source": src, "reason": reason})))
        yield pd.DataFrame(records, columns=["table", "data"])

def list_xml_paths(spark, raw_volume):
    """Cheap listing of all XML paths (selecting only `path` skips reading bytes)."""
    df = (
        spark.read.format("binaryFile")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "*.xml")
        .load(raw_volume)
        .select("path")
    )
    return [r["path"] for r in df.collect()]


def already_parsed_files(spark, target):
    """Filenames already present in the notices table (the 'done' marker)."""
    tbl = f"{target}.notices"
    if not spark.catalog.tableExists(tbl):
        return set()
    return {
        r["source_file"]
        for r in spark.table(tbl).select("source_file").distinct().collect()
    }

def _parse_paths_to_tables(spark, paths: list[str]) -> dict:
    """Load + parse ONE batch of file paths on the driver, return per-table DataFrames."""
    files = (
        spark.read.format("binaryFile")
        .load(paths)
        .select("path", "content")
    )

    # Parse on the driver (has lxml, no UDF sandbox). Use collect() rather than
    # toLocalIterator(): on serverless (Spark Connect), toLocalIterator() holds
    # a server-side streaming execute handle open across the whole loop, and
    # the per-row lxml parsing here is slow enough that the gaps between row
    # fetches exceed the server's inactivity timeout, killing the handle with
    # INVALID_HANDLE.OPERATION_ABANDONED. collect() fetches the batch's file
    # content in one RPC, so parsing afterwards never touches Spark Connect.
    rows = files.collect()
    bucket = {name: [] for name in TABLE_NAMES}
    errors = []
    for row in tqdm(rows, total=len(rows), desc="Parsing", unit="file"):
        out = parse_bytes(bytes(row["content"]), row["path"])
        for name in TABLE_NAMES:
            bucket[name].extend(out[name])
        errors.extend(out["errors"])

    tables = {}
    for name in TABLE_NAMES:
        rows = [tuple(r.get(f.name) for f in SCHEMAS[name].fields) for r in bucket[name]]
        df = spark.createDataFrame(rows, SCHEMAS[name]).dropDuplicates(KEYS[name])
        tables[name] = df
        tqdm.write(f"  {name:15s} {df.count():6d} new rows")

    if errors:
        tqdm.write(f"\n{len(errors)} file(s) skipped or failed (first few):")
        for src, reason in errors[:10]:
            tqdm.write(f"  - {src.rsplit('/', 1)[-1]}: {reason}")
    return tables


def write_delta(tables: dict, target: str, writing_mode: str = "overwrite") -> None:
    """Append each DataFrame to <catalog>.<schema>.<name>. Notices written LAST."""
    # notices is the 'done' marker, so commit it only after the child tables.
    order = [n for n in tables if n != "notices"]
    if "notices" in tables:
        order.append("notices")

    for name in tqdm(order, total=len(order), desc="Writing Delta", unit="table"):
        full_name = f"{target}.{name}"
        (
            tables[name].write.format("delta")
            .mode(writing_mode)
            .option("mergeSchema", "true")
            .saveAsTable(full_name)
        )
        tqdm.write(f"  wrote {full_name}")


def parse_and_write_incremental(spark, raw_volume: str, target: str,
                                 batch_size: int = 500) -> None:
    """
    Parse new XML files in bounded-size batches, writing each batch to Delta
    before moving to the next. Parsing happens on the driver (lxml, no UDF
    sandbox), so without batching, a large backlog holds every parsed record
    for every new file in driver memory at once — this is what made the
    ~115-edition backlog crash with an opaque platform error after 100+
    minutes. Batching bounds that memory use and checkpoints progress:
    notices are written last within each batch, so a crash mid-run only
    re-parses the batch in flight, not files already committed earlier.
    """
    all_paths = list_xml_paths(spark, raw_volume)
    done = already_parsed_files(spark, target)
    new_paths = [p for p in all_paths if p.rsplit("/", 1)[-1] not in done]

    print(f"{len(all_paths)} files in volume | {len(done)} already parsed "
          f"| {len(new_paths)} new to process")
    if not new_paths:
        print("Nothing new to parse — tables are up to date.")
        return

    batches = [new_paths[i:i + batch_size] for i in range(0, len(new_paths), batch_size)]
    print(f"Processing in {len(batches)} batch(es) of up to {batch_size} files")

    for i, batch_paths in enumerate(batches, start=1):
        print(f"\n--- Batch {i}/{len(batches)} ({len(batch_paths)} files) ---")
        tables = _parse_paths_to_tables(spark, batch_paths)
        write_delta(tables, target, writing_mode="append")

    print(f"\nDone. Processed {len(new_paths)} new file(s) in {len(batches)} batch(es).")


def main() -> None:
    p = argparse.ArgumentParser(description="Incrementally shred new bronze XML into Delta.")
    p.add_argument("--raw-volume", default=config.RAW_XML_VOLUME)
    p.add_argument("--target", default=config.PARSED_TARGET)
    p.add_argument("--batch-size", type=int, default=500,
                   help="Max files parsed and written per batch (bounds driver memory).")
    args = p.parse_args()

    spark = get_spark()
    catalog, schema = args.target.split(".")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    parse_and_write_incremental(spark, args.raw_volume, args.target, args.batch_size)

if __name__ == "__main__":
    main()
