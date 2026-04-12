#!/usr/bin/env python3
"""
weekly_refresh.py — League-wide benchmark refresh and ML retrain placeholder.

Runs weekly (e.g., Monday at 6 AM CT) to:
  1. Re-pull ALL MLB player stats from FanGraphs (full league refresh)
  2. Recompute league-wide benchmarks (pitching, hitting, pitch-type)
  3. Recompute ALL Cubs player percentile ranks
  4. Run divergence detection
  5. Retrain ML models (Phase 5 placeholder)

Benchmark blending logic:
  - Before ~30 Cubs games: 100% prior season benchmarks
  - 30-80 games: 70% current / 30% prior
  - After 80 games: 100% current season

Usage:
    cd backend
    python -m scripts.weekly_refresh
"""

import logging
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, PipelineRun, TeamSeasonStats
from app.services.ingestion import (
    pull_fg_pitching, pull_fg_batting,
    load_fg_pitching_to_db, load_fg_batting_to_db,
    compute_team_season_stats,
)
from app.services.benchmark_engine import (
    compute_pitching_benchmarks, compute_hitting_benchmarks,
    compute_pitch_type_benchmarks, refresh_player_benchmarks,
)
from app.services.divergence_engine import detect_pitcher_divergences, detect_hitter_divergences
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


def main():
    logger.info("=" * 60)
    logger.info("CubsEdge Weekly Refresh")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()

    season = date.today().year

    run = PipelineRun(pipeline_name="weekly_refresh", status="running")
    db.add(run)
    db.commit()

    total = 0

    try:
        # 1. Refresh FanGraphs league-wide stats
        logger.info("Step 1: Pulling league-wide FanGraphs data...")
        try:
            pitching_df = pull_fg_pitching(season, qual=10)
            if pitching_df is not None:
                count = load_fg_pitching_to_db(pitching_df, season, db)
                logger.info(f"  Loaded/updated {count} pitcher records")
                total += count
        except Exception as e:
            logger.error(f"  FG pitching pull failed: {e}")

        try:
            batting_df = pull_fg_batting(season, qual=30)
            if batting_df is not None:
                count = load_fg_batting_to_db(batting_df, season, db)
                logger.info(f"  Loaded/updated {count} hitter records")
                total += count
        except Exception as e:
            logger.error(f"  FG batting pull failed: {e}")

        # 2. Recompute league-wide benchmarks
        logger.info("Step 2: Recomputing league-wide benchmarks...")
        count = compute_pitching_benchmarks(season, db)
        logger.info(f"  Pitching benchmarks: {count}")
        total += count

        count = compute_hitting_benchmarks(season, db)
        logger.info(f"  Hitting benchmarks: {count}")
        total += count

        # 3. Refresh pitch-type benchmarks
        logger.info("Step 3: Refreshing pitch-type benchmarks...")
        count = compute_pitch_type_benchmarks(season, db)
        logger.info(f"  Pitch-type benchmarks: {count}")
        total += count

        # 4. Refresh team stats
        logger.info("Step 4: Updating team aggregate stats...")
        compute_team_season_stats("CHC", season, db)

        # 5. Refresh ALL Cubs player percentile ranks
        logger.info("Step 5: Refreshing Cubs player percentile ranks...")
        count = refresh_player_benchmarks(season, db, cubs_only=True)
        logger.info(f"  Player benchmarks refreshed: {count}")
        total += count

        # 6. Run divergence detection
        logger.info("Step 6: Running divergence detection...")
        p_count = detect_pitcher_divergences(season, db)
        h_count = detect_hitter_divergences(season, db)
        logger.info(f"  Divergences: {p_count} pitcher, {h_count} hitter")

        # 7. ML model retrain
        logger.info("Step 7: Retraining ML models...")
        try:
            from app.services.ml_engine import train_all_models
            ml_results = train_all_models(db)
            for model_name, result in ml_results.items():
                status = result.get("status", "unknown")
                logger.info(f"  {model_name}: {status}")
                if "cv_accuracy" in result:
                    logger.info(f"    CV accuracy: {result['cv_accuracy']:.3f}")
                if "cv_mae" in result:
                    logger.info(f"    CV MAE: {result['cv_mae']:.2f} wins")
        except Exception as e:
            logger.error(f"  ML retrain failed: {e}")

        # 8. Generate weekly editorials
        logger.info("Step 8: Generating weekly editorials...")
        try:
            from app.services.editorial_engine import generate_weekly_state, generate_prediction_recap
            weekly = generate_weekly_state(season, db)
            if weekly:
                logger.info(f"  Weekly state editorial: {weekly.title}")
            recap = generate_prediction_recap(season, db)
            if recap:
                logger.info(f"  Prediction recap editorial: {recap.title}")

            # Player spotlights for top divergence flags
            from app.services.editorial_engine import generate_player_spotlight
            from app.models.database import DivergenceAlert
            top_alerts = db.query(DivergenceAlert).filter(
                DivergenceAlert.is_active == True,
            ).order_by(DivergenceAlert.created_at.desc()).limit(2).all()
            seen_players = set()
            for alert in top_alerts:
                if alert.player_id not in seen_players:
                    seen_players.add(alert.player_id)
                    spotlight = generate_player_spotlight(alert.player_id, season, db)
                    if spotlight:
                        logger.info(f"  Player spotlight: {spotlight.title}")
        except Exception as e:
            logger.error(f"  Editorial generation failed: {e}")

        # Log blending status
        cubs_stats = db.query(TeamSeasonStats).filter(
            TeamSeasonStats.team == "CHC",
            TeamSeasonStats.season == season,
        ).first()
        if cubs_stats:
            gp = cubs_stats.games_played
            if gp < settings.blend_start_games:
                blend_status = f"100% prior season (Cubs at {gp} games, need {settings.blend_start_games} to start blending)"
            elif gp > settings.blend_end_games:
                blend_status = f"100% current season (Cubs at {gp} games)"
            else:
                blend_status = f"70/30 current/prior blend (Cubs at {gp} games)"
            logger.info(f"  Benchmark blending: {blend_status}")

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.records_processed = total
        db.commit()

        logger.info(f"\nWeekly refresh complete! Total records processed: {total}")

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Weekly refresh failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
