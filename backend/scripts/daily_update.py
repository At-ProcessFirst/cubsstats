#!/usr/bin/env python3
"""
daily_update.py — Two-pass post-game data pipeline.

Pass 1 (immediate, triggered by game_watcher or cron):
  - Pull box score from MLB Stats API
  - Update game results, pitcher/hitter game stats
  - Recompute team aggregate stats
  - Refresh Cubs player percentile ranks

Pass 2 (morning after, ~6 AM CT):
  - Pull Statcast pitch-level data for yesterday's games
  - Refresh FanGraphs season stats (advanced metrics)
  - Rerun divergence detection
  - Refresh pitch-type benchmarks if it's a weekly refresh day

Usage:
    cd backend
    python -m scripts.daily_update           # Run both passes
    python -m scripts.daily_update --pass1   # Box score only
    python -m scripts.daily_update --pass2   # Statcast + advanced only
"""

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, PipelineRun, Game
from app.services.ingestion import (
    fetch_schedule, parse_mlb_api_games, upsert_games,
    fetch_boxscore, parse_boxscore_pitchers, parse_boxscore_hitters,
    compute_team_season_stats,
    pull_mlb_pitching_stats, pull_mlb_batting_stats,
    load_mlb_pitching_to_db, load_mlb_batting_to_db,
    pull_statcast_range, load_statcast_to_db,
    refresh_team_strength,
)
from app.services.benchmark_engine import refresh_player_benchmarks
from app.services.divergence_engine import detect_pitcher_divergences, detect_hitter_divergences
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


def run_pass1(db, target_date: date = None):
    """Pass 1: Box score data from MLB Stats API."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    season = target_date.year
    logger.info(f"=== Pass 1: Box score pull for {target_date} ===")

    # Fetch games
    games_data = fetch_schedule(target_date, target_date, team_id=settings.cubs_team_id)
    if not games_data:
        logger.info("No Cubs games on this date.")
        return 0

    games = parse_mlb_api_games(games_data, db)
    upsert_games(games, db)

    count = 0
    for game_data in games_data:
        game_pk = game_data["gamePk"]
        status = game_data.get("status", {}).get("abstractGameState", "Preview")
        if status != "Final":
            continue

        logger.info(f"  Processing box score for game {game_pk}...")
        try:
            boxscore = fetch_boxscore(game_pk)
            home_team = game_data.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
            cubs_key = "home" if "Cubs" in home_team else "away"

            parse_boxscore_pitchers(boxscore, game_pk, target_date, season, cubs_key, db)
            parse_boxscore_hitters(boxscore, game_pk, target_date, season, cubs_key, db)
            count += 1
        except Exception as e:
            logger.error(f"  Box score failed for {game_pk}: {e}")

    # Update team stats
    compute_team_season_stats("CHC", season, db)

    # Refresh league-wide team strength (for ML opponent feature)
    try:
        refresh_team_strength(season, db)
    except Exception as e:
        logger.error(f"  Team strength refresh failed: {e}")

    # Refresh player percentiles
    refresh_player_benchmarks(season, db, cubs_only=True)

    # Generate post-game editorial for each completed game
    for game_data in games_data:
        game_pk = game_data["gamePk"]
        status = game_data.get("status", {}).get("abstractGameState", "Preview")
        if status == "Final":
            try:
                from app.services.editorial_engine import generate_daily_takeaway
                editorial = generate_daily_takeaway(game_pk, db)
                if editorial:
                    logger.info(f"  Generated editorial for game {game_pk}: {editorial.title}")
            except Exception as e:
                logger.error(f"  Editorial generation failed for {game_pk}: {e}")

    logger.info(f"Pass 1 complete: processed {count} games")
    return count


def run_pass2(db, target_date: date = None):
    """Pass 2: Statcast + advanced stats (morning after)."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    season = target_date.year
    logger.info(f"=== Pass 2: Statcast + advanced stats for {target_date} ===")

    # 1. Pull Statcast data for yesterday
    try:
        date_str = target_date.isoformat()
        logger.info(f"  Pulling Statcast data for {date_str}...")
        df = pull_statcast_range(date_str, date_str, team="CHC")
        if df is not None and not df.empty:
            count = load_statcast_to_db(df, season, db)
            logger.info(f"  Loaded {count} Statcast pitches")

            # Mark games as statcast-loaded
            game_pks = df["game_pk"].unique() if "game_pk" in df.columns else []
            for gp in game_pks:
                game = db.query(Game).filter(Game.game_pk == int(gp)).first()
                if game:
                    game.statcast_loaded = True
            db.commit()
        else:
            logger.info("  No Statcast data available yet")
    except Exception as e:
        logger.error(f"  Statcast pull failed: {e}")

    # 2. Refresh MLB Stats API season stats
    try:
        logger.info("  Refreshing MLB API pitching stats...")
        pitching_records = pull_mlb_pitching_stats(season)
        load_mlb_pitching_to_db(pitching_records, season, db)

        logger.info("  Refreshing MLB API batting stats...")
        batting_records = pull_mlb_batting_stats(season)
        load_mlb_batting_to_db(batting_records, season, db)
    except Exception as e:
        logger.error(f"  MLB API stats refresh failed: {e}")

    # 3. Recompute team stats with updated data
    compute_team_season_stats("CHC", season, db)

    # 4. Refresh player percentiles
    refresh_player_benchmarks(season, db, cubs_only=True)

    # 5. Run divergence detection
    logger.info("  Running divergence detection...")
    p_divs = detect_pitcher_divergences(season, db)
    h_divs = detect_hitter_divergences(season, db)
    logger.info(f"  Found {p_divs} pitcher divergences, {h_divs} hitter divergences")

    logger.info("Pass 2 complete")


def main():
    parser = argparse.ArgumentParser(description="CubsStats daily update pipeline")
    parser.add_argument("--pass1", action="store_true", help="Run Pass 1 only (box scores)")
    parser.add_argument("--pass2", action="store_true", help="Run Pass 2 only (Statcast + advanced)")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD), defaults to yesterday")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    target_date = date.fromisoformat(args.date) if args.date else None

    run = PipelineRun(pipeline_name="daily_update", status="running")
    db.add(run)
    db.commit()

    try:
        if args.pass1:
            run_pass1(db, target_date)
        elif args.pass2:
            run_pass2(db, target_date)
        else:
            run_pass1(db, target_date)
            run_pass2(db, target_date)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Daily update pipeline complete!")

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Daily update failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
