#!/usr/bin/env python3
"""
statcast_backfill.py — Morning-after Statcast data backfill.

Finds games in the database that are marked Final but don't have Statcast data
loaded yet, and pulls the pitch-level data from Baseball Savant.

Statcast data is typically available ~24 hours after a game.

Usage:
    cd backend
    python -m scripts.statcast_backfill
    python -m scripts.statcast_backfill --days 3   # Backfill last 3 days
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, Game, PipelineRun
from app.services.ingestion import pull_statcast_range, load_statcast_to_db
from app.services.benchmark_engine import compute_pitch_type_benchmarks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_games_needing_statcast(db, lookback_days: int = 7) -> list[Game]:
    """Find final Cubs games without Statcast data loaded."""
    cutoff = date.today() - timedelta(days=lookback_days)
    games = db.query(Game).filter(
        Game.status == "final",
        Game.statcast_loaded == False,
        Game.game_date >= cutoff,
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
    ).order_by(Game.game_date.asc()).all()
    return games


def backfill_game(game: Game, db) -> int:
    """Pull Statcast data for a specific game date and load it."""
    date_str = game.game_date.isoformat()
    logger.info(f"  Backfilling Statcast for {date_str} (game {game.game_pk})...")

    try:
        df = pull_statcast_range(date_str, date_str, team="CHC")
        if df is not None and not df.empty:
            count = load_statcast_to_db(df, game.season, db)
            game.statcast_loaded = True
            db.commit()
            logger.info(f"  Loaded {count} pitches for {date_str}")
            return count
        else:
            logger.warning(f"  No Statcast data available for {date_str} — may need more time")
            return 0
    except Exception as e:
        logger.error(f"  Failed to backfill {date_str}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Statcast data backfill")
    parser.add_argument("--days", type=int, default=7, help="Lookback days (default: 7)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    run = PipelineRun(pipeline_name="statcast_backfill", status="running")
    db.add(run)
    db.commit()

    try:
        games = find_games_needing_statcast(db, lookback_days=args.days)
        logger.info(f"Found {len(games)} games needing Statcast backfill")

        total_pitches = 0
        games_filled = 0

        for game in games:
            count = backfill_game(game, db)
            if count > 0:
                total_pitches += count
                games_filled += 1
            # Rate limiting
            time.sleep(5)

        # If we loaded new Statcast data, refresh pitch-type benchmarks
        if total_pitches > 0:
            season = date.today().year
            logger.info(f"Refreshing pitch-type benchmarks for {season}...")
            compute_pitch_type_benchmarks(season, db)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.records_processed = total_pitches
        db.commit()

        logger.info(f"Backfill complete: {games_filled} games, {total_pitches} pitches")

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Backfill failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
