from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
import json

from app.models.database import get_db, Editorial
from app.services.editorial_engine import (
    generate_daily_takeaway,
    generate_weekly_state,
    generate_player_spotlight,
    generate_prediction_recap,
)

router = APIRouter()


@router.get("")
def list_editorials(
    editorial_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List editorials, newest first. Optionally filter by type."""
    q = db.query(Editorial)
    if editorial_type:
        q = q.filter(Editorial.editorial_type == editorial_type)
    total = q.count()
    editorials = q.order_by(Editorial.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "editorials": [_serialize(e) for e in editorials],
    }


@router.get("/latest")
def get_latest_editorial(
    editorial_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get the most recent editorial, optionally by type."""
    q = db.query(Editorial)
    if editorial_type:
        q = q.filter(Editorial.editorial_type == editorial_type)
    editorial = q.order_by(Editorial.created_at.desc()).first()
    if not editorial:
        return None
    return _serialize(editorial)


@router.get("/{editorial_id}")
def get_editorial(
    editorial_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific editorial by ID."""
    editorial = db.query(Editorial).filter(Editorial.id == editorial_id).first()
    if not editorial:
        raise HTTPException(status_code=404, detail="Editorial not found")
    return _serialize(editorial)


@router.post("/generate")
def generate_editorial(
    editorial_type: str = Query(..., description="daily_takeaway, weekly_state, player_spotlight, prediction_recap"),
    game_pk: Optional[int] = None,
    player_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Generate a new editorial on demand.

    - daily_takeaway: requires game_pk
    - weekly_state: no params needed
    - player_spotlight: requires player_id
    - prediction_recap: no params needed
    """
    season = date.today().year

    if editorial_type == "daily_takeaway":
        if not game_pk:
            raise HTTPException(400, "game_pk required for daily_takeaway")
        editorial = generate_daily_takeaway(game_pk, db)

    elif editorial_type == "weekly_state":
        editorial = generate_weekly_state(season, db)

    elif editorial_type == "player_spotlight":
        if not player_id:
            raise HTTPException(400, "player_id required for player_spotlight")
        editorial = generate_player_spotlight(player_id, season, db)

    elif editorial_type == "prediction_recap":
        editorial = generate_prediction_recap(season, db)

    else:
        raise HTTPException(400, f"Unknown editorial type: {editorial_type}")

    if not editorial:
        raise HTTPException(500, "Failed to generate editorial")

    return _serialize(editorial)


def _serialize(e: Editorial) -> dict:
    """Serialize an editorial for JSON response."""
    return {
        "id": e.id,
        "editorial_type": e.editorial_type,
        "title": e.title,
        "body": e.body,
        "summary": e.summary,
        "player_ids": json.loads(e.player_ids) if e.player_ids else [],
        "game_pk": e.game_pk,
        "season": e.season,
        "created_at": e.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if e.created_at else None,
    }
