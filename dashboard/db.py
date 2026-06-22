"""
dashboard/db.py — Databricks SQL connector for the Streamlit dashboard.

Uses databricks-sql-connector (not Spark/Databricks Connect) so queries run
against the serverless SQL Warehouse and return in under a second. Results are
cached per Streamlit session so page re-renders never re-query Databricks.

Required env vars (already in .env):
    DATABRICKS_HOST        e.g. https://dbc-xxxx.cloud.databricks.com
    DATABRICKS_TOKEN       personal access token
    DATABRICKS_HTTP_PATH   e.g. /sql/1.0/warehouses/<id>
"""
from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

load_dotenv()

_HOST = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
_TOKEN = os.environ["DATABRICKS_TOKEN"]
_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]

CATALOG = "capstone"
SCHEMA = "ted"


def _connect():
    return sql.connect(
        server_hostname=_HOST,
        http_path=_HTTP_PATH,
        access_token=_TOKEN,
    )


@st.cache_data(ttl=300, show_spinner="Loading data…")
def query(sql_str: str) -> pd.DataFrame:
    """Run a SQL query against the Databricks SQL Warehouse and return a DataFrame."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_str)
            return cur.fetchall_arrow().to_pandas()


# ---------------------------------------------------------------------------
# Pre-built query helpers — one function per logical dataset
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def notices_summary() -> dict:
    """Top-level counts and totals across all notices."""
    df = query(f"""
        SELECT
            COUNT(DISTINCT notice_publication_id)                         AS total_notices,
            COUNT(DISTINCT buyer_country_code)                            AS countries,
            ROUND(SUM(lot_value_eur) / 1e6, 1)                           AS total_value_m,
            ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT notice_publication_id), 0), 1)
                                                                          AS avg_lots_per_notice
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
    """)
    return df.iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def cn_summary() -> dict:
    """Counts/totals for open contract notices (CN)."""
    df = query(f"""
        SELECT
            COUNT(DISTINCT notice_publication_id) AS open_tenders,
            COUNT(DISTINCT buyer_country_code)    AS countries,
            ROUND(SUM(lot_value_eur) / 1e6, 1)   AS total_value_m,
            ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT notice_publication_id), 0), 1)
                                                  AS avg_lots_per_tender
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE notice_type = 'ContractNotice'
    """)
    return df.iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def can_summary() -> dict:
    """Counts/totals for contract award notices (CAN)."""
    df = query(f"""
        SELECT
            COUNT(DISTINCT notice_publication_id)  AS awards,
            COUNT(DISTINCT buyer_country_code)     AS countries,
            ROUND(SUM(lot_value_eur) / 1e6, 1)    AS total_awarded_m,
            ROUND(AVG(lot_value_eur) / 1e3, 0)    AS avg_award_k
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE notice_type = 'ContractAwardNotice'
    """)
    return df.iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def top_countries_by_notices(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT buyer_country_code AS country,
               COUNT(DISTINCT notice_publication_id) AS notices
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE buyer_country_code IS NOT NULL
        GROUP BY buyer_country_code
        ORDER BY notices DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def top_countries_by_award_value(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT buyer_country_code                     AS country,
               ROUND(SUM(lot_value_eur) / 1e6, 2)   AS awarded_m
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE notice_type = 'ContractAwardNotice'
          AND buyer_country_code IS NOT NULL
          AND lot_value_eur IS NOT NULL
        GROUP BY buyer_country_code
        ORDER BY awarded_m DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def top_cpv_divisions(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT cpv_division,
               FIRST(cpv_name)    AS cpv_label,
               COUNT(*)           AS lots
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE cpv_division IS NOT NULL
        GROUP BY cpv_division
        ORDER BY lots DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def procurement_type_distribution() -> pd.DataFrame:
    return query(f"""
        SELECT COALESCE(procurement_type, 'Unknown') AS type,
               COUNT(*)                              AS lots
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        GROUP BY procurement_type
        ORDER BY lots DESC
    """)


@st.cache_data(ttl=300, show_spinner=False)
def largest_cn_lots(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT
            n.lot_name                                       AS title,
            n.buyer_country_code                             AS country,
            CONCAT('€', FORMAT_NUMBER(n.lot_value_eur, 0))  AS est_amount,
            n.cpv_name                                       AS cpv,
            n.cpv_division                                   AS cpv_div
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched n
        WHERE n.notice_type = 'ContractNotice'
          AND n.lot_value_eur IS NOT NULL
        ORDER BY n.lot_value_eur DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def largest_can_lots(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT
            lot_name                                        AS title,
            buyer_country_code                              AS country,
            CONCAT('€', FORMAT_NUMBER(lot_value_eur, 0))   AS awarded,
            tenderer_name                                   AS winner,
            cpv_name                                        AS cpv
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE notice_type = 'ContractAwardNotice'
          AND lot_value_eur IS NOT NULL
        ORDER BY lot_value_eur DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def top_buyers(limit: int = 20) -> pd.DataFrame:
    return query(f"""
        SELECT
            buyer_name                                          AS buyer,
            buyer_country_code                                  AS country,
            buyer_legal_type                                    AS type,
            COUNT(DISTINCT notice_publication_id)               AS tenders,
            ROUND(SUM(lot_value_eur) / 1e6, 2)                 AS total_spend_m,
            ROUND(AVG(lot_value_eur) / 1e3, 0)                 AS avg_spend_k
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE buyer_name IS NOT NULL
        GROUP BY buyer_name, buyer_country_code, buyer_legal_type
        ORDER BY total_spend_m DESC NULLS LAST
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def buyer_type_distribution() -> pd.DataFrame:
    return query(f"""
        SELECT COALESCE(buyer_legal_type, 'Unknown') AS type,
               COUNT(DISTINCT buyer_org_ref)         AS buyers
        FROM {CATALOG}.{SCHEMA}.silver_notices_enriched
        WHERE buyer_legal_type IS NOT NULL
        GROUP BY buyer_legal_type
        ORDER BY buyers DESC
        LIMIT 8
    """)


@st.cache_data(ttl=300, show_spinner=False)
def buyer_country_distribution(limit: int = 15) -> pd.DataFrame:
    return query(f"""
        SELECT buyer_country_code AS country,
               COUNT(DISTINCT buyer_org_ref) AS buyers
        FROM {CATALOG}.{SCHEMA}.silver_notices_enriched
        WHERE buyer_country_code IS NOT NULL
        GROUP BY buyer_country_code
        ORDER BY buyers DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def notice_volume_by_date() -> pd.DataFrame:
    return query(f"""
        SELECT issue_date,
               COUNT(DISTINCT notice_publication_id) AS notices
        FROM {CATALOG}.{SCHEMA}.silver_notices_enriched
        WHERE issue_date IS NOT NULL
        GROUP BY issue_date
        ORDER BY issue_date
    """)


@st.cache_data(ttl=300, show_spinner=False)
def top_winners(limit: int = 15) -> pd.DataFrame:
    return query(f"""
        SELECT
            tenderer_name                                       AS organization,
            tenderer_country_code                               AS country,
            COUNT(DISTINCT notice_publication_id)               AS awards,
            ROUND(SUM(lot_value_eur) / 1e6, 2)                 AS total_won_m,
            ROUND(AVG(lot_value_eur) / 1e3, 0)                 AS avg_contract_k
        FROM {CATALOG}.{SCHEMA}.silver_lots_enriched
        WHERE tenderer_name IS NOT NULL
          AND notice_type = 'ContractAwardNotice'
        GROUP BY tenderer_name, tenderer_country_code
        ORDER BY total_won_m DESC NULLS LAST
        LIMIT {limit}
    """)
