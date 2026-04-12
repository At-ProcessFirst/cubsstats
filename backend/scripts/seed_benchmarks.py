#!/usr/bin/env python3
"""
seed_benchmarks.py — Compute baseline benchmark tables from loaded season data.

Run AFTER seed_historical.py. Computes:
  - League-wide pitching benchmarks (SP + RP) by stat
  - League-wide hitting benchmarks (ALL_HITTERS + position groups) by stat
  - Pitch-type benchmarks from Statcast data
  - Cubs player percentile ranks against the league

Usage:
    cd backend
    python -m scripts.seed_benchmarks
"""

import logging
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, PipelineRun
from app.services.benchmark_engine import (
    compute_pitching_benchmarks,
    compute_hitting_benchmarks,
    compute_pitch_type_benchmarks,
    refresh_player_benchmarks,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Compute benchmarks for these seasons
SEASONS = [2024, 2025]


def main():
    logger.info("=" * 60)
    logger.info("CubsEdge Benchmark Seed")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()

    run = PipelineRun(pipeline_name="seed_benchmarks", status="running")
    db.add(run)
    db.commit()

    total = 0

    try:
        for season in SEASONS:
            logger.info(f"\n--- Season {season} ---")

            # 1. Pitching benchmarks
            count = compute_pitching_benchmarks(season, db)
            logger.info(f"  Pitching benchmarks: {count}")
            total += count

            # 2. Hitting benchmarks
            count = compute_hitting_benchmarks(season, db)
            logger.info(f"  Hitting benchmarks: {count}")
            total += count

            # 3. Pitch-type benchmarks
            count = compute_pitch_type_benchmarks(season, db)
            logger.info(f"  Pitch-type benchmarks: {count}")
            total += count

            # 4. Player percentile ranks (Cubs only)
            count = refresh_player_benchmarks(season, db, cubs_only=True)
            logger.info(f"  Cubs player benchmarks: {count}")
            total += count

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.records_processed = total
        db.commit()

        logger.info(f"\nBenchmark seed complete! Total benchmarks computed: {total}")

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"Benchmark seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
