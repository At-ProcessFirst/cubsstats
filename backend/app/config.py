from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cubsedge.db"
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    cubs_team_id: int = 112
    cubs_team_abbr: str = "CHC"
    mlb_stats_api_base: str = "https://statsapi.mlb.com/api/v1"

    # Benchmark blending thresholds (team games played)
    blend_start_games: int = 30
    blend_end_games: int = 80

    # Statcast delay hours (data available ~24hr after games)
    statcast_delay_hours: int = 24

    # Daily update schedule (CT)
    daily_update_hour: int = 6
    daily_update_minute: int = 0

    # Anthropic API for editorial generation
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
