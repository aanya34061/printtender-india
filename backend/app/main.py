from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextlib import suppress
import asyncio

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.alerts import router as alerts_router
from app.api.fetch import router as fetch_router
from app.api.stats import prewarm_stats_cache, router as stats_router
from app.api.tenders import prewarm_tender_list_cache, router as tenders_router
from app.config import get_settings
from app.database import engine, run_startup_migrations

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    prewarm_task: asyncio.Task | None = None
    mail_scheduler_task: asyncio.Task | None = None
    if settings.run_startup_migrations:
        try:
            await run_startup_migrations()
        except Exception as exc:
            print(f"startup migration skipped: {exc}")
    if settings.prewarm_on_startup:
        try:
            prewarm_task = asyncio.create_task(_prewarm_homepage_caches())
        except Exception as exc:
            print(f"startup prewarm skipped: {exc}")
    if settings.enable_scheduled_mails:
        try:
            from app.tasks.mail_scheduler import run_scheduled_mail_loop

            mail_scheduler_task = asyncio.create_task(run_scheduled_mail_loop())
        except Exception as exc:
            print(f"startup scheduled mail loop skipped: {exc}")
    yield
    if prewarm_task is not None and not prewarm_task.done():
        prewarm_task.cancel()
    if mail_scheduler_task is not None and not mail_scheduler_task.done():
        mail_scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await mail_scheduler_task
    await engine.dispose()


app = FastAPI(
    title="PrintTender India API",
    description="Government tender aggregator for the Indian printing press industry.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(tenders_router, prefix="/api/tenders", tags=["tenders"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
app.include_router(fetch_router, prefix="/api/fetch", tags=["fetch"])


@app.exception_handler(asyncpg.PostgresError)
@app.exception_handler(SQLAlchemyError)
@app.exception_handler(OSError)
@app.exception_handler(asyncio.TimeoutError)
async def database_unavailable_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database is unavailable. Check DATABASE_URL and database connectivity."
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/health/db")
async def database_health_check() -> dict[str, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


async def _prewarm_homepage_caches() -> None:
    await asyncio.gather(
        prewarm_stats_cache(),
        prewarm_tender_list_cache(),
        return_exceptions=True,
    )
