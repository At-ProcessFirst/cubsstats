from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, PitcherSeasonStats, Player
from app.models.schemas import PitcherSeasonStatsResponse

router = APIRouter()


@router.get("/cubs", response_model=list[PitcherSeasonStatsResponse])
def get_cubs_pitchers(
    season: Optional[int] = None,
    position_group: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get all Cubs pitcher season stats."""
    q = db.query(PitcherSeasonStats).filter(PitcherSeasonStats.team == "CHC")
    if season:
        q = q.filter(PitcherSeasonStats.season == season)
    else:
        latest = db.query(PitcherSeasonStats.season).filter(
            PitcherSeasonStats.team == "CHC"
        ).order_by(PitcherSeasonStats.season.desc()).first()
        if latest:
            q = q.filter(PitcherSeasonStats.season == latest[0])
    if position_group:
        q = q.filter(PitcherSeasonStats.position_group == position_group)
    return q.all()


@router.get("/player/{player_id}", response_model=Optional[PitcherSeasonStatsResponse])
def get_pitcher_stats(
    player_id: int,
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get a specific pitcher's season stats."""
    q = db.query(PitcherSeasonStats).filter(PitcherSeasonStats.player_id == player_id)
    if season:
        q = q.filter(PitcherSeasonStats.season == season)
    else:
        q = q.order_by(PitcherSeasonStats.season.desc())
    return q.first()


@router.get("/leaderboard", response_model=list[PitcherSeasonStatsResponse])
def pitching_leaderboard(
    stat: str = Query("era", description="Stat to sort by"),
    position_group: str = Query("SP", description="SP or RP"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """MLB-wide pitching leaderboard for a given stat."""
    latest = db.query(PitcherSeasonStats.season).order_by(
        PitcherSeasonStats.season.desc()
    ).first()
    if not latest:
        return []

    q = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == latest[0],
        PitcherSeasonStats.position_group == position_group,
        PitcherSeasonStats.ip >= 20,  # minimum IP filter
    )

    col = getattr(PitcherSeasonStats, stat, None)
    if col is not None:
        lower_better = stat in ("era", "fip", "xfip", "xera", "bb_pct", "hard_hit_pct", "barrel_pct")
        q = q.filter(col.isnot(None))
        q = q.order_by(col.asc() if lower_better else col.desc())

    return q.limit(limit).all()


@router.get("/cubs/enriched")
def get_cubs_pitchers_enriched(
    season: Optional[int] = None,
    position_group: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get Cubs pitcher stats enriched with player names and benchmarks."""
    q = db.query(PitcherSeasonStats).filter(PitcherSeasonStats.team == "CHC")
    if season:
        q = q.filter(PitcherSeasonStats.season == season)
    else:
        latest = db.query(PitcherSeasonStats.season).filter(
            PitcherSeasonStats.team == "CHC"
        ).order_by(PitcherSeasonStats.season.desc()).first()
        if latest:
            q = q.filter(PitcherSeasonStats.season == latest[0])
    if position_group:
        q = q.filter(PitcherSeasonStats.position_group == position_group)

    pitchers = q.all()
    result = []
    for p in pitchers:
        player = db.query(Player).filter(Player.mlb_id == p.player_id).first()
        d = {c.name: getattr(p, c.name) for c in p.__table__.columns if c.name != "id"}
        d["name"] = player.name if player else f"Player {p.player_id}"
        d["position"] = player.position if player else "P"
        result.append(d)
    return result
