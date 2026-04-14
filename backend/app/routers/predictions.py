from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.models.database import get_db, Game, TeamSeasonStats
from app.services.ml_engine import (
    predict_game_outcome, predict_win_trend,
    detect_regression_flags, get_model_status,
)
from app.services.features import (
    build_game_features, FEATURE_LABELS,
    GAME_OUTCOME_FEATURE_NAMES, WIN_TREND_FEATURE_NAMES,
    _get_cubs_games, _rolling_pythag, _opponent_win_pct,
)

router = APIRouter()


@router.get("/game-outcome")
def get_game_outcome_prediction(
    db: Session = Depends(get_db),
):
    """Predict next game outcome using trained XGBoost model.

    If no upcoming game or model not trained, returns status info.
    Display with baselines: 'Coin flip = 50%. Vegas ~55%. Our model: X%.'
    """
    season = date.today().year

    # Find the next scheduled Cubs game
    next_game = db.query(Game).filter(
        Game.game_date >= date.today(),
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        Game.status == "scheduled",
    ).order_by(Game.game_date.asc()).first()

    if not next_game:
        status = get_model_status()
        return {
            **status["game_outcome"],
            "message": "No upcoming game scheduled",
            "baselines": {"coin_flip": 0.50, "typical_home_advantage": 0.54},
        }

    features = build_game_features(next_game.game_pk, db)
    if features is None:
        # Build approximate features from team stats
        cubs_stats = db.query(TeamSeasonStats).filter(
            TeamSeasonStats.team == "CHC",
            TeamSeasonStats.season == season,
        ).first()

        opp = next_game.away_team if next_game.home_team == "CHC" else next_game.home_team
        features = {
            "rolling_10g_fip": cubs_stats.team_fip if cubs_stats else 4.00,
            "rolling_10g_wrc_plus": cubs_stats.team_wrc_plus if cubs_stats else 100.0,
            "team_oaa": 0.0,
            "run_diff_10g": (cubs_stats.run_diff or 0) / max(1, (cubs_stats.games_played or 1)) * 10 if cubs_stats else 0,
            "is_home": 1.0 if next_game.home_team == "CHC" else 0.0,
            "opponent_win_pct": _opponent_win_pct(opp, season, db),
            "rest_days": 1.0,
            "bullpen_usage_3d": 0.0,
        }

    result = predict_game_outcome(features)
    result["game"] = {
        "game_pk": next_game.game_pk,
        "date": next_game.game_date.isoformat(),
        "opponent": next_game.away_team if next_game.home_team == "CHC" else next_game.home_team,
        "is_home": next_game.home_team == "CHC",
    }
    result["feature_labels"] = {k: FEATURE_LABELS.get(k, k) for k in GAME_OUTCOME_FEATURE_NAMES}
    result["feature_values"] = features
    return result


@router.get("/win-trend")
def get_win_trend_prediction(
    db: Session = Depends(get_db),
):
    """Predict next-10-game win total using Ridge regression.

    Display: 'Avg error: ±X wins. Pythagorean alone: ±Y.'
    """
    season = date.today().year

    all_games = _get_cubs_games(season, db)
    cubs_stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC",
        TeamSeasonStats.season == season,
    ).first()

    if len(all_games) < 30:
        status = get_model_status()
        return {
            **status["win_trend"],
            "message": f"Need 30+ games for trend prediction, currently {len(all_games)}",
        }

    pythag = _rolling_pythag(all_games, 30)

    features = {
        "rolling_30g_pythag_wpct": pythag or 0.500,
        "fip_trend": 0.0,
        "wrc_plus_trend": 0.0,
        "roster_war": 0.0,
        "sos_remaining": 0.500,
    }

    result = predict_win_trend(features)
    result["current_record"] = {
        "wins": cubs_stats.wins if cubs_stats else 0,
        "losses": cubs_stats.losses if cubs_stats else 0,
        "games_played": len(all_games),
    }
    result["feature_labels"] = {k: FEATURE_LABELS.get(k, k) for k in WIN_TREND_FEATURE_NAMES}
    return result


@router.get("/regression-flags")
def get_regression_flags(
    db: Session = Depends(get_db),
):
    """Get players flagged for regression using z-score anomaly detection.

    Display: 'X of 10 flags prove correct within 30 days.'
    """
    season = date.today().year
    return detect_regression_flags(season, db)


@router.get("/upcoming-games")
def get_upcoming_predictions(
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Predict outcomes for ALL upcoming scheduled Cubs games."""
    season = date.today().year

    upcoming = db.query(Game).filter(
        Game.game_date >= date.today(),
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        Game.status == "scheduled",
    ).order_by(Game.game_date.asc()).limit(limit).all()

    if not upcoming:
        return {"games": []}

    cubs_stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC",
        TeamSeasonStats.season == season,
    ).first()

    all_games = _get_cubs_games(season, db)

    results = []
    for game in upcoming:
        opp = game.away_team if game.home_team == "CHC" else game.home_team
        is_home = game.home_team == "CHC"

        # Build features from available data
        features = build_game_features(game.game_pk, db)
        if features is None:
            # Compute rolling 10-game run diff from actual game results
            recent = all_games[-10:] if len(all_games) >= 10 else all_games
            rd_10 = 0
            for g in recent:
                rs = g.home_score if g.home_team == "CHC" else g.away_score
                ra = g.away_score if g.home_team == "CHC" else g.home_score
                rd_10 += (rs or 0) - (ra or 0)

            # Rest days
            rest = 1.0
            if all_games:
                rest = max(0, (game.game_date - all_games[-1].game_date).days)

            features = {
                "rolling_10g_fip": (cubs_stats.team_fip or 4.0) if cubs_stats else 4.0,
                "rolling_10g_wrc_plus": (cubs_stats.team_wrc_plus or 100.0) if cubs_stats else 100.0,
                "team_oaa": 0.0,
                "run_diff_10g": float(rd_10),
                "is_home": 1.0 if is_home else 0.0,
                "opponent_win_pct": _opponent_win_pct(opp, season, db),
                "rest_days": float(rest),
                "bullpen_usage_3d": 0.0,
            }

        prediction = predict_game_outcome(features)
        win_prob = prediction.get("win_probability")

        results.append({
            "game_pk": game.game_pk,
            "date": game.game_date.isoformat(),
            "opponent": opp,
            "is_home": is_home,
            "win_probability": win_prob,
        })

    return {"games": results}


@router.get("/model-status")
def model_status():
    """Get training status and metadata for all ML models."""
    return get_model_status()


@router.get("/feature-importance")
def feature_importance():
    """Get feature importance with plain English labels for display."""
    status = get_model_status()

    game_importance = status["game_outcome"].get("feature_importance", {})
    trend_coefficients = status["win_trend"].get("feature_coefficients", {})

    return {
        "game_outcome": {
            "features": [
                {
                    "name": k,
                    "label": FEATURE_LABELS.get(k, k),
                    "importance": game_importance.get(k, 0),
                }
                for k in GAME_OUTCOME_FEATURE_NAMES
            ],
        },
        "win_trend": {
            "features": [
                {
                    "name": k,
                    "label": FEATURE_LABELS.get(k, k),
                    "coefficient": trend_coefficients.get(k, 0),
                }
                for k in WIN_TREND_FEATURE_NAMES
            ],
        },
    }
