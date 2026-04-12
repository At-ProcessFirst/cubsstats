#!/usr/bin/env python3
"""
test_pipeline.py — End-to-end test of the full post-game pipeline.

Simulates the complete flow:
  1. Fetch today's Cubs schedule from MLB Stats API
  2. Find any Final game (or use a recent one)
  3. Run post-game pipeline: box score → team stats → benchmarks → divergence → editorial
  4. Verify all API endpoints return data
  5. Print summary

Usage:
    cd backend
    python -m scripts.test_pipeline
    python -m scripts.test_pipeline --game-pk 12345  # Test specific game
"""

import argparse
import logging
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, Game, Editorial, DivergenceAlert, TeamSeasonStats
from app.services.ingestion import (
    fetch_schedule, parse_mlb_api_games, upsert_games,
    fetch_boxscore, parse_boxscore_pitchers, parse_boxscore_hitters,
    compute_team_season_stats,
)
from app.services.benchmark_engine import refresh_player_benchmarks
from app.services.divergence_engine import detect_pitcher_divergences, detect_hitter_divergences
from app.services.editorial_engine import generate_daily_takeaway
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


def find_recent_final_game(db) -> dict:
    """Find a recent Final Cubs game from the MLB API."""
    for days_back in range(0, 7):
        target = date.today() - timedelta(days=days_back)
        games_data = fetch_schedule(target, target, team_id=settings.cubs_team_id)
        for g in games_data:
            if g.get("status", {}).get("abstractGameState") == "Final":
                return g
    return None


def test_api_endpoints():
    """Test all API endpoints return 200."""
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    endpoints = [
        "/api/team/stats",
        "/api/team/record",
        "/api/team/games",
        "/api/team/win-trend",
        "/api/team/upcoming",
        "/api/pitching/cubs",
        "/api/hitting/cubs",
        "/api/defense/cubs",
        "/api/benchmarks/current",
        "/api/divergences/enriched",
        "/api/predictions/game-outcome",
        "/api/predictions/model-status",
        "/api/predictions/feature-importance",
        "/api/editorials",
        "/api/editorials/latest",
    ]

    results = []
    for ep in endpoints:
        r = client.get(ep)
        status = "OK" if r.status_code == 200 else f"FAIL ({r.status_code})"
        results.append((ep, status))
        if r.status_code != 200:
            logger.error(f"  FAIL: {ep} → {r.status_code}")

    return results


def main():
    parser = argparse.ArgumentParser(description="CubsStats E2E pipeline test")
    parser.add_argument("--game-pk", type=int, help="Specific game PK to test")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CubsStats End-to-End Pipeline Test")
    logger.info("=" * 60)

    init_db()
    db = SessionLocal()
    passed = 0
    failed = 0

    try:
        # Step 1: Find a game to test with
        logger.info("\n--- Step 1: Find a Final Cubs game ---")
        if args.game_pk:
            from app.services.ingestion import mlb_api_get
            game_data = mlb_api_get(f"/game/{args.game_pk}/feed/live")
            game_pk = args.game_pk
            logger.info(f"Using specified game: {game_pk}")
        else:
            game_data_raw = find_recent_final_game(db)
            if not game_data_raw:
                logger.error("No recent Final Cubs game found. Try --game-pk.")
                return
            game_pk = game_data_raw["gamePk"]
            logger.info(f"Found recent Final game: {game_pk}")
            game_data = game_data_raw

        # Step 2: Ingest game
        logger.info("\n--- Step 2: Ingest game data ---")
        games = parse_mlb_api_games([game_data] if isinstance(game_data, dict) and "gamePk" in game_data else [game_data], db)
        count = upsert_games(games, db)
        logger.info(f"  Upserted {count} game(s)")

        game = db.query(Game).filter(Game.game_pk == game_pk).first()
        if game:
            logger.info(f"  Game: {game.away_team} @ {game.home_team}, {game.game_date}, score: {game.away_score}-{game.home_score}")
            passed += 1
        else:
            logger.error("  Game not found in DB after upsert!")
            failed += 1

        # Step 3: Box score
        logger.info("\n--- Step 3: Parse box score ---")
        try:
            boxscore = fetch_boxscore(game_pk)
            home_name = ""
            for team_key in ["home", "away"]:
                team_data = boxscore.get("teams", {}).get(team_key, {})
                team_info = team_data.get("team", {})
                if "Cubs" in team_info.get("name", ""):
                    cubs_key = team_key
                    break
            else:
                cubs_key = "home" if game and game.home_team == "CHC" else "away"

            gd = game.game_date if game else date.today()
            season = gd.year if hasattr(gd, 'year') else date.today().year

            p_count = parse_boxscore_pitchers(boxscore, game_pk, gd, season, cubs_key, db)
            h_count = parse_boxscore_hitters(boxscore, game_pk, gd, season, cubs_key, db)
            logger.info(f"  Loaded {p_count} pitcher lines, {h_count} hitter lines")
            passed += 1
        except Exception as e:
            logger.error(f"  Box score failed: {e}")
            failed += 1

        # Step 4: Team stats
        logger.info("\n--- Step 4: Compute team stats ---")
        season = date.today().year
        compute_team_season_stats("CHC", season, db)
        ts = db.query(TeamSeasonStats).filter(
            TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season
        ).first()
        if ts:
            logger.info(f"  Cubs: {ts.wins}-{ts.losses}, RS={ts.runs_scored}, RA={ts.runs_allowed}")
            passed += 1
        else:
            logger.warning("  No team stats computed (may need more game data)")

        # Step 5: Player benchmarks
        logger.info("\n--- Step 5: Refresh player benchmarks ---")
        bm_count = refresh_player_benchmarks(season, db, cubs_only=True)
        logger.info(f"  Refreshed {bm_count} player benchmarks")
        passed += 1

        # Step 6: Divergence detection
        logger.info("\n--- Step 6: Divergence detection ---")
        p_divs = detect_pitcher_divergences(season, db)
        h_divs = detect_hitter_divergences(season, db)
        total_divs = db.query(DivergenceAlert).filter(DivergenceAlert.is_active == True).count()
        logger.info(f"  New: {p_divs} pitcher, {h_divs} hitter. Total active: {total_divs}")
        passed += 1

        # Step 7: Editorial generation
        logger.info("\n--- Step 7: Generate editorial ---")
        try:
            editorial = generate_daily_takeaway(game_pk, db)
            if editorial:
                logger.info(f"  Title: {editorial.title}")
                logger.info(f"  Body preview: {editorial.body[:100]}...")
                passed += 1
            else:
                logger.warning("  No editorial generated (game may not be Final)")
        except Exception as e:
            logger.error(f"  Editorial failed: {e}")
            failed += 1

        # Step 8: Test all API endpoints
        logger.info("\n--- Step 8: Test API endpoints ---")
        results = test_api_endpoints()
        api_ok = sum(1 for _, s in results if s == "OK")
        api_fail = sum(1 for _, s in results if s != "OK")
        logger.info(f"  API endpoints: {api_ok} OK, {api_fail} failed")
        for ep, status in results:
            marker = "  ✓" if status == "OK" else "  ✗"
            logger.info(f"  {marker} {ep}")
        passed += api_ok
        failed += api_fail

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info(f"Pipeline test complete: {passed} passed, {failed} failed")
        logger.info("=" * 60)

        if failed > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Pipeline test failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
