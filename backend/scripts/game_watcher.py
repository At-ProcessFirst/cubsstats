#!/usr/bin/env python3
"""
game_watcher.py — Polls MLB Stats API to detect when a Cubs game goes Final.

When a game goes Final, triggers the post-game pipeline (Pass 1 of daily_update).
Designed to run as a long-lived process during game hours.

Usage:
    cd backend
    python -m scripts.game_watcher

How it works:
  1. Check today's Cubs schedule via MLB Stats API
  2. If a game is scheduled/live, poll every 60 seconds
  3. When status transitions to Final, run post-game pipeline
  4. After processing, exit or wait for next game (doubleheaders)
"""

import logging
import sys
import time
from datetime import date, datetime, timezone

sys.path.insert(0, ".")

from app.config import get_settings
from app.models.database import SessionLocal, init_db, Game
from app.services.ingestion import (
    fetch_schedule, parse_mlb_api_games, upsert_games,
    fetch_boxscore, parse_boxscore_pitchers, parse_boxscore_hitters,
    compute_team_season_stats,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
POLL_INTERVAL = 60  # seconds between status checks
PREGAME_POLL = 300  # seconds between checks when no game is live


def get_todays_cubs_games() -> list[dict]:
    """Fetch today's Cubs games from MLB Stats API."""
    today = date.today()
    games = fetch_schedule(today, today, team_id=settings.cubs_team_id)
    return games


def run_post_game_pipeline(game_pk: int, game_data: dict):
    """Run Pass 1 post-game pipeline — box score stats from MLB Stats API."""
    logger.info(f"=== Post-game pipeline for game {game_pk} ===")
    db = SessionLocal()

    try:
        # 1. Update game record
        game_date = date.today()
        season = game_date.year

        games = parse_mlb_api_games([game_data], db)
        upsert_games(games, db)

        # 2. Pull box score
        logger.info(f"  Fetching box score for game {game_pk}...")
        boxscore = fetch_boxscore(game_pk)

        # Determine which team key is Cubs (home or away)
        home_team = game_data.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
        cubs_key = "home" if "Cubs" in home_team else "away"

        # 3. Parse pitcher stats from box score
        pitcher_count = parse_boxscore_pitchers(
            boxscore, game_pk, game_date, season, cubs_key, db
        )
        logger.info(f"  Loaded {pitcher_count} Cubs pitcher game lines")

        # 4. Parse hitter stats from box score
        hitter_count = parse_boxscore_hitters(
            boxscore, game_pk, game_date, season, cubs_key, db
        )
        logger.info(f"  Loaded {hitter_count} Cubs hitter game lines")

        # 5. Update team aggregate stats
        compute_team_season_stats("CHC", season, db)
        logger.info("  Updated Cubs team season stats")

        # 6. Mark game as processed (statcast not yet loaded)
        game_record = db.query(Game).filter(Game.game_pk == game_pk).first()
        if game_record:
            game_record.statcast_loaded = False
            db.commit()

        logger.info(f"=== Post-game pipeline complete for {game_pk} ===")

    except Exception as e:
        logger.error(f"Post-game pipeline failed for {game_pk}: {e}")
    finally:
        db.close()


def watch():
    """Main watch loop — poll for game status and trigger pipeline."""
    init_db()
    logger.info("CubsStats Game Watcher started")
    logger.info(f"Monitoring Cubs (team ID {settings.cubs_team_id}) games...")

    processed_today = set()

    while True:
        try:
            today = date.today()
            games = get_todays_cubs_games()

            if not games:
                logger.info(f"No Cubs games today ({today}). Sleeping {PREGAME_POLL}s...")
                time.sleep(PREGAME_POLL)
                continue

            any_live = False
            for game_data in games:
                game_pk = game_data["gamePk"]
                status = game_data.get("status", {}).get("abstractGameState", "Preview")

                if game_pk in processed_today:
                    continue

                if status == "Final":
                    logger.info(f"Game {game_pk} is Final! Triggering post-game pipeline...")
                    run_post_game_pipeline(game_pk, game_data)
                    processed_today.add(game_pk)
                elif status == "Live":
                    any_live = True
                    logger.debug(f"Game {game_pk} is Live...")

            # Determine sleep interval
            if any_live:
                time.sleep(POLL_INTERVAL)
            else:
                all_processed = all(g["gamePk"] in processed_today for g in games)
                if all_processed:
                    logger.info("All today's games processed. Watcher done for today.")
                    break
                else:
                    logger.info(f"Games not yet started. Checking again in {PREGAME_POLL}s...")
                    time.sleep(PREGAME_POLL)

        except KeyboardInterrupt:
            logger.info("Game watcher stopped by user.")
            break
        except Exception as e:
            logger.error(f"Watcher error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    watch()
