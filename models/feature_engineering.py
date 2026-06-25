"""
Feature engineering for TED procurement ML models.
Reads from Databricks Silver tables and produces clean pandas DataFrames
ready for training or inference.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from databricks.connect import DatabricksSession
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# IT-relevant CPV divisions (matches gold_it_lots.sql filter)
IT_CPV_DIVISIONS = {"30", "48", "72"}

# CPV division labels
CPV_LABELS = {
    "30": "Computing Equipment",
    "48": "Software",
    "72": "IT Services",
}


def get_spark():
    return DatabricksSession.builder.remote(
        host=os.getenv("DATABRICKS_HOST"),
        token=os.getenv("DATABRICKS_TOKEN"),
        serverless=True,
    ).getOrCreate()


def load_silver_lots(spark=None) -> pd.DataFrame:
    """Load silver_lots_enriched filtered to IT CPV divisions."""
    if spark is None:
        spark = get_spark()

    df = (
        spark.table("capstone.ted.silver_lots_enriched")
        .filter("cpv_division IN ('30', '48', '72')")
        .toPandas()
    )
    return df


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["year"] = df["issue_date"].dt.year
    df["month"] = df["issue_date"].dt.month
    df["quarter"] = df["issue_date"].dt.quarter
    df["year_month"] = df["issue_date"].dt.to_period("M").astype(str)
    return df


def add_value_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Use lot_value_eur as primary, fall back to estimated_value
    df["value_eur"] = df["lot_value_eur"].fillna(df["estimated_value"])
    df["log_value"] = np.log1p(df["value_eur"].clip(lower=0))
    df["value_bucket"] = pd.cut(
        df["value_eur"].fillna(0),
        bins=[0, 50_000, 200_000, 1_000_000, 5_000_000, np.inf],
        labels=["micro", "small", "medium", "large", "mega"],
    ).astype(str)
    return df


def add_cpv_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cpv_division_label"] = df["cpv_division"].map(CPV_LABELS).fillna("Other IT")
    # CPV group = first 3 digits for finer granularity
    df["cpv_group"] = df["cpv_code"].astype(str).str[:3]
    return df


def encode_categoricals(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("UNKNOWN")
            df[col + "_enc"] = pd.Categorical(df[col]).codes
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all feature engineering steps."""
    df = add_temporal_features(df)
    df = add_value_features(df)
    df = add_cpv_features(df)
    df = encode_categoricals(df, [
        "buyer_country_code",
        "buyer_legal_type",
        "procurement_procedure",
        "procurement_type",
        "cpv_division",
        "cpv_group",
        "value_bucket",
        "notice_type",
    ])
    return df


def load_it_lots(spark=None) -> pd.DataFrame:
    """Full pipeline: load + feature engineering. Main entry point for models."""
    df = load_silver_lots(spark)
    df = build_features(df)
    return df
