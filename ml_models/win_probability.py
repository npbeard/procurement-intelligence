"""
Win Probability Model

Predicts P(win) for each IT tender — the probability that Microsoft
could win this contract if they bid on it.

Since we don't have Microsoft's actual win/loss history, P(win) is a proxy:
    P(win) = f(competition_intensity, buyer_affinity, cpv_relevance)

Specifically:
  - XGBoost trained on historical award notices (where nb_tenders_received is known)
    predicts P(low competition) — fewer bidders = higher chance of winning
  - Combined with buyer affinity score and CPV-to-Microsoft relevance score
  - Final P(win) is a weighted blend of all three signals

Model persistence:
  - save_model() / load_model() use joblib to serialise model + label encoder
  - Train once on historical data, then load daily for scoring new lots
  - Default path: /dbfs/capstone/models/win_probability.pkl

Output: P(win) ∈ [0, 1] per lot, used to compute Expected Value = value × P(win)
"""

from __future__ import annotations

import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
import warnings
warnings.filterwarnings("ignore")

from ml_models.cpv_microsoft_mapping import get_cpv_relevance


LABEL_ORDER = ["Low", "Medium", "High"]

# Weights for the P(win) composite score
W_COMPETITION = 0.50  # P(low competition) from XGBoost
W_AFFINITY    = 0.30  # buyer affinity to Microsoft portfolio
W_RELEVANCE   = 0.20  # how well CPV maps to Microsoft products

DEFAULT_MODEL_PATH = "/Volumes/capstone/ted/models/win_probability.pkl"


def _competition_label(n: int) -> str:
    if n <= 2:
        return "Low"
    elif n <= 7:
        return "Medium"
    else:
        return "High"


def _add_features(df: pd.DataFrame, buyer_affinity: pd.DataFrame) -> pd.DataFrame:
    """Add all features needed by the win probability model."""
    df = df.copy()
    df["value_eur"] = df["lot_value_eur"].fillna(df["estimated_value"])

    df = df.merge(
        buyer_affinity[["buyer_org_ref", "affinity_score"]],
        on="buyer_org_ref",
        how="left",
    )
    df["affinity_score"] = df["affinity_score"].fillna(0.3)

    df["log_value"]        = np.log1p(df["value_eur"].fillna(0))
    df["cpv_relevance"]    = df["cpv_code"].astype(str).apply(get_cpv_relevance)
    df["cpv_division_enc"] = pd.Categorical(df["cpv_division"]).codes
    df["cpv_group_enc"]    = pd.Categorical(df["cpv_code"].astype(str).str[:3]).codes
    df["country_enc"]      = pd.Categorical(df["buyer_country_code"].fillna("UNKNOWN")).codes
    df["procedure_enc"]    = pd.Categorical(df["procurement_procedure"].fillna("UNKNOWN")).codes
    df["buyer_type_enc"]   = pd.Categorical(df["buyer_legal_type"].fillna("UNKNOWN")).codes

    return df


FEATURE_COLS = [
    "log_value",
    "cpv_relevance",
    "affinity_score",
    "cpv_division_enc",
    "cpv_group_enc",
    "country_enc",
    "procedure_enc",
    "buyer_type_enc",
]


# ── Model persistence ─────────────────────────────────────────────────────────

def save_model(
    model: XGBClassifier,
    le: LabelEncoder,
    metrics: dict,
    path: str = DEFAULT_MODEL_PATH,
) -> None:
    """Save trained model, label encoder, and metrics to disk."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # Unity Catalog Volumes don't support mkdir; the volume must pre-exist
    joblib.dump({"model": model, "le": le, "metrics": metrics}, path)
    print(f"  Model saved → {path}")


def load_model(path: str = DEFAULT_MODEL_PATH) -> tuple[XGBClassifier, LabelEncoder, dict] | None:
    """
    Load a previously saved model from disk.
    Returns (model, le, metrics) or None if no saved model exists.
    """
    if not os.path.exists(path):
        return None
    payload = joblib.load(path)
    print(f"  Model loaded ← {path}  (trained on {payload['metrics']['n_train']:,} samples, "
          f"accuracy {payload['metrics']['accuracy']:.1%})")
    return payload["model"], payload["le"], payload["metrics"]


def model_exists(path: str = DEFAULT_MODEL_PATH) -> bool:
    return os.path.exists(path)


# ── Training ──────────────────────────────────────────────────────────────────

def train_win_probability_model(
    df: pd.DataFrame,
    buyer_affinity: pd.DataFrame,
    save_path: str = DEFAULT_MODEL_PATH,
) -> tuple[XGBClassifier, LabelEncoder, dict]:
    """
    Train XGBoost on historical award notices to predict competition level.
    Automatically saves the model to save_path after training.
    Returns (model, label_encoder, metrics).
    """
    df = _add_features(df, buyer_affinity)

    train_df = df[
        (df["notice_type"] == "ContractAwardNotice")
        & (df["nb_tenders_received"].notna())
        & (df["nb_tenders_received"] > 0)
    ].copy()

    if len(train_df) < 100:
        raise ValueError(
            f"Only {len(train_df)} training samples — need at least 100. "
            "Make sure nb_tenders_received is populated in the Silver layer."
        )

    train_df["competition_label"] = (
        train_df["nb_tenders_received"].astype(int).apply(_competition_label)
    )

    print(f"  Training samples: {len(train_df):,}")
    print(f"  Label distribution:\n{train_df['competition_label'].value_counts().to_string()}")

    le = LabelEncoder()
    le.fit(LABEL_ORDER)
    y = le.transform(train_df["competition_label"])
    X = train_df[FEATURE_COLS].fillna(0)

    min_class_count = train_df["competition_label"].value_counts().min()
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if min_class_count >= 2 else None
        )
    except ValueError:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
        use_label_encoder=False,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred   = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report   = classification_report(y_test, y_pred, target_names=LABEL_ORDER)

    print(f"\n  Accuracy: {accuracy:.3f}")
    print(f"\n{report}")

    importance = pd.DataFrame(
        {"feature": FEATURE_COLS, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    metrics = {
        "accuracy":           accuracy,
        "report":             report,
        "feature_importance": importance,
        "n_train":            len(train_df),
    }

    save_model(model, le, metrics, path=save_path)
    return model, le, metrics


# ── Scoring (uses saved model, no retraining) ─────────────────────────────────

def score_opportunities(
    df: pd.DataFrame,
    model: XGBClassifier,
    le: LabelEncoder,
    buyer_affinity: pd.DataFrame,
) -> pd.DataFrame:
    """
    Score all lots with P(win) and Expected Value using a pre-trained model.
    Call load_model() first to get model and le without retraining.

    P(win) = W_competition × P(low competition)
           + W_affinity    × affinity_score
           + W_relevance   × cpv_relevance

    EV = value_eur × P(win)
    """
    df = _add_features(df, buyer_affinity)

    X     = df[FEATURE_COLS].fillna(0)
    proba = model.predict_proba(X)

    low_idx = list(le.classes_).index("Low")
    df["p_low_competition"] = proba[:, low_idx]

    df["p_win"] = (
        df["p_low_competition"] * W_COMPETITION
        + df["affinity_score"]  * W_AFFINITY
        + df["cpv_relevance"]   * W_RELEVANCE
    ).clip(0, 1)

    df["expected_value"] = df["value_eur"].fillna(0) * df["p_win"]

    return df
