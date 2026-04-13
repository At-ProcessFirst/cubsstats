"""
ML engine — model training, evaluation, persistence, and prediction.

Three models:
  1. Game Outcome: XGBoost classifier (win/loss per game)
  2. Win Trend: Ridge regression (next-10-game win total ± CI)
  3. Regression Detection: z-score anomaly detection (from features.py)

Models are persisted to disk via joblib and loaded at prediction time.
"""

import logging
import os
import json
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import joblib
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
GAME_OUTCOME_PATH = os.path.join(MODEL_DIR, "game_outcome.joblib")
WIN_TREND_PATH = os.path.join(MODEL_DIR, "win_trend.joblib")
MODEL_META_PATH = os.path.join(MODEL_DIR, "model_meta.json")


def _ensure_model_dir():
    os.makedirs(MODEL_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Model 1: Game Outcome (XGBoost classifier)
# ---------------------------------------------------------------------------

def train_game_outcome_model(db: Session) -> dict:
    """Train XGBoost game outcome classifier from historical data.

    Returns training metadata (accuracy, feature importance, etc).
    """
    from sklearn.model_selection import cross_val_score
    from app.services.features import build_training_dataset, GAME_OUTCOME_FEATURE_NAMES

    _ensure_model_dir()

    # Build dataset from available seasons
    frames = []
    current_year = date.today().year
    for season in range(current_year - 2, current_year + 1):
        df = build_training_dataset(season, db)
        if df is not None and len(df) >= 20:
            frames.append(df)

    if not frames:
        logger.warning("No training data available for game outcome model")
        return {"status": "no_data", "games": 0}

    dataset = pd.concat(frames, ignore_index=True)
    logger.info(f"Game outcome training data: {len(dataset)} games")

    X = dataset[GAME_OUTCOME_FEATURE_NAMES].fillna(0)
    y = dataset["target"]

    if len(X) < 30:
        logger.warning(f"Only {len(X)} samples — minimum 30 needed")
        return {"status": "limited_data", "games": len(X)}

    # Try XGBoost first, fall back to sklearn GradientBoosting
    try:
        from xgboost import XGBClassifier
        model = XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric="logloss", random_state=42,
        )
        model_name = "XGBoost"
    except (ImportError, Exception) as e:
        logger.info(f"XGBoost unavailable ({e}), using GradientBoosting fallback")
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=42,
        )
        model_name = "GradientBoosting"

    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=min(5, len(X) // 10), scoring="accuracy")
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())
    logger.info(f"Game outcome CV accuracy: {cv_mean:.3f} ± {cv_std:.3f}")

    # Train on full data
    model.fit(X, y)

    # Feature importance
    importance = dict(zip(GAME_OUTCOME_FEATURE_NAMES, model.feature_importances_.tolist()))

    # Save model
    joblib.dump(model, GAME_OUTCOME_PATH)

    meta = {
        "game_outcome": {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "samples": len(X),
            "cv_accuracy": round(cv_mean, 4),
            "cv_std": round(cv_std, 4),
            "feature_importance": {k: round(v, 4) for k, v in importance.items()},
            "status": "trained",
        }
    }
    _update_model_meta(meta)

    logger.info(f"Game outcome model saved to {GAME_OUTCOME_PATH}")
    return meta["game_outcome"]


def predict_game_outcome(features: dict) -> dict:
    """Predict game outcome using trained XGBoost model.

    Returns { status, win_probability, confidence, feature_importance }.
    """
    from app.services.features import GAME_OUTCOME_FEATURE_NAMES

    if not os.path.exists(GAME_OUTCOME_PATH):
        return {"status": "model_not_trained", "win_probability": None}

    try:
        model = joblib.load(GAME_OUTCOME_PATH)
    except Exception as e:
        logger.error(f"Failed to load game outcome model: {e}")
        return {"status": "model_error", "win_probability": None}

    # Build feature array
    X = np.array([[features.get(f, 0.0) for f in GAME_OUTCOME_FEATURE_NAMES]])
    prob = model.predict_proba(X)[0]
    win_prob = float(prob[1]) if len(prob) > 1 else float(prob[0])

    # Load feature importance from metadata
    meta = _load_model_meta()
    importance = meta.get("game_outcome", {}).get("feature_importance", {})

    return {
        "status": "active",
        "win_probability": round(win_prob, 4),
        "confidence": round(abs(win_prob - 0.5) * 2, 4),  # 0 = uncertain, 1 = very confident
        "feature_importance": importance,
        "baselines": {
            "coin_flip": 0.50,
            "typical_home_advantage": 0.54,
        },
    }


# ---------------------------------------------------------------------------
# Model 2: Win Trend (Ridge regression)
# ---------------------------------------------------------------------------

def train_win_trend_model(db: Session) -> dict:
    """Train Ridge regression for next-10-game win total prediction.

    Returns training metadata.
    """
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import cross_val_score
    from app.services.features import build_trend_features, WIN_TREND_FEATURE_NAMES

    _ensure_model_dir()

    frames = []
    current_year = date.today().year
    for season in range(current_year - 2, current_year + 1):
        df = build_trend_features(season, db)
        if df is not None and len(df) >= 10:
            frames.append(df)

    if not frames:
        logger.warning("No training data for win trend model")
        return {"status": "no_data", "windows": 0}

    dataset = pd.concat(frames, ignore_index=True)
    logger.info(f"Win trend training data: {len(dataset)} windows")

    X = dataset[WIN_TREND_FEATURE_NAMES].fillna(0)
    y = dataset["target"]

    if len(X) < 15:
        logger.warning(f"Only {len(X)} samples — need 15+")
        return {"status": "limited_data", "windows": len(X)}

    model = Ridge(alpha=1.0)

    cv_scores = cross_val_score(model, X, y, cv=min(5, len(X) // 5), scoring="neg_mean_absolute_error")
    cv_mae = float(-cv_scores.mean())
    logger.info(f"Win trend CV MAE: {cv_mae:.2f} wins")

    model.fit(X, y)

    # Compute residual std for confidence intervals
    preds = model.predict(X)
    residuals = y.values - preds
    residual_std = float(np.std(residuals))

    # Feature coefficients as importance
    coefs = dict(zip(WIN_TREND_FEATURE_NAMES, model.coef_.tolist()))

    # Save
    save_data = {"model": model, "residual_std": residual_std}
    joblib.dump(save_data, WIN_TREND_PATH)

    meta = {
        "win_trend": {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "samples": len(X),
            "cv_mae": round(cv_mae, 3),
            "residual_std": round(residual_std, 3),
            "feature_coefficients": {k: round(v, 4) for k, v in coefs.items()},
            "status": "trained",
        }
    }
    _update_model_meta(meta)

    logger.info(f"Win trend model saved to {WIN_TREND_PATH}")
    return meta["win_trend"]


def predict_win_trend(features: dict) -> dict:
    """Predict next-10-game win total with confidence interval.

    Returns { status, predicted_wins, ci_lower, ci_upper, avg_error }.
    """
    from app.services.features import WIN_TREND_FEATURE_NAMES

    if not os.path.exists(WIN_TREND_PATH):
        return {"status": "model_not_trained", "predicted_wins": None, "ci_lower": None, "ci_upper": None}

    try:
        save_data = joblib.load(WIN_TREND_PATH)
        model = save_data["model"]
        residual_std = save_data["residual_std"]
    except Exception as e:
        logger.error(f"Failed to load win trend model: {e}")
        return {"status": "model_error", "predicted_wins": None, "ci_lower": None, "ci_upper": None}

    X = np.array([[features.get(f, 0.0) for f in WIN_TREND_FEATURE_NAMES]])
    pred = float(model.predict(X)[0])
    pred = max(0, min(10, pred))  # Clamp to [0, 10]

    ci_width = 1.96 * residual_std  # 95% CI

    meta = _load_model_meta()
    cv_mae = meta.get("win_trend", {}).get("cv_mae")

    return {
        "status": "active",
        "predicted_wins": round(pred, 1),
        "ci_lower": round(max(0, pred - ci_width), 1),
        "ci_upper": round(min(10, pred + ci_width), 1),
        "avg_error": f"±{cv_mae:.1f} wins" if cv_mae else None,
        "pythagorean_error": "±2.1 wins",  # Baseline from literature
    }


# ---------------------------------------------------------------------------
# Model 3: Regression Detection (z-score based — logic in features.py)
# ---------------------------------------------------------------------------

def detect_regression_flags(season: int, db: Session) -> dict:
    """Run regression detection using z-score anomaly detection.

    This delegates to features.compute_player_zscores and formats the output.
    """
    from app.services.features import compute_player_zscores

    zscores = compute_player_zscores(season, db)

    # Filter to significant flags (|z| >= 1.5 or regression_prob >= 0.4)
    flags = [z for z in zscores if abs(z["z_score"]) >= 1.5 or z["regression_probability"] >= 0.4]

    # Build plain English explanations
    for flag in flags:
        flag["explanation"] = _build_regression_explanation(flag)

    return {
        "status": "active" if zscores else "no_data",
        "flags": flags,
        "total_players_analyzed": len(set(z["player_id"] for z in zscores)),
        "total_flags": len(flags),
        "accuracy_target": "7 of 10 flags prove correct within 30 days",
    }


def _build_regression_explanation(flag: dict) -> str:
    """Build a plain English explanation for a regression flag."""
    name = flag["player_name"]
    stat = flag["stat_name"].upper().replace("_", " ")
    val = flag["value"]
    mean = flag["mlb_mean"]
    z = flag["z_score"]
    prob = flag["regression_probability"]
    direction = flag["direction"]

    if direction == "likely_decline":
        return (
            f"{name}'s {stat} ({val}) is {abs(z):.1f} standard deviations above MLB average ({mean}). "
            f"{int(prob * 100)}% chance this regresses toward the mean."
        )
    elif direction == "likely_improve":
        return (
            f"{name}'s {stat} ({val}) is {abs(z):.1f} standard deviations below MLB average ({mean}). "
            f"{int(prob * 100)}% chance this improves toward the mean."
        )
    else:
        return (
            f"{name}'s {stat} ({val}) vs MLB average ({mean}): z-score of {z:.1f}. "
            f"Regression probability: {int(prob * 100)}%."
        )


# ---------------------------------------------------------------------------
# Model metadata persistence
# ---------------------------------------------------------------------------

def _load_model_meta() -> dict:
    """Load model metadata from disk."""
    if not os.path.exists(MODEL_META_PATH):
        return {}
    try:
        with open(MODEL_META_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _update_model_meta(updates: dict):
    """Merge updates into model metadata file."""
    _ensure_model_dir()
    meta = _load_model_meta()
    meta.update(updates)
    with open(MODEL_META_PATH, "w") as f:
        json.dump(meta, f, indent=2)


def get_model_status() -> dict:
    """Get status of all models for the API.

    Checks both the metadata file AND the existence of model files on disk,
    so status is accurate even if meta and files get out of sync.
    """
    meta = _load_model_meta()

    game_outcome = meta.get("game_outcome", {})
    win_trend = meta.get("win_trend", {})

    # If joblib files exist but meta says untrained, the meta is stale
    go_status = game_outcome.get("status", "model_not_trained")
    if go_status == "model_not_trained" and os.path.exists(GAME_OUTCOME_PATH):
        go_status = "trained"

    wt_status = win_trend.get("status", "model_not_trained")
    if wt_status == "model_not_trained" and os.path.exists(WIN_TREND_PATH):
        wt_status = "trained"

    return {
        "game_outcome": {
            "status": go_status,
            "trained_at": game_outcome.get("trained_at"),
            "cv_accuracy": game_outcome.get("cv_accuracy"),
            "samples": game_outcome.get("samples", 0),
            "feature_importance": game_outcome.get("feature_importance", {}),
        },
        "win_trend": {
            "status": wt_status,
            "trained_at": win_trend.get("trained_at"),
            "cv_mae": win_trend.get("cv_mae"),
            "samples": win_trend.get("samples", 0),
            "feature_coefficients": win_trend.get("feature_coefficients", {}),
        },
        "regression_detection": {
            "status": "active",
            "method": "z-score anomaly detection",
        },
    }


def train_all_models(db: Session) -> dict:
    """Train all ML models. Called by weekly_refresh.py."""
    results = {}

    logger.info("Training Game Outcome model (XGBoost)...")
    results["game_outcome"] = train_game_outcome_model(db)

    logger.info("Training Win Trend model (Ridge)...")
    results["win_trend"] = train_win_trend_model(db)

    logger.info("Regression Detection uses z-scores — no training needed")
    results["regression_detection"] = {"status": "active", "method": "z-score"}

    return results
