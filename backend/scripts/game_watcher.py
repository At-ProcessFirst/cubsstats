#!/usr/bin/env python3
"""
game_watcher.py — One-shot script that checks for completed Cubs games
and runs the post-game pipeline for any new Final games.

Designed for Render cron jobs (runs once and exits). Schedule every 15 min
during game hours to catch games as they finish.

Usage:
    cd backend
    python -m scripts.game_watcher
"""

import logging
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

from app.config import get_settings
from app.models.database import SessionLocal, init_db, Game, Editorial
from app.services.ingestion import (
    fetch_schedule, parse_mlb_api_games, upsert_games,
    fetch_boxscore, parse_boxscore_pitchers, parse_boxscore_hitters,
    compute_team_season_stats, refresh_team_strength,
)
from app.services.benchmark_engine import refresh_player_benchmarks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


def process_game(game_data: dict, db) -> bool:
    """Process a single Final game — box score, team stats, editorial."""
    game_pk = game_data["gamePk"]
    today = date.today()
    season = today.year

    # Check if we already fully processed this game
    existing = db.query(Game).filter(Game.game_pk == game_pk).first()
    if existing and existing.status == "final":
        # Already in DB as final — check if team stats are current
        # by verifying the editorial exists for this game
        ed = db.query(Editorial).filter(Editorial.game_pk == game_pk).first()
        if ed:
            return False  # Already fully processed

    logger.info(f"Processing game {game_pk}...")

    # 1. Upsert game record
    games = parse_mlb_api_games([game_data], db)
    upsert_games(games, db)

    # 2. Pull box score
    game_date_str = game_data.get("officialDate") or game_data.get("gameDate", "")[:10]
    try:
        gd = date.fromisoformat(game_date_str)
    except (ValueError, TypeError):
        gd = today

    try:
        boxscore = fetch_boxscore(game_pk)
        home_team = game_data.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
        cubs_key = "home" if "Cubs" in home_team else "away"

        pitcher_count = parse_boxscore_pitchers(boxscore, game_pk, gd, season, cubs_key, db)
        hitter_count = parse_boxscore_hitters(boxscore, game_pk, gd, season, cubs_key, db)
        logger.info(f"  Box score: {pitcher_count} pitcher lines, {hitter_count} hitter lines")
    except Exception as e:
        logger.error(f"  Box score failed for {game_pk}: {e}")

    # 3. Update team stats
    compute_team_season_stats("CHC", season, db)
    logger.info("  Team stats updated")

    # 4. Refresh team strength ratings
    try:
        refresh_team_strength(season, db)
    except Exception as e:
        logger.warning(f"  Team strength refresh failed: {e}")

    # 5. Refresh player benchmarks
    try:
        refresh_player_benchmarks(season, db, cubs_only=True)
    except Exception as e:
        logger.warning(f"  Player benchmarks failed: {e}")

    # 6. Generate editorial
    try:
        from app.services.editorial_engine import generate_daily_takeaway
        editorial = generate_daily_takeaway(game_pk, db)
        if editorial:
            logger.info(f"  Editorial: {editorial.title}")
    except Exception as e:
        logger.warning(f"  Editorial failed: {e}")

    return True


def main():
    logger.info("CubsStats Game Watcher — checking for completed games")

    init_db()
    db = SessionLocal()

    try:
        # Use Central Time — Cubs are a Chicago team, Render runs UTC
        from datetime import datetime, timezone
        ct = timezone(timedelta(hours=-5))
        today = datetime.now(ct).date()
        yesterday = today - timedelta(days=1)

        processed = 0

        for check_date in [yesterday, today]:
            try:
                games_data = fetch_schedule(check_date, check_date, team_id=settings.cubs_team_id)
            except Exception as e:
                logger.error(f"Failed to fetch schedule for {check_date}: {e}")
                continue

            if not games_data:
                continue

            for game_data in games_data:
                status = game_data.get("status", {}).get("abstractGameState", "Preview")
                game_pk = game_data["gamePk"]

                if status != "Final":
                    logger.debug(f"  Game {game_pk} on {check_date}: {status} (not final)")
                    continue

                if process_game(game_data, db):
                    processed += 1

        if processed:
            logger.info(f"Processed {processed} new game(s)")
        else:
            logger.info("No new games to process")

    except Exception as e:
        logger.error(f"Game watcher failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
