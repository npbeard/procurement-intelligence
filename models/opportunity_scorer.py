"""
Opportunity Scorer — Main Entry Point

Combines all ML components into a single ranked opportunity list for Microsoft:

    1. Buyer Affinity Score   — how aligned is this buyer with Microsoft's portfolio?
    2. Win Probability Model  — XGBoost predicting P(low competition)
    3. Expected Value         — contract_value × P(win)

Output: ranked DataFrame of live IT tenders by Expected Value,
        ready for the dashboard or downstream analysis.
"""

from __future__ import annotations

import pandas as pd

from models.feature_engineering import load_it_lots
from models.buyer_affinity import compute_buyer_affinity
from models.cpv_microsoft_mapping import get_cpv_product_line
from models.win_probability import train_win_probability_model, score_opportunities


OUTPUT_COLS = [
    "notice_publication_id",
    "lot_id",
    "lot_name",
    "buyer_name",
    "buyer_org_ref",
    "buyer_country_code",
    "cpv_division",
    "cpv_code",
    "product_line",
    "issue_date",
    "value_eur",
    "p_low_competition",
    "affinity_score",
    "cpv_relevance",
    "p_win",
    "expected_value",
]

# Notice types that represent live/upcoming tenders (not already awarded)
LIVE_NOTICE_TYPES = {"ContractNotice", "PriorInformationNotice"}


def run_opportunity_scoring(
    spark=None,
    days_lookback: int = 60,
) -> dict:
    """
    Full pipeline: load data → affinity scoring → win probability → EV ranking.

    Args:
        spark:         Spark session (created from .env if None)
        days_lookback: how many days back to look for live tenders

    Returns dict with:
        opportunities:  DataFrame ranked by expected_value (live tenders only)
        buyer_affinity: DataFrame with affinity scores for all buyers
        model_metrics:  dict with accuracy, feature importance, n_train
        all_scored:     full DataFrame including award notices (for analysis)
    """
    print("=" * 55)
    print("Microsoft EU Procurement Intelligence — Scoring Run")
    print("=" * 55)

    print("\n[1/4] Loading IT procurement data from Databricks...")
    df = load_it_lots(spark)
    print(f"  {len(df):,} IT lots loaded ({df['buyer_country_code'].nunique()} countries)")

    print("\n[2/4] Computing buyer affinity scores...")
    buyer_affinity = compute_buyer_affinity(df)
    print(f"  {len(buyer_affinity):,} buyers scored")
    print(f"  Avg affinity: {buyer_affinity['affinity_score'].mean():.3f}")

    if "nb_tenders_received" not in df.columns:
        print(
            "\n[WARNING] nb_tenders_received not found in Silver layer.\n"
            "Win probability model cannot train yet.\n"
            "Ask teammate to re-run bronze parsing and dbt silver model."
        )
        return {
            "opportunities": None,
            "buyer_affinity": buyer_affinity,
            "model_metrics": None,
            "all_scored": None,
        }

    print("\n[3/4] Training win probability model...")
    model, le, metrics = train_win_probability_model(df, buyer_affinity)

    print("\n[4/4] Scoring all IT lots...")
    all_scored = score_opportunities(df, model, le, buyer_affinity)
    all_scored["product_line"] = all_scored["cpv_code"].astype(str).apply(get_cpv_product_line)

    # Filter to live tenders within the lookback window
    all_scored["issue_date"] = pd.to_datetime(all_scored["issue_date"], errors="coerce")
    max_date = all_scored["issue_date"].max()
    cutoff = max_date - pd.Timedelta(days=days_lookback)

    opportunities = (
        all_scored[
            all_scored["notice_type"].isin(LIVE_NOTICE_TYPES)
            & (all_scored["issue_date"] >= cutoff)
            & (all_scored["value_eur"].notna())
            & (all_scored["value_eur"] > 0)
        ]
        .drop_duplicates(subset=["notice_publication_id"])
        .sort_values("expected_value", ascending=False)
        .reset_index(drop=True)
    )

    out_cols = [c for c in OUTPUT_COLS if c in opportunities.columns]
    opportunities = opportunities[out_cols]

    print(f"\n  Live tenders scored: {len(opportunities):,}")
    print(f"  Total pipeline EV:  €{opportunities['expected_value'].sum()/1e6:.1f}M")
    if len(opportunities) > 0:
        top = opportunities.iloc[0]
        print(f"  Top opportunity:    {top.get('lot_name', 'N/A')[:60]}")
        print(f"                      €{top['value_eur']:,.0f} × {top['p_win']:.0%} = €{top['expected_value']:,.0f} EV")

    return {
        "opportunities": opportunities,
        "buyer_affinity": buyer_affinity,
        "model_metrics": metrics,
        "all_scored": all_scored,
    }
