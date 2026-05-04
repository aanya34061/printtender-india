from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.config import get_settings
from app.models import Base


def _asyncpg_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


settings = get_settings()
engine = create_async_engine(
    _asyncpg_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    connect_args={"prepared_statement_cache_size": 0},
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
    ]
    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))


async_session = AsyncSessionLocal
get_session = get_db
