from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.api.fetch import router as fetch_router
from app.api.stats import router as stats_router
from app.api.tenders import router as tenders_router
from app.config import get_settings
from app.database import engine, run_startup_migrations
from backfill_links import backfill_bad_links

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        await run_startup_migrations()
        await backfill_bad_links()
    except Exception as exc:
        print(f"startup migration/backfill skipped: {exc}")
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
app.include_router(fetch_router, prefix="/api/fetch", tags=["fetch"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "env": settings.APP_ENV}
