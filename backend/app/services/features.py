"""
Feature engineering pipeline — transforms raw stats into ML model features.

Two feature sets:
  1. Game Outcome features (per-game): rolling 10-game team metrics + opponent + situational
  2. Win Trend features (rolling windows): 30-game Pythagorean, trends, schedule strength

Also provides z-score computation for regression detection.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import (
    Game, PitcherSeasonStats, PitcherGameStats, HitterSeasonStats,
    HitterGameStats, TeamSeasonStats, DefenseSeasonStats,
    PlayerBenchmark, Benchmark, Player,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plain English feature labels (displayed in frontend)
# ---------------------------------------------------------------------------

FEATURE_LABELS = {
    "rolling_10g_fip": "Pitching quality (10-game)",
    "rolling_10g_wrc_plus": "Hitting trend (10-game)",
    "team_oaa": "Team defense",
    "run_diff_10g": "Run margin (10-game)",
    "is_home": "Home vs away",
    "opponent_win_pct": "Opponent strength",
    "rest_days": "Rest days",
    "bullpen_usage_3d": "Bullpen fatigue",
    "cubs_starter_era": "Cubs starter quality",
    "opp_starter_era": "Opponent starter quality",
    "is_day_game": "Day vs night game",
    "streak_length": "Win/loss streak",
    "rolling_30g_pythag_wpct": "Pythagorean pace (30-game)",
    "fip_trend": "Pitching trend",
    "wrc_plus_trend": "Hitting trend",
    "roster_war": "Roster quality",
    "sos_remaining": "Schedule difficulty remaining",
}

GAME_OUTCOME_FEATURE_NAMES = [
    "rolling_10g_fip", "rolling_10g_wrc_plus", "team_oaa",
    "run_diff_10g", "is_home", "opponent_win_pct",
    "rest_days", "bullpen_usage_3d",
    "cubs_starter_era", "opp_starter_era", "is_day_game", "streak_length",
]

WIN_TREND_FEATURE_NAMES = [
    "rolling_30g_pythag_wpct", "fip_trend", "wrc_plus_trend",
    "roster_war", "sos_remaining",
]


# ---------------------------------------------------------------------------
# Helper: get recent Cubs games in order
# ---------------------------------------------------------------------------

def _get_cubs_games(season: int, db: Session, limit: int = None) -> list[Game]:
    """Get Cubs final games for a season, oldest first."""
    q = db.query(Game).filter(
        Game.season == season,
        Game.status == "final",
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
    ).order_by(Game.game_date.asc())
    if limit:
        q = q.limit(limit)
    return q.all()


def _game_runs(game: Game) -> tuple:
    """Return (cubs_rs, cubs_ra) for a game."""
    if game.home_team == "CHC":
        return (game.home_score or 0, game.away_score or 0)
    return (game.away_score or 0, game.home_score or 0)


def _opponent_abbr(game: Game) -> str:
    return game.away_team if game.home_team == "CHC" else game.home_team


# ---------------------------------------------------------------------------
# Rolling stat computations
# ---------------------------------------------------------------------------

def _rolling_run_diff(games: list[Game], window: int) -> float:
    """Sum of (RS - RA) over the last `window` games."""
    recent = games[-window:]
    return sum(_game_runs(g)[0] - _game_runs(g)[1] for g in recent)


def _rolling_pythag(games: list[Game], window: int) -> Optional[float]:
    """Pythagorean win% over last `window` games."""
    recent = games[-window:]
    rs = sum(_game_runs(g)[0] for g in recent)
    ra = sum(_game_runs(g)[1] for g in recent)
    if rs + ra == 0:
        return None
    exp = 1.83
    return (rs ** exp) / (rs ** exp + ra ** exp)


def _opponent_win_pct(opponent: str, season: int, db: Session) -> float:
    """Get opponent's Pythagorean win% from team_strength table.

    Uses Pythagorean W% (more stable than raw record) if available,
    falls back to team_season_stats, then .500.
    """
    # Primary: team_strength table (all 30 teams, Pythagorean)
    try:
        from app.models.database import TeamStrength
        ts = db.query(TeamStrength).filter(
            TeamStrength.team_abbrev == opponent,
            TeamStrength.season == season,
        ).first()
        if ts and ts.pythag_wpct is not None:
            return ts.pythag_wpct
    except Exception:
        pass

    # Fallback: team_season_stats
    stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == opponent,
        TeamSeasonStats.season == season,
    ).first()
    if stats and stats.games_played and stats.games_played > 0:
        return stats.wins / stats.games_played
    return 0.500


def _bullpen_innings_last_3d(game_date, season: int, db: Session) -> float:
    """Total Cubs reliever innings in the 3 days before game_date.
    Uses IP < 5.0 heuristic to identify relievers (works even when position_group not set).
    """
    start = game_date - timedelta(days=3)
    try:
        rp_games = db.query(PitcherGameStats).join(
            Player, PitcherGameStats.player_id == Player.mlb_id
        ).filter(
            PitcherGameStats.season == season,
            PitcherGameStats.game_date >= start,
            PitcherGameStats.game_date < game_date,
            Player.is_cubs == True,
            PitcherGameStats.ip < 5.0,  # Reliever heuristic
        ).all()
        return sum(g.ip or 0 for g in rp_games)
    except Exception:
        return 0.0


def _get_starter_era(game_pk: int, team_abbrev: str, season: int, db: Session) -> float:
    """Get the starting pitcher's ERA for a specific game.

    Uses Game.home_starter_id / away_starter_id (stored during ingestion) to look up
    the starter's season ERA from pitcher_season_stats (league-wide data).
    No API calls — fully DB-driven for both historical and upcoming games.
    Falls back to 4.00 if no starter data available.
    """
    game = db.query(Game).filter(Game.game_pk == game_pk).first()
    if not game:
        return 4.00

    # Determine which starter ID to use based on team
    if team_abbrev == game.home_team:
        starter_id = game.home_starter_id
    elif team_abbrev == game.away_team:
        starter_id = game.away_starter_id
    else:
        # Team abbreviation matches neither side — try Cubs-specific logic
        if team_abbrev == "CHC":
            starter_id = game.home_starter_id if game.cubs_home else game.away_starter_id
        else:
            starter_id = game.away_starter_id if game.cubs_home else game.home_starter_id

    if starter_id:
        ps = db.query(PitcherSeasonStats).filter(
            PitcherSeasonStats.player_id == starter_id,
            PitcherSeasonStats.season == season,
        ).first()
        if ps and ps.era is not None:
            return ps.era

    return 4.00


def _get_day_night(game_pk: int, db: Session) -> float:
    """Return 1.0 for day game, 0.0 for night game. DB-first, API fallback for upcoming."""
    game = db.query(Game).filter(Game.game_pk == game_pk).first()
    if game and game.day_night:
        return 1.0 if game.day_night == "day" else 0.0

    # Only call API for games without day_night stored (upcoming/not yet ingested)
    if game and game.status != "final":
        try:
            from app.services.ingestion import mlb_api_get
            data = mlb_api_get("/schedule", {"gamePk": game_pk})
            for d in data.get("dates", []):
                for g in d.get("games", []):
                    return 1.0 if g.get("dayNight") == "day" else 0.0
        except Exception:
            pass

    return 0.0


def _get_streak(season: int, db: Session, before_date=None) -> float:
    """Compute Cubs win/loss streak from game results in DB.

    For historical games: pass before_date to get streak as of that game.
    For upcoming games: pass None to get current streak.
    """
    query = db.query(Game).filter(
        Game.season == season, Game.status == "final",
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
    ).order_by(Game.game_date.desc())

    if before_date:
        query = query.filter(Game.game_date < before_date)

    games = query.limit(20).all()
    if not games:
        return 0.0

    streak = 0
    first_result = games[0].cubs_won
    for g in games:
        if g.cubs_won == first_result:
            streak += 1
        else:
            break

    return float(streak) if first_result else float(-streak)


def _team_oaa(season: int, db: Session) -> float:
    """Sum of OAA across Cubs defenders."""
    defs = db.query(DefenseSeasonStats).filter(
        DefenseSeasonStats.season == season,
        DefenseSeasonStats.team == "CHC",
    ).all()
    return sum(d.oaa or 0 for d in defs)


def _compute_trend_slope(values: list[float]) -> float:
    """Simple linear regression slope over a list of values."""
    if len(values) < 3:
        return 0.0
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    # Remove NaN
    mask = ~np.isnan(y)
    if mask.sum() < 3:
        return 0.0
    x, y = x[mask], y[mask]
    n = len(x)
    slope = (n * np.dot(x, y) - x.sum() * y.sum()) / (n * np.dot(x, x) - x.sum() ** 2 + 1e-10)
    return float(slope)


# ---------------------------------------------------------------------------
# Game Outcome features (per-game)
# ---------------------------------------------------------------------------

def build_game_features(game_pk: int, db: Session) -> Optional[dict]:
    """Build feature vector for a specific game.

    Computes all features from game results directly (no dependency on
    box score tables), so it works for historical seasons where we only
    have schedule data + season stats.
    """
    game = db.query(Game).filter(Game.game_pk == game_pk).first()
    if not game:
        return None

    season = game.season
    all_games = _get_cubs_games(season, db)

    game_idx = None
    for i, g in enumerate(all_games):
        if g.game_pk == game_pk:
            game_idx = i
            break

    if game_idx is None or game_idx < 10:
        return None

    prior = all_games[:game_idx]
    last10 = prior[-10:]

    # Rolling 10-game run differential
    run_diff_10g = sum(_game_runs(g)[0] - _game_runs(g)[1] for g in last10)

    # Rolling 10-game: raw runs allowed per game (pitching quality proxy)
    # Lower = better pitching. NOT overridden with season constants.
    rolling_ra_per_g = sum(_game_runs(g)[1] for g in last10) / 10.0

    # Rolling 10-game: raw runs scored per game (hitting quality proxy)
    # Higher = better hitting. NOT overridden with season constants.
    rolling_rs_per_g = sum(_game_runs(g)[0] for g in last10) / 10.0

    # Opponent strength from team_strength table (Pythagorean win%)
    opp = _opponent_abbr(game)
    opp_wpct = _opponent_win_pct(opp, season, db)

    # Rest days
    rest = (game.game_date - prior[-1].game_date).days if prior else 1.0

    features = {
        "rolling_10g_fip": rolling_ra_per_g,       # RA/game (lower = better)
        "rolling_10g_wrc_plus": rolling_rs_per_g,   # RS/game (higher = better)
        "team_oaa": _team_oaa(season, db),
        "run_diff_10g": float(run_diff_10g),
        "is_home": 1.0 if game.home_team == "CHC" else 0.0,
        "opponent_win_pct": opp_wpct,
        "rest_days": float(max(0, rest)),
        "bullpen_usage_3d": _bullpen_innings_last_3d(game.game_date, season, db),
        "cubs_starter_era": _get_starter_era(game_pk, "CHC", season, db),
        "opp_starter_era": _get_starter_era(game_pk, opp, season, db),
        "is_day_game": _get_day_night(game_pk, db),
        "streak_length": _get_streak(season, db, before_date=game.game_date),
    }
    return features


def _rest_days(game: Game, prior_games: list[Game]) -> float:
    """Days since last game."""
    if not prior_games:
        return 1.0
    last = prior_games[-1]
    delta = (game.game_date - last.game_date).days
    return float(max(0, delta))


def build_prediction_features(game_pk: int, db: Session) -> Optional[dict]:
    """Build features for a scheduled/upcoming game.

    Unlike build_game_features(), this uses the most recent COMPLETED games
    to compute rolling features — the game itself doesn't need to be final.
    For early-season games with <10 completed, looks back into prior season.
    """
    game = db.query(Game).filter(Game.game_pk == game_pk).first()
    if not game:
        return None

    season = game.season
    # All completed Cubs games up to this game's date
    completed = db.query(Game).filter(
        Game.season == season, Game.status == "final",
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        Game.game_date <= game.game_date,
    ).order_by(Game.game_date.asc()).all()

    # If not enough current-season games, prepend prior season
    if len(completed) < 10:
        prior = db.query(Game).filter(
            Game.season == season - 1, Game.status == "final",
            ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
        ).order_by(Game.game_date.asc()).all()
        completed = prior + completed

    if len(completed) < 10:
        return None

    last10 = completed[-10:]

    rolling_ra_per_g = sum(_game_runs(g)[1] for g in last10) / 10.0
    rolling_rs_per_g = sum(_game_runs(g)[0] for g in last10) / 10.0
    run_diff_10g = sum(_game_runs(g)[0] - _game_runs(g)[1] for g in last10)

    opp = game.away_team if game.home_team == "CHC" else game.home_team
    opp_wpct = _opponent_win_pct(opp, season, db)
    rest = max(0, (game.game_date - completed[-1].game_date).days) if completed else 1.0

    return {
        "rolling_10g_fip": rolling_ra_per_g,
        "rolling_10g_wrc_plus": rolling_rs_per_g,
        "team_oaa": _team_oaa(season, db),
        "run_diff_10g": float(run_diff_10g),
        "is_home": 1.0 if game.home_team == "CHC" else 0.0,
        "opponent_win_pct": opp_wpct,
        "rest_days": float(rest),
        "bullpen_usage_3d": _bullpen_innings_last_3d(game.game_date, season, db),
        "cubs_starter_era": _get_starter_era(game_pk, "CHC", season, db),
        "opp_starter_era": _get_starter_era(game_pk, opp, season, db),
        "is_day_game": _get_day_night(game_pk, db),
        "streak_length": _get_streak(season, db),
    }


def build_training_dataset(season: int, db: Session) -> Optional[pd.DataFrame]:
    """Build training dataset: one row per game with features + win/loss target."""
    all_games = _get_cubs_games(season, db)
    if len(all_games) < 20:
        logger.warning(f"Only {len(all_games)} games in {season}, need 20+ for training")
        return None

    rows = []
    for i in range(10, len(all_games)):
        game = all_games[i]
        features = build_game_features(game.game_pk, db)
        if features is None:
            continue
        features["target"] = 1.0 if game.cubs_won else 0.0
        features["game_pk"] = game.game_pk
        rows.append(features)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    logger.info(f"Built training dataset: {len(df)} games for {season}")
    return df


# ---------------------------------------------------------------------------
# Win Trend features (rolling windows)
# ---------------------------------------------------------------------------

def build_trend_features(season: int, db: Session) -> Optional[pd.DataFrame]:
    """Build feature matrix for win trend model.

    One row per 10-game window, target = wins in next 10 games.
    """
    all_games = _get_cubs_games(season, db)
    if len(all_games) < 40:
        logger.warning(f"Only {len(all_games)} games, need 40+ for trend features")
        return None

    cubs_stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC",
        TeamSeasonStats.season == season,
    ).first()

    # Compute per-game cumulative metrics for slopes
    cum_fips = []
    cum_wrcs = []
    pitchers = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == season,
        PitcherSeasonStats.team == "CHC",
    ).all()
    avg_fip = np.mean([p.fip for p in pitchers if p.fip]) if pitchers else 4.0

    hitters = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season,
        HitterSeasonStats.team == "CHC",
    ).all()
    avg_wrc = np.mean([h.wrc_plus for h in hitters if h.wrc_plus]) if hitters else 100.0

    # Strength of schedule: average opponent win% for remaining games
    def sos_remaining(idx):
        remaining = all_games[idx:]
        if not remaining:
            return 0.500
        wpcts = []
        for g in remaining:
            opp = _opponent_abbr(g)
            wpcts.append(_opponent_win_pct(opp, season, db))
        return np.mean(wpcts) if wpcts else 0.500

    rows = []
    for i in range(30, len(all_games) - 10):
        window = all_games[i - 30:i]
        target_window = all_games[i:i + 10]
        target_wins = sum(1 for g in target_window if g.cubs_won)

        pythag = _rolling_pythag(window, 30)

        # Compute actual trends from per-game run data
        ra_per_game = [_game_runs(g)[1] for g in window]  # RA as FIP proxy
        rs_per_game = [_game_runs(g)[0] for g in window]  # RS as wRC+ proxy
        fip_trend = _compute_trend_slope(ra_per_game)
        wrc_trend = _compute_trend_slope(rs_per_game)

        features = {
            "rolling_30g_pythag_wpct": pythag or 0.500,
            "fip_trend": fip_trend,
            "wrc_plus_trend": wrc_trend,
            "roster_war": 0.0,
            "sos_remaining": sos_remaining(i),
            "target": float(target_wins),
            "game_index": i,
        }
        rows.append(features)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    logger.info(f"Built trend dataset: {len(df)} windows for {season}")
    return df


# ---------------------------------------------------------------------------
# Z-score computation for regression detection
# ---------------------------------------------------------------------------

def compute_player_zscores(season: int, db: Session) -> list[dict]:
    """Compute z-scores for each Cubs player stat vs MLB benchmarks.

    Returns list of { player_id, player_name, stat_name, value, mlb_mean,
    mlb_std, z_score, regression_probability, direction }
    """
    results = []

    # Pitchers
    pitchers = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == season,
        PitcherSeasonStats.team == "CHC",
        PitcherSeasonStats.ip >= 15,
    ).all()

    pitcher_stats = ["era", "fip", "k_pct", "bb_pct", "hard_hit_pct", "barrel_pct"]
    lower_is_better = {"era", "fip", "bb_pct", "hard_hit_pct", "barrel_pct"}

    for p in pitchers:
        player = db.query(Player).filter(Player.mlb_id == p.player_id).first()
        pos_group = p.position_group or "SP"

        for stat in pitcher_stats:
            val = getattr(p, stat, None)
            if val is None:
                continue

            bench = db.query(Benchmark).filter(
                Benchmark.season == season,
                Benchmark.stat_name == stat,
                Benchmark.position_group == pos_group,
            ).first()

            if not bench or bench.mean is None:
                continue

            # Estimate std from percentile breakpoints
            std = _estimate_std(bench)
            if std < 0.001:
                continue

            z = (val - bench.mean) / std

            # For lower-is-better, negative z = good
            if stat in lower_is_better:
                z = -z  # Flip so positive z = "better than average"

            # Regression probability: extreme z-scores regress toward mean
            abs_z = abs(z)
            if abs_z >= 2.0:
                reg_prob = min(0.95, 0.5 + abs_z * 0.15)
            elif abs_z >= 1.5:
                reg_prob = 0.4 + (abs_z - 1.5) * 0.2
            else:
                reg_prob = max(0.0, abs_z * 0.25)

            direction = "toward_mean"
            if z > 1.5:
                direction = "likely_decline"
            elif z < -1.5:
                direction = "likely_improve"

            results.append({
                "player_id": p.player_id,
                "player_name": player.name if player else f"Player {p.player_id}",
                "stat_name": stat,
                "value": round(val, 4),
                "mlb_mean": round(bench.mean, 4),
                "z_score": round(z, 2),
                "regression_probability": round(reg_prob, 2),
                "direction": direction,
                "position_group": pos_group,
            })

    # Hitters
    hitters = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season,
        HitterSeasonStats.team == "CHC",
        HitterSeasonStats.pa >= 30,
    ).all()

    hitter_stats = ["wrc_plus", "woba", "babip", "barrel_pct", "hard_hit_pct", "o_swing_pct"]
    hitter_lower = {"o_swing_pct"}

    for h in hitters:
        player = db.query(Player).filter(Player.mlb_id == h.player_id).first()

        for stat in hitter_stats:
            val = getattr(h, stat, None)
            if val is None:
                continue

            bench = db.query(Benchmark).filter(
                Benchmark.season == season,
                Benchmark.stat_name == stat,
                Benchmark.position_group == "ALL_HITTERS",
            ).first()

            if not bench or bench.mean is None:
                continue

            std = _estimate_std(bench)
            if std < 0.001:
                continue

            z = (val - bench.mean) / std
            if stat in hitter_lower:
                z = -z

            abs_z = abs(z)
            if abs_z >= 2.0:
                reg_prob = min(0.95, 0.5 + abs_z * 0.15)
            elif abs_z >= 1.5:
                reg_prob = 0.4 + (abs_z - 1.5) * 0.2
            else:
                reg_prob = max(0.0, abs_z * 0.25)

            direction = "toward_mean"
            if z > 1.5:
                direction = "likely_decline"
            elif z < -1.5:
                direction = "likely_improve"

            results.append({
                "player_id": h.player_id,
                "player_name": player.name if player else f"Player {h.player_id}",
                "stat_name": stat,
                "value": round(val, 4),
                "mlb_mean": round(bench.mean, 4),
                "z_score": round(z, 2),
                "regression_probability": round(reg_prob, 2),
                "direction": direction,
                "position_group": "ALL_HITTERS",
            })

    # Sort by regression probability (highest first)
    results.sort(key=lambda x: x["regression_probability"], reverse=True)
    return results


def _estimate_std(bench: Benchmark) -> float:
    """Estimate standard deviation from benchmark percentile breakpoints.

    Uses the IQR method: std ≈ (p75 - p25) / 1.35
    """
    if bench.p75 is not None and bench.p25 is not None:
        iqr = abs(bench.p75 - bench.p25)
        return iqr / 1.35 if iqr > 0 else 0.0
    if bench.p90 is not None and bench.p10 is not None:
        r = abs(bench.p90 - bench.p10)
        return r / 2.56 if r > 0 else 0.0
    return 0.0
