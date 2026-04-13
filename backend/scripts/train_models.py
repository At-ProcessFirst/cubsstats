#!/usr/bin/env python3
"""
train_models.py — Train all ML models and generate predictions.

Loads 2024-2025 game data from the database, trains models, saves them
to disk, then generates predictions for upcoming 2026 Cubs games.

Usage:
    cd backend
    python -m scripts.train_models

Run AFTER seed_historical.py and seed_benchmarks.py have populated the DB.
"""

import logging
import sys
from datetime import date

sys.path.insert(0, ".")

from app.models.database import (
    SessionLocal, init_db, Game, TeamSeasonStats,
    PitcherSeasonStats, HitterSeasonStats,
)
from app.services.ml_engine import (
    train_game_outcome_model, train_win_trend_model,
    predict_game_outcome, predict_win_trend,
    detect_regression_flags, get_model_status, train_all_models,
)
from app.services.features import (
    build_game_features, build_training_dataset, build_trend_features,
    compute_player_zscores, FEATURE_LABELS, GAME_OUTCOME_FEATURE_NAMES,
    _get_cubs_games, _rolling_pythag, _opponent_win_pct,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def show_data_summary(db):
    """Print what training data is available."""
    logger.info("=" * 60)
    logger.info("DATA SUMMARY")
    logger.info("=" * 60)
    for season in [2024, 2025, 2026]:
        games = db.query(Game).filter(
            Game.season == season, Game.status == "final",
            ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        ).count()
        pitchers = db.query(PitcherSeasonStats).filter(
            PitcherSeasonStats.season == season, PitcherSeasonStats.team == "CHC",
        ).count()
        hitters = db.query(HitterSeasonStats).filter(
            HitterSeasonStats.season == season, HitterSeasonStats.team == "CHC",
        ).count()
        ts = db.query(TeamSeasonStats).filter(
            TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season,
        ).first()
        record = f"{ts.wins}-{ts.losses}" if ts else "N/A"
        logger.info(f"  {season}: {games} games, {pitchers} pitchers, {hitters} hitters, record={record}")


def show_training_data(db):
    """Show feature dataset sizes."""
    logger.info("\nFEATURE DATASETS")
    logger.info("-" * 40)
    for season in [2024, 2025]:
        df = build_training_dataset(season, db)
        rows = len(df) if df is not None else 0
        logger.info(f"  {season} game outcome features: {rows} rows")

    for season in [2024, 2025]:
        df = build_trend_features(season, db)
        rows = len(df) if df is not None else 0
        logger.info(f"  {season} win trend features: {rows} windows")


def train_and_report(db):
    """Train all models and print results."""
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING MODELS")
    logger.info("=" * 60)

    results = train_all_models(db)

    for name, result in results.items():
        status = result.get("status", "unknown")
        logger.info(f"\n  {name}: {status.upper()}")

        if "cv_accuracy" in result:
            logger.info(f"    CV Accuracy: {result['cv_accuracy']:.1%} (baseline: 50% coin flip)")
            logger.info(f"    Training samples: {result.get('samples', 0)} games")

        if "cv_mae" in result:
            logger.info(f"    CV MAE: ±{result['cv_mae']:.2f} wins (baseline: ±2.1 Pythagorean)")
            logger.info(f"    Training samples: {result.get('samples', 0)} windows")

        if "feature_importance" in result:
            logger.info("    Feature importance (top 5):")
            sorted_fi = sorted(result["feature_importance"].items(), key=lambda x: x[1], reverse=True)
            for feat, imp in sorted_fi[:5]:
                label = FEATURE_LABELS.get(feat, feat)
                logger.info(f"      {label} ({feat}): {imp:.3f}")

    return results


def generate_predictions(db):
    """Generate predictions for upcoming Cubs games."""
    logger.info("\n" + "=" * 60)
    logger.info("PREDICTIONS FOR UPCOMING GAMES")
    logger.info("=" * 60)

    season = date.today().year

    # Find scheduled games
    upcoming = db.query(Game).filter(
        Game.game_date >= date.today(),
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        Game.status == "scheduled",
    ).order_by(Game.game_date.asc()).limit(10).all()

    if not upcoming:
        # Use most recent final games to show the model works
        logger.info("  No upcoming scheduled games found.")
        logger.info("  Showing predictions for most recent completed games (backtest):")

        recent = db.query(Game).filter(
            Game.season == season, Game.status == "final",
            ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        ).order_by(Game.game_date.desc()).limit(5).all()

        correct = 0
        total = 0
        for game in reversed(recent):
            features = build_game_features(game.game_pk, db)
            if features is None:
                continue
            result = predict_game_outcome(features)
            if result.get("status") == "model_not_trained":
                logger.info("    Model not trained — run training first")
                return

            prob = result.get("win_probability", 0.5)
            predicted_win = prob > 0.5
            actual_win = game.cubs_won
            match = "✓" if predicted_win == actual_win else "✗"
            opp = game.away_team if game.home_team == "CHC" else game.home_team
            loc = "vs" if game.home_team == "CHC" else "@"
            actual_str = "W" if actual_win else "L"

            logger.info(f"    {game.game_date} {loc} {opp}: {prob:.1%} win → predicted {'W' if predicted_win else 'L'}, actual {actual_str} {match}")
            total += 1
            if predicted_win == actual_win:
                correct += 1

        if total:
            logger.info(f"    Backtest: {correct}/{total} correct ({correct/total:.0%})")
    else:
        cubs_stats = db.query(TeamSeasonStats).filter(
            TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season,
        ).first()

        for game in upcoming:
            features = build_game_features(game.game_pk, db)
            if features is None:
                opp = game.away_team if game.home_team == "CHC" else game.home_team
                features = {
                    "rolling_10g_fip": cubs_stats.team_fip or 4.0 if cubs_stats else 4.0,
                    "rolling_10g_wrc_plus": cubs_stats.team_wrc_plus or 100.0 if cubs_stats else 100.0,
                    "team_oaa": 0.0,
                    "run_diff_10g": ((cubs_stats.run_diff or 0) / max(1, cubs_stats.games_played or 1)) * 10 if cubs_stats else 0,
                    "is_home": 1.0 if game.home_team == "CHC" else 0.0,
                    "opponent_win_pct": _opponent_win_pct(opp, season, db),
                    "rest_days": 1.0,
                    "bullpen_usage_3d": 0.0,
                }

            result = predict_game_outcome(features)
            prob = result.get("win_probability", 0.5)
            opp = game.away_team if game.home_team == "CHC" else game.home_team
            loc = "vs" if game.home_team == "CHC" else "@"
            logger.info(f"    {game.game_date} {loc} {opp}: {prob:.1%} win probability")


def run_regression_detection(db):
    """Run regression detection and show flags."""
    logger.info("\n" + "=" * 60)
    logger.info("REGRESSION DETECTION (2026 vs benchmarks)")
    logger.info("=" * 60)

    season = date.today().year
    result = detect_regression_flags(season, db)

    logger.info(f"  Players analyzed: {result.get('total_players_analyzed', 0)}")
    logger.info(f"  Flags raised: {result.get('total_flags', 0)}")

    for flag in result.get("flags", [])[:10]:
        direction = "↓ DECLINE" if flag["direction"] == "likely_decline" else "↑ IMPROVE" if flag["direction"] == "likely_improve" else "→ MEAN"
        logger.info(
            f"    {flag['player_name']} — {flag['stat_name'].upper()}: "
            f"{flag['value']} (MLB avg: {flag['mlb_mean']}) "
            f"z={flag['z_score']:+.1f} → {flag['regression_probability']:.0%} regression prob {direction}"
        )


def main():
    logger.info("=" * 60)
    logger.info("CubsStats ML Model Training Pipeline")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()

    try:
        # 1. Show available data
        show_data_summary(db)

        # 2. Show feature dataset sizes
        show_training_data(db)

        # 3. Train models
        train_and_report(db)

        # 4. Generate predictions
        generate_predictions(db)

        # 5. Run regression detection
        run_regression_detection(db)

        # 6. Final status
        status = get_model_status()
        logger.info("\n" + "=" * 60)
        logger.info("FINAL MODEL STATUS")
        logger.info("=" * 60)
        for name, info in status.items():
            s = info.get("status", "unknown").upper()
            extra = ""
            if info.get("cv_accuracy"):
                extra = f" (accuracy: {info['cv_accuracy']:.1%})"
            elif info.get("cv_mae"):
                extra = f" (MAE: ±{info['cv_mae']:.2f})"
            logger.info(f"  {name}: {s}{extra}")

    except Exception as e:
        logger.error(f"Training pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
