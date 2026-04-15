from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid

from app.models.database import get_db
from app.services.booth_engine import ask, check_rate_limit

router = APIRouter()


class BoothQuestion(BaseModel):
    question: str
    conversation_id: Optional[str] = None


# In-memory conversation store (resets on deploy — acceptable for chat)
_conversations: dict = {}


@router.post("/ask")
def booth_ask(
    body: BoothQuestion,
    request: Request,
    db: Session = Depends(get_db),
):
    """Ask The Booth a natural language question about Cubs baseball."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(429, "Rate limit exceeded. Max 20 questions per hour.")

    # Manage conversation history
    conv_id = body.conversation_id or str(uuid.uuid4())
    history = _conversations.get(conv_id, [])

    # Limit conversation length
    if len(history) > 20:
        history = history[-10:]

    result = ask(body.question, db, conversation_history=history)

    # Store conversation turn
    history.append({"role": "user", "content": body.question})
    if result.get("answer"):
        history.append({"role": "assistant", "content": result["answer"]})
    _conversations[conv_id] = history

    # Cap total conversations in memory
    if len(_conversations) > 100:
        oldest = list(_conversations.keys())[:50]
        for k in oldest:
            del _conversations[k]

    return {
        "answer": result.get("answer"),
        "data": result.get("data"),
        "sources": result.get("sources", []),
        "error": result.get("error"),
        "conversation_id": conv_id,
    }


@router.get("/suggestions")
def booth_suggestions():
    """Return starter question suggestions."""
    return {
        "suggestions": [
            "What's the Cubs current record and run differential?",
            "Who has the best ERA on the pitching staff?",
            "Which Cubs hitter has the highest batting average?",
            "How does the Cubs FIP compare to their ERA?",
            "Which pitcher has the most strikeouts this season?",
            "Show me the Cubs strongest opponents this season",
        ]
    }


@router.get("/schema")
def booth_schema():
    """Return available tables and date ranges for reference."""
    return {
        "available_data": {
            "seasons": [2024, 2025, 2026],
            "current_season": 2026,
            "tables": {
                "games": "Game results with scores, opponents, home/away",
                "pitcher_season_stats": "Per-pitcher season stats (ERA, FIP, K%, BB%, IP)",
                "hitter_season_stats": "Per-hitter season stats (AVG, OBP, SLG, wOBA, wRC+)",
                "pitcher_game_stats": "Per-pitcher per-game stats (IP, K, BB, ER)",
                "hitter_game_stats": "Per-hitter per-game stats (AB, H, HR, RBI)",
                "players": "Player names, positions, team",
                "team_season_stats": "Cubs team aggregates (record, ERA, FIP, wRC+)",
                "team_strength": "All 30 MLB teams Pythagorean ratings",
                "benchmarks": "League-wide stat distributions for grading",
                "divergence_alerts": "Active stat divergence flags (BREAKOUT/REGRESS/WATCH)",
            },
        }
    }
