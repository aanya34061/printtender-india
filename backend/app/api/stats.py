from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AlertSubscription, FetchLog, Tender

router = APIRouter()


@router.get("")
async def get_stats(session: AsyncSession = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    seven_days = now + timedelta(days=7)

    total_active = (
        await session.scalar(
            select(func.count()).select_from(Tender).where(Tender.is_active.is_(True))
        )
        or 0
    )
    total_today = (
        await session.scalar(
            select(func.count())
            .select_from(Tender)
            .where(Tender.fetched_at >= today_start)
        )
        or 0
    )
    expiring_7_days = (
        await session.scalar(
            select(func.count())
            .select_from(Tender)
            .where(Tender.is_active.is_(True))
            .where(Tender.bid_end_date > now)
            .where(Tender.bid_end_date <= seven_days)
        )
        or 0
    )
    new_since_yesterday = (
        await session.scalar(
            select(func.count())
            .select_from(Tender)
            .where(Tender.fetched_at >= yesterday_start)
            .where(Tender.fetched_at < today_start)
        )
        or 0
    )
    states_covered = (
        await session.scalar(
            select(func.count(distinct(Tender.state)))
            .where(Tender.is_active.is_(True))
            .where(Tender.state.is_not(None))
        )
        or 0
    )
    last_fetch = await session.scalar(select(func.max(FetchLog.fetched_at)))

    rows = await session.execute(
        select(Tender.portal_source, func.count().label("cnt"))
        .where(Tender.is_active.is_(True))
        .group_by(Tender.portal_source)
    )
    by_portal: dict[str, int] = {}
    for source, cnt in rows:
        label = source or "Unknown"
        by_portal[label] = cnt

    alert_rows = await session.scalars(
        select(AlertSubscription.keywords).where(AlertSubscription.is_active.is_(True))
    )
    keywords_tracked = len({kw for kws in alert_rows for kw in (kws or [])})

    return {
        "total_active": total_active,
        "total_today": total_today,
        "expiring_7_days": expiring_7_days,
        "new_since_yesterday": new_since_yesterday,
        "states_covered": states_covered,
        "by_portal": by_portal,
        "last_fetch": last_fetch,
        "portals_count": len(by_portal),
        "keywords_tracked": keywords_tracked,
    }


@router.get("/portals/status")
async def portal_status(session: AsyncSession = Depends(get_db)) -> list[dict]:
    subq = (
        select(FetchLog.portal, func.max(FetchLog.fetched_at).label("max_fetched"))
        .group_by(FetchLog.portal)
        .subquery()
    )
    rows = await session.execute(
        select(FetchLog).join(
            subq,
            (FetchLog.portal == subq.c.portal)
            & (FetchLog.fetched_at == subq.c.max_fetched),
        )
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
