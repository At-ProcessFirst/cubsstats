from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


# ---------------------------------------------------------------------------
# Benchmark schemas
# ---------------------------------------------------------------------------

class BenchmarkResponse(BaseModel):
    stat_name: str
    position_group: str
    mean: Optional[float] = None
    median: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    sample_size: Optional[int] = None
    season: int

    class Config:
        from_attributes = True


class PercentileRequest(BaseModel):
    stat: str
    value: float
    position: str = "ALL_HITTERS"


class PercentileResponse(BaseModel):
    stat: str
    value: float
    percentile: int
    grade: str
    mlb_avg: float
    delta: float
    lower_is_better: bool = False


class PlayerBenchmarkResponse(BaseModel):
    player_id: int
    stat_name: str
    value: Optional[float] = None
    percentile: Optional[int] = None
    grade: Optional[str] = None
    mlb_avg: Optional[float] = None
    delta: Optional[float] = None

    class Config:
        from_attributes = True


class PitchTypeBenchmarkResponse(BaseModel):
    pitch_type: str
    stat_name: str
    mean: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    sample_size: Optional[int] = None
    season: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Player schemas
# ---------------------------------------------------------------------------

class PlayerResponse(BaseModel):
    mlb_id: int
    name: str
    team: Optional[str] = None
    position: Optional[str] = None
    position_group: Optional[str] = None
    is_cubs: bool = False

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Game schemas
# ---------------------------------------------------------------------------

class GameResponse(BaseModel):
    game_pk: int
    game_date: date
    season: int
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    cubs_opponent: Optional[str] = None
    cubs_home: Optional[bool] = None
    cubs_won: Optional[bool] = None
    status: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Pitching schemas
# ---------------------------------------------------------------------------

class PitcherSeasonStatsResponse(BaseModel):
    player_id: int
    season: int
    team: Optional[str] = None
    position_group: Optional[str] = None
    games: int = 0
    ip: float = 0
    era: Optional[float] = None
    fip: Optional[float] = None
    xfip: Optional[float] = None
    xera: Optional[float] = None
    k_pct: Optional[float] = None
    bb_pct: Optional[float] = None
    k_bb_pct: Optional[float] = None
    swstr_pct: Optional[float] = None
    csw_pct: Optional[float] = None
    hard_hit_pct: Optional[float] = None
    barrel_pct: Optional[float] = None
    avg_velo: Optional[float] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Hitting schemas
# ---------------------------------------------------------------------------

class HitterSeasonStatsResponse(BaseModel):
    player_id: int
    season: int
    team: Optional[str] = None
    games: int = 0
    pa: int = 0
    wrc_plus: Optional[float] = None
    woba: Optional[float] = None
    xba: Optional[float] = None
    xslg: Optional[float] = None
    xwoba: Optional[float] = None
    barrel_pct: Optional[float] = None
    hard_hit_pct: Optional[float] = None
    avg_exit_velo: Optional[float] = None
    o_swing_pct: Optional[float] = None
    z_contact_pct: Optional[float] = None
    chase_rate: Optional[float] = None
    sprint_speed: Optional[float] = None
    babip: Optional[float] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Team schemas
# ---------------------------------------------------------------------------

class TeamStatsResponse(BaseModel):
    team: str
    season: int
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    runs_scored: int = 0
    runs_allowed: int = 0
    team_era: Optional[float] = None
    team_fip: Optional[float] = None
    team_wrc_plus: Optional[float] = None
    team_woba: Optional[float] = None
    team_k_pct: Optional[float] = None
    team_bb_pct: Optional[float] = None
    pythag_wins: Optional[float] = None
    pythag_losses: Optional[float] = None
    run_diff: Optional[int] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Divergence schemas
# ---------------------------------------------------------------------------

class DivergenceAlertResponse(BaseModel):
    id: int
    player_id: int
    alert_type: str
    stat1_name: str
    stat1_value: float
    stat1_percentile: Optional[int] = None
    stat2_name: str
    stat2_value: float
    stat2_percentile: Optional[int] = None
    gap: float
    explanation: Optional[str] = None
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Pipeline schemas
# ---------------------------------------------------------------------------

class PipelineRunResponse(BaseModel):
    id: int
    pipeline_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
