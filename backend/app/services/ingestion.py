"""
Ingestion service — pulls Cubs + league-wide data from pybaseball and MLB Stats API.

Data sources:
  - pybaseball: FanGraphs season stats, Statcast pitch-level data
  - MLB Stats API (statsapi.mlb.com): game schedules, box scores, live game status
    Cubs team ID = 112. Free, no API key needed.
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

# Team abbreviation mapping (MLB Stats API uses full names, we use abbreviations)
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

# FanGraphs team abbreviation to our abbreviation
FG_TEAM_MAP = {
    "Cubs": "CHC", "CHC": "CHC",
    "White Sox": "CHW", "CWS": "CHW", "CHW": "CHW",
    "Diamondbacks": "ARI", "ARI": "ARI",
    "Braves": "ATL", "ATL": "ATL",
    "Orioles": "BAL", "BAL": "BAL",
    "Red Sox": "BOS", "BOS": "BOS",
    "Reds": "CIN", "CIN": "CIN",
    "Guardians": "CLE", "CLE": "CLE",
    "Rockies": "COL", "COL": "COL",
    "Tigers": "DET", "DET": "DET",
    "Astros": "HOU", "HOU": "HOU",
    "Royals": "KCR", "KC": "KCR", "KCR": "KCR",
    "Angels": "LAA", "LAA": "LAA",
    "Dodgers": "LAD", "LAD": "LAD",
    "Marlins": "MIA", "MIA": "MIA",
    "Brewers": "MIL", "MIL": "MIL",
    "Twins": "MIN", "MIN": "MIN",
    "Mets": "NYM", "NYM": "NYM",
    "Yankees": "NYY", "NYY": "NYY",
    "Athletics": "OAK", "OAK": "OAK",
    "Phillies": "PHI", "PHI": "PHI",
    "Pirates": "PIT", "PIT": "PIT",
    "Padres": "SDP", "SD": "SDP", "SDP": "SDP",
    "Giants": "SFG", "SF": "SFG", "SFG": "SFG",
    "Mariners": "SEA", "SEA": "SEA",
    "Cardinals": "STL", "STL": "STL",
    "Rays": "TBR", "TB": "TBR", "TBR": "TBR",
    "Rangers": "TEX", "TEX": "TEX",
    "Blue Jays": "TOR", "TOR": "TOR",
    "Nationals": "WSN", "WSH": "WSN", "WSN": "WSN",
}


def normalize_team(team_str: str) -> str:
    """Normalize a team name or abbreviation to our standard 3-letter code."""
    if not team_str:
        return ""
    team_str = str(team_str).strip()
    if team_str in FG_TEAM_MAP:
        return FG_TEAM_MAP[team_str]
    for full_name, abbr in TEAM_ABBR_MAP.items():
        if team_str in full_name:
            return abbr
    return team_str[:3].upper()


# ---------------------------------------------------------------------------
# MLB Stats API helpers
# ---------------------------------------------------------------------------

def mlb_api_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the MLB Stats API."""
    url = f"{MLB_API}{endpoint}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_schedule(start_date: date, end_date: date, team_id: int = None) -> list[dict]:
    """Fetch game schedule from MLB Stats API."""
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
    """Fetch box score for a specific game."""
    return mlb_api_get(f"/game/{game_pk}/boxscore")


def fetch_game_status(game_pk: int) -> str:
    """Check if a game is Final, Live, or Scheduled."""
    data = mlb_api_get(f"/game/{game_pk}/feed/live")
    return data.get("gameData", {}).get("status", {}).get("abstractGameState", "Unknown")


def parse_mlb_api_games(games_data: list[dict], db: Session) -> list[Game]:
    """Parse MLB Stats API game data into Game model objects."""
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
        if is_cubs_game and status == "final" and home_score is not None and away_score is not None:
            cubs_opponent = away_abbr if cubs_home else home_abbr
            if cubs_home:
                cubs_won = home_score > away_score
            else:
                cubs_won = away_score > home_score

        if is_cubs_game and cubs_opponent is None:
            cubs_opponent = away_abbr if cubs_home else home_abbr

        game = Game(
            game_pk=game_pk,
            game_date=gd,
            season=gd.year,
            home_team=home_abbr,
            away_team=away_abbr,
            home_score=home_score,
            away_score=away_score,
            cubs_opponent=cubs_opponent if is_cubs_game else None,
            cubs_home=cubs_home if is_cubs_game else None,
            cubs_won=cubs_won,
            status=status,
        )
        parsed.append(game)
    return parsed


def upsert_games(games: list[Game], db: Session) -> int:
    """Insert or update games in the database. Returns count of new/updated games."""
    count = 0
    for game in games:
        existing = db.query(Game).filter(Game.game_pk == game.game_pk).first()
        if existing:
            existing.home_score = game.home_score
            existing.away_score = game.away_score
            existing.status = game.status
            existing.cubs_won = game.cubs_won
        else:
            db.add(game)
            count += 1
    db.commit()
    return count


# ---------------------------------------------------------------------------
# pybaseball data pulls
# ---------------------------------------------------------------------------

def pull_fg_pitching(season: int, qual: int = 10) -> pd.DataFrame:
    """Pull FanGraphs pitching stats for all qualified pitchers in a season."""
    from pybaseball import pitching_stats
    logger.info(f"Pulling FanGraphs pitching data for {season} (qual={qual} IP)")
    df = pitching_stats(season, qual=qual)
    return df


def pull_fg_batting(season: int, qual: int = 30) -> pd.DataFrame:
    """Pull FanGraphs batting stats for all qualified hitters in a season."""
    from pybaseball import batting_stats
    logger.info(f"Pulling FanGraphs batting data for {season} (qual={qual} PA)")
    df = batting_stats(season, qual=qual)
    return df


def pull_statcast_range(start_date: str, end_date: str, team: str = None) -> pd.DataFrame:
    """Pull Statcast pitch-level data for a date range."""
    from pybaseball import statcast
    logger.info(f"Pulling Statcast data: {start_date} to {end_date}")
    df = statcast(start_dt=start_date, end_dt=end_date, team=team)
    return df


def pull_statcast_pitcher(pitcher_id: int, start_date: str, end_date: str) -> pd.DataFrame:
    """Pull Statcast data for a specific pitcher."""
    from pybaseball import statcast_pitcher
    return statcast_pitcher(start_dt=start_date, end_dt=end_date, player_id=pitcher_id)


# ---------------------------------------------------------------------------
# Data transformation and loading
# ---------------------------------------------------------------------------

def map_position_group(pos: str, gs: int = 0, g: int = 0) -> str:
    """Map a position string to a position group."""
    if not pos:
        return "ALL_HITTERS"
    pos = str(pos).upper().strip()
    if pos in ("SP", "P") and gs > 0 and gs >= g * 0.5:
        return "SP"
    if pos in ("RP", "P", "CL"):
        return "RP"
    if pos == "SP":
        return "SP"
    if pos == "C":
        return "C"
    if pos in ("1B", "2B", "3B", "SS"):
        return "IF"
    if pos in ("LF", "CF", "RF", "OF"):
        return "OF"
    if pos == "DH":
        return "ALL_HITTERS"
    return "ALL_HITTERS"


def load_fg_pitching_to_db(df: pd.DataFrame, season: int, db: Session) -> int:
    """Load FanGraphs pitching stats into the database."""
    if df is None or df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        # Resolve player identity
        name = str(row.get("Name", ""))
        team = normalize_team(str(row.get("Team", "")))
        fg_id = str(row.get("IDfg", "")) if "IDfg" in row else None
        mlb_id = int(row["mlbam_id"]) if "mlbam_id" in row and pd.notna(row.get("mlbam_id")) else None

        # Try to get mlb_id from playerid_lookup if missing
        if not mlb_id and fg_id:
            mlb_id = hash(f"{name}_{fg_id}") % 10_000_000  # Fallback ID

        if not mlb_id:
            continue

        gs = int(row.get("GS", 0)) if pd.notna(row.get("GS")) else 0
        g = int(row.get("G", 0)) if pd.notna(row.get("G")) else 0
        pos_group = "SP" if gs > 0 and gs >= g * 0.5 else "RP"

        # Upsert player
        player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
        if not player:
            player = Player(
                mlb_id=mlb_id,
                fg_id=fg_id,
                name=name,
                team=team,
                position="P",
                position_group=pos_group,
                is_cubs=(team == "CHC"),
            )
            db.add(player)
        else:
            player.team = team
            player.is_cubs = (team == "CHC")
            player.position_group = pos_group

        def safe_float(val):
            try:
                v = float(val)
                return v if pd.notna(v) else None
            except (ValueError, TypeError):
                return None

        ip = safe_float(row.get("IP", 0))

        stats = PitcherSeasonStats(
            player_id=mlb_id,
            season=season,
            team=team,
            position_group=pos_group,
            games=g,
            games_started=gs,
            ip=ip or 0,
            era=safe_float(row.get("ERA")),
            fip=safe_float(row.get("FIP")),
            xfip=safe_float(row.get("xFIP")),
            xera=safe_float(row.get("xERA")),
            k_pct=safe_float(row.get("K%")),
            bb_pct=safe_float(row.get("BB%")),
            k_bb_pct=safe_float(row.get("K-BB%")),
            swstr_pct=safe_float(row.get("SwStr%")),
            csw_pct=safe_float(row.get("CSW%")),
            hard_hit_pct=safe_float(row.get("Hard%")),
            barrel_pct=safe_float(row.get("Barrel%")),
            avg_velo=safe_float(row.get("vFA (pi)")) or safe_float(row.get("FBv")),
        )

        existing = db.query(PitcherSeasonStats).filter(
            PitcherSeasonStats.player_id == mlb_id,
            PitcherSeasonStats.season == season,
        ).first()

        if existing:
            for col in stats.__table__.columns:
                if col.name not in ("id",):
                    setattr(existing, col.name, getattr(stats, col.name))
        else:
            db.add(stats)
            count += 1

    db.commit()
    return count


def load_fg_batting_to_db(df: pd.DataFrame, season: int, db: Session) -> int:
    """Load FanGraphs batting stats into the database."""
    if df is None or df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        name = str(row.get("Name", ""))
        team = normalize_team(str(row.get("Team", "")))
        fg_id = str(row.get("IDfg", "")) if "IDfg" in row else None
        mlb_id = int(row["mlbam_id"]) if "mlbam_id" in row and pd.notna(row.get("mlbam_id")) else None

        if not mlb_id and fg_id:
            mlb_id = hash(f"{name}_{fg_id}") % 10_000_000

        if not mlb_id:
            continue

        pos = str(row.get("Pos", "")) if "Pos" in row else ""
        pos_group = map_position_group(pos)

        player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
        if not player:
            player = Player(
                mlb_id=mlb_id,
                fg_id=fg_id,
                name=name,
                team=team,
                position=pos,
                position_group=pos_group,
                is_cubs=(team == "CHC"),
            )
            db.add(player)
        else:
            player.team = team
            player.is_cubs = (team == "CHC")
            if pos:
                player.position = pos
                player.position_group = pos_group

        def safe_float(val):
            try:
                v = float(val)
                return v if pd.notna(v) else None
            except (ValueError, TypeError):
                return None

        stats = HitterSeasonStats(
            player_id=mlb_id,
            season=season,
            team=team,
            position_group=pos_group,
            games=int(row.get("G", 0)) if pd.notna(row.get("G")) else 0,
            pa=int(row.get("PA", 0)) if pd.notna(row.get("PA")) else 0,
            ab=int(row.get("AB", 0)) if pd.notna(row.get("AB")) else 0,
            avg=safe_float(row.get("AVG")),
            obp=safe_float(row.get("OBP")),
            slg=safe_float(row.get("SLG")),
            wrc_plus=safe_float(row.get("wRC+")),
            woba=safe_float(row.get("wOBA")),
            xba=safe_float(row.get("xBA")),
            xslg=safe_float(row.get("xSLG")),
            xwoba=safe_float(row.get("xwOBA")),
            barrel_pct=safe_float(row.get("Barrel%")),
            hard_hit_pct=safe_float(row.get("Hard%")),
            avg_exit_velo=safe_float(row.get("EV")),
            o_swing_pct=safe_float(row.get("O-Swing%")),
            z_contact_pct=safe_float(row.get("Z-Contact%")),
            chase_rate=safe_float(row.get("O-Swing%")),  # Chase rate = O-Swing%
            sprint_speed=safe_float(row.get("Spd")),
            bsr=safe_float(row.get("BsR")),
            babip=safe_float(row.get("BABIP")),
        )

        existing = db.query(HitterSeasonStats).filter(
            HitterSeasonStats.player_id == mlb_id,
            HitterSeasonStats.season == season,
        ).first()

        if existing:
            for col in stats.__table__.columns:
                if col.name not in ("id",):
                    setattr(existing, col.name, getattr(stats, col.name))
        else:
            db.add(stats)
            count += 1

    db.commit()
    return count


def load_statcast_to_db(df: pd.DataFrame, season: int, db: Session) -> int:
    """Load Statcast pitch-level data into the database."""
    if df is None or df.empty:
        return 0

    count = 0
    batch = []
    for _, row in df.iterrows():
        pitcher_id = int(row["pitcher"]) if pd.notna(row.get("pitcher")) else None
        batter_id = int(row["batter"]) if pd.notna(row.get("batter")) else None
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

        launch_speed = float(row["launch_speed"]) if pd.notna(row.get("launch_speed")) else None
        launch_angle = float(row["launch_angle"]) if pd.notna(row.get("launch_angle")) else None
        is_barrel = False
        is_hard_hit = False
        if launch_speed is not None:
            is_hard_hit = launch_speed >= 95.0
            if launch_angle is not None:
                is_barrel = launch_speed >= 98.0 and 26 <= launch_angle <= 30

        pitch = StatcastPitch(
            game_pk=int(row["game_pk"]) if pd.notna(row.get("game_pk")) else None,
            game_date=gd,
            season=season,
            pitcher_id=pitcher_id,
            batter_id=batter_id,
            pitch_type=str(row.get("pitch_type", "")) if pd.notna(row.get("pitch_type")) else None,
            release_speed=float(row["release_speed"]) if pd.notna(row.get("release_speed")) else None,
            pfx_x=float(row["pfx_x"]) if pd.notna(row.get("pfx_x")) else None,
            pfx_z=float(row["pfx_z"]) if pd.notna(row.get("pfx_z")) else None,
            plate_x=float(row["plate_x"]) if pd.notna(row.get("plate_x")) else None,
            plate_z=float(row["plate_z"]) if pd.notna(row.get("plate_z")) else None,
            launch_speed=launch_speed,
            launch_angle=launch_angle,
            events=str(row.get("events", "")) if pd.notna(row.get("events")) else None,
            description=description if description else None,
            zone=int(row["zone"]) if pd.notna(row.get("zone")) else None,
            spin_rate=float(row["release_spin_rate"]) if pd.notna(row.get("release_spin_rate")) else None,
            is_whiff=is_whiff,
            is_barrel=is_barrel,
            is_hard_hit=is_hard_hit,
        )
        batch.append(pitch)

        if len(batch) >= 5000:
            db.bulk_save_objects(batch)
            db.commit()
            count += len(batch)
            batch = []

    if batch:
        db.bulk_save_objects(batch)
        db.commit()
        count += len(batch)

    return count


def compute_team_season_stats(team: str, season: int, db: Session) -> TeamSeasonStats:
    """Compute team aggregate stats from individual player stats and game results."""
    games = db.query(Game).filter(
        Game.season == season,
        Game.status == "final",
        ((Game.home_team == team) | (Game.away_team == team)),
    ).all()

    wins = sum(1 for g in games if (
        (g.home_team == team and g.home_score > g.away_score) or
        (g.away_team == team and g.away_score > g.home_score)
    ))
    losses = len(games) - wins
    rs = sum(g.home_score if g.home_team == team else g.away_score for g in games
             if g.home_score is not None)
    ra = sum(g.away_score if g.home_team == team else g.home_score for g in games
             if g.away_score is not None)

    # Pythagorean wins (exponent = 1.83 is standard)
    pythag_wins = None
    pythag_losses = None
    if rs + ra > 0:
        exp = 1.83
        pythag_pct = (rs ** exp) / (rs ** exp + ra ** exp)
        pythag_wins = round(pythag_pct * len(games), 1)
        pythag_losses = round((1 - pythag_pct) * len(games), 1)

    # Aggregate pitching stats from pitcher season stats
    pitcher_stats = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == season,
        PitcherSeasonStats.team == team,
    ).all()

    team_era = None
    team_fip = None
    team_k_pct = None
    team_bb_pct = None
    if pitcher_stats:
        total_ip = sum(p.ip or 0 for p in pitcher_stats)
        if total_ip > 0:
            team_era = sum((p.era or 0) * (p.ip or 0) for p in pitcher_stats) / total_ip
            team_fip = sum((p.fip or 0) * (p.ip or 0) for p in pitcher_stats) / total_ip
        k_pcts = [p.k_pct for p in pitcher_stats if p.k_pct is not None]
        bb_pcts = [p.bb_pct for p in pitcher_stats if p.bb_pct is not None]
        if k_pcts:
            team_k_pct = sum(k_pcts) / len(k_pcts)
        if bb_pcts:
            team_bb_pct = sum(bb_pcts) / len(bb_pcts)

    # Aggregate hitting stats
    hitter_stats = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season,
        HitterSeasonStats.team == team,
    ).all()

    team_wrc_plus = None
    team_woba = None
    team_hard_hit_pct = None
    team_barrel_pct = None
    if hitter_stats:
        wrc_vals = [h.wrc_plus for h in hitter_stats if h.wrc_plus is not None and h.pa and h.pa > 0]
        if wrc_vals:
            total_pa = sum(h.pa for h in hitter_stats if h.wrc_plus is not None and h.pa)
            team_wrc_plus = sum(
                h.wrc_plus * h.pa for h in hitter_stats
                if h.wrc_plus is not None and h.pa
            ) / total_pa
        woba_vals = [h for h in hitter_stats if h.woba is not None and h.pa and h.pa > 0]
        if woba_vals:
            total_pa = sum(h.pa for h in woba_vals)
            team_woba = sum(h.woba * h.pa for h in woba_vals) / total_pa
        hh_vals = [h.hard_hit_pct for h in hitter_stats if h.hard_hit_pct is not None]
        if hh_vals:
            team_hard_hit_pct = sum(hh_vals) / len(hh_vals)
        brl_vals = [h.barrel_pct for h in hitter_stats if h.barrel_pct is not None]
        if brl_vals:
            team_barrel_pct = sum(brl_vals) / len(brl_vals)

    team_stats = TeamSeasonStats(
        team=team,
        season=season,
        games_played=len(games),
        wins=wins,
        losses=losses,
        runs_scored=rs,
        runs_allowed=ra,
        team_era=round(team_era, 2) if team_era else None,
        team_fip=round(team_fip, 2) if team_fip else None,
        team_wrc_plus=round(team_wrc_plus, 1) if team_wrc_plus else None,
        team_woba=round(team_woba, 3) if team_woba else None,
        team_k_pct=round(team_k_pct, 3) if team_k_pct else None,
        team_bb_pct=round(team_bb_pct, 3) if team_bb_pct else None,
        team_hard_hit_pct=round(team_hard_hit_pct, 3) if team_hard_hit_pct else None,
        team_barrel_pct=round(team_barrel_pct, 3) if team_barrel_pct else None,
        pythag_wins=pythag_wins,
        pythag_losses=pythag_losses,
        run_diff=rs - ra,
    )

    existing = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == team,
        TeamSeasonStats.season == season,
    ).first()

    if existing:
        for col in team_stats.__table__.columns:
            if col.name not in ("id",):
                setattr(existing, col.name, getattr(team_stats, col.name))
        db.commit()
        return existing
    else:
        db.add(team_stats)
        db.commit()
        return team_stats


def parse_boxscore_pitchers(boxscore: dict, game_pk: int, game_date: date,
                            season: int, team_key: str, db: Session) -> int:
    """Parse pitcher stats from an MLB Stats API boxscore."""
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

        # Upsert player
        player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
        if not player:
            player = Player(mlb_id=mlb_id, name=name, position="P", is_cubs=True)
            db.add(player)

        ip_str = stats.get("inningsPitched", "0")
        try:
            ip = float(ip_str)
        except (ValueError, TypeError):
            ip = 0

        game_stats = PitcherGameStats(
            player_id=mlb_id,
            game_pk=game_pk,
            game_date=game_date,
            season=season,
            ip=ip,
            hits=int(stats.get("hits", 0)),
            runs=int(stats.get("runs", 0)),
            earned_runs=int(stats.get("earnedRuns", 0)),
            walks=int(stats.get("baseOnBalls", 0)),
            strikeouts=int(stats.get("strikeOuts", 0)),
            home_runs=int(stats.get("homeRuns", 0)),
            pitches=int(stats.get("numberOfPitches", 0)),
            era=float(stats["era"]) if stats.get("era") and stats["era"] != "-.--" else None,
        )
        db.add(game_stats)
        count += 1

    db.commit()
    return count


def parse_boxscore_hitters(boxscore: dict, game_pk: int, game_date: date,
                           season: int, team_key: str, db: Session) -> int:
    """Parse hitter stats from an MLB Stats API boxscore."""
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

        player = db.query(Player).filter(Player.mlb_id == mlb_id).first()
        if not player:
            pos = player_data.get("position", {}).get("abbreviation", "")
            player = Player(mlb_id=mlb_id, name=name, position=pos, is_cubs=True)
            db.add(player)

        game_stats = HitterGameStats(
            player_id=mlb_id,
            game_pk=game_pk,
            game_date=game_date,
            season=season,
            ab=int(stats.get("atBats", 0)),
            hits=int(stats.get("hits", 0)),
            doubles=int(stats.get("doubles", 0)),
            triples=int(stats.get("triples", 0)),
            home_runs=int(stats.get("homeRuns", 0)),
            rbi=int(stats.get("rbi", 0)),
            walks=int(stats.get("baseOnBalls", 0)),
            strikeouts=int(stats.get("strikeOuts", 0)),
            stolen_bases=int(stats.get("stolenBases", 0)),
        )
        db.add(game_stats)
        count += 1

    db.commit()
    return count
