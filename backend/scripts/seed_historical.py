#!/usr/bin/env python3
"""
seed_historical.py — One-time script to load 2024-2025 Cubs + all MLB player data.

Pulls from:
  - MLB Stats API: league-wide pitching + batting season stats, game schedules
  - Statcast (via pybaseball): pitch-level data for Cubs pitchers

FanGraphs is NOT used — returns 403 from cloud IPs.

Usage:
    cd backend
    python -m scripts.seed_historical
"""

import logging
import sys
import time
from datetime import date, datetime, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, PipelineRun
from app.services.ingestion import (
    pull_mlb_pitching_stats, pull_mlb_batting_stats,
    load_mlb_pitching_to_db, load_mlb_batting_to_db,
    pull_statcast_range, load_statcast_to_db,
    fetch_schedule, parse_mlb_api_games, upsert_games,
    compute_team_season_stats,
)
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
SEASONS = [2024, 2025]


def seed_mlb_api_player_stats(db, season: int):
    """Pull and load league-wide pitching + batting stats from MLB Stats API."""
    logger.info(f"=== Seeding MLB Stats API player data for {season} ===")

    try:
        pitching_records = pull_mlb_pitching_stats(season)
        count = load_mlb_pitching_to_db(pitching_records, season, db)
        logger.info(f"  Loaded {count} new pitcher records ({len(pitching_records)} total from API)")
    except Exception as e:
        logger.error(f"  MLB API pitching pull failed for {season}: {e}")
        db.rollback()

    try:
        batting_records = pull_mlb_batting_stats(season)
        count = load_mlb_batting_to_db(batting_records, season, db)
        logger.info(f"  Loaded {count} new hitter records ({len(batting_records)} total from API)")
    except Exception as e:
        logger.error(f"  MLB API batting pull failed for {season}: {e}")
        db.rollback()


def seed_mlb_api_games(db, season: int):
    """Pull Cubs game schedule and results from MLB Stats API."""
    logger.info(f"=== Seeding MLB API games for {season} ===")
    try:
        start = date(season, 3, 20)
        end = date(season, 11, 5) if season < date.today().year else date.today()

        games_data = fetch_schedule(start, end, team_id=settings.cubs_team_id)
        games = parse_mlb_api_games(games_data, db)
        count = upsert_games(games, db)
        logger.info(f"  Loaded {count} new games for {season} ({len(games)} total)")
    except Exception as e:
        logger.error(f"  Failed to pull MLB API games for {season}: {e}")
        db.rollback()


def seed_statcast_sample(db, season: int):
    """Pull Statcast pitch-level data for Cubs (monthly chunks)."""
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
        end_date_val = date.fromisoformat(end_dt)
        if end_date_val > today:
            end_dt = today.isoformat()
        start_date_val = date.fromisoformat(start_dt)
        if start_date_val > today:
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
            time.sleep(5)
        except Exception as e:
            logger.error(f"  Failed Statcast pull {start_dt} to {end_dt}: {e}")
            db.rollback()
            time.sleep(10)

    logger.info(f"  Total Statcast pitches loaded for {season}: {total}")


def main():
    logger.info("=" * 60)
    logger.info("CubsStats Historical Data Seed")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()

    run = PipelineRun(pipeline_name="seed_historical", status="running")
    db.add(run)
    db.commit()

    try:
        for season in SEASONS:
            logger.info(f"\n{'='*40}")
            logger.info(f"Processing season {season}")
            logger.info(f"{'='*40}")

            # 1. MLB Stats API season stats (all MLB players — replaces FanGraphs)
            seed_mlb_api_player_stats(db, season)

            # 2. MLB API games (Cubs schedule + results)
            seed_mlb_api_games(db, season)

            # 3. Statcast pitch-level data (Cubs only, via pybaseball)
            seed_statcast_sample(db, season)

            # 4. Compute team aggregate stats
            logger.info(f"  Computing team season stats for CHC {season}...")
            compute_team_season_stats("CHC", season, db)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("\n" + "=" * 60)
        logger.info("Historical seed complete!")
        logger.info("=" * 60)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
