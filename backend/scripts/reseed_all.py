#!/usr/bin/env python3
"""
reseed_all.py — Complete re-seed + benchmark + train + editorial in one command.

Guarantees correct order:
  1. Drop all tables and re-create
  2. Seed games, player stats, team strength for 2024-2026
  3. Compute benchmarks + divergence detection
  4. Train ML models (with real opponent Pythagorean data)
  5. Generate editorials

Usage:
    cd backend
    python -m scripts.reseed_all
"""

import logging
import sys
import subprocess

sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run(cmd):
    logger.info(f"\n{'='*60}")
    logger.info(f"RUNNING: python -m {cmd}")
    logger.info(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-m", cmd],
        cwd=".",
        capture_output=False,
    )
    if result.returncode != 0:
        logger.error(f"FAILED: {cmd} (exit code {result.returncode})")
        return False
    return True


def main():
    logger.info("=" * 60)
    logger.info("CubsStats Complete Re-Seed")
    logger.info("=" * 60)

    steps = [
        "scripts.seed_historical --clear",  # Drop tables, seed games + roster + team strength
        "scripts.seed_benchmarks",           # Benchmarks + divergences + ML training
        "scripts.generate_editorial --clear", # Fresh editorials
    ]

    for step in steps:
        # Split into module and args
        parts = step.split(" ", 1)
        module = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        logger.info(f"\n{'='*60}")
        logger.info(f"RUNNING: python -m {step}")
        logger.info(f"{'='*60}")

        cmd = [sys.executable, "-m", module]
        if args:
            cmd.extend(args.split())

        result = subprocess.run(cmd, cwd=".")
        if result.returncode != 0:
            logger.error(f"FAILED at: {step}")
            sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.info("COMPLETE RE-SEED FINISHED SUCCESSFULLY")
    logger.info("=" * 60)
    logger.info("Run 'python -m scripts.diagnose' to verify data")


if __name__ == "__main__":
    main()
