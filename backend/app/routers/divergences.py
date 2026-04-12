from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, DivergenceAlert, Player
from app.models.schemas import DivergenceAlertResponse

router = APIRouter()


@router.get("/active", response_model=list[DivergenceAlertResponse])
def get_active_divergences(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get all active divergence alerts for Cubs players."""
    alerts = db.query(DivergenceAlert).filter(
        DivergenceAlert.is_active == True,
    ).order_by(DivergenceAlert.created_at.desc()).limit(limit).all()
    return alerts


@router.get("/player/{player_id}", response_model=list[DivergenceAlertResponse])
def get_player_divergences(
    player_id: int,
    db: Session = Depends(get_db),
):
    """Get divergence alerts for a specific player."""
    return db.query(DivergenceAlert).filter(
        DivergenceAlert.player_id == player_id,
        DivergenceAlert.is_active == True,
    ).all()


@router.get("/enriched")
def get_enriched_divergences(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get active divergences enriched with player names."""
    alerts = db.query(DivergenceAlert).filter(
        DivergenceAlert.is_active == True,
    ).order_by(DivergenceAlert.created_at.desc()).limit(limit).all()

    result = []
    for a in alerts:
        player = db.query(Player).filter(Player.mlb_id == a.player_id).first()
        result.append({
            "id": a.id,
            "player_id": a.player_id,
            "player_name": player.name if player else f"Player {a.player_id}",
            "alert_type": a.alert_type,
            "stat1_name": a.stat1_name,
            "stat1_value": a.stat1_value,
            "stat1_percentile": a.stat1_percentile,
            "stat2_name": a.stat2_name,
            "stat2_value": a.stat2_value,
            "stat2_percentile": a.stat2_percentile,
            "gap": a.gap,
            "explanation": a.explanation,
            "is_active": a.is_active,
            "created_at": a.created_at,
        })
    return result
