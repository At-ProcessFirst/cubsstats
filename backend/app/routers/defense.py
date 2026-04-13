from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
import logging

from app.models.database import get_db, DefenseSeasonStats, Player
from app.services.ingestion import mlb_api_get, pull_cubs_roster, _safe_int, _safe_float

logger = logging.getLogger(__name__)
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


@router.get("/fielding")
def get_cubs_fielding(
    season: Optional[int] = None,
):
    """Pull live fielding stats from MLB Stats API for each Cubs roster player.
    Returns: name, position, games, innings, totalChances, putOuts, assists, errors,
    fielding%, doublePlays — sorted by games descending.
    """
    current_season = season or date.today().year
    result = []

    try:
        roster = pull_cubs_roster(current_season)
    except Exception as e:
        logger.error(f"Roster pull failed: {e}")
        return {"players": [], "error": str(e)}

    for rp in roster:
        mlb_id = rp["mlb_id"]
        name = rp["name"]
        pos = rp["position"]

        try:
            data = mlb_api_get(f"/people/{mlb_id}/stats", {
                "stats": "season", "season": current_season, "group": "fielding",
            })
            for sg in data.get("stats", []):
                for split in sg.get("splits", []):
                    stat = split.get("stat", {})
                    games = _safe_int(stat.get("gamesPlayed"))
                    if games == 0:
                        continue
                    result.append({
                        "player_id": mlb_id,
                        "name": name,
                        "position": split.get("position", {}).get("abbreviation", pos),
                        "games": games,
                        "innings": stat.get("innings", "0"),
                        "total_chances": _safe_int(stat.get("totalChances")),
                        "putouts": _safe_int(stat.get("putOuts")),
                        "assists": _safe_int(stat.get("assists")),
                        "errors": _safe_int(stat.get("errors")),
                        "fielding_pct": stat.get("fielding", ".000"),
                        "double_plays": _safe_int(stat.get("doublePlays")),
                    })
        except Exception as e:
            logger.warning(f"Fielding stats failed for {name}: {e}")

    result.sort(key=lambda x: x["games"], reverse=True)
    return {"players": result}
