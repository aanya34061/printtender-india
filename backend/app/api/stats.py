from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AlertSubscription, FetchLog, Tender
from app.schemas import StatsResponse

router = APIRouter()


@router.get("", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_db)) -> StatsResponse:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_active = (
        await session.scalar(select(func.count()).select_from(Tender).where(Tender.is_active.is_(True))) or 0
    )
    tenders_today = (
        await session.scalar(select(func.count()).select_from(Tender).where(Tender.fetched_at >= today_start)) or 0
    )
    portals_count = (
        await session.scalar(
            select(func.count(distinct(Tender.portal_source))).where(Tender.portal_source.is_not(None))
        )
        or 0
    )
    last_fetch = await session.scalar(select(func.max(FetchLog.fetched_at)))

    alert_rows = await session.scalars(
        select(AlertSubscription.keywords).where(AlertSubscription.is_active.is_(True))
    )
    keywords_tracked = len({kw for kws in alert_rows for kw in (kws or [])})

    return StatsResponse(
        total_active=total_active,
        tenders_today=tenders_today,
        portals_count=portals_count,
        last_fetch=last_fetch,
        keywords_tracked=keywords_tracked,
    )


@router.get("/portals/status")
async def portal_status(session: AsyncSession = Depends(get_db)) -> list[dict]:
    # latest fetch log per portal
    subq = (
        select(FetchLog.portal, func.max(FetchLog.fetched_at).label("max_fetched"))
        .group_by(FetchLog.portal)
        .subquery()
    )
    rows = await session.execute(
        select(FetchLog)
        .join(subq, (FetchLog.portal == subq.c.portal) & (FetchLog.fetched_at == subq.c.max_fetched))
    )
    logs = rows.scalars().all()
    return [
        {
            "portal": log.portal,
            "last_fetch": log.fetched_at,
            "status": log.status,
            "tenders_found": log.tenders_found,
        }
        for log in logs
    ]
