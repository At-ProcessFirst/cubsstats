from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, Benchmark, PitchTypeBenchmark, PlayerBenchmark
from app.models.schemas import (
    BenchmarkResponse, PercentileResponse,
    PlayerBenchmarkResponse, PitchTypeBenchmarkResponse,
)
from app.services.benchmark_engine import compute_percentile, assign_grade, LOWER_IS_BETTER_STATS

router = APIRouter()


@router.get("/current", response_model=list[BenchmarkResponse])
def get_current_benchmarks(
    stat_name: Optional[str] = None,
    position_group: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """All current MLB averages by stat + position group."""
    q = db.query(Benchmark)
    # Get the latest season available
    latest_season = db.query(Benchmark.season).order_by(Benchmark.season.desc()).first()
    if not latest_season:
        return []
    q = q.filter(Benchmark.season == latest_season[0])
    if stat_name:
        q = q.filter(Benchmark.stat_name == stat_name)
    if position_group:
        q = q.filter(Benchmark.position_group == position_group)
    return q.all()


@router.get("/percentile", response_model=PercentileResponse)
def get_percentile(
    stat: str = Query(..., description="Stat name, e.g. K_pct"),
    value: float = Query(..., description="Player's stat value"),
    position: str = Query("ALL_HITTERS", description="Position group: SP, RP, ALL_HITTERS, etc."),
    db: Session = Depends(get_db),
):
    """Compute percentile rank for a given stat value against MLB benchmarks."""
    latest_season = db.query(Benchmark.season).order_by(Benchmark.season.desc()).first()
    if not latest_season:
        return PercentileResponse(
            stat=stat, value=value, percentile=50, grade="AVG",
            mlb_avg=0, delta=0, lower_is_better=stat in LOWER_IS_BETTER_STATS,
        )

    bench = db.query(Benchmark).filter(
        Benchmark.season == latest_season[0],
        Benchmark.stat_name == stat,
        Benchmark.position_group == position,
    ).first()

    if not bench:
        return PercentileResponse(
            stat=stat, value=value, percentile=50, grade="AVG",
            mlb_avg=0, delta=0, lower_is_better=stat in LOWER_IS_BETTER_STATS,
        )

    lower_is_better = stat in LOWER_IS_BETTER_STATS
    pctile = compute_percentile(value, bench, lower_is_better)
    grade = assign_grade(pctile)
    delta = value - bench.mean if bench.mean else 0

    return PercentileResponse(
        stat=stat,
        value=value,
        percentile=pctile,
        grade=grade,
        mlb_avg=bench.mean or 0,
        delta=round(delta, 4),
        lower_is_better=lower_is_better,
    )


@router.get("/player/{player_id}", response_model=list[PlayerBenchmarkResponse])
def get_player_benchmarks(
    player_id: int,
    db: Session = Depends(get_db),
):
    """All benchmarked stats for a specific player."""
    return db.query(PlayerBenchmark).filter(
        PlayerBenchmark.player_id == player_id
    ).all()


@router.get("/pitch-type/{pitch_type}", response_model=list[PitchTypeBenchmarkResponse])
def get_pitch_type_benchmarks(
    pitch_type: str,
    db: Session = Depends(get_db),
):
    """MLB averages for a specific pitch type."""
    latest_season = db.query(PitchTypeBenchmark.season).order_by(
        PitchTypeBenchmark.season.desc()
    ).first()
    if not latest_season:
        return []
    return db.query(PitchTypeBenchmark).filter(
        PitchTypeBenchmark.season == latest_season[0],
        PitchTypeBenchmark.pitch_type == pitch_type.upper(),
    ).all()
