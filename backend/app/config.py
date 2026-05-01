from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str
    RESEND_API_KEY: str
    APP_ENV: str = "development"
    FETCH_INTERVAL_HOURS: int = 6
    MAX_TENDERS_PER_KEYWORD: int = 100
    REQUEST_DELAY_SECONDS: float = 3

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL

    @property
    def resend_api_key(self) -> str:
        return self.RESEND_API_KEY

    @property
    def app_env(self) -> str:
        return self.APP_ENV

    @property
    def fetch_interval_hours(self) -> int:
        return self.FETCH_INTERVAL_HOURS

    @property
    def max_tenders_per_keyword(self) -> int:
        return self.MAX_TENDERS_PER_KEYWORD

    @property
    def request_delay_seconds(self) -> float:
        return self.REQUEST_DELAY_SECONDS

    @property
    def cors_origins(self) -> list[str]:
        return ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
