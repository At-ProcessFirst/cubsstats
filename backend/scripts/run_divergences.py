#!/usr/bin/env python3
"""
run_divergences.py — Run divergence detection and print results.

Usage:
    cd backend
    python -m scripts.run_divergences
"""

import logging
import sys
from datetime import date

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, DivergenceAlert, Player
from app.services.divergence_engine import detect_pitcher_divergences, detect_hitter_divergences

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("Running Divergence Detection")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()
    season = date.today().year

    try:
        p_count = detect_pitcher_divergences(season, db)
        logger.info(f"Pitcher divergences found: {p_count}")

        h_count = detect_hitter_divergences(season, db)
        logger.info(f"Hitter divergences found: {h_count}")

        # Print all active alerts
        alerts = db.query(DivergenceAlert).filter(
            DivergenceAlert.is_active == True,
        ).order_by(DivergenceAlert.created_at.desc()).all()

        logger.info(f"\nTotal active alerts: {len(alerts)}")
        for a in alerts:
            player = db.query(Player).filter(Player.mlb_id == a.player_id).first()
            name = player.name if player else f"#{a.player_id}"
            logger.info(
                f"  [{a.alert_type}] {name}: "
                f"{a.stat1_name}={a.stat1_value:.2f} vs {a.stat2_name}={a.stat2_value:.2f} "
                f"(gap={a.gap:.2f})"
            )
            logger.info(f"    {a.explanation}")

    except Exception as e:
        logger.error(f"Divergence detection failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
