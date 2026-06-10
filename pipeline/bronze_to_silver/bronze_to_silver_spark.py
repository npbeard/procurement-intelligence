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

import argparse

from lxml import etree
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DoubleType, LongType, StringType, StructField, StructType,
)

from databricks.sdk import WorkspaceClient

w = WorkspaceClient(
    host="https://<your-workspace>.cloud.databricks.com", ## TODO: INSERT THE WORKSPACE
    token="<your-personal-access-token>",                 ## TODO: INSERT THE PERSONAL TOKEN
)

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
        "source_file": source.rsplit("/", 1)[-1],
    })

    for lot in root.findall(".//cac:ProcurementProjectLot", NS):
        lot_id = _text(lot, "./cbc:ID")
        project = "./cac:ProcurementProject"
        out["lots"].append({
            "notice_publication_id": pub_id,
            "lot_id": lot_id,
            "name": _text(lot, f"{project}/cbc:Name"),
            "description": _text(lot, f"{project}/cbc:Description"),
            "procurement_type": _text(lot, f"{project}/cbc:ProcurementTypeCode"),
            "cpv_code": _text(
                lot, f"{project}/cac:MainCommodityClassification/cbc:ItemClassificationCode"
            ),
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
        StructField("source_file", StringType()),
    ]),
    "lots": StructType([
        StructField("notice_publication_id", StringType()),
        StructField("lot_id", StringType()),
        StructField("name", StringType()),
        StructField("description", StringType()),
        StructField("procurement_type", StringType()),
        StructField("cpv_code", StringType()),
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


def build_table_dataframes(spark: SparkSession, bronze_dir: str) -> dict:
    """Read every XML in the Volume, parse in parallel, return 4 Spark DataFrames."""
    # binaryFile reads each file as a row with columns: path, content (bytes).
    # recursiveFileLookup walks the ojs=... sub-folders.
    files = (
        spark.read.format("binaryFile")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "*.xml")
        .load(bronze_dir)
    )
    print(f"Found {files.count()} XML files in {bronze_dir}")

    # Parse every file. .cache() keeps the parsed result in memory so the four
    # flatMaps below don't re-parse the same files four times.
    parsed = files.select("path", "content").rdd.map(
        lambda row: parse_bytes(bytes(row["content"]), row["path"])
    )
    parsed.cache()

    tables: dict = {}
    for name in TABLE_NAMES:
        # flatMap pulls out this table's rows from every file's result, then we
        # turn each dict into a tuple in schema order (the most reliable way to
        # hand typed rows to Spark).
        fields = [f.name for f in SCHEMAS[name].fields]
        rows = (
            parsed.flatMap(lambda d, n=name: d[n])
            .map(lambda r, fs=fields: tuple(r[f] for f in fs))
        )
        df = spark.createDataFrame(rows, SCHEMAS[name]).dropDuplicates(KEYS[name])
        tables[name] = df
        print(f"  {name:15s} {df.count():6d} rows")

    # Collect the (small) list of parse failures back to the driver and report.
    errors = parsed.flatMap(lambda d: d["errors"]).collect()
    if errors:
        print(f"\n{len(errors)} file(s) skipped or failed:")
        for src, reason in errors[:10]:
            print(f"  - {src.rsplit('/', 1)[-1]}: {reason}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    return tables


def write_delta(tables: dict, target: str, writing_mode: str = "overwrite") -> None:
    """Write each DataFrame as a managed Delta table at <catalog>.<schema>.<name>."""
    for name, df in tables.items():
        full_name = f"{target}.{name}"
        (
            df.write.format("delta")
            .mode(writing_mode)                  #  the table each run
            .option("overwriteSchema", "true")  # allow column changes between runs
            .saveAsTable(full_name)
        )
        print(f"  wrote {full_name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shred bronze XML from a Volume into silver Delta tables."
    )
    parser.add_argument(
        "--bronze", default="/Volumes/main/ted/raw/bronze", #TODO: REPLEACE WITH PATH WHERE TO READ
        help="Volume path holding the raw .xml files",
    )
    parser.add_argument(
        "--target", default="main.ted_silver",
        help="Destination as <catalog>.<schema> for the four Delta tables", # TODO: REPLACE WITH THE PATH WHERE THE DATAWAREHOUSE LIVE
    )
    args = parser.parse_args()

    spark = SparkSession.builder.appName("ted-bronze-to-silver").getOrCreate()

    # Make sure the destination schema exists before writing into it.
    catalog, schema = args.target.split(".")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    tables = build_table_dataframes(spark, args.bronze)
    write_delta(tables, args.target)
    print(f"\nDone. Four Delta tables updated under {args.target}")


if __name__ == "__main__":
    main()
