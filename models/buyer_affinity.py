"""
Buyer Affinity Scorer

Scores each public sector IT buyer (0–1) on how aligned their procurement
history is with Microsoft's product portfolio (Azure, M365, Security, Dynamics).

Score combines:
  - CPV relevance: what % of their spend maps to Microsoft product lines
  - Recency weighting: contracts in the last 6 months count more
  - Open procedure rate: open tenders are accessible to Microsoft (vs restricted/negotiated)

A buyer with affinity_score = 0.85 has been consistently buying Azure/M365-adjacent
software and uses open procedures — a high-priority target for Microsoft's sales team.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from models.cpv_microsoft_mapping import get_cpv_product_line, get_cpv_relevance


RECENCY_HALF_LIFE_DAYS = 180  # contracts older than 6 months decay in weight


def compute_buyer_affinity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute affinity score per buyer from silver lots DataFrame.

    Returns one row per buyer_org_ref with:
        affinity_score          0-1 composite score
        cpv_relevance_score     weighted average CPV relevance to Microsoft
        open_procedure_pct      share of open tenders (accessible to Microsoft)
        top_product_line        most frequent Microsoft product line this buyer buys
        total_it_spend          total EUR value of IT contracts
        total_contracts         number of distinct tenders
    """
    df = df.copy()
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["value_eur"] = df["lot_value_eur"].fillna(df["estimated_value"]).fillna(0)
    df = df.dropna(subset=["buyer_org_ref"])

    # CPV relevance per lot
    df["cpv_relevance"] = df["cpv_code"].astype(str).apply(get_cpv_relevance)
    df["product_line"] = df["cpv_code"].astype(str).apply(get_cpv_product_line)

    # Recency weight: exponential decay from most recent contract
    max_date = df["issue_date"].max()
    df["days_ago"] = (max_date - df["issue_date"]).dt.days.fillna(365).clip(lower=0)
    df["recency_weight"] = np.exp(-df["days_ago"] / RECENCY_HALF_LIFE_DAYS)

    df["weighted_relevance"] = df["cpv_relevance"] * df["recency_weight"]

    buyer_agg = (
        df.groupby("buyer_org_ref")
        .agg(
            buyer_name=("buyer_name", "first"),
            buyer_country_code=("buyer_country_code", "first"),
            total_contracts=("notice_publication_id", "nunique"),
            total_it_spend=("value_eur", "sum"),
            sum_weighted_relevance=("weighted_relevance", "sum"),
            sum_recency_weight=("recency_weight", "sum"),
            open_procedure_pct=(
                "procurement_procedure",
                lambda x: (x.str.lower() == "open").mean(),
            ),
            top_product_line=(
                "product_line",
                lambda x: x.value_counts().index[0] if len(x) > 0 else "General IT",
            ),
        )
        .reset_index()
    )

    # Recency-weighted average CPV relevance
    buyer_agg["cpv_relevance_score"] = (
        buyer_agg["sum_weighted_relevance"]
        / buyer_agg["sum_recency_weight"].replace(0, 1)
    )

    # Composite affinity score
    # 70% CPV relevance (what they buy aligns with Microsoft portfolio)
    # 30% open procedure (Microsoft can actually bid)
    buyer_agg["affinity_score"] = (
        buyer_agg["cpv_relevance_score"] * 0.7
        + buyer_agg["open_procedure_pct"] * 0.3
    ).clip(0, 1)

    output_cols = [
        "buyer_org_ref", "buyer_name", "buyer_country_code",
        "total_contracts", "total_it_spend",
        "affinity_score", "cpv_relevance_score", "open_procedure_pct",
        "top_product_line",
    ]
    return buyer_agg[output_cols].sort_values("affinity_score", ascending=False)
