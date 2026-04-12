#!/usr/bin/env python3
"""
seed_historical.py — One-time script to load 2024-2025 Cubs + all MLB player data.

Pulls from:
  - FanGraphs (via pybaseball): season pitching + batting stats for all qualified players
  - MLB Stats API: game schedules and results for Cubs
  - Statcast (via pybaseball): pitch-level data for Cubs pitchers (sampled)

Usage:
    cd backend
    python -m scripts.seed_historical
"""

import logging
import sys
import time
from datetime import date, datetime, timezone

# Ensure the backend package is importable
sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, PipelineRun
from app.services.ingestion import (
    pull_fg_pitching, pull_fg_batting, pull_statcast_range,
    load_fg_pitching_to_db, load_fg_batting_to_db, load_statcast_to_db,
    fetch_schedule, parse_mlb_api_games, upsert_games,
    compute_team_season_stats,
)
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
SEASONS = [2024, 2025]


def seed_fg_data(db, season: int):
    """Pull and load FanGraphs pitching + batting data for a season."""
    logger.info(f"=== Seeding FanGraphs data for {season} ===")

    # Pitching — low qual threshold to get more players for benchmarking
    try:
        pitching_df = pull_fg_pitching(season, qual=10)
        if pitching_df is not None and not pitching_df.empty:
            count = load_fg_pitching_to_db(pitching_df, season, db)
            logger.info(f"  Loaded {count} new pitcher records for {season} ({len(pitching_df)} total)")
        else:
            logger.warning(f"  No pitching data returned for {season}")
    except Exception as e:
        logger.error(f"  Failed to pull FG pitching for {season}: {e}")

    # Batting
    try:
        batting_df = pull_fg_batting(season, qual=30)
        if batting_df is not None and not batting_df.empty:
            count = load_fg_batting_to_db(batting_df, season, db)
            logger.info(f"  Loaded {count} new hitter records for {season} ({len(batting_df)} total)")
        else:
            logger.warning(f"  No batting data returned for {season}")
    except Exception as e:
        logger.error(f"  Failed to pull FG batting for {season}: {e}")


def seed_mlb_api_games(db, season: int):
    """Pull Cubs game schedule and results from MLB Stats API."""
    logger.info(f"=== Seeding MLB API games for {season} ===")
    try:
        start = date(season, 3, 20)  # Spring training / season start
        end = date(season, 11, 5) if season < date.today().year else date.today()

        games_data = fetch_schedule(start, end, team_id=settings.cubs_team_id)
        games = parse_mlb_api_games(games_data, db)
        count = upsert_games(games, db)
        logger.info(f"  Loaded {count} new games for {season} ({len(games)} total)")
    except Exception as e:
        logger.error(f"  Failed to pull MLB API games for {season}: {e}")


def seed_statcast_sample(db, season: int):
    """Pull a sample of Statcast pitch-level data for Cubs pitchers.

    Full Statcast pulls are large — for historical seeding we pull
    monthly chunks for the Cubs only.
    """
    logger.info(f"=== Seeding Statcast data for {season} ===")
    months = [
        (f"{season}-03-20", f"{season}-03-31"),
        (f"{season}-04-01", f"{season}-04-30"),
        (f"{season}-05-01", f"{season}-05-31"),
        (f"{season}-06-01", f"{season}-06-30"),
        (f"{season}-07-01", f"{season}-07-31"),
        (f"{season}-08-01", f"{season}-08-31"),
        (f"{season}-09-01", f"{season}-09-30"),
    ]

    today = date.today()
    total = 0
    for start_dt, end_dt in months:
        end_date = date.fromisoformat(end_dt)
        if end_date > today:
            end_dt = today.isoformat()
        start_date = date.fromisoformat(start_dt)
        if start_date > today:
            break

        try:
            logger.info(f"  Pulling Statcast: {start_dt} to {end_dt}")
            df = pull_statcast_range(start_dt, end_dt, team="CHC")
            if df is not None and not df.empty:
                count = load_statcast_to_db(df, season, db)
                total += count
                logger.info(f"  Loaded {count} pitches for {start_dt} to {end_dt}")
            else:
                logger.info(f"  No Statcast data for {start_dt} to {end_dt}")
            # Rate limiting — be nice to Baseball Savant
            time.sleep(5)
        except Exception as e:
            logger.error(f"  Failed Statcast pull {start_dt} to {end_dt}: {e}")
            time.sleep(10)

    logger.info(f"  Total Statcast pitches loaded for {season}: {total}")


def main():
    logger.info("=" * 60)
    logger.info("CubsEdge Historical Data Seed")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()

    run = PipelineRun(pipeline_name="seed_historical", status="running")
    db.add(run)
    db.commit()

    total_records = 0

    try:
        for season in SEASONS:
            logger.info(f"\n{'='*40}")
            logger.info(f"Processing season {season}")
            logger.info(f"{'='*40}")

            # 1. FanGraphs season stats (all MLB players)
            seed_fg_data(db, season)

            # 2. MLB API games (Cubs schedule + results)
            seed_mlb_api_games(db, season)

            # 3. Statcast pitch-level data (Cubs)
            seed_statcast_sample(db, season)

            # 4. Compute team aggregate stats
            logger.info(f"  Computing team season stats for CHC {season}...")
            compute_team_season_stats("CHC", season, db)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.records_processed = total_records
        db.commit()

        logger.info("\n" + "=" * 60)
        logger.info("Historical seed complete!")
        logger.info("=" * 60)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
