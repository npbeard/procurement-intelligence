"""
Model 1 — Contract Value Anomaly Detection


Flags IT tenders where the contract value is unusually high or low
compared to similar contracts in the same CPV category and country.
Uses Isolation Forest — an unsupervised ML algorithm that learns what
a normal contract looks like and scores deviations from that pattern.

Input:  capstone.ted.silver_lots_enriched (IT CPV codes only)
Output: DataFrame with anomaly score and flag per lot
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

from models.feature_engineering import load_it_lots


CONTAMINATION = 0.05  # expect ~5% of contracts to be anomalous


def build_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare features for anomaly detection — value-focused."""
    df = df.copy()

    # Use lot_value_eur, fall back to estimated_value
    df["value_eur"] = df["lot_value_eur"].fillna(df["estimated_value"])

    # Drop rows with no value at all — can't detect value anomalies without a value
    df = df.dropna(subset=["value_eur"])
    df = df[df["value_eur"] > 0].copy()

    df["log_value"] = np.log1p(df["value_eur"])
    df["cpv_division_enc"] = pd.Categorical(df["cpv_division"]).codes
    df["country_enc"] = pd.Categorical(df["buyer_country_code"]).codes
    df["procedure_enc"] = pd.Categorical(
        df["procurement_procedure"].fillna("UNKNOWN")
    ).codes
    df["buyer_type_enc"] = pd.Categorical(
        df["buyer_legal_type"].fillna("UNKNOWN")
    ).codes

    return df


def compute_market_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-market (country + CPV division) value statistics for context."""
    market_stats = (
        df.groupby(["buyer_country_code", "cpv_division"])["value_eur"]
        .agg(
            market_median="median",
            market_mean="mean",
            market_std="std",
        )
        .reset_index()
    )
    df = df.merge(market_stats, on=["buyer_country_code", "cpv_division"], how="left")

    # How many standard deviations from market median
    df["value_zscore"] = (
        (df["value_eur"] - df["market_median"]) /
        df["market_std"].replace(0, np.nan)
    ).fillna(0)

    # Ratio to market median
    df["value_to_median_ratio"] = (
        df["value_eur"] / df["market_median"].replace(0, np.nan)
    ).fillna(1).clip(0, 100)

    return df


def run_anomaly_detection(spark=None) -> pd.DataFrame:
    """
    Main entry point. Returns IT lots with anomaly scores and flags.

    Columns:
        notice_publication_id, lot_id, buyer_country_code, cpv_division,
        value_eur, market_median, value_to_median_ratio,
        anomaly_score, is_anomaly, anomaly_direction
    """
    print("Loading IT procurement data from Databricks...")
    df = load_it_lots(spark)

    print("Building anomaly features...")
    df = build_anomaly_features(df)
    df = compute_market_statistics(df)
    print(f"  {len(df)} IT lots with known values")

    feature_cols = [
        "log_value",
        "cpv_division_enc",
        "country_enc",
        "procedure_enc",
        "buyer_type_enc",
        "value_zscore",
        "value_to_median_ratio",
    ]
    X = df[feature_cols].fillna(0).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("Training Isolation Forest...")
    model = IsolationForest(
        contamination=CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    df["anomaly_score"] = model.fit_predict(X_scaled)
    # Isolation Forest returns -1 for anomalies, 1 for normal
    df["is_anomaly"] = df["anomaly_score"] == -1

    # Label direction — is the anomaly unusually high or low?
    df["anomaly_direction"] = np.where(
        ~df["is_anomaly"], "Normal",
        np.where(df["value_eur"] > df["market_median"], "Unusually High", "Unusually Low")
    )

    n_anomalies = df["is_anomaly"].sum()
    print(f"\nDetected {n_anomalies} anomalies ({n_anomalies/len(df)*100:.1f}% of IT lots)")
    print(df["anomaly_direction"].value_counts().to_string())

    output_cols = [
        "notice_publication_id", "lot_id", "lot_name",
        "buyer_country_code", "cpv_division", "cpv_name",
        "buyer_name", "procurement_procedure",
        "value_eur", "market_median", "value_to_median_ratio",
        "is_anomaly", "anomaly_direction",
    ]
    return df[[c for c in output_cols if c in df.columns]]


if __name__ == "__main__":
    import os
    os.makedirs("outputs", exist_ok=True)
    anomaly_df = run_anomaly_detection()
    anomaly_df.to_csv("outputs/anomaly_detection.csv", index=False)
    print("\nSaved to outputs/anomaly_detection.csv")
