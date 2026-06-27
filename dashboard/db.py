"""
dashboard/db.py — Databricks SQL connector for the Streamlit dashboard.

Uses databricks-sql-connector (not Spark/Databricks Connect) so queries run
against the serverless SQL Warehouse and return in under a second. Results are
cached per Streamlit session so page re-renders never re-query Databricks.

Required env vars (already in .env):
    DATABRICKS_HOST        e.g. https://dbc-xxxx.cloud.databricks.com
    DATABRICKS_TOKEN       personal access token
    DATABRICKS_HTTP_PATH   e.g. /sql/1.0/warehouses/<id>

Layer routing:
    gold_market_kpis   — pre-aggregated daily KPIs (Executive Overview, Trends)
    gold_award_summary — winner aggregations (Supplier & Awards)
    gold_it_lots       — IT-filtered opportunities (Opportunity Radar)
    silver_*           — fallback for anything not yet in gold
"""
from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

load_dotenv()

_HOST      = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
_TOKEN     = os.environ["DATABRICKS_TOKEN"]
_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]

CATALOG = "capstone"
SCHEMA  = "ted"
_S = f"{CATALOG}.{SCHEMA}"   # shorthand


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
# Summary metrics — read from gold_market_kpis (pre-aggregated)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def cn_summary() -> dict:
    """Counts/totals for open contract notices (CN)."""
    df = query(f"""
        SELECT
            SUM(notices)                                                    AS open_tenders,
            COUNT(DISTINCT buyer_country_code)                              AS countries,
            ROUND(SUM(total_value_eur) / 1e6, 1)                           AS total_value_m,
            ROUND(SUM(lots) * 1.0 / NULLIF(SUM(notices), 0), 1)           AS avg_lots_per_tender
        FROM {_S}.gold_market_kpis
        WHERE notice_type = 'ContractNotice'
    """)
    return df.iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def can_summary() -> dict:
    """Counts/totals for contract award notices (CAN)."""
    df = query(f"""
        SELECT
            SUM(notices)                                    AS awards,
            COUNT(DISTINCT buyer_country_code)              AS countries,
            ROUND(SUM(total_value_eur) / 1e6, 1)           AS total_awarded_m,
            ROUND(SUM(total_value_eur) / NULLIF(SUM(lots), 0) / 1e3, 0)
                                                            AS avg_award_k
        FROM {_S}.gold_market_kpis
        WHERE notice_type = 'ContractAwardNotice'
    """)
    return df.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# Country / CPV / type breakdowns — from gold_market_kpis
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def top_countries_by_notices(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT buyer_country_code           AS country,
               SUM(notices)                AS notices
        FROM {_S}.gold_market_kpis
        WHERE buyer_country_code IS NOT NULL
        GROUP BY buyer_country_code
        ORDER BY notices DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def top_countries_by_award_value(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT buyer_country_code                       AS country,
               ROUND(SUM(total_value_eur) / 1e6, 2)   AS awarded_m
        FROM {_S}.gold_market_kpis
        WHERE notice_type = 'ContractAwardNotice'
          AND buyer_country_code IS NOT NULL
          AND total_value_eur IS NOT NULL
        GROUP BY buyer_country_code
        ORDER BY awarded_m DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def top_cpv_divisions(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT cpv_division,
               MAX(cpv_name)   AS cpv_label,
               SUM(lots)       AS lots
        FROM {_S}.gold_market_kpis
        WHERE cpv_division IS NOT NULL
        GROUP BY cpv_division
        ORDER BY lots DESC
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def procurement_type_distribution() -> pd.DataFrame:
    return query(f"""
        SELECT COALESCE(procurement_type, 'Unknown')    AS type,
               SUM(lots)                               AS lots
        FROM {_S}.gold_market_kpis
        GROUP BY procurement_type
        ORDER BY lots DESC
    """)


@st.cache_data(ttl=300, show_spinner=False)
def notice_volume_by_date() -> pd.DataFrame:
    return query(f"""
        SELECT issue_date,
               SUM(notices)    AS notices
        FROM {_S}.gold_market_kpis
        WHERE issue_date IS NOT NULL
        GROUP BY issue_date
        ORDER BY issue_date
    """)


# ---------------------------------------------------------------------------
# Winner aggregations — from gold_award_summary
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def top_winners(limit: int = 15) -> pd.DataFrame:
    return query(f"""
        SELECT
            tenderer_name                               AS organization,
            tenderer_country_code                       AS country,
            awards,
            ROUND(total_won_eur / 1e6, 2)              AS total_won_m,
            ROUND(avg_contract_eur / 1e3, 0)           AS avg_contract_k
        FROM {_S}.gold_award_summary
        WHERE tenderer_name IS NOT NULL
        ORDER BY total_won_eur DESC NULLS LAST
        LIMIT {limit}
    """)


# ---------------------------------------------------------------------------
# IT opportunity lots — from gold_it_lots
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def it_lots(limit: int = 500) -> pd.DataFrame:
    """IT-relevant CN lots for the Opportunity Radar."""
    return query(f"""
        SELECT
            notice_publication_id,
            lot_id,
            lot_name            AS title,
            cpv_code,
            cpv_name,
            cpv_division,
            procurement_type    AS type,
            lot_value_eur,
            submission_deadline_date AS deadline,
            buyer_name,
            buyer_country_code  AS country,
            value_proxy_score,
            opportunity_score,
            predicted_competition
        FROM {_S}.gold_it_lots
        ORDER BY
            opportunity_score IS NULL,
            COALESCE(opportunity_score, value_proxy_score) DESC NULLS LAST
        LIMIT {limit}
    """)


# ---------------------------------------------------------------------------
# Prior Information Notices — early buyer-intent signals, from gold_pin_monitor
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def pin_monitor(limit: int = 1000) -> pd.DataFrame:
    """PINs signal a buyer's intent weeks-to-months before the formal
    Contract Notice opens - the proactive layer ahead of Opportunity Radar."""
    return query(f"""
        SELECT
            notice_publication_id,
            lot_name             AS title,
            buyer_name,
            buyer_country_code   AS country,
            cpv_division,
            cpv_name,
            COALESCE(lot_value_eur, value_eur) AS value_eur,
            expected_value,
            p_win,
            days_since_pin,
            priority
        FROM {_S}.gold_pin_monitor
        ORDER BY priority DESC, expected_value DESC NULLS LAST
        LIMIT {limit}
    """)


# ---------------------------------------------------------------------------
# Largest individual lots — still from silver (row-level, no gold equivalent)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def largest_cn_lots(limit: int = 10) -> pd.DataFrame:
    return query(f"""
        SELECT
            lot_name                                        AS title,
            buyer_country_code                              AS country,
            CONCAT('€', FORMAT_NUMBER(lot_value_eur, 0))   AS est_amount,
            cpv_name                                        AS cpv,
            cpv_division                                    AS cpv_div
        FROM {_S}.silver_lots_enriched
        WHERE notice_type = 'ContractNotice'
          AND lot_value_eur IS NOT NULL
        ORDER BY lot_value_eur DESC
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
        FROM {_S}.silver_lots_enriched
        WHERE notice_type = 'ContractAwardNotice'
          AND lot_value_eur IS NOT NULL
        ORDER BY lot_value_eur DESC
        LIMIT {limit}
    """)


# ---------------------------------------------------------------------------
# Buyer breakdowns — still from silver (buyer aggregations not in gold yet)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def top_buyers(limit: int = 20) -> pd.DataFrame:
    return query(f"""
        SELECT
            buyer_name                                      AS buyer_name,
            buyer_country_code                              AS country,
            buyer_legal_type                                AS type,
            COUNT(DISTINCT notice_publication_id)           AS tenders,
            ROUND(SUM(lot_value_eur) / 1e6, 2)             AS total_spend_m,
            ROUND(AVG(lot_value_eur) / 1e3, 0)             AS avg_spend_k
        FROM {_S}.silver_lots_enriched
        WHERE buyer_name IS NOT NULL
        GROUP BY buyer_name, buyer_country_code, buyer_legal_type
        ORDER BY total_spend_m DESC NULLS LAST
        LIMIT {limit}
    """)


@st.cache_data(ttl=300, show_spinner=False)
def buyer_type_distribution() -> pd.DataFrame:
    return query(f"""
        SELECT COALESCE(buyer_legal_type, 'Unknown')    AS type,
               COUNT(DISTINCT buyer_org_ref)            AS buyers
        FROM {_S}.silver_notices_enriched
        WHERE buyer_legal_type IS NOT NULL
        GROUP BY buyer_legal_type
        ORDER BY buyers DESC
        LIMIT 8
    """)


@st.cache_data(ttl=300, show_spinner=False)
def buyer_country_distribution(limit: int = 15) -> pd.DataFrame:
    return query(f"""
        SELECT buyer_country_code   AS country,
               COUNT(DISTINCT buyer_org_ref) AS buyers
        FROM {_S}.silver_notices_enriched
        WHERE buyer_country_code IS NOT NULL
        GROUP BY buyer_country_code
        ORDER BY buyers DESC
        LIMIT {limit}
    """)
