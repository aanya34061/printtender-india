from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.api.stats import router as stats_router
from app.api.tenders import router as tenders_router
from app.config import get_settings
from app.database import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup
    yield
    # shutdown
    await engine.dispose()


app = FastAPI(
    title="PrintTender India API",
    description="Government tender aggregator for the Indian printing press industry.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenders_router, prefix="/tenders", tags=["tenders"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
app.include_router(stats_router, prefix="/stats", tags=["stats"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "env": settings.APP_ENV}
