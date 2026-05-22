from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import asyncio

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.alerts import router as alerts_router
from app.api.stats import router as stats_router
from app.api.tenders import router as tenders_router
from app.config import get_settings
from app.database import engine, run_startup_migrations

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        await run_startup_migrations()
    except Exception as exc:
        print(f"startup migration skipped: {exc}")
    yield
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

app.include_router(tenders_router, prefix="/api/tenders", tags=["tenders"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
if settings.ENABLE_FETCH_API:
    from app.api.fetch import router as fetch_router

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
