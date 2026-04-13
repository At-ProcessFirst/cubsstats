"""
Divergence detection engine — identifies performance divergences between
surface stats and underlying metrics, with benchmark context.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.database import (
    DivergenceAlert, PitcherSeasonStats, HitterSeasonStats,
    PlayerBenchmark, Player,
)

logger = logging.getLogger(__name__)

DIVERGENCE_THRESHOLDS = {
    "era_fip_gap": 0.75,
    "ba_xba_gap": 0.030,
    "woba_xwoba_gap": 0.025,
    "babip_xbabip_gap": 0.040,
    "velo_drop_mph": 1.5,
    "barrel_babip_diverge": True,
}


def detect_pitcher_divergences(season: int, db: Session) -> int:
    """Detect divergences for Cubs pitchers."""
    count = 0
    pitchers = db.query(PitcherSeasonStats).filter(
        PitcherSeasonStats.season == season,
        PitcherSeasonStats.team == "CHC",
        PitcherSeasonStats.ip >= 5,  # Low threshold for early season
    ).all()

    for p in pitchers:
        # ERA vs FIP gap
        if p.era is not None and p.fip is not None:
            gap = p.era - p.fip
            if abs(gap) >= DIVERGENCE_THRESHOLDS["era_fip_gap"]:
                alert_type = "REGRESS" if gap < 0 else "BREAKOUT"
                explanation = (
                    f"ERA ({p.era:.2f}) is {'lower' if gap < 0 else 'higher'} than FIP ({p.fip:.2f}) "
                    f"by {abs(gap):.2f}. "
                )
                if gap < 0:
                    explanation += "ERA likely to rise — pitching has been lucky or defense-aided."
                else:
                    explanation += "ERA likely to drop — pitching is better than results show."

                _upsert_divergence(
                    db, p.player_id, alert_type,
                    "ERA", p.era, "FIP", p.fip, gap, explanation,
                )
                count += 1

    db.commit()
    return count


def detect_hitter_divergences(season: int, db: Session) -> int:
    """Detect divergences for Cubs hitters."""
    count = 0
    hitters = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season,
        HitterSeasonStats.team == "CHC",
        HitterSeasonStats.pa >= 15,  # Low threshold for early season
    ).all()

    for h in hitters:
        # AVG vs xBA
        if h.avg is not None and h.xba is not None:
            gap = h.avg - h.xba
            if abs(gap) >= DIVERGENCE_THRESHOLDS["ba_xba_gap"]:
                alert_type = "REGRESS" if gap > 0 else "BREAKOUT"
                explanation = (
                    f"AVG ({h.avg:.3f}) vs xBA ({h.xba:.3f}): "
                    f"gap of {abs(gap):.3f}. "
                )
                if gap > 0:
                    explanation += "Batting average likely to drop — getting lucky on batted balls."
                else:
                    explanation += "Batting average likely to rise — hitting better than results show."

                _upsert_divergence(
                    db, h.player_id, alert_type,
                    "AVG", h.avg, "xBA", h.xba, gap, explanation,
                )
                count += 1

        # wOBA vs xwOBA
        if h.woba is not None and h.xwoba is not None:
            gap = h.woba - h.xwoba
            if abs(gap) >= DIVERGENCE_THRESHOLDS["woba_xwoba_gap"]:
                alert_type = "REGRESS" if gap > 0 else "BREAKOUT"
                explanation = (
                    f"wOBA ({h.woba:.3f}) vs xwOBA ({h.xwoba:.3f}): "
                    f"gap of {abs(gap):.3f}. "
                )
                if gap > 0:
                    explanation += "Offensive production likely to decline — surface stats outpacing underlying quality."
                else:
                    explanation += "Offensive production likely to improve — underlying quality better than results."

                _upsert_divergence(
                    db, h.player_id, alert_type,
                    "wOBA", h.woba, "xwOBA", h.xwoba, gap, explanation,
                )
                count += 1

        # BABIP check for outliers
        if h.babip is not None:
            if h.babip > 0.370:
                _upsert_divergence(
                    db, h.player_id, "WATCH",
                    "BABIP", h.babip, "League Avg BABIP", 0.300, h.babip - 0.300,
                    f"BABIP ({h.babip:.3f}) is unusually high. Average is ~.300. "
                    "Batting average will likely regress as luck normalizes.",
                )
                count += 1
            elif h.babip < 0.230:
                _upsert_divergence(
                    db, h.player_id, "WATCH",
                    "BABIP", h.babip, "League Avg BABIP", 0.300, h.babip - 0.300,
                    f"BABIP ({h.babip:.3f}) is unusually low. Average is ~.300. "
                    "Batting average will likely improve as bad luck fades.",
                )
                count += 1

    db.commit()
    return count


def _upsert_divergence(db: Session, player_id: int, alert_type: str,
                        stat1_name: str, stat1_value: float,
                        stat2_name: str, stat2_value: float,
                        gap: float, explanation: str):
    """Create or update a divergence alert."""
    # Check for existing active alert of same type
    existing = db.query(DivergenceAlert).filter(
        DivergenceAlert.player_id == player_id,
        DivergenceAlert.stat1_name == stat1_name,
        DivergenceAlert.stat2_name == stat2_name,
        DivergenceAlert.is_active == True,
    ).first()

    # Look up percentiles if available
    pb1 = db.query(PlayerBenchmark).filter(
        PlayerBenchmark.player_id == player_id,
        PlayerBenchmark.stat_name == stat1_name.lower().replace(" ", "_"),
    ).first()
    pb2 = db.query(PlayerBenchmark).filter(
        PlayerBenchmark.player_id == player_id,
        PlayerBenchmark.stat_name == stat2_name.lower().replace(" ", "_"),
    ).first()

    if existing:
        existing.alert_type = alert_type
        existing.stat1_value = stat1_value
        existing.stat2_value = stat2_value
        existing.stat1_percentile = pb1.percentile if pb1 else None
        existing.stat2_percentile = pb2.percentile if pb2 else None
        existing.gap = gap
        existing.explanation = explanation
    else:
        db.add(DivergenceAlert(
            player_id=player_id,
            alert_type=alert_type,
            stat1_name=stat1_name,
            stat1_value=stat1_value,
            stat1_percentile=pb1.percentile if pb1 else None,
            stat2_name=stat2_name,
            stat2_value=stat2_value,
            stat2_percentile=pb2.percentile if pb2 else None,
            gap=gap,
            explanation=explanation,
        ))
