"""
Benchmark engine — computes MLB league averages, percentile breakpoints,
player percentile ranks, grade assignments, and pitch-type benchmarks.

Handles the dynamic blending logic:
  - Before ~30 team games: 100% prior season benchmarks
  - 30-80 team games: blend 70% current / 30% prior
  - After ~80 team games: 100% current season
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import get_settings
from app.models.database import (
    Benchmark, PitchTypeBenchmark, PlayerBenchmark,
    PitcherSeasonStats, HitterSeasonStats, StatcastPitch,
    TeamSeasonStats, Player,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Stats where lower values are better
LOWER_IS_BETTER_STATS = {
    "era", "fip", "xfip", "xera",
    "bb_pct", "hard_hit_pct", "barrel_pct",
    "o_swing_pct", "chase_rate",
    "hard_hit_pct_against", "barrel_pct_against",
}

# Pitching stats to benchmark
PITCHING_STATS = [
    "era", "fip", "xfip", "xera", "k_pct", "bb_pct", "k_bb_pct",
    "swstr_pct", "csw_pct", "hard_hit_pct", "barrel_pct", "avg_velo", "whiff_pct",
]

# Hitting stats to benchmark
HITTING_STATS = [
    "wrc_plus", "woba", "xba", "xslg", "xwoba", "barrel_pct", "hard_hit_pct",
    "avg_exit_velo", "o_swing_pct", "z_contact_pct", "chase_rate",
    "sprint_speed", "bsr", "babip", "avg", "obp", "slg",
]

# Pitch-type stats
PITCH_TYPE_STATS = ["avg_velo", "whiff_pct", "vert_movement", "horiz_break"]

# Pitch types to track
PITCH_TYPES = ["FF", "SL", "CU", "FC", "CH", "FS", "SI"]


def assign_grade(percentile: int) -> str:
    """Assign a grade based on percentile ranking.

    For stats where lower is better, the percentile should already be
    inverted before calling this function.
    """
    if percentile >= 90:
        return "ELITE"
    elif percentile >= 75:
        return "ABOVE AVG"
    elif percentile >= 25:
        return "AVG"
    elif percentile >= 10:
        return "BELOW AVG"
    else:
        return "POOR"


def compute_percentile(value: float, benchmark: Benchmark, lower_is_better: bool = False) -> int:
    """Compute a player's percentile rank for a stat given the benchmark breakpoints.

    Uses linear interpolation between the stored percentile breakpoints
    (p10, p25, median, p75, p90).
    """
    if benchmark is None or value is None:
        return 50

    # Build the breakpoint ladder
    breakpoints = [
        (benchmark.p10, 10),
        (benchmark.p25, 25),
        (benchmark.median, 50),
        (benchmark.p75, 75),
        (benchmark.p90, 90),
    ]
    # Filter out None breakpoints
    breakpoints = [(v, p) for v, p in breakpoints if v is not None]
    if not breakpoints:
        return 50

    if lower_is_better:
        # For lower-is-better stats, invert: a value below p10 is elite (90th+ percentile)
        # Flip the value relative to the distribution
        breakpoints = [(v, 100 - p) for v, p in breakpoints]
        breakpoints.sort(key=lambda x: x[0])

    # Sort by value for interpolation
    breakpoints.sort(key=lambda x: x[0])

    # Below lowest breakpoint
    if value <= breakpoints[0][0]:
        return max(1, breakpoints[0][1])

    # Above highest breakpoint
    if value >= breakpoints[-1][0]:
        return min(99, breakpoints[-1][1])

    # Interpolate between breakpoints
    for i in range(len(breakpoints) - 1):
        v_low, p_low = breakpoints[i]
        v_high, p_high = breakpoints[i + 1]
        if v_low <= value <= v_high:
            if v_high == v_low:
                return int((p_low + p_high) / 2)
            frac = (value - v_low) / (v_high - v_low)
            pctile = p_low + frac * (p_high - p_low)
            return max(1, min(99, int(round(pctile))))

    return 50


# ---------------------------------------------------------------------------
# Compute league-wide benchmarks from season stats
# ---------------------------------------------------------------------------

def compute_pitching_benchmarks(season: int, db: Session) -> int:
    """Compute MLB pitching benchmarks (mean, median, percentile breakpoints) for a season."""
    count = 0

    for pos_group in ["SP", "RP"]:
        # Minimum IP filter: SP >= 40 IP, RP >= 20 IP
        min_ip = 40 if pos_group == "SP" else 20

        pitchers = db.query(PitcherSeasonStats).filter(
            PitcherSeasonStats.season == season,
            PitcherSeasonStats.position_group == pos_group,
            PitcherSeasonStats.ip >= min_ip,
        ).all()

        if len(pitchers) < 10:
            logger.warning(f"Only {len(pitchers)} {pos_group}s with >= {min_ip} IP in {season}, skipping")
            continue

        for stat_name in PITCHING_STATS:
            values = [getattr(p, stat_name) for p in pitchers if getattr(p, stat_name) is not None]
            if len(values) < 10:
                continue

            arr = np.array(values, dtype=float)

            bench = db.query(Benchmark).filter(
                Benchmark.season == season,
                Benchmark.stat_name == stat_name,
                Benchmark.position_group == pos_group,
            ).first()

            if not bench:
                bench = Benchmark(season=season, stat_name=stat_name, position_group=pos_group)
                db.add(bench)

            bench.mean = round(float(np.mean(arr)), 4)
            bench.median = round(float(np.median(arr)), 4)
            bench.p10 = round(float(np.percentile(arr, 10)), 4)
            bench.p25 = round(float(np.percentile(arr, 25)), 4)
            bench.p75 = round(float(np.percentile(arr, 75)), 4)
            bench.p90 = round(float(np.percentile(arr, 90)), 4)
            bench.sample_size = len(values)
            count += 1

    db.commit()
    logger.info(f"Computed {count} pitching benchmarks for {season}")
    return count


def compute_hitting_benchmarks(season: int, db: Session) -> int:
    """Compute MLB hitting benchmarks for a season."""
    count = 0
    min_pa = 100

    # ALL_HITTERS group
    hitters = db.query(HitterSeasonStats).filter(
        HitterSeasonStats.season == season,
        HitterSeasonStats.pa >= min_pa,
    ).all()

    if len(hitters) < 10:
        logger.warning(f"Only {len(hitters)} hitters with >= {min_pa} PA in {season}")
        return 0

    for stat_name in HITTING_STATS:
        values = [getattr(h, stat_name) for h in hitters if getattr(h, stat_name) is not None]
        if len(values) < 10:
            continue

        arr = np.array(values, dtype=float)

        bench = db.query(Benchmark).filter(
            Benchmark.season == season,
            Benchmark.stat_name == stat_name,
            Benchmark.position_group == "ALL_HITTERS",
        ).first()

        if not bench:
            bench = Benchmark(season=season, stat_name=stat_name, position_group="ALL_HITTERS")
            db.add(bench)

        bench.mean = round(float(np.mean(arr)), 4)
        bench.median = round(float(np.median(arr)), 4)
        bench.p10 = round(float(np.percentile(arr, 10)), 4)
        bench.p25 = round(float(np.percentile(arr, 25)), 4)
        bench.p75 = round(float(np.percentile(arr, 75)), 4)
        bench.p90 = round(float(np.percentile(arr, 90)), 4)
        bench.sample_size = len(values)
        count += 1

    # Position-specific groups
    for pos_group in ["C", "IF", "OF"]:
        pos_hitters = [h for h in hitters if h.position_group == pos_group]
        if len(pos_hitters) < 5:
            continue
        for stat_name in HITTING_STATS:
            values = [getattr(h, stat_name) for h in pos_hitters if getattr(h, stat_name) is not None]
            if len(values) < 5:
                continue

            arr = np.array(values, dtype=float)

            bench = db.query(Benchmark).filter(
                Benchmark.season == season,
                Benchmark.stat_name == stat_name,
                Benchmark.position_group == pos_group,
            ).first()

            if not bench:
                bench = Benchmark(season=season, stat_name=stat_name, position_group=pos_group)
                db.add(bench)

            bench.mean = round(float(np.mean(arr)), 4)
            bench.median = round(float(np.median(arr)), 4)
            bench.p10 = round(float(np.percentile(arr, 10)), 4)
            bench.p25 = round(float(np.percentile(arr, 25)), 4)
            bench.p75 = round(float(np.percentile(arr, 75)), 4)
            bench.p90 = round(float(np.percentile(arr, 90)), 4)
            bench.sample_size = len(values)
            count += 1

    db.commit()
    logger.info(f"Computed {count} hitting benchmarks for {season}")
    return count


def compute_pitch_type_benchmarks(season: int, db: Session) -> int:
    """Compute pitch-type benchmarks from Statcast pitch-level data."""
    count = 0

    for pitch_type in PITCH_TYPES:
        pitches = db.query(StatcastPitch).filter(
            StatcastPitch.season == season,
            StatcastPitch.pitch_type == pitch_type,
        ).all()

        if len(pitches) < 100:
            continue

        # avg_velo
        velos = [p.release_speed for p in pitches if p.release_speed is not None]
        if len(velos) >= 50:
            arr = np.array(velos, dtype=float)
            _upsert_pitch_type_bench(db, season, pitch_type, "avg_velo", arr)
            count += 1

        # whiff_pct — compute per-pitcher, then aggregate
        pitcher_ids = set(p.pitcher_id for p in pitches)
        pitcher_whiff_pcts = []
        for pid in pitcher_ids:
            pp = [p for p in pitches if p.pitcher_id == pid]
            if len(pp) < 30:
                continue
            swings = [p for p in pp if p.description and "swing" in p.description.lower()]
            if len(swings) < 10:
                continue
            whiffs = sum(1 for p in pp if p.is_whiff)
            pitcher_whiff_pcts.append(whiffs / len(swings) * 100)
        if len(pitcher_whiff_pcts) >= 20:
            arr = np.array(pitcher_whiff_pcts, dtype=float)
            _upsert_pitch_type_bench(db, season, pitch_type, "whiff_pct", arr)
            count += 1

        # vert_movement (pfx_z)
        vert = [p.pfx_z for p in pitches if p.pfx_z is not None]
        if len(vert) >= 50:
            arr = np.array(vert, dtype=float)
            _upsert_pitch_type_bench(db, season, pitch_type, "vert_movement", arr)
            count += 1

        # horiz_break (pfx_x)
        horiz = [p.pfx_x for p in pitches if p.pfx_x is not None]
        if len(horiz) >= 50:
            arr = np.array(horiz, dtype=float)
            _upsert_pitch_type_bench(db, season, pitch_type, "horiz_break", arr)
            count += 1

    db.commit()
    logger.info(f"Computed {count} pitch-type benchmarks for {season}")
    return count


def _upsert_pitch_type_bench(db: Session, season: int, pitch_type: str,
                              stat_name: str, arr: np.ndarray):
    """Upsert a single pitch-type benchmark row."""
    bench = db.query(PitchTypeBenchmark).filter(
        PitchTypeBenchmark.season == season,
        PitchTypeBenchmark.pitch_type == pitch_type,
        PitchTypeBenchmark.stat_name == stat_name,
    ).first()

    if not bench:
        bench = PitchTypeBenchmark(season=season, pitch_type=pitch_type, stat_name=stat_name)
        db.add(bench)

    bench.mean = round(float(np.mean(arr)), 4)
    bench.p25 = round(float(np.percentile(arr, 25)), 4)
    bench.p75 = round(float(np.percentile(arr, 75)), 4)
    bench.p90 = round(float(np.percentile(arr, 90)), 4)
    bench.sample_size = len(arr)


# ---------------------------------------------------------------------------
# Player percentile refresh
# ---------------------------------------------------------------------------

def refresh_player_benchmarks(season: int, db: Session, cubs_only: bool = True) -> int:
    """Compute each player's percentile rank against all qualified MLB players.

    Updates the player_benchmarks table.
    """
    count = 0

    # --- Pitchers ---
    if cubs_only:
        pitchers = db.query(PitcherSeasonStats).filter(
            PitcherSeasonStats.season == season,
            PitcherSeasonStats.team == "CHC",
        ).all()
    else:
        pitchers = db.query(PitcherSeasonStats).filter(
            PitcherSeasonStats.season == season,
        ).all()

    for pitcher in pitchers:
        pos_group = pitcher.position_group or "SP"
        for stat_name in PITCHING_STATS:
            value = getattr(pitcher, stat_name, None)
            if value is None:
                continue

            bench = db.query(Benchmark).filter(
                Benchmark.season == season,
                Benchmark.stat_name == stat_name,
                Benchmark.position_group == pos_group,
            ).first()

            if not bench:
                continue

            lower_is_better = stat_name in LOWER_IS_BETTER_STATS
            pctile = compute_percentile(value, bench, lower_is_better)
            grade = assign_grade(pctile)
            delta = round(value - (bench.mean or 0), 4)

            _upsert_player_benchmark(
                db, pitcher.player_id, stat_name, value, pctile, grade,
                bench.mean, delta,
            )
            count += 1

    # --- Hitters ---
    if cubs_only:
        hitters = db.query(HitterSeasonStats).filter(
            HitterSeasonStats.season == season,
            HitterSeasonStats.team == "CHC",
        ).all()
    else:
        hitters = db.query(HitterSeasonStats).filter(
            HitterSeasonStats.season == season,
        ).all()

    for hitter in hitters:
        pos_group = hitter.position_group or "ALL_HITTERS"
        for stat_name in HITTING_STATS:
            value = getattr(hitter, stat_name, None)
            if value is None:
                continue

            # Try position-specific benchmark first, fall back to ALL_HITTERS
            bench = db.query(Benchmark).filter(
                Benchmark.season == season,
                Benchmark.stat_name == stat_name,
                Benchmark.position_group == pos_group,
            ).first()

            if not bench:
                bench = db.query(Benchmark).filter(
                    Benchmark.season == season,
                    Benchmark.stat_name == stat_name,
                    Benchmark.position_group == "ALL_HITTERS",
                ).first()

            if not bench:
                continue

            lower_is_better = stat_name in LOWER_IS_BETTER_STATS
            pctile = compute_percentile(value, bench, lower_is_better)
            grade = assign_grade(pctile)
            delta = round(value - (bench.mean or 0), 4)

            _upsert_player_benchmark(
                db, hitter.player_id, stat_name, value, pctile, grade,
                bench.mean, delta,
            )
            count += 1

    db.commit()
    logger.info(f"Refreshed {count} player benchmarks for {season}")
    return count


def _upsert_player_benchmark(db: Session, player_id: int, stat_name: str,
                              value: float, percentile: int, grade: str,
                              mlb_avg: float, delta: float):
    """Upsert a single player benchmark row."""
    existing = db.query(PlayerBenchmark).filter(
        PlayerBenchmark.player_id == player_id,
        PlayerBenchmark.stat_name == stat_name,
    ).first()

    if existing:
        existing.value = value
        existing.percentile = percentile
        existing.grade = grade
        existing.mlb_avg = mlb_avg
        existing.delta = delta
    else:
        db.add(PlayerBenchmark(
            player_id=player_id,
            stat_name=stat_name,
            value=value,
            percentile=percentile,
            grade=grade,
            mlb_avg=mlb_avg,
            delta=delta,
        ))


# ---------------------------------------------------------------------------
# Benchmark blending (prior season + current season)
# ---------------------------------------------------------------------------

def get_blended_benchmark(stat_name: str, position_group: str,
                           current_season: int, db: Session) -> Optional[Benchmark]:
    """Return a blended benchmark based on how far into the season we are.

    Blending logic:
      - < 30 team games: 100% prior season
      - 30-80 team games: 70% current / 30% prior
      - > 80 team games: 100% current season
    """
    # How many games has the Cubs team played this season?
    cubs_stats = db.query(TeamSeasonStats).filter(
        TeamSeasonStats.team == "CHC",
        TeamSeasonStats.season == current_season,
    ).first()

    games_played = cubs_stats.games_played if cubs_stats else 0
    prior_season = current_season - 1

    current_bench = db.query(Benchmark).filter(
        Benchmark.season == current_season,
        Benchmark.stat_name == stat_name,
        Benchmark.position_group == position_group,
    ).first()

    prior_bench = db.query(Benchmark).filter(
        Benchmark.season == prior_season,
        Benchmark.stat_name == stat_name,
        Benchmark.position_group == position_group,
    ).first()

    if games_played < settings.blend_start_games:
        # 100% prior
        return prior_bench or current_bench
    elif games_played > settings.blend_end_games:
        # 100% current
        return current_bench or prior_bench
    else:
        # Blend 70% current / 30% prior
        if not current_bench or not prior_bench:
            return current_bench or prior_bench

        blended = Benchmark(
            season=current_season,
            stat_name=stat_name,
            position_group=position_group,
        )
        w_current = 0.7
        w_prior = 0.3

        for field in ["mean", "median", "p10", "p25", "p75", "p90"]:
            cv = getattr(current_bench, field)
            pv = getattr(prior_bench, field)
            if cv is not None and pv is not None:
                setattr(blended, field, round(cv * w_current + pv * w_prior, 4))
            else:
                setattr(blended, field, cv or pv)

        blended.sample_size = (current_bench.sample_size or 0) + (prior_bench.sample_size or 0)
        return blended
