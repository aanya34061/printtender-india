from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    resend_api_key: str = Field(alias="RESEND_API_KEY")
    app_env: str = Field(default="development", alias="APP_ENV")
    fetch_interval_hours: int = Field(default=6, alias="FETCH_INTERVAL_HOURS")
    max_tenders_per_keyword: int = Field(default=100, alias="MAX_TENDERS_PER_KEYWORD")
    request_delay_seconds: float = Field(default=3, alias="REQUEST_DELAY_SECONDS")
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
