"""Worker settings, read from environment variables and an optional .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://faultiq:change-me@localhost:5432/faultiq"
    upload_dir: str = "./data/uploads"
    poll_interval_seconds: float = Field(default=5.0, gt=0)
    heartbeat_interval_seconds: float = Field(default=60.0, gt=0)
    model_dir: str = "./models"
    job_timeout_minutes: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
