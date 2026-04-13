#!/usr/bin/env python3
"""
train_models.py — Train all ML models from historical data.

Uses 2024-2025 game data (300+ games) to train:
  1. Game Outcome model (XGBoost) — predicts win/loss per game
  2. Win Trend model (Ridge) — predicts next 10-game win total
  3. Regression Detection — runs z-score analysis (no training needed)

Run AFTER seed_historical.py and seed_benchmarks.py.

Usage:
    cd backend
    python -m scripts.train_models
"""

import logging
import sys
from datetime import date

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db
from app.services.ml_engine import train_all_models, get_model_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("CubsStats ML Model Training")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()

    try:
        results = train_all_models(db)

        logger.info("\n" + "=" * 60)
        logger.info("Training Results")
        logger.info("=" * 60)

        for name, result in results.items():
            status = result.get("status", "unknown")
            logger.info(f"\n  {name}:")
            logger.info(f"    Status: {status}")
            if "cv_accuracy" in result:
                logger.info(f"    CV Accuracy: {result['cv_accuracy']:.1%}")
                logger.info(f"    Samples: {result.get('samples', 0)} games")
            if "cv_mae" in result:
                logger.info(f"    CV MAE: {result['cv_mae']:.2f} wins")
                logger.info(f"    Samples: {result.get('samples', 0)} windows")
            if "feature_importance" in result:
                logger.info("    Top features:")
                sorted_fi = sorted(result["feature_importance"].items(), key=lambda x: x[1], reverse=True)
                for feat, imp in sorted_fi[:5]:
                    logger.info(f"      {feat}: {imp:.3f}")

        # Show final status
        status = get_model_status()
        logger.info("\n" + "=" * 60)
        logger.info("Final Model Status")
        logger.info("=" * 60)
        for name, info in status.items():
            s = info.get("status", "unknown")
            logger.info(f"  {name}: {s.upper()}")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
