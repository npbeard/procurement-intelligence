"""
Model 2 — IT Buyer Segmentation


Clusters public sector IT buyers into behavioral segments based on
their procurement history. Helps Microsoft identify which buyers to target
and how to approach them.

Input:  capstone.ted.silver_lots_enriched (IT CPV codes only)
Output: DataFrame with buyer_org_ref, segment label, and behavioral stats
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings("ignore")

from models.feature_engineering import load_it_lots


MIN_TENDERS = 2  # minimum tenders for a buyer to be included


def build_buyer_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate silver lots into one row per buyer with behavioral features.
    """
    df = df.copy()
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df = df.dropna(subset=["buyer_org_ref"])

    profiles = (
        df.groupby(["buyer_org_ref", "buyer_name", "buyer_country_code"])
        .agg(
            total_tenders=("notice_publication_id", "nunique"),
            total_lots=("lot_id", "count"),
            total_value_eur=("value_eur", "sum"),
            avg_lot_value=("value_eur", "mean"),
            max_lot_value=("value_eur", "max"),
            cpv_diversity=("cpv_code", "nunique"),
            cpv_division_diversity=("cpv_division", "nunique"),
            countries_active=("buyer_country_code", "nunique"),
            open_procedure_pct=(
                "procurement_procedure",
                lambda x: (x.str.lower() == "open").mean(),
            ),
            first_tender=("issue_date", "min"),
            last_tender=("issue_date", "max"),
        )
        .reset_index()
    )

    # Active months = how long the buyer has been active
    profiles["active_days"] = (
        profiles["last_tender"] - profiles["first_tender"]
    ).dt.days.clip(lower=1)

    # Tender frequency = tenders per month
    profiles["tenders_per_month"] = (
        profiles["total_tenders"] / (profiles["active_days"] / 30)
    ).clip(upper=50)

    # Filter out buyers with too few tenders
    profiles = profiles[profiles["total_tenders"] >= MIN_TENDERS].copy()

    # Log-transform skewed value columns
    profiles["log_total_value"] = np.log1p(profiles["total_value_eur"].fillna(0))
    profiles["log_avg_lot_value"] = np.log1p(profiles["avg_lot_value"].fillna(0))
    profiles["log_total_tenders"] = np.log1p(profiles["total_tenders"])

    return profiles


def select_optimal_k(features_scaled: np.ndarray, k_range: range) -> int:
    """Select best k using silhouette score."""
    best_k, best_score = k_range[0], -1
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(features_scaled)
        score = silhouette_score(features_scaled, labels)
        if score > best_score:
            best_score = score
            best_k = k
    print(f"Optimal k={best_k} (silhouette={best_score:.3f})")
    return best_k


def assign_persona(cluster_stats: pd.DataFrame) -> dict[int, str]:
    """
    Automatically assign persona names based on cluster characteristics.
    Ranks clusters by total_value_eur and total_tenders to label them.
    """
    personas = {}
    ranked_by_value = cluster_stats["total_value_eur"].rank(ascending=False)
    ranked_by_freq = cluster_stats["tenders_per_month"].rank(ascending=False)

    for cluster_id in cluster_stats.index:
        value_rank = ranked_by_value[cluster_id]
        freq_rank = ranked_by_freq[cluster_id]

        if value_rank == 1 and freq_rank <= 2:
            personas[cluster_id] = "High-Value Enterprise Buyer"
        elif freq_rank == 1:
            personas[cluster_id] = "Frequent Small Buyer"
        elif value_rank <= 2:
            personas[cluster_id] = "Occasional Large Buyer"
        elif cluster_stats.loc[cluster_id, "cpv_diversity"] >= cluster_stats["cpv_diversity"].median():
            personas[cluster_id] = "Specialist IT Buyer"
        else:
            personas[cluster_id] = "Emerging IT Buyer"

    return personas


def run_buyer_segmentation(spark=None, k: int | None = None) -> pd.DataFrame:
    """
    Main entry point. Returns buyer profiles with segment labels.

    Columns:
        buyer_org_ref, buyer_name, buyer_country_code,
        segment_id, segment_label,
        total_tenders, total_value_eur, avg_lot_value,
        cpv_diversity, open_procedure_pct, tenders_per_month
    """
    print("Loading IT procurement data from Databricks...")
    df = load_it_lots(spark)

    print("Building buyer profiles...")
    profiles = build_buyer_profiles(df)
    print(f"  {len(profiles)} buyers with {MIN_TENDERS}+ IT tenders")

    # Features for clustering
    feature_cols = [
        "log_total_value",
        "log_avg_lot_value",
        "log_total_tenders",
        "tenders_per_month",
        "cpv_diversity",
        "open_procedure_pct",
    ]
    X = profiles[feature_cols].fillna(0).values

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Select k automatically if not provided
    if k is None:
        print("Selecting optimal number of segments...")
        k = select_optimal_k(X_scaled, k_range=range(3, 7))

    # Train KMeans
    print(f"Training KMeans with k={k}...")
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    profiles["segment_id"] = km.fit_predict(X_scaled)

    # Assign persona names
    cluster_stats = profiles.groupby("segment_id").agg(
        total_value_eur=("total_value_eur", "mean"),
        tenders_per_month=("tenders_per_month", "mean"),
        cpv_diversity=("cpv_diversity", "mean"),
    )
    personas = assign_persona(cluster_stats)
    profiles["segment_label"] = profiles["segment_id"].map(personas)

    # Summary
    summary = (
        profiles.groupby(["segment_id", "segment_label"])
        .agg(
            buyer_count=("buyer_org_ref", "count"),
            avg_total_value=("total_value_eur", "mean"),
            avg_tenders=("total_tenders", "mean"),
            top_country=("buyer_country_code", lambda x: x.value_counts().index[0]),
        )
        .reset_index()
    )
    print("\nSegment Summary:")
    print(summary.to_string(index=False))

    output_cols = [
        "buyer_org_ref", "buyer_name", "buyer_country_code",
        "segment_id", "segment_label",
        "total_tenders", "total_value_eur", "avg_lot_value",
        "cpv_diversity", "open_procedure_pct", "tenders_per_month",
    ]
    return profiles[output_cols]


if __name__ == "__main__":
    segments_df = run_buyer_segmentation()
    segments_df.to_csv("outputs/buyer_segments.csv", index=False)
    print("\nSaved to outputs/buyer_segments.csv")
