"""
Ingestion service — pulls Cubs + league-wide data from MLB Stats API and pybaseball.

Data sources:
  - MLB Stats API (statsapi.mlb.com): game schedules, box scores, season stats
    Free, no API key, no IP blocking. Cubs team ID = 112.
  - pybaseball (Statcast only): pitch-level data from Baseball Savant

FanGraphs is NOT used — their servers return 403 from cloud IPs (Render, Railway).
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import pandas as pd
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import (
    Player, Game, PitcherSeasonStats, HitterSeasonStats,
    DefenseSeasonStats, TeamSeasonStats, PitcherGameStats,
    HitterGameStats, StatcastPitch,
)

logger = logging.getLogger(__name__)
settings = get_settings()

MLB_API = settings.mlb_stats_api_base
CUBS_ID = settings.cubs_team_id

TEAM_ABBR_MAP = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP", "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN",
}

# MLB Stats API team ID → abbreviation
TEAM_ID_ABBR = {
    109: "ARI", 144: "ATL", 110: "BAL", 111: "BOS",
    112: "CHC", 145: "CHW", 113: "CIN", 114: "CLE",
    115: "COL", 116: "DET", 117: "HOU", 118: "KCR",
    108: "LAA", 119: "LAD", 146: "MIA", 158: "MIL",
    142: "MIN", 121: "NYM", 147: "NYY", 133: "OAK",
    143: "PHI", 134: "PIT", 135: "SDP", 137: "SFG",
    136: "SEA", 138: "STL", 139: "TBR", 140: "TEX",
    141: "TOR", 120: "WSN",
}


def normalize_team(team_str: str) -> str:
    if not team_str:
        return ""
    team_str = str(team_str).strip()
    for full_name, abbr in TEAM_ABBR_MAP.items():
        if team_str == abbr or team_str in full_name:
            return abbr
    return team_str[:3].upper()


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        v = float(val)
        return v if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def _safe_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# MLB Stats API helpers
# ---------------------------------------------------------------------------

def mlb_api_get(endpoint: str, params: dict = None) -> dict:
    url = f"{MLB_API}{endpoint}"
    with httpx.Client(timeout=60) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_schedule(start_date: date, end_date: date, team_id: int = None) -> list[dict]:
    params = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "sportId": 1,
        "hydrate": "team,linescore",
    }
    if team_id:
        params["teamId"] = team_id
    data = mlb_api_get("/schedule", params)
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append(g)
    return games


def fetch_boxscore(game_pk: int) -> dict:
    return mlb_api_get(f"/game/{game_pk}/boxscore")


# ---------------------------------------------------------------------------
# MLB Stats API: League-wide season stats (replaces FanGraphs)
# ---------------------------------------------------------------------------

def _paginated_stats_pull(group: str, season: int) -> list[dict]:
    """Pull all player season stats with pagination. MLB API caps at ~50 per page."""
    results = []
    offset = 0
    page_size = 50
    while True:
        data = mlb_api_get("/stats", {
            "stats": "season",
            "group": group,
            "season": season,
            "sportId": 1,
            "playerPool": "ALL",
            "limit": page_size,
            "offset": offset,
        })
        page_results = []
        total_splits = 0
        for split_group in data.get("stats", []):
            total_splits = split_group.get("totalSplits", 0)
            for entry in split_group.get("splits", []):
                player_info = entry.get("player", {})
                team_info = entry.get("team", {})
                stat = entry.get("stat", {})
                page_results.append({
                    "mlb_id": player_info.get("id"),
                    "name": player_info.get("fullName", ""),
                    "team_id": team_info.get("id"),
                    "team_name": team_info.get("name", ""),
                    **stat,
                })
        results.extend(page_results)
        offset += page_size
        if not page_results or offset >= total_splits:
            break
    return results


def pull_mlb_pitching_stats(season: int) -> list[dict]:
    """Pull ALL league-wide pitching season stats (paginated)."""
    logger.info(f"Pulling MLB API pitching stats for {season} (paginated)...")
    results = _paginated_stats_pull("pitching", season)
    logger.info(f"  Got {len(results)} pitcher records")
    return results


def pull_mlb_batting_stats(season: int) -> list[dict]:
    """Pull ALL league-wide batting season stats (paginated)."""
    logger.info(f"Pulling MLB API batting stats for {season} (paginated)...")
    results = _paginated_stats_pull("hitting", season)
    logger.info(f"  Got {len(results)} hitter records")
    return results


def pull_cubs_roster(season: int) -> list[dict]:
    """Pull Cubs 40-man roster from MLB Stats API."""
    logger.info(f"Pulling Cubs roster for {season}...")
    data = mlb_api_get(f"/teams/{CUBS_ID}/roster", {
        "season": season,
        "rosterType": "fullSeason",
    })
    players = []
    for entry in data.get("roster", []):
        person = entry.get("person", {})
        pos = entry.get("position", {})
        players.append({
            "mlb_id": person.get("id"),
            "name": person.get("fullName", ""),
            "position": pos.get("abbreviation", ""),
            "position_type": pos.get("type", ""),
        })
    logger.info(f"  Got {len(players)} Cubs roster players")
    return players


def pull_player_season_stats(player_id: int, season: int, group: str = "hitting") -> Optional[dict]:
    """Pull an individual player's season stats."""
    try:
        data = mlb_api_get(f"/people/{player_id}/stats", {
            "stats": "season",
            "season": season,
            "group": group,
        })
        for sg in data.get("stats", []):
            for split in sg.get("splits", []):
                return split.get("stat", {})
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Load MLB API stats into database (with upsert + rollback safety)
# ---------------------------------------------------------------------------

def load_mlb_pitching_to_db(records: list[dict], season: int, db: Session) -> int:
    """Load MLB Stats API pitching data. Upserts players + season stats."""
    count = 0
    for r in records:
        try:
            mlb_id = r.get("mlb_id")
            if not mlb_id:
                continue

            name = r.get("name", "")
            team_id = r.get("team_id")
            team = TEAM_ID_ABBR.get(team_id, "")

            gs = _safe_int(r.get("gamesStarted"))
            g = _safe_int(r.get("gamesPlayed"))
            pos_group = "SP" if gs > 0 and gs >= g * 0.5 else "RP"

            # Upsert player
            player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
            if not player:
                player = Player(
                    mlb_id=mlb_id, name=name, team=team,
                    position="P", position_group=pos_group,
                    is_cubs=(team == "CHC"),
                )
                db.add(player)
                db.flush()
            else:
                player.team = team
                player.is_cubs = (team == "CHC")
                player.position_group = pos_group
                if name:
                    player.name = name

            ip_str = r.get("inningsPitched", "0")
            try:
                ip = float(ip_str)
            except (ValueError, TypeError):
                ip = 0

            # Compute K% and BB% from counts
            bf = _safe_int(r.get("battersFaced"))
            k_pct = ((_safe_int(r.get("strikeOuts")) / bf) * 100) if bf > 0 else None
            bb_pct = ((_safe_int(r.get("baseOnBalls")) / bf) * 100) if bf > 0 else None
            k_bb_pct = (k_pct - bb_pct) if k_pct is not None and bb_pct is not None else None

            existing = db.query(PitcherSeasonStats).filter(
                PitcherSeasonStats.player_id == mlb_id,
                PitcherSeasonStats.season == season,
            ).first()

            vals = dict(
                player_id=mlb_id, season=season, team=team,
                position_group=pos_group, games=g, games_started=gs,
                ip=ip,
                era=_safe_float(r.get("era")),
                k_pct=round(k_pct, 1) if k_pct is not None else None,
                bb_pct=round(bb_pct, 1) if bb_pct is not None else None,
                k_bb_pct=round(k_bb_pct, 1) if k_bb_pct is not None else None,
                avg_velo=None,  # Not in MLB Stats API — comes from Statcast
                whiff_pct=None,
            )

            if existing:
                for k, v in vals.items():
                    if k != "player_id" and v is not None:
                        setattr(existing, k, v)
            else:
                db.add(PitcherSeasonStats(**vals))
                count += 1

            db.flush()
        except Exception as e:
            logger.warning(f"  Skipping pitcher {r.get('mlb_id')}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"  Commit failed for pitching batch: {e}")
        db.rollback()

    return count


def load_mlb_batting_to_db(records: list[dict], season: int, db: Session) -> int:
    """Load MLB Stats API batting data. Upserts players + season stats."""
    count = 0
    for r in records:
        try:
            mlb_id = r.get("mlb_id")
            if not mlb_id:
                continue

            name = r.get("name", "")
            team_id = r.get("team_id")
            team = TEAM_ID_ABBR.get(team_id, "")
            pos = r.get("position", {}).get("abbreviation", "") if isinstance(r.get("position"), dict) else ""
            pos_group = "ALL_HITTERS"

            player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
            if not player:
                player = Player(
                    mlb_id=mlb_id, name=name, team=team,
                    position=pos, position_group=pos_group,
                    is_cubs=(team == "CHC"),
                )
                db.add(player)
                db.flush()
            else:
                player.team = team
                player.is_cubs = (team == "CHC")
                if name:
                    player.name = name

            pa = _safe_int(r.get("plateAppearances"))
            ab = _safe_int(r.get("atBats"))

            existing = db.query(HitterSeasonStats).filter(
                HitterSeasonStats.player_id == mlb_id,
                HitterSeasonStats.season == season,
            ).first()

            vals = dict(
                player_id=mlb_id, season=season, team=team,
                position_group=pos_group,
                games=_safe_int(r.get("gamesPlayed")),
                pa=pa, ab=ab,
                avg=_safe_float(r.get("avg")),
                obp=_safe_float(r.get("obp")),
                slg=_safe_float(r.get("slg")),
                babip=_safe_float(r.get("babip")),
                # wRC+, wOBA, xBA, xSLG, xwOBA not in MLB Stats API
                # — these come from Statcast/FanGraphs, will be null initially
            )

            if existing:
                for k, v in vals.items():
                    if k != "player_id" and v is not None:
                        setattr(existing, k, v)
            else:
                db.add(HitterSeasonStats(**vals))
                count += 1

            db.flush()
        except Exception as e:
            logger.warning(f"  Skipping hitter {r.get('mlb_id')}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"  Commit failed for batting batch: {e}")
        db.rollback()

    return count


# ---------------------------------------------------------------------------
# Game upsert (safe)
# ---------------------------------------------------------------------------

def parse_mlb_api_games(games_data: list[dict], db: Session) -> list[Game]:
    parsed = []
    for g in games_data:
        game_pk = g["gamePk"]
        game_date_str = g.get("officialDate") or g.get("gameDate", "")[:10]
        try:
            gd = date.fromisoformat(game_date_str)
        except (ValueError, TypeError):
            continue

        home_team_name = g.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
        away_team_name = g.get("teams", {}).get("away", {}).get("team", {}).get("name", "")
        home_abbr = TEAM_ABBR_MAP.get(home_team_name, home_team_name[:3].upper())
        away_abbr = TEAM_ABBR_MAP.get(away_team_name, away_team_name[:3].upper())

        home_score = g.get("teams", {}).get("home", {}).get("score")
        away_score = g.get("teams", {}).get("away", {}).get("score")

        status_str = g.get("status", {}).get("abstractGameState", "Scheduled")
        status_map = {"Final": "final", "Live": "live", "Preview": "scheduled"}
        status = status_map.get(status_str, "scheduled")

        cubs_home = home_abbr == "CHC"
        cubs_away = away_abbr == "CHC"
        is_cubs_game = cubs_home or cubs_away

        cubs_won = None
        cubs_opponent = None
        if is_cubs_game:
            cubs_opponent = away_abbr if cubs_home else home_abbr
            if status == "final" and home_score is not None and away_score is not None:
                cubs_won = (home_score > away_score) if cubs_home else (away_score > home_score)

        game = Game(
            game_pk=game_pk, game_date=gd, season=gd.year,
            home_team=home_abbr, away_team=away_abbr,
            home_score=home_score, away_score=away_score,
            cubs_opponent=cubs_opponent if is_cubs_game else None,
            cubs_home=cubs_home if is_cubs_game else None,
            cubs_won=cubs_won, status=status,
        )
        parsed.append(game)
    return parsed


def upsert_games(games: list[Game], db: Session) -> int:
    count = 0
    for game in games:
        try:
            existing = db.query(Game).filter(Game.game_pk == game.game_pk).first()
            if existing:
                existing.home_score = game.home_score
                existing.away_score = game.away_score
                existing.status = game.status
                existing.cubs_won = game.cubs_won
            else:
                db.add(game)
                count += 1
            db.flush()
        except Exception as e:
            logger.warning(f"  Skipping game {game.game_pk}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"  Commit failed for games: {e}")
        db.rollback()
    return count


# ---------------------------------------------------------------------------
# Statcast (still via pybaseball — Baseball Savant doesn't block cloud IPs)
# ---------------------------------------------------------------------------

def pull_statcast_range(start_date: str, end_date: str, team: str = None) -> pd.DataFrame:
    from pybaseball import statcast
    logger.info(f"Pulling Statcast data: {start_date} to {end_date}")
    df = statcast(start_dt=start_date, end_dt=end_date, team=team)
    return df


def load_statcast_to_db(df: pd.DataFrame, season: int, db: Session) -> int:
    if df is None or df.empty:
        return 0

    count = 0
    batch = []
    for _, row in df.iterrows():
        pitcher_id = _safe_int(row.get("pitcher"), default=None)
        batter_id = _safe_int(row.get("batter"), default=None)
        if not pitcher_id or not batter_id:
            continue

        game_date_val = row.get("game_date")
        if isinstance(game_date_val, str):
            gd = date.fromisoformat(game_date_val)
        elif isinstance(game_date_val, pd.Timestamp):
            gd = game_date_val.date()
        else:
            continue

        description = str(row.get("description", ""))
        is_whiff = description in ("swinging_strike", "swinging_strike_blocked", "foul_tip")

        launch_speed = _safe_float(row.get("launch_speed"))
        launch_angle = _safe_float(row.get("launch_angle"))
        is_barrel = False
        is_hard_hit = False
        if launch_speed is not None:
            is_hard_hit = launch_speed >= 95.0
            if launch_angle is not None:
                is_barrel = launch_speed >= 98.0 and 26 <= launch_angle <= 30

        pitch = StatcastPitch(
            game_pk=_safe_int(row.get("game_pk"), default=None),
            game_date=gd, season=season,
            pitcher_id=pitcher_id, batter_id=batter_id,
            pitch_type=str(row.get("pitch_type", "")) if pd.notna(row.get("pitch_type")) else None,
            release_speed=_safe_float(row.get("release_speed")),
            pfx_x=_safe_float(row.get("pfx_x")),
            pfx_z=_safe_float(row.get("pfx_z")),
            plate_x=_safe_float(row.get("plate_x")),
            plate_z=_safe_float(row.get("plate_z")),
            launch_speed=launch_speed, launch_angle=launch_angle,
            events=str(row.get("events", "")) if pd.notna(row.get("events")) else None,
            description=description if description else None,
            zone=_safe_int(row.get("zone"), default=None),
            spin_rate=_safe_float(row.get("release_spin_rate")),
            is_whiff=is_whiff, is_barrel=is_barrel, is_hard_hit=is_hard_hit,
        )
        batch.append(pitch)

        if len(batch) >= 5000:
            try:
                db.bulk_save_objects(batch)
                db.commit()
                count += len(batch)
            except Exception as e:
                logger.warning(f"  Statcast batch failed, rolling back: {e}")
                db.rollback()
            batch = []

    if batch:
        try:
            db.bulk_save_objects(batch)
            db.commit()
            count += len(batch)
        except Exception as e:
            logger.warning(f"  Statcast final batch failed: {e}")
            db.rollback()

    return count


# ---------------------------------------------------------------------------
# Box score parsers (with upsert safety)
# ---------------------------------------------------------------------------

def parse_boxscore_pitchers(boxscore: dict, game_pk: int, game_date: date,
                            season: int, team_key: str, db: Session) -> int:
    count = 0
    team_data = boxscore.get("teams", {}).get(team_key, {})
    players = team_data.get("players", {})

    for player_key, player_data in players.items():
        if not player_key.startswith("ID"):
            continue
        stats = player_data.get("stats", {}).get("pitching", {})
        if not stats or stats.get("inningsPitched") is None:
            continue

        mlb_id = player_data.get("person", {}).get("id")
        name = player_data.get("person", {}).get("fullName", "")
        if not mlb_id:
            continue

        try:
            player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
            if not player:
                player = Player(mlb_id=mlb_id, name=name, position="P", is_cubs=True)
                db.add(player)
                db.flush()

            # Check for existing game stat to avoid duplicate
            existing = db.query(PitcherGameStats).filter(
                PitcherGameStats.player_id == mlb_id,
                PitcherGameStats.game_pk == game_pk,
            ).first()
            if existing:
                continue

            ip_str = stats.get("inningsPitched", "0")
            try:
                ip = float(ip_str)
            except (ValueError, TypeError):
                ip = 0

            db.add(PitcherGameStats(
                player_id=mlb_id, game_pk=game_pk, game_date=game_date,
                season=season, ip=ip,
                hits=_safe_int(stats.get("hits")),
                runs=_safe_int(stats.get("runs")),
                earned_runs=_safe_int(stats.get("earnedRuns")),
                walks=_safe_int(stats.get("baseOnBalls")),
                strikeouts=_safe_int(stats.get("strikeOuts")),
                home_runs=_safe_int(stats.get("homeRuns")),
                pitches=_safe_int(stats.get("numberOfPitches")),
                era=_safe_float(stats.get("era")) if stats.get("era") != "-.--" else None,
            ))
            db.flush()
            count += 1
        except Exception as e:
            logger.warning(f"  Skipping pitcher game stat {mlb_id}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"  Commit failed for pitcher game stats: {e}")
        db.rollback()
    return count


def parse_boxscore_hitters(boxscore: dict, game_pk: int, game_date: date,
                           season: int, team_key: str, db: Session) -> int:
    count = 0
    team_data = boxscore.get("teams", {}).get(team_key, {})
    players = team_data.get("players", {})

    for player_key, player_data in players.items():
        if not player_key.startswith("ID"):
            continue
        stats = player_data.get("stats", {}).get("batting", {})
        if not stats or stats.get("atBats") is None:
            continue

        mlb_id = player_data.get("person", {}).get("id")
        name = player_data.get("person", {}).get("fullName", "")
        if not mlb_id:
            continue

        try:
            player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
            if not player:
                pos = player_data.get("position", {}).get("abbreviation", "")
                player = Player(mlb_id=mlb_id, name=name, position=pos, is_cubs=True)
                db.add(player)
                db.flush()

            existing = db.query(HitterGameStats).filter(
                HitterGameStats.player_id == mlb_id,
                HitterGameStats.game_pk == game_pk,
            ).first()
            if existing:
                continue

            db.add(HitterGameStats(
                player_id=mlb_id, game_pk=game_pk, game_date=game_date,
                season=season,
                ab=_safe_int(stats.get("atBats")),
                hits=_safe_int(stats.get("hits")),
                doubles=_safe_int(stats.get("doubles")),
                triples=_safe_int(stats.get("triples")),
                home_runs=_safe_int(stats.get("homeRuns")),
                rbi=_safe_int(stats.get("rbi")),
                walks=_safe_int(stats.get("baseOnBalls")),
                strikeouts=_safe_int(stats.get("strikeOuts")),
                stolen_bases=_safe_int(stats.get("stolenBases")),
            ))
            db.flush()
            count += 1
        except Exception as e:
            logger.warning(f"  Skipping hitter game stat {mlb_id}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"  Commit failed for hitter game stats: {e}")
        db.rollback()
    return count


# ---------------------------------------------------------------------------
# Team aggregate computation
# ---------------------------------------------------------------------------

def compute_team_season_stats(team: str, season: int, db: Session) -> TeamSeasonStats:
    games = db.query(Game).filter(
        Game.season == season, Game.status == "final",
        ((Game.home_team == team) | (Game.away_team == team)),
    ).all()

    wins = sum(1 for g in games if (
        (g.home_team == team and (g.home_score or 0) > (g.away_score or 0)) or
        (g.away_team == team and (g.away_score or 0) > (g.home_score or 0))
    ))
    losses = len(games) - wins
    rs = sum((g.home_score if g.home_team == team else g.away_score) or 0 for g in games)
    ra = sum((g.away_score if g.home_team == team else g.home_score) or 0 for g in games)

    pythag_wins = pythag_losses = None
    if rs + ra > 0:
        exp = 1.83
        pythag_pct = (rs ** exp) / (rs ** exp + ra ** exp)
        pythag_wins = round(pythag_pct * len(games), 1)
        pythag_losses = round((1 - pythag_pct) * len(games), 1)

    pitchers = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == season, PitcherSeasonStats.team == team,
    ).all()

    team_era = team_fip = team_k_pct = team_bb_pct = None
    if pitchers:
        total_ip = sum(p.ip or 0 for p in pitchers)
        if total_ip > 0:
            team_era = sum((p.era or 0) * (p.ip or 0) for p in pitchers) / total_ip
            team_fip = sum((p.fip or 0) * (p.ip or 0) for p in pitchers if p.fip) / total_ip if any(p.fip for p in pitchers) else None
        k_pcts = [p.k_pct for p in pitchers if p.k_pct is not None]
        bb_pcts = [p.bb_pct for p in pitchers if p.bb_pct is not None]
        if k_pcts:
            team_k_pct = sum(k_pcts) / len(k_pcts)
        if bb_pcts:
            team_bb_pct = sum(bb_pcts) / len(bb_pcts)

    hitters = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season, HitterSeasonStats.team == team,
    ).all()

    team_wrc_plus = team_woba = team_hard_hit_pct = team_barrel_pct = None
    team_avg = team_obp = team_slg = None
    if hitters:
        # Compute team AVG, OBP, SLG weighted by PA
        qualified = [h for h in hitters if h.pa and h.pa > 0]
        if qualified:
            total_pa = sum(h.pa for h in qualified)
            total_ab = sum(h.ab or 0 for h in qualified)
            if total_ab > 0:
                total_hits = sum((h.ab or 0) * (h.avg or 0) for h in qualified if h.avg is not None)
                team_avg = total_hits / total_ab
            avg_with_obp = [h for h in qualified if h.obp is not None]
            if avg_with_obp:
                team_obp = sum(h.obp * h.pa for h in avg_with_obp) / sum(h.pa for h in avg_with_obp)
            avg_with_slg = [h for h in qualified if h.slg is not None]
            if avg_with_slg:
                team_slg = sum(h.slg * h.pa for h in avg_with_slg) / sum(h.pa for h in avg_with_slg)
            # Approximate wRC+ from OPS+ logic: (OBP/lgOBP + SLG/lgSLG - 1) * 100
            # Using .320 OBP and .400 SLG as league averages
            if team_obp is not None and team_slg is not None:
                team_wrc_plus = ((team_obp / 0.320) + (team_slg / 0.400) - 1) * 100
        woba_vals = [h for h in hitters if h.woba and h.pa and h.pa > 0]
        if woba_vals:
            total_pa = sum(h.pa for h in woba_vals)
            team_woba = sum(h.woba * h.pa for h in woba_vals) / total_pa

    try:
        existing = db.query(TeamSeasonStats).filter(
            TeamSeasonStats.team == team, TeamSeasonStats.season == season,
        ).first()

        vals = dict(
            team=team, season=season, games_played=len(games),
            wins=wins, losses=losses, runs_scored=rs, runs_allowed=ra,
            team_era=round(team_era, 2) if team_era else None,
            team_fip=round(team_fip, 2) if team_fip else None,
            team_wrc_plus=round(team_wrc_plus, 1) if team_wrc_plus else None,
            team_woba=round(team_woba, 3) if team_woba else None,
            team_k_pct=round(team_k_pct, 3) if team_k_pct else None,
            team_bb_pct=round(team_bb_pct, 3) if team_bb_pct else None,
            team_hard_hit_pct=round(team_hard_hit_pct, 3) if team_hard_hit_pct else None,
            team_barrel_pct=round(team_barrel_pct, 3) if team_barrel_pct else None,
            pythag_wins=pythag_wins, pythag_losses=pythag_losses,
            run_diff=rs - ra,
        )

        if existing:
            for k, v in vals.items():
                setattr(existing, k, v)
            db.commit()
            return existing
        else:
            ts = TeamSeasonStats(**vals)
            db.add(ts)
            db.commit()
            return ts
    except Exception as e:
        logger.error(f"  Team stats upsert failed: {e}")
        db.rollback()
        return None
