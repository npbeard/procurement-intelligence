"""
Opportunity Scorer — Main Entry Point

Combines all ML components into a single ranked opportunity list for Microsoft:

    1. Buyer Affinity Score   — how aligned is this buyer with Microsoft's portfolio?
    2. Win Probability Model  — XGBoost predicting P(low competition)
    3. Expected Value         — contract_value × P(win)

Model persistence:
    - On first run (or force_retrain=True): trains XGBoost on historical CANs and saves it.
    - On all subsequent daily runs: loads the saved model and scores new data without retraining.
    - Saved to DEFAULT_MODEL_PATH (default: /dbfs/capstone/models/win_probability.pkl)

Output: ranked DataFrame of live IT tenders by Expected Value,
        written to Gold Delta tables and returned for notebook use.
"""

from __future__ import annotations

import pandas as pd

from models.feature_engineering import load_it_lots
from models.buyer_affinity import compute_buyer_affinity
from models.cpv_microsoft_mapping import get_cpv_product_line
from models.win_probability import (
    DEFAULT_MODEL_PATH,
    load_model,
    model_exists,
    score_opportunities,
    train_win_probability_model,
)


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

LIVE_NOTICE_TYPES = {"ContractNotice", "PriorInformationNotice"}

GOLD_OPPORTUNITIES_TABLE = "capstone.ted.gold_opportunity_scores"
GOLD_AFFINITY_TABLE      = "capstone.ted.gold_buyer_affinity"
GOLD_PIN_TABLE           = "capstone.ted.gold_pin_monitor"

DEFAULT_MODEL_PATH = "/tmp/capstone_win_probability.pkl"


def run_opportunity_scoring(
    spark=None,
    days_lookback: int = 60,
    force_retrain: bool = False,
    model_path: str = DEFAULT_MODEL_PATH,
    write_gold: bool = True,
) -> dict:
    """
    Full daily pipeline: load data → affinity scoring → score with saved model → Gold tables.

    Args:
        spark:          Spark session (created from .env if None)
        days_lookback:  how many days back to look for live tenders
        force_retrain:  if True, retrain XGBoost even if a saved model exists
                        (run this monthly or when Silver data grows significantly)
        model_path:     where the serialised model is stored on DBFS
        write_gold:     if True, write results to Gold Delta tables

    Returns dict with:
        opportunities:  DataFrame ranked by expected_value (live tenders only)
        buyer_affinity: DataFrame with affinity scores for all buyers
        model_metrics:  dict with accuracy, feature importance, n_train
        all_scored:     full DataFrame including award notices (for analysis)
        pins:           Prior Information Notices with priority flag
    """
    print("=" * 55)
    print("Microsoft EU Procurement Intelligence — Scoring Run")
    print("=" * 55)

    # ── Step 1: Load Silver data ──────────────────────────────
    print("\n[1/4] Loading IT procurement data from Databricks...")
    df = load_it_lots(spark)
    print(f"  {len(df):,} IT lots loaded ({df['buyer_country_code'].nunique()} countries)")

    # ── Step 2: Buyer affinity (always recomputed — fast, no training) ────────
    print("\n[2/4] Computing buyer affinity scores...")
    buyer_affinity = compute_buyer_affinity(df)
    print(f"  {len(buyer_affinity):,} buyers scored")
    print(f"  Avg affinity: {buyer_affinity['affinity_score'].mean():.3f}")

    # ── Step 3: Load or train XGBoost ─────────────────────────
    if "nb_tenders_received" not in df.columns:
        print(
            "\n[WARNING] nb_tenders_received not found in Silver layer.\n"
            "Win probability model cannot train yet.\n"
            "Ask teammate to re-run bronze parsing and dbt silver model."
        )
        return {
            "opportunities": None,
            "buyer_affinity": buyer_affinity,
            "model_metrics":  None,
            "all_scored":     None,
            "pins":           None,
        }

    saved = load_model(model_path) if not force_retrain else None

    if saved is not None:
        model, le, metrics = saved
        print(f"\n[3/4] Using saved model — skipping retraining.")
    else:
        reason = "force_retrain=True" if force_retrain else "no saved model found"
        print(f"\n[3/4] Training win probability model ({reason})...")
        model, le, metrics = train_win_probability_model(df, buyer_affinity, save_path=model_path)

    # ── Step 4: Score all lots with the loaded/trained model ──
    print("\n[4/4] Scoring all IT lots...")
    all_scored = score_opportunities(df, model, le, buyer_affinity)
    all_scored["product_line"] = all_scored["cpv_code"].astype(str).apply(get_cpv_product_line)

    all_scored["issue_date"] = pd.to_datetime(all_scored["issue_date"], errors="coerce")
    max_date = all_scored["issue_date"].max()
    cutoff   = max_date - pd.Timedelta(days=days_lookback)

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

    out_cols      = [c for c in OUTPUT_COLS if c in opportunities.columns]
    opportunities = opportunities[out_cols]

    # PIN monitor view
    pins = all_scored[
        (all_scored["notice_type"] == "PriorInformationNotice")
        & all_scored["value_eur"].notna()
        & (all_scored["value_eur"] > 0)
    ].drop_duplicates(subset=["notice_publication_id"]).copy()
    pins["pin_ev"]         = pins["value_eur"] * (pins["affinity_score"] * 0.6 + pins["cpv_relevance"] * 0.4)
    pins["days_since_pin"] = (max_date - pins["issue_date"]).dt.days
    pins["priority"]       = (pins["affinity_score"] >= 0.6) & (pins["value_eur"] >= 500_000)

    print(f"\n  Live tenders scored:  {len(opportunities):,}")
    print(f"  Total pipeline EV:    €{opportunities['expected_value'].sum()/1e6:.1f}M")
    print(f"  Early pipeline PINs:  {len(pins):,}")
    if len(opportunities) > 0:
        top = opportunities.iloc[0]
        print(f"  Top opportunity:      {top.get('lot_name', 'N/A')[:55]}")
        print(f"                        €{top['value_eur']:,.0f} × {top['p_win']:.0%} = €{top['expected_value']:,.0f} EV")

    # ── Step 5 (optional): Write Gold tables ──────────────────
    if write_gold and spark is not None:
        print("\n[5/5] Writing Gold Delta tables...")
        spark.createDataFrame(opportunities).write.mode("overwrite").saveAsTable(GOLD_OPPORTUNITIES_TABLE)
        spark.createDataFrame(buyer_affinity).write.mode("overwrite").saveAsTable(GOLD_AFFINITY_TABLE)
        spark.createDataFrame(pins).write.mode("overwrite").saveAsTable(GOLD_PIN_TABLE)
        print(f"  Written: {GOLD_OPPORTUNITIES_TABLE}")
        print(f"  Written: {GOLD_AFFINITY_TABLE}")
        print(f"  Written: {GOLD_PIN_TABLE}")

    return {
        "opportunities": opportunities,
        "buyer_affinity": buyer_affinity,
        "model_metrics":  metrics,
        "all_scored":     all_scored,
        "pins":           pins,
    }
