from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.config import get_settings
from app.models import Base


def _asyncpg_url(database_url: str) -> str:
    url = (
        database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if database_url.startswith("postgresql://")
        else database_url
    )
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if query.get("sslmode") == "require":
        query.pop("sslmode", None)
        query["ssl"] = "require"
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


settings = get_settings()
engine = create_async_engine(
    _asyncpg_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    connect_args={"prepared_statement_cache_size": 0, "timeout": 10},
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def run_startup_migrations() -> None:
    statements = [
        "ALTER TABLE IF EXISTS tenders ADD COLUMN IF NOT EXISTS tender_id TEXT",
        "ALTER TABLE IF EXISTS tenders ADD COLUMN IF NOT EXISTS link_type VARCHAR(10) DEFAULT 'search'",
        "ALTER TABLE IF EXISTS tenders ADD COLUMN IF NOT EXISTS link_verified BOOLEAN DEFAULT FALSE",
        "CREATE INDEX IF NOT EXISTS idx_tenders_tender_id ON tenders(tender_id)",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS keyword TEXT DEFAULT 'printing'",
        "UPDATE alert_subscriptions SET keyword = COALESCE(keyword, keywords[1], 'printing') WHERE keyword IS NULL",
        "ALTER TABLE IF EXISTS alert_subscriptions ALTER COLUMN keyword SET NOT NULL",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS confirmed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS token TEXT",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS last_alerted_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS is_confirmed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS confirm_token TEXT",
        "ALTER TABLE IF EXISTS alert_subscriptions ADD COLUMN IF NOT EXISTS last_sent TIMESTAMPTZ",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_email_keyword ON alert_subscriptions(email, keyword)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_subscriptions_token ON alert_subscriptions(token) WHERE token IS NOT NULL",
    ]
    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))


async_session = AsyncSessionLocal
get_session = get_db
