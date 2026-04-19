from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.models.database import get_db, TeamSeasonStats, Game, PitcherSeasonStats
from app.models.schemas import TeamStatsResponse, GameResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/stats")
def get_team_stats(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get Cubs team aggregate stats. Computes K%/BB% on the fly if missing."""
    q = db.query(TeamSeasonStats).filter(TeamSeasonStats.team == "CHC")
    if season:
        q = q.filter(TeamSeasonStats.season == season)
    else:
        q = q.order_by(TeamSeasonStats.season.desc())
    stats = q.first()

    if not stats:
        return None

    # Build response dict from the ORM object
    result = {
        "team": stats.team,
        "season": stats.season,
        "games_played": stats.games_played or 0,
        "wins": stats.wins or 0,
        "losses": stats.losses or 0,
        "runs_scored": stats.runs_scored or 0,
        "runs_allowed": stats.runs_allowed or 0,
        "team_era": stats.team_era,
        "team_fip": stats.team_fip,
        "team_wrc_plus": stats.team_wrc_plus,
        "team_woba": stats.team_woba,
        "team_k_pct": stats.team_k_pct,
        "team_bb_pct": stats.team_bb_pct,
        "pythag_wins": stats.pythag_wins,
        "pythag_losses": stats.pythag_losses,
        "run_diff": stats.run_diff,
    }

    # If K% or BB% are null, compute directly from pitcher_season_stats
    target_season = season or stats.season
    if result["team_k_pct"] is None or result["team_bb_pct"] is None:
        row = db.execute(text("""
            SELECT
                ROUND(CAST(SUM(k_pct * ip) AS FLOAT) / NULLIF(SUM(ip), 0), 1) as team_k_pct,
                ROUND(CAST(SUM(bb_pct * ip) AS FLOAT) / NULLIF(SUM(ip), 0), 1) as team_bb_pct
            FROM pitcher_season_stats
            WHERE season = :season AND team = 'CHC' AND ip > 0
                AND k_pct IS NOT NULL AND bb_pct IS NOT NULL
        """), {"season": target_season}).fetchone()

        if row:
            if result["team_k_pct"] is None and row.team_k_pct is not None:
                result["team_k_pct"] = float(row.team_k_pct)
            if result["team_bb_pct"] is None and row.team_bb_pct is not None:
                result["team_bb_pct"] = float(row.team_bb_pct)

    return result


@router.get("/games", response_model=list[GameResponse])
def get_cubs_games(
    season: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Get recent Cubs games."""
    q = db.query(Game).filter(
        (Game.home_team == "CHC") | (Game.away_team == "CHC")
    )
    if season:
        q = q.filter(Game.season == season)
    q = q.order_by(Game.game_date.desc()).limit(limit)
    return q.all()


@router.get("/record")
def get_team_record(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get current Cubs W-L record with Pythagorean projection."""
    stats = db.query(TeamSeasonStats).filter(TeamSeasonStats.team == "CHC")
    if season:
        stats = stats.filter(TeamSeasonStats.season == season)
    else:
        stats = stats.order_by(TeamSeasonStats.season.desc())
    stats = stats.first()

    if not stats:
        return {"wins": 0, "losses": 0, "pythag_wins": 0, "pythag_losses": 0, "run_diff": 0}

    return {
        "wins": stats.wins,
        "losses": stats.losses,
        "games_played": stats.games_played,
        "pythag_wins": stats.pythag_wins,
        "pythag_losses": stats.pythag_losses,
        "run_diff": stats.run_diff,
        "runs_scored": stats.runs_scored,
        "runs_allowed": stats.runs_allowed,
    }


@router.get("/win-trend")
def get_win_trend(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Build win trend data for the chart: cumulative wins per game with Pythagorean + .500 pace + ML predicted."""
    from app.services.ml_engine import predict_win_trend
    from app.services.features import _rolling_pythag, _game_runs

    current_season = season or date.today().year
    games = db.query(Game).filter(
        Game.season == current_season,
        Game.status == "final",
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
    ).order_by(Game.game_date.asc()).all()

    if not games:
        return []

    trend = []
    cum_wins = 0
    cum_rs = 0
    cum_ra = 0
    for i, g in enumerate(games, 1):
        is_home = g.home_team == "CHC"
        won = g.cubs_won
        if won:
            cum_wins += 1
        rs = g.home_score if is_home else g.away_score
        ra = g.away_score if is_home else g.home_score
        cum_rs += (rs or 0)
        cum_ra += (ra or 0)

        # Pythagorean expected wins
        pythag = None
        if cum_rs + cum_ra > 0:
            exp = 1.83
            pythag_pct = (cum_rs ** exp) / (cum_rs ** exp + cum_ra ** exp)
            pythag = round(pythag_pct * i, 1)

        trend.append({
            "game": i,
            "date": g.game_date.isoformat(),
            "actual": cum_wins,
            "pythagorean": pythag,
            "pace500": round(i * 0.5, 1),
            "predicted": None,
            "ciLow": None,
            "ciHigh": None,
        })

    # Overlay ML predicted win trend (needs 30+ games)
    if len(games) >= 30:
        try:
            window = games[-30:]
            pythag_wpct = _rolling_pythag(window, 30) or 0.500

            # Compute simple trends from run data
            ra_per_game = [_game_runs(g)[1] for g in window]
            rs_per_game = [_game_runs(g)[0] for g in window]
            import numpy as np
            ra_slope = float(np.polyfit(range(len(ra_per_game)), ra_per_game, 1)[0]) if len(ra_per_game) >= 3 else 0.0
            rs_slope = float(np.polyfit(range(len(rs_per_game)), rs_per_game, 1)[0]) if len(rs_per_game) >= 3 else 0.0

            features = {
                "rolling_30g_pythag_wpct": pythag_wpct,
                "fip_trend": ra_slope,
                "wrc_plus_trend": rs_slope,
                "roster_war": 0.0,
                "sos_remaining": 0.500,
            }
            result = predict_win_trend(features)
            if result.get("status") == "active" and result.get("predicted_wins") is not None:
                pred_wins = result["predicted_wins"]
                ci_low = result.get("ci_lower", pred_wins - 1.5)
                ci_high = result.get("ci_upper", pred_wins + 1.5)
                current_wins = cum_wins
                # Project from current game forward
                for j in range(10):
                    game_num = len(games) + j + 1
                    projected = round(current_wins + (pred_wins * (j + 1) / 10), 1)
                    trend.append({
                        "game": game_num,
                        "date": None,
                        "actual": None,
                        "pythagorean": None,
                        "pace500": round(game_num * 0.5, 1),
                        "predicted": projected,
                        "ciLow": round(current_wins + (ci_low * (j + 1) / 10), 1),
                        "ciHigh": round(current_wins + (ci_high * (j + 1) / 10), 1),
                    })
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Win trend prediction failed: {e}")

    return trend


@router.get("/live-context")
def get_live_context():
    """Get live Cubs data from MLB Stats API (standings, injuries, leaders, transactions, today's game)."""
    try:
        from app.services.live_context import get_live_context_data
        return get_live_context_data()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Live context failed: {e}")
        return {
            "date": None, "standings": [], "injuries": [], "team_leaders": {},
            "transactions": [], "streak": {"type": "W", "count": 0}, "today": None,
        }


@router.get("/upcoming")
def get_upcoming_games(
    limit: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Get upcoming scheduled Cubs games."""
    today = date.today()
    games = db.query(Game).filter(
        Game.game_date >= today,
        Game.status == "scheduled",
        ((Game.home_team == "CHC") | (Game.away_team == "CHC")),
    ).order_by(Game.game_date.asc()).limit(limit).all()

    result = []
    for g in games:
        is_home = g.home_team == "CHC"
        result.append({
            "game_pk": g.game_pk,
            "date": g.game_date.isoformat(),
            "opponent": g.away_team if is_home else g.home_team,
            "is_home": is_home,
        })
    return result
