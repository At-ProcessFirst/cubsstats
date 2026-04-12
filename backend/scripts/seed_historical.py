#!/usr/bin/env python3
"""
seed_historical.py — Load historical Cubs + MLB player data.

Data sources (all MLB Stats API — no FanGraphs):
  1. League-wide pitching + batting season stats (paginated)
  2. Cubs roster → individual player stats for each roster member
  3. Cubs game schedule + results
  4. Team aggregate computation

Usage:
    cd backend
    python -m scripts.seed_historical
    python -m scripts.seed_historical --clear   # Drop and re-create all tables first
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone

sys.path.insert(0, ".")

from app.models.database import SessionLocal, init_db, Base, engine, PipelineRun
from app.services.ingestion import (
    pull_mlb_pitching_stats, pull_mlb_batting_stats,
    load_mlb_pitching_to_db, load_mlb_batting_to_db,
    fetch_schedule, parse_mlb_api_games, upsert_games,
    compute_team_season_stats,
    pull_cubs_roster, pull_player_season_stats,
    mlb_api_get, TEAM_ID_ABBR, _safe_float, _safe_int,
)
from app.models.database import Player, PitcherSeasonStats, HitterSeasonStats
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
CURRENT_YEAR = date.today().year
SEASONS = [2024, 2025, CURRENT_YEAR] if CURRENT_YEAR > 2025 else [2024, 2025]


def seed_league_wide_stats(db, season: int):
    """Pull ALL league-wide pitching + batting stats from MLB Stats API (paginated)."""
    logger.info(f"=== League-wide player stats for {season} ===")

    try:
        pitching_records = pull_mlb_pitching_stats(season)
        count = load_mlb_pitching_to_db(pitching_records, season, db)
        logger.info(f"  Pitchers: {count} new / {len(pitching_records)} total from API")
    except Exception as e:
        logger.error(f"  Pitching pull failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass

    try:
        batting_records = pull_mlb_batting_stats(season)
        count = load_mlb_batting_to_db(batting_records, season, db)
        logger.info(f"  Hitters: {count} new / {len(batting_records)} total from API")
    except Exception as e:
        logger.error(f"  Batting pull failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def seed_cubs_roster_stats(db, season: int):
    """Pull Cubs roster and each player's individual season stats.
    This ensures Cubs players have full stat lines even if the league-wide
    pull missed details.
    """
    logger.info(f"=== Cubs roster + individual stats for {season} ===")

    try:
        roster = pull_cubs_roster(season)
    except Exception as e:
        logger.error(f"  Roster pull failed: {e}")
        return

    pitchers_loaded = 0
    hitters_loaded = 0

    for rp in roster:
        mlb_id = rp["mlb_id"]
        name = rp["name"]
        pos = rp["position"]
        pos_type = rp.get("position_type", "")

        try:
            # Upsert player
            player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
            if not player:
                player = Player(
                    mlb_id=mlb_id, name=name, team="CHC",
                    position=pos, is_cubs=True,
                )
                db.add(player)
                db.flush()
            else:
                player.name = name
                player.team = "CHC"
                player.position = pos
                player.is_cubs = True

            # Pull individual stats based on position
            if pos_type == "Pitcher" or pos == "P":
                stats = pull_player_season_stats(mlb_id, season, "pitching")
                if stats:
                    gs = _safe_int(stats.get("gamesStarted"))
                    g = _safe_int(stats.get("gamesPlayed"))
                    pos_group = "SP" if gs > 0 and gs >= g * 0.5 else "RP"
                    player.position_group = pos_group

                    ip_str = stats.get("inningsPitched", "0")
                    try:
                        ip = float(ip_str)
                    except (ValueError, TypeError):
                        ip = 0

                    bf = _safe_int(stats.get("battersFaced"))
                    k_pct = ((_safe_int(stats.get("strikeOuts")) / bf) * 100) if bf > 0 else None
                    bb_pct = ((_safe_int(stats.get("baseOnBalls")) / bf) * 100) if bf > 0 else None

                    existing = db.query(PitcherSeasonStats).filter(
                        PitcherSeasonStats.player_id == mlb_id,
                        PitcherSeasonStats.season == season,
                    ).first()

                    vals = dict(
                        player_id=mlb_id, season=season, team="CHC",
                        position_group=pos_group, games=g, games_started=gs, ip=ip,
                        era=_safe_float(stats.get("era")),
                        k_pct=round(k_pct, 1) if k_pct else None,
                        bb_pct=round(bb_pct, 1) if bb_pct else None,
                        k_bb_pct=round(k_pct - bb_pct, 1) if k_pct and bb_pct else None,
                    )

                    if existing:
                        for k, v in vals.items():
                            if k != "player_id" and v is not None:
                                setattr(existing, k, v)
                    else:
                        db.add(PitcherSeasonStats(**vals))
                    pitchers_loaded += 1
            else:
                stats = pull_player_season_stats(mlb_id, season, "hitting")
                if stats:
                    from app.services.ingestion import normalize_team
                    player.position_group = "ALL_HITTERS"

                    pa = _safe_int(stats.get("plateAppearances"))
                    ab = _safe_int(stats.get("atBats"))

                    existing = db.query(HitterSeasonStats).filter(
                        HitterSeasonStats.player_id == mlb_id,
                        HitterSeasonStats.season == season,
                    ).first()

                    vals = dict(
                        player_id=mlb_id, season=season, team="CHC",
                        position_group="ALL_HITTERS",
                        games=_safe_int(stats.get("gamesPlayed")),
                        pa=pa, ab=ab,
                        avg=_safe_float(stats.get("avg")),
                        obp=_safe_float(stats.get("obp")),
                        slg=_safe_float(stats.get("slg")),
                        babip=_safe_float(stats.get("babip")),
                    )

                    if existing:
                        for k, v in vals.items():
                            if k != "player_id" and v is not None:
                                setattr(existing, k, v)
                    else:
                        db.add(HitterSeasonStats(**vals))
                    hitters_loaded += 1

            db.flush()
            time.sleep(0.1)  # Rate limit individual player calls
        except Exception as e:
            logger.warning(f"  Skipping {name} ({mlb_id}): {e}")
            try:
                db.rollback()
            except Exception:
                pass
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"  Commit failed: {e}")
        db.rollback()

    logger.info(f"  Cubs roster: {pitchers_loaded} pitchers, {hitters_loaded} hitters loaded")


def seed_games(db, season: int):
    """Pull Cubs game schedule and results. Fetches in monthly chunks to get all games."""
    logger.info(f"=== Cubs games for {season} ===")

    today = date.today()
    # Fetch month by month to avoid API limits
    total_loaded = 0
    month_starts = []
    for month in range(3, 12):  # March through November
        start = date(season, month, 1)
        if month == 11:
            end = date(season, 11, 15)
        else:
            end = date(season, month + 1, 1) - __import__('datetime').timedelta(days=1)

        if start > today:
            break
        if end > today:
            end = today

        month_starts.append((start, end))

    for start, end in month_starts:
        try:
            games_data = fetch_schedule(start, end, team_id=settings.cubs_team_id)
            if games_data:
                games = parse_mlb_api_games(games_data, db)
                count = upsert_games(games, db)
                total_loaded += count
                logger.info(f"  {start.strftime('%b %Y')}: {count} new / {len(games)} total games")
        except Exception as e:
            logger.error(f"  Failed for {start} to {end}: {e}")
            try:
                db.rollback()
            except Exception:
                pass

    logger.info(f"  Total games loaded for {season}: {total_loaded}")


def main():
    parser = argparse.ArgumentParser(description="CubsStats Historical Data Seed")
    parser.add_argument("--clear", action="store_true", help="Drop all tables and re-create")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CubsStats Historical Data Seed")
    logger.info(f"Seasons: {SEASONS}")
    logger.info("=" * 60)

    if args.clear:
        logger.info("CLEARING ALL TABLES...")
        Base.metadata.drop_all(bind=engine)
        logger.info("Tables dropped.")

    init_db()
    db = SessionLocal()

    run = PipelineRun(pipeline_name="seed_historical", status="running")
    db.add(run)
    db.commit()

    try:
        for season in SEASONS:
            logger.info(f"\n{'='*50}")
            logger.info(f"  SEASON {season}")
            logger.info(f"{'='*50}")

            # 1. League-wide stats (for benchmarking)
            seed_league_wide_stats(db, season)

            # 2. Cubs roster + individual player stats
            seed_cubs_roster_stats(db, season)

            # 3. Cubs game schedule + results
            seed_games(db, season)

            # 4. Team aggregates
            logger.info(f"  Computing team stats for CHC {season}...")
            compute_team_season_stats("CHC", season, db)

        # Summary
        from app.models.database import Game, TeamSeasonStats
        for season in SEASONS:
            games = db.query(Game).filter(
                Game.season == season,
                ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
            ).count()
            pitchers = db.query(PitcherSeasonStats).filter(
                PitcherSeasonStats.season == season, PitcherSeasonStats.team == "CHC",
            ).count()
            hitters = db.query(HitterSeasonStats).filter(
                HitterSeasonStats.season == season, HitterSeasonStats.team == "CHC",
            ).count()
            ts = db.query(TeamSeasonStats).filter(
                TeamSeasonStats.team == "CHC", TeamSeasonStats.season == season,
            ).first()
            record = f"{ts.wins}-{ts.losses}" if ts else "N/A"
            logger.info(f"  {season}: {games} games, {pitchers} pitchers, {hitters} hitters, record: {record}")

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("\n" + "=" * 60)
        logger.info("Historical seed complete!")
        logger.info("=" * 60)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
