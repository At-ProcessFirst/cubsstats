#!/usr/bin/env python3
"""
generate_editorial.py — Manually generate editorials from current data.

Usage:
    cd backend
    python -m scripts.generate_editorial                    # Generate all types
    python -m scripts.generate_editorial --type weekly      # Weekly state only
    python -m scripts.generate_editorial --type daily       # Latest final game
    python -m scripts.generate_editorial --type spotlight   # Top divergence player
    python -m scripts.generate_editorial --type recap       # Prediction recap
"""

import argparse
import logging
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, Game, DivergenceAlert, Editorial
from app.services.editorial_engine import (
    generate_daily_takeaway,
    generate_weekly_state,
    generate_player_spotlight,
    generate_prediction_recap,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Generate CubsStats editorials")
    parser.add_argument("--type", choices=["daily", "weekly", "spotlight", "recap", "all"],
                        default="all", help="Editorial type to generate")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    season = date.today().year
    generated = []

    try:
        if args.type in ("daily", "all"):
            # Find most recent Final Cubs game
            game = db.query(Game).filter(
                Game.status == "final",
                ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
            ).order_by(Game.game_date.desc()).first()

            if game:
                logger.info(f"Generating Daily Takeaway for game {game.game_pk} ({game.game_date})...")
                ed = generate_daily_takeaway(game.game_pk, db)
                if ed:
                    generated.append(ed)
                    logger.info(f"  Title: {ed.title}")
            else:
                logger.warning("No Final Cubs games found for Daily Takeaway")

        if args.type in ("weekly", "all"):
            logger.info("Generating Weekly State...")
            ed = generate_weekly_state(season, db)
            if ed:
                generated.append(ed)
                logger.info(f"  Title: {ed.title}")

        if args.type in ("spotlight", "all"):
            # Find player with most active divergence alerts
            alert = db.query(DivergenceAlert).filter(
                DivergenceAlert.is_active == True,
            ).order_by(DivergenceAlert.created_at.desc()).first()

            if alert:
                logger.info(f"Generating Player Spotlight for player {alert.player_id}...")
                ed = generate_player_spotlight(alert.player_id, season, db)
                if ed:
                    generated.append(ed)
                    logger.info(f"  Title: {ed.title}")
            else:
                logger.info("No divergence alerts — skipping player spotlight")

        if args.type in ("recap", "all"):
            logger.info("Generating Prediction Recap...")
            ed = generate_prediction_recap(season, db)
            if ed:
                generated.append(ed)
                logger.info(f"  Title: {ed.title}")

        # Summary
        total = db.query(Editorial).count()
        logger.info(f"\nGenerated {len(generated)} editorial(s). Total in database: {total}")
        for ed in generated:
            logger.info(f"  [{ed.editorial_type}] {ed.title}")
            logger.info(f"    Preview: {ed.body[:120]}...")

    except Exception as e:
        logger.error(f"Editorial generation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
