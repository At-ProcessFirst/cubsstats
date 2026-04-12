from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, DefenseSeasonStats, Player

router = APIRouter()


@router.get("/cubs")
def get_cubs_defense(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get Cubs defensive stats."""
    q = db.query(DefenseSeasonStats).filter(DefenseSeasonStats.team == "CHC")
    if season:
        q = q.filter(DefenseSeasonStats.season == season)
    else:
        latest = db.query(DefenseSeasonStats.season).filter(
            DefenseSeasonStats.team == "CHC"
        ).order_by(DefenseSeasonStats.season.desc()).first()
        if latest:
            q = q.filter(DefenseSeasonStats.season == latest[0])
    return q.all()


@router.get("/player/{player_id}")
def get_player_defense(
    player_id: int,
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get a specific player's defensive stats."""
    q = db.query(DefenseSeasonStats).filter(DefenseSeasonStats.player_id == player_id)
    if season:
        q = q.filter(DefenseSeasonStats.season == season)
    else:
        q = q.order_by(DefenseSeasonStats.season.desc())
    return q.first()


@router.get("/cubs/enriched")
def get_cubs_defense_enriched(
    season: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get Cubs defensive stats enriched with player names."""
    q = db.query(DefenseSeasonStats).filter(DefenseSeasonStats.team == "CHC")
    if season:
        q = q.filter(DefenseSeasonStats.season == season)
    else:
        latest = db.query(DefenseSeasonStats.season).filter(
            DefenseSeasonStats.team == "CHC"
        ).order_by(DefenseSeasonStats.season.desc()).first()
        if latest:
            q = q.filter(DefenseSeasonStats.season == latest[0])

    stats = q.all()
    result = []
    for s in stats:
        player = db.query(Player).filter(Player.mlb_id == s.player_id).first()
        d = {c.name: getattr(s, c.name) for c in s.__table__.columns if c.name != "id"}
        d["name"] = player.name if player else f"Player {s.player_id}"
        result.append(d)
    return result
