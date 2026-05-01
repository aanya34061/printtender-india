from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.api.stats import router as stats_router
from app.api.tenders import router as tenders_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="PrintTender India API",
    description="Government tender aggregator for the Indian printing press industry.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenders_router, prefix="/api/tenders", tags=["tenders"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(stats_router, prefix="/api/stats", tags=["stats"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
