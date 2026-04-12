from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, HitterSeasonStats, Player
from app.models.schemas import HitterSeasonStatsResponse

router = APIRouter()


@router.get("/cubs", response_model=list[HitterSeasonStatsResponse])
def get_cubs_hitters(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get all Cubs hitter season stats."""
    q = db.query(HitterSeasonStats).filter(HitterSeasonStats.team == "CHC")
    if season:
        q = q.filter(HitterSeasonStats.season == season)
    else:
        latest = db.query(HitterSeasonStats.season).filter(
            HitterSeasonStats.team == "CHC"
        ).order_by(HitterSeasonStats.season.desc()).first()
        if latest:
            q = q.filter(HitterSeasonStats.season == latest[0])
    return q.all()


@router.get("/player/{player_id}", response_model=Optional[HitterSeasonStatsResponse])
def get_hitter_stats(
    player_id: int,
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get a specific hitter's season stats."""
    q = db.query(HitterSeasonStats).filter(HitterSeasonStats.player_id == player_id)
    if season:
        q = q.filter(HitterSeasonStats.season == season)
    else:
        q = q.order_by(HitterSeasonStats.season.desc())
    return q.first()


@router.get("/leaderboard", response_model=list[HitterSeasonStatsResponse])
def hitting_leaderboard(
    stat: str = Query("wrc_plus", description="Stat to sort by"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """MLB-wide hitting leaderboard for a given stat."""
    latest = db.query(HitterSeasonStats.season).order_by(
        HitterSeasonStats.season.desc()
    ).first()
    if not latest:
        return []

    q = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == latest[0],
        HitterSeasonStats.pa >= 50,  # minimum PA filter
    )

    col = getattr(HitterSeasonStats, stat, None)
    if col is not None:
        lower_better = stat in ("o_swing_pct", "chase_rate")
        q = q.filter(col.isnot(None))
        q = q.order_by(col.asc() if lower_better else col.desc())

    return q.limit(limit).all()


@router.get("/cubs/enriched")
def get_cubs_hitters_enriched(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get Cubs hitter stats enriched with player names."""
    q = db.query(HitterSeasonStats).filter(HitterSeasonStats.team == "CHC")
    if season:
        q = q.filter(HitterSeasonStats.season == season)
    else:
        latest = db.query(HitterSeasonStats.season).filter(
            HitterSeasonStats.team == "CHC"
        ).order_by(HitterSeasonStats.season.desc()).first()
        if latest:
            q = q.filter(HitterSeasonStats.season == latest[0])

    hitters = q.all()
    result = []
    for h in hitters:
        player = db.query(Player).filter(Player.mlb_id == h.player_id).first()
        d = {c.name: getattr(h, c.name) for c in h.__table__.columns if c.name != "id"}
        d["name"] = player.name if player else f"Player {h.player_id}"
        d["position"] = player.position if player else ""
        result.append(d)
    return result
