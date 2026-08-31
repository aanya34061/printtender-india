from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"), env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str
    REDIS_URL: str = ""
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "PrintTender India <alerts@printtender.in>"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    CRON_SECRET: str = ""
    ENABLE_FETCH_API: bool = True
    APP_ENV: str = "development"
    FETCH_INTERVAL_HOURS: int = 6
    MAX_TENDERS_PER_KEYWORD: int = 100
    REQUEST_DELAY_SECONDS: float = 3
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    RUN_STARTUP_MIGRATIONS: bool | None = None
    PREWARM_ON_STARTUP: bool | None = None
    ENABLE_SCHEDULED_MAILS: bool | None = None

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
    def cron_secret(self) -> str:
        return self.CRON_SECRET

    @property
    def enable_fetch_api(self) -> bool:
        return self.ENABLE_FETCH_API

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
        return ["*"]

    @property
    def run_startup_migrations(self) -> bool:
        if self.RUN_STARTUP_MIGRATIONS is not None:
            return self.RUN_STARTUP_MIGRATIONS
        return self.APP_ENV != "production"

    @property
    def prewarm_on_startup(self) -> bool:
        if self.PREWARM_ON_STARTUP is not None:
            return self.PREWARM_ON_STARTUP
        return self.APP_ENV != "production"

    @property
    def enable_scheduled_mails(self) -> bool:
        if self.ENABLE_SCHEDULED_MAILS is not None:
            return self.ENABLE_SCHEDULED_MAILS
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
