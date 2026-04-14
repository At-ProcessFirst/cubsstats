"""
ML engine — model training, evaluation, persistence, and prediction.

Models are stored in the DATABASE (trained_models table) so they survive
Render deploys (ephemeral filesystem). Local file cache avoids
deserializing on every request.
"""

import logging
import os
import io
import json
import base64
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

# In-memory cache so we don't deserialize on every request
_model_cache = {}


def _ensure_model_dir():
    os.makedirs(MODEL_DIR, exist_ok=True)


def _save_model_to_db(model_name: str, model_obj, metadata: dict = None):
    """Serialize model and store in database (survives Render deploys)."""
    from app.models.database import SessionLocal, TrainedModel
    buf = io.BytesIO()
    joblib.dump(model_obj, buf)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")

    db = SessionLocal()
    try:
        existing = db.query(TrainedModel).filter(TrainedModel.model_name == model_name).first()
        if existing:
            existing.model_data = encoded
            existing.metadata_json = json.dumps(metadata) if metadata else None
            existing.trained_at = datetime.now(timezone.utc)
        else:
            db.add(TrainedModel(
                model_name=model_name,
                model_data=encoded,
                metadata_json=json.dumps(metadata) if metadata else None,
            ))
        db.commit()
        logger.info(f"Model '{model_name}' saved to database ({len(encoded)} chars)")
    except Exception as e:
        logger.error(f"Failed to save model to DB: {e}")
        db.rollback()
    finally:
        db.close()

    # Also cache in memory
    _model_cache[model_name] = model_obj


def _load_model_from_db(model_name: str):
    """Load model from database, with in-memory and disk cache."""
    # 1. Check in-memory cache
    if model_name in _model_cache:
        return _model_cache[model_name]

    # 2. Check local file cache
    file_path = GAME_OUTCOME_PATH if model_name == "game_outcome" else WIN_TREND_PATH
    if os.path.exists(file_path):
        try:
            obj = joblib.load(file_path)
            _model_cache[model_name] = obj
            return obj
        except Exception:
            pass

    # 3. Load from database
    from app.models.database import SessionLocal, TrainedModel
    db = SessionLocal()
    try:
        row = db.query(TrainedModel).filter(TrainedModel.model_name == model_name).first()
        if row and row.model_data:
            decoded = base64.b64decode(row.model_data)
            obj = joblib.load(io.BytesIO(decoded))
            _model_cache[model_name] = obj
            # Write to disk cache for next time
            _ensure_model_dir()
            try:
                joblib.dump(obj, file_path)
            except Exception:
                pass
            logger.info(f"Model '{model_name}' loaded from database")
            return obj
    except Exception as e:
        logger.error(f"Failed to load model '{model_name}' from DB: {e}")
    finally:
        db.close()

    return None


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
    # Wrap in CalibratedClassifierCV for realistic probability estimates
    from sklearn.calibration import CalibratedClassifierCV
    try:
        from xgboost import XGBClassifier
        base_model = XGBClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric="logloss", random_state=42,
        )
        model_name = "XGBoost"
    except (ImportError, Exception) as e:
        logger.info(f"XGBoost unavailable ({e}), using GradientBoosting fallback")
        from sklearn.ensemble import GradientBoostingClassifier
        base_model = GradientBoostingClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42,
        )
        model_name = "GradientBoosting"

    # Cross-validation on base model
    cv_scores = cross_val_score(base_model, X, y, cv=min(5, len(X) // 10), scoring="accuracy")
    cv_mean = float(cv_scores.mean())
    cv_std = float(cv_scores.std())
    logger.info(f"Game outcome CV accuracy: {cv_mean:.3f} ± {cv_std:.3f}")

    # Train model
    base_model.fit(X, y)
    importance = dict(zip(GAME_OUTCOME_FEATURE_NAMES, base_model.feature_importances_.tolist()))
    model = base_model
    logger.info(f"Model trained ({model_name})")

    # Save model to database (survives Render deploys) and disk cache
    _ensure_model_dir()
    joblib.dump(model, GAME_OUTCOME_PATH)
    _save_model_to_db("game_outcome", model, {
        "cv_accuracy": round(cv_mean, 4),
        "samples": len(X),
        "feature_importance": {k: round(v, 4) for k, v in importance.items()},
    })

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

    logger.info(f"Game outcome model saved to database + disk")
    return meta["game_outcome"]


def predict_game_outcome(features: dict) -> dict:
    """Predict game outcome. Loads model from DB → disk cache → memory cache."""
    from app.services.features import GAME_OUTCOME_FEATURE_NAMES

    model = _load_model_from_db("game_outcome")
    if model is None:
        return {"status": "model_not_trained", "win_probability": None}

    # Build feature array
    X = np.array([[features.get(f, 0.0) for f in GAME_OUTCOME_FEATURE_NAMES]])
    prob = model.predict_proba(X)[0]
    raw_prob = float(prob[1]) if len(prob) > 1 else float(prob[0])

    # Clamp to realistic MLB range [0.30, 0.70]
    # No game in baseball has >70% true win probability — too much variance.
    win_prob = max(0.30, min(0.70, raw_prob))

    # Load feature importance from metadata
    meta = _load_model_meta()
    importance = meta.get("game_outcome", {}).get("feature_importance", {})

    return {
        "status": "active",
        "win_probability": round(win_prob, 4),
        "confidence": round(abs(win_prob - 0.5) * 2, 4),
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

    # Save to database (survives deploys) and disk cache
    save_data = {"model": model, "residual_std": residual_std}
    _ensure_model_dir()
    joblib.dump(save_data, WIN_TREND_PATH)
    _save_model_to_db("win_trend", save_data, {
        "cv_mae": round(cv_mae, 3),
        "residual_std": round(residual_std, 3),
        "samples": len(X),
    })

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

    logger.info(f"Win trend model saved to database + disk")
    return meta["win_trend"]


def predict_win_trend(features: dict) -> dict:
    """Predict next-10-game win total with confidence interval.

    Returns { status, predicted_wins, ci_lower, ci_upper, avg_error }.
    """
    from app.services.features import WIN_TREND_FEATURE_NAMES

    save_data = _load_model_from_db("win_trend")
    if save_data is None:
        return {"status": "model_not_trained", "predicted_wins": None, "ci_lower": None, "ci_upper": None}

    try:
        model = save_data["model"]
        residual_std = save_data["residual_std"]
    except (KeyError, TypeError) as e:
        logger.error(f"Win trend model format error: {e}")
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
# Model metadata persistence (database-backed + file fallback)
# ---------------------------------------------------------------------------

def _save_model_status_to_db(model_name: str, status: str, accuracy: float = None,
                              accuracy_label: str = None, samples: int = 0,
                              feature_importance: dict = None):
    """Persist model training status to the database."""
    from app.models.database import SessionLocal, ModelStatus
    db = SessionLocal()
    try:
        existing = db.query(ModelStatus).filter(ModelStatus.model_name == model_name).first()
        if existing:
            existing.status = status
            existing.accuracy = accuracy
            existing.accuracy_label = accuracy_label
            existing.training_samples = samples
            existing.feature_importance = json.dumps(feature_importance) if feature_importance else None
            existing.trained_at = datetime.now(timezone.utc)
        else:
            db.add(ModelStatus(
                model_name=model_name, status=status,
                accuracy=accuracy, accuracy_label=accuracy_label,
                training_samples=samples,
                feature_importance=json.dumps(feature_importance) if feature_importance else None,
                trained_at=datetime.now(timezone.utc),
            ))
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to save model status to DB: {e}")
        db.rollback()
    finally:
        db.close()


def _load_model_meta() -> dict:
    """Load model metadata — tries DB first, falls back to JSON file."""
    # Try database first
    try:
        from app.models.database import SessionLocal, ModelStatus
        db = SessionLocal()
        rows = db.query(ModelStatus).all()
        db.close()
        if rows:
            meta = {}
            for r in rows:
                meta[r.model_name] = {
                    "status": r.status,
                    "trained_at": r.trained_at.isoformat() if r.trained_at else None,
                    "cv_accuracy": r.accuracy if r.model_name == "game_outcome" else None,
                    "cv_mae": r.accuracy if r.model_name == "win_trend" else None,
                    "samples": r.training_samples,
                    "feature_importance": json.loads(r.feature_importance) if r.feature_importance else {},
                }
            return meta
    except Exception:
        pass

    # Fallback to file
    if os.path.exists(MODEL_META_PATH):
        try:
            with open(MODEL_META_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _update_model_meta(updates: dict):
    """Save model metadata to both DB and file."""
    # Save to file (legacy)
    _ensure_model_dir()
    try:
        meta = {}
        if os.path.exists(MODEL_META_PATH):
            with open(MODEL_META_PATH, "r") as f:
                meta = json.load(f)
        meta.update(updates)
        with open(MODEL_META_PATH, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass

    # Save to DB
    for model_name, data in updates.items():
        _save_model_status_to_db(
            model_name=model_name,
            status=data.get("status", "active"),
            accuracy=data.get("cv_accuracy") or data.get("cv_mae"),
            accuracy_label=_make_accuracy_label(model_name, data),
            samples=data.get("samples", 0),
            feature_importance=data.get("feature_importance"),
        )


def _make_accuracy_label(model_name: str, data: dict) -> str:
    if model_name == "game_outcome" and data.get("cv_accuracy"):
        return f"{data['cv_accuracy']:.1%} accuracy"
    if model_name == "win_trend" and data.get("cv_mae"):
        return f"±{data['cv_mae']:.2f} MAE"
    return "active"


def get_model_status() -> dict:
    """Get status of all models. Checks DB trained_models table as final authority."""
    meta = _load_model_meta()

    game_outcome = meta.get("game_outcome", {})
    win_trend = meta.get("win_trend", {})

    go_status = game_outcome.get("status", "model_not_trained")
    wt_status = win_trend.get("status", "model_not_trained")

    # Check trained_models table — if model binary exists in DB, it's trained
    try:
        from app.models.database import SessionLocal, TrainedModel
        db = SessionLocal()
        for row in db.query(TrainedModel).all():
            if row.model_name == "game_outcome" and row.model_data:
                go_status = "active"
            if row.model_name == "win_trend" and row.model_data:
                wt_status = "active"
        db.close()
    except Exception:
        pass

    # File fallback
    if go_status not in ("active", "trained") and os.path.exists(GAME_OUTCOME_PATH):
        go_status = "active"
    if wt_status not in ("active", "trained") and os.path.exists(WIN_TREND_PATH):
        wt_status = "active"

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
