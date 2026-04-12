#!/usr/bin/env python3
"""
scheduler.py — APScheduler-based cron runner for all CubsStats scheduled jobs.

Runs as a long-lived process (docker-compose scheduler service or Render worker).

Schedule (all times Central):
  ┌─────────────────────────────────────────────────────────────────────┐
  │ Job                │ Schedule                      │ Description    │
  ├─────────────────────────────────────────────────────────────────────┤
  │ game_watcher_tick  │ Every 15 min, 5PM-1AM CT      │ Poll for Final │
  │ daily_update_pass2 │ 10:00 AM CT daily              │ Statcast+adv   │
  │ statcast_backfill  │ 10:30 AM CT daily              │ Fill gaps      │
  │ weekly_refresh     │ Sunday 12:00 AM CT             │ Full refresh   │
  └─────────────────────────────────────────────────────────────────────┘

Usage:
    cd backend
    python -m scripts.scheduler
"""

import logging
import sys
import signal
from datetime import date, datetime, timedelta

sys.path.insert(0, ".")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.models.database import SessionLocal, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("cubsstats.scheduler")


# ---------------------------------------------------------------------------
# Job 1: Game watcher tick (every 15 min during game hours)
# ---------------------------------------------------------------------------

def game_watcher_tick():
    """Check if a Cubs game just went Final. If so, run post-game pipeline."""
    from app.services.ingestion import (
        fetch_schedule, parse_mlb_api_games, upsert_games,
        fetch_boxscore, parse_boxscore_pitchers, parse_boxscore_hitters,
        compute_team_season_stats,
    )
    from app.services.benchmark_engine import refresh_player_benchmarks
    from app.services.editorial_engine import generate_daily_takeaway
    from app.config import get_settings

    settings = get_settings()
    db = SessionLocal()
    try:
        today = date.today()
        games_data = fetch_schedule(today, today, team_id=settings.cubs_team_id)
        if not games_data:
            logger.debug("No Cubs games today")
            return

        season = today.year
        for game_data in games_data:
            game_pk = game_data["gamePk"]
            status = game_data.get("status", {}).get("abstractGameState", "Preview")

            if status != "Final":
                continue

            # Check if we already processed this game
            from app.models.database import Game
            existing = db.query(Game).filter(
                Game.game_pk == game_pk, Game.status == "final"
            ).first()
            if existing and existing.statcast_loaded is not None:
                # Already processed — check if editorial exists
                from app.models.database import Editorial
                ed = db.query(Editorial).filter(Editorial.game_pk == game_pk).first()
                if ed:
                    continue

            logger.info(f"Game {game_pk} is Final — running post-game pipeline")

            # 1. Upsert game record
            games = parse_mlb_api_games([game_data], db)
            upsert_games(games, db)

            # 2. Box score
            try:
                boxscore = fetch_boxscore(game_pk)
                home_team = game_data.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
                cubs_key = "home" if "Cubs" in home_team else "away"
                parse_boxscore_pitchers(boxscore, game_pk, today, season, cubs_key, db)
                parse_boxscore_hitters(boxscore, game_pk, today, season, cubs_key, db)
            except Exception as e:
                logger.error(f"Box score failed for {game_pk}: {e}")

            # 3. Team stats + benchmarks
            compute_team_season_stats("CHC", season, db)
            refresh_player_benchmarks(season, db, cubs_only=True)

            # 4. Editorial
            try:
                editorial = generate_daily_takeaway(game_pk, db)
                if editorial:
                    logger.info(f"Editorial generated: {editorial.title}")
            except Exception as e:
                logger.error(f"Editorial failed for {game_pk}: {e}")

            logger.info(f"Post-game pipeline complete for {game_pk}")

    except Exception as e:
        logger.error(f"game_watcher_tick error: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 2: Daily update Pass 2 (Statcast + advanced stats)
# ---------------------------------------------------------------------------

def daily_update_pass2():
    """Morning-after Statcast and FanGraphs refresh."""
    logger.info("Running daily update Pass 2...")
    db = SessionLocal()
    try:
        from scripts.daily_update import run_pass2
        run_pass2(db)
        logger.info("Daily update Pass 2 complete")
    except Exception as e:
        logger.error(f"Daily update Pass 2 failed: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 3: Statcast backfill
# ---------------------------------------------------------------------------

def statcast_backfill():
    """Backfill any games missing Statcast data."""
    logger.info("Running Statcast backfill...")
    db = SessionLocal()
    try:
        from scripts.statcast_backfill import find_games_needing_statcast, backfill_game
        from app.services.benchmark_engine import compute_pitch_type_benchmarks

        games = find_games_needing_statcast(db, lookback_days=7)
        if not games:
            logger.info("No games need Statcast backfill")
            return

        total = 0
        for game in games:
            count = backfill_game(game, db)
            total += count

        if total > 0:
            season = date.today().year
            compute_pitch_type_benchmarks(season, db)
            logger.info(f"Backfilled {total} pitches, refreshed pitch-type benchmarks")
        else:
            logger.info("No Statcast data available yet for pending games")
    except Exception as e:
        logger.error(f"Statcast backfill failed: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job 4: Weekly full refresh (Sunday midnight CT)
# ---------------------------------------------------------------------------

def weekly_refresh():
    """Full league-wide benchmark refresh, ML retrain, and editorial generation."""
    logger.info("Running weekly refresh...")
    try:
        from scripts.weekly_refresh import main as weekly_main
        weekly_main()
        logger.info("Weekly refresh complete")
    except Exception as e:
        logger.error(f"Weekly refresh failed: {e}")


# ---------------------------------------------------------------------------
# Main scheduler
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("CubsStats Scheduler starting")
    logger.info("=" * 60)

    init_db()

    scheduler = BlockingScheduler(timezone="America/Chicago")

    # Game watcher: every 15 min from 4PM to 1AM CT (covers ~all game windows)
    # APScheduler cron: hour 16-23 + 0 = 4PM-midnight + midnight-1AM
    scheduler.add_job(
        game_watcher_tick,
        CronTrigger(minute="*/15", hour="16-23,0", timezone="America/Chicago"),
        id="game_watcher",
        name="Game Watcher (15-min poll)",
        max_instances=1,
        replace_existing=True,
    )

    # Daily Pass 2: 10:00 AM CT (Statcast available ~24h after game)
    scheduler.add_job(
        daily_update_pass2,
        CronTrigger(hour=10, minute=0, timezone="America/Chicago"),
        id="daily_pass2",
        name="Daily Update Pass 2 (Statcast + Advanced)",
        max_instances=1,
        replace_existing=True,
    )

    # Statcast backfill: 10:30 AM CT daily
    scheduler.add_job(
        statcast_backfill,
        CronTrigger(hour=10, minute=30, timezone="America/Chicago"),
        id="statcast_backfill",
        name="Statcast Backfill",
        max_instances=1,
        replace_existing=True,
    )

    # Weekly refresh: Sunday at midnight CT
    scheduler.add_job(
        weekly_refresh,
        CronTrigger(day_of_week="sun", hour=0, minute=0, timezone="America/Chicago"),
        id="weekly_refresh",
        name="Weekly Full Refresh",
        max_instances=1,
        replace_existing=True,
    )

    # Log schedule
    logger.info("Scheduled jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  {job.name} — next run: {job.next_run_time}")

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutdown signal received, stopping scheduler...")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
