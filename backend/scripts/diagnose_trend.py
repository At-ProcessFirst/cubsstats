#!/usr/bin/env python3
"""Diagnose why Win Trend model has no training data."""
import logging
import sys
sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, Game
from app.services.features import _get_cubs_games, build_trend_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    init_db()
    db = SessionLocal()

    try:
        for season in range(2015, 2027):
            games = _get_cubs_games(season, db)
            logger.info(f"{season}: {len(games)} final Cubs games")
            if games:
                g = games[0]
                logger.info(f"  First game: {g.game_date} home_score={g.home_score} away_score={g.away_score}")
                g = games[-1]
                logger.info(f"  Last game:  {g.game_date} home_score={g.home_score} away_score={g.away_score}")

            if len(games) >= 40:
                logger.info(f"  Attempting build_trend_features({season})...")
                try:
                    df = build_trend_features(season, db)
                    if df is not None:
                        logger.info(f"  SUCCESS: {len(df)} windows")
                    else:
                        logger.info(f"  RETURNED None")
                except Exception as e:
                    logger.error(f"  EXCEPTION: {e}")
                    import traceback
                    traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
