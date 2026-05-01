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

    total_active = await session.scalar(select(func.count()).select_from(Tender).where(Tender.is_active.is_(True))) or 0
    tenders_today = await session.scalar(select(func.count()).select_from(Tender).where(Tender.fetched_at >= today_start)) or 0
    portals_count = await session.scalar(select(func.count(distinct(Tender.portal_source))).where(Tender.portal_source.is_not(None))) or 0
    last_fetch = await session.scalar(select(func.max(FetchLog.fetched_at)))

    alert_rows = await session.scalars(select(AlertSubscription.keywords).where(AlertSubscription.is_active.is_(True)))
    keywords_tracked = len({keyword for keywords in alert_rows for keyword in (keywords or [])})

    return StatsResponse(
        total_active=total_active,
        tenders_today=tenders_today,
        portals_count=portals_count,
        last_fetch=last_fetch,
        keywords_tracked=keywords_tracked,
    )
